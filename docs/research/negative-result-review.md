# Negative-result review — October 27, 2026

This sprint implements one saved railway review. It makes no accuracy or independent safety-performance claim, and adds no inference requests. The existing Linux detector/tracker, Hafnia evaluation code, gateway code and XProtect transport are unchanged by this implementation. Pre-existing uncommitted work is excluded from its commit.

## Case and evidence decision

- Camera: `person_on_railway_tracks`; the exact original camera GUID remains in the private record.
- Original interval: **October 22, 11:03:39–11:03:52 UTC**.
- Original Hafnia summary: `5a1ab040-fc44-4156-ad7a-1eeecd8c7b60`; original decision **not_observed**. The main screen quotes its original first sentence; details retain its full original response and request.
- CV: existing Linux A10G Faster R-CNN output, revision `1163ddf94ef7252b8a41563c8ed5e2b46a925612`. Selected track **7**, with its original boxes. Approach track 1 is not merged into it. Missing observations stay missing.
- Initial risk condition: the selected bounding-box bottom has zero distance to the saved attention polygon at **11:03:44.513 UTC**. Distance is measured in normalized image coordinates, with zero inside the region. This is a proximity observation, never confirmed entry.
- Exact source frame indices, UTC timestamps, measured distances, original hashes, original response, available actions and separate pending human verification are retained in the immutable review record. SQLite keeps current region configuration, decisions, review notes and an append-only application audit.

The **24 completed diagnostic requests** are verified against their persisted read-only ledger and sanitized report. Their railway interval is **October 27, 11:55:38–11:55:51 UTC**, and is never aligned to the October 22 CV timestamps. The comparison image reports 3/12 railway responses claiming entry/occupancy and 9/12 describing platform-only movement or denying entry. These are qualitative response-claim counts from one known railway loop family, not accuracy estimates or independent events.

The saved entry bracket, 11:03:48.013–11:03:48.513 on October 22, comes from an **AI-reviewed calibration reference**. No human attestation was supplied. The human entry annotation therefore starts as `not_verified`, independent of both automated findings and that reference. Browser recordings are automated walkthroughs and retain `not_verified`; they are not human verification.

## Playback and operator flow

The original MKV is preserved and available in details. Its PTS-to-UTC origin remains unverified. The main video therefore encodes the original server-timestamped JPEGs in order at **2 fps**, without interpolation. Media time zero corresponds to **11:03:39.013 UTC**. A displayed timestamp denotes the original sample, not a continuous measurement. The UI labels the half-second sampling rate.

Preparation checks encoded frame count, PTS and image correspondence. The browser selects overlays by presented video-frame time; seeking hides boxes until the seek completes. No box is carried through a missed detection. The screen shows one selected track, its attention region, the original negative conclusion and relevant moments. Technical evidence is confined to the secondary details dialog.

The operator can draw a four-corner attention region directly on the footage; normalized coordinates and the proximity margin are also available in details. Changing the region creates a new workflow revision and clears prior review/annotation for the current decision. Original CV and evidence stay unchanged.

**Review footage** opens playback and the decision controls. **Dismiss** and **Save review request** require explicit footage-review acknowledgement. Human entry annotations other than `not_verified` require a supporting note. Decisions persist across reloads. A stale revision returns HTTP 409, refreshes the case and clears the acknowledgement. The saved request status says **Review request saved locally**, and the result explicitly says the decision is saved locally and **no native event has been sent**. A local request preserves camera, original interval and evidence association. Existing internal action/status identifiers are retained for compatibility; they do not dispatch an event.

## Integrity and native boundaries

Every evidence read and decision checks the immutable record digest and original source hashes, including all 26 JPEGs, CV output, manifest, raw Hafnia response, original export, diagnostic report, read-only diagnostic ledger and derived media. The import checks the CV hash against the existing frame audit, exact manifest equality, camera/interval identity, Hafnia request and original negative response, and all 24 diagnostic envelope identities. No original is rewritten.

The API binds to loopback, checks Host/Origin, uses a local HttpOnly SameSite cookie plus a session-bound CSRF token, rejects stale decisions transactionally and supports video byte ranges. This is a local prototype; the cookie is not authenticated operator identity. Annotation provenance says so explicitly.

`prepare_review_event.py` uses the existing XML serializer to prepare **Adaptive Watch Review Required** locally, retaining the original source camera, interval and summary association. XML and approval metadata remain private. It does not modify the configured event map, event definition, alarm definition or existing sidewalk integration. The new API has no configuration or native dispatch route; calls are rejected.

Native follow-up remains gated on:

1. Explicit authorization to create the new analytics event and camera-specific alarm definition.
2. Read-back verification of that actual configuration and retained recording availability.
3. Separate human approval of one exact payload and destination, using the existing persistent dispatch protections.
4. Verification in Smart Client of the actual alarm ID, associated camera and playback of the original interval.

No configuration or dispatch authorization was provided in this sprint. No native event was sent; no Smart Client alarm or playback verification is claimed. A local review request never claims railway trespass was automatically confirmed.

## Validation and assets

- Full Python suite: **157 tests, 17 skipped** (existing environment-dependent tests). Includes eight focused checks for integrity, stale decisions, review/annotation gates, region changes, persistent state, local CSRF and absent native dispatch routes.
- Frontend: TypeScript and production Vite build.
- Browser script: real-case copies at 1440×900 and 1920×1080; original summary, video duration, selected-box/UTC/frame synchronization (including a detection gap), region drawing, both final outcomes, persisted reloads, stale UI recovery and rejected native calls.
- Release browser reports and captures: `runs/negative-review-release-checks/`, separate from the preserved submission assets.
- Private historical assets: `runs/negative-review-checks/diagnostic-comparison.png`, operator recordings, screenshots, browser report and the **78-second evidence assembly** `adaptive-watch-negative-review.mp4`. `submission-video.json` records actual duration, source hashes and segment boundaries. The video and diagnostic image are preserved unchanged and can retain earlier action wording. This is **not the final narrated submission video**. The final submission still needs the existing Polar slides, narration, current UI evidence, limitations, a runtime under three minutes, claim/playback review and submission with the repository link and judge-access instructions.

Final release verification on p022 passed `git diff --check`, the full Python suite from an exact release-source snapshot excluding unrelated edits (157 tests, 17 skipped), the production frontend build, both browser viewports, and the source/evidence preflight. The preflight reverified source hashes, all 26 decoded frames, frame PTS and image correspondence. Tracked files and all 31 commits since the original main were scanned for credentials, private recordings and generated captures; only dummy credential URLs in security tests matched. All nine unrelated working files and the preserved submission assets retained their original hashes. Local reports remain under ignored `runs/final-release/` and `runs/negative-review-release-checks/`.

The production page, case API and video byte ranges were verified on port 8776. For judging, the existing API was started as a temporary hidden process with redirected logs under `runs/final-release/`; it remained reachable after its setup PowerShell process exited. This installs no service and provides no automatic restart after reboot. If it stops, use the root README foreground command and keep that terminal open. Judges still need existing authorized p022 desktop access and must open the URL inside p022; external judge credentials/access have not been independently tested.

Only this workflow is in scope. The operator authorized the reviewed `feat/negative-result-review` history and these final wording/documentation corrections for release to `main`. This Git authorization does not authorize native configuration or dispatch. The existing prepared application is launched with the root README command on p022; judges require authorized access to a browser inside that machine. A foreground launch requires keeping its terminal open. No Windows service or network configuration is changed. No Windows Tailscale command is used.
