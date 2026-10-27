"""Derive a timestamp-faithful video from saved originals; no inference or network."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from adaptive_watch.negative_review import ReviewStore, build_record, read, sha


def verify_media(video_path,frames):
    import av
    from PIL import Image, ImageChops, ImageStat
    errors = []
    with av.open(str(video_path)) as encoded:
        decoded = list(encoded.decode(video=0))
    if len(decoded) != len(frames):
        raise ValueError('Encoded sample count changed')
    for i,(actual,original) in enumerate(zip(decoded,frames)):
        if abs(float(actual.pts*actual.time_base)-i*.5) > .0001:
            raise ValueError('Encoded video timestamps differ from the source sample clock')
        with Image.open(original['path']) as image:
            error = sum(ImageStat.Stat(ImageChops.difference(actual.to_image().convert('RGB'),image.convert('RGB'))).mean)/3
        if error > 8:
            raise ValueError('Encoded image does not match its original sample')
        errors.append(error)
    return dict(verifiedDecodedFrames=len(decoded),ptsVerified=True,maximumMeanPixelError=max(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT/'runs/negative-review')
    parser.add_argument('--response',type=Path,required=True)
    parser.add_argument('--decode-deps',type=Path)
    args = parser.parse_args()
    if args.decode_deps:
        sys.path.insert(0,str(args.decode_deps.resolve()))
    import av
    from PIL import Image
    store = ReviewStore(args.root)
    try:
        if store.db.execute('SELECT 1 FROM review').fetchone():
            existing = store.view()
            record,_ = store.verified()
            verification = verify_media(record['media']['path'],record['frames'])
            (args.root/'media-validation.json').write_text(json.dumps(verification,indent=2))
            print(json.dumps(dict(status='existing_verified',id=existing['id'],revision=existing['revision'],media=verification)))
            return
        manifest_path = ROOT/'runs/xprotect/person_on_railway_tracks_20261022T110339Z/manifest.json'
        manifest = read(manifest_path)
        frames = manifest['frames']
        # Verify every original before decoding; the manifest's .013 UTC origin is retained.
        for f in frames:
            if sha(manifest_path.parent/f['file']) != f['sha256']:
                raise ValueError('Original frame hash mismatch')
        target = args.root.resolve()/'media'
        target.mkdir(parents=True,exist_ok=True)
        video_path = target/'railway-samples.mp4'
        with Image.open(manifest_path.parent/frames[0]['file']) as image:
            width,height = image.size
        with av.open(str(video_path),'w') as output:
            stream = output.add_stream('libx264',rate=2)
            stream.width,stream.height,stream.pix_fmt = width,height,'yuv420p'
            stream.options = dict(crf='18',preset='medium')
            for i,f in enumerate(frames):
                with Image.open(manifest_path.parent/f['file']) as image:
                    frame = av.VideoFrame.from_image(image.convert('RGB'))
                frame.pts,frame.time_base = i,Fraction(1,2)
                for packet in stream.encode(frame):
                    output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)
        # Verify the encoded media's actual PTS and order, rather than assuming encoder behavior.
        verification = verify_media(video_path,[dict(path=str(manifest_path.parent/f['file'])) for f in frames])
        (target/'media.json').write_text(json.dumps(dict(sha256=sha(video_path),frameHashes=[f['sha256'] for f in frames],
            fps=2,duration=len(frames)/2,width=width,height=height,utcOrigin=frames[0]['timestamp_utc'],
            method='Original snapshots encoded in timestamp order; no interpolation; no MKV PTS-to-UTC assumption',
            **verification),indent=2))
        record = build_record(ROOT,args.response,target)
        view = store.install(record)
        # Review record export retains all original hashes and absolute private paths outside Git.
        (args.root/'review-record.private.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        (args.root/'native-event-proposal.private.json').write_text(json.dumps(dict(
            eventName=record['native']['eventName'],cameraGuid=record['cameraGuid'],interval=record['interval'],
            summaryId=record['hafnia']['summaryId'],configured=False,dispatchAuthorized=False,
            description='Human review requested after a negative Hafnia assessment and independent image-space proximity observation. Entry is not automatically confirmed.',
            requiredApprovals=['Explicit event and alarm definition configuration authorization','Separate approval of one native dispatch'],
            requiredVerification=['Actual Smart Client alarm','Associated source camera','Playback of the observed interval']),indent=2),encoding='utf-8')
        print(json.dumps(dict(status='imported_verified',id=view['id'],samples=len(frames),trigger=view['trigger']['timestamp'])))
    finally:
        store.close()


if __name__ == '__main__':
    main()
