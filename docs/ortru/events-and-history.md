# Repeated events and decision history

## The four station-platform exceptions are one synthetic event, seen four times

The hackathon cameras replay a short recorded clip. Camera `person_on_railway_tracks` replays one with a 15 s cycle
(seam 12:42:09.013 UTC, measured by Ortru on 29 Oct). Each scheduled assessment cut a 12 s window at the same position in
that cycle (0.99 s in) and so recorded the same footage again.

Compared on 29 Oct (assessments `b586966c`, `930b704a`, `9ce054ee`, `e7030748`, windows starting 12:42:25, 13:56:10,
14:11:25 and 14:26:25 UTC, all Watch `w-c95bfc089f` version 2):

| Evidence | Result |
| --- | --- |
| Window start relative to the cycle seam | 0.987 s after a seam in all four (each start is a whole number of 15 s cycles after 12:42:09.013, plus 0.987) |
| Exported MKV and MP4 | byte-identical (MKV `59b4d510…`, MP4 `a7bf821f…`) |
| Decoded frames, 120 per clip | mean absolute pixel difference 0.00 between every pair. A control (the same clip against itself shifted 5 s) differs by 11.75 |
| Detector output, 24 samples | identical boxes and tracks, IoU 1.0 at every sample |
| Hafnia answer | `not_observed` with the same evidence text, four separate requests (summary ids differ) |

Conclusion: these are four recurrences of one visual event, not four events. They are still four assessments with four
Hafnia answers. The comparison output is kept in the private evidence directory for this gate. Nothing was merged, deleted
or hidden.

## Deduplication policy

Implemented in `ortru/events.py`. It groups assessments for display and for sending. It never alters an assessment, its
evidence files, its decision or its native state, and it never stops a Watch from raising an exception.

* **Distinct** is the default. A different camera, or a different Watch focus (condition, detector, parameters or region),
  is never the same event.
* **Same occurrence**: same focus and the recorded windows overlap in real time (one real moment assessed more than once).
* **Recurrence**: same focus, different times, and both of
  * identical content: the exported recording has the same hash, or the detector tracked the same boxes (within 0.01 of the
    image) at every sample, with at least three samples that contain a person; and
  * the same position in the camera's replay cycle (within 0.15 s, about one frame).
* Matching content at a different cycle position, the same position with different content, or content with no measured
  cycle position stays distinct. A genuinely new event on the same camera and Watch therefore always stays its own event.

What the interface and API do with a group (`event` on each exception view, `GET /api/exceptions/<id>`; queue entries do not carry it):

* Every member stays in the queue (the queue lists all four) and keeps its own review decision.
* Sending to XProtect for one member never hides the others. If another member of the same event has already been sent,
  the send is refused until the request carries `acknowledgeRepeat: true` (a deliberate second alarm). The duplicate-send
  ledger still blocks the same dispatch twice.

Known limit: the cycle position is compared directly, not modulo the cycle length. Windows are cut at a fixed position, so
this holds for Ortru's own windows. A window that wrapped around the seam would be treated as distinct (it is never merged
wrongly, it can only be missed).

## Decision history is append-only

Review decisions used to be one row per exception that was overwritten on every save. They are now stored as revisions in
`decision_revisions`: one row per saved revision, and the database refuses `UPDATE` and `DELETE` on it. The earlier
`decisions` table is kept as a frozen record (it refuses writes too). On first start the existing row is copied unchanged
into `decision_revisions`.

Exception `b586966c61d7460c997bcc47b0a3ce38` holds revision 2 (the AI demo review, `reviewer=claude_ai_demo`, saved
2026-10-29T14:42:22Z, status `review_requested`). It was migrated field for field and verified identical to the pre-migration
dump.

**Revision 1 of that exception cannot be reconstructed.** It was overwritten by revision 2 before append-only storage
existed, and the old table kept no history. No record of it was invented. `GET /api/exceptions/<id>/history` lists it as an
entry with `available: false` and the reason, so the numbering gap is visible rather than hidden. The same is true of any
other revision number that has no stored row.

New decisions append revision N+1 inside one transaction that checks the expected revision. A stale save is refused (HTTP 409)
and writes nothing.
