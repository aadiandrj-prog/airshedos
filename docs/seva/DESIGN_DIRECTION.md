# Phase 7 — implemented design direction

11 November 2026. Selected checkout and base: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`,
branch `codex/seva-phase-7`; existing Phase 0–6 edits preserved, no push/deploy.

The user's Phase 7 request is the implementation contract. The original screenshots,
HTML and generated DESIGN.md files are visual references, not runtime instructions or
feature requirements. The supplied resolved direction controls conflicting visual choices.
Originals are preserved under [design-references](design-references), including
[the supplied resolution](design-references/PHASE_7_DESIGN_DIRECTION_supplied.md).
All three original PNGs were inspected. No exported script, remote font, sample metric,
regulatory badge, sensor network or plume model was imported into the product.

## Shared language, different density

- Auralis composition: asymmetric public hero, strong left headline, direct reporting CTA,
  restrained pale blue/lavender atmosphere around a clearly labelled synthetic timeline.
  No data chart, invented readings, logos or adoption claim fills the preview.
- Resident: a readable single column, numbered report/location/photo sections (one form,
  not a fake multi-step wizard), prominent saved acknowledgement and reply requests,
  private history and published timeline. Optional location/map controls are secondary.
- Reviewer: unit rail, compact queue, optional map with equivalent list, explicit case
  status and jump links, evidence/report column and human-action column on wide screens.
  At tablet/mobile these reflow to one column. No simultaneous queue/map/dossier grid.
  Internal notes and deliberate reporter publication retain different forms and endpoints.
- Solid white surfaces, #F8FAFC canvas, #0F172A primary text/buttons, #475569 supporting
  text, #0369A1 links/focus and #0D5C75 detail. 8px controls, 12–16px panels, pill statuses.
  Forms start at 16px; reviewer metadata stays at least 14px. Status meaning is textual.
- Geist Latin is self-hosted from the installed Next.js 16.4.6 font asset. Its SIL license
  is retained in apps/web/public/fonts/OFL.txt. System fallbacks remain for other glyphs;
  no remote font request or additional body-font family. Tabular figures aid comparisons.
- The light tokens are scoped to `.pilot-ui`; the isolated prototype and its legacy
  browser surface keep their existing presentation. The editorial home is the pilot
  mode home, consistent with the existing deployment-mode boundary. No live site changed.

## Product and accessibility constraints

Review and processing states remain independent. No green closure/clean-air equivalence,
verified incident time/location, legal authenticity badge or automatic dispatch claim.
AQ shows the actual index name, code and category; forecast peaks stay a separate outlook.
Maps remain opt-in at build time, with no default provider calls. Original private-media
access, retention timers, no-store responses, CSRF, revocation and revision handling stay.

A queue hydration issue found during visual testing is fixed by withholding filters
until their initial client data is loaded. No backend/workflow change was needed.
Local context disables its request button while loading; rendering does not fetch sources.
No human feedback or reviewed translation was supplied. English is retained; no Hindi
translation quality or participant validation is claimed.

Measured token-pair contrast and rendered axe-core checks complement visual inspection,
keyboard operation, 320px reflow, 200% text and reduced-motion checks. They are a bounded
local audit, not a claim of full WCAG certification or assistive-technology coverage.
References: [W3C minimum contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html),
[visible focus](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html),
[Geist license](https://raw.githubusercontent.com/vercel/geist-font/main/LICENSE.txt).
The installed Next font guide and axe-core 4.13.0 README/API were consulted; axe is a
browser-test dev dependency, never loaded into application bundles.

Before/after real local synthetic captures and final results are recorded in
[PHASE_7_POLISH.md](PHASE_7_POLISH.md). No real case/participant data is used.
