---
type: log
title: 'Docs — top bundle log'
---

# Docs — top bundle log

Chronological history of the `docs/` knowledge plane, newest first (ISO-8601).

- 2026-06-20 — Phase 3: converted the rest of `docs/` to OKF. Declared bundles for
  `vision`, `contributing`, `handbooks`, `StructuredReasoning`, `walk-through`, `deploy`,
  `explainability`, `Architectures`, `plans`, `plan` (+ 5 layer sub-bundles), and the
  relocation targets `style-guides`, `guides`, `analysis`, `reviews`. Added typed
  frontmatter to ~238 Concepts (pure prepend; native-plan frontmatter got a `type:` key
  inserted). Relocated the 25 loose root files into thematic sub-bundles via `git mv` and
  rewrote every reference (markdown links, `@docs/` @-mentions, `agent/docs/` mentions,
  and the moved files' own outbound relative links). Added this top `index.md` + `log.md`.
- 2026-06-20 — Phase 2: converted `docs/recipes/` to OKF sub-bundles (see
  [recipes/log.md](recipes/log.md)).
- 2026-06-20 — Phase 0: established the convention + first bundles (`docs/skills/`,
  root `research/`); see [CONVENTIONS_OKF.md](CONVENTIONS_OKF.md).
