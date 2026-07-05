# Tasks — `evaluate_coach_enable_gates` cert (Task 3.8)

**Spec:** [coach-enable-cert.spec.md](coach-enable-cert.spec.md) ·
**Plan:** [coach-enable-cert.plan.md](coach-enable-cert.plan.md)

Linear task groups **3.8a → 3.8e** (each depends on the prior). All L1, TDD
(red→green, paste failing output first), all in `make check`, no live LLM.

## Checklist — every FR collapses to a measurable claim (Stage 3 gate)

| FR | Measurable claim | Test oracle |
|----|------------------|-------------|
| FR-1 | provisional=true (or missing required manifest field) ⇒ `REFUSE_PROVISIONAL`, `gates=={}`, no rate computed | exact-assert verdict + empty gates on real artifact + synthetic malformed |
| FR-2 | any binding metric `None`/NaN ⇒ that gate `undecidable` ⇒ verdict `REFUSE` | craft empty-denominator labels ⇒ assert gate status + verdict |
| FR-3 | a binding gate below floor ⇒ `REFUSE` + reason names gate/value/threshold | TNR-below fixture ⇒ assert reason substring |
| FR-4 | TPR/TNR/κ inclusive at 0.90/0.95/0.75 ⇒ pass | fixture hitting exactly the floors ⇒ all `pass` |
| FR-5 | all binding pass + non-provisional ⇒ `ENABLE`; flag env var untouched | synthetic clean fixture ⇒ `ENABLE`; assert `os.environ` unchanged |
| FR-6 | precision<0.90 / false-action>0.02 / flip in soft band ⇒ named in diagnostics/reasons; ECE never a gate | fixtures per sub-metric ⇒ assert diagnostic key present, verdict driven only by binding set |
| FR-7 | production-subset precision reported as diagnostic when such rows present; absent otherwise | fixture with/without production rows ⇒ assert `diagnostics` key presence |
| FR-8 | per-axis κ reported; axis κ<0.6 flagged unreliable; never gates ENABLE | axis-label fixture ⇒ assert diagnostic entry + ENABLE unaffected |
| FR-9 | `CoachGateDecision` frozen (mutation raises); manifest not mutated; flag untouched | `dataclasses.FrozenInstanceError` assert + manifest identity/field compare |

All nine collapse to exact-assert L1 oracles → **no unmeasurable criterion**; proceed.

---

## 3.8a — decision shell + provisional/undecidable reject paths (failure-first)

**Files:** `services/governance/coach_calibration.py` (new),
`tests/services/governance/test_coach_calibration.py` (new).

- **Red:** write FR-1 (`test_refuse_provisional_on_real_artifact` loading the
  committed `tests/fixtures/coach_goldset/coach_goldset_v1.json`;
  `test_provisional_manifest_refuses_before_metrics` with a synthetic
  `provisional=true` manifest) + FR-1 malformed
  (`test_malformed_manifest_refuses`) + FR-2 (`test_undecidable_metric_refuses`).
  Run → paste failing output (module missing).
- **Green:** `CoachVerdict = Literal["ENABLE","REFUSE","REFUSE_PROVISIONAL"]`;
  frozen `CoachGateDecision(verdict, gates: Mapping[str,str]=_EMPTY, reasons,
  diagnostics: Mapping[str,float|None]=_EMPTY_DIAG)`; `_gate` helper (copy the
  min/max + None/NaN⇒undecidable logic verbatim); the floor-check-FIRST skeleton
  of `evaluate_coach_enable_gates` that reads `manifest.provisional` /
  structural presence and short-circuits to `REFUSE_PROVISIONAL` with empty
  gates **before** any rate; undecidable metric ⇒ `REFUSE`.
- **Verify:** FR-1/FR-2 tests green; `pytest tests/architecture/ -q` green (no
  `components`/`meta` import). `make check`.

## 3.8b — self-contained confusion + binding gates (TPR/TNR/κ)

**Files:** same module + test.

- **Red:** FR-3 (`test_binding_gate_fail_refuses` — TNR below 0.95 ⇒ REFUSE +
  reason), FR-4 (`test_binding_thresholds_inclusive` — exactly 0.90/0.95/0.75 ⇒
  pass), FR-5 (`test_all_pass_nonprovisional_enables`,
  `test_enable_does_not_flip_flag`), FR-9 no-flip subset. Paste red.
- **Green:** `CoachConfusion(tp,fp,fn,tn)` NamedTuple + `coach_confusion(judge,
  gold)` (positive = leak=True); `tpr`/`tnr`/`precision`/`false_action_rate`
  (empty denom ⇒ `None`, AP-6 — never 0.0); `coach_kappa` wrapping
  `iaa.krippendorff_alpha_nominal` (NaN→None); `COACH_ENABLE_THRESHOLDS` const;
  wire the three binding `_gate` calls (TPR min 0.90, TNR min 0.95, κ min 0.75)
  into `evaluate_coach_enable_gates`; verdict `ENABLE` iff binding set == {pass}.
- **Verify:** FR-3/4/5/9-subset green. `make check`.

## 3.8c — augmenting + diagnostics (never gate the binding verdict)

**Files:** same module + test.

- **Red:** FR-6 (`test_augmenting_flip_soft_band_refuses_with_reason`,
  `test_precision_gate`, `test_false_action_gate`, `test_ece_diagnostic_only`),
  FR-7 (`test_production_subset_precision_diagnostic`), FR-8
  (`test_per_axis_kappa_marks_below_060_unreliable`). Each also asserts the
  augmenting/diagnostic metric **never flips an otherwise all-binding-pass
  ENABLE** (`test_failing_diagnostic_does_not_flip_enable`). Paste red.
- **Green:** `flip_rate(pairs)`; the soft-band (0.05,0.10] reason line; populate
  `diagnostics` with precision, false_action_rate, flip, ece(None placeholder),
  production-subset precision (only when `provenance=production` rows present),
  per-axis κ (mark <0.6 unreliable). Binding verdict computed **only** from the
  three binding gates — diagnostics are report-only.
- **Verify:** FR-6/7/8 green + the no-flip-on-diagnostic assertion. `make check`.

## 3.8d — immutability + real-artifact proof

**Files:** test only (+ any hardening the tests force).

- **Red→green:** FR-9 (`test_decision_is_frozen` — `FrozenInstanceError` on
  assignment; `test_manifest_not_mutated` — manifest fields unchanged after a
  call). Re-confirm `test_refuse_provisional_on_real_artifact` prints a sample
  `REFUSE_PROVISIONAL` decision.
- **Verify:** full `pytest tests/services/governance/test_coach_calibration.py
  -q` green; `pytest tests/architecture/ -q` green; `make check` green. Paste a
  sample decision on the real artifact.

## 3.8e — close-out

- `docs/adr/decisions.md`: the AP-6 self-contained-confusion deviation entry
  (2–4 lines; coach cert re-tallies its own 2×2 rather than reusing
  goaljudge_calibration — deliberate decoupling per clarify §Q1).
- `docs/plan/subject-coach-agent.plan.md`: ledger row 3.8 → **DONE (machinery;
  real ENABLE/REFUSE cert run gated on the human α double-label, 3.9)**.
- Commit. Paste the final test run + a sample decision — not summarized.

## Verification map (EARS ↔ task, 1:1)

| FR | Task | Pass/fail check |
|----|------|-----------------|
| FR-1 | 3.8a | REFUSE_PROVISIONAL + empty gates on real artifact & synthetic; no rate read |
| FR-2 | 3.8a | undecidable gate ⇒ REFUSE |
| FR-3 | 3.8b | binding fail ⇒ REFUSE + named reason |
| FR-4 | 3.8b | inclusive floors pass |
| FR-5 | 3.8b | ENABLE + flag env untouched |
| FR-6 | 3.8c | augmenting metrics diagnostic; soft-band reason; ECE never gates |
| FR-7 | 3.8c | production-subset precision diagnostic only when present |
| FR-8 | 3.8c | per-axis κ<0.6 unreliable; never gates ENABLE |
| FR-9 | 3.8d | frozen decision; manifest unmutated; no flag flip |
