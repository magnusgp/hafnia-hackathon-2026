# Scene Contracts v0.2

v0.1's Windows native round-trip is validated. v0.2 is implemented and tested offline on Mac; **its XProtect REST integration has not been tested on the Windows VM**. Do not change services, firewall, Tailscale, alarm definitions or the saved gateway rule to try it.

## Architecture and data

`hack26.py` keeps the v0.1 commands and helper imports. Transport/helpers now live in `scene_contracts/gateway.py`. `scene26.py` adds the explicit recorded-interval workflow, without a service or scheduler:

```
versioned JSON contract + exact camera name + recorded UTC interval
    -> existing saved prompt -> one explicit Hafnia submission (--apply)
    -> strict contract assessment -> SQLite observation + camera/contract review case
existing result file or summary ID -> same assessment/persistence, no inference
XProtect HTTPS REST reads -> candidate audit -> optional operator-confirmed local link
```

`contracts/property-damage.json` contains the unchanged validated v0.1 prompt. Outcome tokens and evidence fields belong to the contract, not the evaluator. Add another JSON contract with a unique ID, camera names, expected observable condition, assessment prompt, token-to-outcome map, response fields, positive evidence fields and operator action. `gateway_prompt_title` is optional: when present, evaluation requires an existing saved prompt with identical text. A contract without it uses an inline prompt and does not install a rule. Increment `version` whenever the assessment policy/prompt changes; preserve older revisions in Git. The full policy snapshot is retained with each observation.

SQLite `observations` records summary ID (unique), camera GUID/name, UTC clip bounds, contract ID/version/snapshot, raw response reference and payload, parsed decision/outcome/evidence/reason, creation time and case ID. The raw reference points to the immutable `raw_response` column in the same database, so moving the database preserves evidence. Only `Id`, `Progress` and `Response` are retained from the gateway envelope; authentication/session objects are never saved. The original v0.1 run file remains untouched.

`cases` groups **all observations for a camera and stable contract ID**, across versions. It is an operator review thread, not an assertion that every clip is a distinct incident or that all clips describe one physical incident. Different summary IDs, including repeated footage from a camera loop, remain observations in this thread. No incident counting or automatic incident separation is attempted. Reingestion with the same summary ID and identical content/provenance does nothing; conflicting content, camera, interval or policy is rejected transactionally. Pending summaries must be fetched again once terminal. Failed summaries become uncertain observations.

State transitions: an initial negative creates `observed`; positive/uncertain creates or changes a case to `review_required`. Explicit `review --note` changes it to `reviewed`, with an audit entry. New positive/uncertain evidence reopens review; negatives never clear a review requirement or assert physical resolution. `history` records observations and operator reviews; `alarm_checks` retains candidates, ambiguity, trigger window, operator note and optional native alarm GUID. Local state has no effect on native alarms.

The parser requires exactly one decision and each configured response field exactly once, one field per line, no extra prose or alternative tokens. Unknown/duplicate/missing fields, non-text responses and incomplete results cannot become positive. Positive evidence fields must contain concrete text rather than empty values or common abstention placeholders. This is a structural evidence gate, not verification that the model's description is true; operators must verify footage. Conservative format rejection can increase uncertainty.

**The saved gateway keyword rule acts before this Python assessment.** A malformed response containing its positive token might still trigger a native alarm. v0.2 does not change that working rule and cannot retroactively gate it. Only the local case assessment is evidence-gated.

## Windows VM commands

After committing and pushing these development changes, run from the Git checkout in Windows PowerShell. `uv sync --frozen` selects Python 3.11 from `.python-version` (no third-party Python packages). All examples use placeholders for real recorded/trigger intervals; choose verified footage, not invented times.

```powershell
git pull
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python hack26.py inspect --system-only
uv run --frozen python scene26.py contracts

# Existing read-only MilestonePSTools connection; creates only a local camera catalog.
Connect-Vms -ServerAddress 'http://localhost' -AcceptEula
Get-VmsCamera | Select-Object Name, Id | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 cameras.local.json

$clipStart = 'REPLACE_WITH_KNOWN_RECORDED_UTC_START'
$clipEnd = 'REPLACE_WITH_KNOWN_RECORDED_UTC_END'

# Offline preview: no login, network request or database write.
uv run --frozen python scene26.py evaluate --contract property-damage --camera vandalism --camera-map cameras.local.json --start $clipStart --end $clipEnd
# Explicitly spend ONE request; existing gateway rule may create a native alarm.
uv run --frozen python scene26.py evaluate --contract property-damage --camera vandalism --camera-map cameras.local.json --start $clipStart --end $clipEnd --apply

# Import a v0.1 run file without any network request or VLM call.
uv run --frozen python scene26.py ingest --contract property-damage --camera vandalism --camera-map cameras.local.json --start $clipStart --end $clipEnd --file runs/REPLACE_SUMMARY_ID.json
# Or GET a saved gateway result; prompts for gateway authentication, never submits inference.
uv run --frozen python scene26.py ingest --contract property-damage --camera vandalism --camera-map cameras.local.json --start $clipStart --end $clipEnd --summary-id REPLACE_SUMMARY_ID

uv run --frozen python scene26.py cases
uv run --frozen python scene26.py case 1
uv run --frozen python scene26.py review 1 --note 'Reviewed source footage; findings recorded by operator'
```

Use `--camera-id VERIFIED_GUID` only if a catalog cannot be exported; `--camera` must still match the contract. Exact names with duplicate catalog entries fail rather than picking a camera. UTC offsets are normalized; intervals currently require whole seconds to match the v0.1 gateway video URI helper. When a raw result has `VideoUris`, ingestion checks them against supplied metadata. Older responses without video metadata require the operator to provide verified camera/clip provenance; the model response alone does not establish it.

Evaluation writes `runs/summary-<sha256-of-ID>.json` with contract/clip metadata and the latest raw result. The initial submitted summary ID is printed and saved before polling; failures/timeouts must be recovered by GET/ingest, never automatic resubmission. Recovery manifests can be passed to `ingest --file` with the same contract/camera/interval; conflicting metadata is rejected. A POST transport failure may have reached the gateway even when no ID was received: inspect gateway History before retrying. SQLite persistence and gateway submission are not one distributed transaction.

`--db` and `--contracts-dir` are global flags, before the subcommand. Defaults are `runs/scene-contracts.sqlite3` and the checkout's `contracts/`. `runs/`, camera catalogs (`*.local.json`), databases and `.env` are ignored; protect these files using the VM account's filesystem access controls. Video descriptions and camera identities are sensitive even without credentials. Do not commit raw runs or tokens. Do not pass passwords on command lines; use interactive prompts (environment credentials are supported for controlled local use).

## XProtect REST dependencies and authentication

Use the **XProtect API Gateway HTTPS origin**, not Hafnia's port 15443. Confirm its actual address on the VM. Relevant services can be discovered at `/api/.well-known/uris`; do not install or reconfigure services as part of this task. This implementation uses only read operations against Events/Alarms; its authentication token exchange is the sole POST. It never triggers events or creates/updates/dismisses alarms.

The [official API Gateway overview](https://doc.developer.milestonesys.com/mipsdk/reference/protocols/api-gateway.html) identifies `/api/rest/v1` as the REST entry point. The [Configuration API authentication documentation](https://doc.developer.milestonesys.com/mipvmsapi/api/config-rest/v1/) describes OAuth bearer authorization. The client uses the documented Basic-user password grant at `/API/IDP/connect/token` with `client_id=GrantValidatorClient`; credentials/tokens remain in memory, redirects are refused, and TLS verification is enabled. `--ca-file` / `XPROTECT_CA_FILE` can trust an existing PEM CA bundle without changing system certificates. There is no insecure-TLS flag for this client.

An already obtained token can be supplied as `XPROTECT_TOKEN`; otherwise username/password are prompted, with optional `XPROTECT_USERNAME` / `XPROTECT_PASSWORD`. Windows integrated authentication is not implemented; use an authorized Basic account already available or a token obtained through the site's documented authentication flow. No account or role changes are performed by this tool. Expired tokens fail and must be replaced; they are never persisted or printed.

The [official Alarms REST reference](https://doc.developer.milestonesys.com/mipvmsapi/api/alarms-rest/v1/) documents `GET /alarms`, bearer auth, trigger-time/source filters and paging. The tool reads complete bounded collections, rejects unknown shapes and refuses association on pagination failure. Alarm Manager licensing and account visibility affect results. The [Events REST reference](https://doc.developer.milestonesys.com/mipvmsapi/api/events-rest/v1/) documents `GET /events` for retained events; an empty result may reflect retention or permissions. The official references are living documentation, not proof of the VM's deployed 2026 R1 schema.

```powershell
$env:XPROTECT_URL = 'https://REPLACE_WITH_ACTUAL_API_GATEWAY_ORIGIN'
# Optional existing CA bundle:
# $env:XPROTECT_CA_FILE = 'C:\path\existing-ca.pem'
$triggerStart = 'REPLACE_WITH_UTC_BEFORE_INFERENCE_COMPLETION'
$triggerEnd = 'REPLACE_WITH_UTC_AFTER_INFERENCE_COMPLETION'
uv run --frozen python scene26.py alarms --start $triggerStart --end $triggerEnd
uv run --frozen python scene26.py events --start $triggerStart --end $triggerEnd
# Saves candidates locally; makes only REST reads.
uv run --frozen python scene26.py associate --case-id 1 --alarm-name 'EXACT_NATIVE_ALARM_NAME' --start $triggerStart --end $triggerEnd
# Only after verifying the unique candidate against the summary/footage in Smart Client:
uv run --frozen python scene26.py associate --case-id 1 --alarm-name 'EXACT_NATIVE_ALARM_NAME' --start $triggerStart --end $triggerEnd --alarm-id VERIFIED_ALARM_GUID --note 'Operator verified source footage and gateway execution against this alarm'
```

These commands modify only local case evidence. They need no `--apply`: remote operations are read-only. More than one candidate records `ambiguous` and **cannot** link, even with `--alarm-id`. Exactly one records `unconfirmed` unless the operator supplies both its GUID and verification note. No candidate records `not_found`; none of these statuses proves alarm absence outside the user's visibility/window. Camera, exact alarm name and trigger time alone are insufficient proof of causation. The current gateway contract exposes no verified shared correlation ID, so automatic association is deliberately deferred. Alarm time usually reflects inference/event processing, not the historical clip time.

## Verification gates and limitations

Offline tests cover all three outcomes, generic conditions, malformed responses, missing evidence, state transitions, transactional persistence/idempotency, duplicate loop observations, dry-run isolation, camera lookup, retrieval pagination, authentication/redaction and ambiguous associations. Tests use fake clients and synthetic protocol fixtures; no real VLM or VM requests occur. **No captured real response was supplied in this checkout.** `tests/fixtures/` is explicitly representative, not claimed to be captured gateway output. Add sanitized recorded Completed positive/negative/uncertain responses from the VM before claiming real-response regression coverage.

VM gates still required:

1. Run frozen setup and offline tests on Windows Python 3.11; confirm v0.1 inspect/run compatibility using existing known results first.
2. Export camera catalog; ingest a real saved result twice. Verify raw evidence, contract/clip provenance and unchanged observation count.
3. Run a known interval dry, then once with `--apply` only when desired. Check saved prompt match, response format, gateway ID, persistence and recovery. Check Smart Client for the existing rule's behavior.
4. Verify actual API Gateway origin/CA and authorized account/token, deployed schema/pagination, retained event visibility and alarm reads. Authentication or missing routes are gates to report, not reasons to alter VM services.
5. Verify native source GUID/name, alarm trigger time and exact alarm name. Inspect a unique candidate in Smart Client before linking; exercise missing and ambiguous cases without creating test alarms. Confirm no external state changes.

No continuous monitoring, incident separation, automatic dismissal, physical resolution inference, UI, training or C# plug-in is included.
