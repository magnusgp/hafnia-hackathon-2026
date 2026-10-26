# Frozen experiment protocol

Definitions are versioned in `label-definitions.json`; its hash is stored with the private review draft. Definitions were written before new inference (none has run). AI draft labels are not a human attestation. A human must review original timestamped frames, ambiguous samples, negatives and loop boundaries and provide `status: human_confirmed`, reviewer, reviewed_at, definitions_sha256, review_artifact and review_artifact_sha256. The review artifact must contain the corrected frame labels and source hashes, not merely an approval of this report.

Stage ceilings are budgets, not targets. One durable ledger covers all days. Gateway day is checked against UTC; if the installed service uses another reset convention, adapt and test the verified contract before running. No new requests are useful while the access and labeling gates remain unresolved.

| Stage | Fixed experiment ID form | Planned matrix | Stop rule |
|---|---|---|---|
| A | `REL26-A-{scene}-v{1,2}-r{01..03}` | Reuse 12 incident responses and four busy-street controls first. At most two additional repetitions per incident/prompt cell (24 new requests) if stability is useful. | No repeats merely to reproduce known responses; never exceed 128 new requests. |
| B | `REL26-B-{railway,gate}-v{3,4}-r{01..03}` | Two visible-action prompt variants, three repeats, each of two scenes: 12 new full-interval requests. | Stop if no diagnostic information is added. Unsupported short intervals contribute zero requests. Ceiling 192. |
| C | `REL26-C-{scene}-negative{01,02}-v{1,2}` | Two distinct task-matched negative events per scene and two prompts: up to 24 requests, only if footage exists and is human reviewed. | Zero if no suitable footage; ceiling 144. |

Stage B v3 body: railway “Report whether the red-clothed person visibly leaves the platform and stands or moves in the track bed. Sitting on the edge alone is ambiguous.” Gate “Report whether the person visibly handles or manipulates the gate area. Successful opening is not required; distinguish uncertain tool identity.”

Stage B v4 body: railway “Review the sequence in time order: platform approach, seated edge, descent, track-bed presence. Decide only whether descent or track-bed presence is visible.” Gate “Review approach, contact with the gate area, crouching and departure. Decide whether visible gate manipulation occurs, independently of whether opening occurs.”

For both variants append the exact common schema/intent suffix from the existing `prompt()` function. These are prospective prompts, not evaluated variants. Pin exact full text into each executable plan entry before submission. New source intervals need separate manifests and continuity review. Never infer human labels from model descriptions.

Each executable plan is a JSON list with experiment_id, stage, event_id (same for repeated loops), prompt, camera_id, start, end, recording_manifest, manifest_sha256, label_review_sha256 and continuity_review=`human_confirmed_no_loop_boundary`. Intervals must be hash-bound acquired recordings. The runner conservatively accepts only 12–17 seconds until shorter intervals are verified. No event-generation PromptId is accepted or constructed.

The quota-contract JSON must specify a documented read-only `endpoint`, `remaining_field`, `limit_field`, `day_field`, and `verified_from` reference. The response must supply a 500-request limit, integer remaining balance and current UTC date. There is deliberately no guessed endpoint or manually asserted remaining balance fallback. Adapt to the actual documented API rather than inventing data to satisfy these fields.

Run offline preparation and analysis:

```powershell
.venv/Scripts/python.exe scripts/reliability_evidence.py prepare --root runs/reliability-20261026
.venv/Scripts/python.exe scripts/reliability_evidence.py analyze --root runs/reliability-20261026 --responses C:/Users/Administrator/adaptive-watch-private/hafnia-16
```

After the gates are satisfied, validate without submitting, then use the same root with `--apply --quota-contract PATH`. Authentication uses the existing Gateway environment/terminal mechanism; never paste credentials into chat. If submission is ambiguous, use `--reconcile EXPERIMENT SUMMARY_ID` only after identifying the exact request in gateway history. Reconciliation verifies returned prompt and video URI; insufficient history evidence leaves it blocked. Re-running a known ID polls it and never re-POSTs. A network error stops the batch; retain its ledger. The runner intentionally provides no automatic claim deletion or retry switch.

Keep footage, private review, quota snapshots, ledgers and raw responses under ignored runs/ or outside Git. Commit only code, definitions, sanitized counts and presentation artifacts. Do not include the unrelated pre-existing working-tree changes in this sprint commit.
