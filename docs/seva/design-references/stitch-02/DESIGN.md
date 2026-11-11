---
name: Airshed Atmospheric Precision
colors:
  surface: '#fbf8ff'
  surface-dim: '#dad9e3'
  surface-bright: '#fbf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f2fd'
  surface-container: '#eeedf7'
  surface-container-high: '#e8e7f1'
  surface-container-highest: '#e3e1ec'
  on-surface: '#1a1b22'
  on-surface-variant: '#40484c'
  inverse-surface: '#2f3038'
  inverse-on-surface: '#f1effa'
  outline: '#70787d'
  outline-variant: '#bfc8cd'
  surface-tint: '#1e667f'
  primary: '#004357'
  on-primary: '#ffffff'
  primary-container: '#0d5c75'
  on-primary-container: '#93d3ef'
  inverse-primary: '#90cfec'
  secondary: '#0058be'
  on-secondary: '#ffffff'
  secondary-container: '#2170e4'
  on-secondary-container: '#fefcff'
  tertiary: '#4f00af'
  on-tertiary: '#ffffff'
  tertiary-container: '#691dda'
  on-tertiary-container: '#d5bfff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#bde9ff'
  primary-fixed-dim: '#90cfec'
  on-primary-fixed: '#001f2a'
  on-primary-fixed-variant: '#004d64'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#eaddff'
  tertiary-fixed-dim: '#d2bbff'
  on-tertiary-fixed: '#25005a'
  on-tertiary-fixed-variant: '#5a00c6'
  background: '#fbf8ff'
  on-background: '#1a1b22'
  surface-variant: '#e3e1ec'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 56px
    fontWeight: '400'
    lineHeight: 64px
    letterSpacing: -0.03em
  display-lg-mobile:
    fontFamily: Geist
    fontSize: 36px
    fontWeight: '400'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '500'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 26px
    fontWeight: '500'
    lineHeight: 34px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '500'
    lineHeight: 30px
    letterSpacing: -0.01em
  title-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.005em
  title-sm:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '500'
    lineHeight: 22px
    letterSpacing: 0em
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-xs:
    fontFamily: Geist
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 0.75rem
  margin: 3rem
  margin-mobile: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.75rem
  space-xl: 3rem
---

## Brand & Style
This design system pairs the rigorous instrumentation of environmental atmospheric monitoring with the weightless, high-craft aesthetics of modern ambient minimalism. Built for dual audiences—grounded civic observers reporting hyper-local anomalies and authority operators orchestrating municipal containment protocols—the interface replaces intimidating industrial dashboards with luminous clarity, generous spatial discipline, and serene glassmorphic surfaces.

The visual style blends **Minimalism** and **Ambient Glassmorphism**. Key tenets include:
- **Atmospheric Luminosity:** Broad, pristine ivory and optic white canvases punctuated by subtle, drifting multi-spectral atmospheric gradients (diffuse azure, faint ozone cyan, and transient dusk violet).
- **Weightless Hierarchy:** Removal of dense framing, dark borders, and aggressive telemetry boxes in favor of structural left-aligned anchor rails, ultra-fine semi-translucent perimeters, and backdrop blurs.
- **Instrumental Precision:** Restrained, razor-sharp geometric typography with deliberate negative space, delivering dense ecological telemetry with effortless legibility.

## Colors
The palette evokes clean air, optical clarity, and atmospheric strata. The default canvas balances optic pure `#FFFFFF`, soft alabaster `#FAFAF9`, and mineral stone `#F7F7F5`.

### Color Roles & Guidelines
- **Primary (`#0D5C75` - Deep Ozone Teal):** Anchor color for critical authoritative metrics, structural indicators, primary interactive triggers, and high-confidence telemetry. Ensures contrast against translucent surfaces.
- **Secondary (`#3B82F6` - Atmospheric Azure):** Accent for live civic telemetry streams, dynamic spatial maps, active flow states, and link treatments.
- **Tertiary (`#7C3AED` - Dusk Ion Violet):** Reserved for low-frequency anomalies, sensory thresholds, alert highlights, and atmospheric particulate density transitions.
- **Neutral (`#71717A` - Slate Mist):** Controls inactive indicators, supplementary metadata, secondary navigation items, and fine structural delimiters.

### Ambient Atmospheric Glows
Background layers feature expansive, non-repeating radial color pools (`filter: blur(120px)`) composed of `#E0F2FE` (faint sky), `#EDE9FE` (subtle dusk), and `#CCFBF1` (faint ozone) set at 20% to 35% opacity against `#FAFAF9`, giving glassmorphic panels depth without tinting text.

## Typography
Typography relies on the hyper-clean, technical geometry of **Geist**. Its neutral aperture and tabular numeric support make it ideal for delicate atmospheric counts, sensor readings, and unencumbered narrative text.

### Implementation Directives
- **Tabular Figures:** Numbers in live monitoring cards, PM2.5 readings, and telemetry dials must strictly use tabular lining figures (`font-variant-numeric: tabular-nums`).
- **Letter Spacing:** Maintain tight tracking on display headlines to balance high-contrast weightlessness. Small metadata markers and pill badges require expanded tracking (`0.06em`) with full uppercase rendering.
- **Visual Weight:** Avoid heavy font weights. Limit bold weights to small titles or micro-indicators to sustain an airy visual rhythm.

## Layout & Spacing
The layout adheres to a flexible 12-column grid anchored by an expansive left-aligned navigation rail, intentionally freeing 85% of screen width for broad telemetry canvases and uncluttered workstations.

### Breakpoint Architecture & Reflow Rules
- **Desktop (1280px+):** Fixed 72px collapsed or 240px expanded left rail. Main stage follows a 12-column fluid grid with 48px outer margins and 24px gutters. Dual-path actions (Community vs. Authority) occupy split lateral panels.
- **Tablet (768px - 1279px):** Rail compresses into an iconic floating dock. Content shifts to an 8-column grid with 32px outer margins and 20px gutters. Dual-path actions stack vertically into balanced glass tab structures.
- **Mobile (< 768px):** Rail transforms into a bottom glass action strip. Grid collapses to a 4-column stack with 20px outer margins and 12px gutters. Telemetry shifts from panoramic charts to compact swipeable glass cards.

### Spacing Philosophy
Rely on macro-spacing (`space-xl`) between major sections to let content breathe. Avoid enclosing every card in dense margins; let clear background intervals create implicit structural divisions.

## Elevation & Depth
Elevation abandons traditional drop shadows in favor of luminous backdrops, low-contrast ghost perimeters, and refractive blurs.

### Surface Tiers & Translucency
1. **Base Layer (Level 0):** Pure `#FFFFFF` and `#FAFAF9` with ambient, non-static gradient blooms drifting below the functional canvas.
2. **Frosted Glass Cards (Level 1):** `rgba(255, 255, 255, 0.72)` paired with `backdrop-filter: blur(24px)` and `border: 1px solid rgba(255, 255, 255, 0.8)`. Outer drop shadow is limited to a feather-light atmospheric veil: `0 8px 32px -4px rgba(13, 92, 117, 0.04)`.
3. **Interactive Overlays & Flyouts (Level 2):** `rgba(255, 255, 255, 0.88)` with `backdrop-filter: blur(32px)`, bordered by `1px solid rgba(0, 0, 0, 0.04)` and elevated via an ambient shadow of `0 16px 48px -8px rgba(13, 92, 117, 0.08)`.
4. **Modal Workstations (Level 3):** `rgba(255, 255, 255, 0.95)` with dual rim highlights: an inner ring of `inset 0 1px 0 rgba(255, 255, 255, 1)` and an outer perimeter of `rgba(0, 0, 0, 0.06)`.

## Shapes
Shapes express aerodynamic fluidity combined with modern product industrial design. Smooth, continuous corners soften data-heavy metrics without feeling cartoonish.

- **Cards & Data Modules:** Standardized at `rounded-lg` (16px) to maintain a soft frame for atmospheric charts and telemetry gauges.
- **Badges, Tags, & Status Pills:** Configured with full pill rounding (`9999px`) to create high tactile contrast against rectangular content tiles.
- **Workstation Inputs & Sliders:** Use `rounded` (8px) for precise, grounded interaction zones.
- **Inner Corner Consistency:** When nesting elements (e.g., a chart preview inside a glass card), maintain proportional nesting radius (`R_inner = R_outer - padding`) to preserve optical coherence.

## Components

### Buttons & Interactive Triggers
- **Primary Authority Action:** Solid Deep Ozone Teal (`#0D5C75`) with optic white label text, `rounded-md` (8px), no border, subtle inset top highlight (`inset 0 1px 0 rgba(255, 255, 255, 0.2)`).
- **Secondary Community Action:** Frosted glass capsule, `rgba(255, 255, 255, 0.7)`, bordered with `rgba(0, 0, 0, 0.06)`, text in `#0D5C75`. On hover, scale background opacity to `0.9` with an ultra-soft azure glow (`box-shadow: 0 0 16px rgba(59, 130, 246, 0.15)`).
- **Ghost/Tertiary:** Zero background, padding bounded, slate text `#71717A` turning to `#0D5C75` on hover.

### Frosted Telemetry Cards
- **Construction:** `bg-white/70 backdrop-blur-xl border border-white/60`. Top rim features an ultra-fine linear gradient line transitioning from `rgba(255, 255, 255, 0.8)` to `transparent`.
- **Telemetry Indicators:** Metrics displayed in `Geist`, headline scale, with unit superscripts in slate mist. Sparklines are rendered with 1.5px stroke weight using primary or secondary hues over soft shaded gradient fills fading to zero opacity at the baseline.

### Dual Pathway Switcher (Community Reporting vs. Authority Operations)
- **Container:** Segmented pill bar surfaced with `rgba(244, 244, 245, 0.8)` and a 1px inner border.
- **Active Segment:** Elevated white pill (`#FFFFFF`) with `box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05)`, text color `#0D5C75`, and an micro-dot status glow (cyan for Community, teal for Authority).

### Status Chips & Sensor Badges
- **Form:** Pill-shaped (`rounded-full`), height 24px, padding 0 10px.
- **Variant - Optimal Air:** Pale emerald glass tint (`rgba(16, 185, 129, 0.08)`), text `#059669`, with a pulsing 6px breathing dot.
- **Variant - Elevated Ozone:** Pale amber glass tint (`rgba(245, 158, 11, 0.08)`), text `#D97706`.
- **Variant - Authority Advisory:** Soft dusk purple tint (`rgba(124, 58, 237, 0.08)`), text `#7C3AED`.

### Input Fields & Search Bars
- **Surface:** `rgba(255, 255, 255, 0.6)` with backdrop blur, inset shadow `inset 0 1px 2px rgba(0, 0, 0, 0.02)`.
- **Borders:** `1px solid rgba(0, 0, 0, 0.06)`. On focus: `border-color: #3B82F6` accompanied by an ethereal azure focus ring (`box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12)`).
- **Placeholder:** `#A1A1AA` set in `body-md`.

### Precision Checkboxes & Radios
- **Checkboxes:** 18px square with 4px border radius. Unchecked: `border: 1px solid rgba(0, 0, 0, 0.15)`, background: `rgba(255, 255, 255, 0.5)`. Checked: `#0D5C75` with crisp white check glyph.
- **Radios:** 18px concentric circle. On selection, inward animation of a 6px solid teal core enveloped by a 2px translucent white halo.