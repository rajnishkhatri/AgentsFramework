---
type: log
title: 'Project plans registry — bundle log'
---

# Project plans registry — bundle log

Chronological history, newest first (ISO-8601).

- 2026-06-21 — Added `c1_message_compaction.phase9.runbook.md`: operator-driven runbook for the Phase 9 live-validation step (tagged --no-traffic rev with the 8 CONTEXT_* env vars, `compaction`-phase planning-stress corpus run, analyzer gate). Also extended `scripts/build_planning_stress_corpus.py` with 4 `compaction`-phase rows and `scripts/analyze_planning_traces.py` with the `score_run` compaction branch + `gate_failures` bars (unsafe_folds_total == 0 INVIOLABLE; mean_drop_ratio ≥ 0.20 on the folded subset).
- 2026-06-21 — Added `c1_message_compaction.impl.md`: implementation companion to the C1 design doc (OKF Concept + machine-readable `todos:` array; the what-file/what-function/what-line/what-test build sheet). Design doc unchanged.
- 2026-06-20 — Declared `docs/plans/` an OKF bundle: added `index.md` + this `log.md` and typed frontmatter on every Concept (pure prepend, bodies unchanged). Convention in [CONVENTIONS_OKF.md](../CONVENTIONS_OKF.md); linted by `scripts/okf_lint.py`.
