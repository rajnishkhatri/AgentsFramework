---
type: decision-record
title: 'ADR-0020: Coach answer-leakage gate goes inline on the live path (off/shadow/enforce) — supersedes ADR-0009 with conditions'
status: proposed
created: 2026-07-06
updated: 2026-07-06
owner: Rajnish Khatri
related: coach-leakage-gate-rollout.spec.md, coach-leakage-gate-rollout.plan.md, 0009-subject-coach-reflexion-not-on-live-path.md, 0008-subject-coach-judges-grader-and-pedagogy.md, 0019-fireworks-host-adapter.md, 0005-reflections-task-id-guard-cross-turn-leak.md
tags: [decision-record]
---

# ADR-0020: Coach answer-leakage gate goes inline on the live path (off/shadow/enforce) — supersedes ADR-0009 with conditions

**Status:** Proposed — 2026-07-06. (Ratify at the tasks→implement human gate.)
**Related:** [Phase-5 spec](../plan/coach-leakage-gate-rollout.spec.md) ·
[Phase-5 plan](../plan/coach-leakage-gate-rollout.plan.md) ·
[ADR-0009 (superseded in part)](0009-subject-coach-reflexion-not-on-live-path.md) ·
[ADR-0019 (judge CERTIFIED)](0019-fireworks-host-adapter.md) ·
[ADR-0008 (the judges)](0008-subject-coach-judges-grader-and-pedagogy.md).
**Audience:** anyone touching the coach request path, the OFF-GRAPH judge
invariant (`tests/architecture/test_coach_judges_never_inline.py`), or tempted to
add a *second* inline judge binding.

---

## Context

Phase 3.9 certified the coach answer-leakage judge on `glm-5.2-fireworks`
(ADR-0019: TNR 1.0 / TPR 1.0 / κ pass, 0 FP, zero-flip). But the runtime flag
`coach_leakage_gate_enabled` is read by **nothing on the live request path** — its
only consumer is the offline `meta/subject_coach_judge_sampler.py`. To actually
*prevent* a leaking coach reply from reaching a learner, the certified judge must
run **inline**, on the coach turn, before the reply is emitted — and act on a
positive verdict.

That collides with **ADR-0009** (*Reflexion loop is offline-only for the
Subject-Coach*), enforced by `tests/architecture/test_coach_judges_never_inline.py`,
which forbids `orchestration/` and `middleware/` from importing the coach judges or
their config reader at all. The blocker surfaced during Stage-6 implementation, not
at plan time — the Stage-4 grounding confirmed the seam *existed* but did not grep
the architecture suite for a rule forbidding the move.

The tension is real and worth stating precisely: ADR-0009's own
rejected-alternatives reasoning names **answer-leakage** as a hazard of putting
judgment inline — because the judgment it had in mind was **T2 Reflexion**, which
*converges toward the correct answer* and would push a coach toward leaking. The
Phase-5 gate is the **opposite motion**: a leak-**safety** check that suppresses a
reply *because* it leaks. Same path, inverse intent.

---

## Decision

Ship the coach answer-leakage gate **inline** on the live coach turn, driven by a
3-mode config value `coach_leakage_gate_mode ∈ {off, shadow, enforce}` (reversible
per-deploy), and **supersede ADR-0009 *with conditions*** to permit it. The
OFF-GRAPH rule is **narrowed, not deleted**: the Reflexion / GoalJudge /
coach-judge-**sampler** inline path stays forbidden; the certified **leakage gate**
gets exactly **one named, declared** inline binding (the `evaluate_node`
OUTPUT_VALIDATION seam + its `components/coach_leakage_gate.py` adapter). The policy
is a pure `decide_leakage_enforcement`; enforce regenerates a flagged reply once,
then suppresses to a safe Socratic fallback; a judge outage fails **open** with a
loud carrier. Ships with `mode=off` in every environment.

---

## Options considered & rejected

| Option | Why rejected |
|---|---|
| **Delete `test_coach_judges_never_inline.py`** | Throws away the Reflexion/sampler OFF-GRAPH guard wholesale — the very protection that keeps a *convergence* loop off the coach path. The right move is to narrow the rule to one carve-out, keeping the ban on everything else. |
| **Enforce in `middleware/` instead of `orchestration/`** | The same arch test forbids `middleware/` too, so this needs the identical ADR + carve-out — same governance cost, different seam — while moving the judge *outside* the phase context where the reply, `trace_id`, and `black_box` recorder already live. No benefit, more plumbing. |
| **Shadow-only Phase 5; defer enforce indefinitely** | Defensible and smaller — shadow already runs offline in the sampler (ADR-0009-clean). But it drops the enforce goal the whole 3.9 cert was aimed at (a REFUSE→ENABLE journey to *act on* leaks), leaving a certified gate permanently dormant. Kept as the fallback if enforce ever proves too costly, not the plan. |
| **Keep ADR-0009 intact; do not supersede** | Impossible to also enforce inline — a direct contradiction. Pretending otherwise (e.g. a `# noqa`-style test bypass) would be a silent invariant breach, exactly what the ratchet exists to stop. |
| **Fail-closed on judge outage** | A judge availability blip would black out *all* coaching (deny-by-default on every turn). Rejected in the clarify pass: availability beats a rare leak during an outage, made loud + alertable via the `judge_unavailable` carrier. |

---

## Rationale

ADR-0009 defines a **reversal trigger** with three preconditions; superseding it is
legitimate only if all three are met. They are:

1. **(a) the `reflections` cross-turn leak is fixed** — done in ADR-0005
   (`efc1715`/`27f1490`), ADR-0009's own named prerequisite.
2. **(b) a coaching-specific critique replaces the task-failure critique** — the
   gate uses the ADR-0019-certified **answer-leakage** judge (leak-aware, coach
   pedagogy rubric), *not* the GoalJudge task-failure Reflexion critique that
   ADR-0009 declined.
3. **(c) a benchmark shows the intervention is warranted** — ADR-0009 framed this
   as "latency buys measurable learning gain"; the Phase-5 analog is a **safety
   guarantee**: the judge is certified TNR 1.0 / TPR 1.0 / 0 FP on the frozen
   split (ADR-0019), so the inline cost buys a measurable *leak-prevention*
   guarantee, not a speculative learning gain.

Because the gate's intent is the inverse of Reflexion's (prevent leakage vs.
converge toward the answer), superseding ADR-0009 does not reopen the hazard
ADR-0009 guarded against — it adds the mechanism that *closes* it. Keeping the
OFF-GRAPH ban on the sampler/Reflexion path means the one thing ADR-0009 truly
protected — no answer-converging loop on the coach turn — still holds.

---

## Consequences

- **A live LLM call joins the coach request path in `enforce`** — one judge call
  per coach turn, plus at most one regeneration on a flagged turn (rare — 0 FP
  certified). Mitigation: a pinned per-call timeout; fail-open on breach; the
  shadow stage measures real added latency before enforce is ever armed. `off`
  adds zero.
- **The OFF-GRAPH invariant is now a *narrowed* rule.** `test_coach_judges_never_inline.py`
  is reworked (red-first, `G8-OK: ADR-0020 supersedes ADR-0009`) to forbid every
  inline judge import EXCEPT the single declared leakage-gate binding, with a
  positive test that the carve-out is an explicit allowlist and a negative test
  that a *second* undeclared binding still fails. A future contributor adding an
  inline judge for any other purpose is stopped by the gate.
- **Config schema is additive** — `coach_leakage_gate_mode` defaults `off`,
  `schema_version` unchanged, backward-compatible under `extra="forbid"` (a legacy
  doc carrying only the deprecated bool still parses and derives its mode). Not a
  trust-kernel type → **no re-signing**.
- **Ships OFF.** `mode=off` in all environments; arming to `shadow`/`enforce` is a
  separate operational runbook after a shadow-observation window. The `arm()`
  guard refuses `shadow`/`enforce` below the ADR-0008 cond#1 cert floor, so a
  config typo can never enforce on an uncertified judge.
- **ADR-0009 is updated** to `status: superseded-in-part (by ADR-0020)` with a note
  that the OFF-GRAPH ban survives for Reflexion/sampler; the coach-leakage gate is
  the single sanctioned inline judge binding.

---

## Supersedes / related

**Supersedes ADR-0009 *in part / with conditions*** — narrows its OFF-GRAPH rule to
admit one declared leakage-gate binding; the Reflexion/sampler inline ban stands.
Builds on [ADR-0019](0019-fireworks-host-adapter.md) (the certified judge this gate
runs) and [ADR-0008](0008-subject-coach-judges-grader-and-pedagogy.md) (the judge
floor `arm()` guards). Realises Phase 5 of the
[Phase-5 spec/plan/tasks](../plan/coach-leakage-gate-rollout.spec.md). The
`reflections` fix it depends on is
[ADR-0005](0005-reflections-task-id-guard-cross-turn-leak.md).
