# Research record

Pre-registered experiments, negative results and reliability work from before and during the hackathon. This is the
evidence trail behind the product's limits. Files here are kept as written; they are not product instructions.

| Area | Documents |
|---|---|
| Anomaly-detection feasibility (pre-registered, gate not passed) | [preregistration.md](preregistration.md), [checkpoint-a.md](checkpoint-a.md), [hybrid-milestone.md](hybrid-milestone.md) |
| Fog and haze visibility (pre-registered, gate not passed) | [visibility/](visibility/preregistration.md), [results](visibility/results.md) |
| Hafnia reliability on recorded scenes (frozen protocol, diagnostic campaign) | [reliability/](reliability/protocol.md), [report](reliability/report.md), [completed diagnostic](reliability/completed-diagnostic-24.md) |
| Railway negative-result review (the flagship case) | [negative-result-review.md](negative-result-review.md) |
| Sidewalk MVP (scooter, bin) | [sidewalk-mvp.md](sidewalk-mvp.md) |

Result files (JSON) live in [`results/`](../../results/). Two of them, `results/reliability/completed-diagnostic-24.json`
and `results/reliability/railway-frame-audit.json`, are read by the application's source-integrity check, so they
stay at that path. The frozen matrices and definitions in `docs/research/reliability/*.json` are hashed by the
experiment scripts and tests; do not edit them.

All of this is controlled-scenario work: there is no accuracy benchmark and no production deployment claim.
