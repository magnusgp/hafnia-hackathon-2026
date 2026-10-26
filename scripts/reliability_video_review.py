"""Decode every exported video frame for local private visual continuity review.

No inference, interpolation, transcoding of source, or assertion of absolute PTS origin.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--deps',type=Path,help='Optional isolated directory containing pinned PyAV/Pillow')
    a=p.parse_args()
    if a.deps:sys.path.insert(0,str(a.deps.resolve()))
    import av
    from PIL import Image,ImageDraw
    frames=[];pts=[]
    with av.open(str(a.video)) as container:
        for f in container.decode(video=0):
            if f.pts is None:raise ValueError('Missing PTS')
            pts.append(float(f.pts*f.time_base))
            frames.append(f.to_image().resize((240,139)))
    if not pts or any(b<=a for a,b in zip(pts,pts[1:])):raise ValueError('Nonmonotonic or empty stream')
    sheet=Image.new('RGB',(240*8,160*((len(frames)+7)//8)))
    draw=ImageDraw.Draw(sheet)
    for i,frame in enumerate(frames):
        x=i%8*240;y=i//8*160
        sheet.paste(frame,(x,y));draw.text((x,y+140),f'{i}: PTS {pts[i]:.3f}s',fill='white')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    image=a.out.with_suffix('.jpg')
    sheet.save(image)
    result=dict(mkv_sha256=hashlib.sha256(a.video.read_bytes()).hexdigest(),decoded_frames=len(frames),
                pts_s=pts,sheet_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                continuity='Requires visual review of decoded sheet',absolute_pts_origin='unverified')
    a.out.with_suffix('.json').write_text(json.dumps(result,indent=2))
    print('Decoded',len(frames),'frames; first/last PTS',pts[0],pts[-1])


if __name__=='__main__':main()
