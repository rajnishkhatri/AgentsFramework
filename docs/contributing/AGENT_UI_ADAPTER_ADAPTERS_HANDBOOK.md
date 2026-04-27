# Contributor Handbook: Adding a New Adapter to `agent_ui_adapter/adapters/`

**Audience:** Contributors who want to add a new concrete `AgentRuntime` implementation or a new adapter family.
**Prerequisite reading:**
- `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md` — big-picture view of the adapter ring.
- `docs/Architectures/AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md` — full architectural spec for `adapters/`.

---

## 1. Decision Tree — Do You Need a New Adapter?

Work through this tree before writing any code.

```
Does the new code wrap an external technology
(SDK, network protocol, storage engine)?
│
├── NO  ─────────────────────────────────────────────────────────
│        Is it a pure data shape or schema?      → wire/
│        Is it a pure translation function?      → translators/
│        Is it SSE / connection management?      → transport/
│        Is it domain infrastructure (no SDK)?   → services/
│        Is it domain logic / pipeline step?     → components/
│
└── YES
     │
     Does it implement an existing port in ports/?
     │
     ├── YES
     │     adapters/runtime/    (implements AgentRuntime)
     │     adapters/transport/  (Phase 3 — when second transport exists)
     │     adapters/storage/    (Phase 3 — when second store exists)
     │     adapters/memory/     (Phase 3 — when second memory backend exists)
     │
     └── NO
           Does a second concrete implementation of the same thing
           already exist in the project?
           │
           ├── YES → Define a new port in ports/, then create the adapter.
           │
           └── NO  → Don't create an adapter family yet.
                     Build the single implementation directly (possibly
                     inside server.py or a new service). Apply the
                     abstraction-introduction principle: create the port
                     and adapter family when the second implementation arrives.
```

---

## 2. Where Does It Go? Naming Convention

### New `AgentRuntime` (most common case)

| Artifact | Location | Name pattern |
|---|---|---|
| Adapter module | `agent_ui_adapter/adapters/runtime/` | `<technology>_runtime.py` |
| Adapter class | inside the module | `<Technology>Runtime` |
| Structural SDK protocol | inside the adapter module | `_<Technology>Like` (private, underscore prefix) |
| Tests | `tests/agent_ui_adapter/adapters/runtime/` | `test_<technology>_runtime.py` |

Examples: `autogen_runtime.py` / `AutoGenRuntime`, `grpc_runtime.py` / `GRPCRuntime`.

### New adapter family (Phase 3+)

Only when a second concrete backend exists for the same concern:

| Artifact | Location |
|---|---|
| New port Protocol | `agent_ui_adapter/ports/<concern>.py` |
| Adapter sub-directory | `agent_ui_adapter/adapters/<concern>/` |
| First implementation | `agent_ui_adapter/adapters/<concern>/<technology>_<concern>.py` |
| Conformance suite | `tests/agent_ui_adapter/adapters/<concern>/test_conformance.py` |

---

## 3. Step-by-Step Recipe: Adding a New `AgentRuntime`

The following steps use `autogen_runtime.py` as a concrete example. Replace `autogen` / `AutoGen` with your technology name throughout.

### Step 1 — Create the adapter module

Create `agent_ui_adapter/adapters/runtime/autogen_runtime.py` with the module docstring:

```python
"""AutoGenRuntime — production AgentRuntime wrapping AutoGen.

Translation contract:
- Accepts a <describe the SDK handle> as `graph`.
- Translates <list the SDK event types> to DomainEvent.
- Exceptions raised by the SDK are caught and translated to
  RunFinishedDomain(error=<message>).
- Every emitted event carries the same trace_id for the run.
"""
```

### Step 2 — Define the structural SDK protocol

Define a local `Protocol` for the minimum SDK surface you need. Do **not** import the SDK's own class:

```python
from typing import Any, AsyncIterator, Protocol

class _AutoGenLike(Protocol):
    """Structural shape of the AutoGen agent handle (subset)."""

    async def run_stream(
        self, task: str, cancellation_token: Any = ...
    ) -> AsyncIterator[dict]: ...
```

This keeps tests free of the real SDK. Any object with the right shape satisfies the protocol.

### Step 3 — Implement the three `AgentRuntime` methods

```python
import asyncio, logging, uuid
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Callable

from agent_ui_adapter.wire.agent_protocol import ThreadState
from agent_ui_adapter.wire.domain_events import DomainEvent, RunFinishedDomain, RunStartedDomain
from trust.models import AgentFacts, TrustTraceRecord

_logger = logging.getLogger("agent_ui_adapter.adapters.autogen_runtime")


class AutoGenRuntime:
    """Production AgentRuntime wrapping an AutoGen agent handle."""

    def __init__(
        self,
        agent: _AutoGenLike,
        *,
        trace_emit: Callable[[TrustTraceRecord], None] | None = None,
    ) -> None:
        self._agent = agent
        self._trace_emit = trace_emit
        self._run_tasks: dict[str, asyncio.Task] = {}

    async def run(
        self, thread_id: str, input: dict[str, Any], identity: AgentFacts
    ) -> AsyncIterator[DomainEvent]:
        trace_id = uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        self._emit_trace(trace_id=trace_id, agent_id=identity.agent_id,
                         event_type="run_started", outcome="pass",
                         details={"run_id": run_id, "thread_id": thread_id})
        yield RunStartedDomain(trace_id=trace_id, run_id=run_id, thread_id=thread_id)

        error: str | None = None
        try:
            async for raw in self._agent.run_stream(input.get("task", "")):
                event = self._translate(raw, trace_id)
                if event is not None:
                    yield event
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        self._emit_trace(trace_id=trace_id, agent_id=identity.agent_id,
                         event_type="run_finished",
                         outcome="fail" if error else "pass",
                         details={"run_id": run_id, "thread_id": thread_id, "error": error})
        yield RunFinishedDomain(trace_id=trace_id, run_id=run_id,
                                thread_id=thread_id, error=error)

    async def cancel(self, run_id: str) -> None:
        task = self._run_tasks.pop(run_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def get_state(self, thread_id: str) -> ThreadState:
        now = datetime.now(UTC)
        return ThreadState(
            thread_id=thread_id, user_id="autogen",
            messages=[], created_at=now, updated_at=now,
        )
```

### Step 4 — Implement `_translate` and `_emit_trace`

Implement the translation method. Map SDK event types to `DomainEvent` variants. Return `None` for unmapped events — never raise for unknown event types, as SDK versions may add new events.

```python
    @staticmethod
    def _translate(raw: dict, trace_id: str) -> DomainEvent | None:
        ev = raw.get("type", "")
        # ... map SDK event types to DomainEvent variants ...
        return None  # default: drop unknown events

    def _emit_trace(self, *, trace_id, agent_id, event_type, outcome, details=None):
        if self._trace_emit is None:
            return
        record = TrustTraceRecord(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            trace_id=trace_id,
            agent_id=agent_id,
            layer="L4",
            event_type=event_type,
            details=details or {},
            outcome=outcome,
        )
        try:
            self._trace_emit(record)
        except Exception as exc:
            _logger.error("trace_emit failed: %s: %s", type(exc).__name__, exc)
```

### Step 5 — Add `__all__`

```python
__all__ = ["AutoGenRuntime"]
```

### Step 6 — Add to the conformance suite

Open `tests/agent_ui_adapter/adapters/runtime/test_conformance.py` and add a factory:

```python
def _make_autogen() -> AgentRuntime:
    class _EmptyAgent:
        async def run_stream(self, task, cancellation_token=None):
            if False:
                yield  # empty async generator

    return AutoGenRuntime(agent=_EmptyAgent())
```

Then add it to the `@pytest.mark.parametrize` list:

```python
@pytest.mark.parametrize(
    "make_runtime",
    [_make_mock, _make_langgraph, _make_autogen],
    ids=["MockRuntime", "LangGraphRuntime", "AutoGenRuntime"],
)
class TestAgentRuntimeConformance:
    ...
```

### Step 7 — Write unit tests for the new adapter

Create `tests/agent_ui_adapter/adapters/runtime/test_autogen_runtime.py`. Tests should cover:

- Happy path: a scripted sequence of SDK events maps to the expected `DomainEvent` sequence.
- Empty run: no SDK events → only `RunStartedDomain` + `RunFinishedDomain(error=None)` are emitted.
- Error path: SDK raises an exception → `RunFinishedDomain(error=...)` is the last event.
- `cancel()` idempotency: calling `cancel("unknown")` does not raise.
- `trace_emit` failure isolation: if `trace_emit` raises, `run()` completes normally and logs the error.

### Step 8 — Add a logging entry (if needed)

If the adapter produces operational logs worth routing to a dedicated file, extend `logging.json`:

```json
{
    "handlers": {
        "adapter_autogen": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "adapter_autogen.log"
        }
    },
    "loggers": {
        "agent_ui_adapter.adapters.autogen_runtime": {
            "handlers": ["adapter_autogen"],
            "level": "DEBUG",
            "propagate": false
        }
    }
}
```

### Step 9 — Wire into `build_app` when it becomes the production default

When the new adapter replaces `LangGraphRuntime` as the production default, update the entry point that calls `build_app(runtime=...)`. Do not change `build_app` itself — only the caller changes.

---

## 4. Definition of Done

The adapter is complete when all of the following are true:

- [ ] Module is under `agent_ui_adapter/adapters/runtime/<name>_runtime.py`.
- [ ] Class implements the three `AgentRuntime` methods: `run`, `cancel`, `get_state`.
- [ ] `run()` always ends with `RunFinishedDomain` if it yields any events.
- [ ] Every yielded `DomainEvent` carries the same `trace_id` for the run.
- [ ] No SDK type is yielded or re-exported past the module boundary. Only `wire/` and `trust/` types exit.
- [ ] `cancel()` is idempotent for unknown `run_id` values.
- [ ] Exceptions from the SDK are caught and translated to `RunFinishedDomain(error=...)`.
- [ ] `_emit_trace` failures are logged and swallowed; they never interrupt `run()`.
- [ ] A local structural `Protocol` (`_<Technology>Like`) is defined so tests do not require the real SDK.
- [ ] `__all__` is defined.
- [ ] Module logger is named `agent_ui_adapter.adapters.<technology>_runtime`.
- [ ] Adapter is registered in `test_conformance.py` parametrize list.
- [ ] All three conformance tests pass: `isinstance`, happy path ending with `RunFinishedDomain`, `cancel` idempotency.
- [ ] Unit tests cover happy path, empty run, error path, cancel idempotency, `trace_emit` isolation.
- [ ] `mypy` and `ruff` pass with no new errors.

---

## 5. Common Pitfalls

| Do | Not |
|---|---|
| Accept services as constructor arguments: `def __init__(self, ..., trace_emit: Callable | None = None)` | Import `services/trace_service.py` at module scope |
| Use a local structural `Protocol` for the SDK handle: `class _MySDKLike(Protocol): ...` | Import the SDK's concrete class at module scope (causes import error when SDK is not installed) |
| Return `None` from `_translate` for unknown event types | Raise for unknown event types (SDK version bumps add new events; raising breaks existing runs) |
| Catch all exceptions from the SDK inside `run()` and translate to `RunFinishedDomain(error=...)` | Let exceptions escape `run()` (they crash the SSE generator in `server.py`) |
| Catch exceptions inside `_emit_trace` and log them | Let trace failures propagate (a broken trace service must not interrupt the agent run) |
| Generate fresh `trace_id` and `run_id` with `uuid.uuid4().hex` at the start of `run()` | Reuse the thread_id, input dict keys, or any caller-provided value as trace_id |
| Write the empty-run test first (no events → `RunFinishedDomain`) | Skip the empty-run test (it covers the `error=None` path, which is the most common SSE edge case) |
| Populate `_run_tasks` when creating the async task | Skip task registration and assume cancel is unnecessary (Phase 2 requires it) |

---

## 6. Worked Example: `LangGraphRuntime`

The reference implementation for all the patterns in this handbook is `LangGraphRuntime` in `agent_ui_adapter/adapters/runtime/langgraph_runtime.py`. Here is how the nine steps map to that file:

| Step | Location in `langgraph_runtime.py` |
|---|---|
| 1. Module with docstring | Lines 1–27: module docstring with translation contract table |
| 2. Structural SDK protocol | `_CompiledGraphLike` Protocol (lines 54–65): defines `astream_events` + `aget_state` |
| 3. Three `AgentRuntime` methods | `run()` (lines 106–152), `cancel()` (lines 154–158), `get_state()` (lines 159–191) |
| 4. `_translate` + `_emit_trace` | `_emit_trace()` (lines 80–104), `_translate()` (lines 195–247) |
| 5. `__all__` | Line 250 |
| 6. Conformance suite registration | `tests/agent_ui_adapter/adapters/runtime/test_conformance.py` `_make_langgraph` factory |
| 7. Unit tests | `tests/agent_ui_adapter/adapters/runtime/test_langgraph_runtime.py` |
| 8. Logger | `_logger = logging.getLogger("agent_ui_adapter.adapters.langgraph_runtime")` (line 51) |
| 9. Composition root wiring | Called from entry point / test via `build_app(runtime=LangGraphRuntime(...))` |

The five LangGraph event type mappings in `_translate` follow the exact shape described in the deep-dive document's `Translation Contract` section. Any new adapter should produce a similar mapping table in its module docstring.

---

## 7. When to Introduce a New Adapter Family

The abstraction-introduction principle: **build the Protocol and the adapter sub-directory only when the second concrete implementation exists.**

| Situation | Correct action |
|---|---|
| One storage backend (the current in-memory `_ThreadStore`) | No `adapters/storage/`, no `ports/AgentStorage`. The single backend is constructed directly in `build_app`. |
| A second storage backend is added (e.g., Redis-backed store) | Define `ports/agent_storage.py` (Protocol), create `adapters/storage/` directory, move the in-memory backend into `adapters/storage/in_memory_storage.py`, create `adapters/storage/redis_storage.py`. |
| One transport (SSE) | No `adapters/transport/`, no `ports/AgentTransport`. SSE is wired directly in `server.py`. |
| A second transport is needed (e.g., WebSocket) | Define `ports/agent_transport.py`, create `adapters/transport/` directory with `sse_transport.py` and `websocket_transport.py`. |
| One graph engine (LangGraph) | `LangGraphRuntime` exists. No new port needed (it is already an `AgentRuntime`). |
| A second graph engine is added (e.g., AutoGen) | Add `autogen_runtime.py` following this handbook. No new port — `AgentRuntime` already accommodates both. |

The cost of prematurely creating a port and adapter family is a directory with one implementation, a protocol that one class satisfies, and future contributors misreading the abstractions as more flexible than they are. The cost of deferring is that the first implementation is constructed directly — which is always the simpler code. Refactoring to the adapter pattern when the second backend arrives is a contained, mechanical change.
