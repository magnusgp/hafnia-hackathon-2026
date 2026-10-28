"""Write docs/submission/storyboard.md from timing.json and narration.json."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
timing = json.loads((root/'timing.json').read_text(encoding='utf-8'))
text = {s['id']: s['text'] for s in json.loads((root/'narration.json').read_text(encoding='utf-8'))['scenes']}
shows = dict(
    open="Real railway footage from XProtect. The person sits, then climbs down. Hafnia's answer card appears: No entry observed.",
    silent='Light slide: "A no is silent." The climb replays faintly beside it.',
    signal='Footage paused on the detector sample at 11:03:44.5 with box and region, then stepped through the real 2 Hz samples to the climb. 3.8 s label.',
    how='Diagram: XProtect records; Hafnia reads; Linux A10G watches; Adaptive Watch compares; review exception; XProtect alarm.',
    operator='Real screen capture of the application: open at the trigger, play to the climb, jump between signals, save the review request, preview the XProtect send (cancelled).',
    live='Real screenshot of the live assessment started from the browser (28 Oct 15:34 UTC): same flow, fresh recording, one Hafnia request.',
    xprotect='Real Smart Client Alarm Manager capture after a client restart: alarm 5 (live run) selected, its preview playing the recording with the detector box; alarm 4 (saved case) is past retention. Line on screen: live and recorded playback of the camera verified.',
    built='Three cards: XProtect, Hafnia VLM, Linux GPU vision. Footer: what was built.',
    close='"A negative AI assessment no longer has to be the end of the review." One small line on the synthetic-scenario limit.')
mmss = lambda x: f"{int(x // 60)}:{x % 60:04.1f}"
out = ['# Storyboard and timing', f"Total {timing['total']:.1f} s, 1920x1080, local Windows voice (Microsoft David), burned-in captions.\n",
       '| Time | Scene | On screen | Narration |', '|---|---|---|---|']
for s in timing['scenes']:
    out.append(f"| {mmss(s['start'])} to {mmss(s['start'] + s['dur'])} | {s['id']} | {shows[s['id']]} | {text[s['id']]} |")
out += ['', "The first ten seconds work without sound: the footage shows the climb, the caption states it, and Hafnia's answer card appears at 5 s.", '',
        'Narration script: [presentation/narration.json](../../presentation/narration.json). Source: [presentation/](../../presentation/).']
Path(root.parent/'docs/submission/storyboard.md').write_text('\n'.join(out), encoding='utf-8')
