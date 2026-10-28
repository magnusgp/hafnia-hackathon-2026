# Incident lifecycle sprint — 26 October 2026

The queue now stores episodes separately from observations, Hafnia assessments,
append-only operator decisions, approval requests and native dispatch reservations.
Existing saved evidence is migrated without upgrading its historical eligibility.

`candidate ? review_required ? escalated` is the main path. Dismissal is terminal;
`resolution_unverified` holds uncertainty for further review. Missing observations
never close an episode. Escalated means guarded CLI transport acceptance; native
alarm verification remains separately unverified. No browser dispatch route exists.

Grouping requires camera/capability/query family, approved matching polygon,
box coordinates within 0.025 of the original episode anchor and at most 1.5 seconds
between supporting windows. Conflicting or ambiguous evidence does not merge.
Exact source reimports attach new assessments without creating observations.
Identical frame-hash sequences are repeated evidence, not independent support;
they do not extend the supported interval. Known loop resets can be imported with
`--loop-reset`; different unrecognized reset windows are conservatively separated
and never count as independent evidence. This is not a general loop detector.
Each observation retains source manifests, recording sequences, frame identities,
CV/join hashes and source paths. Decision snapshots include assessment contents
and evidence hashes. Unknown native send outcomes remain reserved for manual
reconciliation. Decisions cannot be changed or deleted through the API or SQL
updates/deletes. An operator identity/authentication system is outside this local
single-workstation prototype; notes are not authenticated operator attribution.

Run the queue against the private persisted index (choose an unused localhost port):

```powershell
.\.venv\Scripts\python.exe -m adaptive_watch.evidence_api --root runs/product-evidence serve --port 8767 --frontend frontend/dist
```

## Reproducible offline replay

```powershell
.\.venv\Scripts\python.exe scripts/adaptive_watch/replay_episodes.py --source runs/product-evidence --output runs/lifecycle-replay/report.json
```

The source database is copied before replay. Original saved joined/CV/manifest
hashes are checked. Synthetic windows keep source recording provenance and are
explicitly labeled; their approved geometry is only a synthetic grouping input.
Counts below are separate fixtures, not totals from an operational deployment.

| Fixture | Inputs ingested | Unique observations | Episodes | Duplicate queue notifications avoided | Require review |
|---|---:|---:|---:|---:|---:|
| Real saved baseline | 2 | 2 | 2 | 0 | 2 |
| Synthetic loop reimports | 6 | 2 | 2 | 4 | 2 |
| Synthetic compatible windows | 6 | 6 | 2 | 4 | 2 |

Notifications mean duplicate candidate queue entries avoided, not delivered
messages. Each fixture makes **0 Hafnia requests** and verifies **0 native events**.
Avoided Hafnia requests are **0 measured**: replay does not schedule inference,
so it does not establish inference savings. Existing saved assessments are reused.
No independent real-world accuracy, persistence or notification-rate claim follows.

Before: open each joined recording as a separate incident; leave session-only notes.
After: open one condition in the queue, inspect its supporting observations, save a
review/dismissal/escalation request, then use a separately approved native action.
The six-window synthetic fixture reduces six candidate entries to two episodes.

## Native handoff and approval gates

Linux access was restored using the existing Windows key, BatchMode and
IdentitiesOnly. Host `p022-linux` reports an NVIDIA A10G. No credentials regenerated.
The first fresh 15-second export visibly crossed a loop reset and was retained.
A shifted 15-second export also included a reset in its final sampled frame.
The final 14-second export ends before that reset; full continuity still requires
operator review of the MKV, not just inference from sparse samples.

Private workspace: `runs/lifecycle-native-final-20261026`.
Recording: **2026-10-26 09:37:31.802–09:37:45.802 UTC**; matching whole-second
analysis: **09:37:32–09:37:45 UTC**. Actual Linux CUDA CV completed on **13 frames**.
Source manifest SHA-256:
`a31e3fd3d64ff038c5218a944c0ba380e9cd3af95807aeb2c503378dbd1acc5c`.
CV SHA-256:
`302e64dc34ca8841ca3f9e6a0fb049e56d5b302a4a046c9eeee5e32e86bb0dd6`.
Runner/config hashes and all CV source frame hashes were verified locally.
Qualifying sampled run: **09:37:39.809–09:37:44.809 UTC**, **5 seconds / 6 samples**;
minimum draft-region overlap **43.0%**. This is not a clearance measurement.

Pending: human continuity attestation; camera-specific polygon approval; matching
Hafnia analysis using terminal-only credentials; exact source rejoin; configuration
approval; separate exact XML digest approval; Smart Client alarm/camera verification.
No fresh Hafnia call, joined dispatch proposal or native event has been produced.
No valid fresh XML digest is available for dispatch approval yet.

Resume in a user-opened PowerShell before this recording exceeds the existing
24-hour inference gate; inspect the MKV and draft spatial.local.json first:

```powershell
.\.venv\Scripts\python.exe scripts/adaptive_watch/incident.py analyze --camera escooter_left_across_sidewalk --root runs/lifecycle-native-final-20261026 --spatial runs/lifecycle-native-final-20261026/spatial.local.json --identity C:\Users\Administrator\.ssh\hafnia_p022_linux
```

The command asks for continuity review, reuses the matching CUDA result, requests
the existing terminal-only Gateway password, submits at most one matching Hafnia
analysis and produces joined evidence/XML only if source validation succeeds.
Unapproved geometry or a normalized/invalid model response must remain blocked.
Never reuse a different recording's polygon approval. If the evidence expires,
acquire and review new evidence rather than changing source timestamps.

The exact camera-scoped event and alarm configuration is in
[final-integration.md](final-integration.md#exact-proposed-management-client-configuration).
The approval question has been presented; no response or configuration change is
recorded. Configuration approval is distinct from dispatch approval. The dedicated
event is not verified configured. No services/firewall/accounts were changed.

After a valid fresh join, import it with the existing evidence API import command
and `--spatial`; save Request escalation in the queue. Invoke the existing guarded
`incident.py dispatch` with the stable root, existing ledger and additionally
`--episode-root <index-root> --episode-id <queue-id>` to associate the native action.
It still demands configuration confirmation, recording review and the complete
exact XML SHA-256 at the terminal. Evidence changes invalidate the request.
Transport acceptance is not proof of a native alarm. Record the actual alarm ID,
camera, playback time and observed overlay inside Smart Client; no demo is complete
until those are verified. Nothing has been merged into main.

## Validation

Full regression suite: 110 tests, 17 skipped (93 executed successfully).
Production TypeScript/Vite build passed. Headless Edge verified both saved cameras
at 1440×900 and 1920×1080, source images, geometry toggle, persisted review after
reload, unknown-ID handling, no horizontal overflow and zero browser errors.
Browser decisions were written only to the isolated `runs/lifecycle-browser` copy.
Private screenshots/check output remain under ignored runs/product-integration.
