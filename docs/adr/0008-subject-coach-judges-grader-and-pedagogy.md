---
type: decision-record
title: 'ADR-0008: Subject-Coach judges — Grader, Grader Judge, and Pedagogy GoalJudge'
status: accepted
created: 2026-06-30
updated: 2026-07-01
owner: Rajnish Khatri
related: subject-coach-agent.spec.md, subject-coach-agent.brainstorm.md, 0007-subject-coach-agent-tool-capability-gating.md, 0006-subject-coach-component-protocols.md, 0003-goaljudge-l2l3-readjudication-cascade.md, SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md
tags: [decision-record]
---

# ADR-0008: Subject-Coach judges — Grader, Grader Judge, and Pedagogy GoalJudge

**Status:** Accepted — 2026-07-01, **with conditions** (was Proposed — 2026-06-30).
Ratified in the detailed-component-design adjudication
([SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §7).

> **Acceptance conditions (2026-07-01) — ⏳ PENDING.** The three-judge design is ratified;
> two of its mitigations are prose, not yet mechanical, and MUST land **before the coach flag
> flips on** (before the answer-leakage flag is trusted in any gate):
> 1. **A stated, tracked κ TPR/TNR floor for the answer-leakage detector.** The brainstorm §3.3
>    warns "a bad judge propagates errors unless rubric-anchored, criterion-separated, **and
>    calibrated**." Until the Pedagogy judge's answer-leakage axis is calibrated against human
>    raters to a recorded TPR/TNR floor (reusing the ADR-0003 cascade + cert harness), its flag
>    is **not** trusted in a gate — the deterministic MC Grader + keyword fallback remain the CI
>    path.
> 2. **The `GoalJudge` `build_graph`-injection API change lands paired with the judge build.**
>    ADR-0008 makes the judge set injectable into `build_graph` (today it is constructed
>    internally). That API change MUST land **with** the two new judges, not drift ahead of or
>    behind them (mirrors ADR-0007's paired `build_graph` change).
>
> Until both land, treat the answer-leakage flag as **unvalidated**. The conditions gate the
> coach-flag flip, not the ratified design.
**Related:** [agent spec](../plan/subject-coach-agent.spec.md) · [agent brainstorm](../plan/subject-coach-agent.brainstorm.md) · [ADR-0006 Grader port](0006-subject-coach-component-protocols.md) · [ADR-0003 GoalJudge cascade](0003-goaljudge-l2l3-readjudication-cascade.md)
**Audience:** anyone building the coach's grading/evaluation, or reconsidering whether the existing GoalJudge can be retargeted to a teaching domain.

---

## Context

The coach has two things to grade: the **learner's answer** (is it correct?) and the
**coach's own dynamically generated content** (is the hint/explanation faithful, correct,
and pedagogically sound — and did it *avoid revealing the answer*?). The user asked,
correctly, whether the existing general-purpose `components/goal_judge.py::GoalJudge` can
serve, before adding new judges.

**Evaluation of the existing GoalJudge (from the English-coach angle):**
- It is a **goal-completion** judge — "did this run accomplish what the user asked,"
  reference-free over `final_answer` + trajectory. Its verdict schema (`goal_met`,
  `criteria_met`, `unmet_conditions`) has **no per-criterion axis and no answer-leakage
  axis**.
- Its **correctness cascade** (`verify_answer` owns `goal_met` when checkable, else the LLM
  rubric — the ADR-0003 pattern) is the *right shape*, but `verify_answer`
  (`components/answer_verifiers.py`) is bound to **generic** task constraints (topological
  sorts, etc.), not "is this the correct letter for an English MC item."
- **Conclusion:** it **cannot be retargeted to English grading or pedagogy by config
  alone.** A dedicated Grader and a dedicated Pedagogy judge are justified.

2026 tutoring research is unambiguous: (a) **answer-leakage is the #1 measured failure
mode** and must be a *penalized, first-class axis* (MathTutorBench, EduBench); (b)
correctness, pedagogical quality, and goal-completion are **distinct concerns** that should
be **separate, rubric-anchored, criterion-separated, calibrated** judges — and merely
splitting judges without rubrics doesn't help; (c) grammar/mechanics MC grading is
rule-bound and *most reliable as deterministic match*; (d) grading *generated* tutor content
is reference-free rubric grading on **faithfulness + correctness + justification +
actionability**, where LLM explanations are known to be weak on justification/subgoaling
(so those must be explicit rubric items). Sources in the [brainstorm](../plan/subject-coach-agent.brainstorm.md) §3.

---

## Decision

Ship **three judges, with maximal reuse of the GoalJudge shape and cascade pattern** — and
**keep** the general GoalJudge unchanged for session-goal completion.

| Judge | Verdict | Home | Built from |
|---|---|---|---|
| **MC Grader** | `correct: bool` (letter exact-match) | **Frontend** (client-side, offline) | the deterministic stage of ADR-0006's `Grader` port — no LLM |
| **Grader Judge** | per-criterion: `faithfulness, correctness, justification, actionability` | **Backend** (`components/`) | GoalJudge H1/H2 injectable shape + new `.j2`; grades the coach's **generated content** |
| **Pedagogy GoalJudge** | `mistake_identification, mistake_location, actionability, coherence` + **`answer_leakage` flag** | **Backend** (`components/`) | GoalJudge shape + new `.j2`; AI-tutor taxonomy dimensions |
| **general GoalJudge** | `goal_met` (session objective) | **Backend** | **reused as-is** |

**Home split** (matches ADR-0005 local-first): deterministic MC correctness runs
**client-side** (instant, offline); LLM grading (Grader Judge + Pedagogy) calls the
**backend** coach agent over the BFF. The frontend MC Grader **is** the deterministic stage
of ADR-0006's `Grader` port; the backend judges are the LLM stage behind it — together they
compose the port's `Verdict`.

The answer-leakage axis is **recorded distinctly, never averaged** into a single quality
score (a high-clarity hint that leaks the answer must still be flagged). All three LLM
judges are **flag-gated and mockable** (reusing `GoalJudgeRuntimeConfigReader`), so the CI
path stays the deterministic grader + keyword fallback — **no live LLM in CI**.

---

## Options considered & rejected

| Option | What | Why it lost |
|---|---|---|
| **Retarget the general GoalJudge** | Point its `.j2` + `verify_answer` at English grading | Its verdict schema has no correctness/leakage/per-criterion axis; `verify_answer` is bound to generic constraints. Config alone can't express "didn't reveal the answer." Rejected on capability, not cost. |
| **One mega-judge** (correctness + pedagogy + goal in one call) | A single rubric covering everything | Research warns this is exactly the failure: collapsed concerns hide answer-leakage behind clarity; criterion-separated rubrics are required. Rejected. |
| **LLM grader for MC correctness too** | Grade letter-match via the LLM | Wasteful and *introduces* leakage/latency risk where a deterministic check is more reliable (ICC research). MC correctness is deterministic by nature. Rejected. |
| **All grading on the backend** | Even letter-match calls the agent | Breaks ADR-0005's local-first offline posture for the one check that needs no model. Rejected. |
| **Three judges, split homes** *(chosen)* | Deterministic MC on frontend; LLM Grader Judge + Pedagogy on backend; GoalJudge reused | Each concern gets its own rubric; correctness stays deterministic + offline; leakage is first-class. |

---

## Rationale

The honest finding — the general GoalJudge *cannot* be retargeted — is what forces dedicated
judges; but reusing its injectable H1/H2 shape and the ADR-0003 cascade means we add
**rubrics, not machinery**. Separating correctness from pedagogy from goal-completion is the
research consensus, and it maps cleanly onto distinct verdict schemas the code can test
independently. Keeping MC correctness deterministic and client-side is both the most
*reliable* choice (rule-bound grading) and the one that honors the local-first split. Making
answer-leakage a distinct flag (not a sub-score) is the single most important design choice:
it is the failure the whole tutoring literature warns about, and averaging it away would
reproduce that failure.

The Grader Judge is what makes the LLM-rubric stage **non-speculative now**: the coach
generates dynamic content *every turn*, so there is an immediate consumer for reference-free
faithfulness/correctness grading — this is not a "someday free-response" abstraction.

---

## Consequences

**Commits us to:**
- New `GraderVerdict` / `PedagogyVerdict` types in `components/` (framework-agnostic; import
  only `services/` + `trust/`; no langgraph). **No `trust/models.py` change → no kernel
  re-sign.**
- New prompt templates `prompts/subject_coach_grader_judge.j2` and
  `prompts/subject_coach_pedagogy_judge.j2`.
- A **calibration obligation**: each LLM judge is calibrated against human raters with **κ**,
  reusing the GoalJudge calibration-cert harness and the ADR-0003 TPR/TNR-floor discipline —
  specifically, the answer-leakage detector must meet a stated TPR/TNR floor before its flag
  is trusted in the gate.
- Making `GoalJudge` (or the judge set) **injectable** into `build_graph` (today it is
  constructed internally) — a small recorded API change, paired with ADR-0007's `build_graph`
  changes.
- Frontend + backend each own part of ADR-0006's `Grader` port `Verdict` (the accepted cost
  of the local-first split).

**Accepted risks / mitigations:**
- *Judge propagates errors* (the research caution) → mitigated by criterion-separated rubrics
  + calibration floors + the deterministic MC grader owning correctness (the LLM never grades
  MC correctness).
- *Faithfulness false-negatives* (hallucinated explanation graded faithful) → mitigated by
  composing the judge with the redactor + deterministic checks and calibrating the
  faithfulness axis explicitly (weak-justification is a known LLM-explanation gap).
- *Two grader homes drift* → the frontend MC Grader and backend judges share ADR-0006's
  `Verdict` contract; a contract test keeps them aligned.

**Follow-on:** the LLM-rubric grader for **learner free-response essays** is deferred until
free-response items exist (the Grader Judge grades the *coach's* content now, not learner
essays). A second subject's judges are an extension (new `.j2` rubrics), zero engine edits.

---

## Supersedes / related

Makes canonical the agent [spec](../plan/subject-coach-agent.spec.md) §3.5 and the
[brainstorm](../plan/subject-coach-agent.brainstorm.md) §5. Pairs with
[ADR-0007](0007-subject-coach-agent-tool-capability-gating.md) (the agent that produces what
these judges grade) and extends [ADR-0006](0006-subject-coach-component-protocols.md)'s
`Grader` port. Reuses the cascade discipline of
[ADR-0003](0003-goaljudge-l2l3-readjudication-cascade.md). Supersedes nothing.
