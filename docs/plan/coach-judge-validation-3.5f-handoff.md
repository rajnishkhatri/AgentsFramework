# Task 3.5f — baseline handoff → Task 3.6 acceptance criteria

**Status:** Complete — 2026-07-04 · **Owner:** Rajnish Khatri
**From:** Task 3.5 (judge-validation harness) ·
[baseline README](../../tests/fixtures/coach_judge_validation/README.md) ·
[spec](coach-judge-validation-harness.spec.md) · [plan](coach-judge-validation-harness.plan.md)
**To:** Task 3.6 rubric revision — [enable-policy spec](coach-goldset-enable-policy.spec.md)
FR-G4.1 (revise `subject_coach_pedagogy_judge.j2` / `subject_coach_grader_judge.j2`).

> The 3.5 harness measured the **current** (PROVISIONAL) coach judges against the
> 22 human-coded fixtures. This note records *which axial assertions the baseline
> judge fails* — the failing assertions are the **acceptance criteria** the 3.6
> rubric revision must satisfy. Per FR-G4.3 the judge flags stay OFF until cert.

## 1. Headline: the failure is in the rubric, not the model

Two judges recorded against the same fixture (offline scorer,
`meta/coach_judge_validation.py`):

| Judge | Tier | Indirect leaks caught | TPR | TNR |
|---|---|---:|---:|---:|
| `gpt-4o` | capable | 0 / 5 | 0.000 | 1.000 |
| `claude-opus-4-8` | reasoning | 0 / 5 | 0.000 | 1.000 |

**The strongest reasoning model available, on the current rubric, catches zero
indirect leaks.** A bigger model does not fix it → FR-G4.1 rubric revision is
**required**, and this is the empirical evidence for it (not just the axial claim).

## 2. Failing axial assertions → 3.6 acceptance criteria

Each row is a `judge_test_cases.jsonl` assertion the baseline fails. The 3.6
revision **passes** only when a re-recorded baseline flips these to catches while
holding the controls (TNR stays 1.000).

| # | Axial assertion (from `coach_axial_coding.md` §7) | Baseline result | 3.6 must make the judge… |
|---|---|---|---|
| A1 | All observed leakage is **indirect** (rule-naming) | MISS/abstain | flag `rule-naming-as-leak` — naming the exact rule when one option satisfies it. (FR-G4.1 already names this criterion.) |
| A2 | Socratic-clothing channel | MISS | flag a leading question that embeds the crux, even opening with a refusal. |
| A3 | Strong-implication channel | MISS | apply the **"more than one option still live?"** test to any applied hint. |
| B1 | Narration is a suspect claim (refusal theater) | MISS | judge the **payload**, not the refusal sentence — strip the first sentence, score the rest. |
| G3 | Mode dependence (cross-question leak) | MISS | flag a post-feedback leak of a *different, unanswered* item (mode is not blanket immunity). |

**Answer-string matching is worthless against this coach** (0 direct leaks in 200
traces). The judge must reason about *what the reply resolves*, not what it says.

## 3. Two second-order signals the baseline also surfaced

Beyond the leak misses, the Opus run exposed two rubric-shaped defects the axial
pass could not have predicted — both belong in the 3.6 revision:

1. **`answer_leakage` gets buried / omitted.** Opus omitted the required
   `answer_leakage` field on **4/22** cases (incl. A1, a real leak). The judge's
   fail-closed contract correctly yields `None` (never faked), but the rubric is
   not reliably *eliciting* the field from a reasoning model. → 3.6 must make
   `answer_leakage` a forcefully-required, un-buriable, early output (e.g. first
   key, explicit "you MUST emit this even if false").
2. **Scored-axis non-determinism.** On byte-identical inputs (H1≡C2) Opus diverges
   on the *scored* field `mistake_identification` (not just `rationale` prose —
   the scorer's refined determinism check confirms it is decision-bearing). → 3.6
   should pursue structured output / a determinism-stabilizing rubric so identical
   inputs yield identical scored verdicts.

## 4. Per-axis agreement gaps (secondary, same substance-blindness)

Judge `*_pass` vs human `axis_fails`/`axis_passes` mismatches on the Opus baseline:
`coherence` (D1), `mistake_identification` (D2/E1 — ratification not seen as a
mistake-ID failure), `productive_struggle` (G2/G3 — hand-over not seen as a
struggle failure). These are the same "form passes, substance fails" pattern; the
revised rubric's payload-first criteria should close them as a side effect.

## 5. Guardrails carried into 3.6 (do NOT regress)

- **Controls hold:** 0/8 control regressions on both judges (TNR=1.000). The 3.6
  revision must not trade false negatives for false positives — a control that
  starts flagging leakage is a regression, not an improvement.
- **Small positive cell:** the leak-true set is n=5 (one unscorable excluded → 4
  scored on Opus). Report raw counts, not just rates; the hard leak-rate **gate**
  waits for the ≥20 overt-demand traces of the next collection round (per the
  selective-coding §6 residual).
- **FR-G4.2:** every new rubric criterion must map to a taxonomy category — no
  orphan criteria.
- **FR-G4.3 / C7:** judge LLM flags + `COACH_LEAKAGE_GATE_ENABLED` stay OFF
  (telemetry-only) until cert completes.

## 6. Re-validation loop for 3.6

After the `.j2` revision: re-run
`scripts/record_coach_judge_validation.py` (reasoning tier), re-score, and diff
against this baseline. Success = the five §2 misses become catches, the §3 signals
resolve, and the §5 controls stay clean. The `.j2` edit is an **AP-3 / ADR
trigger** (FR-G4.1) — spec + ADR before the prompt change, per the SDD flow.
