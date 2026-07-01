---
type: decision-record
title: 'ADR-0009: Reflexion loop is offline-only for the Subject-Coach (not on the live conversational path)'
status: accepted
created: 2026-06-30
updated: 2026-07-01
owner: Rajnish Khatri
related: subject-coach-agent.spec.md, subject-coach-agent.brainstorm.md, 0007-subject-coach-agent-tool-capability-gating.md, 0008-subject-coach-judges-grader-and-pedagogy.md, 0005-reflections-task-id-guard-cross-turn-leak.md, planning_pipeline_tiered_loops.design.md
tags: [decision-record]
---

# ADR-0009: Reflexion loop is offline-only for the Subject-Coach (not on the live conversational path)

**Status:** Accepted — 2026-07-01 (was Proposed — 2026-06-30). Ratified in the
detailed-component-design adjudication
([SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md](../Architectures/SUBJECT_COACH_DETAILED_COMPONENT_DESIGN.md) §7);
the one hard prerequisite (the `reflections` cross-turn leak) was satisfied ahead of
ratification by [ADR-0005-reflections](0005-reflections-task-id-guard-cross-turn-leak.md)
(`efc1715`/`27f1490`).
**Related:** [agent spec](../plan/subject-coach-agent.spec.md) · [agent brainstorm](../plan/subject-coach-agent.brainstorm.md) · [ADR-0008 judges](0008-subject-coach-judges-grader-and-pedagogy.md) · [tiered-loops T2 design](../plans/planning_pipeline_tiered_loops.design.md)
**Audience:** anyone tempted to set `reflexion_enabled=True` for a conversational/coaching agent, or reconsidering where self-reflection belongs in a tutoring loop.

---

## Context

A coach↔student conversation is inherently multi-turn, which raises an obvious question:
should we enable the pipeline's existing **T2 Reflexion** self-critique loop for the
Subject-Coach so it improves each turn before replying?

**What T2 Reflexion actually is (verified in the live code):** a **per-task retry
mechanism within a single run**, not a conversational mechanism.
- `reflect_node` (`orchestration/react_loop.py:3247`) fires when the **GoalJudge** verdict is
  `failed`/`partial` (or on `prose_repeat` thrash), generates a one-shot critique via a
  fast-tier LLM call, and **re-runs the same task** (`reflect → route → call_llm →
  execute_tool → evaluate`) up to `max_reflexion_attempts` (default **2**).
- The critique is folded into the **system prompt** of the retry
  (`react_loop.py:2038–2049`), not the message history.
- It is **gated OFF by default** (`AgentConfig.reflexion_enabled = False`,
  `services/base_config.py:99`; env `REFLEXION_ENABLED`) and has **no quality benchmark** —
  the tiered-loops design ships it dark, pending evidence.
- Each iteration adds **~2–3 LLM calls**; worst case 4–6 per turn.

This shape is the canonical Reflexion pattern (Actor → Evaluator → Self-Reflector), whose
proof points are **objective, checkable, single-task** problems (e.g. HumanEval code-gen).

---

## Decision

**Do not enable the inline T2 Reflexion retry loop for the Subject-Coach.** For the coach,
reflection lives in the **offline judge layer** (the Pedagogy GoalJudge of ADR-0008 already
*is* reflection-on-the-coach's-turn) and in **offline content-improvement**, never on the
live conversational hot path.

**General principle this rests on:** inline Reflexion is for **checkable, single-task runs**
where a wrong answer is costly and there is an objective failure signal to retry against — it
is **not** for **conversational turns**, where the student's next message *is* the natural
evaluation loop and the latency/cost of an inline retry is not justified.

---

## Options considered & rejected

| Option | What | Why it lost |
|---|---|---|
| **Enable T2 for the coach as-is** | `reflexion_enabled=True` on the coach `AgentConfig` | (1) **Wrong trigger** — T2 retries on a *task-failure* verdict; a coaching turn has no such verdict to silently re-attempt (the student's reply is the loop). (2) **Fights the pedagogy** — Reflexion converges toward *the correct answer*, the exact opposite of scaffolding; it would push the model toward **answer-leakage** (the #1 failure ADR-0008 penalizes). (3) **Cost** — 2–3× LLM calls/turn on a latency-sensitive chat UX, with **no measured gain**. (4) **Live bug** — `reflections` has no `task_id` guard, so a prior turn's critique leaks into the next turn (see Consequences). Rejected on four independent grounds. |
| **Enable T2 but fix the leak + add a coaching critique prompt** | Re-target the critique to pedagogy and guard per-turn | Still pays the latency tax and still inverts the scaffolding intent; the offline Pedagogy judge gets the same signal without the hot-path cost. Rejected as effort for a worse place to put reflection. |
| **Offline-only reflection** *(chosen)* | Reflection lives in the Pedagogy/Grader judges (ADR-0008) + offline content-improvement, T2 OFF for the coach | Keeps the live turn fast and scaffolding-faithful; puts self-critique exactly where it helps (grading + generation), reusing judges we are already building. |

---

## Rationale

The 2026 reflection literature gives a sharp decision rule that this case fails cleanly:
*"skip reflection when the task is a quick conversational reply or latency-sensitive… if you
can evaluate and retry in seconds, a loop is overkill"* — and reserves the pattern for
*"code generation and research"* with an objective failure check. A Socratic coaching turn
is the textbook "weak fit."

More importantly, the **pedagogy inverts the mechanism.** Feynman (teach-it-simply, surface
the gap), Oakley (active recall over re-explaining; productive desirable difficulty), and
Holt (productive struggle, learner autonomy, anti-coercion) all say the coach should *let the
student do the work* and resist rescuing. Reflexion's whole purpose is to *rescue the
agent's own answer faster*. Bolting it onto a coach optimizes for the one behavior the design
forbids (answer-leakage). The right home for "did this turn coach well?" is the **offline
Pedagogy judge**, which critiques without retrying inline.

Finally, T2 has **no evidence base** even for tasks (shipped dark, no corpus result), so
enabling it for an unproven, ill-fitting use case is speculative complexity — against the
repo's "build on the second consumer / demand evidence" discipline.

---

## Consequences

**Commits us to:**
- The coach `AgentConfig` keeps `reflexion_enabled = False`. The agent spec (§9) lists T2 as
  explicitly out of scope for the live loop.
- Reflection capability for the coach is delivered by the **Pedagogy GoalJudge + Grader
  Judge** (ADR-0008) and offline content-improvement — not new machinery.

**Prerequisite — the `reflections` cross-turn leak — ✅ MET (2026-07-01).** The exploration
found `reflections` (`orchestration/state.py:144–151`) used a plain `_append_list` reducer with
**no `task_id` guard** — unlike every other memoized artifact (`planning_depth_task_id`,
`task_understanding_task_id`, …). On a reused chat `thread_id`, a prior turn's failed-reflexion
critique would still be in state and re-injected into the next turn's system prompt
(`react_loop.py:2039`, which checked `if reflections:` without filtering by `task_id`). This
was a latent bug affecting **any** chat use of the pipeline with reflexion enabled — not just
the coach, and **a hard prerequisite for ever enabling T2 in a conversational context.** It is
now **fixed**: [ADR-0005-reflections](0005-reflections-task-id-guard-cross-turn-leak.md)
(`efc1715`/`27f1490`) tags each `reflections` entry with its `task_id` and filters every
consumer through the pure `components.reflexion.reflections_for_task(reflections, task_id)`
(red/green: a component L1 test + a two-turn `call_llm_node` integration test). So the leak that
would have forced this ADR to "Accepted with conditions" is closed; the coach still keeps
`reflexion_enabled = False` (this ADR), so the fix is latent on the live path until reflexion is
ever promoted.

**Reversal trigger:** if a future need for inline coach-turn reflection appears (e.g. a
non-Socratic "drill" mode where converging on the answer *is* the goal), reconsider — but only
after (a) the `reflections` leak is fixed (**now done — `efc1715`/`27f1490`**), (b) a
coaching-specific critique prompt replaces the task-failure critique, and (c) a benchmark shows
the latency buys measurable learning gain.

---

## Supersedes / related

Settles the agent [brainstorm](../plan/subject-coach-agent.brainstorm.md)'s reflexion
question and the agent [spec](../plan/subject-coach-agent.spec.md) §9 out-of-scope line.
Pairs with [ADR-0008](0008-subject-coach-judges-grader-and-pedagogy.md) (the offline judges
that are the coach's real reflection layer). References the
[tiered-loops T2 design](../plans/planning_pipeline_tiered_loops.design.md) (the mechanism it
declines to enable here). Supersedes nothing.
