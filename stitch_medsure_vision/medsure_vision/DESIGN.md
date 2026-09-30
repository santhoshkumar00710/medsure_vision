---
name: MedSure Vision
colors:
  surface: '#fcf8fc'
  surface-dim: '#dcd9dd'
  surface-bright: '#fcf8fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f2f7'
  surface-container: '#f0edf1'
  surface-container-high: '#eae7eb'
  surface-container-highest: '#e4e1e6'
  on-surface: '#1b1b1e'
  on-surface-variant: '#464555'
  inverse-surface: '#303033'
  inverse-on-surface: '#f3f0f4'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4c42e9'
  primary: '#493ee5'
  on-primary: '#ffffff'
  primary-container: '#635bff'
  on-primary-container: '#fefaff'
  inverse-primary: '#c3c0ff'
  secondary: '#5d5d6a'
  on-secondary: '#ffffff'
  secondary-container: '#e3e1f1'
  on-secondary-container: '#636370'
  tertiary: '#00675c'
  on-tertiary: '#ffffff'
  tertiary-container: '#258175'
  on-tertiary-container: '#effffa'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#321ed2'
  secondary-fixed: '#e3e1f1'
  secondary-fixed-dim: '#c6c5d4'
  on-secondary-fixed: '#1a1b26'
  on-secondary-fixed-variant: '#454652'
  tertiary-fixed: '#9cf2e3'
  tertiary-fixed-dim: '#80d6c7'
  on-tertiary-fixed: '#00201c'
  on-tertiary-fixed-variant: '#005047'
  background: '#fcf8fc'
  on-background: '#1b1b1e'
  surface-variant: '#e4e1e6'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '800'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 30px
    fontWeight: '800'
    lineHeight: 38px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 30px
    letterSpacing: -0.005em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  title-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system defines a mobile-first, AI-assisted medicine pack screening platform built for the Indian healthcare ecosystem. The interface bridges high-velocity operational environments (busy retail pharmacists, distributor loading bays) and sensitive personal moments (elderly patients, low-literacy caregivers checking strip authenticity). 

The emotional tone balances clinical rigor with warm, approachable SaaS modernism—drawing visual inspiration from crisp lilac-tinted containers, high-contrast black typography, and pill-shaped structural tokens. The experience must feel infallible, protective, and immediate: zero ambiguity during verification, high legibility under erratic ambient lighting, and frictionless ergonomics for single-handed mobile scanning.

The aesthetic blends **Modern SaaS Warmth** with **Accessible Clinical Utility**:
- **Pill Geometry & Soft Canvases:** Pill-shaped interaction controls and pill tags evoke medicine capsules, softened with rounded container geometry.
- **High-Contrast Clarity:** Bold headlines, deeply saturated dark ink, and generous whitespace ensure visual comfort for senior citizens and tired warehouse staff alike.
- **Clarity-First Color Feedback:** Status outcomes rely on unmistakable chromatic signals paired with explicit micro-copy, iconography, and dual multilingual labels (English, Hindi, Tamil).

## Colors

The color palette prioritizes clinical authority without cold sterility. The default experience operates strictly in **light mode** to maximize readability under harsh pharmacy fluorescent strips or outdoor sunlight at distribution docks.

### Palette Architecture
- **Primary (`#635BFF`):** A digital violet-indigo conveying high-tech verification intelligence. Used for primary CTAs, focal active states, and AI visual focus points.
- **Secondary (`#EEECFC`):** A soft, calming lilac surface wash used for container fills, secondary interactive buttons, and gentle framing cards as seen in modern warm SaaS layouts.
- **Tertiary (`#107569`):** A medical pine teal used for verified low-risk security guarantees, clinical notes, and auxiliary information.
- **Neutral (`#131316`):** Deep carbon black for text, providing an uncompromising 14:1 contrast ratio against white and off-white backdrops.

### Status Tiers (Screening & Verification)
Each verification state is mapped to a dedicated pair of solid foreground accents and pale background tints:
- **Low Risk (Authentic):** Emerald `#0E8A54` on `#EBFDF2` tint. Conveys complete confidence.
- **Needs Verification (Anomaly / Flag):** Warm Amber `#B54708` on `#FFFAEB` tint. Directs attention to batch mismatches or secondary checks.
- **High Suspicion (Counterfeit / Alert):** Crimson `#D92D20` on `#FEF3F2` tint. High urgency with clear advisory steps.
- **Insufficient Quality (Rescan Needed):** Slate Indigo `#475467` on `#F2F4F7` tint. For blurred cameras, glare, or torn blister foils.

### Canvas & Foundation Tones
- **Canvas Base:** Pure White `#FFFFFF` for primary cards and sheets; soft Off-White/Mist `#F8F9FC` for page scaffolding.
- **Border Ghost Tint:** `#E5E7EB` (40% opacity on soft panels, 100% on interactive boundaries).

## Typography

The design system standardizes on **Plus Jakarta Sans** across display, body, and operational tiers. Its open aperture, wide counters, and rounded modern geometry provide crisp optical rendering on low-cost Android displays while remaining approachable and friendly.

### Multilingual Support (EN / HI / TA)
- When rendering **Devanagari (Hindi)** or **Tamil**, character metrics automatically scale line-height by `+15%` to accommodate vowel matras and conjunct ascenders/descenders without clipping.
- System fallback stacks fall back gracefully to Noto Sans Devanagari and Noto Sans Tamil while maintaining equivalent weights (Medium 500 / SemiBold 600).
- Dual-script microcopy (e.g., "Scan Medicine / दवाई स्कैन करें") uses standard English `title-md` paired with a subordinate Hindi label rendered in `body-sm` neutral slate.

### Accessibility Safeguards
- Base body copy is elevated to `15px` minimum, preventing eye strain for elderly users inspecting blister-pack serials.
- Critical alphanumeric tokens (Batch IDs, Expiry Dates, NAFDAC/CDSCO codes) must be styled in SemiBold weights with an expanded letter-spacing of `+0.04em`.

## Layout & Spacing

A fluid, mobile-first grid governs all layout logic, scaling cleanly across three primary device profiles:
- **Mobile Handheld (360px – 599px):** 4-column layout with `margin: 1rem` (16px) and `gutter: 1rem`. Focuses entirely on full-width camera viewports, vertical scanning result stacks, and thumb-accessible bottom actions.
- **Tablet & Countertop POS (600px – 1023px):** 8-column layout with `margin: 1.5rem` and split dual-pane views (Live scan on left, AI inspection breakdown on right).
- **Desktop & Depot Station (1024px+):** 12-column fixed-max layout (capped at 1280px) for bulk intake triage, inventory audits, and supplier anomaly logs.

### Ergonomic Rules
- All primary interactive elements adhere strictly to a **48px minimum touch target height** (`space-xl` touch envelope) to accommodate wet or gloved pharmacy hands and older fingers with reduced precision.
- Vertical gap between card clusters uses `space-md` (16px); section headers to content blocks follow `space-lg` (24px).

## Elevation & Depth

This system utilizes soft **tonal layering combined with ultra-diffused, ambient purple-tinted shadows** rather than heavy drop-shadows, creating the airy, refined SaaS feel established in the reference.

### Surface Tiers
- **Base Surface (Level 0):** Background screen canvas in `#F8F9FC` or crisp `#FFFFFF`.
- **Raised Container (Level 1):** Soft container blocks utilizing `#EEECFC` (soft lilac) or `#FFFFFF` bound by a delicate outline (`1px solid rgba(99, 91, 255, 0.08)`).
- **Floating Overlay (Level 2):** Inspection bottom-sheets, scan modal dialogs, and verification banners. Rendered with an ambient shadow: `0 12px 32px -4px rgba(33, 23, 95, 0.08), 0 4px 12px -2px rgba(33, 23, 95, 0.04)`.
- **Critical Action/Floating Bar (Level 3):** Scanner shutter trigger and emergency warning banners. Casts a focused, brand-tinted bloom: `0 16px 36px -6px rgba(99, 91, 255, 0.28)`.

### Border Discipline
All cards and interactive modules employ low-contrast ghost borders (`1px solid #E4E7EC` or `1px solid rgba(99, 91, 255, 0.12)` on lilac containers) ensuring crisp physical structure without visual noise.

## Shapes

The geometry reflects medical confidence softened by digital empathy. A baseline roundedness rating of **2** (`0.5rem` base, `1rem` on cards, and `1.5rem` on larger modals) gives structure to the operational UI, punctuated by **full pill geometry (`9999px`)** for badges, navigation tags, and primary CTAs.

### Radius Assignments
- **Chips, Badges, & Action Pills:** Full pill radius (`9999px`) to echo medicinal capsules and provide a clean, touchable silhouette.
- **Card Containers & Result Modules:** `rounded-lg` (`1rem` / 16px) for approachable encapsulation.
- **Camera Viewport Cutout & Modal Drawers:** `rounded-xl` (`1.5rem` / 24px) on top edges to embrace friendly modern mobile ergonomics.
- **Inputs & Data Fields:** `rounded` (`0.5rem` / 8px to 12px) to communicate clean tabular alignment.

## Components

### 1. Buttons
- **Primary Action (Scan / Confirm / Report):** Full pill-shaped (`9999px`), solid `#635BFF` fill with crisp white text (`label-lg`), minimum height of `48px` (desktop: `44px`). Accompanied by a trailing arrow icon or camera icon. Hover/tap states shift to `#5147E5`.
- **Secondary Action (Manual Entry / Batch Check):** Soft lilac fill (`#EEECFC`), text in `#635BFF`, 0px border. Provides a zero-friction alternate choice.
- **Destructive Action (Report Counterfeit):** Crimson boundary with soft red tint `#FEF3F2`, text `#D92D20`.

### 2. Status & Verification Badges
Large, prominent verification tags designed for instant at-a-glance recognition:
- **Badge Anatomy:** Full pill container (`9999px`), `32px` to `40px` height, featuring a bold status icon on the left (Check, Warning Triangle, Shield X, Camera Refresh), uppercase status label in `label-md`, followed by an optional localized secondary label.
- **Low Risk:** Solid `#0E8A54` on `#EBFDF2` background, bordered with `#A6F4C5`.
- **Needs Verification:** Solid `#B54708` on `#FFFAEB` background, bordered with `#FEDF89`.
- **High Suspicion:** Solid `#D92D20` on `#FEF3F2` background, bordered with `#FECDCA`.
- **Insufficient Quality:** Solid `#475467` on `#F2F4F7` background, bordered with `#D0D5DD`.

### 3. Language Selector (EN / HI / TA)
- Persistent in top navigation header: pill toggle chip showing active language with chevron (e.g., `🇮🇳 हिंदी (HI)`).
- Tapping opens a bottom-sheet with large, thumb-friendly radio rows clearly styled with local native scripts (English, हिन्दी, தமிழ்).

### 4. Inspection Result Cards
- Constructed with a dual-tone surface: `#FFFFFF` primary container with inner secondary sections backed by `#EEECFC` (soft lilac).
- Displays extracted medicine name (`headline-sm`), manufacturer name (`body-sm`), matched hologram fidelity score, and expiry date.
- Explicit visual cues (green tick vs red alert icon) alongside each verified pack attribute (Packaging Foil, Font Alignment, Hologram, 2D DataMatrix).

### 5. Input Fields (Manual Search & Batch Verification)
- Height `48px`, `rounded-md` (8px), background `#FFFFFF`, border `1px solid #D0D5DD`.
- On focus: `border-color: #635BFF` with an exterior soft focus ring `0 0 0 4px rgba(99, 91, 255, 0.12)`.
- Numeric keypad default for Batch & Pin fields.

### 6. Shutter & Camera Guidance Frame
- Viewport features rounded bounding brackets (`#635BFF`) with dynamic real-time alignment text ("Align medicine blister pack inside the frame").
- High-contrast floating white pill at bottom center containing the capture trigger.