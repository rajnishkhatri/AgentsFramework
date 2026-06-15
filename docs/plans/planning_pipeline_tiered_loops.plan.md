# Planning Pipeline — Tiered Reasoning Loops (ReAct → Plan-Execute → Reflexion)

> **⚠️ Status (updated 2026-06-15): Phases 0–3 are BUILT, committed, and live-validated.** This was
> authored as a plan-only doc; it is now also the design-of-record for shipped code. The as-built reconciliation
> is in **§0 (Implementation status)** — read it first; it supersedes the future-tense framing in §3/§7 below.
> The supervisor tier (T3) is the only tier with **no source written**, but it is no longer a blank — it was
> **un-deferred 2026-06-15** (§3.5a) and is now **design-complete**: the component contract
> ([`t3_supervisor_plan.component.md`](t3_supervisor_plan.component.md)), the design-doc diagrams + protocol
> crosswalk (design §B.5), and the validation corpus ([`t3_fanout_corpus.plan.md`](t3_fanout_corpus.plan.md),
> **built**: 29 `phase="fanout"` rows in `build_planning_stress_corpus.py`) all exist. What remains is the build
> itself (the nodes + the analyzer `fanout` branch).
>
> **Deliverable (original intent).** Implementation **plan** for a redesign of the planning pipeline from the
> current single flat ReAct loop into a **complexity-routed tier ladder**
> (T0 ReAct → T1 Plan-and-Execute → T2 Reflexion) on the **existing LangGraph stack**, plus the prerequisite
> fix to the planning-depth collapse. The supervisor / parallel-subagent tier (T3) was originally **scoped out**
> on the §2.3 corpus evidence, but has since been **un-deferred to de-risk the seam** (§3.5a) — design-complete,
> not yet built.
>
> **Date:** 2026-06-14 (T3 un-deferred 2026-06-15). **Scope:** the planning + routing + loop topology in
> `orchestration/react_loop.py`, `components/router.py`, `components/plan_builder.py`, **plus the T3 supervisor /
> fan-out tier (§3.5a, design-complete)**. **Out of scope:** any new framework (we keep LangGraph), the
> governance pillars themselves (they wrap new nodes unchanged).
>
> **Companions:** [`planning_pipeline_tiered_loops.design.md`](planning_pipeline_tiered_loops.design.md) pins the
> protocols (*how*); [`planning_pipeline_tiered_loops.impl.md`](planning_pipeline_tiered_loops.impl.md) is the
> file-level build doc (*what file / function / line / test*; resolves §6's D1/D2 + design's D3 to concrete
> values).
>
> **Grounding.** Current-impl claims (§1) were read from source, not assumed. The depth-collapse evidence
> (§2.1) and parallelism finding (§2.3) come from running the real task corpus
> (`cache/goaljudge_eval/depth_strata_corpus.jsonl`, `tests/fixtures/deep_agent_*`). The routing and
> escalation trade-offs (§4, §5) are grounded in 2026 literature cited inline.
>
> **Layering authority:** [`AGENTS.md`](../../AGENTS.md) — topology-only in `orchestration/`, framework-agnostic
> logic in `components/`/`services/`; prompts via `PromptService`; never run a live LLM in CI.
> **Related memory:** `planning-pipeline-redesign-brainstorm`, `planning-depth-underplans`,
> `goaljudge-task-understanding-gate`.

---

## Table of contents

- [1. Current implementation (ground truth)](#1-current-implementation-ground-truth)
- [2. The three problems, with evidence](#2-the-three-problems-with-evidence)
- [3. Target architecture — the tier ladder](#3-target-architecture--the-tier-ladder)
  - [3.4 Reflexion decoupling — onion-architecture separation of concerns](#34-reflexion-decoupling--onion-architecture-separation-of-concerns)
  - [3.5 Supervisor tier (T3) — pre-binding (historical; superseded by §3.5a)](#35-supervisor-tier-t3--pre-binding-historical-superseded-by-35a)
  - [3.5a Supervisor tier (T3) — as-built design (2026-06-15: un-deferred to de-risk the seam)](#35a-supervisor-tier-t3--as-built-design-2026-06-15-un-deferred-to-de-risk-the-seam)
  - [3.6 Frontend / middleware connection seam — the new tiers must not cross it](#36-frontend--middleware-connection-seam--the-new-tiers-must-not-cross-it)
  - [3.7 Governance-triangle conformance — every new fact needs a verified carrier](#37-governance-triangle-conformance--every-new-fact-needs-a-verified-carrier)
- [4. Routing design (hybrid cascade)](#4-routing-design-hybrid-cascade)
- [5. Escalation triggers](#5-escalation-triggers)
- [6. Open decisions (decide via trade-off before build)](#6-open-decisions-decide-via-trade-off-before-build)
- [7. Phased rollout](#7-phased-rollout)
  - [7.5 TDD methodology — how each phase is built](#75-tdd-methodology--how-each-phase-is-built)
- [8. Eval & acceptance](#8-eval--acceptance)
- [9. Risks](#9-risks)

---

## 0. Implementation status (as-built reconciliation, 2026-06-15)

Phases 0–3 are committed. This section reconciles each planned artifact against the shipped source so the
future-tense prose in §3/§7 reads as the *rationale* for code that now exists, not as pending work. Verified by
reading source at the cited lines, not assumed.

**Commits (in order):** `baf19aa` depth-collapse fix (Phase 0) → `97fd4d0` T1 plan-and-execute → `bfeaea8`
T2 reflexion → `9ff81f4` Phase 3 `decide_escalation` predicate → `0047c8e` Step-0 trace carriers + stress
corpus + e2e profiles.

| Planned (this doc) | As-built | Status |
|---|---|---|
| **Phase 0** — fix `task_tool_results_count → L0` collapse + flattener | `select_planning_depth` ([`router.py:97`](../../components/router.py)) keeps the post-tool-synthesis early-return but adds 4 reason-tagged L1 floors (strong-intent-verb, long-task-floor, sequenced-multistep) + an L2 incident-narrative promotion; depth memoized per-task on `planning_depth_task_id` ([`state.py:103-112`](../../orchestration/state.py)) so it no longer flips to L0 after the first tool call | ✅ **shipped + live-validated** (depth 0.917, §8.1) |
| **Phase 1** — `planner_node` (LLM plan, deterministic floor fallback) + `replan` back-edge | No separate node — folded into `route_node` ([`react_loop.py:815-881`](../../orchestration/react_loop.py)): `build_plan_artifact_llm` parse/validate/floor in `components/`; new `components/plan_generator.py` is the LLM boundary; `plan_source` config gates `deterministic`/`shadow`/`generated`; replan = `plan_is_stale` → **deterministic** rebuild (not LLM re-plan) + `replan_count++` | ✅ **shipped** (replan 0.900) — *deviation:* no standalone `planner_node`; replan rebuilds via the floor, not the LLM |
| **Phase 2** — `reflect_node` re-entering on GoalJudge failed/partial; D1 ceiling | `components/reflexion.py` = pure `generate_reflection` + `decide_reentry`; `reflect_node` ([`react_loop.py:1987`](../../orchestration/react_loop.py)) is a thin wrapper appending to `reflections` ([`state.py:134`](../../orchestration/state.py)); critique folded into prompt in `call_llm_node` ([`react_loop.py:1231`](../../orchestration/react_loop.py)); `reflect → route` re-entry edge ([`react_loop.py:2168`](../../orchestration/react_loop.py)) | ✅ **shipped** (reflexion 0.800) |
| **Phase 3** — hybrid escalation routing | `decide_escalation` ([`router.py:235`](../../components/router.py)) — pure predicate, budget-first, primary=verdict (via `decide_reentry`), tertiary=`prose_repeat`; gathered (not decided) in `_should_continue_or_escalate` ([`react_loop.py:2056`](../../orchestration/react_loop.py)) | ✅ **shipped** (escalation precision 1.000 / recall 0.800, §8.1) |
| **D1 — reflexion budget ceiling** | Resolved to **fixed `max_reflexion_attempts` config** (the most-tunable option); `len(reflections)` is the attempt counter (no separate counter to drift) | ✅ decided + built |
| **D2 — entry LLM-nudge scope** | **Not built** — entry stays heuristic-only (`select_planning_depth`); all routing intelligence is on the evidence-grounded escalation edge per §4 | ⏸️ deferred (open) |
| Runtime flags | `REFLEXION_ENABLED` / `PLANNING_PLAN_SOURCE` / `MAX_REFLEXION_ATTEMPTS` → `AgentConfig.reflexion_enabled` / `.plan_source` / `.max_reflexion_attempts` | ✅ flag-gated (steady-state parity when off) |

**Two deviations worth naming for the T3 design** (both deliberate, both reduce blast radius):
1. **No `planner_node`; the plan lives in `route_node`.** The plan is built/reused/replanned inline and memoized
   on `plan_artifact_task_id`. This is *cheaper* (no extra node, no extra edge) but means there is no single node
   a future supervisor could swap — T3 will add its own `supervisor_node` (§3.5) rather than wrapping a planner.
2. **Replan rebuilds with the deterministic floor, not the LLM.** `plan_is_stale` → `build_plan_artifact` (not
   `build_plan_artifact_llm`). The comment ([`react_loop.py:845`](../../orchestration/react_loop.py)) is explicit:
   the LLM re-plan would re-incur cost and the floor is the safe brittle-plan backstop. **Consequence:** a replan
   currently *narrows* (re-decomposes deterministically), it does not re-reason. CE-2 (§8.1) — the garbage-input
   miss — partly follows from this: a junk input that never surfaced as a failed tool result never trips the gate,
   and even if it did, the deterministic rebuild would not "understand" the junk. A future enhancement (not
   scheduled) would be an LLM re-plan on the *stale* path; it inherits the same cost/floor trade-off as Phase 1.

**Validation status:** all four seams measured live against the loops-on `stress` Cloud Run revision; numbers in
§8.1. Re-scoring the same Langfuse traces is **deterministic** (the trace-ids in `ui_batch.jsonl` are fixed) and
reproduced bit-for-bit on 2026-06-15 — the §8.1 "jitter ±a case" caveat applies to re-*running* the batch, not
re-*scoring* it. The governance-trace-audit gate (§3.7/§8) has **not** yet been run against a from-step-0 trace
for these phases — it remains an open acceptance item.

---

## 1. Current implementation (ground truth)

> **Note (2026-06-15):** §1 describes the *pre-Phase-0* baseline — the problem state the redesign fixed. It is
> retained as the motivating ground truth. For what runs *today*, see §0.

What "L0/L1/L2" actually is today — read from source:

- **There is no planning loop.** `select_planning_depth` ([`components/router.py:72`](../../components/router.py)) is a
  **deterministic lexical heuristic** (word-count buckets + marker keywords + regex). `build_plan_artifact`
  ([`components/plan_builder.py:171`](../../components/plan_builder.py)) then **regex-splits** the prompt into
  subtask strings and caps step count at `{L0:1, L1:3, L2:5}`. The plan is **never LLM-generated or revised**.
- **Depth has almost no teeth.** It selects **one sentence** of system-prompt addendum
  (`build_planning_instructions`, [`plan_builder.py:256`](../../components/plan_builder.py)) plus the step cap.
  The model is free to ignore it.
- **The only loop is flat ReAct**: `route → call_llm → execute_tool → evaluate → route`
  ([`react_loop.py:1797-1833`](../../orchestration/react_loop.py)). The plan is fingerprinted
  (`compute_plan_fingerprint`) and **frozen** — never replanned against tool output.
- **A second loop skeleton already exists but is unwired**: `StructuredReasoning/orchestration/pyramid_loop.py`
  (decompose/hypothesize/act/synthesize). Evidence the repo already wants structured reasoning.
- **`reasoning_recap`** ([`react_loop.py:387`](../../orchestration/react_loop.py)) is a **post-hoc UI summary**,
  not load-bearing reflexion — it never re-enters the loop.

## 2. The three problems, with evidence

### 2.1 Depth collapses to L0 (the prerequisite bug)
`select_planning_depth` returns `L0` whenever `task_tool_results_count > 0` ([`router.py:91`](../../components/router.py)),
and an upstream flattener collapses depth before the scorer (see `planning-depth-underplans` memory).
**Corpus proof:** in `cache/goaljudge_eval/depth_strata_corpus.jsonl`, **14 of 17 tasks have intended depth
(`want`) ≠ fired depth (`depth`), every mismatch flattened to L0, every plan capped at 1 step** — including
"Plan the Postgres migration", "Design a rate limiter", "Audit the deployment architecture, design…". The
planning signal is destroyed before it is used. **Nothing built on top matters until this is fixed.**

### 2.2 The plan is non-agentic and frozen
Even when depth is right, the "plan" is a regex split, and it is never revised after seeing tool output. The
2026 plan-and-execute literature names this the **"brittle plan"** failure — a planner that commits before any
tool result, so a surprising result leaves subsequent steps already wrong
([LangChain Plan-and-Execute](https://www.langchain.com/blog/planning-agents)). The fix is a **replan gate**.

### 2.3 No escalation path — but T3 isn't the answer here
Reflexion (self-critique re-entering the loop) is genuinely missing. A **supervisor / parallel-subagent** tier
is *not* warranted for this workload: across the depth-strata + `deep_agent` fixtures (26 unique tasks),
**~18 are simple, ~5 are sequential-dependent, and the ~3 "parallel"-looking ones are all gather-then-compare
("Compare Redis and Memcached, benchmark…, recommend") — i.e. sequential synthesis, not independent fan-out.**
Genuinely parallelizable branches are essentially absent. Adding a supervisor would buy the
[MAST](https://arxiv.org/abs/2503.13657) failure surface (41–86.7% multi-agent failure; 79% from
inter-agent misalignment + verification gaps) for tasks that don't need it. **T3 was deferred on this evidence —**
**and this finding still holds.** It was later **un-deferred (2026-06-15, §3.5a) to de-risk the seam, *not*
because the workload changed**: the acceptance bar is therefore seam-and-safety, never throughput (the GAIA
single-agent-wins guard *is* this section's finding, encoded as the fan-out corpus's decline rows, §8.2).

## 3. Target architecture — the tier ladder

One **complexity-routed strategy selector** over the existing `StateGraph`. Each tier is extra nodes +
conditional edges; no new framework.

| Tier | Strategy | Trigger | New machinery |
|---|---|---|---|
| **T0** | ReAct (today's loop) | simple / post-tool synthesis | none |
| **T1** | **Plan-and-Execute** + replan gate | multi-step, single-thread | LLM `planner_node`; `replan` back-edge on surprising tool output |
| **T2** | **Reflexion** wrapper | T1 verification failed, budget left | `reflect_node` writing verbal critique to a `reflections` state key, re-enters `route` |
| **T3** 🔮 | **Supervisor + parallel fan-out** | un-deferred 2026-06-15 (§3.5a) to de-risk the seam; design-complete, **not built** | `supervisor_node` → `Send` fan-out → `worker_node` → `join_node` over existing `services/tools/task_tool.py` + `delegation_dispatcher.py` |

Design anchors, each tied to existing code:

1. **LLM planner replaces the regex, deterministic floor stays.** Add `planner_node` for T1+ producing the
   `PlanArtifact`; keep `derive_success_conditions` ([`plan_builder.py:206`](../../components/plan_builder.py))
   as the fallback when generation fails — the **exact shadow/generated/deterministic pattern already proven for
   `TaskUnderstanding`** ([`react_loop.py:801-866`](../../orchestration/react_loop.py)).
2. **Reflexion is load-bearing, not cosmetic — and decoupled from the ReAct loop.** Distinct from
   `reasoning_recap`: it turns the GoalJudge `unmet_conditions` into a verbal critique (Reflexion's
   "semantic gradient", [arxiv 2303.11366](https://arxiv.org/abs/2303.11366)). The decoupling discipline is in
   §3.4 — the reflexion *generator* is a pure component that knows nothing about LangGraph or the ReAct loop; the
   thin `reflect_node` wrapper and the re-entry edge are the *only* parts that touch the graph.
3. **Governance pillars wrap new nodes unchanged.** BlackBox / AgentFacts / GuardRails / PhaseLogger wrap
   `planner_node`/`reflect_node` the same way they wrap existing nodes — which also keeps MAST-style
   "lost context / skipped verification" observable.

### 3.4 Reflexion decoupling — onion-architecture separation of concerns

The single most important structural rule for T2: **Reflexion is a vertical component that produces a value; the
ReAct loop is orchestration topology that consumes it. The two never reach into each other.** This is the onion
rule from [`FOUR_LAYER_ARCHITECTURE.md`](../Architectures/FOUR_LAYER_ARCHITECTURE.md) (dependencies point inward;
orchestration is topology-only) applied to a control loop. The existing graph already honours it —
[`react_loop.py:1`](../../orchestration/react_loop.py) states *"Every node function is a thin wrapper that
delegates to framework-agnostic logic in components/ and services/"*, and `evaluate_node` delegates to
[`components/evaluator.py`](../../components/evaluator.py). Reflexion follows the same shape; the trap is that
"re-enter the loop" tempts control flow *into* the reflexion logic, which would weld it to LangGraph.

**The boundary, stated as four hard rules:**

| Concern | Where it lives | Layer | Must NOT |
|---|---|---|---|
| **Reflexion generation** — `unmet_conditions` → verbal critique | new `components/reflexion.py` (`generate_reflection(...)`) | Vertical component | import `langgraph`, `orchestration.*`, or `AgentState`; decide whether to loop; mutate state |
| **Re-entry decision** — "reflect again, or stop?" | a pure predicate in `components/reflexion.py` returning an enum (`reflect` \| `stop`) over plain inputs | Vertical component | read `AgentState` directly — it takes scalars (attempt count, budget, last verdict) as args |
| **`reflect_node` wrapper** — adapt state ↔ component, call generator | [`react_loop.py`](../../orchestration/react_loop.py) | Orchestration | contain any reflexion *logic*; it unpacks state, calls the component, returns a state delta — nothing more |
| **Re-entry edge** — wire the predicate's enum to `route` vs `END` | `add_conditional_edges` in the graph builder | Orchestration | live anywhere but the topology section |

**Why a pure generator + pure predicate (not a `ReflexionLoop` class that drives itself):** if the component owns
the loop, it owns the graph, and you can no longer (a) unit-test reflexion without spinning a LangGraph runtime,
(b) swap the topology (e.g. cap attempts, reorder the escalation cascade) without editing component code, or
(c) reuse the same critique generator from the `StructuredReasoning/` pyramid loop. Keeping generation and the
*decision* pure — and the *wiring* in topology — preserves all three. It mirrors the architecture doc's PEP/PDP
rule exactly ([lines 654-675](../Architectures/FOUR_LAYER_ARCHITECTURE.md)): the orchestrator composes; the
component returns a decision as data and never reaches outward.

**State, not call-stack, carries the critique.** The reflexion output lands in a new `reflections` state key
([`orchestration/state.py`](../../orchestration/state.py)), append-only via the existing `operator.add` /
`_append_list` reducer convention, so prior critiques survive a checkpoint reload and accumulate as the semantic
gradient. `route_node` reads `reflections` on re-entry and folds the latest critique into the system prompt via
`PromptService` — the same memoize-on-`task_id` discipline already used for `task_understanding`
([state.py:87-99](../../orchestration/state.py)). The loop is closed through **shared state**, never through the
component calling back into the loop.

**Graph topology delta (the entire orchestration-side change for T2):** today the `done` branch goes
`evaluate → reasoning_recap → END` ([react_loop.py:1828-1833](../../orchestration/react_loop.py)). T2 inserts
`reflect` on that branch *behind the escalation predicate*: `evaluate →[verdict failed/partial & budget left]→
reflect → route` (re-enter), else `→ reasoning_recap → END` (unchanged). `reflect_node` is added with
`add_node`; the fork is one `add_conditional_edges`. No existing node, edge, or component is modified — T2 is
purely additive, which is what keeps Phase 2 independently shippable and independently revertible.

### 3.5 Supervisor tier (T3) — pre-binding (historical; superseded by §3.5a)

> **Superseded 2026-06-15 by §3.5a (T3 un-deferred).** This section is retained as the *original pre-binding* —
> the architecture contract a supervisor must obey — and §3.5a still relies on it. But the framing below ("does
> not un-defer it") is historical: T3 is now an active, design-complete tier. Read §3.5a for the live decision.

T3 *was* **deferred** on workload grounds (§2.3) — this section pre-specifies the
*architecture* a supervisor would have to obey, so the deferral is a scheduling decision, not an architectural
hole, and so a future builder cannot reach for the easy-but-illegal shape (a "supervisor" that drives the graph
from inside a component, or a worker that imports `AgentState`). The same four onion rules from §3.4 apply,
**plus** the multi-agent-specific invariants from [`AGENTS.md`](../../AGENTS.md) and the architecture doc.

**The foundation already exists and is already layer-clean.** `services/tools/task_tool.py` (delegation envelope
+ deterministic budget/policy/approval gates + filesystem handoff) and `services/tools/delegation_dispatcher.py`
(`LocalLLMDelegationDispatcher`, isolated worker invocation → normalized handoff payload) are **horizontal
services with zero `langgraph`/`orchestration`/`components` imports** — verified, not assumed. The architecture
doc's deep-agent capability map ([lines 154-161](../Architectures/FOUR_LAYER_ARCHITECTURE.md)) already places
"Delegation with policy/budget/handoff" in **Services + Orchestration**. T3 is therefore *not* a new subsystem —
it is a thin orchestration topology over delegation machinery that is already built and already conformant.

**The boundary, same table shape as §3.4:**

| Concern | Where it lives | Layer | Must NOT |
|---|---|---|---|
| **Worker execution** — run one delegated objective, return a handoff payload | `services/tools/delegation_dispatcher.py` (exists) | Horizontal service | import `langgraph`, `orchestration.*`, `components.*`, or `AgentState`; know it is "a worker under a supervisor" |
| **Delegation gates** — budget / policy / approval / subagent-allow | `services/tools/task_tool.py` (exists) | Horizontal service | make topology decisions; it returns a structured `ToolExecutionResult`, the graph routes on it |
| **Fan-out / fan-in *decision*** — decompose into N branches? which results are done? | new pure planner in `components/` (e.g. `supervisor_plan.py`) returning a plan of delegations as data | Vertical component | import `langgraph`; spawn or await workers itself; hold worker handles |
| **`supervisor_node` wrapper** — read state, call the component for the plan, dispatch via the service, fold handoffs back | [`react_loop.py`](../../orchestration/react_loop.py) | Orchestration | contain decomposition or merge *logic*; it is glue between the component (plan) and the service (dispatch) |
| **Fan-out edges + join** — wire parallel branches and the synthesis gather | graph builder (LangGraph `Send` / conditional edges) | Orchestration | live anywhere but topology |

**Multi-agent-specific invariants T3 inherits (beyond the §3.4 four):**

- **No worker imports `AgentState`.** Each worker receives a plain `DelegationDispatchRequest` (it already does)
  and returns a handoff payload — the same "receive data, not state" discipline as AP-2
  ([`AGENTS.md` AP-2](../../AGENTS.md)). The supervisor merges payloads back into state in the *node*, never the
  worker.
- **No peer-component imports for decomposition.** The supervisor planner is a component and therefore **must not**
  import `router`, `evaluator`, or `goal_judge` directly (AGENTS.md invariant 5 / no V→V). If it needs a verdict
  to decide fan-in, the *node* reads it and passes it as a scalar — identical to the router/goal_judge rule in §4.
- **Handoff is filesystem/state, not a call-back channel.** Inter-worker and worker→supervisor communication
  rides the existing in-state virtual filesystem handoff (`task_tool` already persists this), not direct method
  calls between agents. This is what keeps the MAST "inter-agent misalignment" surface (§2.3) *observable* through
  the same BlackBox/PhaseLogger pillars rather than hidden in call stacks.
- **Delegation events reuse `TrustTraceRecord`.** The `execution`-category event types
  `delegation_requested`, `delegation_budget_checked`, `delegation_handoff_written`
  ([architecture doc line 146](../Architectures/FOUR_LAYER_ARCHITECTURE.md)) are already reserved — T3 emits
  these, inventing no new event *names*. But "reuses an existing event type" is **not** the same as "has a
  verified carrier" — §3.7 makes the carrier obligation explicit (the token-seam incident died on exactly that
  unverified assumption).

**Why pre-specify a deferred tier:** the MAST failure modes that justified deferring T3 (§2.3) are *the same
failures an un-disciplined implementation would reintroduce* — lost context across workers, skipped verification,
hidden inter-agent state. Binding T3 to these rules now means the deferral can be revisited as a pure
cost/benefit question ("does the corpus now have parallel work?") without re-litigating architecture. The
trigger to revisit remains the §2.3 corpus condition; the build, when it comes, is additive nodes + edges over
services that already pass `tests/architecture/`.

### 3.5a Supervisor tier (T3) — as-built design (2026-06-15: un-deferred to de-risk the seam)

**Decision (2026-06-15):** build a **thin T3** for **parallel independent fan-out** *now*, despite §2.3's finding
that the corpus has ~0 genuine parallel work. The rationale is **seam de-risking**, not a workload need — so the
acceptance bar is set accordingly (below). This section is the concrete design; §3.5 above remains the binding
*architecture contract* T3 must obey. Where they meet: §3.5's onion table names *where* each concern lives; this
section names *what each node does* and *how the fan-out actually runs concurrently*.

**Honest success metric (read this before building).** Two independent 2026 findings say a parallel T3 will **not**
move quality on our workload, and we must not pretend otherwise:
1. **The "<3 items" rule** ([LangChain forum](https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900)):
   below ~3 branches, `Send` routing overhead exceeds the latency saved. Our corpus's parallel work tops out at
   ~3 gather-then-compare tasks — exactly the regime where fan-out barely pays.
2. **Single-agent beats multi-agent on GAIA-Val** (benchmark literature, June 2026): multi-agent decomposition
   *raises* information-loss + mistake-propagation; a single agent keeps a continuous reasoning trajectory. This is
   the §2.3 MAST surface confirmed empirically.

Therefore **T3's acceptance bar is not goal-met rate or latency.** It is: **(a)** the fan-out/fan-in seam exists and
is **layer-clean** (`tests/architecture/` proves no worker/`supervisor_plan` imports `langgraph`/`orchestration`/
`AgentState`); **(b)** it is **observable** (the `delegation_*` carriers in the §3.7 table actually export per
branch); **(c)** the **MAST failure modes are bounded by Protocol-D tests** (one slow/failed branch cannot hang or
corrupt the join). A throughput win, if it ever appears, is a bonus measured later on a real parallel workload —
never the gate. Building the mechanism ahead of the workload is the explicit, accepted trade.

**Pattern decision (2026-06-15): custom `Send` nodes, NOT `create_agent` subagents-as-tools.** The official
LangChain tutorial ([subagents-personal-assistant](https://docs.langchain.com/oss/python/langchain/multi-agent))
builds a supervisor as `create_agent(tools=[subagent_as_tool, …])` — far less code, built-in HITL, parallel tool
calls. We **rejected** it for two source-verified reasons:

1. **It's the same primitive underneath — so the custom path costs no concurrency, only code.** Reading the
   installed `langgraph/prebuilt/tool_node.py`: the prebuilt `ToolNode` runs multiple tool calls via
   `await asyncio.gather(*(self._arun_one(call, …) for call in tool_calls))` (`_afunc`, ~line 259) under `ainvoke`,
   and its `_parse_input` literally returns `[Send("tools", [tool_call]) for tool_call in tool_calls]` (~line 188).
   **`create_agent` fan-out *is* `Send` fan-out** with the supervisor LLM making the split inside an
   un-instrumentable ReAct loop. Our `supervisor_node` → `Send` design uses the identical execution mechanism,
   exposed one layer down where the §3.7 pillars can wrap each branch and the decompose decision is a pure,
   testable component. The custom path is not "heavier for the same result" — it is the *same result, instrumented*.
2. **`create_agent` violates the framework-substitutability principle; the custom path honors it.** The four-layer
   doc ([`FOUR_LAYER_ARCHITECTURE.md`](../Architectures/FOUR_LAYER_ARCHITECTURE.md) lines 47/78/161) mandates
   **orchestration = "topology only, thin wrappers"** and **vertical components = "framework-agnostic domain
   logic"** — operationally, *LangGraph must be swappable*. `create_agent` puts a sub-agent's entire reasoning
   loop (domain behavior) *inside LangChain* → you could not swap the graph runtime without rewriting the
   sub-agents (domain logic leaked upward — forbidden). The §3.5a shape keeps `supervisor_plan.py` (the decompose
   decision = domain logic) a pure `components/` function with zero `langgraph` import; only the node wrappers +
   the `Send` edge touch the framework. Swap LangGraph → rewrite the thin wrappers, the component is untouched.
   This is the substitutability test *passing*, and it is the deciding reason. (It also re-confirms the §2.3/§3.5
   MAST guard: a `create_agent` sub-agent's reasoning is exactly the "hidden inter-agent state" the pillars must
   see — the convenient pattern reintroduces the failure surface the deferral was protecting against.)

**Topology — `Send`-based map-reduce (the idiomatic LangGraph fan-out).**

```
route ─→ supervisor ──(conditional edge returns list[Send])──→ ⟨ worker × N, parallel ⟩ ─→ join ─→ evaluate
              │  (calls pure components/supervisor_plan.py            │ (thin wrapper over          │ (existing
              │   for the decomposition; returns Send list,           │  the EXISTING dispatcher,   │  node — judge
              │   one per branch, SMALL payload = ids/objective)      │  try/except → sentinel)     │  still runs
              └─ no decompose logic in the node                       └─ writes worker_results      │  on final)
                                                                         (Annotated[list,add])      │
```

- **`supervisor_node`** (orchestration, new) — reads state, calls a pure **`components/supervisor_plan.py`**
  (`plan_delegations(...) -> list[Delegation]`, decomposition as *data*), and returns `list[Send]` — one
  `Send("worker", {…small payload…})` per branch. Holds **no** decomposition logic (§3.5 row 3/4). Fan-out is a
  **conditional edge** returning the `Send` list, per the researched pattern
  (`builder.add_conditional_edges("supervisor", route_fn, ["worker"])`).
- **`worker_node`** (orchestration, new) — a thin wrapper over the **existing** `LocalLLMDelegationDispatcher`
  (§3.5 row 1, already layer-clean). **Mandatory** `try/except` returning a sentinel result: per the research, *one
  branch raising cancels the entire super-step* — so a worker must never propagate its exception to the graph.
  Per-branch **timeout** is load-bearing for the same reason (the super-step barrier waits for the slowest branch;
  [langgraph#6320](https://github.com/langchain-ai/langgraph/issues/6320) — an unrelated slow sibling blocks the
  join). Attach a `RetryPolicy` for transient provider errors.
- **fan-in state key** (new on `state.py`): `worker_results: Annotated[list[dict], operator.add]` — the reducer is
  **mandatory** for parallel writes (without it, concurrent branch writes raise `INVALID_CONCURRENT_GRAPH_UPDATE`
  and "the second write erases the first"). This is the *same* `operator.add` / `_append_list` convention already
  used for `reflections`/`tool_results` ([`state.py:17-30`](../../orchestration/state.py)) — no new mechanism.
- **`join_node`** (orchestration, new) — a plain node that reads the merged `worker_results` after all branches
  complete, synthesizes one answer, and edges to the **existing `evaluate` node** so GoalJudge runs on the *final*
  synthesized answer. This is what keeps the §3.7 corrupt-success guard honest for T3: the judge sees the merged
  output, not a per-worker fragment.

**The concurrency fork — RESOLVED (the one open technical question).** `Send` gives *graph-level* parallel
branches, but each branch still executes its `worker_node`, which calls the dispatcher. The dispatcher today is
**synchronous and event-loop-blocking**: `dispatch()` does `thread.start(); thread.join()`
([`delegation_dispatcher.py:84-86`](../../services/tools/delegation_dispatcher.py)). The repo runs the graph under
**`app.ainvoke`** ([`react_loop.py:483`](../../orchestration/react_loop.py)) and **every existing node is
`async def`** with `await llm_service.invoke(...)` → `await llm.ainvoke(...)`
([`llm_config.py:75`](../../services/llm_config.py)) — i.e. the whole loop is non-blocking async and LLM I/O yields
the event loop. **Consequence:** if `worker_node` calls the *current* sync `dispatch()`, the `thread.join()` blocks
the single event loop and the N branches **serialize** — fan-out topology with **zero** real concurrency. **The
fix is small and contained:** add an **`async def dispatch`** to `LocalLLMDelegationDispatcher` that `await`s
`self._invoke_worker(...)` directly (dropping the `thread`/`join` shim, which only existed to run a coroutine from
sync code), and have `worker_node` `await` it. Then the N branches' `await`ed LLM calls overlap on the loop —
genuine concurrency, no new threading. The sync `dispatch()` stays for the existing non-graph caller. *This keeps
the dispatcher layer-clean: it still imports no `langgraph`/`orchestration`.* (A `max_concurrency` run-config cap
bounds fan-out against the LLM rate limit — fan-out N vs the provider's req/min, else 429s.)

**Per-pillar carriers (extends the §3.7 table for T3, all `execution`-category, none crosses the SSE seam).** The
event *names* already exist (§3.5): `delegation_requested` / `delegation_budget_checked` /
`delegation_handoff_written`, plus a budget/policy **deny** as `error.occurred`. T3 must emit one set **per
branch** (carry the branch's `correlation_id` so the trace can join fan-out to fan-in), and the `supervisor_node`
emits one decomposition carrier (how many branches, on what basis) — the same "verified carrier, not assumed"
obligation (§3.7). The reflexion/escalation interplay is unchanged: T2 can still re-enter *after* the join if the
judge fails the synthesized answer.

**TDD shape (extends §7.5).** `components/supervisor_plan.py` is **Protocol C** (mocked-LLM decompose logic +
the failure path: a non-decomposable task returns a single-branch plan, *tested first*). The `supervisor_node` /
`worker_node` / `join_node` + fan-out/fan-in edges are **Protocol D** — a **failure-mode matrix** is the headline:
*one worker raises → join still synthesizes from the survivors* (sentinel path), *one worker times out → super-step
does not hang past the cap*, *all workers fail → graceful degraded answer, judge still runs*. The
`worker_results` reducer gets a **Pattern-1 property test** (N concurrent appends merge, none lost) — the
"canary test simulating N workers" the research recommends. Per §7.5's non-negotiable rule, **every one of these
failure tests lands before the happy-path fan-out test.**

### 3.6 Frontend / middleware connection seam — the new tiers must not cross it

This plan is **backend-only** (`orchestration/`/`components/`/`services/`/`trust/`). The Frontend Ring
([`FRONTEND_ARCHITECTURE.md`](../Architectures/FRONTEND_ARCHITECTURE.md)) is an **additive outer ring** that
consumes the backend through exactly one seam — the `agent_ui_adapter` SSE surface — and "can be removed without
changing a single file in `trust/`, `services/`, `components/`, `orchestration/`". The conformance question for
T1/T2/T3 is therefore narrow and answerable: **does anything the new tiers introduce force a change across that
seam, and if so, does it stay inside the ring's rules?** Verified against the live wire shapes, the answer is
*no forced change* — the new state and events are backend-internal by default.

**The seam is one-directional and HTTP/SSE-only.** Per [`AGENTS.md` invariant 8 / AP-4](../../AGENTS.md) and
[`FRONTEND_ARCHITECTURE.md` Rule M1](../Architectures/FRONTEND_ARCHITECTURE.md), nothing in the backend may
import from `middleware/` or `frontend/`, and `middleware/` reaches the backend only via the `agent_ui_adapter`
HTTP client — never at module scope. The new nodes (`planner_node`/`reflect_node`/`supervisor_node`) live *below*
`agent_ui_adapter`; they are invisible to the frontend except through whatever the runtime adapter chooses to
emit. **No new tier may add a `middleware/` or `frontend/` import** — that would be the same upward-dependency
violation §3.4/§3.5 already forbid, now across a process boundary.

**Two event tiers already exist — put new events in the right one.** The repo has a deliberate split, confirmed
in the live wire (`agent_ui_adapter/wire/domain_events.py`):

| Tier | Carrier | Audience | Crosses the SSE seam? | The new tiers' events |
|---|---|---|---|---|
| **Backend-internal telemetry** | `TrustTraceRecord` `execution`-category (`planning_depth_selected`, `reflection_recorded`, `delegation_*`) | governance / eval / observability | **No** — never reaches the frontend wire | **default home** for T1/T2/T3 events |
| **UI-facing domain events** | curated `DomainEvent` union (`StateMutated`, `StepProgressed`, `ReasoningSummarized`, `TaskUnderstood`, …) | the browser, via `agent_ui_adapter → middleware → BFF → browser` | **Yes** | only by *deliberate promotion* (below) |

The `DomainEvent` union is a **curated UI surface, not a mirror of backend telemetry** — it already omits the
fine-grained backend events. So T1/T2/T3 emitting `TrustTraceRecord` `execution` events (per §3.4/§3.5) reaches
governance and eval **without touching the frontend at all**. This is the default and requires zero frontend work.

**If a tier's progress must be *shown* (e.g. a "replanning…" or "reflecting…" indicator), promotion is a
ring-internal change, not a backend one.** The discipline, end to end:

1. Add a new variant to `agent_ui_adapter/wire/domain_events.py` (Python wire kernel) **and** its mirror in
   `frontend/lib/wire/domain_events.ts` — the two are kept in lock-step by design; `wire/` imports only
   stdlib + Zod and every variant carries `trace_id` ([F-R7](../Architectures/FRONTEND_ARCHITECTURE.md)).
2. The runtime adapter (`agent_ui_adapter/adapters/runtime/`) emits it; `trace_id` flows **verbatim** from the
   Python runtime — the browser never generates one (F-R7 / FE-AP-7 auto-reject).
3. Translation AG-UI → UIRuntime stays in `frontend/lib/translators/`; rendering is a pure prop-driven React
   component ([F-R1](../Architectures/FRONTEND_ARCHITECTURE.md): no domain logic in components).
4. **No SDK type, no backend Python type, and no raw `AgentState` shape crosses the seam** — only `wire/` shapes
   (F-R8). The reflexion critique text or supervisor fan-out plan, if surfaced, crosses as a plain `wire/` field,
   never as the internal component object.

**Net:** the planning tiers conform to the frontend architecture *by staying behind the seam*. The recommended
posture is **telemetry-only (no promotion) for the initial T1/T2 rollout** — it satisfies the eval/governance
scoreboard (§8) with zero frontend surface area — and to treat any "show planning/reflection in the UI" work as
a **separate, frontend-ring-scoped follow-up** that adds a curated `DomainEvent` variant under the four-step
discipline above. That keeps this plan's blast radius inside the backend, exactly as the ring's additive-removal
guarantee intends.

### 3.7 Governance-triangle conformance — every new fact needs a verified carrier

The §3 design anchors say "the governance pillars wrap new nodes unchanged" (anchor 3). That is necessary but
**not sufficient**: wrapping a node does not guarantee the *facts the node introduces* survive into the curated
trace. The
[`governance-trace-audit`](../skills/governance-trace-audit/SKILL.md) contract is the acceptance bar — a trace
must let a reader answer four questions **from the trace alone**, and the audit validates the *instrumentation*,
not task success. The new tiers add new facts ("which depth, and why?", "did we replan, and on what surprise?",
"what was the reflexion critique?", "what was delegated, under what budget?"). Each must land on the right pillar
with a carrier that **actually exports**.

**The one rule that governs all of this: _curate volume, never truth_.** A fact may have duplicate carriers
suppressed, but every fact must retain **exactly one reliable carrier that actually exports**. A fact with zero
carriers is the worst class of finding — and it is almost always created by suppressing a carrier "because
another observation has it" without verifying the substitute. **This is not hypothetical:** the token-usage seam
([trace-checks §3d](../skills/governance-trace-audit/references/trace-checks.md)) suppressed `STEP_EXECUTED` on
the premise the wire `llm.call` carried tokens; it didn't, so tokens had zero carriers and vanished from the
curated trace. CI was green throughout. **Every new tier fact inherits this obligation explicitly.**

**Per-pillar landing for the new facts (the conformance table):**

| New fact (tier) | Pillar | Carrier observation | Must verify |
|---|---|---|---|
| planning depth chosen + reason (Phase 0/T1) | Reasoning | `step.planned` (`planning_depth`, `plan_fingerprint`, `plan_summary`) + `model.selected.rationale` (already folds `plan_depth`) | the *fixed* depth (not the collapsed L0) is what exports |
| LLM-generated plan (T1) | Reasoning | `step.planned` with `plan_changed: true`, `plan_summary` | dedup still holds — one `step.planned` per *distinct* plan, not one per generation |
| **replan** on surprising tool output (T1) | Reasoning | a `step.planned` with a **new** `plan_fingerprint` + `plan_changed: true` | a replan is a genuinely new plan → it MUST export (it is not a dedup-suppressible re-emission); the *unchanged* re-emissions still suppress |
| reflexion critique (T2) | Reasoning | `eval.*` / `step.planned`-adjacent carrier holding the verbal critique + the `unmet_conditions` it derived from | the critique text has a carrier at all — do **not** assume `reasoning_recap` carries it (that's the cosmetic summary, §1) |
| escalation decision (T2/T3) | Reasoning | `model.selected.rationale` / a decision carrier with `decision_id` | the escalation trigger (which §5 signal fired) is in the rationale, joinable by `decision_id` |
| delegation request + budget + handoff (T3) | Recording + Validation | `delegation_requested` / `delegation_budget_checked` / `delegation_handoff_written`; budget **denials** as `error.occurred` | a budget/policy **deny** surfaces as Validation evidence, not a silent drop (the silent-failure cross-check) |

**Three governance interactions the plan must respect:**

1. **Corrupt-success is the headline check, and T2 *strengthens* it.** The audit leads with `outcome: "success"`
   vs `goal_met: false`. T2's whole premise is escalating on GoalJudge failed/partial (§5) — so Reflexion is
   *acting on the same signal the audit treats as the most important fact in the trace*. The plan must keep that
   signal honest end-to-end: `task.completed` must still carry `goal_met`/`unmet_conditions` after a reflexion
   loop, and the judge must run on the *final* (post-reflexion) answer so the corrupt-success check sees the real
   outcome. A reflexion loop that masked a failed `goal_met` into a success would be the exact governance-missed
   corrupt success the audit escalates to NON-COMPLIANT.

2. **Honest time / no backdating applies to re-entrant loops.** Reflexion and replan re-enter `route`, producing
   *more* observations on the same `trace_id`. Each carries `event_time` first-class and is stamped at relay
   time (decision D-0a); near-zero relay durations are correct, not a defect. The plan must not try to
   "reconstruct" a single linear timeline or backdate a reflexion span to look contiguous — the honest record is
   multiple stamped passes under one `trace_id`.

3. **Dedup vs. real change is the subtle one.** `step.planned` dedups on `plan_fingerprint` (one export per
   distinct plan). A **replan** is a new fingerprint → it must export. The failure mode to avoid is a too-eager
   suppressor treating a replanned plan as a duplicate (truth lost) — or the opposite, re-exporting an unchanged
   plan every reflexion pass (volume noise). The fingerprint in `components/plan_builder.py` is the arbiter;
   the new tiers must compute it over the *actual* (possibly replanned) plan.

**Acceptance hook:** each phase's gate (§7/§8) adds one governance assertion — run a from-step-0 trace through the
`governance-trace-audit` contract and confirm the phase's new fact has a non-empty carrier (Phase 0: fixed depth
on `step.planned`; Phase 1: replan exports a new fingerprint; Phase 2: critique carrier non-empty + post-reflexion
`goal_judge` present). "CI is green" is explicitly **not** sufficient evidence — one contradictory trace outweighs
a clean suite (the skill's hard-won rule).

## 4. Routing design (hybrid cascade)

**Decision: hybrid, with the LLM override on the *escalation* edge, not the *entry* edge.** This is the
non-obvious correction the 2026 calibration research forces.

- **Pure lexical heuristic** = the current bug (the routing survey: rule-based routers "lack adaptability",
  [arxiv 2509.07571](https://arxiv.org/html/2509.07571v1)).
- **Pure LLM self-router re-introduces the bug.** [Agentic Overconfidence (arxiv 2602.06948)](https://arxiv.org/pdf/2602.06948):
  LLMs are systematically overconfident, **worst on hard tasks**, and **evidence tools (web search) induce severe
  overconfidence** → an upfront "how hard is this?" self-router would **under-route exactly the hard, tool-heavy
  tasks** that need T2.
- **Hybrid is where 2026 converges.** [Select-then-Solve (arxiv 2604.06753)](https://arxiv.org/pdf/2604.06753)
  routes between ReAct/plan-execute/reflexion paradigms and lands on hybrid as the middle ground; cascade routing
  ([survey, arxiv 2603.04445](https://arxiv.org/pdf/2603.04445)) starts cheap and escalates on failure. Custom
  routers win by using **task-specific signals a generic router lacks** — and we *own* them (`task_tool_results_count`,
  `consecutive_errors`, GoalJudge `unmet_conditions`).

**Two routing moments:**
1. **Entry routing (cheap, conservative).** Heuristic floor (the fixed `select_planning_depth`) + a *narrow*
   LLM nudge limited to the structural question "is this multi-part / does it need an explicit plan?" — biased to
   **under-commit** (start a tier low; cascade escalation is cheap, a mis-fire is not).
2. **Escalation routing (the real intelligence).** Do **not** trust upfront difficulty estimation. Escalate on
   **observed failure evidence** (§5). This sidesteps overconfidence because we route on *evidence of failure*,
   not *prediction of difficulty*.

## 5. Escalation triggers

The 2026 escalation-design literature ([Runtime Verification 2026](https://thebackenddevelopers.substack.com/p/runtime-verification-for-ai-agents),
[HITL Escalation Design 2026](https://www.digitalapplied.com/blog/human-in-the-loop-escalation-design-ai-agents-2026))
is consistent: escalate on **objective signals — verification failures and unresolved loops — not arbitrary
thresholds.** Those fire at different times, so they compose as a two-layer trip-wire rather than competing:

| Trigger | Type | Fires | Reuses | Role |
|---|---|---|---|---|
| **GoalJudge failed/partial + `unmet_conditions`** | semantic | end-of-run | `goal_judge.evaluate` (I2 path) | **primary** — only signal that catches *confidently-wrong* output |
| **no-progress / repeated-tool** | structural | mid-run | `_count_trailing_repeats`, `no_progress_directive_sent` | **secondary** — escalate before burning budget finishing a doomed run |
| synthesis-validation failure | semantic (coverage) | pre-judge | `validate_synthesis` | cheap **pre-filter into** the judge, not a standalone escalator (known all-or-nothing grounding FP) |
| `consecutive_errors` | operational | per-step | `select_model` escalate-after-N | stays on **model** escalation; misses silent failures, so not primary for tier escalation |

**Rationale for "GoalJudge primary":** alignment-trained models are overconfident
([arxiv 2602.06948](https://arxiv.org/pdf/2602.06948)), so an error-count threshold under-fires on the
silent-failure case (confident, wrong, error-free). The judge is the only trigger that catches it, and it is
already computed + already eval'd — this promotes an existing **observability** signal into a **control** signal.

## 6. Open decisions (decide via trade-off before build)

These are deliberately **not** pre-decided; weigh before implementing the relevant phase.

**D1 — Reflexion budget ceiling.** Options, with trade-offs:
- *Reuse `no_progress` threshold as the ceiling* — cheapest, reuses machinery, low blast radius; but couples
  reflexion budget to a structural signal that may not correlate with "one more reflexion would help".
- *Fixed `max_reflexion_attempts` config (e.g. 2)* — most tunable, clearest telemetry; but a new knob and new
  eval surface to calibrate.
- *Budget-fraction gated* (allow reflexion while `total_cost_usd < f · max_cost_usd`) — ties retries to real
  spend, naturally protects the budget; but a cheap task gets few retries regardless of whether they'd help.

**D2 — Entry LLM-nudge scope.** Exactly what the narrow structural classifier asks (multi-part? needs-plan?),
and whether it's even worth one fast-tier call per task vs. heuristic-only entry with all intelligence on the
escalation edge.

## 7. Phased rollout

Each phase is independently shippable and independently eval-able.

- **Phase 0 — Fix the depth collapse (prerequisite).** Repair `task_tool_results_count → L0` and the upstream
  flattener so the existing signal survives. Re-run `scripts/diagnose_planning_depth.py` and the depth-strata
  corpus; gate: the 14/17 collapse clears. *No new tier — pure fix. Highest leverage.*
- **Phase 1 — T1 Plan-and-Execute.** Add `planner_node` (LLM plan, deterministic floor fallback) + the
  `replan` back-edge (after K steps or on surprising tool output). Gate: T1 ≥ ReAct baseline on the corpus with
  no brittle-plan regressions.
- **Phase 2 — T2 Reflexion.** Add `reflect_node` re-entering on GoalJudge failed/partial; wire the
  no-progress secondary trip-wire; apply the D1 budget ceiling. Gate: T2 recovers a measurable fraction of
  partials without thrash.
- **Phase 3 — Hybrid escalation routing.** Promote the cascade: entry heuristic+nudge, escalation on §5
  signals. Gate: entry-router accuracy (via `diagnose_planning_depth`) + escalation precision measured
  separately.
- **Phase 4 — T3 supervisor / parallel fan-out (thin, seam-de-risking).** Add `supervisor_node` (calls pure
  `components/supervisor_plan.py`) → `Send` fan-out → `worker_node` (wraps the dispatcher, made **async**) →
  `join_node` → existing `evaluate`; new `worker_results` reducer key (§3.5a). **Gate is NOT throughput/goal-met**
  (the §3.5a honest metric): the seam is layer-clean (`tests/architecture/`), per-branch `delegation_*` carriers
  export, and the Protocol-D failure matrix passes (one slow/failed branch never hangs or corrupts the join).
  Validated against the §8.2 synthetic fan-out corpus in calibration mode.

## 7.5 TDD methodology — how each phase is built

Implementation follows [`research/tdd_agentic_systems_prompt.md`](../../research/tdd_agentic_systems_prompt.md):
the **agentic testing pyramid** + the four layer-specific protocols + the 11-pattern catalog. The non-negotiable
rule across every phase is **failure paths first** — write the rejection/abort test *before* the acceptance test
for every new gate (router decision, replan trigger, reflexion ceiling, delegation budget). A gate that accepts
everything is more dangerous than one that rejects everything ([AGENTS.md TAP-4](../../AGENTS.md);
[tdd doc Anti-Pattern 6](../../research/tdd_agentic_systems_prompt.md)).

**Each new artifact is built under the protocol for its layer** (the architecture-to-pyramid mapping, tdd doc
§Architecture-to-Pyramid Mapping — note its illustrative names `utils/`/`agents/` are this repo's
`services/`/`components/`):

| New artifact | Layer | Pyramid / Protocol | Test strategy | Key patterns |
|---|---|---|---|---|
| `reflections` / replan keys on `state.py` (schema shape) | Orchestration state | L1-style purity for the schema | Pydantic/TypedDict validity + reducer behavior (append-only, dedup) — deterministic, <10s, zero flake | P1 property-based schema, P2 state-machine invariant |
| `components/reflexion.py` generator + re-entry predicate | Vertical component | **Protocol C — Eval-Driven** | C1 deterministic scaffolding with `TestModel`/`FunctionModel` (mocked LLM) for the predicate + parsing; C2 trajectory eval that a failed verdict → critique → re-entry actually fires | P6 mock provider, P8 trajectory, P5 record/replay |
| `components/supervisor_plan.py` (T3, 🔮 planned) | Vertical component | **Protocol C** | decline-first decompose decision, mocked LLM; the dependent-plan→decline (GAIA guard) test lands FIRST; never live LLM | P1, P6 |
| LLM `planner_node` logic (in `components/plan_builder.py`) | Vertical component | **Protocol C** | C1 plan-structure validity + **deterministic floor fallback on generation failure** (the failure path is the headline test); C3 rubric eval for plan quality | P6, P9 rubric |
| `planner_node` / `reflect_node` / `supervisor_node` wrappers + edges | Orchestration | **Protocol D — Simulation-Driven** | Protocol-D1 **failure-mode matrix** over the escalation fork (verdict × budget × no-progress → reflect / recap / END); Protocol-D3 binary-outcome scenarios ("does a failed-then-reflected run recover? YES/NO") | P11 failure-mode matrix, P10 governance-loop sim |
| escalation routing (`components/router.py`) | Vertical component | **Protocol C** + Protocol-D1 at the edge | C1 deterministic heuristic floor (failure paths: each §5 trigger fires/doesn't); the LLM nudge mocked | P6, P11 |

**Per-phase TDD shape (mirrors the §7 gates):**

- **Phase 0 (depth fix).** Pure Protocol C/L3 — *regression-test the collapse first* (a failing test asserting
  the 14/17 corpus rows reach their intended depth) → fix → green. This is classic red-green on a deterministic
  heuristic; `diagnose_planning_depth.py` becomes the fixture oracle. No LLM, so zero-flake L1-discipline applies.
- **Phase 1 (T1).** Protocol C for the planner (mocked-LLM structure tests + the deterministic-floor **fallback**
  test before the success test) and Protocol D for the `replan` edge (Protocol-D1 matrix: surprising-output →
  replan, stable-output → no replan). Brittle-plan regression (Risk §9) gets a dedicated failure test: a
  surprising tool result must trigger replan, not silently continue.
- **Phase 2 (T2).** Protocol C for `reflexion.py` (predicate ceiling tested **failure-first**: at-budget → `stop`
  before under-budget → `reflect`) + Protocol D simulation for the re-entry loop. Reflexion-thrash (Risk §9) is a
  D-level sim: N reflexions must hit the **D1 budget ceiling (§6)** and terminate. The §3.7 corrupt-success guard
  is a Protocol-D3 binary scenario: "a reflexion loop never masks `goal_met:false` into success."
- **Phase 3 (routing).** Protocol C for entry heuristic + Protocol-D1 matrix for escalation precision (each §5
  signal, fired and not-fired, maps to the right tier transition).

**Determinism & CI policy (inherited verbatim):** unit tests mock the LLM (`TestModel`/`FunctionModel` or
record/replay, Patterns 5/6) — **never live LLM in CI** ([AGENTS.md](../../AGENTS.md); tdd Anti-Pattern 5).
L3/L4 quality and trajectory evals run on **aggregate pass rates** (e.g. 4/5), tagged `@pytest.mark.slow` /
`@pytest.mark.simulation`, off the CI hot path. No determinism theater — assert structure/trajectory/properties,
not exact LLM strings (Anti-Pattern 3).

**Layer-boundary enforcement is itself a test (Pattern 7).** The onion rules from §3.4/§3.5 are not just prose:
`tests/architecture/` ([AGENTS.md](../../AGENTS.md): "These MUST pass") must gain assertions that
`components/reflexion.py` / `supervisor_plan.py` do **not** import `langgraph`/`orchestration`/`AgentState`, and
that no new peer-component import appears (router ↮ goal_judge). Run Pattern 7 against the **test** tree too — a
`tests/components/` file importing from `orchestration/` is the same leak (Anti-Pattern 7).

## 8. Eval & acceptance

- **Reuse the existing harness.** GoalJudge verdicts + the eval-probe pipeline are the scoreboard; the
  depth-strata corpus is the planning-quality fixture; `diagnose_planning_depth.py` is the entry-router probe.
- **Separable metrics** (the hybrid's eval payoff): *entry-router accuracy* (did the floor+nudge pick a
  sensible starting tier?) and *escalation precision* (when we escalated, did the higher tier actually do
  better?) are measured independently.
- **Governance-trace gate (per §3.7).** Each phase additionally passes a from-step-0 trace through the
  [`governance-trace-audit`](../skills/governance-trace-audit/SKILL.md) contract: the phase's new fact must have
  a non-empty carrier that actually exports, and the corrupt-success check (`outcome` vs `goal_met`) must remain
  honest after any reflexion loop. One contradictory trace blocks the phase — green CI is not sufficient.
- **Per-phase gate** as in §7; ship behind a flag tier (`steady-state` parity first), promote on evidence —
  mirroring the GoalJudge shadow→consume discipline.

### 8.1 Live validation — first loops-on Cloud Run measurement (2026-06-15)

First run of all four seams against the loops-on `stress` Cloud Run revision
(`REFLEXION_ENABLED=1 PLANNING_PLAN_SOURCE=generated`), 42-case batch
(`frontend/stress-batch-results.json` + `cache/planning_stress/ui_batch.jsonl`), scored read-only by
`scripts/analyze_planning_traces.py --source langfuse` (calibration mode — records rates, no gate). Langfuse
is the durable trace store; the Playwright "42 passed" is liveness only, **not** the planning-quality verdict.

| Seam | Rate | Detail |
| --- | --- | --- |
| **Depth (entry-router)** | **0.917 (11/12)** | The Phase-0 verdict: pre-fix, 14/17 strata rows collapsed to L0; now **8 of 9 non-L0 cases (6×L1, 3×L2) fire their intended depth.** The collapse is cleared. |
| Replan gate | 0.900 (9/10) | — |
| Reflexion | 0.800 (8/10) | Both misses same shape, benign direction (see edges below) |
| Escalation | 0.900 (9/10) | **precision 1.000 / recall 0.800 / tp4 fp0 tn5 fn1** — never false-escalated; one missed escalation (the cheaper error per MAST asymmetry). |

**Verdict: Phase 0 holds on the live backend.** The depth-collapse bug that motivated the redesign is gone —
the lone depth miss is an *under-by-one-tier*, not a flatten-to-L0. Caveats kept honest: N is small per seam
(10–12 cases; one case ≈ 8 pts, wide CIs — robust enough to confirm the *categorical* collapse-cleared result,
not to finely calibrate the L1/L2 boundary); calibration mode *records*, does not gate; LLM runs jitter ±a case
on re-run.

**Calibration-edge backlog (named, minor — not Phase-0 blockers):**
- **CE-1 `STRESS-DEPTH-009` want=L2 got=L1.** L1/L2 boundary under-plans one tier (3-step plan vs 5 ideal).
  A `select_planning_depth` calibration edge, not a collapse. Candidate for the depth-strata oracle.
- **CE-2 `STRESS-REPLAN-garbage-input-02` want_replan=True got_replan=False.** `plan_is_stale` keys on
  tool-failure / explicit-surprise scalars ([`plan_builder.py:278`](../../components/plan_builder.py)); a
  *garbage input* that never surfaced as a failed tool result doesn't trip the gate. A stale-detection coverage
  gap for the "junk input, no tool error" case.
- **CE-3 reflexion over-trigger on trivials (`control-trivial-07`, `-10`).** Both re-entered reflexion once on
  a task that wanted none — but `bounded=True, attempts=1`: the D1 ceiling held, no thrash. A precision-on-trivials
  edge, not a safety issue.

### 8.2 T3 fan-out validation corpus (data BUILT 2026-06-15; analyzer branch pending)

> **Full corpus plan: [`t3_fanout_corpus.plan.md`](t3_fanout_corpus.plan.md)** — the row catalog, the T3 planning
> decision-space axes, the coverage matrix, and the scoring delta live there (single source). This section is the
> *summary*; that doc is authoritative for *which tasks* and *why each one*. **Scope updated 2026-06-15:** the
> corpus is a **blend** of consumer tuples (trip/restaurant/gift) and benchmark-derived shapes, deliberately
> **seeds near-miss decline traps** (tasks that look parallel but are sequentially dependent), and scales to
> **≈30 rows, hard cap 40** — dimensioned by §2's decision-space coverage matrix, not a fixed row count.
>
> **Status (2026-06-15): corpus DATA is built and verified** — `build_planning_stress_corpus.py` now emits **29
> `phase="fanout"` rows** (`FANOUT-independent` 10 / `FANOUT-decline` 10 [7 near-miss ⚠ traps + 3 obvious] /
> `FANOUT-fault` 5 / `FANOUT-control` 4; `want_fanout` 15 True / 14 False so precision is measurable), `pytest
> tests/scripts/` green. **It is inert data until Phase 4 nodes emit the carriers**, and the analyzer has **no
> `fanout` branch yet** — a fanout row currently falls through `score_run`'s `if/elif` and silently reports
> `rate=0.0` (not a crash; do not misread a pre-Phase-4 run as "fan-out failed"). Building the analyzer branch is
> part of Phase 4 (impl §7.6).

Because §2.3 says the real corpus has ~0 parallel work, T3 is validated against a **synthetic fan-out stress
corpus** authored from **industry-standard agent benchmarks plus relatable consumer tuples**, mirroring the T1/T2
stress-corpus shape (`build_planning_stress_corpus.py` + `analyze_planning_traces.py`). This is a *mechanism*
validation, consistent with §3.5a's seam-not-throughput acceptance bar — it proves the fan-out/fan-in seam behaves,
**not** that the workload needs it.

**Benchmark source (June 2026 survey).** **GAIA** (466 tasks chaining web browse + file parse + multi-document
reasoning) is the natural fit: its multi-document tasks are the closest thing to *genuinely independent* branches
(summarize/extract from N sources, then synthesize). We **adapt** a handful of GAIA-style task *shapes* (not the
private answer set) into prompts whose decomposition is observably parallel. Secondary shapes from Tau²-bench
(independent policy checks) and WebArena (independent multi-tab lookups) round out the adversarial cases. **We
deliberately include the §3.5a counter-evidence as test cases**: the GAIA-Val finding that single-agent beats
multi-agent means a sub-set of rows must be tasks where fan-out is *wrong* (sequential-dependent disguised as
parallel) — the supervisor must **decline to fan out** (single-branch plan), and that decline is a scored
expectation, not a failure.

**New row shape (extends `_row`):** `phase="fanout"`, with new expectation keys the (new) fan-out analyzer reads:

| Key | Meaning | Scored by |
|---|---|---|
| `want_fanout` (bool) | should the supervisor decompose into ≥2 parallel branches at all? | did `supervisor` emit ≥2 `Send`? (the *decline-to-fan-out* cases set this `False`) |
| `want_branch_count` (int, optional) | expected branch count for genuinely-parallel rows | branch count from per-branch `delegation_requested` carriers |
| `want_join_synthesizes` (bool) | did the join produce one coherent answer from the branch results? | `join_node` carrier + GoalJudge ran on the merged answer |
| `want_survives_partial` (bool) | for fault-injection rows: one branch fails → join still answers from survivors | sentinel path observed; final answer non-empty; no super-step hang |

**Row families (start at the answered 8/6/3/3 = 20 split, scale to ≈30 / cap 40 to fill the
[corpus plan](t3_fanout_corpus.plan.md) §6 coverage matrix). Decline is weighted heaviest — it is the
load-bearing decision):**
- **`FANOUT-independent-NN`** (8 → 10–12) — genuinely parallel GAIA-style multi-doc lookups + consumer tuples
  (parallel research / unrelated cuisine lookups); `want_fanout=True`, `want_branch_count≥2`,
  `want_join_synthesizes=True`. Cardinality spread (2 boundary / 3 / many ceiling) + one L2 row.
- **`FANOUT-decline-NN`** (6 → 10–12) — sequential-dependent tasks that *look* parallelizable, **incl. seeded
  near-miss traps** ("book a trip: flight → hotel around the flight dates → car"; "benchmark A, then use the result
  to tune B"; shared-write-target); `want_fanout=False` — the supervisor must keep it single-branch (the GAIA
  single-agent-wins guard, made a test). A near-miss row that gets fanned out is the headline failure.
- **`FANOUT-fault-NN`** (3 → 5–6) — fault injection: a branch objective designed to fail/time out/straggle;
  `want_fanout=True`, `want_survives_partial=True` — proves the sentinel + per-branch-timeout path (the §3.5a MAST
  bound) on a *live* trace, not just a unit sim.
- **`FANOUT-control-NN`** (3 → 4–5) — trivial single-step tasks + an at-the-floor boundary (2 trivial independent
  writes, below the "<3 don't bother" rule); `want_fanout=False` — the precision guard, mirroring the
  `control-trivial` reflexion rows.

**Analyzer delta:** `analyze_planning_traces.py` gains a `fanout` phase reading the per-branch `delegation_*` +
`join_node` carriers, reporting **fan-out precision** (of the rows we fanned out, how many *should* have been —
the decline cases are the negatives) and **partial-survival rate** — the two halves that match the §3.5a
acceptance bar. Calibration mode first (records, never gates), exactly as the T1/T2 phases.

## 9. Risks

- **Brittle plan (T1).** Mandatory replan gate; without it T1 is *worse* than ReAct on noisy tool output.
- **Reflexion thrash (T2).** D1 budget ceiling + reuse of no-progress detection as a hard stop.
- **Reflexion coupling regression.** If the re-entry decision or critique generation leaks into `reflect_node`
  (or the component starts importing `AgentState`/`langgraph`), the onion boundary in §3.4 is breached and T2 is
  no longer unit-testable in isolation. Guard: the generator + predicate stay pure components; the wrapper holds
  no logic; topology stays in the graph builder.
- **Overconfident self-routing.** Mitigated by design: LLM lives on the evidence-grounded escalation edge,
  never on upfront difficulty estimation (§4).
- **Depth flattener regression.** Phase 0 is the prerequisite; every later tier inherits the L0 collapse if it
  is skipped.
- **Over-investing in T3 ahead of the workload.** T3 is un-deferred (§3.5a) to de-risk the seam, *not* because
  the corpus needs parallel work (§2.3 still holds: ~0 genuine fan-out; GAIA shows single-agent wins). Guard: the
  §3.5a acceptance bar is seam + layer-clean + observable + MAST-bounded — **never** a throughput/goal-met claim;
  build the thin mechanism, do not grow T3 features (waves, nested supervisors) without new parallel-workload
  evidence.
- **Zero-carrier governance fact (§3.7).** A new-tier fact (replan, reflexion critique, delegation handoff) gets
  suppressed in the curated relay on the assumption another observation carries it — the token-seam failure mode,
  which CI cannot catch. Guard: the §3.7 carrier table + the per-phase governance-trace gate; verify the
  substitute carrier actually exports before suppressing anything; never trust green CI over one contradictory
  trace.
- **Reflexion masks a corrupt success.** A T2 loop that turns a failed `goal_met` into a reported success would
  be the governance-missed corrupt success the audit escalates to NON-COMPLIANT. Guard: judge runs on the
  *final* post-reflexion answer; `task.completed` keeps `goal_met`/`unmet_conditions` honest end-to-end (§3.7).
- **Frontend-seam leak.** A new tier that emits a backend type / raw `AgentState` shape across the
  `agent_ui_adapter` SSE surface, or that adds a `middleware/`/`frontend/` import, breaks the ring's
  additive-removal guarantee and F-R8/M1 (§3.6). Guard: new-tier events default to `TrustTraceRecord`
  telemetry (never crosses the seam); UI promotion only via a curated `wire/` `DomainEvent` variant carrying
  `trace_id`, as a separate frontend-ring-scoped change.
- **Supervisor coupling regression (if T3 is un-deferred).** The MAST failure surface (§2.3) re-enters if a
  worker imports `AgentState`, the decomposition planner imports peer components, or inter-worker comms become
  call-backs instead of state/filesystem handoff. Guard: §3.5 binds T3 to the §3.4 onion rules + AGENTS.md AP-2 /
  invariant-5 / no-upward-import before any code is written; workers stay on the existing layer-clean
  `services/tools/` substrate that already passes `tests/architecture/`.
- **Happy-path-only / determinism-theater tests (§7.5).** A new gate shipped with only its acceptance test (no
  rejection test), or an L3/L4 surface asserted as if it were deterministic, produces green CI that proves
  nothing — Anti-Patterns 3 and 6 from the TDD doc, the exact shape behind every incident this repo encodes
  ("one contradictory trace outweighs a clean test suite"). Concretely: a planner test that only checks the
  LLM-plan success path and never the deterministic-floor fallback, or a reflexion test that asserts a single
  mocked critique as a fixed string instead of an aggregated trajectory pass-rate. Guard: §7.5's failure-paths-first
  rule (every gate's rejection test lands before its acceptance test, per TAP-4); L3/L4 surfaces use aggregated
  pass-rates under `@pytest.mark.slow`/`.simulation`, never live LLM in CI; the Pattern-7 dependency assertions in
  `tests/architecture/` run against the test tree too.
