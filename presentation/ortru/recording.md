# Recording the Ortru walkthrough

No screen recorder was found on p022, and no video or synthesized speech has been produced. Record on a machine you control.
The earlier 177-second film (`presentation/`) is untouched.

## Before

1. On p022 run `scripts\ortru.ps1 -Gateway` and type the Hafnia gateway password yourself in the server window. Leave sending
   off unless you intend a real, confirmed event.
2. Open `presentation/ortru/index.html` in Edge. Press `F` for full screen, `N` for the notes dock, `S` for a presenter window
   that follows the main one (notes, next slide, timer).
3. Real screenshots live in `presentation/ortru/media/` (private, ignored by Git). Regenerate with
   `bun frontend/scripts/shoot-real.mjs ../presentation/ortru/media` while the server runs.

## Capture

- Option A, simplest: record the RDP window on your own computer with OBS (Window Capture) at 1920x1080, microphone on.
- Option B: run OBS inside p022 if you install it; capture the Edge window.
- Two scenes: the deck (full screen) and the live app at `http://127.0.0.1:8790` for an optional live segment between slides 6
  and 8.

## Take

1. Read [narration.md](narration.md); target 3 minutes.
2. Advance with Right arrow or Space; each press reveals the next step, then the next slide.
3. Do not send a diagnostic alarm to make the take look better. The deck's native slide describes events verified earlier.
4. Export MP4 from OBS. Keep it private until the owner approves publication.
