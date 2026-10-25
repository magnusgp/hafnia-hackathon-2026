"""Linux CUDA open-vocabulary localization; private configuration and outputs only.

Config: model_id, model_revision, scenes [{name, manifest, start, end, queries,
walkway, walkway_approved}]. No inference submission or dispatch capability.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import time
from datetime import datetime


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('UTC offset required')
    return parsed


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('config', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if platform.node().split('.')[0] != 'p022-linux':
        raise RuntimeError('GPU workloads must run on p022-linux')
    if platform.system() != 'Linux':
        raise RuntimeError('ML execution requires Linux CUDA')
    import numpy as np
    import torch
    import transformers
    from PIL import Image, ImageDraw
    from transformers import OwlViTProcessor, OwlViTForObjectDetection
    from torchvision.ops import nms
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    cfg = json.loads(a.config.read_text())
    model_id, revision = cfg['model_id'], cfg['model_revision']
    processor = OwlViTProcessor.from_pretrained(model_id, revision=revision)
    model = OwlViTForObjectDetection.from_pretrained(model_id, revision=revision,
                                                    use_safetensors=True).eval().cuda()
    a.out.mkdir(parents=True, exist_ok=True)
    for scene in cfg['scenes']:
        manifest = Path(scene['manifest'])
        m = json.loads(manifest.read_text(encoding='utf-8-sig'))
        frames = [f for f in m['frames'] if utc(scene['start']) <= utc(f['timestamp_utc']) < utc(scene['end'])]
        if not frames:
            raise ValueError('No frames in requested interval')
        polygon = scene['walkway']
        if len(polygon) < 3 or any(len(xy) != 2 or any(v < 0 or v > 1 for v in xy) for xy in polygon):
            raise ValueError('Invalid walkway polygon')
        observations, previous, reference, sheet = [], None, None, None
        for i, f in enumerate(frames):
            path = (manifest.parent / f['file']).resolve()
            if not path.is_relative_to(manifest.parent.resolve()):
                raise ValueError('Frame path escapes acquisition directory')
            digest = sha(path)
            if f.get('sha256') and digest != f['sha256']:
                raise ValueError('Frame hash mismatch')
            im = Image.open(path).convert('RGB')
            w, h = im.size
            arr = np.asarray(im).astype(float)
            gray = arr.mean(axis=2)
            mask = Image.new('1', im.size)
            ImageDraw.Draw(mask).polygon([(x*w,y*h) for x,y in polygon], fill=1)
            region = np.asarray(mask, dtype=bool)
            if reference is None:
                reference = gray.copy()
            inputs = processor(text=[scene['queries']], images=im, return_tensors='pt').to('cuda')
            torch.cuda.synchronize()
            tick = time.perf_counter()
            with torch.inference_mode():
                outputs = model(**inputs)
            torch.cuda.synchronize()
            elapsed = time.perf_counter()-tick
            result = processor.post_process_object_detection(outputs, threshold=0.10,
                        target_sizes=torch.tensor([[h,w]], device='cuda'))[0]
            keep = nms(result['boxes'], result['scores'], 0.5)
            objects = []
            draw = ImageDraw.Draw(im)
            draw.polygon([(x*w,y*h) for x,y in polygon], outline='cyan', width=3)
            for k in keep.cpu().tolist():
                b = result['boxes'][k].detach().cpu().tolist()
                b = [max(0,min(w,b[0])),max(0,min(h,b[1])),max(0,min(w,b[2])),max(0,min(h,b[3]))]
                x0,y0,x1,y1 = map(int,b)
                overlap = float(region[y0:y1,x0:x1].mean()) if x1>x0 and y1>y0 else 0
                obj = dict(box=[b[0]/w,b[1]/h,b[2]/w,b[3]/h],
                    score=float(result['scores'][k]),query=scene['queries'][int(result['labels'][k])],
                    box_walkway_overlap=overlap)
                objects.append(obj)
                draw.rectangle(b, outline='lime', width=3)
                draw.text((x0,max(0,y0-14)), f"{obj['score']:.2f} overlap {overlap:.2f}",fill='yellow')
            baseline = dict(frame_difference=None if previous is None else float((np.abs(gray-previous)[region]>25).mean()),
                            reference_change=float((np.abs(gray-reference)[region]>25).mean()))
            observations.append(dict(timestamp_utc=f['timestamp_utc'],file=f['file'],sha256=digest,
                objects=objects,baseline=baseline,detector_s=elapsed))
            previous = gray
            tile = im.resize((480,270))
            if sheet is None:
                sheet = Image.new('RGB',(480*3,300*((len(frames)+2)//3)))
            x,y = i%3*480,i//3*300
            sheet.paste(tile,(x,y))
            ImageDraw.Draw(sheet).text((x,y+272),f['timestamp_utc'], fill='white')
        report = dict(schema_version=1,scene=scene,source_manifest=m,manifest_sha256=sha(manifest),
            runner_sha256=sha(__file__),config_sha256=sha(a.config),model=model_id,model_revision=revision,
            torch=torch.__version__,transformers=transformers.__version__,host=platform.node(),
            device=torch.cuda.get_device_name(),execution_device='cuda',execution_platform=platform.system(),
            score_threshold=0.10,nms_iou=0.5,observations=observations,
            limitations=['Scores are not calibrated confidence. Box overlap is not object-mask overlap.',
                'Draft walkway requires operator approval; no metric clearance or pedestrian accessibility inferred.',
                'No interpolation across missing observations. Same synthetic scene is not independent validation.',
                'Reference change includes lighting, people and background changes; first frame is not empty background.',
                'No automatic dispatch; no inference about intent or persistence after the last measured frame.'])
        (a.out/(scene['name']+'.json')).write_text(json.dumps(report,indent=2))
        sheet.save(a.out/(scene['name']+'.jpg'))
        print(scene['name'],len(frames),'frames',sum(bool(x['objects']) for x in observations),'localized',flush=True)


if __name__ == '__main__':
    main()
