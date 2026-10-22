"""Private contact sheets for manual loop-boundary review; never model labels."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
a = p.parse_args()
for manifest in a.root.rglob('manifest.json'):
    m = json.loads(manifest.read_text(encoding='utf-8-sig'))
    frames = m['frames']
    sheet = Image.new('RGB', (4 * 312, ((len(frames)+3)//4)*200))
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        x, y = i % 4 * 312, i // 4 * 200
        with Image.open(manifest.parent / f['file']) as im:
            sheet.paste(im.resize((312,180)), (x,y))
        draw.text((x,y+180), f"{i}: {f['timestamp_utc'][11:23]}", fill='white')
    sheet.save(manifest.parent / 'contact.jpg')
