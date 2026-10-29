# Watches, capabilities and monitoring

## A Watch configuration

Stored per Watch as immutable versions (SQLite, `runs/ortru/ortru.sqlite3`). Every assessment records the Watch id and the
version it ran under and keeps a copy of that exact configuration, so editing a Watch never rewrites history.

| Field | Meaning |
|---|---|
| `camera` | Chosen by GUID from the authorized XProtect camera catalog (`cameras.local.json`, produced by `scripts\list_cameras.ps1`) |
| `hafnia.instruction` | The operator's plain-words description of what should be visible. Ortru adds a fixed answer contract (`outcome`, `evidence`, `timing`, `limitations`) that the parser enforces. The whole request is shown to the operator |
| `hafnia.condition` | Short name of the visible condition. It becomes the review question and the answer options |
| `detector` | A capability id from the registry plus validated parameters |
| `region` | Normalized polygon (3 to 12 points) drawn on a camera snapshot |
| `policy.raiseOn` | Which signal combinations raise an exception (see [product.md](product.md)) |
| `schedule` | Cadence in minutes (5 to 1440), recording window (12 to 17 s, what Hafnia accepts) |
| `quota.perDay` | Maximum Hafnia requests for this Watch in 24 hours (plus a global limit across Watches) |
| `native` | Event type and alarm. Taken from the verified destination registry, never typed in the form |
| `source.loopReference` | Optional, API only: a recorded manifest used to align windows on cameras that replay a short clip |

Lifecycle: draft, active, paused, disabled. Editing needs the version you loaded; a stale edit is refused with a conflict.

## Capability registry (not a prompt-to-detector generator)

| Capability | State | What it establishes |
|---|---|---|
| `person_region_proximity` | available (Faster R-CNN ResNet-50 FPN v2, COCO person, Linux A10G, 2 samples per second) | A tracked person's foot was inside or near the region at a sampled moment. Proximity, not entry |
| `object_stationarity` | listed, **unavailable** | Needs the object-localization model and a stationarity runner that has not been made operational on the A10G for this release. Activation is refused with this reason |

Unsupported combinations are rejected when the Watch is saved, with the reason.

## Monitoring over recorded windows

A durable job table (`runs/ortru/ortru.sqlite3`) holds one assessment per Watch, version and recorded window.

1. **Retention check.** The camera's retained recording sequences are listed (read only); the newest clean window ending at
   least 90 s ago is chosen. If nothing is retained the Watch records why and nothing starts.
2. **Interval deduplication.** A window that overlaps one already assessed for the same Watch version is not assessed again.
3. **Budgets.** Per-Watch and global daily Hafnia limits are checked before acquisition.
4. **Acquire and align.** Snapshots and the original recording are read from XProtect, encoded to a browser MP4 and aligned.
   For cameras that replay a short clip, the loop restart is located (from a reference clip, or from visible jumps in the
   footage) and the window is cut inside one cycle. Every recorded window is checked again for a restart; a window that
   contains one fails before Hafnia.
5. **Local vision** on the A10G over SSH, with the exact runner and tracker verified by hash.
6. **One Hafnia request**, claimed in a ledger before it is sent. After an uncertain transport result the request is polled or
   reported, never resent. With no gateway session the assessment waits visibly ("Hafnia gateway: sign-in needed").
7. **Policy.** The two outcomes are compared under the Watch policy. An exception is built only from verified source files.

Jobs resume after a restart. Failed jobs show the exact reason and the next step; a failed job without a Hafnia claim can be
retried, a parked one can be discarded, and one with a Hafnia claim can be neither.

## Honest limits

- Windows are read after the fact; there is no streaming.
- The hackathon cameras replay short clips on a loop. A camera whose clip has two cuts per cycle (the graffiti camera) has no
  clean 12 second window and cannot be assessed by Hafnia under the continuity rule. Ortru reports that instead of sending a
  broken window.
- The Hafnia gateway password is typed only by the operator, in the server window (`scripts\ortru.ps1 -Gateway`); it is kept in
  memory and never reaches the browser.
