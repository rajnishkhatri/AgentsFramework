# Spec — Coach judge-validation harness (Task 3.5)

**Status:** Draft — 2026-07-04
**Owner:** Rajnish Khatri
**Related:** [coach-judge-validation-harness.plan.md](coach-judge-validation-harness.plan.md) ·
[coach-goldset-enable-policy.spec.md](coach-goldset-enable-policy.spec.md) (FR-G3.1/FR-G4.1) ·
fixtures [docs/evals/eng-coach/judge_test_cases.jsonl](../evals/eng-coach/judge_test_cases.jsonl) ·
precedents `meta/judge_validation.py`, `tests/fixtures/code_reviewer/wi8_validation/`.

---

## 1. Goal

Turn the 22 axial-derived judge fixtures into a committed **record-once /
replay-in-CI** harness that measures how the coach judges (`PedagogyJudge`,
`GraderJudge`) score against human-coded ground truth — reporting `answer_leakage`
TPR/TNR (with raw counts), per-axis agreement, input-determinism, and
control non-regression. Stage 3.5 **measures**; it does not yet gate on the leak
rate (n=5 positives is too thin) — the failing assertions become the acceptance
criteria for the Task 3.6 rubric revision.

## 2. Context

Task 3.4 produced `judge_test_cases.jsonl` (22 cases, provenance-verified verbatim
against `coded.jsonl`; the H1≡C2 determinism defect was fixed 2026-07-04). The
fixtures target `components/subject_coach_judges.py`, which already exists and is
unit-tested for parse/fail-open safety — but nothing replays fixtures against
`expected` verdicts. The judge is an LLM, so any real evaluation is a live call:
this harness records that call **locally**, commits the output, and replays it
**offline in CI** (the GoalJudge/WI-8 pattern) so the constitution's
no-live-LLM-in-CI rule holds. The core axial finding — leakage is entirely
indirect (0/200 direct), so a form-keyed judge likely misses it — is exactly what
the baseline must quantify before the rubric is touched.

## 3. Functional requirements (EARS)

**Failure paths first.**

- **FR-1.** IF a fixture case has `scorable == false` (e.g. truncated I1) THEN the
  scorer SHALL exclude it from every leakage denominator and per-axis tally, and
  SHALL NOT synthesize a verdict for it.
- **FR-2.** IF a case's `expected.answer_leakage` is `null` THEN the scorer SHALL
  count it matched ONLY by an explicit abstain/unscorable judge output, never by a
  `false` verdict (a leak detector that fails open is a defect — mirrors the
  existing `subject_coach_judges` "never repair to answer_leakage=False" rule).
- **FR-3.** IF the committed `verdicts.json` is missing, malformed, or its case set
  does not match `cases.json` 1:1 (by `case_id`) THEN the replay test SHALL fail
  with a message naming the discrepancy, never silently score a subset.
- **FR-4.** IF `verdicts.json` gives the two byte-identical-input cases (H1, C2)
  different verdicts on any axis or on `answer_leakage` THEN the determinism check
  SHALL fail, naming both `case_id`s (the judge noise-floor sensor).
- **FR-5.** IF any of the 8 control cases (A4, B2, D2, D3, E3, F1, G1, G4) has a
  recorded `answer_leakage == true` THEN the control-regression check SHALL fail,
  naming the regressed control.
- **FR-6.** THE scorer SHALL compute `answer_leakage` TPR/TNR/FPR/FNR over the
  scorable cases via `meta.judge_validation.judge_rates` (composing the
  `goaljudge_calibration` confusion primitives — never re-implemented) AND SHALL
  report the raw confusion counts (tp, fp, tn, fn) alongside every rate.
- **FR-7.** WHERE a rate has an empty denominator or zero discriminative power THE
  scorer SHALL return `None` for that rate, never a fabricated `0.0` (AP-6).
- **FR-8.** THE per-axis check SHALL, for each case's `expected.axis_fails`, assert
  the judge's `<axis>_pass == False`, and for each `expected.axis_passes`, assert
  `<axis>_pass == True`; axes listed in neither SHALL be left unconstrained.
- **FR-9.** WHEN the recording script runs THE SYSTEM SHALL render each case
  through `PedagogyJudge.evaluate` (and `GraderJudge` where the case exercises
  content axes) exactly as production renders (`PromptService.render_prompt`, same
  `mode`), and write one verdict row per `case_id` to `verdicts.json`.
- **FR-10.** THE committed `verdicts.json` README SHALL record the model id, the
  run date, and the achieved TPR/TNR + raw counts, with re-record instructions
  (WI-8 README shape).
- **FR-11.** THE CI replay test SHALL assert FR-1..FR-5 and FR-8 (deterministic,
  offline) and SHALL report FR-6 rates as informational — it SHALL NOT fail on
  `answer_leakage` TPR/TNR below any threshold at Stage 3.5 (advisory-baseline
  decision; the leak-rate gate is deferred to Task 3.6 once the corpus grows).

## 4. Data model / contracts

- **`cases.json`** — the 22 fixtures, committed under
  `tests/fixtures/coach_judge_validation/` (copied from the docs fixture; the docs
  copy stays the analytic source). Each row: `case_id, suite, trace_id, mode,
  stratum, question_id, learner_prompt, coach_reply, open_codes, expected{...}`.
- **`verdicts.json`** — recorded output, one row per `case_id`:
  `{case_id, judge, verdict: <PedagogyVerdict|GraderVerdict|null>, abstained: bool,
  model, recorded_at}`. `verdict:null` + `abstained:true` is the unscorable path.
- **Axis mapping (resolved in clarify):** the fixture's boolean `axis_fails` /
  `axis_passes` map to the verdict's REQUIRED binary `*_pass` companions
  (`PedagogyVerdict.<axis>_pass`, `components/schemas.py`), NOT to the 0..1 float
  — no threshold coupling.
- No trust-kernel type is added or changed (no re-signing).

## 5. Invariants & security boundaries

- **Invariant #8 / AP-4 (meta):** `meta/coach_judge_validation.py` imports only
  `meta` / `services` / `trust` — never `orchestration`. Pure scoring, no graph
  call. `tests/architecture/` enforces.
- **No live LLM in CI (🚫 Never):** the only live call is the local Stage-B
  recording script; CI replays the committed `verdicts.json` offline. The spec
  states this in §7 and the recording script is the single seam that touches a
  provider.
- **No new confusion math (meta convention):** rates come from
  `judge_validation.judge_rates`; AP-6 `None`-not-`0.0` for undecidable rates.
- **Prompts (AP-3):** the recording script renders via
  `PromptService.render_prompt` (`PedagogyJudge` already does) — no hardcoded
  judge prompt string.

## 6. Edge cases

- **Unscorable (truncation):** I1 — excluded from denominators (FR-1), not guessed.
- **Judge returns `None`** (provider error / prose non-JSON): recorded as
  `abstained:true`; a case whose `expected` is a real verdict but whose recording
  abstained counts as a miss for that case's constraints, surfaced not hidden.
- **Small positive cell:** 5 leak-true cases — rates reported with raw counts so a
  single FN is visible as `fn=1`, not laundered into a rate (FR-6).
- **`cases.json` ↔ `verdicts.json` drift** after a re-record that changes the case
  set: FR-3 hard-fails on the 1:1 mismatch.
- **Duplicate `case_id`** in either file: parse-time error, never last-wins.

## 7. Non-functional requirements

- **Determinism:** the CI replay test is L1/L2 deterministic — pure functions over
  committed JSON, no LLM, no network. Runs in `make check`.
- **Live path off the hot path:** the recording script (live LLM) runs on demand
  locally only; keys from env; never invoked by CI or `make check`.
- **Cost/latency:** one judge call per applicable case (~22–30 calls) per
  re-record — bounded, occasional, human-triggered.
- **Reversibility:** re-recording is idempotent per `case_id`; committing a new
  `verdicts.json` is the only state change and is a normal reviewable diff.

## 8. Test plan

Failure-path tests before happy-path.

| FR | Test | Layer | In `make check`? |
|----|------|-------|------------------|
| FR-1 | `tests/meta/test_coach_judge_validation.py::test_unscorable_excluded_from_denominators` | L1 | yes |
| FR-2 | `::test_null_expected_matched_only_by_abstain` | L1 | yes |
| FR-3 | `::test_verdicts_cases_mismatch_fails_loud` | L1 | yes |
| FR-4 | `::test_h1_c2_determinism_divergence_fails` | L1 | yes |
| FR-5 | `::test_control_leakage_regression_fails` | L1 | yes |
| FR-6 | `::test_leakage_rates_report_raw_counts` | L1 | yes |
| FR-7 | `::test_undecidable_rate_is_none_not_zero` | L1 | yes |
| FR-8 | `::test_axis_fail_maps_to_pass_false` / `::test_axis_pass_maps_to_pass_true` | L1 | yes |
| FR-9 | `scripts/record_coach_judge_validation.py` — smoke via a stub provider in test; **live run is manual** | L2 (stub) / live (manual) | stub yes / live no |
| FR-10 | README presence + fields asserted by `::test_recorded_readme_has_model_and_rates` | L1 | yes |
| FR-11 | `::test_ci_replay_does_not_gate_on_leak_rate` (asserts the advisory posture) | L1 | yes |

The committed `verdicts.json` for FR-1..FR-8 in `make check` is a **small pinned
fixture** (hand-built rows incl. one leak, the H1/C2 pair, one control, I1) so the
deterministic tests never need a live call. The **real** baseline `verdicts.json`
(Stage B) is recorded separately and replayed by the same scorer; its rates are
reported, not gated (FR-11).

## 9. Definition of Done

- [ ] FR-1..FR-11 implemented; each has a passing test *seen to fail first*.
- [ ] `make check` green; `pytest tests/architecture/ -q` green (Invariant #8 held).
- [ ] `meta/coach_judge_validation.py` imports no `orchestration`; scoring composes
      `judge_validation.judge_rates` (no re-implemented confusion math).
- [ ] Stage-B baseline recorded locally, `verdicts.json` + README committed with
      model id / date / rates + raw counts; **no live call in CI**.
- [ ] No ADR trigger fired for the harness (scorer is same-class as the GoalJudge
      validator; no new dep/service/node/abstraction). The Task 3.6 rubric `.j2`
      revision — which WILL trigger AP-3/ADR — is out of scope here.
- [ ] Actual command output pasted (not summarized) for every verification claim.
