---
type: log
title: 'Recipes — top bundle log'
---

# Recipes — top bundle log

Chronological history, newest first (ISO-8601).

- 2026-06-20 — Added cross-cutting [Recipe 16 — Adding and Linting an OKF Knowledge Bundle](16_okf_bundle_lint.md): documents how to promote a directory to a declared OKF bundle (add `index.md`/`log.md`, stamp `type` frontmatter, register in `scripts/okf_lint.py`) and keep `python scripts/okf_lint.py` exiting clean. Linked from this bundle's `index.md`.
- 2026-06-20 — Converted `docs/recipes/` to OKF: added this top `index.md` (bundle-of-bundles) + `log.md`, declared 5 topic sub-bundles (gcp / goaljudge / governance / guardrails / memory_extractor) each with their own `index.md` + `log.md`, and added typed frontmatter to all 48 recipe Concepts in place (pure prepend, bodies unchanged, no file moves). Registered the sub-bundles in `scripts/okf_lint.py`.
