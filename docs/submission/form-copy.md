# Submission form copy

Fields not supplied by the team are left as placeholders on purpose. Submission deadline: Monday, 2 November 2026 at 11:00 CET.

**Project name:** Adaptive Watch

**One line:** A second signal for XProtect: when Hafnia says no but independent vision sees the condition, the operator gets a review exception inside XProtect.

**Problem:** A negative AI assessment is silent. Hafnia can read a recording and answer "no entry" for a scene where a person sat at a platform edge and then climbed down. Nothing in the workflow tells an operator that a second look is worth taking.

**What we built:** Adaptive Watch runs independent person detection on a Linux A10G GPU over the same XProtect recording, compares it with Hafnia's answer, and builds a review exception: the right camera, the recording, the moment, both signals and a next step. A browser interface lets the operator inspect the footage with the detector's box and region at the sampled moments, and request the XProtect review. A guarded handoff sends a dedicated analytics event to the XProtect Event Server, which raises a camera-specific alarm.

**How we use XProtect:** Recordings and snapshots come from XProtect (MilestonePSTools). The review travels back as a documented Analytics Event over the Event Server protocol, matched to an Analytics Event and an alarm definition we created for that camera. The operator keeps working in Smart Client's Alarm Manager. Verified: alarms 4 (saved case) and 5 (a live assessment started from the browser) for `person_on_railway_tracks` appear in Smart Client's Alarm Manager. Not verified: playback association and the bounding-box overlay. Smart Client's alarm preview reports the camera as not available for both alarms; retention explains the old alarm but not the live one, and the cause is still being isolated.

**How we use Hafnia VLM:** Hafnia reads each recording through the local gateway (a live assessment from the browser made one real request on 28 Oct) and its answer, including a negative one, is the first signal. Its original request and response are kept with the case and shown next to the detector. We make one request per assessment and guard against duplicates.

**Why it adds value:** It gives a negative answer a second opinion that does not depend on the same model, and turns a disagreement into work in the tool operators already use. It does not replace Hafnia or XProtect alarms.

**What was original hackathon work:** The detector pipeline and tracker, the comparison logic, source-integrity checks and case-scoped review storage, the review interface, the guarded XProtect handoff with a duplicate-send ledger, the New assessment job runner, the presentation and this package.

**Evidence and limits:** Controlled synthetic camera scenarios only. No accuracy benchmark, no measured reduction in missed events, no production deployment. The flagship case is a single scripted clip; the detector trigger is a proximity observation, not a trespass classification. The footage review and the live run's continuity confirmation were made by an AI reviewer (Claude, demo reviewer), not a human, and are labelled that way.

**Source:** https://github.com/magnusgp/hafnia-hackathon-2026 (branch `release/adaptive-watch-submission`, pushed to origin; not yet merged to `main`).

**Judge access:** Remote Desktop to the existing Windows machine p022, then `scripts\launch.ps1` (see README). The application opens at `http://127.0.0.1:8780` inside p022; localhost does not reach it from another computer.

**Supporting materials:** README, [storyboard](storyboard.md), [product definition](../adaptive-watch/product-definition.md), presentation source in `presentation/`, release manifest (`docs/submission/release-manifest.json`).

**Video URL:** `<to be published by the team>`  (local file: `runs/release/adaptive-watch-submission.mp4`)

**Team members / contact:** `<to be supplied by the team>`
