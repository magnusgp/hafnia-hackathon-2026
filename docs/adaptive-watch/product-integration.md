# Adaptive Watch — product integration checkpoint

25 October 2026. Branch: `feat/adaptive-watch`. Polar is unchanged.

The shared `persistent_object` path supports both configured cameras through
`config/camera-capabilities.json`: camera GUID, object queries, draft region,
explicit temporal policy and native event identity. Fresh runs require a separate
camera-specific spatial file carrying operator approval and reference-frame identity.
Registry polygons are drafts, never operational approvals.

## First deliverable

The Python evidence index has loaded both actual saved joins through one importer:

| Camera | CV stationarity | Source interval (22 October, UTC) |
|---|---|---|
| escooter_left_across_sidewalk | 5 s / 6 samples | 11:04:48–11:05:01 |
| bin_pushed_over_onto_sidewalk | 3 s / 4 samples | 11:04:31–11:04:43 |

No new detection or Hafnia inference is claimed for these records. The importer
checks original CV and manifest hashes, frame hashes/timestamps, original Hafnia
record hashes and responses, exact request identity, and re-runs the common
configured temporal measurement. Fresh schema-v2 imports additionally rebuild the
join from its actual source artifacts and spatial configuration. Historical records
retain their review-only classification; indexing never grants dispatch eligibility.

Monitoring reads `/api/incidents`. Clicking either row opens
`#/investigation/<incident-id>`; direct-link reloads work. IDs derive from the
persisted joined artifact digest. Unknown IDs show an error rather than falling
back to another incident. Original frames are served through indexed IDs and are
hash-checked again on each request. Python serves no gateway credentials and no
native dispatch route. API is bound only to 127.0.0.1:8765, read-only, without CORS.
The frontend can use a same-origin Vite proxy or be served by the evidence server
from `frontend/dist`. Private data is excluded from Vite public assets/build output.

The existing local CV/Hafnia contributor separation and Polar layout are retained.
UI now says Review queue, Monitoring rules and Cameras. Status, camera, source time
and operator action come from the indexed record. Raw replies, hashes and detailed
limitations are expandable. Notes/hold are explicitly session-only; they neither
persist approval nor send an event.

Validation: 105 Python tests run, 88 pass and 17 optional ML tests skip on Windows
because ML dependencies are absent. Fresh assembly and XML preview tests exercise
both cameras. Existing deduplication/ambiguous-outcome tests remain. Browser checks
load both real records by ID, decode their actual images, exercise filters,
localization/draft-region controls, seeking, provenance, local hold and unknown IDs
at 1440×900 and 1920×1080. No browser errors or horizontal overflow were observed.
TypeScript and production build pass. Private screenshots/check results are in
`runs/product-integration/`; test output is `runs/product-tests.txt`.

## Native alarm: exact outstanding gates

No dedicated event/alarm definition has been created and no native event sent.
No dedicated alarm ID, native playback or bounding-box rendering is verified.

1. Operator must explicitly authorize creation of analytics event
   **Adaptive Watch Sidewalk Obstruction** in Management Client. Then create/verify
   the corresponding alarm definition, with source restricted to the individually
   approved camera GUIDs in `config/camera-capabilities.json`. Do not select all
   cameras. Keep existing priority settings; do not change network, Event Server,
   firewall, services or accounts. Detailed fields and operator instructions remain
   in `final-integration.md`.
2. Review each actual pedestrian polygon against original camera frames. The saved
   scooter and bin drafts reuse the same diagonal boundary; that does not establish
   approval. Scooter boundary cuts through pedestrian paving and the selected box;
   bin review must account for wall-side occlusion and usable route width. Correct
   or explicitly confirm each camera independently. Save operator, UTC approval
   time and the reference-frame hash in its own private spatial file. No polygon
   was approved by this implementation. Partial box overlap cannot prove clearance.
3. Restore use of an **existing** authorized SSH identity for `p022-linux`. The
   read-only connection check as `ubuntu` reached the host but failed
   `Permission denied (publickey)`. No accounts or SSH configuration were changed.
4. Select/acquire a fresh coherent interval spanning placement and subsequent
   stationarity. One fresh acquisition succeeded on 25 October:
   10:59:17.517–10:59:32.517 UTC, 15 timestamped snapshots and MKV, retained under
   ignored `runs/product-live-20261025/`. Sample review showed an approach, fallen
   scooter, then a rider on a scooter again: a loop reset. The private acquisition
   review rejects this interval. It has **no** no-loop-boundary attestation and
   cannot be used for fresh qualification. Review a suitable 12–17 s whole-second
   interval before spending inference. MKV PTS-to-UTC alignment also remains to be
   verified against source snapshots. No inference was submitted for this attempt.
5. Run `scripts/adaptive_watch/incident.py analyze --camera CAMERA --root PRIVATE_ROOT
   --spatial PRIVATE_SPATIAL --ssh-user EXISTING_USER --identity EXISTING_KEY` from a
   user-opened interactive terminal. CUDA runs only on p022-linux; Hafnia credentials
   stay terminal-only. CV and Hafnia must identify the same manifest and exact
   interval. Reuse the incident root and ledger to resume existing IDs; never retry
   an ambiguous submission or bypass the one-request-per-incident gate.
6. Generate/review the joined record and exact `proposal.xml`/`proposal.json`.
   Strict unnormalized Hafnia support, camera-specific geometry approval, coherent
   recording and CV candidate remain mandatory. Stop for **separate explicit
   approval of the complete XML SHA-256**. Existing retrospective XML previews do
   not authorize fresh dispatch. Dispatch now rebuilds the proposal from persisted
   sources and rejects changed camera capability configuration before approval.
7. Only after that approval, use the existing `dispatch` stage with the persistent
   native ledger. Reservation/overlap deduplication remains camera-specific across
   roots and prompt variants; ambiguous outcomes remain reserved for reconciliation.
8. Inspect Smart Client and record actual alarm ID, displayed source camera,
   recording/playback time and bounding-box rendering (including absent or
   unsupported). Record transport acceptance separately. An empty HTTP 200 is not
   an alarm or overlay verification. The dispatch command retains operator fields
   for these observations only after acceptance.

## Vehicle assessment

Deferred until scooter/bin live gates pass, as requested. Existing vehicle recording
and Hafnia plans do not demonstrate stationary-vehicle/queue temporal logic or a
working evidence join. No vehicle capability is presented as implemented. No custom
training, extra inference, final presentation, merge or Windows Tailscale execution
was performed.
