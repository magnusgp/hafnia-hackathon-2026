"""Package genuine saved footage, CV samples and the captured operator flow (<3 min)."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from adaptive_watch.negative_review import ReviewStore, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT/'runs/negative-result-review')
    p.add_argument('--captures',type=Path,default=ROOT/'runs/negative-review-checks')
    p.add_argument('--decode-deps',type=Path)
    a=p.parse_args()
    if a.decode_deps:sys.path.insert(0,str(a.decode_deps.resolve()))
    import av
    from PIL import Image, ImageDraw, ImageFont
    store=ReviewStore(a.root)
    try:
        record,_=store.verified();view=store.view()
        browser_report=json.loads((a.captures/'browser-report.json').read_text())
        operator=next(r for r in browser_report if r['width']==1920)
        if operator['durationSeconds']>=140:raise ValueError('Operator capture leaves insufficient footage budget')
        output_path=a.captures/'adaptive-watch-negative-review.mp4'
        font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',27)
        segments=[];count=0
        with av.open(str(output_path),'w') as output:
            stream=output.add_stream('libx264',rate=10)
            stream.width,stream.height,stream.pix_fmt=1920,1080,'yuv420p'
            stream.options=dict(crf='20',preset='fast')

            def emit(image,title):
                nonlocal count
                if count>=1800:raise ValueError('Submission video would exceed three minutes')
                canvas=Image.new('RGB',(1920,1080),'#0A1524')
                image=image.copy();image.thumbnail((1920,1028),Image.Resampling.LANCZOS)
                canvas.paste(image,((1920-image.width)//2,52+(1028-image.height)//2))
                ImageDraw.Draw(canvas).text((30,8),title,font=font,fill='#EAF1FA')
                frame=av.VideoFrame.from_image(canvas);frame.pts=count;frame.time_base=Fraction(1,10)
                for packet in stream.encode(frame):output.mux(packet)
                count+=1

            def video(path,title):
                first=None;next_time=0.;start=count
                with av.open(str(path)) as source:
                    for decoded in source.decode(video=0):
                        now=float(decoded.pts*decoded.time_base)
                        if first is None:first=now
                        relative=now-first
                        if relative+.0001<next_time:continue
                        image=decoded.to_image()
                        while next_time<=relative+.0001:
                            emit(image,title);next_time+=.1
                segments.append(dict(source=str(path),sha256=sha(path),startSeconds=start/10,endSeconds=count/10))

            video(record['originalVideo'],'Original XProtect export | Requested interval: 22 Oct 2026, 11:03:39–11:03:52 UTC')
            begin=count
            for source,measured in zip(record['frames'],view['frames']):
                with Image.open(source['path']) as raw:image=raw.convert('RGB')
                w,h=image.size;draw=ImageDraw.Draw(image)
                polygon=[(x*w,y*h) for x,y in view['state']['region']['polygon']]
                draw.line(polygon+[polygon[0]],fill='#8CB3FF',width=2)
                if source['box']:
                    left,top,right,bottom=source['box']
                    draw.rectangle((left*w,top*h,right*w,bottom*h),outline='#FFD185',width=2)
                    draw.ellipse(((left+right)/2*w-3,bottom*h-3,(left+right)/2*w+3,bottom*h+3),fill='#FFD185')
                title=f'Independent CV | Track 7 proximity | {source["timestamp"]} | 0.5 s samples'
                for _ in range(5):emit(image,title)
            segments.append(dict(source='Original timestamped JPEGs + unchanged saved track 7 boxes',startSeconds=begin/10,endSeconds=count/10,frameHashes=[f['sha256'] for f in record['frames']]))
            video(operator['recording'],'Operator workflow | Saved negative Hafnia assessment → human review → local review request')
            for packet in stream.encode():output.mux(packet)
        with av.open(str(output_path)) as encoded:
            duration=float(encoded.duration/av.time_base)
        if not 0<duration<180:raise ValueError('Invalid final submission duration')
        result=dict(file=str(output_path),sha256=sha(output_path),durationSeconds=duration,fps=10,segments=segments,
            noNewInference=True,nativeEventSent=False,humanEntryVerification='Not supplied; browser walkthrough is automated',
            originalEvidenceIntegrity='All persisted source hashes reverified before packaging')
        (a.captures/'submission-video.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(file=str(output_path),durationSeconds=duration,sha256=result['sha256'])))
    finally:store.close()


if __name__=='__main__':main()
