# Browser workflow and recording checkpoint â€” 26 October 2026

The motion ends. The incident doesn't.

## Operator demonstration

Open the locally prepared application at http://127.0.0.1:8769/#/monitoring.
Choose **New demo session**, then **Start replay**. Six controlled arrivals form
two incidents with three observations each. Open either incident, inspect the
saved imagery, object location, stationarity and Hafnia interpretation, add a
review note and choose **Mark reviewed**, then **Dismiss** or **Request
escalation**. Reload to confirm the saved decision. Native escalation is
unavailable in replay. Pausing and stepping arrivals is also supported.

Replay sessions use their own databases. Reset creates a new session and retains
the previous session's decisions; it never resets the source index or dispatch
ledger. Repeated imagery demonstrates grouping, not independent observations,
removal, recurrence or operational accuracy.

## Administrator preparation

From the repository root, after building the existing frontend:

```powershell
.\.venv\Scripts\python.exe -m adaptive_watch.evidence_api --root runs/operator-demo-final2 serve --demo-source runs/product-evidence --evaluations C:/Users/Administrator/adaptive-watch-private/hafnia-16 --frontend frontend/dist --port 8769
```

These paths are local demonstration inputs, not a portable evidence bundle.
The loader requires genuine saved raw Hafnia records and validates source
manifests, CV, joined records and imagery. It fails closed if they are absent or
changed. No credentials or Event Server addresses are passed to the browser.

Sources are the saved scooter and bin XProtect recordings from 22 October,
represented by timestamped snapshots, their recorded local CV trajectories and
genuine recorded Hafnia interpretations. The arrival schedule is synthetic.
No new Hafnia request or native event is made. Original continuous scooter/bin
video has not been verified as an export; do not label the snapshot sequence as
the original video sequence.

## Checks and capture

The frontend production build passed. Python regression checks ran 119 tests:
102 passed, 17 optional ML checks skipped. Offline tests explicitly mock and
assert zero Gateway submission and native send calls during replay. Browser
checks passed at 1440Ã—900 and 1920Ã—1080, with two incidents, three observations
each, decisions surviving reload, no external requests and no page errors.

Run `frontend/scripts/check-demo.mjs` with Bun and Playwright's installed Edge
channel. Set REVIEW_URL to the prepared server and PLAYWRIGHT_BROWSERS_PATH to
the local Playwright tooling directory. The script resets only replay sessions.
Screenshots, browser-report.json and recordings go to ignored
`runs/operator-demo-capture/`; lifecycle-WIDTH.webm provides stable filenames.

Use short cuts in the existing Polar deck: saved sequence, CV object location
and stationarity, Hafnia interpretation, six arrivals forming two incidents,
review and saved decision. Keep the deck as the narrative and the application
captures as evidence. Do not include a native alarm clip until verified. No
presentation rebuild is included in this change.

## Live action and remaining verification

Administrator-only `--native-config` enables the backend action service and is
mutually exclusive with replay. Its private JSON contains configured=true,
configuration_verified_by/at, event_name, destination_label, target, an existing
ledger path and incidents mapping camera GUIDs to root and spatial paths.
Only enable it after independently verifying the configuration and evidence.
The local cookie/CSRF session protection is not authenticated operator identity
or production authorization. Bind any deployment to a real identity and access
control layer before operational use.

The operator reviews, requests escalation, opens the confirmation, explicitly
checks authorization and confirms one event. The one-use, expiring backend
confirmation binds the incident, evidence revision, destination, configuration
and action. Changes require another review. Persistent reservations and the
existing dispatch ledger suppress duplicate/uncertain sends. Transport acceptance
is displayed separately from Smart Client verification; never retry an uncertain
send without administrator reconciliation.

With explicit configuration permission, the dedicated event was created as
92e13f24-2fea-4c0a-b7c9-cc40c6379ab2 and the alarm definition as
c5c54858-0706-4cb1-bb09-454bf1e8f71e. Source and related camera are exclusively
the scooter camera 8b27a358-df7e-496b-8dac-722d0f4b151c. Existing High priority
8188ff24-b5da-4c19-9ebf-c1d8fc2caa75 was retained. No event was sent.

The current polygons remain unapproved. The offline calibration comparison
supports reusing camera-specific approved geometry across recordings only when
all bound frame checks pass; ambiguous or shifted views require reapproval.
Its conservative ORB thresholds are an engineering gate, not measured accuracy.
Actual camera review and a real calibration run remain outstanding. Recent CV
evidence is preserved in runs/lifecycle-native-final-20261026; do not replace it
with synthetic repetitions. Check recording availability before any authorized
fresh inference.

Next gates: camera-specific polygon approval, valid coherent recorded evidence,
exact human authorization to send, then separately record transport result,
Smart Client alarm ID, camera, playback and actual overlay behavior. The earlier
property-damage alarm ID 3 does not verify this dedicated event.
