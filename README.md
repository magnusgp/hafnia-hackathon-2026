# Ortru

A configurable video intelligence and exception-handling layer for Milestone XProtect and Hafnia VLM.

Ortru is named after Orthrus, the two-headed guardian hound. Its two watchers are **Hafnia**, which reads recorded video and
answers in words, and **independent local vision**, a detector on a Linux A10G that keeps its own record of the same footage.
Ortru connects them, applies a review policy you define, and sends actionable exceptions into XProtect, where the operator
already works.

Built for Hafnia Hackathon 2026. Submission deadline: Monday, 2 November 2026 at 11:00 CET.

## What it does

1. **Create a Watch** on an existing XProtect camera: pick the camera, write what Hafnia should look for, choose a local vision
   capability, draw a region on a camera picture, choose when to raise an exception and how often to look. No code changes.
2. **Ortru monitors recorded windows** of that camera at the Watch cadence, within a per-Watch and a global Hafnia budget, and
   compares Hafnia's answer with the detector's independent measurements.
3. **Exceptions** are real assessments that meet the Watch's policy. Each opens as an **Investigation**: the footage, what each
   source established, why it was raised, the Watch's own review question, and the action that sends a review event to XProtect.
4. **Send to XProtect** is a real, confirmed, once-only handoff to the Event Server. Transport acceptance and Smart Client
   verification are reported as different states.

```
XProtect recording --> Hafnia answer ----\
        |                                 +--> Watch policy --> Exception --> operator investigates
        +-------> local vision (A10G) ---/                                        |
                                                              confirmed, guarded handoff to the Event Server
                                                              --> XProtect alarm in Smart Client
```

A "no" from Hafnia next to a person at a hazardous region is not a contradiction: they are separate observers. An unsure or
unreadable Hafnia answer is never silently treated as "no". Details: [docs/ortru/product.md](docs/ortru/product.md).

## Run it (on p022)

Ortru runs on the hackathon Windows machine and is opened inside p022 (Remote Desktop); `localhost` on another computer does not
reach it.

```powershell
cd C:\Users\Administrator\dev\hafnia-ortru
powershell -ExecutionPolicy Bypass -File scripts\ortru.ps1          # http://127.0.0.1:8790
```

Without a Hafnia gateway session Ortru still reads the recording and runs local vision; the Hafnia step waits and says so.
`-Gateway` asks once, in the server window, for the gateway password (kept in memory, never sent to the browser). `-NativeSend`
allows one confirmed event at a time. Options and first-use walkthrough: [docs/ortru/operating.md](docs/ortru/operating.md).

## The verified native path

The event `Adaptive Watch Review Required` and the camera alarm `Adaptive Watch review: station platform` exist in XProtect (the
names predate Ortru and are kept so existing events and recorded payloads stay valid). Two events were sent earlier through the
guarded dialog and both alarms are listed in Smart Client; alarm 5 opens its source recording with the detector box. Playback
began working after an approved Smart Client restart; the underlying cause was not independently established. Details and limits:
[docs/ortru/native-xprotect.md](docs/ortru/native-xprotect.md).

The **evidence archive** shows those two authentic records (the station platform case and the first live assessment) exactly as
saved, labelled as recorded before Watches existed, plus the earlier single-case experiments (school gate, scooter, bin), which
are evidence only and not product features.

## Limits

Ortru samples recorded windows; it does not stream. The evidence comes from controlled synthetic camera scenarios: there is no
accuracy benchmark, no measured reduction in missed events and no production deployment. Hafnia is an AI footage review, not a
human one; the operator's decision is the human review.

## Repository

```
ortru/                 Watch store, capability registry, policy, durable scheduler, exception views, native handoff, server
adaptive_watch/        acquisition and encoding helpers, evidence verification, earlier assessment pipeline (stable import name)
scene_contracts/       Hafnia gateway client, Event Server serializer and duplicate-send ledger
frontend/              React 19, TypeScript, Vite: the Ortru application and its browser acceptance checks
brand-kit/ortru/       guardian mark, favicon and wordmark (editable SVG); brand-kit/ holds the Polar tokens
presentation/ortru/    standalone HTML presentation with speaker notes (the earlier film's pipeline stays in presentation/)
scripts/               ortru.ps1, XProtect acquisition and setup, vision runner, archive preparation, browser check runner
tests/                 Python regression tests (unittest) and the isolated browser-test server
docs/                  docs/ortru (current), docs/research (pre-registered experiments), docs/archive (superseded notes)
config/, results/      camera capabilities and event definitions; research result files (two are read by source verification)
```

Source CCTV, credentials, raw Hafnia responses, identity files, model weights, databases, recordings and captures are private
and ignored by Git. The older Adaptive Watch release remains on the branch `release/adaptive-watch-submission` as a working
fallback.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
cd frontend; ..\runs\tooling\bun-windows-x64\bun.exe run build
cd ..; powershell -ExecutionPolicy Bypass -File scripts\run-ortru-check.ps1
```

## License and notices

No software license has been chosen yet; that is an open repository-governance item for the team. Bundled fonts (DM Sans, IBM
Plex Mono, Space Grotesk) are under the SIL Open Font License 1.1: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
