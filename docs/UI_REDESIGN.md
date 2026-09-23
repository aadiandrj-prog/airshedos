# Frontend visual / UX redesign

## Inspection and plan

Baseline: verified Phase 3C commit `85a3f7f`. This branch preserves backend, generated contracts, provider behavior, scientific rules, review/handoff state machines and all prior verification records. PR #10 is not merged by this work.

Observed problems: large introductions push the map below the fold; equally weighted nested boxes obscure hierarchy; case metadata precedes the actual assessment; large queue cards slow scanning; generic green controls obscure state distinctions; the narrow mobile handoff reads as a long technical record.

Design direction: graphite/ink surfaces, warm off-white type, restrained botanical accent for primary actions, separate provider blue and caution amber. A system sans-serif stack avoids a font download. Shared tokens own color, type, spacing, radii, borders, shadows and motion.

Implementation sequence:
1. Replace the fragmented stylesheet with a coherent token-driven visual system and a compact application shell.
2. Compose one queue / spatial / intelligence workspace; use an explicit collapsible case selector on tablet/mobile and in-panel action navigation.
3. Elevate support and concise evidence ahead of expandable technical facts; show actual provider horizon summaries without implying end-of-horizon readings.
4. Unify labels and empty/loading states with a few small primitives. Refine citizen intake and deliberate handoff/receipt presentation.
5. Inspect desktop, tablet and 390px screenshots, then refine spacing/density and run all behavioral and regression checks.

No new dependency, backend endpoint, analysis, data source, map overlay or product phase is planned. Motion respects reduced-motion preferences. No mock data is inserted into the runtime product.

## Implemented visual system

- **Direction:** graphite surfaces, warm off-white type and a restrained botanical action accent. Provider blue, AI violet, caution amber, verified green and error red separate meanings without relying on color alone. No gradients, decorative data or new imagery.
- **Layout:** a short application masthead and demo journey rail lead into one divided queue / map / intelligence workspace. The map is the spatial anchor. Compact queue rows expose event, prototype location, support, review state and submission time.
- **Tokens:** `apps/web/src/app/tokens.css` owns surfaces, text, semantic colors, borders, radii, shadows, typography, spacing and motion. Spacing uses 4/8/12/16/24/32/48px; surfaces use consistent 6/10/14px radii. A system font stack requires no download.
- **Primitives:** small `Badge`, `EmptyState` and `LoadingState` components; shared styling also covers existing status pills, controls, segmented buttons and disclosure panels. No internal component framework was added.
- **Intelligence:** possible event and review state precede the large deterministic support classification and the existing aggregation explanation. Evidence, report time semantics and provenance remain expandable. Review and handoff actions are reachable by an in-panel shortcut.
- **Fusion:** source verdicts use compact divided rows; support and “Why this result” establish hierarchy. Limitations start open for WEAK/INSUFFICIENT and remain accessible for every support level. No rule, source verdict or confidence meaning changed.
- **Forecast:** current PM2.5 and the actual 6/12/24-hour maxima form a compact numeric comparison. These are explicitly **horizon peaks**, not readings at hours 6/12/24. No interpolation, smoothing or new arithmetic is used. Google attribution, native units and separation from corroboration remain visible. Detailed coverage/comparisons are expandable in the selected-case panel.
- **Handoff/inbox:** From → To leads the handoff; event, support, reason, workflow state and integrity are grouped facts. Technical version/packet/timing fields move behind “View packet details.” The inbox uses the same compact operational row system. All actions retain their original state-machine behavior.
- **States:** contextual loading cues, quiet empty states and readable error/status text use the shared surface system. Maps failure, provider failure, unavailable satellite/forecast, expired cases and integrity mismatch retain their existing recovery paths.
- **Map:** Google's supported DARK initialization color scheme replaces the light map, with compact framing and a text legend. Marker roles, selection, viewport fitting, Google attribution and text alternatives remain intact. The SDK is still loaded once. See [official color-scheme documentation](https://developers.google.com/maps/documentation/javascript/mapcolorscheme).
- **Responsive:** desktop retains three integrated areas; tablet uses map/detail with a collapsible queue; mobile uses an explicit case selector, map, intelligence and action links. Case selection brings the mobile summary into view. Switching selected cases or incoming packets resets the internal detail scroll, while ordinary review updates preserve it. Coordinates link back to the map.
- **Accessibility:** keyboard skip link, visible focus, semantic buttons, pressed/expanded states, text status labels, accessible map alternatives and action anchors. The queue toggle and selection work by keyboard. Reduced-motion preferences suppress nonessential animation.
- **Motion:** 160–220ms hover/disclosure/loading treatments and subtle pressed feedback; no fake percentage progress or heavy animation package.
- **Dependencies:** zero added or removed. Backend, generated API/types/schema, credentials, provider/cache logic, scientific rules, forecast calculations and review/handoff state machines are unchanged. Phase 2D remains `MODEL_NOT_ACCEPTED`; no custom model is deployed.

## Screenshot review and refinements

Reviewed command center, selected case, fusion, citizen intake and handoff/inbox at desktop, tablet and 390px mobile sizes. Iterations corrected oversized introductory chrome, equal-weight metadata, mobile queue density, detail panels retaining an old scroll position, coordinate-field alignment, synthetic-action spacing and a skip-link capture artifact. No horizontal overflow was observed in the final checks.

Final genuine Google Maps / provider screenshots are local, gitignored artifacts:

- `data/verification/ui-redesign-command-desktop.png`
- `data/verification/ui-redesign-case-desktop.png`
- `data/verification/ui-redesign-command-mobile.png`
- `data/verification/ui-redesign-case-mobile.png`
- `data/verification/ui-redesign-case-mobile-viewport.png`
- `data/verification/ui-redesign-desktop.png` — accepted destination inbox
- `data/verification/ui-redesign-mobile.png` — accepted handoff on mobile

Final fixture-based visual checks are under `data/verification/ui-redesign/`: desktop/tablet/mobile command, selected case, fusion and inbox, plus citizen intake and standalone fusion. These browser-test screenshots use **mocked maps/providers** and are not evidence of live availability. The genuine captures above use a clearly synthetic citizen image with real interpretation/providers and simulated handoff; no private citizen material is included.

## Final verification — 23 September 2026

| Check | Result |
| --- | --- |
| Full backend regression | **536 passed**, 2 existing dependency deprecation warnings, 27.95s |
| Full production browser suite | **57 passed**, 1.0m: all 54 prior tests plus 3 viewport/keyboard/hierarchy tests |
| Frontend lint | PASS |
| Frontend typecheck | PASS |
| Frontend production build | PASS |
| Ruff / format | PASS; 92 files already formatted |
| OpenAPI, frontend generated types, PollutionEvent JSON Schema | Regeneration byte-identical |
| Docker rebuild / startup / health | API and web healthy |
| Secret scan, including compiled frontend and sanitized live artifacts | PASS; 1,910 files, zero findings |
| Protected records | All 11 manifest records plus Phase 3C verification unchanged: **12/12** |
| Backend/domain diff | None |

Existing behavioral assertions were preserved. Two request-count tests initially failed against a development server because of development double mounting; both passed unchanged against the production build. A new mobile viewport assertion identified that incoming selection did not bring its heading into view; the UI navigation was corrected and the entire production suite rerun successfully.

The new tests cover keyboard skip/selection/toggling, the actual support label, explicit peak units/semantics, compact disclosure, action navigation, detail scroll reset, handoff integrity labeling and absence of horizontal overflow at 1440×1000, 1024×900 and 390×844. Existing tests continue to cover failure states, maps fallback, immutable workflows, provider separation and no extra provider calls on marker selection.

### Genuine final workflow

The final browser-driven live rehearsal started at **2026-09-23T11:40:43.707Z**. It used the existing synthetic boundary-area workflow at **28.52, 77.08**, genuine Gemini interpretation, Google Maps, current AQ/weather, FIRMS, Sentinel-5P and Google forecast. The location remains honestly **Unknown** in the prototype jurisdiction lookup. Source control room HARYANA and destination DELHI were manually selected; no authority received anything.

Outcome: **PASS**. MODERATE support; AQ, weather, FIRMS, satellite and forecast LIVE; all three satellite products available. Review → frozen packet → simulated send → receive → accept → JSON export → independent receiver validation passed. Packet and source case remained unchanged; audit was append-only; **zero provider reruns** during handoff. Mobile had no horizontal overflow. All cached diagnostic providers returned CACHED.

| Measured browser-driven step | Time |
| --- | --- |
| Page/map readiness including deliberate screenshot paint wait | 4.707s |
| Gemini interpretation / provider call | 3.564s / 3.330s |
| Corroboration including satellite and forecast | 5.830s |
| Satellite provider | 3.370s |
| Forecast provider | 2.322s |
| Handoff operations | 0.511s |
| Export, screenshot work and independent validation | 2.190s |
| Cached corroboration diagnostic | 0.018s |
| Full automated rehearsal | **17.779s**, no retries or manual workarounds |

These measurements verify integration and responsiveness, not forecast accuracy or a human-presented demo duration. Timing fields overlap where provider calls are part of corroboration. The earlier successful rehearsal is retained separately as `ui-redesign-first-rehearsal.json`; the final sanitized result is `ui-redesign-manual.json`.

## Remaining visual limitations and scope

Google controls its base-map labels/POI density; no new cloud map style or map overlay was introduced. System fonts differ slightly by operating system. Full expanded evidence/provenance can still be long, especially on mobile, so action anchors and progressive disclosure remain important. Detailed diagnostics and the preserved fictional reference workflow intentionally remain more technical than the main workspace. No dedicated custom icon library, bespoke map tiles or forecast line chart was added.

This is a frontend-only redesign from verified Phase 3C. PR #10 remains unmerged; the redesign review is stacked on that branch to keep the review diff scoped. No deployment, automatic merge or new product phase is part of this work.
