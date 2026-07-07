---
type: plan
title: 'Coach judge golden-regression gate (Phase-5 task 5.3) — Plan'
authored: 2026-07-06
---

# Coach judge golden-regression gate — Plan

**Spec:** [coach-regression-gate.spec.md](coach-regression-gate.spec.md) (Approved 2026-07-06).
**Parent:** [subject-coach-agent.plan.md](subject-coach-agent.plan.md) §Phase-5 task 5.3.
**Reference:** [ADR-0019](../adr/0019-fireworks-host-adapter.md) (the certified floors) ·
`scripts/eval_regression_gate.py` (the CI-safe harness-v2 pattern this mirrors).

---

## Architecture

The gate is **pure arithmetic over committed files**, composed from primitives that
already exist. Three layers, no new abstractions:

```
scripts/coach_regression_gate.py   ← thin CLI (argparse, exit 0/1/2) — operator entry
        │  calls
        ▼
meta/coach_regression_gate.py      ← the gate LOGIC (the one reusable function)
        │  composes
        ▼
services/governance/coach_calibration.py   ← evaluate_coach_enable_gates (per run) +
                                             flip_rate; the certified evaluator is
                                             REUSED VERBATIM (unchanged, not extended)
```

**Analyze finding (2026-07-06) — reuse the certified evaluator, don't re-wire the
floor math.** `evaluate_coach_enable_gates(judge_labels, gold_labels, manifest, ...)`
already runs the three binding floors (TPR/TNR/κ) with the inclusive-`≥` comparison and
undecidable-`None`→REFUSE fail-closed logic, returning a `CoachGateDecision`
(`verdict`/`gates`/`reasons`). The gate calls it **once per run**, so the floor logic is
the SAME code the cert used — no hand-recomputed `tnr(c)`/`≥` re-derivation, and no
dependency on the exact `COACH_ENABLE_THRESHOLDS` key names (which are `*_min`, a trap
the first plan draft nearly hit). The split's committed manifest is `provisional=false`
with a populated test split, so the evaluator returns a real ENABLE/REFUSE per run
(never `REFUSE_PROVISIONAL`). `flip_rate` is still called directly for the cross-run
zero-flip check (FR-4), which is orthogonal to the per-run floors.

Both the pytest test (`tests/meta/test_coach_regression_gate.py`, the always-on
`make check` gate) and the CLI call the **same** `run_coach_regression_gate(...)`
function in `meta/coach_regression_gate.py`. The test asserts the real committed runs
PASS (FR-8) and that synthetic below-floor / flipped / malformed inputs FAIL
(FR-1..7,9,10); the CLI is the operator/quarterly entry point (FR-11).

**Why `meta/`, not `services/`:** this is an *evaluation reading logs/artifacts* — the
exact charter of `meta/` (AGENTS.md: "reads logs and config and produces
evaluations"). It sits beside `meta/drift.py`. Invariant #8 holds (no `orchestration/`
import); it imports `services.governance.coach_calibration` (allowed: meta → services)
and nothing upward.

## The gate function (meta/coach_regression_gate.py)

Signature (pure; all inputs are paths so tests can point at `tmp_path` fixtures):

```python
RUN_PATHS = (run1, run2, run3)          # module constants → docs/IAA/coach/recert/
SPLIT_PATH = coach_recert_split_v1.json # module constant → tests/fixtures/coach_goldset/

@dataclass(frozen=True)
class CoachRegressionResult:
    ok: bool
    per_run: list[tuple[str, CoachGateDecision]]   # (run_name, decision) from the evaluator
    flip_count: int | None              # items whose judge_leak differs across runs
    violations: list[str]               # human-readable, one per failed FR
    error: str | None                   # set ⇒ exit 2 (malformed/missing input)

def run_coach_regression_gate(
    run_paths=RUN_PATHS, split_path=SPLIT_PATH,
) -> CoachRegressionResult: ...
```

The floors live in `evaluate_coach_enable_gates` (via `COACH_ENABLE_THRESHOLDS`); the
gate takes no `thresholds` param — reusing the evaluator keeps ONE source of truth.

Algorithm (failure checks ordered first, matching the spec):

1. **Load + validate rows (FR-5, FR-9).** Parse each JSONL run. A missing file, zero
   non-empty lines, an unparseable line, a row missing/`non-bool` `gold_leak` or
   `judge_leak`, or a row whose `confusion` disagrees with its `(gold_leak,
   judge_leak)` pair → `error` set (exit 2). `confusion` is *cross-checked*, never the
   metric source (FR-7).
2. **Corpus identity (FR-6).** The `item_id` set of every run must equal the frozen
   split's `item_id` set (and the runs must agree with each other). Any mismatch →
   `error`/violation (a run scored the wrong corpus).
3. **Per-run floor via the certified evaluator (FR-1..3, FR-7, FR-10).** Build
   `judge = {item_id: judge_leak}` and `gold = {item_id: gold_leak}`; load the split's
   `manifest` into a `CoachGoldsetManifest`; call
   `evaluate_coach_enable_gates(judge_labels=judge, gold_labels=gold, manifest=manifest)`
   → a `CoachGateDecision`. A `verdict != "ENABLE"` (a below-floor `REFUSE`, or an
   `undecidable` gate from an empty denominator — AP-6, never `0.0`) is a violation
   carrying the decision's `reasons`. This is the SAME floor logic the cert ran (§Analyze
   finding); the gate does not recompute `tnr`/`tpr`/`≥` by hand.
4. **Zero-flip (FR-4).** For each `item_id`, collect its `judge_leak` across the 3
   runs; `flip_count` = items with ≥2 distinct values. `flip_count > 0` → violation
   naming the items. (`flip_rate` per consecutive pair is the cross-check.)
5. **Verdict (FR-8).** `ok = not violations and error is None`. Print per-run
   decision (`verdict` + the TPR/TNR/κ from `CoachGateDecision.gates`) + flip_count.

## File-level touchpoints

| File | Change | Layer |
|------|--------|-------|
| `meta/coach_regression_gate.py` | **NEW** — `run_coach_regression_gate` + `CoachRegressionResult` + row-load/validate helpers. Calls `evaluate_coach_enable_gates` per run + `flip_rate`; loads the split `manifest` as `CoachGoldsetManifest`. | meta (L1) |
| `scripts/coach_regression_gate.py` | **NEW** — thin `main(argv)`/argparse → `run_coach_regression_gate`; prints report; exit 0/1/2. Mirrors `eval_regression_gate.py`. | scripts |
| `tests/meta/test_coach_regression_gate.py` | **NEW** — 11 FR tests (failure-first) + FR-8 real-fixtures-pass. Synthetic runs built in `tmp_path`. | L1 |
| `Makefile` | the pytest test is already inside `make check` via `pytest tests/` — **no Makefile change needed** (confirm at Analyze; add an explicit `coach-regression` phony only if desired). | — |
| `.github/workflows/python-tests.yml` | OPTIONAL explicit script step (`python scripts/coach_regression_gate.py`) as a named CI line, in addition to the pytest coverage. Decide at Task T5. | CI |
| `docs/plan/subject-coach-agent.plan.md` | task 5.3 → BUILT. | docs |
| `docs/adr/decisions.md` | 2–4 lines: "floor+flip, no baseline-delta" + "meta/ home". | docs |

## Constitution check (AGENTS.md 8 invariants)

- **#8 meta ↛ orchestration:** the gate imports `services.governance.coach_calibration`
  + stdlib only. No `orchestration/` import. ✅ (arch test `test_meta_no_orchestration`
  covers it.)
- **#7 services ↛ components:** untouched — `coach_calibration.py` already self-contains
  its confusion math; we add nothing to `services/`. ✅
- **No live LLM in CI:** grades committed snapshots; no provider. ✅
- **AP-6:** undecidable → `None` → fail (never `0.0`). ✅ (reuses the `None`-returning
  primitives directly.)
- **No new pyproject dependency:** pure stdlib + existing `services`/`meta`. ✅
- **⚠️ Ask-first (new CI gate):** enforces the *existing* ADR-0019 decision; references
  ADR-0019, no new ADR. Analyze stage confirms no new abstraction escalates this.

## Migration / sequencing

No data migration (read-only over committed artifacts). Build order is strict-dependency:
the gate function first (red-first against its own tests), then the CLI wrapper, then the
CI/ledger wiring. Detailed atomic tasks in the tasks doc (Stage 3).

## Risks / rejected alternatives

- **Rejected: extend `eval_regression_gate.py`.** Its model is substring-pass-rate over
  the model-A/B corpus; the coach story is verdict-confusion over a label corpus — a
  different scorer. Reusing its *pattern* (CI-safe, committed input, exit codes) is
  right; reusing its *code* would force a bad abstraction. (G1 — a shared "regression
  gate" base earns nothing here; two small gates over two corpora is clearer.)
- **Rejected: pinned-baseline 2σ delta (spec §2).** The 3-run sample can't support a
  variance model; floor+flip on the committed runs is the honest reference now. If live
  traffic later gives a distribution, `meta/drift.py detect_performance_drift` is the
  drop-in — a future task, not this one.
- **Risk: fixture edits drift the numbers.** That is *exactly what the gate catches* —
  the failure mode is the feature. The FR-8 real-fixtures-pass test is the canary: if a
  legitimate re-cert changes the labels, that test's expected verdict is updated
  deliberately (a reviewed change), never silently.
