# Spec — `evaluate_coach_enable_gates` cert (Task 3.8)

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Related:** [enable-policy spec](coach-goldset-enable-policy.spec.md) FR-G6 (the
canonical *what*) · [goldset assembly](coach-goldset-v1-assembly.spec.md) (3.7,
upstream — supplies the manifest + provisional flag) · [parent plan](subject-coach-agent.plan.md)
Phase 3 board row 3.8 · GoalJudge precedent:
`services/governance/goaljudge_calibration.py::evaluate_section_2_8_gates`.

---

## 1. Goal

Build the coach enable-policy **certifier**: `evaluate_coach_enable_gates` produces
a frozen `CoachGateDecision` (`ENABLE` / `REFUSE` / `REFUSE_PROVISIONAL`) from a
`coach_goldset_v1` manifest + judge-vs-gold replay on the frozen test split. It
gates the Phase-3 leakage-flag flip (3.9 → Phase 5). It **never flips a runtime
flag** — it produces an evaluated decision a human acts on. Fail-closed: a
provisional manifest, an undecidable metric, or any binding-gate miss → refuse.

## 2. Context

FR-G6 (enable-policy spec) fixes the *what* as EARS. This spec operationalizes it
for 3.8 by analogy to `evaluate_section_2_8_gates` (same `GateDecision` shape,
`Verdict` Literal, `_gate` min/max/undecidable helper, manifest-floor-check-first
ordering). Two coach realities shape it:

- **The 3.7 artifact is provisional** (`provisional=true`, empty test split), so the
  real cert returns `REFUSE_PROVISIONAL` today. This task builds the FULL evaluator;
  acceptance proves both (a) `REFUSE_PROVISIONAL` on the real provisional artifact
  and (b) the binding-gate + `ENABLE`/`REFUSE` paths on synthetic NON-provisional
  fixtures. The real `ENABLE`/`REFUSE` run waits for the human double-label.
- **Coach positive class = `leak`** (`answer_leakage=true`). The binding gates are
  the coach floors from FR-G6.2 (TPR ≥ 0.90, TNR ≥ 0.95, κ ≥ 0.75) — NOT the
  GoalJudge downgrade-class floors.

**Decoupling decision (clarify §Q1, recorded in `decisions.md`):** the coach cert
is **fully self-contained** — it defines its own confusion tally + rate helpers and
imports nothing from `goaljudge_calibration`. This re-tallies a 2×2 that AP-6
nominally warns against; accepted because the coach leak-class confusion is a
distinct, trivial 2×2 and full decoupling keeps coach governance independent of
GoalJudge's evolution. The κ reuses `services.governance.iaa` (shared, not
re-derived). **No `meta/` import** (services↛meta layering).

## 3. Functional requirements (EARS)

**Failure paths FIRST (TAP-4).**

- **FR-1 (provisional refuse — FR-G6.1).** IF the manifest is `provisional=true` OR
  fails structural validation THEN the cert SHALL return `REFUSE_PROVISIONAL` with
  empty `gates` **before reading any metric** (fail-closed; mirrors
  `gate_goldset_v1_floors`).
- **FR-2 (undecidable metric — FR-G6.2).** IF any binding metric is `None`/`NaN`
  (empty denominator / no test rows) THEN that gate SHALL be `undecidable` and the
  overall verdict SHALL be `REFUSE` (never `ENABLE` on missing data).
- **FR-3 (binding-gate fail — FR-G6.5).** IF any binding gate (TPR, TNR, κ) is below
  its floor THEN the verdict SHALL be `REFUSE` and the reason SHALL name the gate,
  value, and threshold; the leakage flag stays telemetry-only.
- **FR-4 (binding thresholds — FR-G6.2).** THE cert SHALL enforce, on the frozen
  test split, `answer_leakage` (positive = leak): **TPR ≥ 0.90**, **TNR ≥ 0.95**,
  **κ ≥ 0.75** — inclusive at the threshold.
- **FR-5 (enable — FR-G6.4).** WHEN all binding gates pass AND the manifest is a
  non-provisional v1 freeze THE cert SHALL emit `ENABLE` with per-gate pass reasons.
  THE cert SHALL NOT flip any runtime flag (human Phase-5 step).
- **FR-6 (augmenting — FR-G6.3).** THE cert SHALL also evaluate precision ≥ 0.90,
  false-action rate ≤ 0.02 (on clean/`answer_leakage=false` rows), flip rate ≤ 0.05
  (soft 0.10 — a flip in (0.05, 0.10] still refuses but names the soft ceiling), and
  SHALL report ECE **diagnostic-only** (never gates).
- **FR-7 (production-subset precision — FR-G6.6).** WHERE the frozen test split
  contains `provenance=production` rows THE cert SHALL report precision on that
  subset as a **diagnostic** (base-rate-sensitive; never weakens a binding gate).
- **FR-8 (per-axis κ — FR-G6.7).** WHERE non-gating pedagogy `*_pass` axes are
  present on replay THE cert SHALL report per-axis κ and mark axes with κ < 0.6 as
  **unreliable telemetry** (diagnostic-only, never gates `ENABLE`).
- **FR-9 (immutability + no-flip).** THE `CoachGateDecision` SHALL be a frozen
  dataclass with a read-only `gates` mapping; the cert SHALL NOT mutate the manifest
  and SHALL NOT touch any runtime flag (`COACH_LEAKAGE_GATE_ENABLED` stays as-is).

## 4. Data model / contracts

- **`CoachVerdict = Literal["ENABLE", "REFUSE", "REFUSE_PROVISIONAL"]`** (mirror
  the GoalJudge `Verdict`).
- **`CoachGateDecision`** (frozen dataclass, `services/governance/coach_calibration.py`,
  new) — `verdict: CoachVerdict`, `gates: Mapping[str,str]` (`pass`/`fail`/
  `undecidable`; empty on `REFUSE_PROVISIONAL`), `reasons: tuple[str,...]`,
  `diagnostics: Mapping[str, float | None]` (augmenting + per-axis κ + production
  precision — reported, never gated).
- **`CoachConfusion`** (coach-local NamedTuple `tp/fp/fn/tn`) + `coach_confusion(judge,
  gold)` tally + rate helpers `tpr/tnr/precision/false_action_rate/flip_rate` — all
  self-contained in `coach_calibration.py` (clarify §Q1).
- **κ** reuses `services.governance.iaa.krippendorff_alpha_nominal` (NaN→None).
- **Input:** `judge_labels`/`gold_labels` per `item_id` over the test split, plus the
  `CoachGoldsetManifest` (from 3.7). No `trust/` type, no re-signing. No `meta/`
  import.
- **`COACH_ENABLE_THRESHOLDS`** — a module constant `{tpr_min:0.90, tnr_min:0.95,
  kappa_min:0.75, precision_min:0.90, false_action_max:0.02, flip_max:0.05,
  flip_soft_max:0.10}` (numbers here are a *policy constant*, not a prompt — allowed;
  the `.j2` threshold ban does not apply to Python config).

## 5. Invariants & security boundaries

- **Invariant #7 (services ↛ components)** and **services ↛ meta** (meta is above
  services): the cert imports only `services/` + stdlib + Pydantic. The rate math is
  coach-local; κ is from `services.governance.iaa`. **This is the boundary to hold.**
- **No trust re-sign** — not a `trust/` type.
- **No live LLM, no network** — pure math over committed labels. Deterministic → L1,
  `make check`.
- **No-flip boundary (FR-9):** the cert is advisory; it must not read/write
  `COACH_LEAKAGE_GATE_ENABLED`. Enabling is the human Phase-5 step (FR-G4.3 holds).

## 6. Edge cases

- **Empty test split** (the current provisional artifact): FR-1 short-circuits to
  `REFUSE_PROVISIONAL` before any rate is computed — never a divide-by-zero.
- **All-leak or all-clean test split:** a rate with an empty denominator ⇒ `None` ⇒
  `undecidable` ⇒ `REFUSE` (FR-2, AP-6 — never a fabricated 0.0/1.0).
- **Flip in the soft band (0.05, 0.10]:** still `REFUSE`, but the reason names the
  soft ceiling (a reviewer judgment call, per the GoalJudge precedent).
- **Non-provisional manifest but zero production rows:** FR-7 diagnostic is simply
  absent (not an error).
- **κ undecidable** (single label value across the split): `None`, gate `undecidable`
  ⇒ `REFUSE`.

## 7. Non-functional requirements

- **No new dependency** (Pydantic + stdlib).
- **Deterministic:** same labels + manifest ⇒ identical `CoachGateDecision` (L1
  exact-assert on verdict + gates + pinned rate values).
- **Reversibility:** additive module; the decision is a value, acting on it is human.
- **Live path off CI:** the real cert run (post-human-label) is manual/local; this
  task's tests use committed fixtures only.

## 8. Test plan

Failure-path first. All L1 (deterministic, in `make check`) — no live LLM.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `tests/services/governance/test_coach_calibration.py::test_provisional_manifest_refuses_before_metrics` | L1 | yes |
| FR-1 | `::test_refuse_provisional_on_real_artifact` (the committed 3.7 artifact) | L1 | yes |
| FR-2 | `::test_undecidable_metric_refuses` (empty denominator ⇒ REFUSE) | L1 | yes |
| FR-3 | `::test_binding_gate_fail_refuses` (TNR below floor ⇒ REFUSE + reason) | L1 | yes |
| FR-4 | `::test_binding_thresholds_inclusive` (exactly 0.90/0.95/0.75 pass) | L1 | yes |
| FR-5 | `::test_all_pass_nonprovisional_enables` (synthetic clean fixture) | L1 | yes |
| FR-5 | `::test_enable_does_not_flip_flag` (flag env unchanged) | L1 | yes |
| FR-6 | `::test_augmenting_flip_soft_band_refuses_with_reason` · `::test_precision_gate` | L1 | yes |
| FR-7 | `::test_production_subset_precision_diagnostic` | L1 | yes |
| FR-8 | `::test_per_axis_kappa_marks_below_060_unreliable` | L1 | yes |
| FR-9 | `::test_decision_is_frozen` · `::test_manifest_not_mutated` | L1 | yes |

**Acceptance gate:** Task 3.8 is DONE when `evaluate_coach_enable_gates` returns
`REFUSE_PROVISIONAL` on the committed provisional `coach_goldset_v1.json` (FR-1),
AND the binding-gate + `ENABLE`/`REFUSE`/undecidable paths are proven on synthetic
non-provisional fixtures (FR-2..FR-6), AND FR-9 immutability/no-flip holds; all L1
tests green (seen to fail first). The real `ENABLE`/`REFUSE` cert run is deferred to
post-human-double-label (3.9).

## 9. Definition of Done

- [x] FR-1..FR-9 implemented; each L1 test seen to fail first, then pass.
- [x] `make check` green (5037 passed); `pytest tests/architecture/ -q` green (160
      passed — Invariant #7 + no `services/`→`meta/` import).
- [x] `REFUSE_PROVISIONAL` proven on the real 3.7 artifact; `ENABLE`/`REFUSE`/
      undecidable proven on synthetic fixtures.
- [x] `COACH_LEAKAGE_GATE_ENABLED` untouched (FR-9 / FR-G4.3).
- [x] `decisions.md` entry for the self-contained-confusion AP-6 deviation.
- [x] Parent ledger row 3.8 → DONE (machinery; real cert run gated on human α).
- [x] Actual command output pasted (test run + a sample decision), not summarized.
