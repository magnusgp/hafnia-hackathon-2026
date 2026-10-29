# Native XProtect verification

The event and alarm names below (`Adaptive Watch Review Required`, `Adaptive Watch review: station platform`) were created before the product was named Ortru. They are kept so that existing events, recorded payloads and Smart Client alarms stay valid; Ortru sends the same event type.

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
| 10 | Ortru exception `b586966c` (station platform Watch), sent once on 29 Oct 2026 15:08:38 UTC with the product owner's explicit authorization | 29 Oct 2026 12:42:29 UTC |
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

## Alarm 10 (Ortru, 29 Oct 2026)

Checked separately, each by its own evidence:

- **Event Server**: HTTP 200, ledger attempt 1 `accepted`, payload sha256 `3691b7b2…9323` identical to the preview taken before any code change.
- **Alarm in XProtect** (read-only `Get-AlarmLine`): `LocalId` 10, camera `person_on_railway_tracks`, source time 12:42:29.513 UTC, state New, vendor Ortru. The alarm count went from 9 to 10, with one alarm for the dispatch key.
- **Source recording**: retained for 12:42:25 to 12:42:37 UTC (`Test-Playback` true at 12:42:29.5); the camera keeps about one day, so it will expire. The evidence MP4 and snapshots stay in Ortru's archive.
- **Recording content**: a read-only `Get-Snapshot` of the camera's recording at 12:42:29.513 UTC is closest to the assessed evidence frame for that sample (index 9; mean grey-level difference 3.3, next closest 5.7, median over the 24 frames 10.3). Not bit-identical, since it is a separate JPEG encode, but it is the same footage and the same moment.
- **Smart Client**: not viewed by the assistant, so Ortru keeps `smartClient: not_verified` for this exception until a person opens the alarm.

The evidence files (send response, ledger row, alarm line, hashes) are in the private gate evidence directory, not in the repository.

## Operator state

The saved application state keeps the original send records (event IDs, dispatch keys, source times, payload hashes).
On 28 Oct 2026 the product owner authorized correcting only the stale note that Smart Client playback was
unavailable; the original was backed up privately with its checksum before the edit.

## Not claimed

No accuracy benchmark, no measured reduction in missed events, no production deployment. A person has not reviewed
the footage review or the live run's continuity confirmation; both are labelled as made by an AI reviewer.
