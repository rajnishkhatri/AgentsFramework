# AgentsFramework UI — Export Bundle

Self-contained export of the AgentsFramework UI design system. Open `kit/index.html`
to browse components; open `Verify.html` to auto-check the stylesheet against the spec.

## Contents

| File | What it is |
|---|---|
| `styles.css` | **The stylesheet** — all 14 primitives, `.nav-item`, `.status-orb`, etched surfaces, and the ≥44pt coarse touch layer. Rebased to the **production token baseline** (root 16px). |
| `bundle.js` | React component bundle. Exposes composed components on `window.AgentsFrameworkUI_f8ce5c` (needs React + ReactDOM loaded first). |
| `Verify.html` | Live self-checking harness. Renders real elements, measures them, and introspects the CSS source. Open it and read the Pass/Fail/Manual scorecard. |
| `Responsive Layout Spec.md` | Desktop / iPhone / iPad spec with exact values + verification checklist. |
| `kit/` | One preview page per primitive (`index.html` is the gallery). |

## Usage

```html
<link rel="stylesheet" href="styles.css" />
<!-- For React components: -->
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js"></script>
<script src="bundle.js"></script>
<script>const { ChatShell, Composer, ToolCard } = window.AgentsFrameworkUI_f8ce5c;</script>
```

Compose with the token classes and `var(--*)` custom properties — never hard-code hex.

## Token baseline (production)

| Token | Light | Dark |
|---|---|---|
| `--color-bg` | #f9f7f5 | #241c15 |
| `--color-fg` | #1f1e1d | #f9f7f5 |
| `--color-muted` | #7d7a75 | #e4e1da |
| `--color-accent` | #c2704e | #d98b6a |

Warm-neutral terracotta theme, verbatim from `design/tokens/*` → `app/generated-theme.css`.
Dark bg is cocoa `#241c15` (NOT `#1f1e1d` — that's the dark *fg*); muted is warm
`#7d7a75`/`#e4e1da`, never cool-gray `#6b7280`/`#9ca3af` (the dead pre-terracotta values
the §2.6 contract forbids).

Root = **16px**. `--radius-sm/md/lg` = 0.375/0.5/0.75rem = **6/8/12px**.

## Notes
- **Touch targets:** both this bundle's `@media (pointer: coarse)` rules AND the shipped
  app meet the **≥44pt** floor — the app encodes it always-on via Tailwind `size-11` /
  `min-h-11` (hamburger, theme toggle, composer Add/model-picker/Send), verified 44×44 live.
  (The autosizing message textarea has a 40px *min-height*, but that is a text field, not a
  tap target.) The two implementations reach the same 44pt via different mechanisms.
- **Fonts:** `styles.css` `@import`s Geist from Google Fonts so it works standalone; the app self-hosts Geist via next/font.
