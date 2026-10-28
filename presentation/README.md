# Presentation

Standalone HTML, CSS and JavaScript. Open `index.html` in a browser (Edge on p022). Arrow keys or space move between
scenes, `f` toggles fullscreen, `c` toggles captions. `?auto=1` runs the timed film from `timing.json`.

The footage, narration audio and captures live in git-ignored `assets/` because they are private recordings. Rebuild them on p022:

```powershell
.\.venv\Scripts\python.exe presentation\prepare_assets.py           # footage and detector samples from the verified case
powershell -ExecutionPolicy Bypass -File presentation\synthesize.ps1  # narration with the local Windows voice
.\.venv\Scripts\python.exe presentation\build_timing.py <operator_capture_seconds> "<proof line>"
```

Then record the application (`frontend/scripts/capture-walkthrough.mjs`), convert it with `render.py convert`, record the
deck (`frontend/scripts/record-deck.mjs`) and mux with `render.py mux`. The narration script is `narration.json`; the
timed storyboard is in `docs/submission/storyboard.md`.
