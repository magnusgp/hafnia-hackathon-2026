# Adaptive Watch

A second signal for Milestone XProtect. Hafnia reads recorded video and sometimes answers "no" for something that
deserves a look. Adaptive Watch runs independent computer vision on the same recording for one configured condition.
When Hafnia says no and the detector sees the condition, it builds a **review exception** (camera, recording, moment,
both signals) and sends it into XProtect, where the operator already works.

It is not a second summarizer, an incident manager or a model comparison. Hafnia's answer stays on record. The new
thing is a way to stop a negative answer from being the last word.

## What happens in the flagship case

A person in a red jacket sits on a station platform edge, climbs down onto the tracks and walks away (22 Oct 2026,
11:03:39 to 11:03:52 UTC, camera `person_on_railway_tracks`).

1. XProtect recorded the scene.
2. Hafnia answered `not_observed` for entry onto the tracks.
3. A person detector on the Linux A10G placed the person at the platform edge from 11:03:44.5, about 3.8 s before the
   climb. This is a proximity trigger. It does not claim entry.
4. Adaptive Watch built the review exception. A separate footage review (by an AI, labelled as such) found the person
   reaching the track bed at 11:03:48.3.
5. The operator inspects the footage and requests the XProtect review. Adaptive Watch sends the
   `Adaptive Watch Review Required` analytics event for that camera. XProtect raises its own alarm.

## Open it on the judge machine (p022)

The application runs on the hackathon Windows machine and is opened **inside p022** (over Remote Desktop).
`localhost` on any other computer does not reach it.

```powershell
cd C:\Users\Administrator\dev\hafnia-hackathon-2026
powershell -ExecutionPolicy Bypass -File scripts\launch.ps1 -Demo
```

`-Demo` opens an isolated copy of the flagship case in its pending state, so a judge can walk the whole flow without
touching the operator's own saved decision. Without `-Demo` the launcher opens the real saved state (review request
saved, alarm 4 sent). Edge opens `http://127.0.0.1:8780/#/railway`. Close the window to stop it. If `frontend\dist` is
missing the launcher builds it first.

1. The **Station platform** exception is already selected and the footage is paused on the trigger sample.
2. Press **Play from the trigger**. The person climbs down about four seconds later.
3. Click a signal on the right (Hafnia, Local vision, Footage review) to jump to its moment. The three lanes under the
   footage show what each source said and when.
4. **Send to XProtect review** saves your review request. The next step, **Send to XProtect**, shows the exact event and
   its fingerprint and needs a second confirmation (add `-NativeSend` to the launch command to enable it). The duplicate
   ledger refuses a second send of an event that was already sent.
5. Open Smart Client, Alarm Manager, to see the alarm.

The other tabs are secondary evidence: the school gate (Hafnia prompts disagree, saved snapshots only, no local vision),
and the scooter and bin (local vision measured how long each stayed still; Hafnia agreed). They are not railway
false-negative validations.

Optional: `scripts\launch.ps1 -AssessmentLogin` asks once in that window for the Hafnia gateway password (kept in memory,
never sent to the browser) and enables **New assessment**, which acquires the latest 15 s of the camera from XProtect,
runs the A10G detector, asks Hafnia once and compares them. See [docs/adaptive-watch/new-assessment.md](docs/adaptive-watch/new-assessment.md).

## How XProtect, Hafnia and the GPU each contribute

| System | Job |
|---|---|
| XProtect Corporate 2026 R1 | Records and plays back the scene; receives the Analytics Event (Event Server, port 9090); raises the camera-specific alarm the operator works from. |
| Hafnia VLM | Reads the recording through the local gateway and answers in words, including when the answer is no. |
| Linux A10G vision | Watches the same footage for one configured condition and keeps its own record. |

Built during the hackathon: the detector pipeline and tracker, the Hafnia/vision comparison, source-integrity checks and
case-scoped review storage, the review interface, the guarded native handoff (ledger-protected, never retried), the job
runner for New assessment, and the presentation.

## Native XProtect status (verified 28 Oct 2026)

- Analytics Event `Adaptive Watch Review Required` and alarm definition `Adaptive Watch review: station platform`
  (scoped to the one camera) were created ([script](scripts/xprotect/setup_review_alarm.ps1)).
- Two events were sent, each once, through the app's confirmation dialog and the duplicate ledger: the saved flagship case
  (source time 22 Oct 11:03:44) and a **live assessment started from the browser** (source time 28 Oct 15:34:29, with the
  detector's bounding box). The Event Server accepted both. **Smart Client's Alarm Manager lists alarms 4 and 5** with the
  right camera, message and source time.
- **Not verified:** playback association and bounding-box overlay. In both cases Smart Client's alarm preview shows
  "The camera is not available", although XProtect holds recording at the live alarm's source time. This was not
  investigated further (a camera or alarm-definition preview setting is the likely place to look).

## Live assessment (verified 28 Oct 2026)

Started from the browser with `-AssessmentLogin`: a fresh 13 s window of `person_on_railway_tracks` was acquired from
XProtect (chosen to avoid the camera's 15 s loop seam), a person detector ran on the A10G (26 frames in 2.4 s), and one
Hafnia request answered `not observed`; the detector placed a person at the platform edge from 15:34:29.5. The continuity
confirmation for that run was given by the Claude demo reviewer after viewing every snapshot, not by a human.

## Limits

The evidence comes from controlled synthetic camera scenarios. There is no accuracy benchmark, no measured reduction in
missed events and no production deployment. The attention region is a draft. The camera replays a 15 s clip on a loop.

## Repository

```
adaptive_watch/        casebook, review store, native handoff, job runner, API server
scene_contracts/       Hafnia gateway client and the Event Server serializer and ledger
frontend/              React 19, TypeScript, Vite application and browser checks
presentation/          standalone HTML/CSS/JS deck, narration, timing, render script
scripts/               acquisition, vision, launch and XProtect setup
docs/                  product definition, submission copy, storyboard, evidence notes
```

Source CCTV, credentials, raw Hafnia responses, identity files, model weights, review databases and captures are private
and ignored by Git. A clone alone cannot show the saved cases; they need the original files on p022.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
cd frontend; ..\runs\tooling\bun-windows-x64\bun.exe run build
```

See [docs/adaptive-watch/product-definition.md](docs/adaptive-watch/product-definition.md) for the design reasoning and
[docs/submission/](docs/submission/) for the submission package. Earlier workflows are kept in
[docs/adaptive-watch/prior-workflow.md](docs/adaptive-watch/prior-workflow.md) and
[docs/adaptive-watch/single-case-readme.md](docs/adaptive-watch/single-case-readme.md).
