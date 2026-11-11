# AirshedOS Phase 7 design direction

Prepared 10 November 2026 from the user's screenshot, two Stitch exports and supplied DESIGN.md. This is the recommended interpretation of those references for the agreed product. It refines the Phase 7 plan; it does not implement the frontend or establish that preceding development phases are complete.

## Recommended combination

Use the **Auralis reference for visual composition**, the **AirshedOS remix for its two-audience structure**, and the **standalone civic DESIGN.md for practical casework organisation**. Resolve these into one design system rather than importing three conflicting systems.

The result should be a light, editorial public website with a simple resident application and a precise authority workspace. Shared typography, surfaces, controls and status language connect the experiences. Information density changes according to the task.

These references express a design preference. Their copy, sample metrics, instructions, compliance language and implied features are not new product requirements or evidence of implementation.

## What each reference contributes

| Source | Keep | Adapt or omit |
| --- | --- | --- |
| User Auralis screenshot and Stitch 01 | Strong headline, asymmetric hero, generous whitespace, restrained black actions, soft gradient atmosphere and clear sectional rhythm | Audio products, voice widgets, pricing/sales navigation, placeholder copy, trust logos and invented metrics |
| Stitch 02 AirshedOS remix | Distinct resident/reviewer entry points, environmental visual accents, softened panels and a shared platform story | Sensor hardware, station counts, cross-verified readings, confidence percentages, Gaussian plume simulation, dispatch promises and US regulatory claims |
| Standalone DESIGN.md | Readable light surfaces, structured case layouts, clear forms and explicit separation of internal notes from reporter updates | Assertions of legal certainty or regulatory privilege; EXIF-based verified location; hardcoded generic AQI; untested AAA claims; inconsistent tokens |

Both ZIP files mainly provide **landing-page compositions**. They do not define a complete reporting form, resident history, case queue or reviewer workbench. Phase 7 must design those screens from the actual functioning workflows and Phase 6 findings.

## One visual system

### Colours

| Role | Recommended starting token | Use |
| --- | --- | --- |
| Page background | `#F8FAFC` | Application canvas |
| Reading surface | `#FFFFFF` | Forms, case content and tables |
| Soft neutral | `#F1F5F9` | Secondary surfaces and quiet selection backgrounds |
| Main text and primary action | `#0F172A` | Headings, body emphasis and primary buttons |
| Secondary text | `#475569` | Supporting descriptions |
| Metadata | `#64748B` | Readable nonessential metadata on white; verify other surfaces |
| Structural divider | `#E2E8F0` | Subtle panel separation; not automatically sufficient as an input boundary |
| Interactive blue | `#0369A1` | Links, focus treatment and optional secondary emphasis |
| Teal detail | `#0D5C75` | Selected environmental/source accents |
| Decorative glow | Pale blue and lavender | Limited to introductory/landing compositions |

Prefer the neutral canvas over a lavender tint throughout the working application. Use dark primary actions consistently on both sides; distinguish importance with placement and wording rather than arbitrarily giving residents and reviewers unrelated brands. Teal/blue remains a restrained accent.

The standalone reference's white text on `#0284C7` computes to approximately **4.095:1** contrast, below the 4.5:1 AA requirement for ordinary-size text. White on `#0369A1` computes to approximately **5.934:1**, a safer starting combination. These are calculated token-pair checks, not a full rendered accessibility audit. Composite/translucent surfaces and actual components still require testing. The statement that the supplied system already exceeds AAA is not established.

### Typography and shape

- Use **Geist** as the primary family to match the Auralis/Stitch direction. Use the existing installed font setup if compatible; do not add both Inter and Geist as competing body families.
- Enable tabular numerals for comparable readings and table counts. Reserve monospace for IDs, coordinates and genuinely technical details, rather than every number or label.
- Public landing headlines can be approximately 48–64px on desktop and 32–40px on mobile. Application page titles should be much smaller, approximately 24–32px. Refine through actual fitting and responsive inspection.
- Resident body/form text should generally start at 16px. Authority tables may use 14px where comfortably readable. Do not transplant 10–11px uppercase microcopy into essential labels, status text or instructions.
- Start with 8px control radii, 12–16px panels and fully rounded status chips. Pill-shaped landing actions can echo the reference; the workbench needs compact, recognisable controls.
- Use a 4px spacing scale. Keep generous public storytelling space and more compact internal case rows. Avoid large landing-page gaps inside a form or review queue.

Use solid reading surfaces. A subtle translucent header or decorative atmospheric background may work on the landing page, but dense tables, form fields, evidence text and decision controls should not sit on blurry glass. Avoid continuous drifting animations and excessive backdrop blur, particularly on mobile. Respect reduced motion.

## Public website

Keep the reference's composition: a compact header, strong left-aligned headline, concise explanation and an immediately visible reporting action.

Suggested hero content:

**A clearer way to report local pollution**

Submit a concern, understand the available evidence and follow the review in one place.

Primary action: **Report a concern**. Secondary action: **My reports** or **Resident sign in**, depending on session state. Keep **Authority sign in** available in the header. Preserve the intended reporting destination through authentication.

Replace the enormous imaginary sensor chart with a useful product preview: a clearly labelled synthetic report timeline or a real, permission-safe capture of the finished resident/reviewer journey. A decorative gradient may frame the preview but must not look like a measured pollution plume or heatmap. If showing real AQ, display the named index, location applicability, source and observation time. No data means an honest unavailable state.

Follow with a short reporting/review explanation, a restrained two-pathway resident/reviewer section, evidence-and-limitations information and a final reporting action. The first useful action should remain reachable without scrolling through a long marketing page.

No invented trust strip, station network, public case feed, customer list, pricing page or unsupported environmental-impact headline is needed. Links must reach functioning pages or meaningful on-page sections; avoid placeholder `href="#"` controls.

## Resident application

Use the same light visual language with simpler, task-focused layouts. Navigation should make **Report a concern** and **My reports** easy to find.

- **Report form:** a readable single column, optional photograph, manual location alternative, optional location permission, declared observation time and clear validation. A visible progress indicator is useful only if the actual flow has multiple steps.
- **Confirmation:** a reference and accurate saved/submitted status, followed by the next step and link to the report. Analysis pending must not imply the submission failed.
- **My reports:** a list of the signed-in person's reports, with a concise summary, date, textual review status and last published update. Do not turn it into an analytics dashboard.
- **Report detail:** original submission, a human-readable progress timeline and a prominent request/reply area where needed. Internal reviewer notes never appear here.

Use 44–48px practical mobile targets where possible, large input text, visible focus and clear error recovery. A map or unavailable provider must not block text reporting. Reporter-facing copy should avoid telemetry, plume modelling, regulatory privilege and legal-verification terminology.

## Authority workspace

Apply the same brand with denser composition: a compact navigation rail, useful queue and a selected case workspace. A desktop list/detail split is appropriate where actual content fits. Do not insist on simultaneous sidebar, queue, map and dossier columns on every viewport.

- **Queue:** scope and status filters, assignment, pagination and meaningful counts derived from permitted records. A map is optional and has a full list alternative.
- **Case heading:** case reference, human review status, assignment and next action. Analysis state has a separate label.
- **Evidence:** reporter claim, photograph, AI interpretation, environmental context and source limitations form distinct sections. Put relevant timestamps next to the information they qualify.
- **Follow-up:** reviewer reasons, verification requests/findings and published updates are organised around the current task.
- **Notes:** two explicitly named actions, **Add internal note** and **Publish update to reporter**. Use text and icons in addition to visual treatment; colour alone is insufficient. Say “Internal note — visible to your review unit”, not “Regulatory privilege”.
- **History/export:** preserve evidence versions and decision context. Show integrity metadata only where it helps; a hash snippet should not act as a legal-authenticity badge.

On tablet/mobile, use list-to-detail navigation with collapsible supporting sections. Do not shrink the full desktop workbench into unreadable columns or hide essential information in hover-only controls.

## Semantic rules for visual states

Processing, review and environmental condition are different kinds of information. Give them separate labels and avoid a single colour system that silently merges their meanings.

| Meaning | Suitable presentation |
| --- | --- |
| Analysis pending/running | Quiet progress state with text; not an authority acknowledgement |
| Partial data or failed analysis | Explicit limitation plus any available retry/action; report remains saved |
| Received or under review | Human workflow label mapped to actual backend state |
| More information requested | A visible resident task and response action |
| Verification requested | A recorded task, not proof of field verification |
| Follow-up/closure recorded | Reason and action history; green must not automatically mean clean air or a proven resolution |
| AQI category | Named provider/index-specific category; separate from case and analysis status |

The supplied generic AQI palette is not a universal conversion table. The existing adapter preserves index code/name/value/category and may return both universal and local indices. Keep a named index consistent within a panel, preserve its category meaning and do not apply one index's thresholds to another. Do not invent a missing category or interpolate a pollution history to produce an attractive chart.

Use local context around DTU/Shahbad Daulatpur for genuine pilot material. Avoid the exports' US station names, PST timestamps, EPA references and example industrial-source findings. Do not invent a current Delhi reading to replace them. Label IST/local time and UTC where appropriate, using actual timestamps.

## Copy and feature corrections before reuse

Replace these export concepts with the real product's task:

| Export wording or visual | Product-appropriate treatment |
| --- | --- |
| Municipal sensor mesh, 142 stations, roof-mounted edge nodes | Available third-party environmental context; no owned sensor network implied |
| 82% correlation, 96.4% confidence, 99.98% uplink | Actual recorded processing/source state; no invented performance percentage |
| Gaussian plume mapping and forward projection | Existing attributed provider forecast, if useful, shown separately |
| Sensor triangulation or EPA Method 9 verification | Human review and a recorded field-check request/finding where genuinely available |
| Immutable evidence cannot be altered or silenced | Versioned records with documented integrity and retention limits |
| Regulatory compliant, legal certainty, regulatory privilege | Accurate access/visibility labels and recorded review reasons |
| EXIF verified coordinates | Reporter-declared place/time; metadata-stripped retained image |
| Automatic field dispatch and sub-hour response | Assigned pilot follow-up and published status, without a response-time promise |
| Open raw telemetry feed or CC BY licensing | Only explicitly permitted public content/licensing; no blanket licence for private reports/provider data |

## Implementation use

Read this file before the Phase 7 prompt. Supply `design-references/` with it. The updated prompt incorporates the key decisions, but the original images remain the visual reference. Preserve source files as references and build real components in the current project. Do not paste standalone Tailwind CDN scripts, remote-font imports, mock chart paths or generated HTML wholesale into the application.

Where the raw references disagree, use this resolved direction and the implemented product contract. If actual Phase 6 findings justify a change, record the reason. Do not use the design exercise to claim earlier phases have happened or to start an unrelated backend rebuild.

Before implementation, capture the real current views. Verify both complete journeys and the unavailable/partial/conflict states after changes. Inspect narrow and desktop layouts, keyboard/focus, contrast, readable status labels, the separation of internal/public notes and a map failure. Compare actual before/after captures rather than evaluating a static landing screenshot alone.

## Reference provenance

- `design-references/auralis-user-reference.png` — user's attached Auralis screenshot, if available at import.
- `design-references/stitch-01/` — first supplied ZIP, original `code.html` and `screen.png`.
- `design-references/stitch-02/` — second supplied ZIP, original `code.html`, `screen.png` and embedded `DESIGN.md`.
- `design-references/DESIGN_supplied.md` — standalone DESIGN.md supplied by the user, preserved without rewriting.

External accessibility reference: [W3C contrast minimum guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). The final interface needs measured checks; no compliance certification is claimed.
