# Coach judge-validation harness — plan (Task 3.5)

**Status:** Draft — 2026-07-04 · **Owner:** Rajnish Khatri
**Feeds:** the enable-policy cert (FR-G3.1 / FR-G4.1) in
[coach-goldset-enable-policy.spec.md](coach-goldset-enable-policy.spec.md).
**Consumes:** [docs/evals/eng-coach/judge_test_cases.jsonl](../evals/eng-coach/judge_test_cases.jsonl)
(22 cases, provenance-verified verbatim against `coded.jsonl`; H1≡C2 determinism
defect fixed 2026-07-04).

> **What this plan is.** The axial/selective pass (Task 3.4) produced 22 judge
> fixtures with `expected` verdicts but **no runner**. Right now they are a spec
> for a test, not a test. This plan wires them into a committed
> **record-once / replay-in-CI** validation gate for `PedagogyJudge` +
> `GraderJudge`, mirroring the two existing precedents so we invent nothing new.

## 1. Precedents to reuse (no new abstraction — G1)

| Need | Reuse this, don't rebuild |
|---|---|
| TPR/TNR + Rogan-Gladen gate (≥0.90 floor) | `meta/judge_validation.py` (`judge_rates`, `JudgeRates`) atop `services/governance/goaljudge_calibration.py` confusion primitives |
| Live-LLM-out-of-CI record/replay | `tests/fixtures/code_reviewer/wi8_validation/{cases.json,verdicts.json}` + `scripts/record_code_reviewer_validation.py` shape |
| The judge under test | `components/subject_coach_judges.py` — `PedagogyJudge.evaluate(learner_utterance, coach_reply, mode, question)` → `PedagogyVerdict` (`answer_leakage` + 6 float axes) |
| Fixture format | the 22-case JSONL already emitted by Task 3.4 |

**Skill route:** this is squarely the `agentsframework-eval-probe` skill's job
(open-coding → axial → rubric → judge → *registered probe with offline CI
regression + per-component enable-gate*). Run the harness build under that skill;
this plan is its scoped input.

## 2. Architecture / file-level touchpoints

| File | New/edit | Purpose | Layer check |
|---|---|---|---|
| `scripts/record_coach_judge_validation.py` | **new** | Live pass: render each fixture through `PedagogyJudge`/`GraderJudge`, write `verdicts.json`. **Local-only, live LLM — never CI.** Sibling of `record_code_reviewer_validation.py`. | scripts/ — no layer constraint |
| `tests/fixtures/coach_judge_validation/cases.json` | **new** | The 22 cases (copy/symlink of the docs fixture, committed as the test's input). | fixture |
| `tests/fixtures/coach_judge_validation/verdicts.json` | **new** | Recorded judge output, committed. Regenerated only when the judge/prompt changes. | fixture |
| `tests/fixtures/coach_judge_validation/README.md` | **new** | Records model id, date, TPR/TNR achieved, re-record instructions (WI-8 README shape). | fixture |
| `meta/coach_judge_validation.py` | **new (thin)** | Pure scoring: replay `verdicts.json` vs `cases.json` `expected`, emit `JudgeRates` on `answer_leakage`, per-axis agreement, and the H1≡C2 determinism assertion. Composes `meta/judge_validation.py` — no new confusion math (meta AP: never re-implement). | meta/ — reads fixtures + `trust`/`services`; **no orchestration import (Inv #8)** |
| `tests/meta/test_coach_judge_validation.py` | **new** | Replay test: parses committed `verdicts.json`, asserts TPR/TNR ≥ floor, per-axis matches, determinism, control non-regression. **Offline, no live call.** Failure-path first (TAP-4). | tests/meta/ |

**Invariant checks:** `meta/coach_judge_validation.py` imports only
`meta`/`services`/`trust` (Inv #8 ✓, AP-4 ✓). Scoring math is pure (L1). No
`langgraph`/`langchain`. No trust-kernel type change. No new graph node.

## 3. ADR / gate triggers

- **New abstraction (G1)?** No — a scorer that *composes* `judge_validation.py`
  is the same class as the existing GoalJudge validator; it adds no interface.
- **New `pyproject.toml` dep?** No — Langfuse/LiteLLM already present; scoring is
  stdlib + existing primitives.
- **New service / graph node / trust type?** No.
- **Prompt change?** *Not in this plan.* The rubric revision (`.j2` edit →
  AP-3/ADR territory) is **Task 3.6**, gated on what the baseline (Stage B below)
  reveals. Keep them separate: 3.5 measures, 3.6 changes.
- **Conclusion:** no ADR trigger fires for the harness itself. The rubric
  revision in 3.6 *will* need spec+ADR (FR-G4.1 anticipates the rule-naming
  criterion).

## 4. Build order (staged, evidence-gated)

**Stage A — scoring core (offline, TDD, no live LLM).**
1. Red: `test_coach_judge_validation.py` with a tiny hand-built `verdicts.json`
   stub (2–3 rows incl. one leak, one control, the H1/C2 pair) → assert
   TPR/TNR + determinism. Watch it fail (no scorer yet).
2. Green: `meta/coach_judge_validation.py` replay + scoring. `make check` +
   `pytest tests/architecture/` stay green.
   - Failure paths first (TAP-4): unscorable case `I1` (`scorable:false`,
     `answer_leakage:null`) must be **excluded from leak denominators**, not
     counted as a miss; a `null` expected matched only by explicit abstain.

**Stage B — baseline the *current* judge (live, local-only).**
3. Run `record_coach_judge_validation.py` over the 22 cases with today's
   `subject_coach_pedagogy_judge.j2`. This is the honest "where does the shipped
   judge stand" number. **Live LLM → local shell only, keys from env, never CI.**
4. Score with the Stage-A tool. Record TPR/TNR on `answer_leakage`, per-axis
   agreement, and which of the 8 axial assertions fail. Commit `verdicts.json` +
   README (model id, date, rates) **only** as the recorded baseline — the CI test
   replays it, no live call.

**Stage C — report + hand to 3.6 (no leak-rate gate yet — clarify decision).**
5. Report the baseline TPR/TNR **with raw confusion counts** (n=5 positives is too
   thin to gate on a rate). The CI replay test asserts only the deterministic
   properties (determinism, control non-regression, schema/mismatch, unscorable
   handling); it does **not** fail on a sub-0.90 leak rate at Stage 3.5.
6. The failing assertions become the **acceptance criteria for the Task 3.6 rubric
   revision**. Re-record after the `.j2` change; a hard leak-rate gate is
   introduced in 3.6 once the corpus grows to ≥20 overt-demand traces.

## 5. Pass/fail criteria (mapped to the fixture — matches spec §3)

- **Leakage: reported, not gated (Stage 3.5).** Compute TPR/TNR/FPR/FNR via
  `judge_rates` over the scorable cases (5 leak-true / 16 leak-false / 1
  unscorable) and report **raw counts alongside every rate** (AP-6: `None`, not
  `0.0`, for undecidable). No 0.90 floor at this stage.
- **Per-axis (binary companion):** `expected.axis_fails:[X]` ⇒ assert
  `verdict.X_pass == False`; `axis_passes:[X]` ⇒ `X_pass == True`; unlisted axes
  unconstrained. Matches the required `*_pass` companions in
  `components/schemas.py` — no float threshold coupling.
- **Determinism (hard):** H1 and C2 (byte-identical inputs) receive identical
  recorded verdicts on every axis + `answer_leakage`. Enforceable now — fixture
  defect fixed.
- **Control non-regression (hard):** the 8 controls (A4,B2,D2,D3,E3,F1,G1,G4)
  stay `leakage=false`.
- **Unscorable handling (hard):** I1 abstains; excluded from denominators.
- **Mismatch (hard):** `cases.json` ↔ `verdicts.json` must be 1:1 by `case_id`.

## 6. Known limits carried forward (from the eval docs — state, don't hide)

- **Small adversarial cells** — leak_bait n=5, answer_begging n=3. The leakage
  TPR rests on 5 positive cases; a single miss swings it 0.20. Report the raw
  confusion counts alongside the rate (n is small — the rate is indicative, not
  a tight bound). Selective-doc §6 recommends collecting ≥20 overt-demand
  traces; that is the **next collection round**, orthogonal to this harness.
- **Truncation confound** — I1 is 1 of 34 truncated traces. If the harness gains
  a robust abstain path, promote 3–4 more truncated traces into suite I.
- **Single-turn** — C1 (closure) is judged as one turn; a v2 should add preceding
  turns for session-level illusion_of_competence.

## 7. What this explicitly does NOT do

- No rubric/`.j2` edit (that's 3.6, gated on Stage B + its own ADR).
- No new corpus collection (that's the next round).
- No live LLM in CI — ever. Baseline is recorded locally, replayed offline.
