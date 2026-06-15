# OpenManus vs the tiered-loop pipeline (post-implementation + T3 design)

**Status:** research note — refreshed **2026-06-15** after Phases 0–3 shipped and T3 was **design-completed** ([plan §3.5a](../plans/planning_pipeline_tiered_loops.plan.md), [design §B.5](../plans/planning_pipeline_tiered_loops.design.md), [component spec](../plans/t3_supervisor_plan.component.md)).
**Scope:** Fresh comparison of the tier ladder — **T0–T2 as-built**, **T3 design-complete but unbuilt** — against [OpenManus](https://github.com/FoundationAgents/OpenManus). §3–§5 cover head-to-head axes; §3.2 covers the T3 design vs OpenManus multi-agent; §6–§8 are file mapping, flow trace, and parity scorecard.
**Verdict (one line):** OpenManus remains a useful *negative control* — we **lead on every shipped control axis** (replan, GoalJudge reflexion, model tiers, governance trace, OBP layering) and have a **typed, decline-first T3 design** that explicitly rejects OpenManus's tag-regex dispatch and LangChain `create_agent` subagents-as-tools. OpenManus still wins on **one UX mechanic we have not wired** (live plan-status per turn). Its multi-agent flow is a cautionary reference, not a port target.

Protocol IDs referenced below (LP, OBP, tier T0–T3, depth L0–L2) are defined in the design doc's §A Protocol Registry.

---

## 1. What OpenManus is

An open-source [Manus](https://manus.im) clone. Its architecture is a **class-inheritance ladder** plus a thin multi-agent **Flow** layer — *not* a graph.

```
BaseAgent          state enum (IDLE→RUNNING→FINISHED/ERROR), max_steps, memory, is_stuck()
  └─ ReActAgent    abstract think()->bool, act()->str ;  step() = think then maybe act
       └─ ToolCallAgent      tool-calling mechanics
            └─ PlanningAgent  current_step_index, step_execution_tracker, plan-in-prompt
                 └─ Manus     flagship: + browser, python, files, web search
```

Plus:
- **Flow layer** — `BaseFlow` / `PlanningFlow` orchestrate *several* agents over one shared plan.
- **`protocol/a2a`** — agent-to-agent messaging.
- Three entrypoints: `main.py` (single agent), `run_mcp.py` (MCP tools), `run_flow.py` (multi-agent, self-described as **"unstable"**).

Sources: [FoundationAgents/OpenManus](https://github.com/FoundationAgents/OpenManus), [LLM Multi Agents technical analysis](https://llmmultiagents.com/en/blogs/OpenManus_Technical_Analysis), [Hacking OpenManus (Medium)](https://medium.com/@ai-data-drive/hacking-openmanus-inside-the-world-of-ai-agents-b18fe9aba571).

---

## 2. How its three subsystems work (verbatim where it matters)

### 2.1 Planning — plan-once, then linear execute (no replan gate)

`PlanningFlow._create_initial_plan()` asks the LLM (bound to a `PlanningTool`) to emit a step list; on no tool-call it falls back to a default 3-step plan. `PlanningAgent.think()` re-injects the current plan status into the prompt each turn and marks steps via `planning.mark_step`.

**The decisive limitation:** there is no replanning mechanism. Execution follows the linear plan sequence until completion (confirmed by the technical analysis: *"execution simply follows the linear plan sequence until completion"*). Step status is a 4-value enum: `NOT_STARTED → IN_PROGRESS → COMPLETED / BLOCKED`.

### 2.2 Routing — string-tag agent dispatch, single model

Two senses, both thin:

**Agent routing** — `PlanningFlow.get_executor()`:
```python
def get_executor(self, step_type: Optional[str] = None) -> BaseAgent:
    # If step type is provided and matches an agent key, use that agent
    if step_type and step_type in self.agents:
        return self.agents[step_type]
    # Otherwise use the first available executor or fall back to primary agent
    for key in self.executor_keys:
        if key in self.agents:
            return self.agents[key]
    return self.primary_agent
```
The `step_type` comes from a regex over the step text: `re.search(r"\[([A-Z_]+)\]", step)` — i.e. the planner literally writes `[SEARCH]` / `[CODE]` into the step string and the flow parses it back out.

**Model routing** — *none.* Single `model = "gpt-4o"` config. No per-step model selection, no complexity tiering, no escalation/downgrade.

### 2.3 Orchestration — counter + enum `while` loop

`BaseAgent.run()` loops while `current_step < max_steps and state != FINISHED`, calling the abstract `step()`. Termination is max-steps or an agent self-setting `FINISHED`. **No checkpointer, no conditional edges, no DAG.** State/memory is an in-process message list (`update_memory(role, content, ...)`).

The one piece of adaptive control is duplicate-response detection:
```python
def is_stuck(self) -> bool:
    """Check if the agent is stuck in a loop by detecting duplicate content"""
    if len(self.memory.messages) < 2:
        return False
    last_message = self.memory.messages[-1]
    if not last_message.content:
        return False
    duplicate_count = sum(
        1 for msg in reversed(self.memory.messages[:-1])
        if msg.role == "assistant" and msg.content == last_message.content
    )
    return duplicate_count >= self.duplicate_threshold        # default 2

def handle_stuck_state(self):
    """Handle stuck state by adding a prompt to change strategy"""
    stuck_prompt = "Observed duplicate responses. Consider new strategies ..."
    self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
```
Called once per loop in `run()`: `if self.is_stuck(): self.handle_stuck_state()`.

---

## 3. Head-to-head — as-built vs OpenManus

| Axis | OpenManus | This repo (implemented) |
|---|---|---|
| Control flow | linear `while` + state enum | LangGraph `StateGraph`, 3-way evaluate fork, `InstrumentedCheckpointer` ([react_loop.py](../../orchestration/react_loop.py)) |
| Planning (T1) | LLM plan-once at flow start; **no replan** | LLM plan in `route_node` via `PlanGenerator` + `build_plan_artifact_llm`; **replan gate** via `plan_is_stale` on re-entry ([plan_builder.py:278](../../components/plan_builder.py)); shadow-first `plan_source` flag |
| Live plan status in prompt | `_get_plan_text()` every executor turn | **Not wired** — depth sentence only (`build_planning_instructions`); plan lives in `files[plan_ref]` + trace, not re-injected each `call_llm` turn |
| Replan on surprise | ❌ | ✅ deterministic rebuild when tool fails / `surprising` flag; `replan_count` on state; replan **does not** re-call LLM (floor only) |
| Depth routing (Phase 0) | none | `select_planning_depth` → L0/L1/L2, memoized per `task_id` ([router.py:97](../../components/router.py)); collapse fixed |
| Model routing | single `gpt-4o` | `select_model` 5-branch cascade + budget downgrade ([router.py:286](../../components/router.py)) |
| Reflexion (T2) | none | `reflect_node` + `components/reflexion.py`; critiques folded in `call_llm_node`; **off by default** (`reflexion_enabled=False`) |
| Escalation (Phase 3) | prepend stuck prompt | `decide_escalation` composes GoalJudge verdict (primary) + `prose_repeat` (D3 tertiary); budget ceiling via `decide_reentry` |
| Tool-loop stuck | none | `count_trailing_repeats` → no-progress wrap-up ([evaluator.py:62](../../components/evaluator.py)) |
| Prose-loop stuck (D3) | `is_stuck()` string equality | `classify_no_progress` → `prose_repeat` → `reflect_node` when budget left ([evaluator.py:102](../../components/evaluator.py)) |
| Semantic stop | max_steps / self-terminate | GoalJudge + `evaluate_task_outcome` + corrupt-success guard |
| Multi-agent | A2A, "unstable" `PlanningFlow`; `[TAG]` regex dispatch | **T3 design-complete, not built** — `supervisor_plan.py` (decline-first) → `Send` fan-out → `worker`/`join`; substrate in `task_tool` + `delegation_dispatcher` ([plan §3.5a](../plans/planning_pipeline_tiered_loops.plan.md)) |
| Governance | stdout logger | BlackBox, PhaseLogger, AgentFacts, guardrails, eval capture, GTP audit skill |
| Layering | agents mutate plan in-place | OBP: components return data; topology in graph; loop closes through state |

**Net:** T0–T2 are shipped; T3 is specced but not coded. OpenManus is still the simpler reference for *plan-object UX* (status text every turn), but we are strictly ahead on *planning policy* (replan), *recovery* (Reflexion + GoalJudge), and *observability*. On multi-agent, we have a **designed** path that rejects their brittle dispatch — not yet a running one. The one remaining borrow from their single-agent loop is Idea B (live plan-status render).

### 3.1 As-built topology — T0–T2 (differs from the design sketch)

The design doc drew a separate `planner_node` and an `execute_tool → planner` back-edge. **Implementation chose a smaller shape** ([impl.md §4](../plans/planning_pipeline_tiered_loops.impl.md)):

```text
START → guard_input → route → call_llm → execute_tool → evaluate
                              ↑              │              │
                              │              └──────────────┘
                              │         continue / reflect / done
                              └──── reflect (T2, when enabled)
```

- **T1 planning lives inside `route_node`**, not a separate graph node — the plan is built/memoized/rebuilt when `plan_is_stale` fires on the existing `continue → route` edge.
- **T2 reflect** is the only additive node; evaluate forks to `reflect → route` when `decide_escalation == "escalate"`.
- **Flags:** `plan_source` (`deterministic` \| `shadow` \| `generated`, default deterministic); `reflexion_enabled` (default false); `max_reflexion_attempts=2` (D1 settled).

### 3.2 T3 design topology — vs OpenManus multi-agent (not built)

T3 was **un-deferred 2026-06-15** as a *seam de-risking* exercise, not because the real corpus has parallel work (§2.3 still holds: ~0 genuine fan-out). The acceptance bar is **layer-clean + observable + MAST-bounded**, not throughput or goal-met rate.

```text
route ─→ supervisor ──(conditional edge: list[Send])──→ ⟨ worker × N, parallel ⟩ ─→ join ─→ evaluate
              │  plan_delegations() in components/              │  LocalLLMDelegationDispatcher
              │  validate_independence() — decline-first        │  try/except → sentinel per branch
              └─ no decompose logic in the node                  └─ worker_results[] reducer (operator.add)
```

| Aspect | OpenManus `PlanningFlow` | Our T3 design |
|---|---|---|
| Dispatch mechanism | Regex `[TAG]` over step prose → `get_executor(step_type)` | `SupervisorPlan` typed data → `list[Send("worker", payload)]` |
| Decompose decision | Planner writes agent tags into step strings | `plan_delegations()` reads **existing T1 `PlanArtifact`**, classifies independence — does not re-plan |
| Default when uncertain | First available executor | **Decline** → single-thread T0/T1 (GAIA guard: fan-out on dependent work is harmful) |
| Independence gate | none | `validate_independence()` — any `depends_on` edge → decline |
| Worker substrate | In-process agent instances | Existing `DelegationDispatchRequest` + filesystem handoff (`task_tool`) |
| Concurrency | Sequential step loop | LangGraph `Send` + async `dispatch()` on dispatcher (sync `thread.join()` would serialize) |
| Pattern rejected | — | LangChain `create_agent(subagents-as-tools)` — same `Send` underneath but domain logic leaked into framework |
| Observability | stdout | Per-branch `delegation_*` `TrustTraceRecord` carriers + join → GoalJudge on **merged** answer |
| Stability | Self-described **"unstable"** | Protocol-D failure matrix: one branch raises/timeouts → join survives; all fail → degraded answer, judge still runs |

**Headline design bet vs OpenManus:** their multi-agent routing is *prose-tag dispatch over a linear plan*; ours is *typed decline-first fan-out over T1's plan artifact*, with the load-bearing test being **"dependent task is NOT fanned out"** ([component spec §2](../plans/t3_supervisor_plan.component.md)). OpenManus's `PlanningFlow` is the negative control that justifies this shape — not something to port.

**What exists today:** `services/tools/task_tool.py` and `services/tools/delegation_dispatcher.py` (layer-clean, verified). **What does not:** `components/supervisor_plan.py`, `supervisor_node`/`worker_node`/`join_node`, `worker_results` state key, async dispatch, fan-out corpus ([t3_fanout_corpus.plan.md](../plans/t3_fanout_corpus.plan.md)).

---

## 4. The three borrowable ideas — trade-off ledger

Each idea is rated **add / replace / modify / reject**, with the repo anchor that already covers it.

### Idea A — `is_stuck()` / `handle_stuck_state()` (pre-LLM stuck-breaker)

**OpenManus mechanism:** if the last assistant message string-equals ≥2 earlier ones, prepend a "change strategy" line to the next prompt.

**Already in repo, stronger:** `count_trailing_repeats` ([evaluator.py:62](../../components/evaluator.py)) counts the trailing run of tool_results sharing a normalized `(tool_name, tool_input)` key *or* an echo-normalized `tool_output`. It feeds the **no-progress graceful wrap-up** ([react_loop.py:1135-1156](../../orchestration/react_loop.py)): at `no_progress_repeat_threshold` (=3, [base_config.py:40](../../services/base_config.py)) it injects a `no_progress_wrapup` directive, strips tool schemas, records a `STEP_PLANNED{no_progress:true}` governance event, and sets the idempotent `no_progress_directive_sent` flag ([state.py:114](../../orchestration/state.py)).

Where OpenManus matches on *assistant prose string equality* (brittle: any rephrase escapes it), ours matches on *tool-call signature and normalized output* (catches the search-stub echo case), is config-gated, governance-traced, and idempotent.

| | Add | Replace | Modify | **Reject** |
|---|---|---|---|---|
| **Verdict** | | | | ✅ already implemented, in a superior form |

**Decision needed from you:** none — unless you want the *prose-duplicate* signal as an *additional* trigger (OpenManus catches a stuck LLM that keeps emitting the same text **without** calling a tool; `count_trailing_repeats` only looks at `tool_results`). That is the single genuine gap → see Idea A′.

#### Idea A′ — prose-duplicate detection → T2 escalation ✅ **SHIPPED**

**Implemented as D3:** `classify_no_progress` returns `tool_repeat` \| `prose_repeat` \| `none`; `decide_escalation` routes `prose_repeat → reflect_node` when budget remains ([evaluator.py:102](../../components/evaluator.py), [router.py:235](../../components/router.py)). Unlike OpenManus, recovery writes to `reflections[]` and re-enters through the graph — no in-place `next_step_prompt` mutation.

| | Add | Replace | Modify | Reject |
|---|---|---|---|---|
| **Verdict** | | | ✅ **done** | |

### Idea B — live plan-status injected into every turn's prompt ⚠️ **PARTIAL GAP**

**OpenManus mechanism:** `PlanningFlow._get_plan_text()` re-renders steps + statuses into every executor prompt.

**Our as-built:** T1 produces a real `PlanArtifact` (LLM or floor), memoized on `plan_artifact` / `plan_artifact_task_id`, fingerprinted on `STEP_PLANNED`, stored in `files[plan_ref]` for GoalJudge. **`call_llm_node` does not re-inject step titles/status each turn** — only `build_planning_instructions(planning_depth)` plus accumulated reflexion critiques. The executor therefore lacks OpenManus's "you are on step 2 of 4, status IN_PROGRESS" steering during mid-task tool loops.

- **Impact:** replan still fires on surprise (`plan_is_stale`); judge still scores against `success_conditions`; trace still exports `plan_summary` on change. The gap is *in-loop steering*, not *plan existence*.
- **Fix shape (if wanted):** pure `render_plan_status(plan_artifact, step_index) -> str` in `plan_builder.py` (OBP-1), appended in `call_llm_node` alongside planning instructions (OBP-3). No graph change.

| | **Add** | Replace | Modify | Reject |
|---|---|---|---|---|
| **Verdict** | yes — small follow-up | | | |

### Idea C — `get_executor()` tag-dispatch (multi-agent routing)

**OpenManus mechanism:** planner writes `[AGENT]` into step text; flow regexes it out and dispatches.

**Our T3 design (Phase 4, not built):** `plan_delegations()` returns a typed `SupervisorPlan` with `FanoutDecision` + `Delegation` branches; the node emits `list[Send]` only after `validate_independence()` passes. Decline is the safe default (conditions 1–4 in [component spec §2](../plans/t3_supervisor_plan.component.md) are all rejections, tested before the one fan-out acceptance).

**Assessment:** OpenManus's tag-regex dispatch is exactly the brittle seam OBP forbids. T3 is now **designed** to solve the same problem with typed data + decline-first independence checks — but **not yet implemented**. OpenManus labelling its own flow "unstable" remains the cautionary data point; our design explicitly bounds MAST failure modes (sentinel workers, per-branch timeout, join on survivors).

| | Add | Replace | Modify | **Reject** |
|---|---|---|---|---|
| **Verdict** | ✅ T3 design adopts the *problem*, rejects the *mechanism* | | | ✅ reject OpenManus tag-regex; do not port |

**Decision needed from you:** none — the design is settled. Build Phase 4 when ready; routing stays typed supervisor decision, never tag-regex.

---

## 5. Summary — post-implementation disposition

| Idea | Repo anchor | Disposition |
|---|---|---|
| A — tool-call stuck-breaker | `count_trailing_repeats` + no-progress wrap-up | **Rejected** (already superior) |
| A′ — prose-duplicate signal | `classify_no_progress` | **Shipped** (Phase 2 / D3) |
| A′ — prose → reflect escalation | `decide_escalation` + `reflect_node` | **Shipped** (gated on `reflexion_enabled` + D1 ceiling) |
| B — live plan-status in prompt | *not yet* — plan in state/trace only | **Open follow-up** (OBP-shaped prompt addendum) |
| C — `[TAG]` agent dispatch | T3 `supervisor_plan.py` (decline-first, not built) | **Rejected** (OpenManus mechanism); **designed replacement** (typed Send fan-out) |

**Bottom line:** T0–T2 closed every single-agent gap OpenManus surfaced except live plan-status injection. T3 closes the multi-agent *design* gap with a decline-first supervisor that rejects OpenManus's dispatch shape — code pending Phase 4. Reflexion and prose-stuck recovery are implemented but **config-gated off in steady state** — promote `plan_source=generated` and `reflexion_enabled=True` on eval evidence, same shadow→consume discipline as GoalJudge.

---

## 6. File-by-file mapping (OpenManus → this repo)

**Source tree note.** OpenManus `main` (verified 2026-06-14) has refactored planning out of the agent
inheritance ladder and into the Flow layer. The historical `PlanningAgent` class described in §1 and older
write-ups is **not** a separate file on `main` today — plan-once-linear execution lives in
`app/flow/planning.py` + `app/tool/planning.py`, while single-agent ReAct is `Manus → ToolCallAgent →
ReActAgent → BaseAgent`. The mapping below uses the **current** tree; rows marked *(historical)* note where
older docs placed the same concern.

### 6.1 Orchestration & control loop

| OpenManus | Role | This repo (as-built) |
|---|---|---|
| `app/agent/base.py` — `BaseAgent.run()` | `while` loop, max-steps, state enum | `build_graph()` — evaluate 3-way fork (`continue`/`reflect`/`done`) |
| `app/agent/base.py` — `is_stuck()` / `handle_stuck_state()` | Prose-duplicate → prepend prompt | `classify_no_progress` → `decide_escalation` → `reflect_node` (D3); tool thrash → wrap-up |
| `app/agent/react.py` — `step()` | Abstract ReAct step | `call_llm_node` + `execute_tool_node` + `evaluate_node` |
| `app/flow/planning.py` — `PlanningFlow` | Plan-once, linear step loop | T1 in `route_node`: `PlanGenerator` + `build_plan_artifact_llm`; replan via `plan_is_stale` on re-entry |
| `app/schema.py` — `Memory`, `Message` | In-process chat list | `AgentState` + `reflections[]`, `replan_count`, memoized `plan_artifact` |
| *(historical)* `PlanningAgent` | Plan status in every `think()` | **Gap:** no per-turn plan-status render in `call_llm_node` (Idea B) |

### 6.2 Planning artifacts

| OpenManus | Role | This repo (as-built) |
|---|---|---|
| `app/tool/planning.py` — `PlanningTool` | In-memory plan store | `PlanArtifact` in state + `files[plan_ref]`; no tool surface |
| `app/flow/planning.py` — `_create_initial_plan()` | LLM → step list | `PlanGenerator` + `plan_builder_prompt.j2`; floor = `build_plan_artifact` |
| `app/flow/planning.py` — `_get_plan_text()` | Live status injected per step | **Not implemented** — trace exports `plan_summary` on fingerprint change only |
| `app/flow/planning.py` — replan | *(none)* | `plan_is_stale` → deterministic rebuild in `route_node`; `replan_count` increments |

### 6.3 Routing & model selection

| OpenManus | Role | This repo |
|---|---|---|
| `app/config.py` — single `model = "gpt-4o"` | One model for all steps | `services/base_config.py` — `ModelProfile` list with `fast` / `capable` tiers |
| *(none)* | Model routing | `components/router.py` — `select_model()` 5-branch cascade |
| `PlanningFlow.get_executor(step_type)` | Agent routing by prose tag | **T3 (designed):** `plan_delegations()` → `SupervisorPlan` + `validate_independence()` → `Send`; today: single agent; `select_planning_depth()` + `select_model()` separate |
| `app/flow/planning.py` — agent list in system prompt | Planner told which agents exist | Single agent today; `AgentFacts` + capability list at guard |

### 6.4 Tools

| OpenManus | Role | This repo |
|---|---|---|
| `app/tool/base.py`, `tool_collection.py` | Tool base + collection | `services/tools/registry.py` — `ToolRegistry` |
| `app/tool/bash.py` | Shell | `services/tools/shell.py` (allowlist validators) |
| `app/tool/str_replace_editor.py`, `file_operators.py` | File I/O | `services/tools/file_io.py`, `file_tools.py` (path sandbox) |
| `app/tool/web_search.py`, `app/tool/search/*` | Web search | `services/tools/web_search.py` (stub + echo-normalization tests) |
| `app/tool/python_execute.py` | Python REPL | `services/tools/sandbox.py` |
| `app/tool/browser_use_tool.py` | Browser automation | *(not in core registry)* — separate concern |
| `app/tool/terminate.py` | Agent self-terminates | `evaluate_node` + `check_continuation` + GoalJudge |
| `app/tool/planning.py` | Plan CRUD tool | `components/plan_builder.py` + `files` state (no tool surface) |
| `app/tool/mcp.py`, `app/agent/mcp.py` | MCP client tools | MCP via adapter layer; `run_mcp.py` analogue is deployment-specific |

### 6.5 LLM, prompts, config

| OpenManus | Role | This repo |
|---|---|---|
| `app/llm.py` — `LLM.ask` / `ask_tool` | Direct LLM wrapper | `services/llm_config.py` — `LLMService`, LiteLLM, tier profiles |
| `app/prompt/*` — inline Python strings | Hardcoded prompts | `prompts/*.j2` via `PromptService.render_prompt()` (H1) |
| `app/config.py` | Monolithic config | `services/base_config.py`, `components/routing_config.py`, env-driven GoalJudge reader |
| `app/logger.py` | stdlib logging | `logging.json` per-concern loggers (H4) |

### 6.6 Governance, verification, observability — the parity gap

OpenManus has **no first-class equivalent** for most of this column. Reaching parity would be a greenfield
build, not a port.

| Concern | OpenManus | This repo |
|---|---|---|
| Execution trace / audit log | `app/logger.py` (stdout) | `services/governance/black_box.py` — `TraceEvent`, JSONL export, Langfuse relay |
| Phase-scoped decisions | *(none)* | `services/governance/phase_logger.py` — `Decision`, `WorkflowPhase` |
| Agent identity / capabilities | *(none)* | `services/governance/agent_facts_registry.py` + `trust/models.py` — `AgentFacts` |
| Input guardrail | *(none)* | `services/guardrails.py` — LLM-as-judge injection gate; `guard_input_node` |
| Output guardrail | *(none)* | Output validation + PII/API-key scan in guardrails pipeline |
| Tool authorization | *(none)* | `verify_authorize_log_node` when policy service wired |
| Eval capture (every LLM call) | *(none)* | `services/eval_capture.py` — `user_id`, `task_id`, `target` tags (H5) |
| Task understanding artifact | *(none)* | `components/task_understanding.py` + memoized `task_understanding` state |
| Goal verification | *(none)* | `components/goal_judge.py` — rubric judge at `evaluate_node` |
| Corrupt-success guard | *(none)* | `evaluate_task_outcome` + I2 no-progress downgrade; GoalJudge gate |
| Trace audit contract | *(none)* | `governance-trace-audit` skill — four-pillar GTP |
| Frontend seam | *(none)* | `frontend/lib/wire/`, `middleware/telemetry_bridge.py` — FSP two-tier events |
| Architecture CI enforcement | *(none)* | `tests/architecture/` — LP, OBP, P7 dependency rules |

### 6.7 Alternate structured-reasoning skeleton (in-repo, unwired)

OpenManus has no direct counterpart. This is evidence the repo already wanted multi-phase reasoning before T1:

| OpenManus (concept) | This repo |
|---|---|
| Multi-phase analyze loop | `StructuredReasoning/orchestration/pyramid_loop.py` — decompose/hypothesize/act/synthesize (PR 1 skeleton) |
| Structured output schema | `StructuredReasoning/trust/pyramid_schema.py` |
| Parse + retry | `StructuredReasoning/components/pyramid_parser.py` |

T1 planning is wired through `route_node`; the pyramid loop remains an optional second consumer of the same OBP-shaped components.

### 6.8 T3 supervisor (designed, not built)

| OpenManus | Role | This repo (T3 design — Phase 4) |
|---|---|---|
| `PlanningFlow.get_executor()` | Regex `[TAG]` → agent instance | `supervisor_node` → `plan_delegations()` → `list[Send("worker", …)]` |
| `PlanningFlow` step loop | Sequential executor per step | Parallel `worker_node × N` via LangGraph `Send` |
| In-process agent memory | Shared within flow | `DelegationDispatchRequest` → `delegation_dispatcher` → filesystem handoff |
| *(none)* | Independence check before fan-out | `validate_independence()` — any `depends_on` → decline to T1 |
| *(none)* | Partial branch failure handling | Sentinel worker + per-branch timeout; `join_node` synthesizes from survivors |
| `app/protocol/a2a` | Agent-to-agent messaging | `TrustTraceRecord` `delegation_*` carriers per branch (GTP-1) |
| *(none)* | Join + verify merged answer | `join_node` → existing `evaluate` (GoalJudge on synthesized output) |

Substrate already exists: [`task_tool.py`](../../services/tools/task_tool.py), [`delegation_dispatcher.py`](../../services/tools/delegation_dispatcher.py). Component + nodes: [`t3_supervisor_plan.component.md`](../plans/t3_supervisor_plan.component.md), impl §7.

---

## 7. Method-level flow mapping (one task, both systems)

```text
OPENMANUS (run_flow.py → PlanningFlow)
──────────────────────────────────────
1. PlanningFlow.execute(input)
2. _create_initial_plan → LLM + PlanningTool.create → steps[]
3. while step = next non-completed:
     a. get_executor([TAG] from step text)
     b. executor.run(step_prompt + plan_status)   ← plan text every turn
     c. _mark_step_completed                      ← always COMPLETED; no replan
4. _finalize_plan → LLM summary
5. return string

THIS REPO (as-built — reflexion enabled, plan_source=generated)
────────────────────────────────────────────────────────────────
1. START → guard_input (injection gate + AgentFacts)
2. route → memoized depth (L0/L1/L2) + select_model + TaskUnderstanding
         → PlanGenerator (if shadow/generated) → PlanArtifact memoized
         → plan_is_stale? → deterministic replan + replan_count++
3. call_llm → depth instructions + prior reflexion critiques + tools
            → no-progress wrap-up if tool_repeat ≥ threshold
4. execute_tool → registry + cache + stamped tool_results[]
5. evaluate → classify_outcome + GoalJudge → persist verdict carriers
6. continue → route (loop) | reflect → route (T2) | done → reasoning_recap → END

THIS REPO (T3 planned — when route selects fan-out path)
──────────────────────────────────────────────────────────
2b. route → supervisor → plan_delegations(T1 PlanArtifact)
         → validate_independence? decline → call_llm (single-thread)
         → fan_out → Send × N → worker (async dispatch) → worker_results[]
         → join → synthesize → evaluate (GoalJudge on merged answer)
         → same continue / reflect / done fork as above
```

| Step | OpenManus | This repo (as-built) | Who leads |
|---|---|---|---|
| Loop driver | `BaseAgent.run()` while | LangGraph conditional edges + checkpointer | **Us** |
| Plan create | `_create_initial_plan` (always LLM) | `PlanGenerator` + floor; default deterministic | Tie (they always LLM; we shadow-first) |
| Plan status in prompt | `_get_plan_text` each step | depth sentence only | **OpenManus** |
| Replan on surprise | ❌ | `plan_is_stale` → floor rebuild on `route` re-entry | **Us** |
| Model pick | none | `select_model` cascade | **Us** |
| Stuck (tools) | none | `count_trailing_repeats` → wrap-up | **Us** |
| Stuck (prose) | `is_stuck` → prepend | `prose_repeat` → `reflect_node` | **Us** (stronger recovery) |
| Verification | none | GoalJudge + reflexion loop | **Us** |
| Trace / audit | stdout | BlackBox + GTP four-pillar contract | **Us** |
| Multi-agent dispatch | `[TAG]` regex → executor | T3: typed `SupervisorPlan` → `Send` (designed, not built) | **Us** (design); neither shipped |

---

## 8. Parity scorecard (T0–T2 shipped, T3 designed)

### 8.1 Capability matrix

| Capability | OpenManus | Us (steady-state defaults) | Us (flags on: `plan_source=generated`, `reflexion_enabled=True`) |
|---|---|---|---|
| LLM plan object | ✅ always | ⚠️ deterministic floor (regex split) | ✅ + replan |
| Live plan status in executor prompt | ✅ | ❌ | ❌ *(Idea B — open)* |
| Replan on surprise | ❌ | ✅ (floor rebuild, not LLM re-plan) | ✅ |
| Depth routing L0/L1/L2 | ❌ | ✅ (memoized, collapse fixed) | ✅ |
| Model tiers + escalation | ❌ | ✅ | ✅ |
| Tool-loop stuck detect | ❌ | ✅ | ✅ |
| Prose-loop stuck → recovery | ⚠️ prepend only | ✅ (when reflexion on) | ✅ |
| GoalJudge semantic stop | ❌ | ✅ | ✅ |
| Reflexion on failed/partial | ❌ | ⚠️ wired, off by default | ✅ |
| Governance trace (GTP) | ❌ | ✅ | ✅ |
| Multi-agent supervisor | ⚠️ unstable, tag-regex | ❌ not built | 🔮 designed (Phase 4); decline-first `supervisor_plan` |

### 8.2 What OpenManus would need for *our* parity

Unchanged from pre-build analysis — items 1–9 are prerequisites before replan/reflexion mean the same thing:

| # | Capability | We have | OpenManus |
|---|---|---|---|
| 1–9 | Trace, guardrails, validators, eval capture, TU, GoalJudge, model tiers, LangGraph, layer CI | ✅ shipped | ❌ greenfield |
| 10 | Replan gate | ✅ `plan_is_stale` | ❌ |
| 11 | Reflexion + budget ceiling | ✅ T2 (config-gated) | ❌ |
| 12 | Frontend trace seam + GTP audit | ✅ FSP ring | ❌ |
| 13 | Typed supervisor + decline-first fan-out | 🔮 designed (Phase 4) | ⚠️ tag-regex, unstable |

### 8.3 T3 design vs OpenManus multi-agent (detailed)

| Dimension | OpenManus | Our T3 design | Build status |
|---|---|---|---|
| When to fan out | Planner embeds `[TAG]` in steps; flow always iterates steps | `plan_delegations()` — only if ≥2 **independent** branches after T1 plan exists | 🔮 not built |
| When to decline | N/A (always picks an executor) | L0, `<2` steps, sequential-dependent, no generator, failed independence check | 🔮 spec'd + failure-first tests planned |
| Worker isolation | Shared agent instances, in-process memory | `DelegationDispatchRequest` + filesystem handoff; worker never sees `AgentState` (OBP-M1) | substrate ✅; nodes 🔮 |
| Partial failure | Unclear / unstable flow | Sentinel per branch + timeout; join synthesizes from survivors | 🔮 Protocol-D matrix planned |
| Eval corpus | none | Synthetic fan-out corpus (~30 rows, cap 40); **decline rows weighted heaviest** | 🔮 [t3_fanout_corpus.plan.md](../plans/t3_fanout_corpus.plan.md) |
| Honest metric | throughput implied | seam + observable + MAST-bounded — **not** goal-met or latency | explicit in plan §3.5a |

### 8.4 Remaining follow-ups (us ← OpenManus or plan)

| Item | Source | Effort | Notes |
|---|---|---|---|
| Live plan-status prompt injection | OpenManus Idea B | Small | Pure component render + `call_llm_node` append; no graph change |
| LLM re-plan on surprise | Plan §2.2 (optional) | Medium | Today replan uses deterministic floor only — safer/cheaper, less adaptive |
| Promote `plan_source` / `reflexion_enabled` | Eval gates | Ops | Shadow→consume; steady state unchanged until evidence |
| **T3 Phase 4 build** | Plan §3.5a, design §B.5 | Large | `supervisor_plan.py` + Send nodes + async dispatch + fan-out corpus; seam de-risk, not workload-driven |
| Governance trace audit (Phases 0–3) | Plan §3.7 | Medium | From-step-0 trace through GTP skill — open acceptance item |
| D2 entry LLM-nudge | Plan §6 | Skipped | Phase 3 chose heuristic-only entry; escalation intelligence on evidence edge |

---

## 9. Quick reference links

| Document | Purpose |
|---|---|
| [planning_pipeline_tiered_loops.impl.md](../plans/planning_pipeline_tiered_loops.impl.md) | **As-built** file map (Phases 0–3), Phase 4 planned |
| [planning_pipeline_tiered_loops.plan.md](../plans/planning_pipeline_tiered_loops.plan.md) | What/why, §0 as-built reconciliation, §3.5a T3 design |
| [planning_pipeline_tiered_loops.design.md](../plans/planning_pipeline_tiered_loops.design.md) | Protocol registry (LP/OBP/GTP/FSP), §B.5 T3 crosswalk |
| [t3_supervisor_plan.component.md](../plans/t3_supervisor_plan.component.md) | T3 component contract — decline-first decompose logic |
| [t3_fanout_corpus.plan.md](../plans/t3_fanout_corpus.plan.md) | Synthetic T3 eval corpus (~30 rows, decline-weighted) |
| [components/reflexion.py](../../components/reflexion.py) | T2 pure generator + `decide_reentry` (shipped) |
| [components/plan_generator.py](../../components/plan_generator.py) | T1 LLM boundary (shipped) |
| [services/tools/delegation_dispatcher.py](../../services/tools/delegation_dispatcher.py) | T3 worker substrate (exists; needs async dispatch) |
| [tests/orchestration/test_tier_topology_sim.py](../../tests/orchestration/test_tier_topology_sim.py) | Replan + reflexion Protocol-D sims |
| [OpenManus `app/flow/planning.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/flow/planning.py) | Their plan-once-linear + multi-agent reference |
| [OpenManus `app/agent/base.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/agent/base.py) | Their loop + `is_stuck` |
