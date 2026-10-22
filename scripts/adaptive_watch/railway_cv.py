"""Linux CUDA-only pretrained detector POC; private timestamped evidence output.

Install with ~/.local/bin/uv pip install --python .venv/bin/python torchvision==0.20.1 --no-deps
Run from repository root: .venv/bin/python scripts/adaptive_watch/railway_cv.py MANIFEST --zone ZONE_JSON --out OUTPUT
Zone coordinates are normalized image coordinates, explicitly reviewed by an operator before dispatch.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adaptive_watch.tracking import Tracker


def main():
    p = argparse.ArgumentParser()
    p.add_argument('manifest', type=Path)
    p.add_argument('--zone', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if platform.system() != 'Linux':
        raise RuntimeError('Run substantial ML on Linux only')
    import numpy as np
    import torch
    import torchvision
    from PIL import Image
    from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2, FasterRCNN_ResNet50_FPN_V2_Weights
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    from adaptive_watch.footage import load_manifest, parse_utc
    m = load_manifest(a.manifest)
    zone = json.loads(a.zone.read_text())
    polygon = zone['polygon']
    if len(polygon) < 3 or any(not (0 <= v <= 1) for xy in polygon for v in xy):
        raise ValueError('Invalid normalized zone polygon')
    torch.manual_seed(0)
    weights = FasterRCNN_ResNet50_FPN_V2_Weights.COCO_V1
    start = time.perf_counter()
    model = fasterrcnn_resnet50_fpn_v2(weights=weights).eval().cuda()
    torch.cuda.synchronize()
    model_load_s = time.perf_counter()-start
    tracker, observations, timings, baselines = Tracker(), [], [], []
    previous = None
    start = time.perf_counter()
    for i,f in enumerate(m['frames']):
        if f.get('sha256') and hashlib.sha256((a.manifest.parent / f['file']).read_bytes()).hexdigest() != f['sha256']:
            raise ValueError('Recorded frame hash mismatch')
        with Image.open(a.manifest.parent / f['file']) as im:
            arr = np.asarray(im.convert('RGB')).copy()
        h,w = arr.shape[:2]
        tensor = torch.from_numpy(arr).permute(2,0,1).float().div(255).cuda()
        with torch.inference_mode():
            if i == 0:
                model([tensor])
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
            tick = time.perf_counter()
            output = model([tensor])[0]
            torch.cuda.synchronize()
            timings.append(time.perf_counter()-tick)
        ds = []
        for b,s,c in zip(output['boxes'].cpu().tolist(),output['scores'].cpu().tolist(),output['labels'].cpu().tolist()):
            if c == 1 and s >= 0.5:
                ds.append(dict(box=[b[0]/w,b[1]/h,b[2]/w,b[3]/h],score=s))
        t = parse_utc(f['timestamp_utc']).timestamp()
        observations.append(dict(timestamp_utc=f['timestamp_utc'],objects=tracker.update(t,ds,polygon)))
        # Simple motion baseline: per-pixel change inside exactly the same zone. No person semantics.
        tick = time.perf_counter()
        from PIL import ImageDraw
        mask = Image.new('1',(w,h))
        ImageDraw.Draw(mask).polygon([(int(x*w),int(y*h)) for x,y in polygon],fill=1)
        region = np.asarray(mask,dtype=bool)
        gray = arr.mean(axis=2)
        changed = None if previous is None else float((np.abs(gray-previous)[region]>25).mean())
        baselines.append(dict(timestamp_utc=f['timestamp_utc'],changed_zone_fraction=changed,elapsed_s=time.perf_counter()-tick))
        previous = gray
    elapsed = time.perf_counter()-start
    checkpoint = Path(torch.hub.get_dir())/'checkpoints'/Path(weights.url).name
    report = dict(schema_version=1,host=platform.node(),device=torch.cuda.get_device_name(),
        revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        tracker_sha256=hashlib.sha256((Path(__file__).resolve().parents[2]/'adaptive_watch/tracking.py').read_bytes()).hexdigest(),
        torch=torch.__version__,torchvision=torchvision.__version__,model='fasterrcnn_resnet50_fpn_v2',weights=weights.name,
        weights_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),source_manifest=m,
        manifest_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),zone=zone,
        model_load_s=model_load_s,processing_s=elapsed,frames=len(observations),
        detector_ms_per_frame=1000*sum(timings)/len(timings),
        detector_p95_ms=1000*float(np.percentile(timings,95)),peak_vram_mib=torch.cuda.max_memory_allocated()/2**20,
        observations=observations,tracks=tracker.measurements(),motion_baseline=baselines,
        limitations=['Pretrained inference plus handwritten tracking; no custom neural training.',
        'Detection score is not calibrated probability; misses and false detections possible.',
        'Greedy association can switch identities; foot is bounding-box bottom, not anatomical feet.',
        'Zone is a provisional developer polygon until operator approval; image distance is not metres.',
        'Consecutive in-zone sample pairs only; not proven continuous physical occupancy.',
        'One synthetic scene, no independent accuracy estimate; no incident or dispatch decision.'])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('host','device','revision','frames','detector_ms_per_frame','processing_s','tracks')},indent=2))


if __name__ == '__main__':
    main()
