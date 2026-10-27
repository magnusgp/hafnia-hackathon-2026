# REL26-D: completed diagnostic campaign

**24 submitted, 24 completed, 0 further inference.** All 24 returned `traffic-general`; all yielded nonempty free text preserved as `valid_descriptive_response`. No JSON schema was imposed on descriptive answers. There were no unresolved claims or saved gateway failure states. `Completed` is the gateway analysis status; HTTP response codes were not saved.

The campaign ran October 27, **12:53:27–12:55:36 UTC**, sequentially. Authenticated history read succeeded at 12:53:26 UTC and live preflight showed 500 requests remaining. The ledger contains 24 unique experiment IDs, 24 unique summary IDs and 24 saved POST envelopes. Every returned prompt and video URI exactly matches its persisted request. All prompt/matrix, manifest, video, snapshot and reference hashes passed offline audit; exact camera GUIDs match manifests. Source age and coverage freshness also passed when checked against every actual summary creation time. Optional model discovery was not used as a submission blocker.

Sources remain railway **11:55:38–11:55:51 UTC** and gate **11:55:49–11:56:02 UTC** on October 27. Frozen continuity reviews record no reset within either selected interval. Gate export preroll/absolute PTS origin remains unverified; no fabricated UTC-to-PTS alignment is used. The two scenes are **two existing loop families, zero new independent events and zero eligible distinct task-matched negatives**. Railway export bytes are identical to the October 26 v3/v4 export. This is a prompt diagnostic, not a failure-rate study.

## Response matrix

Each cell summarizes two exact repetitions. Counts refer to claims in responses, not independently validated detections. Broad setting, relevant person, movement and some chronological progression appear in all 24 responses. That recognition does not establish correct location, depth, contact detail or timing.

| Prompt family | Railway: two responses | Gate: two responses |
|---|---|---|
| Open description | Both describe sitting, then walking along the platform; no track entry recovered | Both tentatively describe inspecting/working on lock or latch |
| Visible inventory | r01 says lowering onto track area; r02 describes platform sitting and walking away | r01 describes approach/crouching without explicit handling; r02 describes working on padlock |
| Temporal sequence | Both substitute platform sitting/rising for the reviewed descent/occupancy | Both describe approach, tool/latch interaction and crouching |
| Direct action | Both answer **No**, explicitly denying movement down into track area | Both answer **Yes** to contact/manipulation; r01 explicitly separates this from opening |
| Spatial/contact detail | Both deny lower limbs below platform top; both contradict themselves about sitting at edge | Both describe hand/latch contact; precise hands and object identities unverified |
| Separate action stages | Both label descent and occupancy observed, but support this with crouching/legs over tracks at incorrect times | Both label handling observed and opening not observed |

Railway: **3/12 responses assert entry or track occupancy; 9/12 describe platform-only movement or deny entry.** The three are inventory r01 and separate-stage r01/r02. Gate: **9/12 explicitly describe handling, 2/12 tentatively describe work on the lock, 1/12 omits explicit handling**. Omission is not a denial. Tool identity, forced entry and criminal intent remain unestablished; these responses do not establish successful opening.

Across the 12 scene/family repeat pairs, **10/12 agree on the reviewed action-claim category**, with disagreements in railway inventory and gate inventory. Only **1/12 is byte-identical text**, the railway spatial pair. This is coarse within-source agreement, not a reliability estimate. Both railway separate-stage answers claim occupancy but disagree about subsequent walking along versus away from the tracks. Consistent repeated output can still be wrong.

## Perception, interpretation and conclusion

The railway person and setting are recognized, so this is not simply failure to notice a person. The dominant error is the described spatial/action sequence: sitting and rising on the platform replace reviewed descent and track-area presence. Direct-action **No** is consistent with that incorrect description. It is therefore not evidence of a correct visual description followed by an isolated wrong binary label. We cannot determine whether the underlying cause is source retrieval, sampled frames, spatial representation or another internal mechanism; the gateway exposes no consumed frames or sampling trace.

There is **partial wording recovery, not robust event recovery**. Inventory r01 explicitly says “lower themselves onto the track area,” but describes sitting and a subsequent route toward the waiting area. Both separate-stage responses mark body movement down and occupancy observed while citing crouching with legs extended over tracks at **3–9 seconds**. The accepted snapshot review places visible descent about **10 seconds** after the requested start and clear track-area presence about **10.5 seconds**. Those answers do not reliably distinguish proximity/seating from actual entry. No tested prompt gives a repeatable, fully faithful account of the reviewed railway transition and subsequent location.

Two explicit self-contradictions occur in the identical railway spatial answers: they first say “they crouch and sit on the platform edge” and later “The person is not sitting at the edge.” The separate-stage positive labels also overstate what their crouching evidence alone establishes. These are useful examples of why an action label must be checked against its supporting description, not counted automatically as a correct detection.

Gate handling is substantially more often described in this campaign. The direct answers and separated stages demonstrate that manipulation can be recognized without requiring the gate to open. Their descriptions support their handling conclusions; no new handling-versus-final-decision contradiction was found. Exact hand use, orange tool versus small key, and padlock mechanics vary and are not independently established. Descriptive prompts expose useful evidence but also unsupported specificity.

## Comparison with v1–v4

All eight earlier railway/gate incident evaluations returned `not_observed` using the same observed `traffic-general` model identifier. Historical gate v1/v2 describe manipulation yet reject the incident because success/opening is absent: those are evidence/decision mismatches relative to the visible-handling task. Gate v3/v4 instead deny handling in their descriptions; their negative outcomes are internally consistent but disagree with the accepted reference. The new direct/separated answers recover handling without opening, suggesting task framing matters. The inventory repeats show remaining variability.

Railway v1–v4 deny entry. The new direct and most descriptive prompts preserve that denial; inventory/separated prompts sometimes elicit track-area claims. Requested URI/prompt pairs are controlled within each new repeat pair, but earlier bounds differ. Even identical local railway export bytes do not prove the gateway consumed identical frames. These observations support output sensitivity to prompt/source context and within-pair variability; they do not isolate a hidden causal mechanism or measure model accuracy. Total audited task responses are **32 across the same two known loop families**, not 32 distinct events.

## Demonstration and decision

The clearest railway comparison is direct r01 (`55d04b4f-b884-479d-892a-d8a14ed36ad8`, explicit denial) versus separate r01 (`efdd3c62-3efa-4437-b959-91dbce8f314c`, occupancy claimed with early/crouching evidence), beside the accepted reviewed transition. The clearest gate example is direct r01 (`3736db1a-c8ba-4f99-ab4a-f81425dc0c2a`): handling **Yes**, gate opening absent. Compare that with historical gate v1's manipulation description plus negative incident outcome. Show the [presentation comparison](diagnostic-comparison.svg) without private footage or credentials.

**NO-GO for independent AI verification as a validated reliability flagship. GO for a carefully qualified evidence-disagreement demonstration.** This campaign strengthens the case for checking spatial evidence and separating action from incident interpretation, but does not validate the current CV layer. Its original bounding-box/polygon candidate fires **3.5–4 seconds early on the October 22 calibration source**; that remains a proximity warning, not confirmed entry. No pose inference, threshold tuning, new training or independent CV validation occurred. Do not align that older trigger directly to the new source timestamps. Distinct positive events and task-matched hard negatives remain missing.

All further Hafnia inference stops here. Recommended next work is offline physical-region/pose calibration with uncertainty retained, followed by distinct held-out footage before any accuracy or added-value claim. No additional inference batch is proposed for immediate execution.

Reproduce with `scripts/reliability_diagnostic_report.py` offline. It opens ledgers read-only, verifies all 24 exact request/source identities, preserves literal responses privately, checks the 16 original historical response-file hashes and all four unchanged REL26-B response hashes, and writes [sanitized per-request results](../../results/reliability/completed-diagnostic-24.json). Semantic codes are explicit AI review judgments against the accepted AI demo reference, not an independently validated classifier or human attestation. Full prompts remain unchanged in [the frozen matrix](diagnostic-24-matrix.json); raw envelopes, recordings, actual camera GUIDs and credentials remain outside Git.
