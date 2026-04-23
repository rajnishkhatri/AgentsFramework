# User Manual -- Run one query against the ReAct agent

You have a clone of this repo and Python 3.10 or newer. By the end of this manual you will have installed the package, set two API keys, asked the agent one question, found the four files that recorded what just happened, and recognised every named way one query can fail.

The agent is a LangGraph ReAct loop with input and output guardrails, two-tier model routing, full-trail recording, and a positional CLI. The grid below is what the rest of this manual unpacks.

```
You type:        python cli.py "<task>"
                          v
                   guard_input  -->  rejected -> done (no answer)
                          v
                       route   -->  picks gpt-4o-mini or gpt-4o
                          v
                     call_llm  -->  budget_exceeded -> done
                          v
                  execute_tool  -->  tool error -> route retries
                          v
                    evaluate    -->  done (answer printed)

You read:        stdout panel + logs/ + cache/black_box_recordings/ + cache/phase_logs/
```

## Skim these headings to read this manual in one minute

1. [You will need Python 3.10+, two API keys, and `pip install -e ".[dev]"` to run anything](#1-you-will-need-python-310-two-api-keys-and-pip-install--e-dev-to-run-anything)
2. [Set `OPENAI_API_KEY` and `AGENT_FACTS_SECRET` -- everything else in `.env.example` is optional](#2-set-openai_api_key-and-agent_facts_secret----everything-else-in-envexample-is-optional)
3. [Docker reproduces the exact runtime in two commands and three environment flags](#3-docker-reproduces-the-exact-runtime-in-two-commands-and-three-environment-flags)
4. [One quoted argument is the whole CLI surface](#4-one-quoted-argument-is-the-whole-cli-surface)
5. `[gpt-4o-mini` answers most questions; `gpt-4o` takes over after two consecutive errors](#5-gpt-4o-mini-answers-most-questions-gpt-4o-takes-over-after-two-consecutive-errors)
6. [The trail of every query lives in three places, not one](#6-the-trail-of-every-query-lives-in-three-places-not-one)
7. [Eight per-service log files under `logs/` are routed by `logging.json](#7-eight-per-service-log-files-under-logs-are-routed-by-loggingjson)`
8. [Hash-chained JSONL under `cache/black_box_recordings/<workflow_id>/trace.jsonl` is the full replay tape](#8-hash-chained-jsonl-under-cacheblack_box_recordings_workflow_id_tracejsonl-is-the-full-replay-tape)
9. [Decision JSONL under `cache/phase_logs/<workflow_id>/decisions.jsonl` shows what the agent chose and why](#9-decision-jsonl-under-cachephase_logs_workflow_id_decisionsjsonl-shows-what-the-agent-chose-and-why)
10. [LangSmith tracing turns on when `LANGCHAIN_TRACING_V2=true` -- only then](#10-langsmith-tracing-turns-on-when-langchain_tracing_v2true----only-then)
11. [Six named failures cover every way one query can break](#11-six-named-failures-cover-every-way-one-query-can-break)
12. [Where to look -- a glossary from common topics to the section that owns them](#12-where-to-look----a-glossary-from-common-topics-to-the-section-that-owns-them)

---

## 1. You will need Python 3.10+, two API keys, and `pip install -e ".[dev]"` to run anything

You have a clone of this repository and Python on your `PATH`. The agent will not start without three things: a Python version that supports `from typing import Self` (3.10+), an editable install of the local package, and an LLM provider key. Every later chapter assumes those three are in place.

Run these from the parent of `agent/`:

```bash
cd agent
pip install -e ".[dev]"
```

The `[dev]` extra adds `pytest`, `pytest-asyncio`, `hypothesis`, `freezegun`, and `ruff` -- you do not strictly need them to run a query, but skipping them blocks you from running `pytest tests/ -q` to check anything went wrong.

Verify the install with:

```bash
python -c "import trust, services, components, orchestration, meta; print('ok')"
```

Five package imports, one `ok`. If any one fails, stop and fix the install before continuing.

The pinned dependency floor (from `pyproject.toml`):


| Package                  | Floor | Why it is required                                                                                    |
| ------------------------ | ----- | ----------------------------------------------------------------------------------------------------- |
| `pydantic>=2.0`          | 2.0   | Every Pydantic model in `trust/`, `components/`, `services/` requires v2 syntax.                      |
| `pydantic-settings>=2.0` | 2.0   | Drives `.env` loading for `meta/CodeReviewerAgentTest/env_settings.py` and the cloud-provider config. |
| `langgraph>=0.2`         | 0.2   | The graph in `orchestration/react_loop.py` uses `MessagesState` and `add_conditional_edges`.          |
| `langchain-litellm>=0.2` | 0.2   | `services/llm_config.py` wraps `ChatLiteLLM`.                                                         |
| `litellm>=1.0`           | 1.0   | The provider router under `ChatLiteLLM`.                                                              |
| `langsmith>=0.1`         | 0.1   | Optional tracing for `LANGCHAIN_TRACING_V2`.                                                          |
| `jinja2>=3.0`            | 3.0   | `services/prompt_service.py` renders templates from `prompts/`.                                       |
| `rich>=13.0`             | 13.0  | The `Rich Console` that prints the answer in `cli.py`.                                                |


---

## 2. Set `OPENAI_API_KEY` and `AGENT_FACTS_SECRET` -- everything else in `.env.example` is optional

You have an editable install. The agent now needs an LLM provider key (it will not call a model without one) and a signing secret (it will not register the agent's own identity card without one). Without those two values the graph builds and immediately throws a provider exception or a registry exception on first call.

Copy and fill the example:

```bash
cp .env.example .env
```

The complete env table -- only the first two are mandatory for the default flow:


| Variable               | Required?                          | What it controls                                                                                                                                      | Read by                                                                                                                           |
| ---------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY`       | **Yes**                            | LiteLLM provider credential for `gpt-4o-mini` and `gpt-4o`.                                                                                           | LiteLLM at LLM call time, plus `meta/code_reviewer.py:479-490` and the fixture recorder.                                          |
| `AGENT_FACTS_SECRET`   | **Yes**                            | HMAC secret used by `AgentFactsRegistry` to sign the agent's identity card on first run. Default placeholder `change-me` is acceptable for local use. | `cli.py:92-97`, `services/governance/agent_facts_registry.py:27-32`.                                                              |
| `WORKSPACE_DIR`        | Optional, defaults to `/workspace` | The sandbox directory for the file-IO tool.                                                                                                           | `services/tools/file_io.py:21-22`.                                                                                                |
| `TRUST_PROVIDER`       | Optional, defaults to `local`      | Selects the trust provider; only `local` is wired today.                                                                                              | `utils/cloud_providers/config.py:14-24`.                                                                                          |
| `LANGCHAIN_TRACING_V2` | Optional                           | Turns LangSmith tracing on.                                                                                                                           | LangChain SDK -- not in-repo Python. See [chapter 10](#10-langsmith-tracing-turns-on-when-langchain_tracing_v2true----only-then). |
| `LANGCHAIN_API_KEY`    | Optional                           | LangSmith API key, only consulted when tracing is on.                                                                                                 | LangChain SDK.                                                                                                                    |
| `LANGCHAIN_PROJECT`    | Optional                           | LangSmith project name.                                                                                                                               | LangChain SDK.                                                                                                                    |


The agent reads `OPENAI_API_KEY` lazily (at the moment of the first LLM call), so a missing key does not fail at import time. It fails when the `call_llm` node runs -- which is after the input guardrail passes, so you may see one entry in `logs/guards.log` before the failure. That is the expected ordering.

---

## 3. Docker reproduces the exact runtime in two commands and three environment flags

Sometimes you do not want to install Python locally. The Dockerfile installs the same package against `python:3.11-slim`, sets `WORKSPACE_DIR=/workspace` and `TRUST_PROVIDER=local` baked into the image, and entrypoints `python -m agent.cli`. You pass the API key and the signing secret through `-e` flags at run time.

Build once, run every query:

```bash
docker build -t react-agent .
docker run \
    -e OPENAI_API_KEY=$OPENAI_API_KEY \
    -e AGENT_FACTS_SECRET=change-me \
    react-agent "What is 2+2?"
```

Three differences from a local install:

- The Docker image runs as `root` (no `USER` directive in the Dockerfile). For a server context, override the user at run time.
- The default `cache_dir` is `cache/` relative to the container's `WORKDIR=/app`. To keep the trail across runs, mount a volume: `-v $(pwd)/cache:/app/cache`.
- The Dockerfile mirrors what `AGENTS.md` documents and accepts the same task-as-positional-argument syntax described in chapter 4.

---

## 4. One quoted argument is the whole CLI surface

You have install and config done. The CLI does not use `argparse` or `click` -- there is no `--help`, no `--version`, no subcommand. Everything after the script name is joined into one task string and handed to the graph.

Run from inside the `agent/` directory:

```bash
python cli.py "What is the capital of France?"
```

Or, in a context where the parent of `agent/` is on `sys.path`:

```bash
python -m agent.cli "What is the capital of France?"
```

Both forms behave the same. If you forget the quoted argument, the program prints exactly:

```text
Usage: python -m agent.cli '<task>'
```

and exits 1. There are no other shapes to learn.

What stdout shows on a successful run, in order:

1. A header line beginning `Task:` followed by the task string you passed.
2. (After the LLM finishes) a `Rich Panel` containing the final answer.
3. A trailing line of the form `Steps: <n>  Total cost: $<dollars>` that summarises how many ReAct steps the loop took and what it cost.

What stderr shows: every log record from the `console` handler in `logging.json` (one line per service per event). Successful runs are quiet; you will mostly see startup lines and the route decision. Use `2>/dev/null` to suppress the noise during a demo.

The agent treats the quoted argument as untrusted user input -- it goes through the input guardrail before any LLM call.

---

## 5. `gpt-4o-mini` answers most questions; `gpt-4o` takes over after two consecutive errors

You will not configure the model. The default profile list lives in `cli.py:48-68` and wires two LiteLLM models with two tier labels:


| Profile name  | LiteLLM id    | Tier      | When it is selected                                                                                                                                                                                  |
| ------------- | ------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gpt-4o-mini` | `gpt-4o-mini` | `fast`    | Default for every step.                                                                                                                                                                              |
| `gpt-4o`      | `gpt-4o`      | `capable` | Selected by the router when `consecutive_errors >= escalate_after_failures` or when the cost trajectory crosses `budget_downgrade_threshold` -- both numbers live in `components/routing_config.py`. |


The router is `components.router.select_model(...)`. It receives the current step count, the consecutive error count, the last error type, the running cost, and the `RoutingConfig`, and returns one of the two profiles plus a one-line `routing_reason` that you will see in `logs/routing.log` and in the phase decisions JSONL described in [chapter 9](#9-decision-jsonl-under-cachephase_logs_workflow_id_decisionsjsonl-shows-what-the-agent-chose-and-why).

You do not need to do anything to enable escalation -- it is on by default, and a query that triggers it will say so in the trail.

---

## 6. The trail of every query lives in three places, not one

A query that prints a wrong answer is not a dead end -- the agent records what it did in three independent surfaces. You do not need to instrument anything to get them; they exist after the first run.

The three locations, relative to your working directory:


| Surface               | Path                                                   | What it captures                                                                                                                                                                                                            | When you read it                                                  |
| --------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Per-service log files | `logs/<service>.log`                                   | One file per concern: prompts rendered, guardrail decisions, eval records, drift reports, tool calls, routing decisions, governance events. Plain text + JSON depending on the handler.                                     | First stop for "what did the agent print and decide?"             |
| Black-box trace       | `cache/black_box_recordings/<workflow_id>/trace.jsonl` | Hash-chained JSONL of every event the orchestration nodes emitted: `TASK_STARTED`, `GUARDRAIL_CHECKED`, `MODEL_SELECTED`, `STEP_EXECUTED`, `TOOL_CALLED`. Every record has an `integrity_hash` chained to the previous one. | Full replay -- "exactly what happened, in order, tamper-evident." |
| Phase decisions       | `cache/phase_logs/<workflow_id>/decisions.jsonl`       | Structured `Decision` records for routing and continuation: which model the router picked, which alternatives it considered, the rationale; whether to continue or stop after each step.                                    | "Why did the agent choose what it chose?"                         |


The `<workflow_id>` is the value of `task_id` in the agent state -- a UUID generated per query. The default `cache_dir` is `cache/` in your current working directory; if you ran the agent from `agent/`, the JSONL lives under `agent/cache/`. Mount a host volume to keep the trail across Docker runs.

The next three chapters open each surface in detail.

---

## 7. Eight per-service log files under `logs/` are routed by `logging.json`

Each service has its own logger and its own file. The handlers in `logging.json` open plain `FileHandler` streams in append mode -- there is no rotation today, so the files will grow until you delete them. The `console` handler writes the same records to `sys.stderr` so you see them live.

The complete log map:


| Logger name                        | File                           | Source that writes to it                                                                                             |
| ---------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `services.prompt_service`          | `logs/prompts.log`             | Every template render via `PromptService.render_prompt`.                                                             |
| `services.guardrails`              | `logs/guards.log`              | Every input-guardrail verdict (accept / reject / parse error).                                                       |
| `services.eval_capture`            | `logs/evals.log`               | One structured record per LLM call, with `target`, `ai_input`, `ai_response`, model id, token counts, cost, latency. |
| `services.tools`                   | `logs/tools.log`               | Configured but no in-repo code currently writes here; child loggers like `services.tools.sandbox` may write to it.   |
| `components.router`                | `logs/routing.log`             | Configured but no in-repo code currently writes here; routing decisions land in the phase-decisions JSONL instead.   |
| `services.governance.black_box`    | `logs/black_box.log`           | Initialisation + integrity-chain warnings from the `BlackBoxRecorder`.                                               |
| `services.governance.phase_logger` | `logs/phases.log`              | Initialisation messages from `PhaseLogger`.                                                                          |
| `services.governance.agent_facts`  | `logs/identity.log`            | One line per registry operation: `register`, `verify`, `suspend`, `restore`.                                         |
| `meta.drift`                       | `logs/drift.log`               | Drift-check execution traces from `python -m meta.drift`.                                                            |
| `services.observability`           | `logs/framework_telemetry.log` | LangGraph checkpoint writes captured by `InstrumentedCheckpointer`.                                                  |
| (root, `console` only)             | stderr                         | Anything not handled above.                                                                                          |
| `orchestration.react_loop`         | stderr only                    | Graph-build and node-execution log lines -- intentionally not file-routed; use the black-box trace instead.          |


`logs/evals.log` is the file you will read most often. Each record looks like:

```json
{
    "schema_version": 1,
    "target": "call_llm_node",
    "task_id": "<uuid>",
    "step": 2,
    "model": "gpt-4o-mini",
    "tokens_in": 412,
    "tokens_out": 87,
    "cost_usd": 0.00021,
    "latency_ms": 612,
    "ai_input": "...",
    "ai_response": "..."
}
```

`tail -f logs/evals.log` while a query runs gives you a live read of every LLM call.

---

## 8. Hash-chained JSONL under `cache/black_box_recordings/<workflow_id>/trace.jsonl` is the full replay tape

A wrong answer or a strange tool call is reconstructable. The `BlackBoxRecorder` writes one JSONL line per orchestration event in the order they happened, and each line carries an `integrity_hash` that incorporates the previous line's hash. Tampering with an earlier event invalidates every later hash; the recorder's `export()` returns a `hash_chain_valid` flag.

Inspect the most recent run:

```bash
ls cache/black_box_recordings/
# pick the workflow_id that matches the run you care about
cat cache/black_box_recordings/<workflow_id>/trace.jsonl | jq
```

Each record carries: `event_id`, `workflow_id`, `event_type`, `timestamp`, `step`, `details` (event-specific payload), `integrity_hash`. The event types you will see in order for a normal query:


| Order | `event_type`                   | What it means                                                                                                              |
| ----- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| 1     | `TASK_STARTED`                 | The CLI accepted your quoted task and called `build_graph(...).invoke({...})`.                                             |
| 2     | `GUARDRAIL_CHECKED`            | The input guardrail finished judging your task. `details.outcome` is `accepted` or `rejected`.                             |
| 3     | `MODEL_SELECTED`               | The router chose `gpt-4o-mini` or `gpt-4o`. `details.routing_reason` is the one-line rationale.                            |
| 4     | `STEP_EXECUTED` (one per step) | The `call_llm` node returned. `details` includes the assistant message and any tool calls it requested.                    |
| 5     | `TOOL_CALLED` (per tool call)  | The `execute_tool` node invoked one tool. `details` includes the tool name, the input, the output, and whether it errored. |
| --    | `STEP_EXECUTED` again          | The `evaluate` node decided continue or done. `details.outcome` is `continue` or `done`.                                   |


A failed run still emits the early events; the absence of a `STEP_EXECUTED` with `outcome=done` is the signal that the loop terminated for another reason (rejection, budget, error). [Chapter 11](#11-six-named-failures-cover-every-way-one-query-can-break) maps each named failure to the events you will see (and not see).

---

## 9. Decision JSONL under `cache/phase_logs/<workflow_id>/decisions.jsonl` shows what the agent chose and why

The black-box tape tells you what happened. The phase decisions tell you *why the agent picked what it picked*. Two nodes call into `PhaseLogger.log_decision`: the `route_node` (records the model choice and the alternatives considered) and the `evaluate_node` (records continue-or-stop with the rationale).

A typical record:

```json
{
    "phase": "ROUTING",
    "decision": "select_model:gpt-4o-mini",
    "alternatives": ["gpt-4o-mini", "gpt-4o"],
    "rationale": "default model: step=0 errors=0 cost=$0.00",
    "metadata": {
        "step_count": 0,
        "consecutive_errors": 0,
        "total_cost_usd": 0.0
    },
    "timestamp": "2026-04-17T12:34:56.789Z"
}
```

The decisions file is the right place to start when the question is "why did the agent escalate to `gpt-4o`?" or "why did the loop stop after two steps?" You read the decisions JSONL; you do not need to re-run with verbose flags.

The same `PhaseLogger` interface is reused by `python -m meta.drift` and `python -m meta.optimizer` to record their own decisions in separate workflow ids. You will only see those if you run those commands.

---

## 10. LangSmith tracing turns on when `LANGCHAIN_TRACING_V2=true` -- only then

The optional fourth observability surface is LangSmith. The agent does not import `langsmith` at runtime -- the LangChain SDK reads three environment variables at import time and uploads traces if all three are set:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your-langsmith-key>
export LANGCHAIN_PROJECT=react-agent-phase1
```

Re-run any query. The trace appears in the LangSmith UI under the project name, with one trace per `task_id`. The local trail in `logs/`, `cache/black_box_recordings/`, and `cache/phase_logs/` continues to be written exactly as before -- LangSmith is additive, not replacement.

If `LANGCHAIN_TRACING_V2` is unset or `false`, no upload happens; this is the default. Nothing in this manual depends on it.

---

## 11. Six named failures cover every way one query can break

Every failure has a name, a visible signal, and a one-line fix. You should be able to read this chapter, see your failure, and know the next action.

### 11.1 Missing API key produces a provider exception after `guard_input` passes

You set up `.env` and forgot `OPENAI_API_KEY`, or you ran Docker without `-e OPENAI_API_KEY=...`.

- **Signal:** a Python traceback ending in a LiteLLM `AuthenticationError` or `OpenAIError` after the agent has already printed `Task: ...` and after `logs/guards.log` has recorded one accept event.
- **Trail:** `cache/black_box_recordings/<workflow_id>/trace.jsonl` contains `TASK_STARTED`, `GUARDRAIL_CHECKED` (accepted), `MODEL_SELECTED`, but no `STEP_EXECUTED`.
- **Fix:** set `OPENAI_API_KEY` in `.env` (local) or pass `-e OPENAI_API_KEY=$OPENAI_API_KEY` (Docker). See [chapter 2](#2-set-openai_api_key-and-agent_facts_secret----everything-else-in-envexample-is-optional).

### 11.2 An input guardrail rejection ends the run before any LLM call

Your task contained content the input guardrail considered unacceptable -- a prompt-injection attempt, a system-prompt override, or whatever `accept_condition` your judge profile is set to reject.

- **Signal:** the program exits without printing a `Rich Panel`. `logs/guards.log` contains a record with the rejected verdict and the judge's text.
- **Trail:** `cache/black_box_recordings/<workflow_id>/trace.jsonl` contains `TASK_STARTED` and `GUARDRAIL_CHECKED` (rejected). The conditional edge `_guard_routing` returned `"rejected"` and the graph went straight to END.
- **Fix:** rephrase the task. The judge's text in `logs/guards.log` tells you what condition failed.

### 11.3 An output guardrail block replaces the answer with a sanitized message

The LLM produced a response containing PII, an API-key-shaped string, or other content that one of the deterministic `GuardRail` rules in `services/governance/guardrail_validator.py` flagged with `severity in (HIGH, CRITICAL)` and `fail_action == BLOCK`.

- **Signal:** the `Rich Panel` contains the canonical sanitized message produced by `_sanitized_block_message`, not the model's original output.
- **Trail:** `logs/guards.log` records the failing rule(s); `cache/black_box_recordings/<workflow_id>/trace.jsonl` shows a `STEP_EXECUTED` with the sanitized assistant content.
- **Fix:** if the original content was legitimate and the rule was wrong, edit the corresponding factory in `services/governance/guardrail_validator.py` (or its caller). For a one-off, re-ask the question with less specific data.

### 11.4 A model fallback escalates from `gpt-4o-mini` to `gpt-4o` after two consecutive errors

The fast model errored twice in a row. The router escalated.

- **Signal:** `cache/phase_logs/<workflow_id>/decisions.jsonl` contains a `ROUTING` decision with `decision: "select_model:gpt-4o"` and a `rationale` that names `consecutive_errors`.
- **Trail:** the previous two `STEP_EXECUTED` records in `cache/black_box_recordings/<workflow_id>/trace.jsonl` carry an `error` payload; the next `MODEL_SELECTED` flips to `gpt-4o`.
- **Fix:** none required if the escalation produced a good answer -- this is the routing policy working. To make escalation happen sooner or later, change `escalate_after_failures` in `components/routing_config.py`.

### 11.5 A budget-exceeded exit ends the loop before the answer is ready

The accumulated cost on this task crossed `user_max_cost_per_task` (read from the `RunnableConfig` and surfaced in `route_node`) or the per-step cap in `RoutingConfig`. The `_parse_response` conditional edge returned `"budget_exceeded"`.

- **Signal:** the trailing line on stdout shows a positive cost and a step count, but no `Rich Panel` -- the loop ended without an answer.
- **Trail:** the last record in `cache/black_box_recordings/<workflow_id>/trace.jsonl` is a `STEP_EXECUTED` with the budget-breaching cost. There is no `outcome=done`.
- **Fix:** raise the cost cap in your invocation config, or rewrite the task to take fewer steps. Querying the cheaper model is usually one rephrasing away.

### 11.6 A tool error triggers a retry with the same or a different profile

A tool call -- shell, file IO, web search -- raised an exception or returned a structured error. The graph populated `last_error_type` and `consecutive_errors` and the next `route_node` invocation read those.

- **Signal:** `cache/black_box_recordings/<workflow_id>/trace.jsonl` contains a `TOOL_CALLED` with an error-shaped payload, followed by another `MODEL_SELECTED` and `STEP_EXECUTED`.
- **Trail:** if the retry succeeded, the next step's `STEP_EXECUTED` ends with `outcome=done`. If it errored again, the model-fallback rule from [11.4](#114-a-model-fallback-escalates-from-gpt-4o-mini-to-gpt-4o-after-two-consecutive-errors) kicks in.
- **Fix:** if the tool input was wrong, re-ask the task with a more specific phrasing. If the tool itself is broken, fix the underlying issue (path sandboxing for file IO, allowlist for shell). Tool input contracts live in `services/tools/`.

---

## 12. Where to look -- a glossary from common topics to the section that owns them


| If you came here looking for... | Read this section                                                                                                                                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Installation                    | [Chapter 1](#1-you-will-need-python-310-two-api-keys-and-pip-install--e-dev-to-run-anything)                                                                                                                             |
| Environment variables / `.env`  | [Chapter 2](#2-set-openai_api_key-and-agent_facts_secret----everything-else-in-envexample-is-optional)                                                                                                                   |
| API keys / credentials          | [Chapter 2](#2-set-openai_api_key-and-agent_facts_secret----everything-else-in-envexample-is-optional)                                                                                                                   |
| Docker                          | [Chapter 3](#3-docker-reproduces-the-exact-runtime-in-two-commands-and-three-environment-flags)                                                                                                                          |
| CLI reference / flags           | [Chapter 4](#4-one-quoted-argument-is-the-whole-cli-surface) (there are no flags)                                                                                                                                        |
| Models                          | [Chapter 5](#5-gpt-4o-mini-answers-most-questions-gpt-4o-takes-over-after-two-consecutive-errors)                                                                                                                        |
| Routing                         | [Chapter 5](#5-gpt-4o-mini-answers-most-questions-gpt-4o-takes-over-after-two-consecutive-errors) and [Chapter 9](#9-decision-jsonl-under-cachephase_logs_workflow_id_decisionsjsonl-shows-what-the-agent-chose-and-why) |
| Logging                         | [Chapter 7](#7-eight-per-service-log-files-under-logs-are-routed-by-loggingjson)                                                                                                                                         |
| Guardrails                      | [Chapter 11.2](#112-an-input-guardrail-rejection-ends-the-run-before-any-llm-call) (input) and [Chapter 11.3](#113-an-output-guardrail-block-replaces-the-answer-with-a-sanitized-message) (output)                      |
| Black-box trace / replay        | [Chapter 8](#8-hash-chained-jsonl-under-cacheblack_box_recordings_workflow_id_tracejsonl-is-the-full-replay-tape)                                                                                                        |
| Decision rationale              | [Chapter 9](#9-decision-jsonl-under-cachephase_logs_workflow_id_decisionsjsonl-shows-what-the-agent-chose-and-why)                                                                                                       |
| LangSmith tracing               | [Chapter 10](#10-langsmith-tracing-turns-on-when-langchain_tracing_v2true----only-then)                                                                                                                                  |
| Trust kernel / `AgentFacts`     | This manual does not cover internals; see `[docs/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)` chapter on the trust foundation.                                                                                               |
| Cost / budget                   | [Chapter 11.5](#115-a-budget-exceeded-exit-ends-the-loop-before-the-answer-is-ready)                                                                                                                                     |
| Errors and exit codes           | [Chapter 11](#11-six-named-failures-cover-every-way-one-query-can-break); the only documented exit code is `1` for missing argument.                                                                                     |
| Extending the agent             | This is a user manual; for extension recipes see `[docs/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)`.                                                                                                                        |
| Architecture overview           | `[docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](FOUR_LAYER_ARCHITECTURE.md)` and `[docs/STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md)`.                                                                                           |
| Governance narratives           | `[governanaceTriangle/](../governanaceTriangle/)` -- six tutorial markdown files covering explainability, the black box recorder, AgentFacts governance, guardrail validation, and the phase logger deep dive.           |


---

*See also:* `[docs/DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)` (extending the framework), `[docs/PYRAMID_ANALYSIS.md](PYRAMID_ANALYSIS.md)` (the planning artifact behind both manuals), `[AGENTS.md](../AGENTS.md)` (the workspace conventions).