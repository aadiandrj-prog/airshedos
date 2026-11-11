---
name: Civic Environmental Airshed Operating System
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006398'
  on-secondary: '#ffffff'
  secondary-container: '#5bb8fe'
  on-secondary-container: '#00476e'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002109'
  on-tertiary-container: '#009842'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#cce5ff'
  secondary-fixed-dim: '#93ccff'
  on-secondary-fixed: '#001d31'
  on-secondary-fixed-variant: '#004b73'
  tertiary-fixed: '#7ffc97'
  tertiary-fixed-dim: '#62df7d'
  on-tertiary-fixed: '#002109'
  on-tertiary-fixed-variant: '#005320'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  mono-data-lg:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 22px
  mono-data-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  mono-data-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-sm: 0.75rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

The design system establishes a high-trust, dual-context aesthetic balancing institutional transparency with civic approachability. It serves two distinct audiences: local residents submitting environmental observations under sensory distress, and environmental regulatory officials managing compliance, sensor telemetry, and legal remediation.

The design philosophy combines **Modern Functional Minimalism** with **Systematic Data Rigor**:
- **Atmospheric Clarity**: Layouts prioritize pristine, uncluttered visual space reminiscent of pure air, reducing cognitive fatigue during critical reporting or incident escalation.
- **Institutional Authority**: Precision lines, disciplined metadata tags, and sharp typography project bureaucratic integrity, chain-of-custody validity, and legal certainty.
- **Empathetic Utility**: Public-facing views present intuitive, human-centered form flows, avoiding clinical jargon while maintaining absolute precision behind the scenes.

## Colors

The color palette is built on strict semantic stratification, separating institutional branding, hardware ingestion telemetry, administrative workflow states, and environmental hazard indexes.

### Core Canvas & Structure
- **Base Canvas**: `#FFFFFF` for primary work surfaces, document canvases, and interactive cards.
- **Substrate Layers**: `#F8FAFC` (Canvas Root / Neutral Tint), `#F1F5F9` (Nested Panel Surface), and `#E2E8F0` (Structural Borders).
- **Primary Ink**: `#0F172A` (Civic Slate / Deep Charcoal) for ultra-legible typography and authoritative controls.
- **Brand Accent**: `#0284C7` (Atmospheric Sky) evoking clear horizons and active systemic observation.

### Sensor & Ingestion States
- **Sensor Correlated**: `#0284C7` with `#E0F2FE` soft background. Indicates incident data validated against active monitoring stations.
- **Awaiting Telemetry / AI Processing**: `#D97706` with `#FEF3C7` soft background. Marks reports currently undergoing spatial/plume modeling.

### Regulatory Case Workflow States
- **Intake / Triage**: Slate `#475569` (bg: `#F1F5F9`).
- **Under Investigation / Field Task Scheduled**: Flame Amber `#EA580C` (bg: `#FFEDD5`).
- **Resident Info Requested**: Deliberative Indigo `#6366F1` (bg: `#EEF2FF`).
- **Verified & Follow-up Logged / Resolved**: Emerald `#16A34A` (bg: `#DCFCE7`).
- **Closed (Reason Explained)**: Muted Carbon `#64748B` (bg: `#F8FAFC`).

### Environmental Severity (AQI / Hazard Scale)
- **Good (0-50)**: `#10B981`
- **Moderate (51-100)**: `#F59E0B`
- **Unhealthy for Sensitive Groups (101-150)**: `#F97316`
- **Unhealthy (151-200)**: `#EF4444`
- **Hazardous (300+)**: `#7F1D1D`

Status badges must never rely on color alone; each status requires a dedicated prefix symbol or clear textual identifier.

## Typography

The typographic system utilizes **Inter** for standard interface reading and **JetBrains Mono** for audit logs, geographic coordinates, legal references, and telemetry streams.

### Typographic Rules
- **Tabular Precision**: All numeric values, case identifiers (`AS-2025-0841`), geographic coordinates (`37.7749° N, 122.4194° W`), and sensor readings (`28.4 µg/m³ PM2.5`) must use the `label_font` (`JetBrains Mono`) with numeric tabular figures enabled.
- **Micro-Labels**: Section headers, column headers in data tables, and field descriptors utilize `label-caps` styled with `text-transform: uppercase` and `letter-spacing: 0.06em`.
- **Readability Under Glare**: High contrast ratios (exceeding WCAG AAA for body text) are enforced to allow mobile resident field submissions in direct sunlight.

## Layout & Spacing

The layout model adapts according to user posture:

### Responsive Grid Framework
- **Desktop (Authority Ledger & Enforcement Workbench)**: 12-column fluid grid, `1.5rem` (`24px`) gutters, `2rem` (`32px`) screen margin. Supports high density: multi-column split views (case index, map visualization, dossier audit timeline).
- **Tablet (Field Inspector View)**: 8-column layout, `1rem` gutters, responsive canvas with collapsable lateral panels.
- **Mobile (Resident Intake Portal)**: 4-column fluid layout, `0.75rem` (`12px`) gutters, `1rem` (`16px`) outer canvas margin. Single-column stacked cards optimized for single-hand touch zones.

### Vertical Rhythm
- Component spacing conforms strictly to the `4px` base module. Compact internal paddings (`space-xs` and `space-sm`) are applied to regulatory data sheets and case rows to maximize information density, while spacious layouts (`space-lg` and `space-xl`) frame public storytelling and resident reporting stages.

## Elevation & Depth

Visual hierarchy is maintained through **tonal stacking and low-contrast outlines** rather than excessive dropshadows, ensuring an audit-grade interface free of visual clutter.

- **Level 0 (Base Canvas)**: `#F8FAFC` flat surface.
- **Level 1 (Data Cards, Dossiers & Sidebars)**: Pure `#FFFFFF` background with a crisp `1px` border of `#E2E8F0`. Shadows are restricted to an ultra-subtle ambient blur: `0 1px 3px 0 rgba(15, 23, 42, 0.04)`.
- **Level 2 (Active Modals, Telemetry Flyouts, Command Palette)**: `#FFFFFF` surface with `1px` border `#CBD5E1` and ambient elevation: `0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`.
- **Level 3 (Fixed Overlays & Toast Alerts)**: `#0F172A` high-contrast badge or solid white card with elevated contrast border `#94A3B8`.

## Shapes

The interface employs a disciplined, structured geometric geometry (`roundedness: 1` — Soft, `0.25rem` / `4px` default radius). 

- **Interactive Controls (Inputs, Form Rows, Standard Buttons)**: `0.25rem` (`4px`) radius, creating a functional, mechanical precision.
- **Cards, Audit Panels, and Dossier Modules**: `rounded-lg` (`0.5rem` / `8px`) with exact `1px` structural division borders.
- **Status Badges & Telemetry Pills**: Fully rounded pill shapes (`9999px`) to immediately distinguish classification chips from actionable rectangular buttons.

## Components

### Buttons
- **Primary Institutional**: Solid `#0F172A` background, white text, `4px` radius, hover state `#1E293B`. For state finalization, filing official citations, and submission triggers.
- **Secondary Atmospheric**: `#0284C7` background, white text, hover state `#0369A1`. For public actions and primary resident inputs.
- **Outline / Utility**: `#FFFFFF` background, `1px` solid `#CBD5E1`, text `#334155`. Hover state fills `#F1F5F9`.

### Note Architecture: Dual-Context Segregation
- **Public Resident Notes**: Framed in a soft blue-tinted container (`#F0F9FF` background, `1px` solid `#BAE6FD`). Tagged with a small user avatar icon, display timestamp in `body-sm`, and human-readable text.
- **Internal Authority Ledger Notes**: Framed in a secure slate-amber substrate (`#FEFCE8` or `#F8FAFC` background with a distinct `3px` left border in `#D97706`). Marked with an explicit padlocked icon badge: `INTERNAL ONLY — REGULATORY PRIVILEGE`, using `mono-data-sm` for employee ID, badge number, and tamper-evident cryptographic hash snippet.

### Data Cards & Dossiers
- Surface: `#FFFFFF` surrounded by `1px` solid `#E2E8F0`.
- Card Headers: Divided by a solid `1px` line (`#F1F5F9`), utilizing `label-caps` text for section title alongside real-time status pills.
- Evidence Attachments: Photo and olfactory logs are framed with micro metadata strips displaying ISO timestamp, EXIF geolocation coordinates, and sensor validation status.

### Status Pills & Segmented Tabs
- **Status Pills**: Height `22px`, font `mono-data-sm`, padding `2px 8px`, rounded `9999px`. Composed of a `6px` solid status circle dot preceding the capitalized label.
- **Segmented Filter Tabs**: Enclosed inside `#F1F5F9` troughs with `4px` padding. Active tab sits on `#FFFFFF` with `1px` border `#CBD5E1` and subtle lift, inactive tab renders in `#64748B`.

### Form Fields & Inputs
- Inputs feature a crisp `1px` border `#CBD5E1`, `#FFFFFF` background, and `4px` corner radius. Focus states exhibit a sharp `2px` ring in `#0284C7` with no offset.
- Monospace fields are enforced for Case Numbers, Sensor Serial Numbers, and Chemical Compound PPM entries.