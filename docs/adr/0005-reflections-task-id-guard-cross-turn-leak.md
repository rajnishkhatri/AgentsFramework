---
type: decision-record
title: 'ADR-0005: Scope the reflexion `reflections` channel per task_id (cross-turn leak)'
status: accepted
created: 2026-06-30
updated: 2026-06-30
owner: Rajnish Khatri
tags: [decision-record, orchestration, reflexion, state]
---

# ADR-0005: Scope the reflexion `reflections` channel per task_id (cross-turn leak)

**Status:** Accepted — 2026-06-30.
**Related:** the Subject-Coach reflexion-not-on-live-path ruling (`reflexion_enabled`
default `False`); `orchestration/state.py` (`reflections`), `orchestration/react_loop.py`
(`call_llm_node`, `reflect_node`, `_escalation_carrier`, `_should_continue_or_escalate`),
`components/reflexion.py` (`reflections_for_task`), `services/base_config.py`
(`reflexion_enabled`).
**Audience:** anyone touching the T2 reflexion loop, AgentState reducers, or the chat
checkpointer lifecycle before changing how critiques accumulate.

---

## Context

`reflections` (`orchestration/state.py`) is the T2 reflexion "semantic gradient"
(Reflexion, arxiv 2303.11366): an **append-only** state channel of verbal critiques.
It uses the plain `_append_list` reducer with **no `task_id` guard** — unlike every
other memoized per-task artifact in state (`planning_depth_task_id`,
`task_understanding_task_id`, `recalled_memories_task_id`, `plan_artifact_task_id`),
each of which regenerates when `task_id` changes.

The two clocks diverge: `task_id` is **minted fresh per invocation**, while the
LangGraph checkpointer `thread_id` is **reused across chat turns**. Because the reducer
is append-only, a prior turn's critique physically persists in `state["reflections"]`
into the next turn — a checkpoint reload appends, it never resets. Both consumers leak:

1. **Prompt injection** — `call_llm_node` folded `state["reflections"]` into the system
   prompt under a bare `if reflections:` with no `task_id` filter, so Turn N's failure
   critique steered Turn N+1's answer. For a tutoring/chat agent each new question
   inherited the previous question's "you failed because…" critique.
2. **Budget counter** — `len(reflections)` is the reflexion attempt counter checked
   against `max_reflexion_attempts` in three places (`_escalation_carrier`,
   `reflect_node`, `_should_continue_or_escalate`). A leaked prior-turn entry
   pre-consumes the budget, so Turn N+1 reflects fewer times (or not at all) than its
   own failures warrant.

This is latent on the live path — `reflexion_enabled` defaults `False`
(`services/base_config.py`), the standing reason T2 reflexion is not yet on the
Subject-Coach live path — but it is a real correctness bug for any chat deployment that
flips reflexion on.

---

## Decision

Tag each reflexion entry with the `task_id` it was recorded under (in `reflect_node`),
and read **every** consumer through a new pure filter
`components.reflexion.reflections_for_task(reflections, task_id)` that returns only the
entries for the current task. Same memoize-on-`task_id` discipline as
`planning_depth_task_id`, expressed per-entry.

---

## Options considered & rejected

| Option | Why rejected |
|--------|--------------|
| **Reset `reflections` to `[]` on a new `task_id`** (mirror `planning_depth` last-write-wins) | The reducer is **append-only**: writing `[]` is a no-op append, not a replace. Concurrent reflexion laps in one superstep also need accumulation. Swapping the reducer to last-write-wins would break the within-turn gradient and the `len()`-as-counter contract. |
| **Filter only the prompt injection site (`call_llm_node`)** | Closes the visible leak but leaves the budget counter inflated by foreign turns — the loop would still under-reflect on the new task. The bug has two faces; one filter must cover both. |
| **Key reflexion state on `task_id` instead of `thread_id`** | Would require a second checkpoint namespace and diverge from the rest of AgentState, which is uniformly thread-scoped. Heavy; the per-entry tag is local and matches the existing memoize idiom. |
| **Inline the filter as a lambda at each site** | Four copies of the same predicate drift apart (G8 risk). One pure component function is testable in isolation (OBP-2) and keeps the nodes thin (AP-5). |

---

## Rationale

The chosen fix is the smallest change that closes **both** faces of the leak while
honoring the append-only reducer the within-turn gradient depends on. A per-entry
`task_id` tag is exactly the memoize-on-`task_id` pattern the four sibling artifacts
already use — only relocated from a sibling scalar key (impossible here) into the entry
itself, because append-only state cannot carry a last-write-wins reset. Centralizing the
predicate in `components/reflexion.py` keeps orchestration nodes thin (AP-5) and the
logic CI-pure (no `AgentState`, no live LLM), so the contract is provable in L1.

**Matching rule: strict equality on the recorded `task_id`.** Only an entry whose
recorded `task_id` equals the current one is kept. *Both* a prior turn's entry (a
different, non-empty `task_id` — the leak) *and* an **untagged** entry (no recorded
`task_id`) are excluded.

Untagged entries are excluded **deliberately**. A first cut after review tried the
opposite — keep untagged entries as the current task's, a "one-deploy grace" so a resumed
pre-fix run kept its gradient. That was unsound: the filter runs on *every* read and never
prunes the append-only channel, so a surviving untagged entry would be re-attributed to
the current task on *every* subsequent turn forever — a **permanent** cross-turn leak (and
permanent budget pre-consumption), not a one-deploy grace. Strict exclusion costs only a
*bounded* one-time loss: a pre-fix in-flight run resumed mid-reflexion loses its
accumulated gradient that once. `reflect_node` stamps a **non-empty** id on every write
(`task_id or workflow_id`, the same identity fallback the memory-store seam uses at
`react_loop.py:3890`), so no NEW entry is ever untagged, and the bounded cost cannot recur.

That `task_id or workflow_id` fallback is the second half of the fix — without it a turn
entered with an empty `task_id` would write entries tagged `""`, which no reader could
attribute, pinning the attempt counter at 0 and **bypassing the budget ceiling**. Read and
write share one scope via the orchestration helper `_task_reflections(state)`, so the two
can never disagree.

---

## Consequences

- **New constraint:** every future reader of `state["reflections"]` MUST go through the
  orchestration helper `_task_reflections(state)` (which wraps the pure
  `components.reflexion.reflections_for_task` with the `task_id or workflow_id` scope). A
  raw `state.get("reflections")` read at a consumer site reintroduces the leak. The
  `state.py` docstring records this; the L1 tests in `tests/components/test_reflexion.py`
  and the orchestration regression tests in `tests/orchestration/test_react_loop.py` pin
  the contract. This is convention, not mechanism — the unbounded-growth follow-on below
  notes a task-aware reducer would make it unbypassable.
- **Accepted risk (bounded one-time loss):** entries written before this change carry no
  `task_id` and are excluded by the strict-equality rule. A pre-fix in-flight run resumed
  mid-reflexion therefore loses its accumulated gradient and starts its budget fresh — a
  *bounded, one-time* cost. The alternative (keep untagged) was rejected: filter-at-read
  never prunes, so an untagged entry would leak into every future turn permanently (see the
  Matching-rule section). The bounded loss cannot recur because `reflect_node` now always
  stamps a non-empty id.
- **Within-turn behavior unchanged:** entries sharing the current `task_id` are kept in
  append order, so the per-turn gradient and `len()`-as-attempt-counter are byte-identical
  for a single turn.
- **Accepted risk (unbounded growth):** filter-at-read never prunes foreign-task entries,
  so over a long reused-thread chat the stored `reflections` list grows without bound (the
  reducer only appends). Negligible while reflexion is off and per-turn lists are tiny
  (bounded by `max_reflexion_attempts`), but a precondition to revisit at live-path
  promotion — the deeper fix is a task-aware reducer that drops foreign-task entries on
  append, which would also make the read-filter contract unbypassable.
- **Follow-on:** when reflexion is promoted to the live path (lifting the Subject-Coach
  not-on-live-path ruling), this guard is a precondition — re-run the two-turn cross-turn
  test against the live config, and resolve the unbounded-growth note above.

---

## Supersedes / related

- Records the accepted-risk prerequisite behind the Subject-Coach
  reflexion-not-on-live-path ruling (`reflexion_enabled` default `False` in
  `services/base_config.py`): this guard must be in place before that ruling is lifted.
- Mirrors the memoize-on-`task_id` discipline of `planning_depth_task_id` /
  `task_understanding_task_id` / `recalled_memories_task_id` in `orchestration/state.py`.
