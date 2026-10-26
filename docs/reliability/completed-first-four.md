# REL26-B: completed four-request diagnostic batch

All four authorized requests completed on 26 October 2026, 22:50:20–22:50:42 UTC. All returned `not_observed`; all parsed as valid model decisions. There were four requests over two previously known loop families, zero independent new events, zero additional controls and zero further submissions during analysis.

| Experiment | Gateway status | Summary ID | Raw / parsed outcome | Formatting deviation |
|---|---|---|---|---|
| railway-v3-r01 | Completed | 7910ad97-dc88-4034-baf8-bc828d8eded4 | not_observed / not_observed | Markdown JSON fence |
| railway-v4-r01 | Completed | 1fa7b22e-7a04-4c6f-9a7a-b0a1bfe1281b | not_observed / not_observed | Markdown JSON fence |
| gate-v3-r01 | Completed | 30e2f6e6-8f5a-47be-9c46-e8edde88bdce | not_observed / not_observed | Markdown JSON fence |
| gate-v4-r01 | Completed | 94375b74-db44-40f6-8238-18fb9895ac2a | not_observed / not_observed | Markdown JSON fence |

Every experiment has the `REL26-B-` prefix. The ledger binds exact committed prompts and video URIs to returned requests and summary IDs. Railway requests used 22:03:53–22:04:06 UTC; gate requests used 22:03:51–22:04:03 UTC. The [source report](fresh-preflight.md) preserves hashes, reviewed continuity and export timestamp limitations. All 16 historical response files remain hash-identical. Original raw responses and the new raw gateway results remain private; [sanitized results](../../results/reliability/completed-first-four.json) contain prompts, source hashes, decisions, evidence text, formatting status and historical comparisons. No credentials, camera GUIDs or footage are included.

## Evidence comparison

| Scene | v1/v2 historical responses | v3/v4 fresh responses | Reference comparison |
|---|---|---|---|
| Railway | Both deny descent and describe remaining on the platform | v3 again describes remaining on the platform; v4 denies descent and describes the platform as flat with no track-bed material apparent | Contradicts accepted visual review of descent and subsequent track occupancy |
| Gate | Both describe manipulation of a padlock with a tool, but return not_observed because opening or success is absent | v3 describes approach and crouching but denies grasping/manipulation; v4 stresses a stationary gate and denies manipulation | Conflicts with accepted visible-handling assessment and with historical evidence descriptions; tool identity, opening, forced entry and intent remain unestablished |

The historical gate responses contain an evidence/decision mismatch for a task asking about visible manipulation: their evidence affirms manipulation while their decision appears to require successful opening. Tool identity itself is not independently established. The new responses do **not** affirm manipulation and then reject it; their evidence and decisions agree internally. Their disagreement is with the reference review and historical descriptions. A stationary gate alone does not disprove handling, and both new prompts explicitly remove successful opening as a requirement.

Railway v3/v4 show an unresolved visual or spatial interpretation miss, rather than recovery through these prompt changes. Railway v4 also risks interpreting “descent” as a scene feature rather than the person's action. No positive change in decisions occurred. Gate evidence wording changes substantially across prompt/source versions, suggesting prompt/task sensitivity, inference variability or source-phase differences; this experiment cannot separate those causes. Gate v3/v4 also broaden the original tool-specific task. Historical and fresh recordings are correlated loops with different source bounds, not a paired prompt-only trial. Gateway-internal decoding, temporal sampling and actual model-consumed frames are unavailable, so local video review does not prove which frames the VLM received.

## CV and decision

The independent railway geometry candidate remains 3.5–4 seconds before reviewed entry, driven by a seated bounding-box bottom crossing the polygon edge by only 0.173 horizontal pixels. It is a proximity candidate, not an automatic confirmed-entry detector. The accepted reference identifies descent and track occupancy separately. These saved predictions disagree meaningfully with Hafnia's persistent denial, but calibration on the same loop, fragmented tracks, ambiguous seated contact and missing hard negatives prevent a validated added-value or failure-rate claim. See the [frame audit](../../results/reliability/railway-frame-audit.json) and [visual timing comparison](railway-timing.svg).

**NO-GO for independent AI verification as a validated flagship.** The demo can show an evidence-backed disagreement with explicit timing/uncertainty limits. Four more negative decisions do not supply independent event coverage or validate CV accuracy.

## Proposed next batch — not submitted

Propose exactly four diagnostic requests, with no repeats or controls: one neutral visible-action inventory and one explicit spatial/contact question for each scene. Proposed new IDs are `REL26-B-railway-v5-r01`, `REL26-B-railway-v6-r01`, `REL26-B-gate-v5-r01`, and `REL26-B-gate-v6-r01`. Freeze full prompts, source bindings and an output schema before execution; this proposal is not an executable plan or submission authorization.

Railway v5 should ask for the person's chronological locations without naming a desired action. Railway v6 should ask whether the person is visibly below the platform top and where they subsequently stand, allowing unknown contact. Gate v5 should inventory hand/body contact without identifying a tool or intent. Gate v6 should separately assess visible handling and gate opening, preventing the latter from becoming a prerequisite for the former. Compare descriptions before binary outcomes. Use the same reviewed source bounds across the four relevant cells if still retrievable and under 24 hours; otherwise acquire and review new sources explicitly. Do not manufacture shorter clips. First seek read-only evidence of the gateway's actual sampled frames or retrieval diagnostics if supported; input uncertainty may be more informative to resolve than spending additional calls.

Distinct platform-only and gate-without-handling footage remains a prerequisite for a later hard-negative batch; eligible count is currently zero. Keep Stage C at zero until suitable footage exists.

Reproduction: run `scripts/reliability_batch_report.py` offline. It opens the ledger read-only, verifies four exact experiment identities and prompt/URI matches, raw/parsed agreement and all 16 original response hashes. The PowerShell coverage JSON reader was corrected to UTF-8 with optional BOM; 17 runner tests pass. No thresholds or reference annotations were changed.
