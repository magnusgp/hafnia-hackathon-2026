# Adaptive Watch — Polar brand specification

**Decision:** Polar is the approved visual direction (23 October 2026). The default font combination in the brand studio is Space Grotesk (display), DM Sans (body), and IBM Plex Mono (technical data). If a different font pairing was selected in the operator's local browser, replace only the font entries after confirming it.

## Brand positioning

**Adaptive Watch** is an incident-qualification layer for Milestone XProtect. It combines local CV measurements on the Linux A10G, Hafnia VLM semantics, and provenance-linked native alarm workflows. It is **not** an e-scooter detection product, and not just a frontend for Hafnia. An e-scooter recording is the current fully developed example; other camera capabilities are at different implementation stages.

**Promise:** Actionable video evidence, with spatial and temporal context and an explicit operator decision.

**Voice:** Plain, precise, operational. State evidence and uncertainty. Do not imply intent, accuracy, sustained persistence, live deployment, or alarm acceptance without verification.

## Colors

| Token | HEX | Use |
|---|---|---|
| Background | `#F5F8FC` | Default light application canvas |
| Surface | `#FFFFFF` | Content regions, detail panes |
| Surface subtle | `#EAF1FA` | Secondary area backgrounds |
| Border | `#D3DDE9` | Dividers and low-contrast boundaries |
| Text | `#13263A` | Headlines, body copy |
| Text secondary | `#53667D` | Captions, metadata |
| Primary | `#2858D6` | Active navigation, primary actions |
| On primary | `#FFFFFF` | Text on primary action |
| Confirmed | `#176F62` | Truly verified success |
| Review | `#A65E14` | Pending operator verification |
| Critical | `#B83551` | Critical/warning states after qualification |

Contrast on main canvas, calculated for solid colors: text 14.43:1, secondary text 5.53:1, review 4.66:1, critical 5.38:1, confirmed 5.65:1. White on blue primary 6.07:1. These tests do not cover overlays or every interactive state.

## Fonts

- **Space Grotesk:** editorial headlines and page titles, 600 weight.
- **DM Sans:** body copy, controls, navigation, 400/500/600 weight.
- **IBM Plex Mono:** camera times, exact identifiers, CV model details, small technical labels. Do not make entire paragraphs monospaced.

Use the sizes and scales in `design-tokens.json`. Never reduce operational information to 10px labels by default. Check rendering at both 1440×900 and 1920×1080.

## Interface grammar

1. **Monitoring workspace:** Start at a camera/capability/incident overview. Mark actual configured capabilities separately from planned ones; do not invent live counts or camera processing state.
2. **Incident review:** Give the recorded video priority. Show the selected evidence object only by default. Show CV temporal/spatial measurements and the Hafnia interpretation separately. Keep uncertainties close to the associated claims. Move hashes and raw responses into expandable provenance.
3. **Camera setup:** A distinct setup surface for region-of-interest review, capability selection, and explicit approval. Never silently approve draft polygons.
4. **Native XProtect action:** Distinguish planned event, approved dispatch, Event Server acceptance, and Smart Client-verified alarm.
5. **Presentation:** Use the same Polar palette and Space Grotesk typography, but more cinematic composition, much less UI, and the genuine XProtect recording/ML evidence. A dark video stage is a neutral media surface, not a different overall brand theme.

## Composition and motion

- Larger camera/video surface, less boxed text. Use 1px dividers and a simple grid.
- Strong typography with measured whitespace, minimal decorative graphics.
- Show spatial overlays in video coordinates, verified against original frame alignment.
- Use blue to guide actions, not to denote successful detection; use semantic colors only for their assigned status.
- Transitions should aid navigation. Respect reduced-motion preferences. Do not obscure evidence behind visual effects.
- Prefer actual XProtect playback over repetitive synthetic looping in presentation. Clearly label any demo replay.

## Implementation boundary

React + TypeScript + Vite + Tailwind 4 + selected shadcn/ui components is appropriate. Python remains responsible for XProtect/Hafnia authentication, ML orchestration, evidence joins and guarded native-event dispatch. No browser-side secrets.

First implement shared tokens, typography and a **visual prototype of the monitoring workspace plus the incident view**. Review screenshots before full feature development. Keep real media, gateway replies and private evidence outside the public repository.

No standalone logo was approved. Use a clean typeset **Adaptive Watch** wordmark until a distinctive mark is reviewed. Do not assume the provisional Brand Studio SVG is the final trademark/logo.
