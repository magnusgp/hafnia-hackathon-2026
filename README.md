# Adaptive Watch

A second signal for Milestone XProtect. Hafnia reads recorded video and sometimes answers "no" for something that
deserves a look. Adaptive Watch runs independent computer vision on the same recording for one configured condition.
When Hafnia says no and the detector sees the condition, it builds a **review exception** (camera, recording, moment,
both signals) and sends it into XProtect, where the operator already works.

It is not a second summarizer, an incident manager or a model comparison. Hafnia's answer stays on record. What is new is
a way to stop a negative answer from being the last word.

Built for Hafnia Hackathon 2026. Submission deadline: Monday, 2 November 2026 at 11:00 CET.

## The flagship case

A person in a red jacket sits on a station platform edge, climbs down onto the tracks and walks away (22 Oct 2026,
11:03:39 to 11:03:52 UTC, camera `person_on_railway_tracks`).

1. XProtect recorded the scene.
2. Hafnia answered `not_observed` for entry onto the tracks.
3. A person detector on a Linux A10G GPU placed the person at the platform edge from 11:03:44.5, about 3.8 s before the
   climb. This is a proximity trigger. It does not claim entry.
4. Adaptive Watch built the review exception. A separate footage review (by an AI, labelled as such) found the person on
   the track bed at 11:03:48.3.
5. The operator inspects the footage and requests the review. Adaptive Watch sends the analytics event
   `Adaptive Watch Review Required` for that camera, and XProtect raises its own alarm.

## Why independent vision matters

A detector that looks only for a person near a platform edge is a different kind of observer from a language model
summarizing a clip. Where the two disagree, there is something worth a human look. The application shows both signals
on one timeline with the original footage; it does not decide which one is right.

## How it works

| System | Job |
|---|---|
| XProtect Corporate 2026 R1 | Records and plays back the scene; receives the analytics event (Event Server, port 9090); raises the camera-specific alarm the operator works from. |
| Hafnia VLM | Reads the recording through the local gateway and answers in words, including when the answer is no. |
| Linux A10G vision | Watches the same footage for one configured condition and keeps its own record. |

```
XProtect recording --> Hafnia answer ----\
        |                                 +--> compare --> review exception --> operator inspects
        +-------> detector (A10G) -------/                                          |
                                                                      guarded handoff to the Event Server
                                                                      --> XProtect alarm in Smart Client
```

Source files are hashed when a case is saved and verified every time it is opened. The handoff is guarded: it needs a
saved review request, shows the exact event and its fingerprint, needs a second confirmation, goes through a
duplicate-send ledger and is never retried.

## Run the judge demo (on p022)

The application runs on the hackathon Windows machine and is opened **inside p022** (over Remote Desktop). `localhost`
on any other computer does not reach it.

```powershell
cd C:\Users\Administrator\dev\hafnia-hackathon-2026
powershell -ExecutionPolicy Bypass -File scripts\review.ps1
```

This checks the release build and source files, starts an **isolated** copy of the flagship case (no password, no
XProtect event can be sent, the operator's saved state is not touched) on port 8781 and opens it in Edge, with the
presentation film in the media player. Walk-through, what to expect and how to restart or stop it:
[docs/submission/product-owner-review.md](docs/submission/product-owner-review.md).

In short: the Station platform case is paused on the detector's trigger. **Play from the trigger** and the person climbs
down about four seconds later. Click a signal on the right (Hafnia, Local vision, Footage review) to jump to its moment;
the three lanes under the footage show what each source said and when. **Send to XProtect review** saves your decision;
**Preview XProtect event** shows the exact event and its fingerprint, with sending switched off.

`scripts\review.ps1 -Reset` starts over; `-Stop` stops only the review server.

## Inspect the prepared evidence

- **Cases.** Four saved cases: the station platform, plus secondary examples that are not railway validations: the
  school gate (Hafnia's two prompts disagree; saved snapshots only, no local vision) and the sidewalk scooter and bin
  (local vision measured how long each stayed still; Hafnia agreed).
- **Evidence details** in the application lists the saved sources behind a case.
- **Prepared release record:** [docs/submission/release-manifest.json](docs/submission/release-manifest.json) (hashes and
  results of the checks), [storyboard](docs/submission/storyboard.md), [form copy](docs/submission/form-copy.md).
- **Research record:** [docs/research/](docs/research/README.md), the pre-registered experiments and negative results
  behind the limits, with result files in [results/](results/).

## Start a new authorized assessment

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch.ps1 -AssessmentLogin
```

This opens the operator application on port 8780 with the saved operator state and asks once, in that window, for the
Hafnia gateway password (kept in memory, never sent to the browser). **New assessment** then acquires the latest 15 s of
the camera from XProtect, runs the A10G detector, asks Hafnia once and compares them. It needs an authorized user, the
gateway and the Linux GPU host. Without the password the dialog explains that it is unavailable and nothing is
submitted. Details: [docs/adaptive-watch/new-assessment.md](docs/adaptive-watch/new-assessment.md).

`launch.ps1 -NativeSend` additionally allows one confirmed event to be sent to the XProtect Event Server.

## Native XProtect: what has been verified

Verified on p022 on 28 Oct 2026 (details and limits in
[docs/adaptive-watch/native-xprotect.md](docs/adaptive-watch/native-xprotect.md)):

- The analytics event `Adaptive Watch Review Required` and the camera-scoped alarm definition
  `Adaptive Watch review: station platform` exist ([setup script](scripts/xprotect/setup_review_alarm.ps1)).
- Two events were sent, each once, through the application's confirmation dialog: the saved flagship case (alarm 4)
  and a **live assessment started from the browser** (alarm 5, with the detector's bounding box). The Event Server
  accepted both and Smart Client's Alarm Manager lists both with the right camera, message and source time.
- **Alarm 5 opens its source recording at 15:34:29.5 with the detector box**, and live view and recorded playback of the
  camera work. Smart Client playback began working after the approved Smart Client restart; the underlying cause was
  not independently established.
- **Alarm 4's source recording (22 Oct) has expired**, so its preview shows other footage of the camera without the box.
- Four further diagnostic events (alarms 6 to 9) were sent while investigating the preview; they remain in the Alarm Manager.

The live assessment (28 Oct, window 15:34:25 to 15:34:38 UTC) acquired the footage from XProtect, ran the detector on the
A10G (26 frames in 2.4 s), made one Hafnia request (`not observed`) and placed a person at the platform edge from
15:34:29.5. Its continuity confirmation was given by Claude (an AI) as demo reviewer, not by a human.

## Limits

The evidence comes from controlled synthetic camera scenarios. There is no accuracy benchmark, no measured reduction in
missed events and no production deployment. The attention region is a draft. The camera replays a 15 s clip on a loop.
Footage reviews labelled "Claude demo reviewer" are AI assessments, not human ones.

## Repository

```
adaptive_watch/        casebook, review store, native handoff, assessment job runner, application server
scene_contracts/       Hafnia gateway client, Event Server serializer and duplicate-send ledger (plus an
                       earlier, separate operator console kept for the record)
frontend/              React 19, TypeScript, Vite: the Adaptive Watch application and its browser checks
presentation/          HTML/CSS/JS deck, narration, timing and render scripts for the film
scripts/               launchers (review.ps1, launch.ps1), XProtect acquisition and setup, vision runner, release tooling
tests/                 Python regression tests (unittest)
docs/                  product docs, submission materials, research record, archive (see docs/README.md)
config/                camera capabilities and analytics-event definitions read by the application
results/               research result files (two are read by the source-integrity check)
contracts/, prompts/   earlier Scene Contracts experiment inputs. With the root scripts hack26.py, scene26.py,
                       scene_web.py, aw.py and vis.py: tested, kept for the record, not part of the demo
brand-kit/             Polar brand tokens
```

Source CCTV, credentials, raw Hafnia responses, identity files, model weights, review databases, recordings and
captures are private and ignored by Git. A clone alone cannot show the saved cases; they need the original files on p022.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
cd frontend; ..\runs\tooling\bun-windows-x64\bun.exe run build      # tsc -b, then vite build
```

Browser checks (real Edge, isolated session): see [frontend/README.md](frontend/README.md).

## Submission status

The presentation film is a local file on p022 (`runs/release/adaptive-watch-submission.mp4`, 177 s); it has not been
published and the form has not been submitted. Source: https://github.com/magnusgp/hafnia-hackathon-2026, branch
`release/adaptive-watch-submission`.

## License and notices

No software license has been chosen yet; that is an open repository-governance item for the team. Bundled fonts (DM Sans, IBM Plex Mono, Space Grotesk) are under the SIL Open
Font License 1.1: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
