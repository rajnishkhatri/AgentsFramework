# Agent planning and tool selection

> How the agent decides task complexity, sets a planning depth, and assigns
> tools to subtasks. All planning is **deterministic** (no LLM); tool selection
> is the only stage where the model makes a choice — and that choice is bounded
> by deterministic gates on either side.

---

## 1. Two-stage planning

The agent plans in two stages, both pure functions. Neither calls an LLM.

### Stage 1 — Depth selection ([components/router.py:72](../../components/router.py))

`select_planning_depth(task_input, task_tool_results_count)` returns one of
`L0` / `L1` / `L2` plus a reason string. It is a pure scoring function.

**Synthesis short-circuit (per-task scoped):**

```python
if task_tool_results_count > 0:
    return "L0", "post-tool-synthesis"
```

Mid-task turns — after the agent has already executed tools *for this task* —
always plan shallowly. There is nothing left to decompose; the agent is
synthesizing a response over fresh evidence.

> **Per-task scoping is load-bearing.** The caller (orchestration) MUST filter
> `state["tool_results"]` to the current `task_id` before passing the count.
> A thread-wide count breaks the heuristic the moment a thread is reused
> (saturation runs, replay batches, multi-turn UIs): a re-asked composite
> task on a thread with prior tool results will short-circuit to `L0`,
> cap the planner at 1 step, and force the agent to fabricate the missing
> subtasks. See [orchestration/react_loop.py:685-694](../../orchestration/react_loop.py)
> for the canonical caller.

### Stage 2 — Complexity scoring (only when no per-task tool results yet)

The scorer walks lowercased text and sums orthogonal signals:

| Signal | Source | +1 when |
|---|---|---|
| Word count (medium) | `len(words)` | `≥ 35` |
| Word count (long) | `len(words)` | `≥ 80` (stacks on top of medium) |
| Multi-part vocabulary | substring | `compare`, `trade-off`, `tradeoff`, `architecture`, `migration`, `refactor`, `roadmap`, `design` |
| Conjunctions / list markers | substring | ` and `, ` then `, ` also `, `\n- `, `\n1.` |
| Multi-line shape | newline count | `≥ 2` newlines |
| Multi-question shape | `?` count | `≥ 2` |
| Explicit enumeration | regex `\([1-9]\)` | `≥ 2` matches (e.g. `(1)…(2)…`) |
| Comma-then-and pattern | regex `,[^,]+,\s*(?:and\|then)\s` | matches **AND** no multi-part marker fired |

**Threshold → depth:**

```python
if complexity_score >= 3: return "L2", "high-complexity-initial-task"
if complexity_score >= 2: return "L1", "moderate-complexity-initial-task"
return "L0", "simple-initial-task"
```

### Two scoring decisions worth knowing

1. **Anti-double-counting on multi-part prompts.** The comma-then-and clause
   only fires if no multi-part marker did. Without that gate, a prompt like
   `"Compare X, design Y, and then produce Z"` would score `+1` (marker) +
   `+1` (` and `) + `+1` (comma-then-and) = `3`, pushing a moderate task into
   `L2`. The pattern measures the same property as the other two; it earns a
   point only when they are silent. This was the root cause of two CI
   failures (`todo_file_progression`, `large_output_offload`) before the
   gating was added.

2. **Synthesis short-circuit beats everything.** Once any per-task tool has
   run, every subsequent routing call returns `L0`. This is intentional:
   later iterations are about synthesizing over evidence, not decomposing
   anew.

### Depth → step cap ([components/plan_builder.py:43](../../components/plan_builder.py))

```python
max_steps = {"L0": 1, "L1": 3, "L2": 5}[planning_depth]
```

`build_plan_artifact(depth, task_input)` produces a `PlanArtifact` containing:

- `ordered_steps`: ≤ `max_steps` ordered subtasks derived from the task language
- `constraints`: anything that gates execution (file paths, deadlines, etc.)
- `success_conditions`: per-step "this is done when…" checks

The artifact also drives `components/synthesis_validator.py`: at `L1` / `L2`
the validator enforces "no open TODOs left" and "answer length ≥ 8 words" —
this prevents the model from shortcutting a multi-step task with a one-line
synthesis.

---

## 2. Tool selection

This is where the LLM makes a choice, but the scaffolding around it is
deterministic.

### Static registration ([services/tool_registry.py](../../services/tool_registry.py))

A `ToolRegistry` is built at app start by the composition root. Each tool
ships with a JSON schema, a name, and a description. There is **no dynamic
discovery** — what's registered at boot is what the model can see for the
session. The current production registry advertises 7 tools (e.g. `file_io`,
`shell`, `write_todos`, `web_search`, `fetch_url`, `image_describe`, plus one
internal).

### Catalog injection at model invocation

The selected `ModelProfile` from `select_model(...)` and the `tools=[...]`
catalog are both passed into `litellm.completion(...)`. The Cloud Run log line
makes this explicit:

```
Invoking gpt-4o-mini (fast tier) with 79 messages, 7 tools
```

The LLM emits tool calls via function-calling JSON. The **policy of which
tool fits which subtask** lives in the model + the rendered system prompt
(`prompts/system_prompt.j2`) and the plan artifact's `success_conditions`
(e.g. "subtask 3: live weather data observed" nudges toward `web_search`).
There is no enum-from-subtask-to-tool table — the matching is learned.

### The step cap bounds *how many* tools can run

`max_steps` from the depth × per-step model call ≈ "the loop iterates at most
N times before forcing a synthesis."

- `L0` (max=1) — model gets exactly one tool-call turn before being asked to
  answer
- `L1` (max=3) — up to three tool-call iterations
- `L2` (max=5) — up to five

This is why a chronically-mis-classified `L0` task that *actually* needs
three tool calls produces a fabricated answer for subtasks 2-N: the agent's
budget runs out, and the language model fills the gap.

### Tool execution and result feedback ([orchestration/react_loop.py:165-360](../../orchestration/react_loop.py))

For each tool call the model emits:

1. **Cache lookup** by `(tool_name, normalized args)` — cached results
   short-circuit execution.
2. **Synchronous dispatch** via `tool_registry.execute_with_result(tool_name, tool_args_with_state)`.
3. **Result envelope** stamped with `record_id`, `step_id`, `task_id`,
   `tool_name`, `tool_input`, `tool_output`, `ok` / `error`, and cache /
   offload flags. The `task_id` stamp is what makes the per-task scoping in
   Stage 1's synthesis short-circuit possible.
4. **History window**: the same loop trims to
   `agent_config.tool_result_history_limit` so context cannot unbounded-grow.

### Validation gates around the tool loop

- **`output_validation`** runs guardrails on the model's response before
  tools fire (PII redaction, etc.).
- **`synthesis_validator.py`** enforces depth-aware rules on the final
  answer: at `L1` / `L2` it refuses answers that leave TODOs open or that
  are under 8 words.
- **`evaluate_node`** calls `GoalJudge` once at completion. Its rubric
  actively checks the **"wrong verification tool"** failure (Step 3 bullet
  d): e.g. an `ls /workspace` directory listing presented as evidence that
  the agent *read* a file is now caught as corrupt-success.

---

## 3. End-to-end loop at a glance

```text
task_input arrives
   ↓
[route_node]                       ← every iteration
   ├─ select_model()                ← deterministic, 5-branch (budget → retryable → escalate → first-step → steady)
   ├─ select_planning_depth()       ← deterministic, pure scoring (above)
   ├─ build_plan_artifact()         ← max_steps=cap, success_conditions per subtask
   ├─ validate_plan_mece()          ← escalate to capable tier on invalid plan
   ↓
[call_llm_node]                    ← litellm.completion(profile, messages, tools=7)
   ↓
[tool_execution]                   ← model emits tool_calls → registry dispatches
   ↓
[output_validation]                ← guardrails + redaction
   ↓
[evaluate_node]                    ← deterministic outcome floor + GoalJudge overlay
   ↓
loop back to [route_node] OR complete
```

---

## 4. Worked example — GJ-012

Task: `"Create a file /workspace/f3.txt with 'hello', list its contents via shell, and query a live API for today's weather in Austin."`

### Before the per-task scoping fix (bug)

| Step | Value | Why |
|---|---|---|
| `task_tool_results_count` | `> 0` | Saturation thread `session-gj-012` carried prior tool results from earlier days' runs |
| `select_planning_depth` | `L0` | Synthesis short-circuit fired on thread-wide tool result count |
| `max_steps` | `1` | L0 cap |
| Tools fired | `file_io` write only | Budget exhausted after subtask 1 |
| Final answer | Fabricated weather details | Model filled the gap for subtasks 2-3 |
| Judge verdict | `pf=0.33` | One of three subtasks grounded in tool evidence |

### After the per-task scoping fix

| Step | Value | Why |
|---|---|---|
| `task_tool_results_count` | `0` | Filtered to current `task_id`; this task has not yet acted |
| Complexity score | `2` | `+1` for ` and `, `+1` for comma-then-and (no multi-part marker hit) |
| `select_planning_depth` | `L1` | Score ≥ 2 |
| `max_steps` | `3` | L1 cap |
| Tools fired | `file_io` + `shell` + `web_search` | All three subtasks budgeted |
| Final answer | Grounded in actual tool outputs | No fabrication |
| Judge verdict | `pf ≈ 0.67` | Matches registry; passes shadow gate |

The fix is one signature change (`step_count` + `tool_results_count` →
`task_tool_results_count`), one caller change (filter `tool_results` by
`task_id`), and one append-time stamp (`task_id` on each tool result row).

---

## 5. Why this design

- **Planning is deterministic** — every routing decision is reproducible
  from `(task_input, task_tool_results_count)`. No hidden LLM state, no
  expensive recompute on resume.
- **Pure-function testability** — `select_planning_depth` has 11
  parametrized rows in
  [tests/components/test_router.py](../../tests/components/test_router.py)
  covering simple, moderate, complex, post-tool, composite imperative,
  TAP-4 rejection, and per-task-scoping regression guards. All run in L1
  Deterministic CI.
- **The LLM owns only what it's good at** — picking the right tool for a
  subtask, given the success_conditions. The framework owns the budget,
  the catalog, and the validation gates.
- **The architecture stays four-layer-clean** — `components/router.py` is a
  framework-agnostic pure function (no `langgraph`, no `langchain`); the
  state and caller orchestration is the only seam that knows about
  per-task scoping.

---

## References

- [components/router.py](../../components/router.py) — `select_model`, `select_planning_depth`
- [components/plan_builder.py](../../components/plan_builder.py) — depth → max_steps mapping, plan artifact construction
- [components/synthesis_validator.py](../../components/synthesis_validator.py) — depth-aware final-answer gates
- [components/goal_judge.py](../../components/goal_judge.py) — wrong-verification-tool rubric
- [orchestration/react_loop.py](../../orchestration/react_loop.py) — `route_node`, tool execution loop, per-task tool_result stamping
- [services/tool_registry.py](../../services/tool_registry.py) — static tool registration
- [docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](FOUR_LAYER_ARCHITECTURE.md) — layering invariants
- [docs/Architectures/BACKEND_SOLUTION_ARCHITECTURE.md](BACKEND_SOLUTION_ARCHITECTURE.md) — `select_model` + `select_planning_depth` in the routing sequence diagram
