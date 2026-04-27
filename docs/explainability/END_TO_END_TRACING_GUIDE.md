# End-to-End Tracing Guide

> How frontend inputs flow through to backend AgentFacts, traces, black-box recording, and observability — and how to capture logs for a live session.

---

## The Five Trace Planes

There are five independent but correlated planes of logging. They share `trace_id` as the correlation key — but only if you bridge the gap described in the [Known Gap](#known-gap) section below.

| Plane | Where it lands | Keyed by |
|---|---|---|
| **HTTP layer** | `middleware` stdout / structlog | `trace_id`, `run_id`, `thread_id` |
| **Domain events → SSE** | SSE stream to browser | `trace_id` (minted by `LangGraphRuntime`) |
| **Black box recorder** | `cache/black_box_recordings/<workflow_id>/trace.jsonl` | `workflow_id` |
| **Phase logger** | `cache/phase_logs/<workflow_id>/decisions.jsonl` | `workflow_id` |
| **Eval capture** | `logging.json` handler for `services.eval_capture` | `task_id`, `user_id` |

---

## Architecture Overview

### How `trace_id` is minted

The Python adapter (`agent_ui_adapter/adapters/runtime/langgraph_runtime.py`) mints a fresh `trace_id` and `run_id` per request:

```python
# langgraph_runtime.py — LangGraphRuntime.run()
trace_id = uuid.uuid4().hex
run_id   = uuid.uuid4().hex
yield RunStartedDomain(trace_id=trace_id, run_id=run_id, thread_id=thread_id)
```

Every subsequent domain event (`LLMTokenEmitted`, `ToolCallStarted`, etc.) carries the same `trace_id`. The translator (`agent_ui_adapter/translators/domain_to_ag_ui.py`) embeds it into each SSE payload:

```json
{"event":"RUN_STARTED","raw_event":{"trace_id":"<hex>","run_id":"<hex>","thread_id":"<hex>"}}
```

**The browser never mints a `trace_id`.** It reads `raw_event.trace_id` off each SSE event. E2E tests in `frontend/e2e/security/` enforce this invariant. On transport failure the composition layer emits a sentinel `trace_id: "no-trace"`.

### How `AgentFacts` relate to a trace

`AgentFacts` is the **signed identity envelope** (`trust/models.py`). It does not hold `trace_id`. Instead:

- The middleware resolves the bearer token → `AgentFacts` (dev: any token → `dev-agent`).
- The runtime receives `identity: AgentFacts` alongside the minted `trace_id`.
- Both travel in parallel: `identity` governs authorization; `trace_id` correlates observability.

```
Bearer token  ──▶  _require_bearer()  ──▶  AgentFacts (signed identity)
                                                     │
POST /run/stream  ──▶  LangGraphRuntime.run()  ──▶  mints trace_id
                                                     │
                                            domain events carry both
```

### The `TrustTraceRecord` plane (optional)

`LangGraphRuntime` accepts an optional `trace_emit` callback:

```python
LangGraphRuntime(graph, trace_emit=trace_service.emit)
```

When wired, it emits `TrustTraceRecord` objects at `run_started` and `run_finished`, tagged with `trace_id` and `agent_id`. By default in `middleware/__main__.py` this is `None` (no-op).

### Black box recording

`services/governance/black_box.py` — `BlackBoxRecorder` writes append-only JSONL with chained SHA-256 integrity hashes:

```
cache/black_box_recordings/<workflow_id>/trace.jsonl
```

Event types recorded during a run:

| `EventType` | When recorded |
|---|---|
| `TASK_STARTED` | Graph entry |
| `GUARDRAIL_CHECKED` | Input / output guardrail pass or fail |
| `MODEL_SELECTED` | Router picks a model tier |
| `TOOL_CALLED` | Any tool invocation (with `cached` flag) |
| `STEP_EXECUTED` | Each ReAct step |
| `TASK_COMPLETED` | Graph exit |
| `ERROR_OCCURRED` | Any unhandled exception |

### Phase logger

`services/governance/phase_logger.py` — `PhaseLogger` writes per-decision JSONL:

```
cache/phase_logs/<workflow_id>/decisions.jsonl
```

Records routing decisions (model tier chosen, reason, confidence) and evaluation decisions (continue vs. finish).

---

## Step-by-Step: Start a Session and Capture Logs

### Step 1 — Start the middleware (backend)

```bash
# from the repo root
python -m middleware
```

This:
- Loads `.env`
- Runs `setup_logging()` → writes structured logs per `logging.json`
- Registers `dev-agent` `AgentFacts` in `cache/agent_facts/`
- Starts LangGraph with SQLite checkpointer at `cache/checkpoints.db`
- Starts the black box recorder at `cache/black_box_recordings/`
- Serves on `http://localhost:8000`

Verify:

```bash
curl http://localhost:8000/healthz
# → {"status":"ok","profile":"dev","runtime":"langgraph"}
```

### Step 2 — Start the frontend

```bash
cd frontend
pnpm dev
# starts Next.js on http://localhost:3000
```

The browser posts to `/api/run/stream` (Next.js BFF), which forwards the request to `http://localhost:8000/run/stream` via `forwardToMiddleware`.

### Step 3 — Send a message and watch the SSE stream

Open `http://localhost:3000`. Type a message. In browser DevTools:

- **Network** tab → filter `stream` → click the request → **EventStream** sub-tab

You will see events like:

```
data: {"event":"RUN_STARTED","raw_event":{"trace_id":"a1b2c3...","run_id":"d4e5f6...","thread_id":"t-..."}}
data: {"event":"LLM_MESSAGE_STARTED","raw_event":{"trace_id":"a1b2c3...","message_id":"..."}}
data: {"event":"LLM_TOKEN_EMITTED","raw_event":{"trace_id":"a1b2c3...","delta":"Hello"}}
data: {"event":"TOOL_CALL_STARTED","raw_event":{"trace_id":"a1b2c3...","tool_name":"shell","args_json":"..."}}
data: {"event":"TOOL_RESULT_RECEIVED","raw_event":{"trace_id":"a1b2c3...","result":"..."}}
data: {"event":"RUN_FINISHED","raw_event":{"trace_id":"a1b2c3..."}}
data: [DONE]
```

**Copy the `trace_id` value** — use it to cross-correlate every other plane.

### Step 4 — Watch the middleware logs

In the terminal running `python -m middleware` you will see:

```
INFO  middleware.__main__  stream_ended run_id=d4e5f6... thread=t-... trace=a1b2c3... duration_ms=1240 errored=False
```

Graph-level logs from `orchestration.react_loop`, `services.guardrails`, `services.llm_config`, etc. are also written here (or to the log file configured by `logging.json`).

### Step 5 — Inspect the black box recording

```bash
ls cache/black_box_recordings/
cat cache/black_box_recordings/<workflow_id>/trace.jsonl | python -m json.tool
```

Each line is a `TraceEvent` with `event_type`, `workflow_id`, `timestamp`, `details`, and an `integrity_hash` that chains from the previous event.

Verify chain integrity programmatically:

```python
from services.governance.black_box import BlackBoxRecorder
from pathlib import Path

recorder = BlackBoxRecorder(Path("cache/black_box_recordings"))
bundle = recorder.export("<workflow_id>")
print(bundle["hash_chain_valid"])   # True = chain unbroken
print(len(bundle["events"]))        # number of recorded events
```

Export a full compliance bundle (joins AgentFacts + phase decisions):

```python
bundle = recorder.export_for_compliance(
    "<workflow_id>",
    agent_facts_registry=agent_facts_registry,
    phase_logger=phase_logger,
)
```

### Step 6 — Inspect phase logger decisions

```bash
cat cache/phase_logs/<workflow_id>/decisions.jsonl | python -m json.tool
```

Each line records the routing or evaluation decision: model tier selected, reason, confidence score.

### Step 7 — Inspect eval capture

`eval_capture.record()` writes via the `services.eval_capture` logger configured in `logging.json`. Look for log lines tagged `task_id` and `user_id`. With the dev middleware path, `task_id` will be empty until you apply the fix in the next section.

### Step 8 — Wire `TrustTraceRecord` emission (optional but recommended)

In `middleware/__main__.py`, change `_build_graph_and_runtime()`:

```python
from services.trace_service import TraceService, JsonlFileTraceSink

trace_service = TraceService(sinks=[JsonlFileTraceSink(cache_dir / "trust_traces")])
runtime = LangGraphRuntime(graph, trace_emit=trace_service.emit)
```

This writes `TrustTraceRecord` objects to `cache/trust_traces/` at `run_started` and `run_finished`, keyed by the same `trace_id` visible in the SSE stream.

---

## Known Gap — `trace_id` is Not Threaded into the Graph

**Current state:** `LangGraphRuntime.run()` passes only `thread_id` into the graph configurable:

```python
# langgraph_runtime.py line 128 — current
config = {"configurable": {"thread_id": thread_id}}
```

This means:
- `verify_authorize_log_node` falls back to `workflow_id` from graph state (empty for the middleware path).
- Black box recorder keys recordings under an empty `workflow_id`.
- Eval capture records have empty `task_id`.
- The `trace_id` visible in SSE events and middleware logs **cannot** be correlated with black box or phase log files.

**Fix (one line):**

```python
# langgraph_runtime.py — proposed fix
config = {
    "configurable": {
        "thread_id": thread_id,
        "trace_id":  trace_id,
        "workflow_id": trace_id,        # correlates black box + phase logs
        "task_id":   run_id,            # correlates eval capture
        "user_id":   identity.owner,    # correlates per-user eval analysis
    }
}
```

After this change, the `trace_id` from the SSE stream will match the `workflow_id` in every black box JSONL file, phase log, and eval capture record — giving you a **single correlation key across all five planes**.

---

## Cross-Correlation Reference

| Log surface | How to read it | Correlation key |
|---|---|---|
| Browser EventStream | DevTools → Network → EventStream tab | `trace_id` in every event payload |
| Middleware stdout | Terminal running `python -m middleware` | `trace=<trace_id>` in `stream_ended` |
| Black box JSONL | `cache/black_box_recordings/<id>/trace.jsonl` | `workflow_id` (should equal `trace_id` after fix) |
| Phase decisions JSONL | `cache/phase_logs/<id>/decisions.jsonl` | `workflow_id` |
| Eval capture logs | structured log file via `logging.json` | `task_id`, `user_id` |
| Trust trace JSONL | `cache/trust_traces/` (after wiring `trace_emit`) | `trace_id` |

---

## Key Source Files

| File | Role |
|---|---|
| `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` | Mints `trace_id`; translates LangGraph events to domain events |
| `agent_ui_adapter/translators/domain_to_ag_ui.py` | Embeds `trace_id` into AG-UI SSE payloads |
| `middleware/__main__.py` | Dev entry point; wires graph, runtime, identity; logs `stream_ended` |
| `orchestration/react_loop.py` | Graph nodes; drives black box + phase logger + eval capture |
| `services/governance/black_box.py` | Append-only JSONL recorder with SHA-256 chain |
| `services/governance/phase_logger.py` | Per-decision routing/evaluation logs |
| `services/eval_capture.py` | Per-LLM-call structured records keyed by `task_id` / `user_id` |
| `services/trace_service.py` | Fan-out sink for `TrustTraceRecord` emission |
| `trust/models.py` | `AgentFacts` (signed identity), `TrustTraceRecord` |
| `frontend/lib/adapters/runtime/self_hosted_langgraph_dev_client.ts` | Browser client; reads `trace_id` from SSE, never generates one |
| `frontend/lib/transport/sse_client.ts` | Parses AG-UI events; routes `raw_event.trace_id` to UI runtime |
| `frontend/app/api/run/stream/route.ts` | BFF route; forwards POST to middleware with bearer token |
