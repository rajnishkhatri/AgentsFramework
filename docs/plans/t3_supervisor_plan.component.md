---
type: plan
title: '`components/supervisor_plan.py` — the decompose-or-decline component (T3)'
description: 'Two functions, mirroring plan_builder''s build_plan_artifact_llm + validate_plan_mece split: one *produces*'
tags: [plan]
---

# `components/supervisor_plan.py` — the decompose-or-decline component (T3)

> **Scope.** Component-level spec for the single load-bearing vertical piece of T3 (§3.5a of
> [`planning_pipeline_tiered_loops.plan.md`](planning_pipeline_tiered_loops.plan.md)). It is the **fan-out
> decision**, extracted as a pure, framework-agnostic function — the same shape as `plan_builder`/`router`/
> `reflexion`. Everything LangGraph-shaped (the `Send` fan-out, the worker/join nodes) lives in orchestration and
> is *out of scope here*; this doc specifies only the decision the orchestration consumes.
>
> **Why this is the load-bearing piece.** The §3.5a acceptance bar is *seam + layer-clean + observable +
> MAST-bounded*, not throughput. The single highest-risk part of that bar is **deciding when N independent branches
> actually exist** — because the published evidence (GAIA single-agent-beats-multi-agent, §3.5a) says fanning out
> a *sequential-dependent* task is actively harmful. So the component's most important job is **declining**, and its
> failure-first test is "a dependent task is NOT fanned out."
>
> **Layer authority.** Pure `components/` (AGENTS.md AP-5/INV-6): no `langgraph`/`orchestration`/`AgentState`
> import; no I/O; the LLM (if used) is an injected callable, exactly like `build_plan_artifact_llm` and
> `generate_reflection`. Verified-against contracts: `PlanArtifact`/`PlanStep`
> ([`plan_builder.py:15-24`](../../components/plan_builder.py)) and `TaskToolInput`
> ([`task_tool.py:30-48`](../../services/tools/task_tool.py)).

---

## 1. Contract (signatures)

```python
# components/supervisor_plan.py
from __future__ import annotations
from typing import Callable, Literal
from pydantic import BaseModel, Field

FanoutDecision = Literal["fan_out", "decline"]

class Delegation(BaseModel):
    """One independent branch the supervisor wants to dispatch.

    Maps 1:1 onto the existing delegation envelope: these fields are exactly the
    TaskToolInput delegate-operation inputs (task_tool.py:30-48), so the worker
    node can hand a Delegation straight to the dispatcher with no translation.
    """
    branch_id: int                                    # contiguous from 1 (MECE check)
    objective: str = Field(min_length=1, max_length=400)   # == TaskToolInput.objective bound
    subagent_type: str = Field(min_length=1, max_length=80)
    constraints: list[str] = Field(default_factory=list)
    expected_output_schema: dict = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)    # branch_ids this needs FIRST (see §3)

class SupervisorPlan(BaseModel):
    decision: FanoutDecision
    branches: list[Delegation] = Field(default_factory=list)
    reason: str                                       # the carrier text (why fan-out / why decline)

def plan_delegations(
    *,
    task_input: str,
    plan_artifact: dict,                              # the T1 PlanArtifact.model_dump() (see §4)
    planning_depth: Literal["L0", "L1", "L2"],
    generate: Callable[[str], dict] | None = None,    # injected decompose-LLM; None => deterministic
) -> SupervisorPlan:
    ...

def validate_independence(plan: SupervisorPlan) -> bool:
    """True iff the fan-out branches are genuinely independent (no depends_on edges
    among the fanned-out set). The MECE/independence gate the node trusts."""
    ...
```

Two functions, mirroring `plan_builder`'s `build_plan_artifact_llm` + `validate_plan_mece` split: one *produces*
the decision (LLM-or-floor), one *validates* its independence (pure predicate, CI-deterministic). The node calls
`plan_delegations`, then **must** pass the result through `validate_independence` before fanning out — the same
"generate then validate then floor" discipline T1 already uses.

## 2. The decompose-or-decline logic (priority order, failure-first)

The function is **biased to decline** — declining is the safe direction (the §3.5a GAIA guard; the cost asymmetry
mirrors §5 MAST: a missed fan-out is cheaper than a wrong fan-out). Order, first match wins:

| # | Condition | Decision | Reason tag |
|---|---|---|---|
| 1 | `planning_depth == "L0"` OR the T1 plan has `< 2` ordered steps | **decline** | `single-step` — nothing to parallelize; the §3.5a "<3 items, don't bother" rule at its floor |
| 2 | the T1 plan's steps are **sequentially dependent** (deterministic signal: step goals reference prior outputs — "use the result", "based on the above", "then", "the previous"; or the branches share a write target) | **decline** | `sequential-dependent` — the GAIA single-agent-wins case; the gather-then-compare shape from §2.3 |
| 3 | `generate is None` (no decompose-LLM injected) | **decline** | `no-generator` — the deterministic floor never *invents* parallelism; absent a model it stays single-thread (safe) |
| 4 | LLM proposes branches BUT `validate_independence` is False (it emitted `depends_on` edges, or duplicate objectives) | **decline** | `not-independent` — trust the structure check over the model's optimism |
| 5 | LLM proposes `>= 2` genuinely independent branches | **fan_out** | `independent-branches` |

**Failure paths first (TAP-4 / §7.5):** conditions 1–4 are all *rejections*. They are written and tested **before**
condition 5 (the only acceptance). A component that fans out by default is the dangerous one — so the default
return, on every path that isn't an explicit, validated, multi-branch independent plan, is `decline`.

**Deterministic floor (condition 3) is the safety net, identical to T1's pattern.** `build_plan_artifact_llm`
falls back to the deterministic `build_plan_artifact` on any generation failure. Here the floor is even simpler:
**absent a decompose-LLM (or on any parse/validate failure), the safe floor is `decline`** — single-threaded T0/T1
execution, which already works. T3 can only ever *add* parallelism on an explicit, validated, model-proposed,
independence-checked plan; it can never silently fan out.

## 3. Why `depends_on` is the crux signal

The whole GAIA finding reduces to one structural question: **do the branches have edges between them?**
- *Independent* (`depends_on == []` for all): "summarize doc A", "summarize doc B", "summarize doc C" → fan out,
  join synthesizes. Real parallelism, real latency win.
- *Dependent* (`depends_on` non-empty): "benchmark Redis", "benchmark Memcached", "**using those numbers**,
  recommend one" → the third branch needs the first two. This is the §2.3 gather-then-compare shape. Fanning it out
  is the GAIA failure: the dependent branch runs on missing/guessed inputs → information loss → wrong answer.

`validate_independence` returns False if **any** fanned-out branch has a non-empty `depends_on`. The node trusts
that predicate, not the LLM's enthusiasm — the same "structure check overrides model optimism" rule as
`validate_plan_mece`. A dependent plan is *not* an error; it's a correct `decline` → the task runs as a normal T1
sequential plan. (A future T3.1 could run *waves* — fan out the independent prefix, then the dependent tail — but
that is explicitly deferred; v1 fan-out is all-independent-or-decline, the simplest provably-safe shape.)

## 3a. The deterministic dependency signal (condition 2, no LLM)

> **This is the one open design question before build** (corpus plan §10.1). It is the predicate behind condition 2:
> *given the existing T1 plan, are its steps sequentially dependent?* It runs on the **common path** (every task),
> so it must be **deterministic, cheap, and CI-testable** — no LLM. It is the gate that makes a `decline` free
> (§4): conditions 1 and 2 classify the existing plan with zero extra model call.

### Design principle: reuse T1's sequencing detector, inverted

The repo **already has** a high-precision sequencing detector, used for the *opposite* purpose. In the router,
`and then` / `, then` / `, and` *promote* depth — more sequencing means a deeper plan
([`router.py:224-227`](../../components/router.py), `sequenced-multistep` floor). `plan_builder` uses the same
markers (`_CONJUNCTION_CLAUSE`, `_COMMA_THEN_AND` at [`plan_builder.py:46-55`](../../components/plan_builder.py)) to
split a task into ordered branches. **T3 inverts the exact same signal:** the markers that say "these are ordered
steps" are precisely the markers that say "these steps are *dependent* → do not parallelize → decline." We do not
invent a new lexical vocabulary; we reuse the one the router/builder already trust, with the sign flipped.

This is the load-bearing reuse: a marker set that's been live-validated for depth promotion is, by construction,
already tuned for *high precision on sequencing* — and high precision is exactly what condition 2 needs (a
false-positive dependency is a *missed fan-out*, the cheap error; we tolerate those).

### The signal has two parts — lexical AND structural

```python
def detect_sequential_dependence(plan_artifact: dict) -> bool:
    """True iff the T1 plan's steps are sequentially dependent (→ decline).
    Pure, deterministic, no LLM. Two independent OR'd signals; either ⇒ dependent."""
```

**Signal 1 — back-reference markers (a later step refers to an earlier step's output).** Scan each step's `goal`
(from step 2 onward) for the reference phrases. These are the §3 "using those numbers" shape made lexical:

| Marker class | Examples | Why it's a dependency |
|---|---|---|
| explicit sequencing | `then`, `and then`, `next`, `after that`, `once …` | the router's own `sequenced-multistep` markers — ordering = dependency |
| result back-reference | `use the result`, `using those`, `based on`, `from the above`, `the previous`, `that file`, `it` (anaphora to a prior artifact) | step N consumes step <N's output |
| conditional gating | `if … then`, `if eligible`, `if green`, `otherwise` | step N is *gated on* step <N's outcome (the Tau²-style `decline-policy-dependent` row) |

**Signal 2 — shared write target (two steps write the same artifact).** Extract path-like / artifact tokens
(`/workspace/…`, a filename, a named report) from each step's `goal`; if **two or more steps write the same
target**, they are not independent even with zero back-reference words — concurrent writes race
(`INVALID_CONCURRENT_GRAPH_UPDATE` at the graph level; a real file clobber at the tool level). This is the
`decline-shared-write` corpus row, and it's the case pure back-reference scanning would *miss* — which is exactly
why it's a separate signal, not an afterthought.

`detect_sequential_dependence` returns `True` (→ decline) if **either** signal fires. Biased to decline (§2): a
borderline plan is held single-threaded, the safe direction.

### Why lexical-on-the-plan, not lexical-on-the-raw-prompt

The detector reads the **T1 `PlanArtifact.ordered_steps`**, not the raw `task_input`. T1 already did the hard work
of splitting the prompt into ordered steps (`_extract_branches`); running the dependency scan over *those* steps —
rather than re-parsing the prompt — means (a) we inherit T1's segmentation for free, (b) the back-reference scan is
naturally *inter-step* (does step 2's goal point back at step 1?), which is the real question, and (c) the
shared-write check is a simple cross-step set-intersection over already-isolated step goals. Re-parsing the prompt
would re-derive segmentation T1 already owns — a layer violation in spirit (two planners) and a duplication in
fact.

### The honest limit (and why it's acceptable)

A lexical detector **will miss semantic dependencies with no surface marker** — "compute the budget; staff the
project" reads as two independent imperatives but the second silently needs the first. This is a *false-negative*:
the detector says independent, the LLM may then propose a fan-out, and `validate_independence` (§3) is the second
gate — but if the LLM *also* emits no `depends_on` edge, a semantically-dependent task could fan out. That is the
residual risk, and it is **acceptable for v1 by the cost asymmetry** (§2): the detector + `validate_independence`
catch every *surface*-marked and *structurally*-marked dependency; the uncaught case is a rare unmarked semantic
chain, and even then the task still *runs* (each branch executes; the join synthesizes) — it just runs as a
possibly-degraded fan-out rather than a clean sequence. The corpus's near-miss ⚠️ rows are deliberately
**surface-or-structurally marked** (they're catchable), and a future T3.1 could add an LLM dependency-classifier as
a *third* gate if the calibration run shows the lexical detector's false-negative rate is material. We do not add
it speculatively.

### Co-design with the corpus (the binding)

The corpus plan's near-miss ⚠️ decline rows **are the test set for this detector**, and each is built to trip a
*named* signal — so the two are co-designed, not independently guessed:

| Corpus row (§4.2) | Trips signal | Marker / target |
|---|---|---|
| `decline-trip-dated-01` | 1 (back-ref) | "around the flight dates", "for the hotel stay" |
| `decline-benchmark-then-tune-03` | 1 (back-ref) | "then use those numbers" |
| `decline-fetch-then-transform-04` | 1 (explicit seq) | "then … then" |
| `decline-shared-write-05` | **2 (shared write)** | all three write `/workspace/report.md` |
| `decline-policy-dependent-10` | 1 (conditional) | "if eligible, then …" |
| `decline-pick-then-act-06` | 1 (back-ref) | "that flight" (anaphora) |

If a ⚠️ row does *not* trip any signal during the calibration run, that's a detector gap to close **before**
gating — surfaced by the `fp` cell of the fan-out confusion matrix (corpus plan §7). The detector and the corpus
are validated against each other.

### Test matrix (extends §5, failure-first)

| Test | Pattern | Asserts |
|---|---|---|
| `back-ref "then" → dependent` | C1 deterministic | signal 1, explicit sequencing |
| `"use the result" → dependent` | C1 deterministic | signal 1, result back-reference |
| `"if eligible, then" → dependent` | C1 deterministic | signal 1, conditional gating |
| **`two steps write same path → dependent`** | C1 deterministic | signal 2 — the case signal 1 misses, written prominently |
| `three independent summaries → NOT dependent` | C1 deterministic | the true negative (must not over-fire) |
| `unmarked semantic chain → NOT dependent (documented FN)` | C1 deterministic | pins the known limit as a *recorded* false-negative, not a silent surprise |
| anaphora `"that file" → dependent` | P1 property | signal 1 anaphora class |

The headline is **`two steps write same path → dependent`** — the structural signal — because it's the one a
naive "just scan for 'then'" implementation would miss, and it's a live corpus row.

## 4. Where the inputs come from (binding to T1)

`plan_delegations` does **not** re-decompose from scratch — it reads the **T1 `PlanArtifact` that already exists**.
T1 (shipped) builds/memoizes `plan_artifact` in `route_node` ([`react_loop.py:815-881`](../../orchestration/react_loop.py)).
The supervisor's job is **not** "what are the steps" (T1 answered that) but "are these steps *independent enough to
parallelize*". So:
- `task_input` + `plan_artifact` (the T1 steps) + `planning_depth` are the inputs — all already in `AgentState`.
- The supervisor reuses T1's decomposition and only *classifies* it. This keeps T3 additive over T1, never a
  competing planner, and means a `decline` is free (zero extra LLM call on the common path — conditions 1/2 are
  deterministic over the existing plan).

## 5. Test matrix (Protocol C, failure-first)

| Test | Layer / pattern | Asserts |
|---|---|---|
| `L0 task → decline` | C1 deterministic | condition 1, no LLM |
| `single-step L1 plan → decline` | C1 deterministic | condition 1 boundary |
| **`dependent multi-step plan → decline`** (the headline) | C1 deterministic | condition 2 — the GAIA guard, written FIRST |
| `no generator injected → decline` | C1 deterministic | condition 3 floor |
| `LLM proposes branches w/ depends_on → decline` | C1 + mocked LLM (P6) | condition 4, `validate_independence` overrides the model |
| `LLM proposes 3 independent branches → fan_out` | C1 + mocked LLM (P6) | condition 5 — the ONE acceptance, written LAST |
| `validate_independence` property test | P1 property-based | any non-empty `depends_on` in a fanned set ⇒ False; empty ⇒ True |
| dependency-rule test | P7 (architecture) | no `langgraph`/`orchestration`/`AgentState` import |

Never a live LLM in CI (AGENTS.md / §7.5); the decompose-LLM is `TestModel`/`FunctionModel`-mocked. The headline
is the **dependent-plan decline** — it is the test that encodes the GAIA finding as a guard.
