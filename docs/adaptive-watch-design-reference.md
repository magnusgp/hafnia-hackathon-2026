# Adaptive Watch — design-system transfer brief

**Source inspected:** user-provided `claude-impact-lab-source.zip` (188 entries, CAI/CD, 21 October 2026). **Target:** `magnusgp/hafnia-hackathon-2026`, branch `feat/adaptive-watch` at `78f97cb`. **Purpose:** a source-grounded visual and architectural handoff, *not* a copy of CAI/CD's branded assets or a completed frontend.

## Findings from CAI/CD

- **Pitch deck** is one file, `presentation/index.html` (~14 KB), plain HTML/CSS/JS with **no framework, Bun runtime, CSS library, or dependencies**. Seven slides, arrow/space navigation, fragment-based slide selection, fullscreen shortcut, slim progress bar, 450 ms transitions, 150/450/750/1050 ms staggered reveals, and a cycling typewriter on slide 2. `presentation/README.md` contains a 90-second slide / 90-second demo talk track.
- **Dashboard** uses React 19, TypeScript, Tailwind CSS 4, TanStack Start/Router, Vite 8, Bun lockfile, shadcn-style primitives (`components.json` New York style; Lucide icons). `src/components/ui/` has 61 component files, but direct dashboard/root imports use just Button, Spinner, Sonner, Tooltip. **Do not port all 61.**
- **Distinctive application components:** `src/components/primitives/TileGrid.tsx` (2 px well gutters, subtle raised-edge shadow), `src/components/dashboard/GrowthRow.tsx` (two-column transformation narrative), `src/components/dashboard/CourseReader.tsx` (focused two-pane flow with monospace provenance). `src/routes/index.tsx` uses one large composition, not a wall of generic cards.
- **Typography:** Manrope for UI and deck (the app loads it via Google Fonts), JetBrains Mono for technical details in the application. Deck fallback uses system sans and monospace.
- **App design:** warm charcoal/dark neutrals (OKLCH hue ~50), rust `#db5a42`, muted green `#6fbf8e`, hairline borders, sharp corners (`--radius: 0rem`), subtle gradients/highlighted tile edges. Deck specific tokens: background `#1c1a19`, alt `#252321`, foreground `#f4f1ee`, muted `#9b948e`, rust `#db5a42`, green `#6fbf8e`, line `#3a3634`.
- **Deck composition:** ~7vw oversized headline, ~4.8vw section headline, 6vh/8vw slide inset, abundant negative space, mono uppercase kicker, one highlighted phrase, staggered reveal, comparison matrix, diagram as CSS and SVG, not an imported component library.
- **Important limitations to fix:** deck uses viewport-width font sizes and an infinite typewriter loop (no reduced-motion handling in source), and navigation uses document-level click-to-advance. Fix responsiveness, keyboard focus, reduced motion and click interception in our version. The deck source is not a UI-component package.

## Decisions for Adaptive Watch

**Use:** React + TypeScript + Vite SPA, Tailwind 4, a **small** curated shadcn/ui subset (Button, Dialog, Tooltip, Sheet, Slider, Separator), Lucide, Bun for local dev/build where available. No TanStack Start SSR, Nitro, TanStack DB/Query, or full shadcn catalog unless a tested requirement emerges. Build static files and serve locally alongside the existing Python viewer/evidence path. Preserve existing Python/XProtect/Hafnia integration, authorization gates and private evidence outputs unchanged.

**Presentation:** separate `presentation/index.html` (or closely related static files), adapted from the proven pure HTML/CSS storytelling *approach*; reuse the design tokens and typography, **not** the CAI/CD brand or copy. Do not spend time integrating the deck into the React router. The deck should launch the actual running app/demo when necessary.

**Deployment:** the browser must not receive Hafnia administrator credentials, SSH keys, or Event Server dispatch authority. Feed the frontend an explicitly versioned, read-only incident view model derived from `joined.json` and camera-specific spatial review. Limit any eventual write action to the separately approved local Python operation; read-only MVP is acceptable while alarm configuration/approval is pending. Keep private footage, XML, hashes and screenshots out of public Git. Don't execute `tailscale.exe` on `p022`.

## Design language

- **Identity:** “Adaptive Watch” (not CAI/CD); strongest proposition: *“Motion tells you something moved. Adaptive Watch shows what was left behind.”* Keep language precise: only visually measured stationary time, not proven danger or blocked accessible clearance.
- **Palette:** warm near-black `#1c1a19`, panel `#252321`, text `#f4f1ee`, muted `#9b948e`, accent rust `#db5a42`. Use green *only* for corroborated evidence/verification, amber for review-required; not saturated teal everywhere.
- **Typography:** Manrope 700/800 for editorial incident heading, Manrope 400/500 for body, mono for abbreviated timestamps, event IDs and diagnostic provenance. Bundle WOFF2 or use system fallbacks for offline demo (do not share third-party font binaries externally).
- **Surfaces:** sharp to slightly softened edges, 1px dividers/2px ‘well’ gutters, subtle inset highlights, minimal raised panels. No generic rainbow dashboards, pill spam, gradient hero backgrounds or oversized icon cards.
- **Motion:** one intentional ~250–450 ms screen/element reveal; restrained scene-state transitions; reduced-motion fallback. Time/selection controls are interactive and never decorative.

## Primary operator screen (desktop 16:9)

1. **Small chrome row:** Adaptive Watch / incident class / source camera, and actual persisted `Needs review` status. No raw GUID or timestamp in the hero.
2. **Large video/stage (65–75% width):** primary source is the original recording *only if* a browser-compatible, timestamp-aligned derivative has been verified. Otherwise explicitly label “Timestamped samples” with 1 Hz cadence and provenance. Thin rust object box for **the confirmed stationary hypothesis only**. Muted pedestrian polygon is individually toggleable. Detector diagnostic boxes OFF by default. A clear frame cursor and event markers below.
3. **Slim evidence rail (25–35%):** one sentence from Hafnia and one concrete statement from CV (“5.0 seconds across six sampled observations, 4.0 after the person departs” where supported). One operator action: **Review pedestrian zone**. Alarm action locked until required approvals. No XML SHA in primary view.
4. **Below stage:** compact chronological event rail: approach → object laid down → actor walks away → last observed stationary. Use sourced timestamps only; manually observed vs model-measured events labeled accordingly. Synthetic loop reset is not removal.
5. **Expandable ‘Technical evidence’ drawer:** Hafnia summary IDs and exact prompts/responses, preserved parser repairs, frame hashes, UTC bounds, bounding-box limitations, XML digest, dispatch ledger state. This is required but should not dominate the initial view.

**Evidence semantics:** object box intersection is not physical clearance. The scooter straddles a pedestrian/cycle-lane boundary; camera-specific zone polygons require manual approval. Current stationarity thresholds are same-clip calibration. If associated object identity is ambiguous, don't emit a native `ObjectList` box. If the gateway response needed JSON repair, block automatic dispatch. Never silently upgrade `HTTP 200` to verified native alarm.

## Presentation concept (seven slides, ~90 seconds plus live demo)

1. **Opening:** “Motion stops. The problem stays.” Hero frame of the *actual* scooter scene; no speculative statistics.
2. **Problem:** Simple “motion alert” versus “what was left behind” comparison, using real timestamped frames.
3. **Insight:** Big left-to-right transformation: “Local vision measures **where & how long**” → “Hafnia explains **what happened**.” Use CAI/CD matrix storytelling technique.
4. **How:** XProtect recording → Linux A10G local CV → Hafnia → operator decision → native XProtect alarm. CSS/SVG diagram with staggered reveals.
5. **LIVE DEMO:** Enter the real operator review; show original scene, the stationary hypothesis, Hafnia evidence and bounded sampled duration.
6. **Native workflow:** only after verified, show actual dedicated XProtect alarm/overlay result and explain operator review/approval. If not verified yet, disclose it rather than stage a fake screenshot.
7. **Closing:** “Less motion noise. More evidence.” Include accurate prototype limitations in a small footer or narration.

Deck should support arrow/space navigation, fullscreen, slide count, hash deep-link, smooth but optional reveals, presenter shortcut to local app. Do not depend on network assets or slide animation before recording the demo. Record at 1920x1080 and verify slide visibility at projected resolution.

## Delivery gates: optimize against ‘mid UI’

- **Gate 0 (first Codex iteration, mandatory STOP):** create `frontend/` skeleton + one *static but real-evidence-grounded* operator screen (scooter) and 2–3 working pitch slides. Run production build and take actual 1440x900 and 1920x1080 Chromium screenshots. STOP and present screenshots/paths for human design review. Do **not** implement a full viewer, additional routes, backend, or dispatch control before approval.
- **Gate 1 (after approval):** implement sourced timeline scrubbing, play/pause, selected stationary track overlay, independent polygon/overlay toggle, accessibility and failure states. Validate all overlays against frame dimensions and timestamped samples.
- **Gate 2:** connect read-only private evidence export and operational status to actual backend. Preserve `scene_contracts/analytics_event.py` and existing dispatch CLI gates untouched. Test sandbox/offline behavior and 91+ existing Python tests.
- **Gate 3:** finish seven-slide presentation, integrate demo switch, record actual footage, verify one dedicated alarm only after **separate explicit** VMS configuration and event-send approvals.

## Target code organization

```text
frontend/
  package.json, bun.lock, index.html, vite.config.ts
  src/
    styles.css            # design tokens and typographic hierarchy
    components/ui/        # only installed shadcn primitives used
    components/IncidentStage.tsx
    components/EvidenceRail.tsx
    components/IncidentTimeline.tsx
    components/EvidenceDetails.tsx
    lib/evidence-schema.ts # runtime shape check, not fake demo responses
    app.tsx
presentation/
  index.html              # standalone static deck + small scoped assets
adaptive_watch/            # existing Python, unchanged
scene_contracts/            # existing Event Server and ledger, unchanged
```

**Source rights:** uploaded repo has no top-level LICENSE file. For safety, transfer its public design concepts, not CAI/CD branding or large chunks of code without contributor permission. The owner/user may have rights as a collaborator; confirm before wholesale copying.
