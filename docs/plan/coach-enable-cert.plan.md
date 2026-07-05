# Plan — `evaluate_coach_enable_gates` cert (Task 3.8)

**Spec:** [coach-enable-cert.spec.md](coach-enable-cert.spec.md) ·
**Precedent:** `services/governance/goaljudge_calibration.py`
(`evaluate_section_2_8_gates`, `GateDecision`, `_gate`, `flip_rate`) ·
**No ADR** — no new dependency / service class / trust type. One AP-6 deviation
(self-contained confusion) → `decisions.md`, not an ADR.

## 1. Approach

Mirror the GoalJudge cert shape 1:1, specialized to the `answer_leakage` leak
class. A new `services/governance/coach_calibration.py` holds the frozen
`CoachGateDecision`, the `CoachVerdict` Literal, the `_gate` min/max/undecidable
helper (copy), a **self-contained** `CoachConfusion` tally + coach-local rate
helpers (TPR/TNR/precision/false-action/flip — clarify §Q1), and
`evaluate_coach_enable_gates` with the manifest-floor-check-FIRST ordering. κ
reuses `services.governance.iaa.krippendorff_alpha_nominal` (NaN→None). No
`meta/` import (services↛meta). All pure/offline → L1, in `make check`.

## 2. File-level touchpoints

| File | Change | Layer / gate |
|---|---|---|
| `services/governance/coach_calibration.py` | **NEW.** `CoachVerdict` Literal; frozen `CoachGateDecision` (verdict, read-only `gates`, `reasons`, `diagnostics`); `COACH_ENABLE_THRESHOLDS` const; `_gate` helper (copy the min/max/undecidable + soft-band logic); **self-contained** `CoachConfusion` NamedTuple + `coach_confusion(judge, gold)` + `tpr`/`tnr`/`precision`/`false_action_rate`/`flip_rate` (FR-4/6); `coach_kappa` wrapping `iaa.krippendorff_alpha_nominal` (NaN→None); `evaluate_coach_enable_gates(*, judge_labels, gold_labels, manifest, provenance_by_id?, axis_labels?)` → `CoachGateDecision` (FR-1..FR-9). | `services/governance/` — **Invariant #7 + ↛meta** |
| `tests/services/governance/test_coach_calibration.py` | **NEW.** FR-1..FR-9 L1 (failure-path first: provisional-refuse, undecidable-refuse, binding-fail-refuse, then enable/augmenting/diagnostic/immutability). Uses the committed 3.7 artifact for FR-1 + synthetic non-provisional fixtures for the pass paths. | tests/ |
| `docs/adr/decisions.md` | The AP-6 self-contained-confusion deviation rationale (clarify §Q1). | docs |
| `docs/plan/subject-coach-agent.plan.md` | Ledger row 3.8 → DONE (machinery; real cert run gated on human α). | docs |

## 3. ADR / gate triggers

**None fire.** No new `pyproject.toml` dependency (Pydantic + stdlib). No new
service *class* (a governance module beside `goaljudge_calibration.py`, same
pattern). No graph node, no `trust/` type. `test_adr_ratchet.py` satisfied. The
AP-6 deviation (self-contained 2×2 tally rather than reusing the goaljudge
container) is a documented small decision → `decisions.md`, below the ADR bar.

## 4. Build order (evidence-gated, TDD)

**Stage A — the decision shell + reject paths (failure-first).**
1. Red: FR-1 provisional-refuse (synthetic provisional manifest + the real 3.7
   artifact), FR-2 undecidable-refuse, FR-3 binding-fail-refuse. Watch fail
   (module doesn't exist).
2. Green: `CoachVerdict`, frozen `CoachGateDecision`, `_gate`, the
   floor-check-first `evaluate_coach_enable_gates` skeleton that returns
   `REFUSE_PROVISIONAL`/`REFUSE`. `pytest tests/architecture/ -q` green (no
   components/meta import).

**Stage B — the rate helpers + binding gates.**
3. Red→green: self-contained `CoachConfusion` + `tpr`/`tnr`/`coach_kappa`; FR-4
   inclusive thresholds (0.90/0.95/0.75); FR-5 all-pass ENABLE on a synthetic
   non-provisional fixture + FR-9 no-flip.

**Stage C — augmenting + diagnostics.**
4. Red→green: FR-6 precision/false-action/flip (+ soft band), FR-7 production-
   subset precision, FR-8 per-axis κ < 0.6 unreliable. All diagnostic-only —
   assert they never change a binding verdict.

**Stage D — close-out.**
5. `make check` green; `decisions.md` entry; ledger row 3.8 → DONE (machinery).
   Paste the test run + a sample `REFUSE_PROVISIONAL` decision on the real artifact.

## 5. Risk + iteration

- **Layer slip (services↛meta):** the tempting reuse is
  `from meta.judge_validation import judge_rates`. FORBIDDEN — meta is above
  services. Rate helpers are coach-local; `tests/architecture/` is the backstop.
  **The one real risk.**
- **AP-6 tension (documented):** the self-contained confusion tally re-derives a
  2×2 the repo has elsewhere. Accepted per clarify §Q1 (decoupling coach governance
  from GoalJudge); the `decisions.md` entry makes it a choice, not drift. Keep the
  tally trivially correct (a 4-line count) so the duplication carries no logic risk.
- **Over-gating:** an augmenting/diagnostic metric must NEVER flip a binding verdict
  (FR-6/7/8 are report-only). A test asserts a failing diagnostic on an otherwise
  all-binding-pass fixture still ENABLEs.

## 6. Out of scope

- The **real ENABLE/REFUSE cert run** (needs the non-provisional human-labeled
  gold set — post-3.7-human-pass; gates 3.9).
- Flipping `COACH_LEAKAGE_GATE_ENABLED` (human Phase-5 / 5.1 — FR-9 forbids it here).
- ECE gating (FR-6 keeps ECE diagnostic-only, never a gate).
