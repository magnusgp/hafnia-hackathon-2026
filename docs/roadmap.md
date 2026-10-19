# Scope and gates — Hafnia Hackathon 2026

## Prototype 0.1: The native round-trip (current)

Scenario: `vandalism` camera, demonstrably positive and negative recorded intervals. This is a *test fixture*, not a final vertical/product.

1. Verify `GET /api/System/Information`, `GET /api/Models`, analytics event options.
2. Use named camera ID from MilestonePSTools; saved prompt via gateway API; one inference per explicit CLI invocation.
3. Inspect raw response; use one of `H26_DAMAGE_EVENT`, `H26_NO_DAMAGE_EVENT`, `H26_UNCERTAIN` and reject invalid formats in the Python client.
4. Configure an XProtect analytics event and alarm definition; attach gateway rule to saved prompt.
5. Demonstrate Hafnia inference results in native Alarm Manager; operator verifies source video.
6. Record evidence of reproducibility (commands, sanitized screenshots, tests, non-secret config exports).

**Gate:** one known positive causes a native alarm, and one negative/uncertain does not; gateway ID preserved; no uncontrolled triggering. If gate fails, diagnose integration and do not expand scope.

## Prototype 0.2: XProtect-initiated request

Create a deliberate *user-defined* event for testing. XProtect rule -> webhook -> Hafnia -> XProtect analytics event -> alarm. Do not connect to motion events or to its own output analytics event. Verify both UI and underlying event IDs.

**Gate:** trigger once manually, observe exactly one Hafnia request and one expected XProtect event/alarm (no recursion).

## Prototype 0.3: General decision/evidence service

After round-trip works, move classification/state schema into a Python service. Preserve original gateway summary ID, camera, UTC interval, raw response, extracted observations, decision, and versioned policy. Implement abstention, controlled actions and read-only operator evidence inspection. Evaluate against curated, non-leaking examples from at least two camera scenarios. Don't auto-close an alarm.

**Gate:** evidence points to original clip; decisions reproducible; negative/uncertain paths tested; own model not needed yet.

## Concept selection (not yet decided)

We previously considered scene contracts, alarm arbitration, physical-state verification, adaptive local monitoring, and multi-camera incidents. Choose only once actual recordings/API capabilities and one native round-trip are demonstrated. The T4 could host a small detector or scene-specific model later, but add it only for an empirically established capability gap.

## Explicitly out of scope until a subsequent milestone

- React UI, MIP SDK plugin, autonomous security decisions, closing alarms automatically, foundation-model fine-tuning, periodic polling, large agent chains, production cloud deployment.
