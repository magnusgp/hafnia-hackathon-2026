# Frozen experiment protocol

Definitions are versioned in `label-definitions.json`; its hash is stored with the private review draft. Definitions were written before new inference (none has run). AI draft labels are not a human attestation. The original protocol required human review. The user subsequently explicitly authorized AI review for this demo. A human signoff may provide `status: human_confirmed`, reviewer, reviewed_at, definitions_sha256, review_artifact and review_artifact_sha256. For this authorized demo, the runner also accepts status=reviewed, review_mode=ai_demo and user_authorized_ai_review=true, with the same artifact hashes, reviewer and timestamp. This is not a human attestation. The review artifact must contain the corrected frame labels and source hashes, not merely an approval of this report.

Stage ceilings are budgets, not targets. One durable ledger covers all days. Gateway day is checked against UTC; if the installed service uses another reset convention, adapt and test the verified contract before running. AI demo labels are frozen. The operator reports the password fixed; no agent login or submission is permitted in this offline follow-up.

| Stage | Fixed experiment ID form | Planned matrix | Stop rule |
|---|---|---|---|
| A | `REL26-A-{scene}-v{1,2}-r{01..03}` | Reuse 12 incident responses and four busy-street controls first. At most two additional repetitions per incident/prompt cell (24 new requests) if stability is useful. | No repeats merely to reproduce known responses; never exceed 128 new requests. |
| B | `REL26-B-{railway,gate}-v{3,4}-r{01..03}` | First batch: two visible-action prompt variants once per scene, four new full-interval requests. Up to eight subsequent repeats remain conditional. | Stop if no diagnostic information is added. Unsupported short intervals contribute zero requests. Ceiling 192. |
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

After the gates are satisfied, validate without submitting, then use the same root with `--apply --quota-contract PATH`. Operator execution uses terminal-only authentication, ignores the password environment variable, and requires --operator-auth-confirmed. No authentication is performed during offline preview. If submission is ambiguous, use `--reconcile EXPERIMENT SUMMARY_ID` only after identifying the exact request in gateway history. Reconciliation verifies returned prompt and video URI; insufficient history evidence leaves it blocked. Re-running a known ID polls it and never re-POSTs. A network error stops the batch; retain its ledger. The runner intentionally provides no automatic claim deletion or retry switch.

Keep footage, private review, quota snapshots, ledgers and raw responses under ignored runs/ or outside Git. Commit only code, definitions, sanitized counts and presentation artifacts. Do not include the unrelated pre-existing working-tree changes in this sprint commit.

AI demo review is frozen in private `reviewed-ai-demo.json` and `review-signoff.json`. Original definitions and draft remain unchanged. Generate a review only after explicit authorization using `review-demo --authorize-ai-demo-review`; analyze it using `--review-artifact`. The v3 railway polygon is calibration-only and still cannot distinguish seated edge contact from established entry.

For authorized AI demo plans, continuity_review may be `ai_reviewed_no_loop_boundary`; retain uncertainty rather than claiming human confirmation. A gate interval crossing the reset candidate is ineligible. Fractional URI bounds and missing or changed frame hashes now block submission.

The exact first-four-request matrix and operator gates are in [operator-runbook.md](operator-runbook.md) and [first-batch-matrix.json](first-batch-matrix.json). Availability proof for the exact original recording interval is required before any new POST; pending IDs can still be resumed without resubmission.
