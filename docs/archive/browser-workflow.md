# Browser workflow — 26 October 2026

On p022, open http://127.0.0.1:8770 in the VM browser. Incidents is the default. Open Demo mode for Start/Continue, Pause, Next observation and New demo session. Replay uses saved XProtect, Linux CV and Hafnia evidence; arrivals are synthetic and do not add independent evidence.

Open an incident before replay completes. Later arrivals join that investigation and show an evidence-change message. Inspect localization, sampled stationarity and recorded Hafnia interpretation. Save review retains the finding; Dismiss incident removes it from the open queue and retains it in Incident history. Reload to verify persistence. Native XProtect action is explicitly unavailable in replay.

Run `bun frontend/scripts/check-recovery.mjs` against the prepared server. It covers both 1440×900 and 1920×1080, including real HTTP 409 races, no automatic stale decision save, explicit retry, playback/overlays, navigation, durable dismissal, unavailable native calls, unauthorized HTTP 403 and duplicate prevention. The expected conflict is deliberately induced only in the regression check.

Run `bun frontend/scripts/capture-operator.mjs` for clean footage with no fault injection. It shows repeated arrivals joining an open incident, real saved CV and Hafnia evidence, successful review/dismissal feedback and persistence/history. It records both resolutions and asserts no browser errors or failed HTTP responses. Results remain in ignored `runs/recovery-capture/`.

See [README](../../README.md) for setup and [recovery sprint](recovery-sprint.md) for actual evidence, release scope and native gates. Keep the Polar deck unchanged and the submission video under 3 minutes.
