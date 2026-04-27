# Agent UI Adapter — Architecture Overview

**Scope:** `agent_ui_adapter/` package
**Related documents:**

- `docs/Architectures/Architectures/FOUR_LAYER_ARCHITECTURE.md` — the inner-layer rules this package builds on top of
- `docs/Architectures/AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md` — exhaustive spec for `adapters/`
- `docs/contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md` — contributor recipe for adding a new adapter

---

## Governing Thought

The four-layer architecture (`FOUR_LAYER_ARCHITECTURE.md`) defines the backend: Trust Foundation, Horizontal Services, Vertical Components, Orchestration, and Meta-Layer. None of those layers were designed to speak AG-UI events over HTTP. Adding that responsibility inside the orchestration or horizontal layers would violate the style guide: orchestration nodes must be topology-only thin wrappers, horizontal services must be domain-agnostic infrastructure.

`agent_ui_adapter/` is the answer to that constraint. It is an **outer adapter ring** that sits entirely above the four-layer grid. It introduces exactly **one new abstraction**: the `AgentRuntime` protocol in `agent_ui_adapter/ports/agent_runtime.py`. Everything else in the package is either a pure data shape, a pure translation function, an SSE transport utility, or a composition root. No domain logic is introduced. The four-layer backend is consumed via constructor injection — the adapter ring never imports a service at module scope.

The single-abstraction principle is enforced by rule R9 in the plan documents: only one `Protocol` may live in `ports/`. This bound keeps the adapter ring from growing its own domain model, which would duplicate or compete with the trust foundation.

---

## Architectural Identity

`agent_ui_adapter/` is a **hexagonal outer adapter ring with a single driven port**. The terminology maps directly to the hexagonal architecture pattern:


| Hexagonal term           | Concrete component                                                              |
| ------------------------ | ------------------------------------------------------------------------------- |
| Application core         | The four-layer backend (`services/`, `trust/`, `components/`, `orchestration/`) |
| Driving port (left side) | HTTP + SSE surface — FastAPI routes in `server.py`                              |
| Driven port (right side) | `AgentRuntime` protocol in `ports/agent_runtime.py`                             |
| Driven adapter           | Concrete implementations in `adapters/runtime/`                                 |
| Composition root         | `build_app(...)` in `server.py` — the only place that names a concrete adapter  |


Dependencies point inward. `server.py` imports `ports/`. `ports/` imports `wire/` and `trust/`. `adapters/` imports `ports/`, `wire/`, and `trust/`. Nothing in the adapter ring is imported by the four-layer backend. The ring is additive — it can be removed without changing a single file in `services/`, `trust/`, `components/`, or `orchestration/`.

---

## The Five Sub-packages

### `agent_ui_adapter/ports/`

Contains exactly one module: `agent_runtime.py`. Defines the `AgentRuntime` `@runtime_checkable` Protocol with three async methods:

- `run(thread_id, input, identity) -> AsyncIterator[DomainEvent]` — executes one run and yields the canonical event stream.
- `cancel(run_id) -> None` — best-effort, idempotent cancellation.
- `get_state(thread_id) -> ThreadState` — returns the persisted thread state.

This is the **only contract** the composition root depends on. All adapter swapping happens here. `AgentFacts` from `trust/models.py` flows in as the identity parameter; `DomainEvent` from `wire/domain_events.py` flows out.

### `agent_ui_adapter/adapters/`

Concrete implementations of `AgentRuntime`. Currently contains one sub-family:

- `adapters/runtime/mock_runtime.py` — scripted, deterministic implementation for tests. Lives in production code so it is available to integration test harnesses without a `tests/` import.
- `adapters/runtime/langgraph_runtime.py` — production implementation wrapping a LangGraph compiled app. The **sole location in the package where a third-party framework SDK (LangGraph) is imported**.

This is the only layer where SDK types are allowed. They never escape past the adapter boundary. See `docs/Architectures/AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md` for the exhaustive spec.

### `agent_ui_adapter/wire/`

Pure data shapes. No I/O, no framework dependencies beyond stdlib and Pydantic. Three modules:

- `domain_events.py` — internal canonical event types emitted by `AgentRuntime.run()`. Nine types in the `DomainEvent` union: `RunStartedDomain`, `RunFinishedDomain`, `LLMTokenEmitted`, `LLMMessageStarted`, `LLMMessageEnded`, `ToolCallStarted`, `ToolCallEnded`, `ToolResultReceived`, `StateMutated`. Every event carries `trace_id`.
- `agent_protocol.py` — HTTP wire shapes for the REST/SSE surface: `RunCreateRequest`, `ThreadCreateRequest`, `ThreadState`, `RunStateView`, `HealthResponse`.
- `ag_ui_events.py` — AG-UI protocol event types emitted on the SSE wire toward the frontend.

`wire/` imports only stdlib and Pydantic. It is the innermost ring of the adapter package — the "shared kernel" for the outer ring, analogous to `trust/` for the four-layer backend.

### `agent_ui_adapter/translators/`

Pure functions mapping between wire shapes. Three modules:

- `domain_to_ag_ui.py` — maps each `DomainEvent` variant to zero or more AG-UI events via `to_ag_ui(event)`. Called in the hot path inside the SSE generator in `server.py`.
- `ag_ui_to_domain.py` — maps incoming AG-UI request payloads to internal domain input dicts.
- `sealed_envelope.py` — wraps/unwraps a sealed message envelope for HITL round-trips.

Translators import from `wire/` and `trust/` only. They have no I/O and no side effects.

### `agent_ui_adapter/transport/`

SSE encoding utilities and connection management:

- `sse.py` — `encode_event()`, `encode_error()`, `SENTINEL_LINE`, `PROXY_HEADERS`. Converts Pydantic models to `data: ...\n\n` SSE frames.
- `heartbeat.py` — periodic keep-alive comment frames to prevent proxy timeouts.
- `backpressure.py` — configurable slow-consumer backpressure; drops or buffers events when the client is not consuming fast enough.
- `resumption.py` — last-event-id tracking for SSE stream resumption on reconnect.

Transport imports from `wire/` only. It has no knowledge of `adapters/` or `ports/`.

### `agent_ui_adapter/server.py` — Composition Root

The only file that names a concrete adapter. `build_app(runtime, jwt_verifier, agent_facts, ...)` wires:

1. A chosen `AgentRuntime` implementation (passed in by the caller).
2. A `JwtVerifier` (local composition-root abstraction, not a port).
3. Horizontal services from the four-layer backend (`AuthorizationService`, `TraceService`, `LongTermMemoryService`, `ToolRegistry`) — all optional, passed as constructor arguments.
4. The FastAPI app with routes that delegate to the runtime, translators, and transport.

`server.py` is the driving (left) side of the hexagon. It receives HTTP requests, extracts identity from JWT claims, calls the runtime, and streams the translated AG-UI events back over SSE.

---

## Data Flow

```
  AG-UI Client (browser / frontend)
       │
       │  POST /agent/runs/stream
       │  Authorization: Bearer <token>
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  server.py  (composition root — driving side)        │
  │                                                      │
  │  1. JwtVerifier.verify(token) → JwtClaims            │
  │  2. AgentFacts lookup by claims.subject              │
  │  3. AuthorizationService.authorize(identity, action) │
  │  4. runtime.run(thread_id, input, identity)          │
  │     → AsyncIterator[DomainEvent]                     │
  │  5. to_ag_ui(domain_event) → list[AG-UI events]      │
  │  6. encode_event(ag_ui_event) → SSE bytes            │
  └──────────────────────────────────────────────────────┘
       │                          ▲
       │  DomainEvent stream       │ AgentFacts, services
       ▼                          │ (constructor injection)
  ┌────────────────────────────────────────────────────┐
  │  adapters/runtime/<impl>  (driven side)            │
  │                                                    │
  │  → AgentRuntime.run()                              │
  │  → yields DomainEvent (trace_id on every event)   │
  │  → _emit_trace() → TrustTraceRecord at L4          │
  └────────────────────────────────────────────────────┘
       │
       │  SDK call (LangGraph.astream_events / scripted)
       ▼
  ┌────────────────────────────────────────────────────┐
  │  Four-Layer Backend                                │
  │                                                    │
  │  orchestration/  →  components/  →  services/     │
  │                                  →  trust/         │
  └────────────────────────────────────────────────────┘
```

The adapter ring only touches the four-layer backend through two interfaces:

1. `**trust/models.py**` — `AgentFacts` and `TrustTraceRecord` are imported directly (trust foundation is a shared kernel).
2. **Constructor injection in `build_app`** — horizontal services (`AuthorizationService`, `TraceService`, etc.) are passed in, never imported at module scope by the adapter ring.

---

## Dependency Direction at a Glance


| Module         | May import from                                          | May NOT import from                                       |
| -------------- | -------------------------------------------------------- | --------------------------------------------------------- |
| `ports/`       | `wire/`, `trust/`                                        | `adapters/`, `translators/`, `transport/`, `server.py`    |
| `adapters/`    | `ports/`, `wire/`, `trust/`, third-party SDKs            | `translators/`, `transport/`, `server.py`, other adapters |
| `wire/`        | stdlib, Pydantic                                         | Everything else in `agent_ui_adapter/`                    |
| `translators/` | `wire/`, `trust/`                                        | `adapters/`, `ports/`, `transport/`, `server.py`          |
| `transport/`   | `wire/`                                                  | `adapters/`, `ports/`, `translators/`, `server.py`        |
| `server.py`    | Everything in `agent_ui_adapter/`, `trust/`, `services/` | Nothing (it is the root)                                  |


The invariant: arrows always point toward `wire/` and `trust/` (the two innermost kernels). `server.py` is the outermost composition layer and is never imported by anything inside the package.

---

## Runtime Contract

Every concrete `AgentRuntime` implementation must satisfy three behavioral rules beyond the Protocol signature:

1. `**run()` must end with `RunFinishedDomain`.** If the implementation yields any events at all, the last event must be `RunFinishedDomain`. This gives the caller a reliable termination signal and a place to carry the error message when the run fails.
2. **Every emitted event must carry the same `trace_id`.** The `trace_id` is generated once at the start of `run()` and attached to all emitted `DomainEvent` instances. It correlates the entire run in the trust trace log.
3. `**cancel()` must be idempotent.** Cancelling an unknown or already-finished `run_id` must not raise. The caller does not manage run lifecycle state — it is the adapter's responsibility to be safe under repeated cancel calls.

These three rules are enforced by the conformance test bundle at `tests/agent_ui_adapter/adapters/runtime/test_conformance.py`.

---

## Phase Progression

The adapter ring grows in three phases. In each phase, the `AgentRuntime` protocol and the `wire/` event types remain stable — only the adapters and the downstream wiring change.


| Phase                 | Runtime adapters                                                                                                                            | Feature additions                                                                                                                                                       | New ports?                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **Phase 1 (current)** | `MockRuntime`, `LangGraphRuntime`                                                                                                           | —                                                                                                                                                                       | No                                                               |
| **Phase 2**           | Existing + HITL `request_approval` wiring; `StateMutated` with JSON Patch translation; additional graph engines (AutoGen, CrewAI) if needed | `StateMutated.delta` populated; `sealed_envelope.py` used in HITL round-trip                                                                                            | No — still exactly one port (`AgentRuntime`)                     |
| **Phase 3**           | + Remote runtime adapter (gRPC or HTTP) for distributed execution; multi-runtime routing by request attribute                               | New adapter families: `adapters/transport/`, `adapters/storage/`, `adapters/memory/` emerge when a second concrete backend arrives (abstraction-introduction principle) | New ports added under `ports/` only when second consumer arrives |


The abstraction-introduction principle: do not create `adapters/storage/` until two storage backends exist; do not add a new `ports/` Protocol until two implementations compete. Building the slot before the second implementation is over-engineering.

---

## Where to Go Next

- **Understanding the adapter internals** — read `docs/Architectures/AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md`. It covers the complete runtime translation contract, the formal dependency rules table, the conformance test bundle requirement, and the Phase 2/3 extension roadmap in full detail.
- **Adding a new concrete adapter** — read `docs/contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md`. It has a decision tree, step-by-step recipe, definition-of-done checklist, and common pitfalls.
- **Understanding the four-layer backend this ring sits above** — read `docs/Architectures/Architectures/FOUR_LAYER_ARCHITECTURE.md`.

