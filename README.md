# Hafnia Hackathon 2026 — Scene Contracts

**Current direction: Adaptive Watch — hybrid, evidence-grounded XProtect video intelligence.**
The [initial hybrid milestone](docs/adaptive-watch/hybrid-milestone.md) records the
railway CUDA detection/tracking proof of concept, guarded six-scene evaluation
runner, provenance fixes, and remaining authentication-dependent Hafnia evaluation.
The older console and experiment descriptions below are historical work; no new
frontend is being built. The fog classifier failed its preregistered superiority gate.

> **Adaptive Watch (branch `feat/adaptive-watch`):** camera-specific visual novelty as a pre-filter for Hafnia. Checkpoint A (ML feasibility) — [report](docs/adaptive-watch/checkpoint-a.md), [pre-registration](docs/adaptive-watch/preregistration.md). **ML recovery sprint (2026-10-21):** [handoff](docs/sprint-handoff.md) — T4/XProtect runbook, visibility task ([results](docs/visibility/results.md)), native analytics XML events. The ML code is opt-in: `uv sync --group ml`, then `uv run --group ml python aw.py --help`.

Give every security camera an operational responsibility. The local browser console provides fixed-template contracts, exact request previews, single recorded-interval inferences, persistent evidence cases and operator reviews. It works with saved Hafnia results while the gateway is unavailable.

**Start here:** [operator MVP setup, current limits, rebuild steps, real-data acceptance checklist and demonstration script](docs/operator-mvp.md). Run `.\scripts\start_scene_contracts.ps1` on p022, then open `http://127.0.0.1:8086` in the VM browser. Export the camera catalog first as described in the guide.

New Scene Contracts evaluations send inline prompts **without the legacy PromptId**. The unchanged v0.1 route below remains a separate regression demonstration; its gateway keyword rule acts before Python validation. REST event writes and a second real roadway analysis remain VM acceptance gates. The [v0.2 architecture document](docs/scene-contracts-v02.md) is retained as historical context.

```powershell
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scene26.py contracts
uv run --frozen python scene26.py cases
```

Python is pinned to 3.11 with uv. No third-party Python dependencies. Existing v0.1 commands below are preserved.

## Validated v0.1 integration

This is a small Python *gateway integration proof*, not a product commitment. Its purpose is to verify `XProtect video → Hafnia VLM → decision token → gateway rule → XProtect analytics event → Smart Client Alarm Manager`.

## Boundaries

- Run on the Windows VM, because `https://localhost:15443` is only reachable there.
- Requires Python 3.11+, no third-party Python dependencies. The VM does not come with Python installed.
- The gateway's **local self-signed** TLS certificate is not verified by this sample. The client only accepts the localhost hostname. Never copy that TLS setting into a remote production client.
- Authentication prompts for the gateway password; no credentials are written to disk. Do **not** share it, and do not check it into Git.
- Installing a prompt/rule and spending a VLM request are opt-in via `--apply`. No automatic retries or scheduled requests.
- `runs/` is ignored by Git; review video-related data before publishing anything.
- **Do not** reset the gateway, change advanced connection settings, stop Tailscale, change the firewall, or restart services.
- **Do not** route motion events, or the output analytics event, back into the Hafnia webhook: this could make an expensive loop.

## First run

1. Install Python 3.11+ on the VM and open **Windows PowerShell** in the unzipped project folder.
2. Verify `py --version`, then `py -m unittest discover -s tests -v`.
3. Check quota and gateway: `py hack26.py inspect --system-only`. Inspect supported models/actions: `py hack26.py inspect`.
4. Find a camera ID: `powershell -ExecutionPolicy Bypass -File .\scripts\list_cameras.ps1`. Find the row named `vandalism`. Save the ID locally, not in code or the repo.
5. Preview new prompt: `py hack26.py install-prompt`; install: `py hack26.py install-prompt --apply`.
6. Preview a request: `py hack26.py run --camera-id YOUR-CAMERA-GUID`.
7. Execute exactly one request: `py hack26.py run --camera-id YOUR-CAMERA-GUID --apply`.
8. Inspect History and `runs/<summary_id>.json`; it should report a decision, evidence, and a gateway summary ID.

The default clip is 15 seconds ending 2 minutes before the current UTC time. Override with `--start 2026-10-19T12:04:09Z --end 2026-10-19T12:04:24Z` to inspect a **known recorded interval**, and with `--title` for a different saved prompt. Do not substitute invented timestamps or run a long interval without a reason.

## Wire a native XProtect alarm (manual bootstrap)

This stage is deliberately **not** automated until the UI behavior is verified.

1. In **Management Client** → **Rules and Events** → **Analytics Events**, create an event named `H26 Visually Observed Damage` (or use another distinctive name and pass `--event-name`). Consult `C:\HackathonKit\hafnia-vlm\references\worked-example.md` and `gateway-rules.md` for exact UI procedures. Enable analytics events/allowed address settings only as prescribed in those instructions; avoid changing network/firewall settings.
2. In **Alarms** → **Alarm Definitions**, define an alarm triggered by that analytics event. Set its source/related camera to `vandalism` where available, give the operator neutral instructions, e.g. *Review the source footage and verify the observed physical damage*. Save.
3. In the gateway, run `py hack26.py inspect` and confirm the new analytics event appears in available `TriggerAnalyticsEvent` options. Do not proceed if absent.
4. Preview the rule: `py hack26.py install-rule`; create once: `py hack26.py install-rule --apply`. It matches `H26_DAMAGE_EVENT` for requests using the saved prompt.
5. Execute a new **known positive** camera interval with `py hack26.py run --camera-id YOUR-CAMERA-GUID --start ... --end ... --apply`; verify `Completed`, the model's decision, and the XProtect Alarm Manager. Note that the gateway rule does keyword matching, not structured parsing: manually review each test.
6. Repeat on a **known negative or uncertain** interval to verify that the positive alarm is not triggered. This costs another completed VLM request.

Avoid using motion detection as a webhook input. A later iteration may use a manually triggered XProtect user-defined event or deliberately configured non-recursive webhook to drive the same flow.

## What isn't implemented yet

- Reading cameras by name directly from the XProtect REST API: use MilestonePSTools to resolve GUIDs in this first iteration.
- Controlled native alarm acknowledgements, continuous monitoring, learned CV models, or webhook origin automation. Cases, a fixed policy template and the local operator UI are implemented.
- Enforcing format semantics inside gateway rules: the gateway checks a whole-word keyword anywhere in the response. Python also checks a strict decision line, but the gateway does not use Python's validation; **never auto-close alarms on this basis**.

## Reproducibility

Store source code and test fixtures in Git (NOT secrets), and later script XProtect alarm/event configuration once manually verified. Do not depend on the VM's disk surviving a rebuild.
