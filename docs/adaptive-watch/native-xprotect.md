# Native XProtect verification

What was actually verified against the real XProtect Corporate 2026 R1 installation on p022, as of 28 October 2026.
Controlled test scene (`person_on_railway_tracks`, a camera that replays a 15 s clip on a loop).

## Created in XProtect

- Analytics Event `Adaptive Watch Review Required`.
- Alarm definition `Adaptive Watch review: station platform`, scoped to the one camera
  ([setup script](../../scripts/xprotect/setup_review_alarm.ps1)).
- Operator-approved edits to that definition while diagnosing the alarm preview: `MapType` 2 to 1 and the related-camera
  list cleared. Prior values are kept in the private `runs/release/native/alarm-definition-before-maptype.json`. It was
  not tested whether these edits are needed; see below.

## Events sent

Each event was sent once through the application's confirmation dialog and the duplicate-send ledger; the Event Server
answered HTTP 200 (transport acceptance only).

| Alarm | What | Source time |
|---|---|---|
| 4 | The saved railway case | 22 Oct 2026 11:03:44 UTC |
| 5 | A live assessment started from the browser, with the detector's bounding box | 28 Oct 2026 15:34:29 UTC |
| 6 to 9 | Diagnostic test events sent while investigating the alarm preview. They stay in the Alarm Manager with their ledgers; no further event was sent | 28 Oct 2026 |

## Smart Client

- **Alarms 4 and 5 are listed in the Alarm Manager** with the right camera, message and source time.
- **Alarm 5 opens its source recording at 15:34:29.5 with the detector box.** Before 28 Oct 18:45 local, the alarm
  preview showed "The camera is not available" for alarms 4 to 9. Playback began working after Smart Client was
  closed and reopened (an operator-approved restart of Smart Client only; no VM, service, Event Server, recording
  server or gateway was restarted). **The underlying cause was not independently established.**
- Live view and recorded playback of `person_on_railway_tracks` also work in Smart Client after the restart.
- **Alarm 4's source recording (22 Oct) has expired**, so its preview shows other footage of the camera without the
  detector box. That is retention, not a camera defect.
- Alarms 6 and 9 (diagnostics) preview their footage too.
- Stored association, read-only with `Get-AlarmLine`: alarms 4 to 9 carry `CameraId` = `SourceId` =
  `1dfb0898-730f-44c1-bca8-7f541e8ef116`, the GUID of `person_on_railway_tracks` in the VMS camera list.
  Alarms 1 to 3 belong to `vandalism`.
- Diagnostic changes that did not by themselves change the outcome: the full management-server `ServerId` block
  (alarm 6) and the definition edits above (alarms 7 to 9).

## Operator state

The saved application state keeps the original send records (event IDs, dispatch keys, source times, payload hashes).
On 28 Oct 2026 the product owner authorized correcting only the stale note that Smart Client playback was
unavailable; the original was backed up privately with its checksum before the edit.

## Not claimed

No accuracy benchmark, no measured reduction in missed events, no production deployment. A person has not reviewed
the footage review or the live run's continuity confirmation; both are labelled as made by an AI reviewer.
