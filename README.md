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
  "The camera is not available". Findings of the 28 Oct investigation (read-only, nothing sent or changed):
  - Alarm 4's source time (22 Oct) is before the retained recording (27 Oct 17:13 onward), so retention explains alarm 4.
    It does **not** explain alarm 5: its source time (28 Oct 15:34:29 UTC) lies inside one continuous recording sequence
    (27 Oct 17:13:39 to 28 Oct 18:02 UTC), and live snapshots of the camera are retrievable for the same operator.
  - Both alarms carry the correct `CameraId` and `SourceId`. A missing `ServerId` in the event's source FQID is **not** the
    cause on its own: alarm 3 (camera `vandalism`, sent 22 Oct by the same serializer, also without a `ServerId`) does show
    a camera preview. In a MIP camera FQID the `ServerId` is the *management* server (`XPCO`), not the recording server.
  - **Tested and refuted:** test alarm 6 (28 Oct 18:17:34 UTC, source time inside the recording, event source FQID with the
    full management-server `ServerId` block `XPCO`/`p022`/80/`9d4de506-...`) also shows "The camera is not available".
    The serializer now supports the full block (tested), but the missing `ServerId` is not the cause.
  - **Strongest lead:** the Adaptive Watch alarm definition has `MapType = 2` (Smart Map); `Visually Observed Damage`, whose
    preview works, has `MapType = 1` (Map). For our alarms Smart Client's map pane says the source must be added to the
    smart map. Changing `MapType` (and possibly removing the related-camera entry) on our own definition is the next test.
    It has **not** been done: the session's permission classifier denied the configuration write. The prior definition is
    saved in `runs/release/native/alarm-definition-before-maptype.json` (private).
  - Differences still open: the Adaptive Watch alarm definition lists the camera as a related camera while
    `Visually Observed Damage` does not; alarms 1 to 3 carry a snapshot icon, alarms 4 and 5 do not; the Smart Client
    alarm-preview settings (Show event source cameras, Show related cameras) and Smart Client's own log were not
    readable from this session. The root cause is therefore **unresolved**. Any fix needs a definition change or a new
    test event, both of which are waiting for operator approval.

## Live assessment (verified 28 Oct 2026)

Started from the browser with `-AssessmentLogin`: a fresh 13 s window of `person_on_railway_tracks` was acquired from
XProtect, a person detector ran on the A10G (26 frames in 2.4 s), and one
Hafnia request answered `not observed`; the detector placed a person at the platform edge from 15:34:29.5. The continuity
confirmation for that run was given by Claude (an AI) as demo reviewer, not by a human.

**Continuity review of that interval (28 Oct 15:34:25 to 15:34:38 UTC).** The camera replays a 15 s clip that is visually
seamless: the step from its last frame to its first is no larger than neighbouring steps, and the next walk-in starts
about 13.3 s into the clip. Frame by frame, the live snapshots at clip positions 1.0 to 12.5 s are identical to the saved
22 Oct reference. The last snapshot (clip position 13.5 s, 15:34:37.5) is a genuine frame of that cycle's tail, not a
restart; it is, however, the next cycle's person entering at the left edge, so the window ended too late. The interval
chooser now stops 2 s before the restart instant (`TAIL_S`), and the historical recording is kept and labelled as it is.

## Limits

The evidence comes from controlled synthetic camera scenarios. There is no accuracy benchmark, no measured reduction in
missed events and no production deployment. The attention region is a draft. The camera replays a 15 s clip on a loop.

**Submission deadline: Monday, 2 November 2026 at 11:00 CET.**

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
