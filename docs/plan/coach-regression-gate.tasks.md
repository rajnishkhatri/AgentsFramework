---
type: tasks
title: 'Coach judge golden-regression gate (Phase-5 task 5.3) — Task list'
authored: 2026-07-06
---

# Coach judge golden-regression gate — Tasks

**Spec:** [coach-regression-gate.spec.md](coach-regression-gate.spec.md) ·
**Plan:** [coach-regression-gate.plan.md](coach-regression-gate.plan.md) ·
**Reference:** ADR-0019 (certified floors).

Legend — **Dep:** hard dependency · **∥** parallel-eligible · each task is
**red-first** (write the failing test, watch it fail, then implement). Every task
pins its own pass/fail oracle mapped 1:1 to the spec FRs.

---

## Stage-3 checklist ("unit tests for English" — every FR measurable?)

| FR | Claim | Measurable by | Verdict |
|----|-------|---------------|---------|
| FR-1 | run TNR<0.95 → fail | synthetic run w/ ≥5 fp on clean rows → `tnr<0.95` asserted | ✅ |
| FR-2 | run TPR<0.90 → fail | synthetic run w/ ≥2 fn on leak rows | ✅ |
| FR-3 | run κ<0.75 → fail | synthetic run w/ enough disagreement to drop α | ✅ |
| FR-4 | verdict flip → fail | one item `judge_leak` differs run1 vs run2 | ✅ |
| FR-5 | missing/empty/malformed → error | 3 sub-cases: absent path, 0 lines, bad JSON / non-bool field | ✅ |
| FR-6 | corpus mismatch → fail | a run w/ an extra/missing `item_id` vs the split | ✅ |
| FR-7 | metric from truth, not `confusion` | a row w/ a LYING `confusion` but honest pair → metric still correct; and FR-9 catches the lie | ✅ |
| FR-8 | committed runs pass | the REAL 3 files → `ok=True` | ✅ (oracle) |
| FR-9 | mislabeled `confusion` → fail | pair says tn, field says fp → error | ✅ |
| FR-10 | undecidable → None → fail | all-clean run (0 leak rows) → `tpr None` → violation | ✅ |
| FR-11 | make check + CLI 0/1/2 | pytest in `make check`; `main([...])` returns 0/1/2 | ✅ |

No unmeasurable criterion. FR-7 is the subtle one: it needs *two* assertions — the
metric is computed from `(gold_leak, judge_leak)` (so a lying `confusion` field does
not corrupt it) AND the lie is independently caught by FR-9. Both are in T1's tests.

---

## T1 — Gate logic core (`run_coach_regression_gate`) *(Dep: none)* — FR-1..10

**File:** `meta/coach_regression_gate.py` (new) ·
**Test:** `tests/meta/test_coach_regression_gate.py` (new)

**Do:** implement per plan §"The gate function":
- module constants `RUN_PATHS` (the 3 `docs/IAA/coach/recert/recert_labels_fw_run{1,2,3}.jsonl`)
  + `SPLIT_PATH` (`tests/fixtures/coach_goldset/coach_recert_split_v1.json`).
- `CoachRegressionResult` frozen dataclass (`ok`, `per_run`, `flip_count`,
  `violations`, `error`).
- `_load_run(path) -> list[Row] | error` — parse JSONL; validate each row has bool
  `gold_leak`/`judge_leak` and a `confusion` that MATCHES the pair (FR-5, FR-9).
- `run_coach_regression_gate(run_paths, split_path)` running the 5-step algorithm
  (load/validate → corpus-identity → **per-run `evaluate_coach_enable_gates`** (the
  certified floor logic, verbatim — no hand-recomputed `tnr`/`≥`) → zero-flip via
  `flip_rate` → verdict). A run's `CoachGateDecision.verdict != "ENABLE"` (below-floor
  REFUSE or an `undecidable` gate — AP-6) is a violation carrying its `reasons`.
- import ONLY `services.governance.coach_calibration` (`evaluate_coach_enable_gates`,
  `flip_rate`) + `services.governance.coach_goldset_dataset` (`CoachGoldsetManifest`)
  + stdlib. **No `orchestration/` import** (Invariant #8). **NB:** the threshold keys
  are `tpr_min`/`tnr_min`/`kappa_min` — don't hand-index them; the evaluator owns them.

**Red-first order (failure paths FIRST):** write these against a stub that returns
`ok=True` unconditionally, watch each FAIL, then implement:
1. FR-5 missing/empty/malformed → `error` set.
2. FR-9 mislabeled `confusion` → `error`.
3. FR-6 corpus mismatch → violation.
4. FR-1/2/3 each floor breach (synthetic run in `tmp_path`) → violation naming metric.
5. FR-10 all-clean run (0 leak rows) → the evaluator's `tpr` gate is `undecidable`
   (empty denominator) → `verdict != ENABLE` → violation (never `0.0`; AP-6).
6. FR-4 one-item flip across runs → `flip_count==1` → violation naming the item.
7. FR-7 lying-`confusion`-honest-pair → metric computed from the pair is correct.
8. FR-8 LAST — the REAL committed 3 runs → `ok=True`, `flip_count==0`, all floors held.

**Pass/fail:** `pytest tests/meta/test_coach_regression_gate.py -q` green; the 7
failure tests each seen red first; FR-8 passes on the real fixtures. Synthetic runs
built in `tmp_path` — the committed fixtures are NEVER mutated.

---

## T2 — Thin CLI wrapper (`scripts/coach_regression_gate.py`) *(Dep: T1)* — FR-11

**File:** `scripts/coach_regression_gate.py` (new) ·
**Test:** same test file (extend) — a `TestCli` class.

**Do:** mirror `scripts/eval_regression_gate.py`:
- `main(argv=None) -> int`: argparse (`--run` xN or defaults, `--split` default) →
  `run_coach_regression_gate(...)`; print the per-run TNR/TPR/κ + flip line + PASS/FAIL;
  return `0` (ok) / `1` (floor-or-flip violation) / `2` (error). `if __name__ ==
  "__main__": sys.exit(main())`.

**Pass/fail (failure first):**
- `main([...point at a synthetic below-floor run...])` returns `1`.
- `main([...point at a missing run file...])` returns `2`.
- `main([])` (real defaults) returns `0`. (FR-11)
Assert the exit int, not stdout text (TAP-3 — don't pin printed strings).

---

## T3 — CI + Makefile wiring *(Dep: T1, T2)* — FR-11

**File:** `.github/workflows/python-tests.yml` (+ optional `Makefile` phony) ·
**Verify:** the pytest test already rides `make check`'s `pytest tests/` — confirm by
running `make check` and seeing `tests/meta/test_coach_regression_gate.py` collected.

**DECISION (implement, 2026-07-06):** NO YAML/Makefile change. The pytest test is
auto-collected by `pytest tests/`, which is BOTH `make check`'s `test` target AND the
CI `Run L1+L2 test suite` step (`.github/workflows/python-tests.yml:79-82`) — so the
gate is already CI-enforced. `scripts/eval_regression_gate.py` (the pattern this
mirrors) has NO dedicated CI step either, so adding one for the coach gate would be an
inconsistent one-off. The always-on pytest test is the hard gate; the CLI is the
operator entry point. Smaller, consistent, correct.

**Pass/fail:** `make check` green with the new test collected (18 items — pasted);
`python scripts/coach_regression_gate.py` exits 0 on the real runs (pasted).

---

## T4 — Ledgers + Stage-7 review *(Dep: T1–T3)* — DoD

**Do:**
- `docs/plan/subject-coach-agent.plan.md` task 5.3 → **BUILT** (CI-safe replay gate;
  floor+zero-flip on the committed runs; script + always-on test).
- `docs/adr/decisions.md`: 2–4 lines — the "floor+flip, no baseline-delta" choice and
  the `meta/` home (spec §2 / plan rejected-alternatives).
- confirm no new `pyproject` dep, no `orchestration/` import (`pytest
  tests/architecture/ -q`).
- run the **code-review** skill (deterministic) over the diff; interpret; fix criticals.

**Pass/fail:** `make check` + `tests/architecture/ -q` green; reviewer verdict ≠ reject;
ledgers updated; ADR-0019 referenced in the commit (no new ADR).

---

## FR ↔ task coverage matrix (Stage-4 pre-check)

| FR | Covered by |
|----|-----------|
| FR-1 TNR floor | T1 |
| FR-2 TPR floor | T1 |
| FR-3 κ floor | T1 |
| FR-4 zero-flip | T1 |
| FR-5 malformed → error | T1 |
| FR-6 corpus identity | T1 |
| FR-7 metric-from-truth | T1 |
| FR-8 real runs pass | T1 |
| FR-9 confusion cross-check | T1 |
| FR-10 undecidable → None → fail | T1 |
| FR-11 make check + CLI 0/1/2 | T2, T3 |

**No FR unmapped; no task without an FR.** T1 carries the logic (FR-1..10); T2/T3 carry
the surfaces (FR-11); T4 is DoD. Stage-4 zero-coverage check passes on this decomposition.
