# Native-wrap UI redesign — design artifacts (PS2/PS3)

Reference-only export from the Claude Design (`/design-sync`) project, imported
2026-06-22. **Nothing here is application source** — it is design provenance and
the design-agent's composed layouts, kept to inform the in-repo P2/P3 work.

Provenance: extracted from `AgentsFramework UI.zip`. Only the non-source
artifacts were taken; the zip's `.tsx`/`globals.css`/`styles.css` were an
*older pre-P2 baseline* (no status-orb, pill composer, primitive ToolCard, or
cocoa-dark tokens) and were deliberately **not** merged — the authoritative
source is the committed P2 work (`9df8656`) plus the DTCG token files under
`design/tokens/`.

## Contents

- **`screens/`** — the design agent's composed layouts (PS3 output):
  - `Final Showcase.html`, `Font Options.html`
  - `Mobile Chat.html`, `iPad Chat.html`, `All Surfaces.html`
  - `Dark Background Options.html`, `Dark Muted Options.html`
  These are the layout/spec reference for implementing P3 (responsive variants)
  and any further P2 surface polish. Open them in a browser to view.
- **`frozen/`** — the v1→v13 design-iteration history (HTML + CSS snapshots).
  `styles.v13-cocoa-dark.css` is the latest; the cocoa-dark + per-mode dark
  derived values it pioneered are already reflected in `design/tokens/` and the
  generated theme.
- **`ui_kit_previews/`** — rendered previews of the 14 synced primitives (the
  design-sync render-check output). `index.html` is the catalog.
- **`uploads/`** — source screenshots used during the design session.
- **`_ds_manifest.json`** — the design-sync bundle manifest for this export.

## How to use

When implementing P3 (or polishing P2), open the relevant `screens/*.html` as
the visual target and build the layout with the real primitives in
`frontend/components/ui/` against the live tokens. Do **not** copy HTML/CSS from
here into the app — these are static design renders, not the token-driven
React source.
