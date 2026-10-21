# Scene Contracts operator MVP

Give every security camera an operational responsibility: an observable condition, an explicit recorded interval, a strict evidence assessment, and a persistent review thread. Unlike a one-off VLM conversation, the application preserves the exact policy, camera/clip provenance, summary identity, raw response, assessment, review notes and native-alarm association audit across sessions. Positive and uncertain evidence reopen review; negative evidence never claims physical resolution.

## Delivery status

Implemented: local operator UI, immutable contract creation using a fixed assessment template, exact prompt/request preview, explicit single inference submission, progress polling by existing summary ID, saved JSON/manifest import, strict assessment, durable cases/evidence/reviews and display of recorded native alarm checks. Two new responsibilities ship: property integrity and roadway visibility. `property-damage` remains the original v0.1 evidence-format contract for existing results.

Offline tests retain the original 28 test cases (two saved-prompt expectations updated for the requested separation), and add backend/HTTP/security/persistence regression coverage. Synthetic data is not real-analysis acceptance evidence.

**VM acceptance remains open.** This development session cannot execute commands on p022 or read its `C:\HackathonKit` material. A read-only HTTPS discovery probe on 21 October reached p022 but failed certificate validation with a self-signed certificate on the development Mac. That does not establish the Windows VM's trust status. No TLS bypass, trust-store change, account creation, firewall/service/Tailscale change or native write was performed.

REST events are deferred at the authentication/trust gate. The official [Events REST API](https://doc.developer.milestonesys.com/mipvmsapi/api/events-rest/v1/) documents `POST /api/rest/v1/events`, source/type resolution, and Windows-user `windows_credentials` token acquisition with NTLM. `scripts/test_xprotect_rest.ps1` provides a read-only VM probe using default Windows credentials, or an existing Basic user with `-BasicUser`. It preserves certificate validation and keeps a token in process memory; it is not yet VM-verified. If trust/authentication does not work within **15 minutes**, stop and use the already verified v0.1 demonstration separately. Event submission is deliberately unimplemented until the event type, source, authentication and deployed schema are actually verified. There is no disabled-looking write route that could accidentally send an event.

## Integration boundary

`hack26.py run` is unchanged: it resolves the saved prompt and sends the legacy rule-bound `PromptId`. The gateway can generate native alarms before Python validates that response. **It does not enforce the Python validation gate.** Preserve it for the regression demonstration only.

Both `scene26.py evaluate` and the UI send only inline `Prompt` and `VideoUris`, even when evaluating the old `property-damage` contract. They never resolve or send a saved `PromptId`, install a rule, or issue an application-controlled native event. Thus malformed, incomplete, uncertain and negative assessments have no positive-event path. The offline tests demonstrate request isolation; on the VM verify that the existing rule is scoped to its saved prompt and no unrelated/global gateway rule applies. Do not claim an end-to-end gated native alarm demonstration until a validated REST event route exists.

The UI displays `alarm_checks` created through existing `scene26.py associate` reads and explicit local operator confirmation. Candidate matching is never treated as proof of causation. `reviewed` is local review state; it does not acknowledge, close or resolve a native alarm.

## Windows startup and environment

From the existing checkout on p022, in Windows PowerShell:

```powershell
git pull --ff-only
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v

# Export the existing camera inventory. No VMS changes.
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula
Get-VmsCamera | Select-Object Name, Id | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 cameras.local.json

# Starts a loopback-only console and prompts securely for the gateway password.
.\scripts\start_scene_contracts.ps1
# Open in the VM browser: http://127.0.0.1:8086
```

For saved evidence only, use `.\scripts\start_scene_contracts.ps1 -Offline`. Existing v0.2 case #1 is immediately visible if it uses the default `runs/scene-contracts.sqlite3`. For another database run `uv run --frozen python scene_web.py --db 'PATH_TO_EXISTING_DB'`; live access requires `HAFNIA_GW_PASSWORD` in that process's environment. No password goes on the command line, into the UI, logs or the database. Stop with Ctrl+C. The launch script restores the previous environment value on exit.

Use the **127.0.0.1** URL exactly. The server refuses other Host headers and cross-origin form actions, uses an unpredictable action token, escapes evidence/review text, and loads all assets locally. It binds only to loopback; use the VM browser through the existing remote desktop. This is a single trusted operator workstation, not a network service or multi-user identity system. SQLite is additive to v0.2: existing tables/data remain intact; new tables store operator contracts and prepared requests.

Python 3.11 and uv are the only requirements; no packages, CDN, Node build or frontend bundle. `scene_web.py --help` lists local paths and port. `HAFNIA_GW_PASSWORD` is used only for local gateway access. The existing CLI uses `XPROTECT_URL=https://p022`, optional `XPROTECT_CA_FILE` pointing to an **existing verified** PEM CA, and an in-memory `XPROTECT_TOKEN` or existing Basic-user credentials. The UI never needs XProtect credentials to review stored cases.

## Read-only VM integration check (15 minutes maximum)

First read the deployed references before considering integration changes:

```powershell
Get-Content C:\HackathonKit\xprotect-hackathon\SKILL.md
Get-Content C:\HackathonKit\hafnia-vlm\SKILL.md
Get-Content C:\HackathonKit\hafnia-vlm\references\worked-example.md
Get-Content C:\HackathonKit\hafnia-vlm\references\gateway-rules.md
Get-Content C:\HackathonKit\xprotect-apis\SKILL.md
Get-Content C:\HackathonKit\xprotect-essentials\SKILL.md

# Certificate checks stay enabled. Stop if trust fails; do not use -k or install a cert blindly.
. .\scripts\test_xprotect_rest.ps1
# If an authorized existing Basic account is available instead:
# . .\scripts\test_xprotect_rest.ps1 -BasicUser
```

The probe reads discovery, attempts the documented IDP grant, and saves only type/camera candidate inventory to ignored `xprotect-candidates.local.json`. Paths must be checked against the deployed IDP discovery if different. It does not create events/types/sources/rules/accounts, and a successful login does not authorize a first write.

Before a future guarded event implementation: verify the exact event type GUID and generator type/subtype, camera/source GUID and permissions, alarm definition, deployed POST schema (including `datatype`), and recording-vs-trigger time semantics. Require a concrete operator preview/approval for the first live POST. Persist a unique per-summary dispatch claim **before** POST; retain unknown outcomes for manual reconciliation rather than retrying. An HTTP acceptance or event ID is not itself a verified native alarm link. No token, response containing a token, or credential object should be shared as troubleshooting output. Clear the process token afterwards with `Remove-Item Env:XPROTECT_TOKEN`.

## Recovery and persistence

The UI stores a request snapshot before any live call, then atomically changes `preview` to `submitting` before POST. Repeated submissions of that request are no-ops. Once received, the gateway summary ID is committed before assessment. Polling uses only GET; a gateway/network failure leaves evidence review available and lets the operator refresh that same ID. Closing the browser stops polling without cancelling or resubmitting the gateway job.

If POST acceptance is unknown or the process stops during `submitting`, inspect gateway History. **Never create a new inference just to recover a result.** With a recorded summary ID, use the existing CLI GET-only ingestion:

```powershell
# Choose actual contract/camera/interval from the original request preview.
uv run --frozen python scene26.py ingest --contract roadway-visibility --camera highway_traffic_overcast_weather --camera-map cameras.local.json --start $clipStart --end $clipEnd --summary-id $summaryId
```

A raw saved response can instead use `--file runs/ACTUAL_RESULT.json`, or be pasted into a preview's import form after verifying provenance. Use `property-damage` for legacy responses; the new `scene-property-damage` template uses different decision/evidence fields. Never reinterpret an old response under a new policy. Manifest imports require exact contract/camera/interval equality. Raw responses without `VideoUris` require explicit operator provenance confirmation. Duplicate summary IDs with conflicting policy, camera, interval or content are rejected.

An interrupted UI `submitting`/`importing` action is never automatically unlocked. Recover through CLI ingest; the case appears in the review queue even if the old request remains interrupted. CLI ingest works with checked-in contracts; for a custom UI contract, export its exact contract snapshot from the database to a private contracts directory and pass `--contracts-dir` before the CLI command. Avoid inference retries. This intentionally small recovery boundary replaces a background orchestration system.

## Rebuild

1. Clone the repository and run frozen setup/tests above.
2. Restore the private `runs/` directory (including SQLite and WAL files if any) from a backup taken while the application was stopped. Also restore the verified local camera catalog. No migrations/tooling/server provisioning are required.
3. Read the deployed HackathonKit material and verify gateway/VM environment. Existing v0.1 saved prompt/rule/alarm definitions belong to the VMS and are not provisioned by this app. Do not rebuild or alter those settings without approval.
4. Start offline first and check existing cases, exact contract snapshots and review history; then launch with the gateway credential when live work is needed.

`.gitignore` excludes local catalogs, run manifests/databases, secrets/certificates and common video formats. Do not commit real recording data or captured gateway responses without separate sanitization. Protect private evidence and backups using the VM account's filesystem controls.

## Real-data acceptance checklist

- [ ] Run the offline suite on p022's Python 3.11; check existing v0.2 case #1 without re-inference.
- [ ] Open the UI offline. Confirm real raw response, observations, limitations, summary ID, recording bounds, policy snapshot and review history; mark reviewed with a factual note and restart to verify persistence.
- [ ] Configure a new contract using a real catalog camera; confirm the exact resulting fixed-format prompt and reject an invalid interval/camera mismatch.
- [ ] Select `Property integrity` with a verified `vandalism` recording. Preview exact inline request and absence of PromptId. Explicitly approve once; record summary ID, terminal status, actual outcome and limitations. Verify native legacy rule did not execute for this new submission.
- [ ] Select `Roadway visibility` with `highway_traffic_overcast_weather`. Inspect the footage first and choose a known recorded UTC interval. Do not assume visibility from the filename. Explicitly approve exactly one inference, record its **actual** outcome and visible supporting evidence. A structurally valid clear or uncertain assessment is an honest result; never manufacture a breach for the demonstration. A malformed response is not a successful second analysis: refine/calibrate before spending another explicitly approved request.
- [ ] Retain this second real result privately; refresh/import it again without spending inference and confirm one persisted observation for its summary ID. This gate is still outstanding.
- [ ] Show offline replay of real saved results after stopping/restarting the UI without gateway credentials. Confirm evidence remains useful.
- [ ] Run the time-boxed REST probe. Record only TLS/auth success/failure, authorized route availability and verified non-secret type/source identities. No write without a separate preview/approval and idempotent dispatch implementation.
- [ ] Show the already verified native alarm separately in Smart Client. Run existing `associate` reads/explicit local confirmation only if its provenance can actually be verified; display unconfirmed/ambiguous checks honestly.
- [ ] Demonstrate legacy v0.1 PromptId behavior using existing run evidence first. Any new v0.1 call is an explicit extra inference and may trigger a native alarm before Python validation.

## Three-minute demonstration

1. **Responsibility (30 s):** Open Contracts. Explain the camera's observable job, expand the exact prompt, and show the different roadway-visibility responsibility.
2. **Controlled assessment (45 s):** Show a prepared real recording interval and exact request preview. Explain one explicit inference, no saved PromptId, strict format validation and visible limitations. Use an already completed real request if the live gateway is slow.
3. **Evidence and action (60 s):** Open the real completed case, inspect observations, evidence, limitations, summary ID and recording reference. Add a review note; show its persistence and the immutable policy snapshot. A chat answer alone does not provide this operational evidence/review workflow.
4. **Generalization and native workflow (45 s):** Open the second real roadway case and report the actual outcome. Show any verified native alarm/check in Smart Client and the UI, explicitly separating the legacy gateway-native route from the new inline assessment path. Disclose REST gate status. Finish by reopening cases offline.
