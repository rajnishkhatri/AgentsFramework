---
title: 'Design-agent prompt — English Coach: Skill-detail lesson screen'
type: design-prompt
epic: E
date: 2026-07-11
status: Ready to hand to a design agent
derives_from: docs/plan/preact-parity-epic-E-lesson-design.brainstorm.md
prototype_ref: docs/plan/assets/preact-parity-2026-07-09/proto/06-skill-detail.png
note: 'Self-contained — a design agent needs NO repo access. Everything (tokens, regions, a11y/CSP rules) is embedded below. Copy the body from the marker.'
---

# Design-agent prompt — Skill-detail lesson screen

> Hand everything below the marker to a design agent. It is self-contained: literal design tokens,
> exact regions/copy, responsive variants, and hard a11y/CSP guardrails are all inline. The agent needs
> no access to this repository.

<!-- ─────────────────── COPY FROM HERE ─────────────────── -->

You are a senior product designer. Produce a **high-fidelity HTML/CSS mockup** of a single screen — the
**Skill-detail lesson** ("Skill detail / tutorial") for an ACT English study web app called *English
Coach*. You have NO access to the source repository; everything you need is in this prompt. Produce a
self-contained `.html` file (inline `<style>` is fine for a mockup deliverable — this is a static design
artifact, not production code) that renders faithfully in a browser, plus a one-paragraph rationale.
Deliver desktop, iPad, and iPhone frames.

## 1. What this screen is
A per-skill mini-lesson. For the reference skill **Punctuation** it teaches the comma rule, shows worked
examples, diagnoses the learner's recent misses, charts accuracy over the last 6 sessions, and lists
what's due for review. It is reached from a dashboard bucket card, from a session-summary "See full
explanation lesson" link, and its own CTA starts a drill. It is a **calm, non-focus, sidebar-bearing**
screen (see §6) — NOT a distraction-free quiz.

## 2. Exact regions and copy (use verbatim)
The body is a **TWO-COLUMN layout under a full-width header** — NOT a five-region vertical stack. On
desktop: header spans both columns; left column ≈ 2fr, right column ≈ 1fr.

**Header (full width, bucket-tinted):** a 14px rounded color swatch (the Punctuation accent) ·
**Punctuation** (large) · sub-line "Commas, colons, semicolons · ~19% of ACT English" (muted) · a primary
CTA button **"Drill this skill"** top-right.

**Left column, block 1 — the lesson (this is the E1 deliverable):**
- Eyebrow: **The rule, in one line**
- Rule body (renders from a markdown string): "A non-essential clause (one you could remove and still
  understand the sentence) must be fenced by a pair of commas. An essential clause that identifies which
  thing you mean takes no commas."
- A checkmark ✓ list of worked examples (renders from a `string[]`):
  - ✓ My car, which is electric, is quiet. *(remove it — still works → commas)*
  - ✓ The car that I bought is electric. *(needed to know which → no commas)*
- **Reserve an annotated empty slot directly below this list** labeled, in a dashed placeholder, "P2:
  faded worked-example ladder mounts here (worked ●●● → completion ●●○ → independent ○○○)". This is the
  forward-compatibility hook — render it as a visibly deferred placeholder, not real content. (Rationale
  in §9.)

**Left column, block 2 — Why you missed these:**
- Eyebrow with a ✦ glyph: **Why you missed these** · muted sub-label "auto-built from your 4 misses"
- Body: "Across 4 missed items you removed commas to make the sentence shorter. Your tell: when the clause
  starts with \"which\", pause and test removal first." · muted trailing line "Drill the 4 below to clear
  this."

**Right column, block 1 — Accuracy chart:**
- Large stat "Accuracy 49%" · caption "Last 6 sessions · trending up"
- A **6-bar vertical bar cluster** with ascending heights (use 32, 28, 42, 40, 55, 62 as the six
  percentages). There is no chart library — build the bars from simple divs (see §5). Each bar sits in a
  faint track; the fill is the skill accent color. **Always show the numeric accuracy too** — bars are
  never the only signal.

**Right column, block 2 — Due for review:**
- Eyebrow: **Due for review**
- A small pill whose data label is "Today" but is CSS-uppercased to render as **TODAY** (warning-colored)
  · copy "4 comma items · spaced repetition".

All numbers (49%, 4 misses, ~19%, the 6 bar heights) are placeholders — style them as real but treat them
as sample data.

## 3. Left navigation sidebar (present on desktop AND iPad; becomes a bottom tab bar on iPhone)
Brand mark: an "A" avatar + "English Coach". Nav items: Dashboard, Practice, **Skills (active)**, Progress,
Coach. The Skills item is the active/highlighted one on this screen. A light/dark theme toggle lives in
the top chrome.

## 4. Design tokens — use THESE literal values (do not invent colors)
The app is fully theme-aware. Author with CSS custom properties and provide BOTH a light and a dark theme;
the dark theme activates under `[data-theme="dark"]` on the root AND `@media (prefers-color-scheme: dark)`.
Every colored surface must be legible in both.

**LIGHT theme:**
- `--color-bg: #f9f7f5` · `--color-fg: #1f1e1d` · `--color-muted: #666460`
- `--color-accent: #93513d` (brand) · `--color-on-accent: #ffffff`
- `--color-surface: #f4f1ee` (a card fill: bg 96% / fg 4%) · `--color-surface-sunken: #efeae6`
- `--color-selected: rgba(31,30,29,0.06)` (faint track fill) · `--color-border: rgba(31,30,29,0.12)`
- `--color-success: #2a7f51` (use for the ✓ checks) · `--color-danger: #c0392b` · `--color-warning: #a9741f`
- Bucket accents: rhetoric `#a75c44` · usage `#94672d` · **punctuation `#3e7b6d`** · organization
  `#627741` · sentence-structure `#537397` · conciseness `#926086`

**DARK theme (`[data-theme="dark"]`):**
- `--color-bg: #241c15` · `--color-fg: #f9f7f5` · `--color-muted: #e4e1da`
- `--color-accent: #e5967c` · `--color-on-accent: #241c15` (on-* flips to the dark bg — do NOT hardcode
  white text on filled buttons)
- `--color-surface: #322a24` · `--color-surface-sunken: #3f3831`
- `--color-selected: rgba(245,245,245,0.10)` · `--color-border: rgba(248,248,248,0.14)`
- `--color-success: #5cba86` · `--color-danger: #e57368` · `--color-warning: #e3b357`
- Bucket accents: rhetoric `#e5967c` · usage `#d6a45a` · **punctuation `#6bbfa9`** · organization
  `#9bb56e` · sentence-structure `#84a6cc` · conciseness `#c08fb4`

**Radii (theme-independent):** `--radius-sm: 0.625rem` · `--radius-md: 1rem` · `--radius-lg: 1.375rem`.
Cards use a literal **13px** radius (this is the app's canonical card corner — use `border-radius: 13px`
on cards, `--radius-sm` on compact chips/buttons).

## 5. Visual idiom — reproduce these exact patterns
**Cards:** `display:flex; flex-direction:column; gap:12px; border-radius:13px; border:1px solid
var(--color-border); padding:16px` (grid/section cards) or `padding:20px` (hero/callout cards). Never use
a different card radius.

**Per-skill accent scoping:** set a local `--accent` on the screen root to the skill's bucket token, e.g.
`style="--accent: var(--color-bucket-punctuation)"`, then read `var(--accent)` in tints. Use these
`color-mix` formulas exactly:
- Accent-forward header/callout card: border `color-mix(in oklab, var(--accent) 35%, var(--color-border))`
  + background `color-mix(in oklab, var(--accent) 8%, transparent)`.
- Interactive card (hover-able): border `color-mix(in oklab, var(--accent) 30%, var(--color-border))`.
- A per-skill tinted pill (like a "Due" chip): `border-radius:9999px; background: color-mix(in oklab,
  var(--accent) 18%, transparent); padding:2px 8px; font-size:12px; font-weight:600`.

**StatTile (for "Accuracy 49%"):** an uppercase, letter-spaced, muted label (`font-size:12px;
font-weight:600; text-transform:uppercase; letter-spacing:.04em; color:var(--color-muted)`) above a large
value (`font-size:24px; font-weight:600; font-variant-numeric:tabular-nums`).

**Accuracy bars (no chart lib):** a flex row of 6 columns; each column is a track
`background:var(--color-selected); border-radius:9999px; overflow:hidden; width:100%` with a fill
`background:var(--accent); border-radius:9999px` whose height is the session %. Pair the cluster with the
visible "49%" number.

**Section eyebrows/kickers:** `font-size:12px; font-weight:600; text-transform:uppercase;
letter-spacing:.04em; color:var(--color-muted)`. Skill name = `font-size:20px; font-weight:600`.
Page/region headings = `font-size:18px; font-weight:600`.

**Buttons — critical AA rule:** the **filled primary CTA "Drill this skill" MUST use the brand pair**
`background:var(--color-accent); color:var(--color-on-accent)` — do NOT fill it with the per-bucket
`--accent` (the per-bucket fill measures ~3.6:1 and fails WCAG-AA; brand clears it). Shape:
`border-radius:var(--radius-sm); padding:8px 16px; font-size:14px; font-weight:600`. A secondary action
(e.g. a "See full explanation lesson" link if you add one) is a bordered button: `border:1px solid
var(--color-border); background:transparent;` same padding/weight. The header swatch and accent tints ARE
per-bucket; only the filled CTA fill is brand.

**Badges/chips:** small chips are `border-radius:var(--radius-sm); padding:2px 8px; font-size:12px;
font-weight:500`. Status tints use `color-mix(in oklab, var(--color-<role>) 18%, transparent)` fills with
the matching role text color.

## 6. Responsive variants — deliver all three frames
- **Desktop (content ≤1180px):** persistent left sidebar + top chrome (theme toggle); header spans full
  width; two-column body side-by-side (left ~2fr lesson+why-missed, right ~1fr accuracy+due).
- **iPad (11" landscape):** persistent left sidebar RETAINED; the two-column body renders as-is in the
  wider surface. There is NO split-coach panel on this screen (that pattern is quiz-only). Keep the same
  two-column lesson body.
- **iPhone (≤393pt):** single column — the body collapses to ONE stacked column in reading order: header →
  rule+examples → why-you-missed → accuracy bars → due-for-review. **CRITICAL:** this is a NON-focus
  screen, so the **bottom tab bar STAYS** (Dashboard / Practice / Progress) and there is **NO ✕-close /
  back button** — do not add one. The sidebar becomes the bottom tab bar; it does not disappear.

Present the three frames stacked in the artifact (label each), each in a device-ish container so they
don't float naked.

## 7. The E1 lesson form (what to actually render) vs the P2 aspiration
- **E1 (build this now):** the lesson region is exactly a RULE (one markdown block) + a LIST of ✓ worked
  examples. Flat. No scaffold dots, no completion/independent cards, no per-step state. That is the whole
  lesson content model.
- **P2 (do NOT build — only foreshadow):** later, the lesson becomes a 3-card *backward-fading ladder*:
  Card 1 "Worked example" (dots ●●●, all steps shown, ends in an answer chip "Keep both commas."), Card 2
  "Completion problem" (dots ●●○, last step blank, ends in a "your turn — fill the last step" row), Card 3
  "Independent" (dots ○○○, no steps, ends in "You solve it — no steps given."). Represent this ONLY as the
  annotated dashed placeholder slot from §2 so the eventual upgrade drops into a reserved space without
  moving other regions. Do not render three real cards.

## 8. Accessibility guardrails (WCAG 2.2 AA — non-negotiable)
- Every action is a real `<button>`; the "Drill this skill" CTA is a `<button>` (it starts a session), NOT
  an `<a>`. Use `<a href>` ONLY for real navigation (nav items). Icon-only controls get an `aria-label`.
- The accuracy bar cluster must NOT convey trend by color/height alone: expose it as a labeled group
  (`role="img"` with an `aria-label` like "Accuracy over last 6 sessions, trending up, currently 49%") AND
  keep the visible "49%" number. Color is never the sole signal.
- Provide a visible focus style on all interactive elements. Contrast: body text on bg, muted text, and
  on-accent-on-accent must all pass AA in BOTH themes (the tokens above are chosen for this — pair every
  filled color with its `on-*`/foreground token).
- Real heading hierarchy (`<h1>` skill name, `<h2>` region headings). No layout tables for content; the
  "Due for review" and stat groups may use a `<dl>`.
- Do not put any live-updating region here (no `aria-live`); this is a static lesson.

## 9. Rationale to include (one paragraph)
Explain how the flat E1 lesson (rule + ✓ examples) sits in the left column with a reserved slot beneath it,
so shipping the P2 faded ladder later changes only that slot's contents (dot states + terminal rows) and
never the two-column layout or region order.

## 10. Do NOT
- Do NOT fill the primary CTA with the per-bucket accent (AA failure) — brand `--color-accent`/
  `--color-on-accent` only.
- Do NOT render the iPhone frame as a distraction-free/back-button/no-tab-bar screen — the tab bar STAYS,
  no ✕.
- Do NOT build the 3-card faded ladder as real content — only the annotated placeholder slot.
- Do NOT invent colors or radii outside §4; do NOT use a card radius other than 13px.
- Do NOT add a streak/score-goal rail to this screen (that belongs on the Dashboard, not here) — the right
  column is accuracy chart + due-for-review ONLY.
- Do NOT hardcode white text on filled buttons (breaks dark mode — use `--color-on-accent`).
- Do NOT use hue-named or generic gray/black text on colored fills — always the token foreground.

## Deliverable
One self-contained `.html` file rendering the desktop, iPad, and iPhone frames (each labeled),
theme-aware (light default, dark via `[data-theme="dark"]` and `prefers-color-scheme`), plus a short
rationale paragraph and a one-line note flagging the two deliberate deviations from a pixel prototype
(brand CTA instead of a per-bucket-gradient CTA; sidebar/tab-bar retained on iPhone rather than a back
button).

<!-- ─────────────────── COPY TO HERE ─────────────────── -->
