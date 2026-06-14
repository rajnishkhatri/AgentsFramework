# OpenManus as prior art for the tiered-loop redesign

**Status:** research note (documentation-only; changes no source).
**Scope:** Does the [OpenManus](https://github.com/FoundationAgents/OpenManus) project offer borrowable ideas for our **planning**, **routing**, and **orchestration** redesign (see [planning_pipeline_tiered_loops.plan.md](../plans/planning_pipeline_tiered_loops.plan.md) and [.design.md](../plans/planning_pipeline_tiered_loops.design.md))? §6–§8 add a **file-by-file mapping**, **method-level flow trace**, and **Phase 0/1 vs governance parity** walkthrough.
**Verdict (one line):** OpenManus is a useful *negative control* — it confirms our architectural bets by sitting one generation behind them on every axis the redesign targets. There are **three concept-level ideas worth examining**, and on inspection **all three already exist in this repo in a stronger form**. Nothing here is a commitment; §4 is a trade-off ledger for you to decide add / replace / modify / reject.

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

## 3. Head-to-head with our design

| Axis | OpenManus | This repo / the tiered-loop plan |
|---|---|---|
| Control flow | linear `while` + state enum | LangGraph `StateGraph`, conditional edges, `InstrumentedCheckpointer` ([react_loop.py:1](../../orchestration/react_loop.py)) |
| Replanning | **none** (plan-once-linear) | **T1 replan gate** is the whole point of T1 (design §B.2/§B.4) |
| Complexity routing | `[TAG]` regex → agent | `select_planning_depth` → L0/L1/L2 ([router.py:72](../../components/router.py)) driving the tier ladder |
| Model routing | single `gpt-4o` | tiered model profiles + `model_history` / `rollback_count` ([state.py:56,121](../../orchestration/state.py)) |
| State / memory | in-process message list | `AgentState` typed reducers, dedup, checkpoint-safe memoization ([state.py](../../orchestration/state.py)) |
| Multi-agent | A2A msgs, "unstable" flow | **T3 supervisor deferred** on corpus + MAST evidence (plan §2.3) |
| Reflexion | none | **T2** `reflect_node` (design §B.3) |
| Stuck / no-progress | string-equality on last msg | `count_trailing_repeats` normalized key + echo-normalized output ([evaluator.py:62](../../components/evaluator.py)) |
| Layering discipline | agents reach into plan & each other | OBP: loop closes through shared state, never call-stack (design §A.2) |

**Net:** adopting OpenManus's model would be a *regression* past our LangGraph topology, and its agent↔plan↔agent reach-ins directly violate OBP. It is not an architecture to copy from. Its value is as evidence:

- Its multi-agent flow is explicitly **"unstable"** → independent confirmation of our §2.3 decision to **defer T3** rather than build a supervisor now.
- Its plan-once-linear model with no replan gate is exactly the gap **T1's replan gate** closes → confirms T1 is the right first rung.
- Its single-model config is the absence our depth-routing already fills.

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

#### Idea A′ — prose-duplicate detection as a T2 escalation trigger (the one real candidate)

The redesign's T2 (Reflexion) needs **entry triggers**. Today's signals are tool-call no-progress and `consecutive_errors` ([react_loop.py:1480](../../orchestration/react_loop.py)). A stuck loop that re-emits identical *assistant content* with no tool call is currently only caught indirectly. OpenManus's `is_stuck` is precisely that signal.

- **Modify, not add:** rather than port the method, extend the existing no-progress predicate to also count trailing identical assistant-message content, and route that to the **T2 reflect_node** escalation fork (design §B.4) instead of OpenManus's prompt-prepend.
- **OBP fit:** the duplicate-detection stays a pure predicate over state in `components/` (OBP-2); the escalation edge lives in the graph builder (OBP-4). No call-stack reach-in — unlike OpenManus mutating `self.next_step_prompt`.
- **Cost:** one more boolean over `messages`; near-zero. **Risk:** false-positive escalation on legitimately repeated short confirmations → gate behind a `threshold` and a min-content-length, mirroring `count_trailing_repeats`'s `bool(last_output)` guard.

| | Add | Replace | **Modify** | Reject |
|---|---|---|---|---|
| **Verdict** | | | ✅ accepted: extend existing predicate to a `kind`, route `prose_repeat → reflect_node` | |

**Decision (settled):** accepted as **modify** — fold the prose-duplicate signal into the existing no-progress
predicate (return a `kind`, not just an int) and route it to T2, gated on the D1 reflexion budget. Recorded as
[design question D3](../plans/planning_pipeline_tiered_loops.design.md#d-open-questions-inherited-from-the-plan);
thresholds (`min-content-length`, one-shot-per-cause) are settled there before Phase 2/3, not built now.

### Idea B — live plan-status injected into every turn's prompt

**OpenManus mechanism:** `PlanningAgent.think()` re-renders the plan (steps + statuses) into the prompt each turn; `step_execution_tracker` holds per-step status.

**Already in repo, partially:** we memoize a plan-time `task_understanding` artifact (restated intent + success conditions) once at step 0 ([state.py:87-99](../../orchestration/state.py)) and render planning instructions per depth via `build_planning_instructions` ([react_loop.py:1115](../../orchestration/react_loop.py)). What we do **not** yet do is re-inject *live per-step plan status* every turn — because T0 (today) has no multi-step plan object to track. That artifact only appears at **T1** (`planner_node` emits a plan; design §B.2).

So Idea B is not redundant — it's a **T1 implementation detail we'll need anyway**: once T1 produces a plan, the executor turns should see current step + status, which is the natural input to the **T1 replan gate** (you can't decide to replan without knowing which steps are done/blocked).

- **OBP fit:** plan-status *rendering* is a pure component function (string from state); *injection* is the node wrapper appending to messages (OBP-1/OBP-3). Status *transitions* are state writes through reducers, not in-place mutation of a shared plan object (contrast OpenManus's `step_statuses[i] = ...` fallback).
- **Cost:** prompt-token growth proportional to plan length → bounded by the same depth gate that bounds plan size. **Risk:** stale status if a step's reducer and the render race → use the existing memoize-and-compare pattern (`last_plan_fingerprint`, [state.py:86](../../orchestration/state.py)).

| | **Add** | Replace | Modify | Reject |
|---|---|---|---|---|
| **Verdict** | yes, as part of T1 (not a separate feature) | | | |

**Decision needed from you:** none new — this is absorbed into the T1 build (design §B.2/§B.4). Worth a one-line callout in the design that the plan-status render feeds the replan gate.

### Idea C — `get_executor()` tag-dispatch (multi-agent routing)

**OpenManus mechanism:** planner writes `[AGENT]` into step text; flow regexes it out and dispatches.

**Assessment:** this is the **T3 supervisor problem** in its crudest form, and OpenManus labelling its own flow "unstable" is the cautionary data point. Regex-over-prose routing is exactly the kind of brittle seam our OBP (typed boundary, pure predicate over scalars — OBP-2/OBP-M2) exists to forbid.

| | Add | Replace | Modify | **Reject** |
|---|---|---|---|---|
| **Verdict** | | | | ✅ reject for now; reinforces deferring T3 (plan §2.3) |

**Decision needed from you:** none — confirms the existing defer-T3 stance. If T3 is ever built, routing must be a typed supervisor decision, **not** tag-regex.

---

## 5. Summary of decisions surfaced

| Idea | Repo anchor | Disposition |
|---|---|---|
| A — tool-call stuck-breaker | `count_trailing_repeats` + no-progress wrap-up | **Rejected** (already superior) |
| A′ — prose-duplicate **signal** | extend no-progress predicate to a `kind` (`tool_repeat`/`prose_repeat`/`none`) | **Accepted** → folded into [design §D D3](../plans/planning_pipeline_tiered_loops.design.md#d-open-questions-inherited-from-the-plan) |
| A′ — prose-duplicate → **T2 escalation** | route `prose_repeat → reflect_node` (OBP-4 edge), gated on D1 budget | **Accepted** → [design §D D3](../plans/planning_pipeline_tiered_loops.design.md#d-open-questions-inherited-from-the-plan) (settle thresholds there) |
| B — live plan-status in prompt | absorbed into T1 `planner_node` + replan gate | **Add as part of T1** (no separate feature) |
| C — `[TAG]` agent dispatch | OBP typed boundary; defer-T3 | **Rejected**; reinforces §2.3 |

**Bottom line:** OpenManus contributes confidence, not code. The one net-new idea it surfaced — a stuck LLM that
repeats prose *without tool calls* — has been **accepted** (signal + T2 escalation) and recorded as **design
question D3**, gated on the D1 reflexion-budget ceiling so it adds a recovery path without risking reflexion
thrash. Everything else either already exists here in stronger form or is something we deliberately chose not to
build.

---

## 6. File-by-file mapping (OpenManus → this repo)

**Source tree note.** OpenManus `main` (verified 2026-06-14) has refactored planning out of the agent
inheritance ladder and into the Flow layer. The historical `PlanningAgent` class described in §1 and older
write-ups is **not** a separate file on `main` today — plan-once-linear execution lives in
`app/flow/planning.py` + `app/tool/planning.py`, while single-agent ReAct is `Manus → ToolCallAgent →
ReActAgent → BaseAgent`. The mapping below uses the **current** tree; rows marked *(historical)* note where
older docs placed the same concern.

### 6.1 Orchestration & control loop

| OpenManus | Role | This repo (today) | Planned (tier ladder) |
|---|---|---|---|
| `app/agent/base.py` — `BaseAgent.run()` | `while` loop, max-steps, state enum | `orchestration/react_loop.py` — `build_graph()` + conditional edges | Same graph; additive `planner_node`, `reflect_node`, replan back-edge ([design §B diagram](../plans/planning_pipeline_tiered_loops.design.md)) |
| `app/agent/base.py` — `is_stuck()` / `handle_stuck_state()` | Prose-duplicate → prepend prompt | `components/evaluator.py` — `count_trailing_repeats`; `react_loop.py` — no-progress wrap-up | Extend predicate → `kind` + route `prose_repeat → reflect_node` (D3) |
| `app/agent/react.py` — `step()` = `think()` + `act()` | Abstract ReAct step | Split across `call_llm_node` + `execute_tool_node` + `evaluate_node` | Unchanged at T0; T1 adds planner hop before `call_llm` |
| `app/agent/toolcall.py` — `think()` / `act()` | LLM tool-call + execute | `call_llm_node` → `services/llm_config.py`; `execute_tool_node` → `services/tools/registry.py` | Same |
| `app/agent/manus.py` | Flagship agent (browser, python, files, MCP) | No single "Manus" class — tools registered in `ToolRegistry`; prompts in `prompts/*.j2` | Same decomposition |
| `app/flow/base.py` — `BaseFlow` | Multi-agent flow shell | *(no equivalent wired)* — T3 deferred; foundation in `services/tools/task_tool.py` + `delegation_dispatcher.py` | `supervisor_node` + `components/supervisor_plan.py` (deferred) |
| `app/flow/planning.py` — `PlanningFlow` | Plan-once, linear step loop, tag dispatch | Partial: regex plan in `components/plan_builder.py`; **no replan** | T1: `planner_node` + replan gate replaces brittle half |
| `main.py` / `run_flow.py` / `run_mcp.py` | Entrypoints | `agent/cli.py`, `middleware/app_prod.py`, LangGraph SDK adapter | Same stack |
| `app/schema.py` — `Memory`, `Message` | In-process chat list | `orchestration/state.py` — `AgentState` (MessagesState + typed reducers) | + `reflections[]`, `replan_count` |
| *(historical)* `PlanningAgent` | Plan status in every `think()` | `build_planning_instructions` — one sentence by depth; no live step status | T1: plan-status render each executor turn (Idea B) |

### 6.2 Planning artifacts

| OpenManus | Role | This repo (today) | Planned (T1) |
|---|---|---|---|
| `app/tool/planning.py` — `PlanningTool` | In-memory plan store; `create` / `mark_step` / `get` | `build_plan_artifact` — deterministic regex split; stored in `files[plan_ref]` | LLM plan via `plan_builder.py`; floor = `derive_success_conditions` |
| `app/flow/planning.py` — `_create_initial_plan()` | LLM → tool-call → step list; 3-step default fallback | No LLM planner | Same pattern as `TaskUnderstanding` shadow/generated/deterministic ([react_loop.py ~801](../../orchestration/react_loop.py)) |
| `app/flow/planning.py` — `_get_plan_text()` | Live status injected per step | Plan fingerprint frozen after step 0 | Re-inject current step + status each turn; fingerprint change → GTP export |
| `app/flow/planning.py` — `_get_current_step_info()` | Linear scan for first non-completed step | N/A (no step tracker) | Step index + status on `AgentState`; replan gate on surprise |
| `app/flow/planning.py` — `get_executor()` | `[TAG]` regex → agent dict lookup | N/A | **Rejected** for T3 — typed supervisor decision, not regex |

### 6.3 Routing & model selection

| OpenManus | Role | This repo |
|---|---|---|
| `app/config.py` — single `model = "gpt-4o"` | One model for all steps | `services/base_config.py` — `ModelProfile` list with `fast` / `capable` tiers |
| *(none)* | Model routing | `components/router.py` — `select_model()` 5-branch cascade |
| `PlanningFlow.get_executor(step_type)` | Agent routing by prose tag | `select_planning_depth()` → L0/L1/L2 (deterministic); `select_model()` separate |
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

T1's `planner_node` is the production wiring path; the pyramid loop remains an optional second consumer of the
same OBP-shaped components once T2 lands.

---

## 7. Method-level flow mapping (one task, both systems)

Tracing a single multi-step task side-by-side clarifies why "adopt OpenManus" would regress planning *policy*
even where OpenManus has a richer plan *object*.

```text
OPENMANUS (run_flow.py → PlanningFlow)
──────────────────────────────────────
1. PlanningFlow.execute(input)
2. _create_initial_plan → LLM + PlanningTool.create → steps[]
3. while step = next non-completed:
     a. get_executor([TAG] from step text)
     b. executor.run(step_prompt + plan_status)   ← nested BaseAgent.run while loop
     c. _mark_step_completed                      ← always COMPLETED; no replan
4. _finalize_plan → LLM summary
5. return string

THIS REPO (today → LangGraph)
─────────────────────────────
1. START → guard_input (injection gate + AgentFacts, step 0 only)
2. route → select_planning_depth + select_model + TaskUnderstanding (step 0)
         → build_plan_artifact (regex) → files[plan_ref]
3. call_llm → PromptService + tools; no-progress wrap-up if repeats ≥ threshold
4. execute_tool → registry + cache + stamped tool_results[]
5. evaluate → classify_outcome + check_continuation + GoalJudge
6. continue → route | done → reasoning_recap → END

THIS REPO (planned Phase 0 + Phase 1)
─────────────────────────────────────
Phase 0: fix depth collapse only — same graph, correct L1/L2 firing
Phase 1: insert planner_node + replan back-edge
  route →[T1] planner_node (LLM plan, det. floor) → call_llm → …
  execute_tool →[surprise] planner_node (replan gate)
  (T2/T3 unchanged until later phases)
```

| Step | OpenManus method | Repo method / node | Gap |
|---|---|---|---|
| Loop driver | `BaseAgent.run()` while | `add_conditional_edges` in `build_graph` | We have checkpointing + conditional termination |
| Plan create | `PlanningFlow._create_initial_plan` | `build_plan_artifact` (today) → `planner_node` (T1) | We add replan; they don't |
| Plan status in prompt | `_get_plan_text` each step | *(missing today)* → T1 render | Idea B |
| Model pick | *(none)* | `select_model` in `route_node` | We have tiers |
| LLM call | `ToolCallAgent.think` | `call_llm_node` | We record eval + BlackBox |
| Tool exec | `ToolCallAgent.act` | `execute_tool_node` | We cache + authorize + stamp |
| Stuck detect | `is_stuck` in `run()` | `count_trailing_repeats` in `call_llm_node` | We miss prose-only (D3) |
| Continue/stop | max_steps / `FINISHED` enum | `check_continuation` + GoalJudge | We have semantic stop |
| Multi-agent | `get_executor` | deferred T3 | Regex vs typed boundary |

---

## 8. Phase 0 + Phase 1 walkthrough vs OpenManus governance parity

What it would take for each system to match the other's strengths — and why Phase 1 is the right next move here.

### 8.1 Our Phase 0 (prerequisite — no new tier)

**Deliverable:** Fix `task_tool_results_count → L0` collapse + upstream flattener so
`select_planning_depth` fires correctly on fresh multi-part tasks.

| Work item | Touches | OpenManus analogue |
|---|---|---|
| Regression test: 14/17 corpus rows reach intended depth | `tests/` + `components/router.py` | *(none — no depth concept)* |
| Fix count scoping to current `task_id` | `route_node` in `react_loop.py` | N/A |
| Re-run `scripts/diagnose_planning_depth.py` | script only | N/A |
| GTP gate: fixed depth exports on `step.planned` | trace audit | N/A |

**Effort:** Small, deterministic, highest leverage. OpenManus doesn't need this because it always LLM-plans
at flow start — but it also has no depth routing at all.

### 8.2 Our Phase 1 (T1 Plan-and-Execute + replan gate)

**Deliverable:** LLM `planner_node`, deterministic floor fallback, live plan-status injection, replan back-edge
on surprising tool output.

| Work item | Layer | OBP rule | Lead test (failure-first) |
|---|---|---|---|
| LLM plan generation + `derive_success_conditions` floor | `components/plan_builder.py` | OBP-1 | generation fails → floor used → valid plan |
| `planner_node` wrapper | `orchestration/react_loop.py` | OBP-3 | thin — no logic in node |
| Replan conditional edge | graph builder | OBP-4 | surprising output → replan; stable → no replan (P11 matrix) |
| Plan-status render in executor prompt | component pure fn | OBP-1 | status matches state after mark |
| `replan_count` + fingerprint export | `orchestration/state.py` | GTP-4 | new fingerprint exports; duplicate suppressed |
| Ship behind flag | config | — | T1 ≥ ReAct baseline on depth-strata corpus |

**Topology delta (additive):**

```text
route ──[T1: needs plan]──► ★ planner_node ──► call_llm
                              ▲                    │
                              └── replan back-edge ┘
                                    (execute_tool)
```

OpenManus already has rows 4–5 of this table (`_create_initial_plan`, `_get_plan_text`) but **never row 3**
(replan). Phase 1 is therefore "OpenManus planning mechanism + the replan gate OpenManus lacks + our existing
governance wrappers."

### 8.3 If OpenManus wanted *our* governance parity

Rough build order for FoundationAgents/OpenManus to reach what this repo already ships on every run:

| # | Capability | Estimated scope | We have since |
|---|---|---|---|
| 1 | Structured trace log (BlackBox-class) | New service + instrument every step | Phase 2+ |
| 2 | Input guardrail (LLM-as-judge) | New gate before `run()` | Story 1.2 |
| 3 | Tool validators (allowlist, path sandbox) | Per-tool Pydantic validators | Phase 1 tools |
| 4 | Eval capture on every LLM call | Wrapper around `app/llm.py` | Story 1.1 |
| 5 | Task understanding + success conditions | New component + memoization | TU plan §4.5 |
| 6 | GoalJudge at end of run | New component + prompt | GoalJudge stages |
| 7 | Model tier routing | Replace single-model config | Phase 2 router |
| 8 | LangGraph + checkpointer | Replace `while` loop | Story 2.1 |
| 9 | Layer architecture + CI dependency tests | Full restructure | AGENTS.md invariants |
| 10 | Replan gate | Add to `PlanningFlow` | **Our Phase 1** |
| 11 | Reflexion on failed judge | New node + re-entry | **Our Phase 2** |
| 12 | Frontend trace seam + GTP audit | Full FE ring | Frontend architecture |

Items 1–9 are **prerequisites** OpenManus would need before item 10–11 even mean the same thing — a replan
without GoalJudge is still blind; a GoalJudge without BlackBox is un-auditable. Our Phase 1 assumes 1–9 exist
and only adds the planning loop OpenManus half-implements.

### 8.4 Phase-by-phase scorecard (who leads)

| Capability | OpenManus today | Us today | Us after Phase 0 | Us after Phase 1 |
|---|---|---|---|---|
| LLM plan object | ✅ | ❌ regex | ❌ regex | ✅ + replan |
| Live plan status | ✅ | ❌ | ❌ | ✅ |
| Replan on surprise | ❌ | ❌ | ❌ | ✅ |
| Depth routing | ❌ | ⚠️ broken | ✅ | ✅ |
| Model tiers | ❌ | ✅ | ✅ | ✅ |
| Tool-loop stuck detect | ❌ | ✅ | ✅ | ✅ |
| Prose stuck detect | ✅ | ❌ | ❌ | ❌ (Phase 2 / D3) |
| GoalJudge / reflexion | ❌ | ⚠️ judge only | ⚠️ | ⚠️ (Phase 2) |
| Governance trace | ❌ | ✅ | ✅ | ✅ |
| Multi-agent | ⚠️ unstable | ❌ deferred | ❌ | ❌ |

### 8.5 Recommended build order (this repo)

```text
Phase 0  ──► depth collapse fix          (1–2 days, zero LLM, pure regression)
    │
Phase 1  ──► T1 planner + replan         (core delta vs OpenManus)
    │
Phase 2  ──► T2 reflect_node + D1/D3     (prose-stuck + judge-driven recovery)
    │
Phase 3  ──► hybrid escalation routing     (entry nudge + §5 signal promotion)
```

Do **not** skip Phase 0: the plan's corpus proof shows every later tier inherits garbage depth if the L0
short-circuit remains. Do **not** port OpenManus's `PlanningFlow` wholesale — import the *requirements* (LLM
plan, live status) via OBP-shaped components, not the `while`+regex dispatch shape.

---

## 9. Quick reference links

| Document | Purpose |
|---|---|
| [planning_pipeline_tiered_loops.plan.md](../plans/planning_pipeline_tiered_loops.plan.md) | What/why, corpus evidence, §7 phases |
| [planning_pipeline_tiered_loops.design.md](../plans/planning_pipeline_tiered_loops.design.md) | Protocol registry, OBP rules, StateGraph topology |
| [AGENT_PLANNING_AND_TOOL_SELECTION.md](../Architectures/AGENT_PLANNING_AND_TOOL_SELECTION.md) | Current loop narrative |
| [OpenManus `app/flow/planning.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/flow/planning.py) | Their plan-once-linear reference impl |
| [OpenManus `app/agent/base.py`](https://github.com/FoundationAgents/OpenManus/blob/main/app/agent/base.py) | Their loop + stuck detection |
