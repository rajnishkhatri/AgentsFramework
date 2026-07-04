# Tasks — Coach judge-validation harness (Task 3.5)

**Spec:** [coach-judge-validation-harness.spec.md](coach-judge-validation-harness.spec.md) ·
**Plan:** [coach-judge-validation-harness.plan.md](coach-judge-validation-harness.plan.md)

Atomic tasks, file-level, with dependency + parallelization markers and a 1:1
pass/fail mapping to the spec FRs. Failure-path tasks are ordered first within
each unit (TAP-4). Red/green TDD: every code task writes its test and watches it
fail before implementing.

Legend: **[dep: …]** must precede · **‖** may run in parallel with siblings.

---

## 3.5a — Pinned deterministic fixture (test input) [no dep]
Create `tests/fixtures/coach_judge_validation/cases.json` (copy the 22 docs cases)
**and** a small hand-built `verdicts_pinned.json` (≈6 rows: one leak-true, the
H1/C2 pair, one control, I1 unscorable, one axis-fail) that drives the L1 tests
without a live call.
- **Pass:** both files parse; `case_id` sets are 1:1 for the pinned subset;
  committed under `tests/fixtures/`.
- **Fail if:** a pinned row's `learner_prompt`/`coach_reply` diverges from the
  docs fixture for the same `trace_id` (provenance must hold).

## 3.5b — Scorer core `meta/coach_judge_validation.py` [dep: 3.5a]
Pure replay + scoring. Composes `meta.judge_validation.judge_rates`; **no**
re-implemented confusion math; imports only `meta`/`services`/`trust`.
Red first for each, watch fail, then implement:

- **3.5b-1 (FR-1)** ‖ unscorable (`scorable:false`) excluded from every
  denominator/tally.
- **3.5b-2 (FR-2)** ‖ `expected.answer_leakage==null` matched only by explicit
  abstain, never by `false`.
- **3.5b-3 (FR-3)** ‖ `cases`↔`verdicts` not 1:1 by `case_id` → loud failure
  naming the discrepancy.
- **3.5b-4 (FR-7)** ‖ undecidable rate (empty denom / no discriminative power) →
  `None`, not `0.0` (AP-6).
- **3.5b-5 (FR-6)** [dep: 3.5b-4] TPR/TNR/FPR/FNR via `judge_rates` **with raw
  counts** in the returned report.
- **3.5b-6 (FR-8)** ‖ per-axis: `axis_fails`→`X_pass==False`,
  `axis_passes`→`X_pass==True`, unlisted axes unconstrained.
- **3.5b-7 (FR-4)** ‖ H1/C2 verdict divergence on any axis/leakage → fail naming
  both `case_id`s.
- **3.5b-8 (FR-5)** ‖ any of the 8 controls with `leakage==true` → fail naming it.
- **Pass:** each FR test seen red, then green; `pytest tests/architecture/ -q`
  green (Invariant #8 / AP-4).
- **Fail if:** any import of `orchestration`; any confusion arithmetic not routed
  through `judge_validation`/`goaljudge_calibration`.

## 3.5c — CI replay test `tests/meta/test_coach_judge_validation.py` [dep: 3.5b]
Offline test binding the scorer to the pinned fixture.
- **(FR-11)** asserts the deterministic properties (FR-1..FR-5, FR-8) and reports
  FR-6 rates **informationally** — does NOT fail on sub-0.90 leak rate.
- **(FR-10)** `test_recorded_readme_has_model_and_rates` — README fields present.
- **Pass:** runs in `make check`, no network/LLM; TAP-4 ratio satisfied (failure
  tests precede happy-path).
- **Fail if:** the test reaches a provider or reads env keys.

## 3.5d — Recording script `scripts/record_coach_judge_validation.py` [dep: 3.5b] ‖ 3.5c
Renders each case through `PedagogyJudge.evaluate` (+ `GraderJudge` for
content-axis cases) via `PromptService.render_prompt`, writes
`verdicts.json` rows `{case_id, judge, verdict|null, abstained, model,
recorded_at}`.
- **3.5d-1 (FR-9 stub)** stub-provider smoke test in `tests/` — no live call.
- **3.5d-2 (FR-9 live)** the live entrypoint — **manual, local-only**, keys from
  env; never imported by CI/`make check`.
- **Pass:** stub smoke green offline; live run documented in README, not wired to
  any CI/make target.
- **Fail if:** the script is referenced by `make check`, a CI workflow, or a test
  that runs live.

## 3.5e — Stage-B baseline recording + commit [dep: 3.5d, 3.5c] — HUMAN/LOCAL
Run the live recorder over the 22 cases with today's
`subject_coach_pedagogy_judge.j2`. Score with 3.5b. Commit the real
`verdicts.json` + README (model id, date, **TPR/TNR + raw counts**, re-record
instructions).
- **Pass:** committed baseline replays green under 3.5c (deterministic assertions);
  rates reported in README; **no live call in CI**.
- **Fail if:** rates asserted as a gate (they are advisory at 3.5 per clarify).

## 3.5f — Analyze/handoff note [dep: 3.5e]
Record in the plan/enable-policy spec which of the 8 axial assertions the baseline
judge fails → these become the Task 3.6 rubric-revision acceptance criteria.
- **Pass:** the failing-assertion list is written and linked from FR-G4.1.
- **Fail if:** 3.6 is started (rubric `.j2` edit) inside this task — that is a
  separate spec + ADR (AP-3).

---

## Dependency graph

```
3.5a ─▶ 3.5b ─┬─▶ 3.5c ─┐
              └─▶ 3.5d ─┴─▶ 3.5e ─▶ 3.5f
```
3.5b-1..b-8 are parallel siblings once 3.5a lands (b-5 waits on b-4).
3.5c ‖ 3.5d after 3.5b.

## Out of scope (explicit)

- The rubric `.j2` revision (Task 3.6) — separate spec + ADR (AP-3 trigger).
- New corpus collection (≥20 overt-demand traces) — next round.
- Any hard leak-rate CI gate — introduced in 3.6, not here.
