# Agent UI Adapter — Adapters Deep Dive

**Scope:** `agent_ui_adapter/adapters/` and the rules governing it
**Related documents:**
- `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md` — big-picture view of the full adapter ring
- `docs/Architectures/Architectures/FOUR_LAYER_ARCHITECTURE.md` — inner-layer rules this package builds on
- `docs/contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md` — step-by-step recipe for contributors

---

## Governing Thought

The four-layer backend (`trust/`, `services/`, `components/`, `orchestration/`) is framework-agnostic by design. The style guide forbids importing `langgraph` or `langchain` anywhere in `components/` or `services/`. That constraint is correct and should be preserved — it keeps the backend testable, portable, and independent of vendor choices.

The `agent_ui_adapter/adapters/` sub-package is the **explicit, bounded exception** to that rule. It is the single location in the entire repository where a third-party graph execution framework SDK is allowed to be imported. By confining SDK imports to one directory, the cost of a framework migration is bounded to that directory. No SDK type ever crosses the adapter boundary; everything yielded by an adapter is a `wire/domain_events.py` value. The rest of the adapter ring (`ports/`, `wire/`, `translators/`, `transport/`, `server.py`) remain framework-agnostic regardless of which runtime adapter is in use.

The design follows the same principle as the trust foundation's `utils/cloud_providers/` directory in the four-layer architecture: infrastructure-specific adapters are isolated behind a shared protocol, and the protocol boundary is the enforcement point.

---

## Architectural Identity

`adapters/` is the **driven (right-hand) side** of the hexagonal architecture. In hexagonal terms:

- The **port** is `agent_ui_adapter/ports/agent_runtime.py` — the `AgentRuntime` `@runtime_checkable` Protocol.
- The **adapter** is any module under `adapters/runtime/` that satisfies `AgentRuntime`.
- The **composition root** (`server.py` / `build_app(...)`) decides which adapter to inject at construction time.

Because the Protocol is `@runtime_checkable`, `isinstance(impl, AgentRuntime)` works at runtime without explicit inheritance. This means the conformance suite can assert structural correctness without mock frameworks, and adapters remain decoupled from the protocol definition by duck typing.

```
  server.py (composition root — driving side)
       │
       │  runtime: AgentRuntime  (injected at build_app())
       ▼
  ports/agent_runtime.py
  ┌─────────────────────────────────────────┐
  │  Protocol AgentRuntime                   │
  │    run(thread_id, input, identity)       │
  │    cancel(run_id)                        │
  │    get_state(thread_id)                  │
  └─────────────────────────────────────────┘
            ▲                    ▲
            │                    │
  adapters/runtime/       adapters/runtime/
  mock_runtime.py         langgraph_runtime.py
  (tests / scripted)      (production / LangGraph)
```

---

## The Problem `adapters/` Solves

Without an isolated adapter layer, three problems compound:

**Problem 1: Untestable server routes.** If `server.py` constructed a `LangGraphRuntime` directly, every test of a route would require LangGraph, a compiled graph, a live LLM or mock, and the full four-layer backend. A single failing dependency would collapse all SSE route tests.

**Problem 2: SDK types bleeding into the wire ring.** LangGraph's `astream_events` yields raw dicts with framework-specific keys (`on_chat_model_stream`, `on_tool_start`, etc.). Without an adapter to translate them, those shapes would appear in `translators/` and eventually in the AG-UI events sent to the client. A LangGraph version bump would then require changes in `translators/`, `transport/`, and possibly `wire/`.

**Problem 3: Symmetric test coverage gap.** Unit tests for the full SSE pipeline need a runtime that emits predictable, scripted events. Without `MockRuntime`, tests either mock at the protocol level (fragile, over-specified) or skip the stream-path logic entirely.

`adapters/` solves all three: the composition root injects either `MockRuntime` (tests) or `LangGraphRuntime` (production); the adapter translates SDK events to `DomainEvent`; the rest of the ring never changes when the SDK changes.

---

## The Adapter Grid

```
  adapters/
  │
  ├── runtime/                      (current: 2 implementations)
  │   ├── __init__.py
  │   ├── mock_runtime.py           MockRuntime — scripted, deterministic
  │   └── langgraph_runtime.py      LangGraphRuntime — wraps LangGraph astream_events
  │
  ├── transport/                    (Phase 3+ — named slot, no implementations yet)
  │                                 Will hold WebSocket or gRPC stream adapters if SSE
  │                                 proves insufficient for a use case.
  │
  ├── storage/                      (Phase 3+ — named slot, no implementations yet)
  │                                 Will hold alternative thread/run store backends
  │                                 when the in-memory _ThreadStore in server.py
  │                                 needs a persistent replacement.
  │
  └── memory/                       (Phase 3+ — named slot, no implementations yet)
                                    Will hold alternative LongTermMemory adapters
                                    if multiple backends (vector DB vs. in-process)
                                    need to be swapped at composition time.
```

The named-but-empty slots are documented now so their directory names are decided before any implementation arrives, preventing ad-hoc naming. No slot directory is created until a second concrete backend exists (abstraction-introduction principle). A single backend does not need an adapter: it can be constructed directly in `build_app`.

---

## What Belongs in `adapters/`

A module belongs under `adapters/` if and only if it satisfies **all** of the following criteria:

1. **Wraps an external technology.** The module's primary purpose is to wrap a third-party SDK, a network protocol, a storage engine, or any dependency that is not stdlib or an in-project type.

2. **Implements a port.** The module provides a concrete implementation of a `Protocol` defined in `ports/` (or a transport/storage contract owned by a sibling `transport/` or `storage/` module in the future). It must satisfy `isinstance(impl, SomePort)`.

3. **Translates without leaking.** The module converts between the external technology's types and the canonical `wire/` types. No type defined outside `agent_ui_adapter/wire/` or `trust/` is re-exported or yielded past the module boundary.

4. **Independently swappable.** Replacing one adapter with another must not require any change in `wire/`, `translators/`, `transport/`, or `ports/`. The composition root picks the adapter; nothing else knows which adapter is active.

A module that satisfies criteria 1 and 3 but not 2 — for example, a general-purpose SDK helper — belongs in `utils/` or a new horizontal service, not in `adapters/`.

---

## Contents: `adapters/runtime/`

### `mock_runtime.py` — MockRuntime

`MockRuntime` is a fully scripted `AgentRuntime` implementation for use in tests above the translator and transport layers (sprint sprints designate these as S3+: translators, transport, server routes). It lives in **production code** under `adapters/runtime/` rather than in `tests/` because:

- Test helpers in `tests/` are not importable by integration test harnesses in other packages.
- The composition root (`server.py`) needs a swap-in that is structurally identical to the production adapter, not a test-only mock.
- Scripted event providers are a recognized pattern (Pattern 6 in the sprint TDD catalog) and are considered part of the adapter family.

**Constructor parameters:**

| Parameter | Type | Purpose |
|---|---|---|
| `events` | `list[DomainEvent]` | The ordered sequence of events to yield from `run()`. |
| `error_after` | `int \| None` | If set, raises `RuntimeError` after emitting `error_after` events. Used to test failure-path handling in `server.py`. |
| `states` | `dict[str, ThreadState] \| None` | Seed state for specific `thread_id` values. |
| `strict_state` | `bool` | If `True`, `get_state()` raises `KeyError` for unknown thread IDs instead of returning a default empty state. |

**Behavioral contract:**

- `run()` yields `self._events` in order. If `error_after=N`, raises `RuntimeError` after yielding event at index N.
- `cancel(run_id)` adds `run_id` to `self.cancelled_runs` (a `set`). Idempotent. Inspectable in tests.
- `get_state(thread_id)` returns the seeded state if the thread_id is in `self._states`, otherwise returns a default `ThreadState` with empty messages (or raises `KeyError` if `strict_state=True`).

```python
# Typical test usage
runtime = MockRuntime(
    events=[
        RunStartedDomain(trace_id="t", run_id="r", thread_id="th"),
        LLMTokenEmitted(trace_id="t", message_id="m", delta="Hello"),
        RunFinishedDomain(trace_id="t", run_id="r", thread_id="th"),
    ]
)
```

### `langgraph_runtime.py` — LangGraphRuntime

`LangGraphRuntime` is the production adapter wrapping a LangGraph compiled app. It is the **only module in the entire `agent_ui_adapter/` package that imports from LangGraph**.

**Structural protocol for the underlying graph:**

```python
class _CompiledGraphLike(Protocol):
    def astream_events(
        self, input: Any, config: dict | None = ..., version: str = ...
    ) -> AsyncIterator[dict]: ...

    async def aget_state(self, config: dict) -> Any: ...
```

`_CompiledGraphLike` is a structural `Protocol` defined locally in the module. This means `LangGraphRuntime` does not import `CompiledGraph` from LangGraph at all — it only requires that the injected object has the right shape. Tests can pass an `_EmptyGraph` stub without installing LangGraph.

**Constructor parameters:**

| Parameter | Type | Purpose |
|---|---|---|
| `graph` | `_CompiledGraphLike` | The compiled graph instance (a LangGraph `CompiledGraph` in production, any structural duck-type in tests). |
| `trace_emit` | `Callable[[TrustTraceRecord], None] \| None` | Optional callback for emitting trust trace records. If `None`, trace emission is silently skipped. Wired by the composition root to `TraceService.record()` in production. |

**Internal state:**

- `_run_tasks: dict[str, asyncio.Task]` — registry of in-flight async tasks keyed by `run_id`. Used by `cancel()` to locate and cancel the task.

---

## Runtime Translation Contract

The translation contract specifies the exact mapping between raw LangGraph `astream_events` dicts and `DomainEvent` instances. This contract is currently documented only in docstrings; this section is the canonical formal specification.

### LangGraph Event → DomainEvent Mapping

The `_translate(raw, trace_id)` static method on `LangGraphRuntime` applies the following table. The raw dict shape is `{"event": str, "data": dict, "name": str, "run_id": str}`.

| LangGraph `event` key | Condition | Emitted `DomainEvent` | Notes |
|---|---|---|---|
| `on_chat_model_stream` | `chunk.content` is a non-empty `str` | `LLMTokenEmitted(trace_id, message_id=run_id, delta=content)` | If `chunk.content` is empty or not a `str`, returns `None` (no event emitted). |
| `on_chat_model_start` | (always) | `LLMMessageStarted(trace_id, message_id=run_id)` | |
| `on_chat_model_end` | (always) | `LLMMessageEnded(trace_id, message_id=run_id)` | |
| `on_tool_start` | (always) | `ToolCallStarted(trace_id, tool_call_id, tool_name, args_json)` | `tool_call_id` resolved from `data["tool_call_id"]`, then `raw["id"]`, then `run_id`. `args_json` is `json.dumps(data["input"])` with `default=str, sort_keys=True`; falls back to `str(input)` on serialization error. |
| `on_tool_end` | (always) | `ToolResultReceived(trace_id, tool_call_id, result=str(output))` | `tool_call_id` resolved same as `on_tool_start`. `output` is `data["output"]`. |
| any other value | (always) | `None` — no event emitted | Unmapped LangGraph events are silently dropped. This is intentional: new LangGraph events should not crash the adapter. |

**`run_id` field resolution for `tool_call_id`:** resolved in priority order: `data.get("tool_call_id")` → `raw.get("id")` → `event_run_id` (the LangGraph event's own `run_id`).

### `trace_id` Propagation Rule

One `trace_id` is generated per `run()` call using `uuid.uuid4().hex` at the start of `run()`, before any events are yielded. The same `trace_id` is attached to:

- Every `DomainEvent` yielded during the run.
- Both `TrustTraceRecord` instances emitted by `_emit_trace()` (`run_started` and `run_finished`).
- The `RunStartedDomain` and `RunFinishedDomain` events.

The `trace_id` is **not** derived from the LangGraph `run_id` or any external identifier. It is a fresh identifier owned by the adapter for the duration of the run. The `server.py` SSE generator propagates it into every AG-UI event via `to_ag_ui(domain_event)` → `raw_event={"trace_id": trace_id}`.

### `run_id` Propagation Rule

One `run_id` is generated per `run()` call using `uuid.uuid4().hex`. It is distinct from `trace_id`:

| Field | Scope | Purpose |
|---|---|---|
| `trace_id` | All events in one run | Correlation key for log aggregation and trust trace |
| `run_id` | Run lifecycle events | Identifies the run in `RunStartedDomain`, `RunFinishedDomain`, run registry in `server.py`, `TrustTraceRecord.details["run_id"]` |

### Error Translation Rule

Any `Exception` raised by `self._graph.astream_events(...)` during a run is caught, translated, and never allowed to escape the adapter:

```
Exception raised by graph
    │
    ▼
error: str | None = f"{type(exc).__name__}: {exc}"
    │
    ▼
_emit_trace(..., event_type="run_finished", outcome="fail",
            details={"run_id": run_id, "error": error})
    │
    ▼
yield RunFinishedDomain(trace_id=trace_id, run_id=run_id,
                        thread_id=thread_id, error=error)
```

The `server.py` translator `to_ag_ui(RunFinishedDomain(error=...))` then emits a `RunError` AG-UI event to the client, so the error is surfaced through the normal SSE channel without exposing a raw Python stack trace.

### Cancellation Semantics

`cancel(run_id)` is **idempotent** in all cases:

| State | Behavior |
|---|---|
| `run_id` not in `_run_tasks` (unknown or already finished) | No-op. Does not raise. |
| `run_id` in `_run_tasks`, task not done | Calls `task.cancel()` and removes from `_run_tasks`. |
| `run_id` in `_run_tasks`, task already done | Removes from `_run_tasks`. `task.cancel()` is not called (LangGraph task is finished). |

The `_run_tasks` registry is populated by the caller at the time the run task is started. In the current implementation, `server.py` does not yet wire task registration; this is a Phase 2 enhancement. The registry mechanism is in place; task registration is the deferred step.

### Trust Trace Emission Boundaries

Every `LangGraphRuntime.run()` emits exactly **two** `TrustTraceRecord` instances when `trace_emit` is wired:

| Record | `event_type` | `outcome` | When emitted |
|---|---|---|---|
| Run started | `"run_started"` | `"pass"` | Before the first `DomainEvent` is yielded (before entering `astream_events`) |
| Run finished | `"run_finished"` | `"pass"` or `"fail"` | After `astream_events` exhausts or raises, before `RunFinishedDomain` is yielded |

Both records carry `layer="L4"` and `details={"run_id": ..., "thread_id": ...}`. The `run_finished` record carries `details["error"]` (the translated error string or `None`).

**Failure isolation:** If `trace_emit` itself raises an exception, the exception is caught, logged via the module logger at `ERROR` level, and **silently swallowed**. A failing trace callback must never interrupt the run or the client's SSE stream.

```python
def _emit_trace(self, *, trace_id, agent_id, event_type, outcome, details=None):
    if self._trace_emit is None:
        return
    record = TrustTraceRecord(...)
    try:
        self._trace_emit(record)
    except Exception as exc:
        _logger.error("trace_emit failed: %s: %s", type(exc).__name__, exc)
        # exception is swallowed — never propagates to the caller
```

---

## Hexagonal Dependency Rules for `adapters/`

Every module under `adapters/` must satisfy the following import table. These rules are enforced by the architecture test suite.

| From `adapters/**` | To | Allowed? | Rationale |
|---|---|---|---|
| adapter module | `agent_ui_adapter/ports/` | **Yes** | Adapter implements the port; must import Protocol to satisfy `isinstance` check |
| adapter module | `agent_ui_adapter/wire/` | **Yes** | Adapter yields wire-shape values (`DomainEvent`, `ThreadState`) |
| adapter module | `trust/` | **Yes** | Accepts `AgentFacts` (identity), emits `TrustTraceRecord` (trust trace). Trust foundation is a shared kernel. |
| adapter module | third-party SDK (LangGraph, etc.) | **Yes — adapters/ only** | This is the one designated SDK boundary |
| adapter module | another `adapters/` module | **FORBIDDEN** | Adapters are siblings; cross-adapter coupling creates hidden shared state and makes individual adapters harder to swap |
| adapter module | `agent_ui_adapter/translators/` | **FORBIDDEN** | Translators consume adapter output; importing translators from an adapter reverses the dependency arrow |
| adapter module | `agent_ui_adapter/transport/` | **FORBIDDEN** | Transport encodes wire values; adapters produce wire values. Transport is downstream of adapters. |
| adapter module | `agent_ui_adapter/server.py` | **FORBIDDEN** | The composition root is the outermost layer; nothing imports it |
| adapter module | `services/` (direct module import) | **FORBIDDEN** | Services are injected by the composition root as constructor arguments. Direct imports create implicit service-location; the adapter must not know which service implementation is used. |
| adapter module | `components/`, `orchestration/`, `governance/` | **FORBIDDEN** | Adapter ring sits above the four-layer backend; these layers are accessed only through the graph SDK (via `_CompiledGraphLike`) |

**Constructor injection rule:** When an adapter needs a service (e.g., `TraceService.record` as the `trace_emit` callback), the service is passed as a constructor argument by `build_app()`. The adapter stores only a callable or a thin protocol; it does not name `TraceService` or import `services/trace_service.py`.

---

## Conformance Test Bundle

Every implementation added to `adapters/runtime/` must be registered in the parametrized conformance suite at `tests/agent_ui_adapter/adapters/runtime/test_conformance.py`. The suite currently covers:

| Test | Asserts |
|---|---|
| `test_satisfies_protocol` | `isinstance(make_runtime(), AgentRuntime)` is `True` |
| `test_happy_path_run_completes_without_raising` | Exhausting the run does not raise; if any events are emitted, the last is `RunFinishedDomain` |
| `test_cancel_does_not_raise` | `cancel(run_id="r1")` does not raise for an unknown run_id |

To register a new runtime, add a factory function `_make_<name>()` and append it to the `@pytest.mark.parametrize` list:

```python
@pytest.mark.parametrize(
    "make_runtime",
    [_make_mock, _make_langgraph, _make_new_runtime],  # add here
    ids=["MockRuntime", "LangGraphRuntime", "NewRuntime"],
)
class TestAgentRuntimeConformance:
    ...
```

The conformance suite is the mandatory gate. A new adapter that does not appear in the parametrize list is considered incomplete regardless of any other tests written for it.

---

## Composition Root Pattern

`server.py:build_app()` is the **only place in the codebase where a concrete adapter class is named**. This is the composition root pattern: the adapter is chosen and constructed at the outermost layer, then injected inward.

```python
# Production wiring (app.py or entrypoint)
from agent_ui_adapter.adapters.runtime.langgraph_runtime import LangGraphRuntime
from agent_ui_adapter.server import build_app

runtime = LangGraphRuntime(
    graph=compiled_graph,
    trace_emit=trace_service.record,
)
app = build_app(
    runtime=runtime,
    jwt_verifier=real_jwt_verifier,
    agent_facts={"agent-id": facts},
    authorization_service=authz_service,
    trace_service=trace_service,
)
```

```python
# Test wiring (test_server.py or conftest.py)
from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.server import build_app

runtime = MockRuntime(events=[
    RunStartedDomain(trace_id="t", run_id="r", thread_id="th"),
    RunFinishedDomain(trace_id="t", run_id="r", thread_id="th"),
])
app = build_app(
    runtime=runtime,
    jwt_verifier=InMemoryJwtVerifier({...}),
    agent_facts={"test-agent": facts},
)
```

`build_app` itself imports `AgentRuntime` from `ports/` (the Protocol), not from `adapters/` (the implementations). This preserves the hexagonal inversion: the composition root depends on the port, not on any specific adapter.

---

## Logging Convention

Each adapter gets its own named logger following the module path convention:

| Adapter | Logger name |
|---|---|
| `LangGraphRuntime` | `agent_ui_adapter.adapters.langgraph_runtime` |
| `MockRuntime` | (no logger — scripted, deterministic, no operational events) |
| Any new runtime `foo_runtime.py` | `agent_ui_adapter.adapters.foo_runtime` |

The logger for `LangGraphRuntime` is used exclusively for:
- `ERROR` level: `trace_emit` failures (swallowed exception details).
- `WARNING` level (future): unexpected LangGraph event shapes that cannot be translated.

Adapters do not log individual domain events — that is the responsibility of `server.py` (which logs at the SSE generator boundary) and `TraceService` (which receives `TrustTraceRecord` events).

To add a per-adapter log file, extend `logging.json` following the H4 pattern from the four-layer style guide:

```json
{
    "handlers": {
        "adapter_langgraph": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "adapter_langgraph.log"
        }
    },
    "loggers": {
        "agent_ui_adapter.adapters.langgraph_runtime": {
            "handlers": ["adapter_langgraph"],
            "level": "DEBUG",
            "propagate": false
        }
    }
}
```

---

## Phase Progression

The adapter family grows across three phases. The `AgentRuntime` Protocol and `wire/domain_events.py` types remain stable across all three phases. Only the adapters and their downstream wiring change.

| Phase | Status | Runtime adapters | Feature additions |
|---|---|---|---|
| **Phase 1** | Current | `MockRuntime`, `LangGraphRuntime` | Baseline: `run_started` / `run_finished` trust trace records; `_translate` covers 5 LangGraph event types |
| **Phase 2** | Planned | Same + HITL `request_approval` wiring | `StateMutated.delta` populated via JSON Patch; `sealed_envelope.py` used for HITL round-trip; `_translate` extended for HITL interrupt events; `_run_tasks` populated for real cancellation support; additional graph engine adapters if a second runtime is needed |
| **Phase 3** | Deferred | Same + remote runtime adapter | Remote runtime adapter over gRPC or HTTP for distributed graph execution; multi-runtime selection by request attribute (e.g., route `thread_id` prefix to different graph backends); new adapter families under `adapters/transport/`, `adapters/storage/`, `adapters/memory/` — each introduced only when a second concrete backend exists |

### Phase 2 Extension Points

| Feature | Status | Adapter change | Grid layer |
|---|---|---|---|
| HITL `request_approval` wiring | Planned | `langgraph_runtime._translate` handles interrupt event; `sealed_envelope.py` integration | `adapters/runtime/langgraph_runtime.py` |
| JSON Patch `StateMutated` | Planned | `langgraph_runtime._translate` maps `on_chain_stream` state snapshot to `StateMutated(delta=[...])` | `adapters/runtime/langgraph_runtime.py` |
| Task registration for cancellation | Planned | `run()` registers `asyncio.Task` in `_run_tasks`; composition root passes the returned task handle | `adapters/runtime/langgraph_runtime.py` |
| AutoGen/CrewAI runtime | Deferred | New `autogen_runtime.py` or `crewai_runtime.py` following the same `_translate` + `_emit_trace` structure | `adapters/runtime/` |
| `adapters/transport/WebSocketRuntime` | Deferred | Introduce only when SSE proves insufficient for a second client type | `adapters/transport/` (new sub-family) |
| Remote gRPC runtime | Deferred | `adapters/runtime/grpc_runtime.py`; wraps a gRPC stub behind `_CompiledGraphLike`-equivalent Protocol | `adapters/runtime/grpc_runtime.py` |

**Abstraction-introduction principle:** each Phase 3 feature is introduced only when the second concrete implementation exists. A single gRPC runtime does not need a new port; it is another concrete `AgentRuntime`. A new `ports/AgentStorage` Protocol is introduced only when two storage backends compete.

---

## Relationship to the Four-Layer Architecture

`adapters/` does not alter the four-layer rules defined in `docs/Architectures/Architectures/FOUR_LAYER_ARCHITECTURE.md`. It builds **on top** of those rules without modifying them.

| Four-layer concern | Adapter ring relationship |
|---|---|
| Trust Foundation (`trust/`) | Imported directly by adapters. `AgentFacts` is the identity parameter to `run()`. `TrustTraceRecord` is the trust event emitted via `_emit_trace()`. |
| Horizontal Services (`services/`) | Never imported by adapters at module scope. Injected by the composition root as constructor arguments (e.g., `trace_emit=trace_service.record`). Adapters hold a callable, not a service reference. |
| Vertical Components (`components/`) | Not visible to adapters. Components execute inside the graph; the adapter consumes graph output as raw dicts. |
| Orchestration Layer (`orchestration/`) | Not visible to adapters. The LangGraph compiled graph is the representation of the orchestration layer; the adapter wraps the graph's streaming interface. |
| Meta-Layer (`governance/`) | Not visible to adapters. Governance events are emitted by the trust trace system after the run completes; they are not part of the per-run SSE stream. |

The four-layer dependency rule "Any → Orchestration is FORBIDDEN" applies symmetrically to the adapter ring: `adapters/` may not call `orchestration/` directly. It calls the graph via the `_CompiledGraphLike` structural Protocol, which the compiled graph (an orchestration artifact) satisfies at runtime. The adapter does not know it is talking to LangGraph; it knows only that it has an object with `astream_events` and `aget_state`.

The adapter ring's own layer, as a whole, sits above the Meta-Layer. It is not part of the four-layer grid and does not participate in the four-layer dependency rules. It consumes the grid's outputs (via graph + DI) and produces AG-UI events for external clients.
