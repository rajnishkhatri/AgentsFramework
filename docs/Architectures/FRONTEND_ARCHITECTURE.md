# Frontend Architecture — Overview

**Scope:** the complete client-to-graph vertical slice
**Related documents:**

- `docs/Architectures/FOUR_LAYER_ARCHITECTURE.md` — the innermost backend ring this architecture sits above
- `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md` — the middle ring (SSE/AG-UI adapter) that the frontend ring drives
- `docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md` — exhaustive spec for every driven port and concrete adapter
- `docs/Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md` — exhaustive spec for the TS wire kernels, translators, and SSE transport
- `docs/plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md` — V2-Frontier substrate profile
- `docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md` — V3-Dev-Tier substrate profile (free-tier substrates, same architecture)
- `docs/STYLE_GUIDE_FRONTEND.md` — prescriptive code-review style guide that turns the F-R1..F-R9 invariants from this document into reviewable W/P/A/T/X/C/B/U/S/O rules with paste-into-PR checklists

---

## Governing Thought

The four-layer architecture (`FOUR_LAYER_ARCHITECTURE.md`) defines the backend; the `agent_ui_adapter/` outer ring exposes it over SSE to AG-UI clients. Neither layer was designed to own a browser application, edge configuration, BFF Route Handlers, or a TypeScript component tree. Adding those responsibilities inside the adapter ring or the backend would violate the existing dependency rules: nothing in `trust/`, `services/`, `components/`, or `orchestration/` may import from an outer ring.

The **Frontend Ring** is the answer to that constraint. It is an **outer cross-process ring** that sits entirely above `agent_ui_adapter/` and the four-layer backend. It introduces exactly **eight new port abstractions** (one per external dependency family: runtime, auth, thread storage, memory, telemetry, feature flags, tool rendering, and UI framework). Everything else in the ring is either a pure data shape, a pure translation function, an SSE transport utility, or a composition root. No domain logic is introduced in the frontend ring. The four-layer backend is consumed via the existing `AgentRuntime` Protocol in `agent_ui_adapter/ports/agent_runtime.py` — the frontend ring never reaches past the `agent_ui_adapter` seam.

**V2-Frontier and V3-Dev-Tier are the same architecture with different adapter wiring.** The ports, wire shapes, translators, and transport are identical across both substrate profiles. The only difference is which concrete adapter each port resolves to in the composition root. This is enforced by the substrate-swap matrix in §7.

---

## Architectural Identity

The Frontend Ring is a **hexagonal outer ring that crosses process boundaries**, composed of three sub-rings (browser+BFF, middleware, `agent_ui_adapter`), each modeled as a hexagon with driving and driven ports. The terminology maps directly:


| Hexagonal term           | Browser + BFF sub-ring                                      | Middleware sub-ring                                    | `agent_ui_adapter` sub-ring                          |
| ------------------------ | ----------------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------- |
| Application core         | `trust/` + `agent_ui_adapter/wire/` (Python shared kernels) | `agent_ui_adapter/` (the ring being driven)            | Four-layer backend                                   |
| Driving port (left side) | DOM events + HTTP requests from the browser                 | HTTP/SSE from the BFF                                  | HTTP/SSE from the middleware                         |
| Driven port (right side) | 8 `frontend/lib/ports/` TypeScript interfaces               | `AgentRuntimeClient` HTTP client to `agent_ui_adapter` | `AgentRuntime` Protocol in `agent_ui_adapter/ports/` |
| Driven adapter           | `frontend/lib/adapters/` concrete implementations           | `middleware/adapters/` concrete implementations        | `agent_ui_adapter/adapters/runtime/`                 |
| Composition root         | `frontend/lib/composition.ts`                               | `middleware/composition.py`                            | `agent_ui_adapter/server.py`                         |


Dependencies point inward. The browser imports from `frontend/lib/`. `frontend/lib/adapters/` imports from `frontend/lib/ports/` and `frontend/lib/wire/`. The middleware imports from `agent_ui_adapter/` via HTTP only — never at module scope. Nothing inside `agent_ui_adapter/` or the four-layer backend imports from `frontend/` or `middleware/`. The frontend ring is additive: it can be removed without changing a single file in `trust/`, `services/`, `components/`, `orchestration/`, `governance/`, or `agent_ui_adapter/`.

The **two TypeScript shared kernels** anchor dependency direction inside the browser+BFF sub-ring exactly as `trust/` anchors the Python backend:

- `frontend/lib/wire/` — pure TypeScript data shapes; mirrors `agent_ui_adapter/wire/`; imports only stdlib and Zod.
- `frontend/lib/trust-view/` — read-only TypeScript viewer shapes derived from `trust/`; imports only stdlib and Zod.

---

## The Three Composition Roots

The Frontend Ring has exactly three composition roots. Each is the **only place that names a concrete adapter**. All other code receives adapters through the port interface only.


| Composition root              | Process                         | Role                                                                                                                                                   |
| ----------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `frontend/lib/composition.ts` | Browser + Vercel/Cloudflare BFF | Wires the 8 `frontend/lib/ports/` implementations; selects adapters by `ARCHITECTURE_PROFILE` env var (`v2` or `v3`); provides them via React context. |
| `middleware/composition.py`   | Cloud Run or Fargate middleware | Wires auth verifier, memory client, telemetry exporter, and the downstream `agent_ui_adapter` HTTP client; selects adapters by `ARCHITECTURE_PROFILE`. |
| `agent_ui_adapter/server.py`  | Python API process              | The existing composition root (unchanged). The seam between the frontend ring and the `agent_ui_adapter` ring.                                         |


**Rule C1:** No module outside a composition root may contain an `import` of a concrete adapter class. Composition roots may import everything in the ring; nothing imports a composition root.

---

## The Five Sub-Packages (mirrored per process)

Each process in the frontend ring mirrors the sub-package layout of `agent_ui_adapter/`. The correspondence is exact:


| `agent_ui_adapter/` sub-package | `frontend/lib/` equivalent                      | `middleware/` equivalent                                            |
| ------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------- |
| `ports/`                        | `frontend/lib/ports/` — 8 TS interfaces         | `middleware/ports/` — 3 Python Protocols (auth, memory, telemetry)  |
| `adapters/`                     | `frontend/lib/adapters/` — SDK boundary         | `middleware/adapters/` — SDK boundary                               |
| `wire/`                         | `frontend/lib/wire/` — TS shared kernel         | `middleware/` uses `agent_ui_adapter/wire/` directly (same process) |
| `translators/`                  | `frontend/lib/translators/` — pure TS functions | `middleware/translators/` — pure Python functions                   |
| `transport/`                    | `frontend/lib/transport/` — SSE client          | `middleware/transport/` — SSE proxy utilities                       |


### `frontend/lib/ports/`

Contains exactly eight modules, one per driven port:

- `agent_runtime_client.ts` — typed wrapper around the AG-UI/SSE stream from `agent_ui_adapter`
- `auth_provider.ts` — abstraction over WorkOS AuthKit (V2/V3) or any OIDC provider
- `thread_store.ts` — abstraction over thread CRUD (Cloud SQL HA vs Neon Free)
- `memory_client.ts` — abstraction over Mem0 (self-hosted vs Cloud Hobby)
- `telemetry_sink.ts` — abstraction over Langfuse (self-hosted vs Cloud Hobby) + OTel
- `feature_flag_provider.ts` — abstraction over env-var flags (extensible to Cloudflare KV)
- `tool_renderer_registry.ts` — registry mapping tool names to CopilotKit React render components
- `ui_runtime.ts` — abstraction over the CopilotKit UI runtime (composition point for V1.5 UIRuntime swap)

**Rule P1:** Only one interface may live in each `ports/` module. This bound prevents the frontend from growing its own domain model.

### `frontend/lib/adapters/`

Concrete implementations of the eight ports. The **only location in `frontend/` where third-party SDK imports are allowed**. SDK types never escape past the adapter boundary; everything returned by an adapter is a `wire/` shape or a plain TypeScript primitive.

```
frontend/lib/adapters/
├── runtime/
│   ├── self_hosted_langgraph_dev_client.ts   (V3 default)
│   └── langgraph_platform_saas_client.ts     (V2 graduation)
├── auth/
│   └── workos_authkit_adapter.ts
├── thread_store/
│   ├── neon_free_thread_store.ts             (V3)
│   └── cloud_sql_thread_store.ts             (V2)
├── memory/
│   ├── mem0_cloud_hobby_adapter.ts           (V3)
│   └── self_hosted_mem0_adapter.ts           (V2)
├── observability/
│   ├── langfuse_cloud_hobby_adapter.ts       (V3)
│   └── self_hosted_langfuse_adapter.ts       (V2)
├── ui_runtime/
│   └── copilotkit_ui_runtime.ts
├── tool_renderer/
│   └── copilotkit_registry.ts
└── flags/
    └── env_var_flags.ts
```

Named-but-empty adapter family directories are **not created** until the second concrete backend arrives (abstraction-introduction principle, same as `agent_ui_adapter/adapters/transport/` and `adapters/storage/`).

### `frontend/lib/wire/`

Pure TypeScript data shapes. No I/O, no framework dependencies beyond stdlib and Zod. Four modules:

- `domain_events.ts` — TypeScript union mirror of `agent_ui_adapter/wire/domain_events.py`; nine `DomainEvent` variants; every event carries `trace_id`.
- `agent_protocol.ts` — HTTP wire shapes for the REST/SSE surface; mirrors `agent_ui_adapter/wire/agent_protocol.py`.
- `ag_ui_events.ts` — AG-UI protocol event types received from the SSE stream.
- `ui_runtime_events.ts` — UI-side derived event types (per-tool render requests, generative-UI widget descriptors).

`wire/` imports only stdlib and Zod. It is the innermost ring of the frontend package.

### `frontend/lib/translators/`

Pure functions mapping between wire shapes and UI-runtime shapes. Four modules:

- `ag_ui_to_ui_runtime.ts` — maps AG-UI events to CopilotKit message-list shapes.
- `ui_input_to_agent_request.ts` — maps Composer input to `RunCreateRequest`.
- `sealed_envelope.ts` — wraps/unwraps HITL approval round-trips.
- `tool_event_to_renderer_request.ts` — maps wire tool events to `ToolRendererRegistry` render requests.

Translators import from `wire/` and `trust-view/` only. No I/O, no side effects.

### `frontend/lib/transport/`

SSE client and BFF proxy utilities:

- `sse_client.ts` — typed `EventSource` wrapper; `Last-Event-ID` resumption; backpressure; retry policy; heartbeat detection.
- `edge_proxy.ts` — BFF Route Handler helper that forwards SSE byte-for-byte; sets `X-Accel-Buffering: no`; strips `Accept-Encoding` on streaming routes.

Transport imports from `wire/` only.

---

## Data Flow

```
  Browser (mobile + desktop)
       │
       │  DOM event: user sends message
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  Composer / CopilotKit  (React, browser process)     │
  │                                                      │
  │  1. UIRuntime.sendMessage(input)                     │
  │  2. ui_input_to_agent_request(input) → RunCreateReq  │
  │  3. AgentRuntimeClient.stream(req) → SSE connect     │
  └──────────────────────────────────────────────────────┘
       │                                   ▲
       │  HTTPS POST + SSE stream          │  AG-UI events
       ▼                                   │
  ┌──────────────────────────────────────────────────────┐
  │  Vercel / Cloudflare Edge                            │
  │  (BFF Route Handlers)                                │
  │                                                      │
  │  4. AuthProvider.verifySession()                     │
  │  5. edge_proxy.forward() → SSE byte passthrough      │
  └──────────────────────────────────────────────────────┘
       │  HTTPS (WorkOS JWT bearing)
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  middleware/  (Cloud Run or Fargate — Python)        │
  │                                                      │
  │  6. WorkOSJwtVerifier.verify(token) → identity       │
  │  7. MemoryClient.lookup(user_id)    → prior context  │
  │  8. TelemetrySink.span("run_start")                  │
  │  9. Forward SSE request → agent_ui_adapter           │
  └──────────────────────────────────────────────────────┘
       │  HTTPS (internal VPC / Cloud Run → Cloud Run)
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  agent_ui_adapter/server.py  (composition root)      │
  │                                                      │
  │  10. JwtVerifier.verify(token) → JwtClaims           │
  │  11. AgentFacts lookup by claims.subject             │
  │  12. AuthorizationService.authorize(identity, action)│
  │  13. runtime.run(thread_id, input, identity)         │
  │      → AsyncIterator[DomainEvent]                    │
  │  14. to_ag_ui(domain_event) → list[AG-UI events]     │
  │  15. encode_event(ag_ui_event) → SSE bytes           │
  └──────────────────────────────────────────────────────┘
       │                              ▲
       │  DomainEvent stream          │  AgentFacts, services
       ▼                              │  (constructor injection)
  ┌──────────────────────────────────────────────────────┐
  │  adapters/runtime/langgraph_*  (driven side)         │
  │                                                      │
  │  → AgentRuntime.run()                                │
  │  → yields DomainEvent (trace_id on every event)      │
  │  → _emit_trace() → TrustTraceRecord                  │
  └──────────────────────────────────────────────────────┘
       │
       │  LangGraph SDK call
       ▼
  ┌──────────────────────────────────────────────────────┐
  │  Four-Layer Backend                                  │
  │                                                      │
  │  orchestration/ → components/ → services/ → trust/  │
  └──────────────────────────────────────────────────────┘
```

The frontend ring touches the four-layer backend through exactly one interface: the `agent_ui_adapter` SSE surface. It never imports a Python module from the backend at module scope.

---

## Dependency Direction at a Glance

### Browser + BFF sub-ring (`frontend/lib/`)


| Module           | May import from                                    | May NOT import from                                               |
| ---------------- | -------------------------------------------------- | ----------------------------------------------------------------- |
| `ports/`         | `wire/`, `trust-view/`                             | `adapters/`, `translators/`, `transport/`, `composition.ts`       |
| `adapters/`      | `ports/`, `wire/`, `trust-view/`, third-party SDKs | `translators/`, `transport/`, `composition.ts`, other `adapters/` |
| `wire/`          | stdlib, Zod                                        | Everything else in `frontend/lib/`                                |
| `trust-view/`    | stdlib, Zod                                        | Everything else in `frontend/lib/`                                |
| `translators/`   | `wire/`, `trust-view/`                             | `adapters/`, `ports/`, `transport/`, `composition.ts`             |
| `transport/`     | `wire/`                                            | `adapters/`, `ports/`, `translators/`, `composition.ts`           |
| `composition.ts` | Everything in `frontend/lib/`, React context       | Nothing (it is the root)                                          |


**Cross-process rule:** `frontend/` must NEVER import a Python module. The process boundary is crossed only via HTTP/SSE through the `AgentRuntimeClient` port interface.

### Middleware sub-ring (`middleware/`)


| Module           | May import from                                                | May NOT import from                                               |
| ---------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| `ports/`         | `agent_ui_adapter/wire/`, `trust/`                             | `adapters/`, `translators/`, `transport/`, `composition.py`       |
| `adapters/`      | `ports/`, `agent_ui_adapter/wire/`, `trust/`, third-party SDKs | `translators/`, `transport/`, `composition.py`, other `adapters/` |
| `translators/`   | `agent_ui_adapter/wire/`, `trust/`                             | `adapters/`, `ports/`, `transport/`, `composition.py`             |
| `transport/`     | `agent_ui_adapter/wire/`                                       | `adapters/`, `ports/`, `translators/`, `composition.py`           |
| `composition.py` | Everything in `middleware/`, `agent_ui_adapter/`, `trust/`     | Nothing in `components/`, `orchestration/`, `governance/`         |


**Rule M1:** Nothing in `services/`, `trust/`, `components/`, `orchestration/`, `governance/`, or `agent_ui_adapter/` may import from `middleware/`.

---

## Substrate-Swap Matrix

The same eight ports appear in both V2-Frontier and V3-Dev-Tier. Only the concrete adapter wired at the composition root differs. Swapping substrates is a composition-root-only change: no `ports/`, `wire/`, `translators/`, or `transport/` file changes.


| Port                   | V3-Dev-Tier adapter (default)                                                  | V2-Frontier adapter (graduation)                              | Swap trigger                                        |
| ---------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------- | --------------------------------------------------- |
| `AgentRuntimeClient`   | `SelfHostedLangGraphDevClient` (self-hosted LangGraph Developer in middleware) | `LangGraphPlatformSaaSClient` (LangGraph Platform Cloud SaaS) | Node usage > 100K/mo                                |
| `AuthProvider`         | `WorkOSAuthKitAdapter` (free ≤1M MAU)                                          | `WorkOSAuthKitAdapter` (same; tier is a config param)         | n/a — same adapter                                  |
| `ThreadStore`          | `NeonFreeThreadStore` (0.5 GB / 100 CU-hr Neon Free)                           | `CloudSQLThreadStore` (Cloud SQL Postgres 16 HA)              | DB > 0.5 GB or scale-to-zero unacceptable           |
| `MemoryClient`         | `Mem0CloudHobbyAdapter` (10K adds + 1K retrievals/mo free)                     | `SelfHostedMem0Adapter` (Cloud Run + pgvector)                | Memory quota exceeded                               |
| `TelemetrySink`        | `LangfuseCloudHobbyAdapter` (50K units/mo free)                                | `SelfHostedLangfuseAdapter` (Cloud Run + ClickHouse)          | Trace volume > 50K/mo or retention > 30 days needed |
| `FeatureFlagProvider`  | `EnvVarFlagsAdapter`                                                           | `EnvVarFlagsAdapter`                                          | n/a — same adapter                                  |
| `ToolRendererRegistry` | `CopilotKitRegistryAdapter`                                                    | `CopilotKitRegistryAdapter`                                   | n/a — same adapter                                  |
| `UIRuntime`            | `CopilotKitUIRuntime`                                                          | `CopilotKitUIRuntime`                                         | n/a; v1.5 may swap for `AssistantUIRuntime`         |


---

## Runtime Contract

Every concrete `AgentRuntimeClient` adapter must satisfy four behavioral rules beyond the interface signature:

1. `**stream()` must end with `run.completed` or `run.error`.** If the adapter yields any events at all, the last event must be one of these two terminal types. This gives the caller a reliable termination signal.
2. **Every emitted event must carry the same `trace_id`.** The `trace_id` is generated by the Python runtime adapter (inside `agent_ui_adapter/adapters/runtime/`) and must be forwarded verbatim by every intermediate layer. The browser must never generate a `trace_id`.
3. `**cancel()` must be idempotent.** Cancelling an unknown or already-finished `run_id` must not throw. The caller does not manage run lifecycle state.
4. **No SDK type may appear in the return value of any port method.** Every value returned by `AgentRuntimeClient`, `MemoryClient`, `TelemetrySink`, or any other port must be typed by `wire/` shapes or plain TypeScript primitives.

These four rules are enforced by the conformance test bundle at `frontend/tests/architecture/test_port_conformance.ts`.

---

## Frontend-Side Architecture Invariants

The following invariants extend the backend invariants in `AGENTS.md` to cover the frontend ring. They are enforced by the architecture test suite described in §10.

**F-R1: No domain logic in React components.**
Components receive typed props and render them. Business logic (auth decisions, run lifecycle management, tool routing) lives in adapters or pure translators — never in a component file. Symptom of violation: a component file imports from `adapters/` directly.

**F-R2: SDK imports allowed only in `adapters/`.**
CopilotKit, Mem0, Langfuse, WorkOS, LangGraph client SDKs, and any other third-party library that owns data shapes or network calls may be imported only in files under `frontend/lib/adapters/` or `middleware/adapters/`. Symptom of violation: a `ports/`, `translators/`, `transport/`, or `wire/` file imports a third-party SDK.

**F-R3: One interface per `ports/` module.**
Each file under `frontend/lib/ports/` defines exactly one TypeScript interface. This mirrors the backend rule R9 and prevents ports from growing into domain models.

**F-R4: BFF Route Handlers are composition adapters, not business logic.**
Route Handlers in `frontend/app/api/` delegate to port implementations; they do not contain conditionals, data transformations, or service calls that are not already captured by a translator or adapter. Symptom of violation: a Route Handler file contains a non-trivial `if` branch that is not a port call.

**F-R5: System prompts remain in `prompts/` as Jinja templates.**
No prompt string, system-prompt fragment, or instruction text appears in any TypeScript file. This is an existing backend invariant (H1 in AGENTS.md); F-R5 extends it to the frontend.

**F-R6: `trust-view/` is read-only.**
No TypeScript file may mutate a value from `frontend/lib/trust-view/`. The frontend can read identity and policy decision views; it cannot sign, verify, or update them. Trust mutations happen in the Python backend only.

**F-R7: Every emitted event must forward `trace_id` untouched.**
Any SSE event or HTTP response that passes through the BFF or middleware must forward the `trace_id` field from the originating Python runtime adapter verbatim. The browser must never generate, modify, or drop a `trace_id`.

**F-R8: No SDK type may escape past an adapter boundary.**
A type defined by a third-party SDK (CopilotKit message shape, Langfuse span, Mem0 memory record, WorkOS session object) may not appear in any function signature, return type, or exported value outside `adapters/`. Use `wire/` shapes or plain primitives instead.

**F-R9: BFF must never hold cloud credentials.**
No AWS key, GCP service-account JSON, or provider API key (WorkOS, Mem0, Langfuse) may appear in a Vercel or Cloudflare Pages environment variable. All credential-bearing calls go through `middleware/` (which holds keys in Cloud Run / Fargate secret injection). The BFF communicates with the middleware via JWT-bearing HTTPS only.

---

## Architecture Test Plan

Two new test files enforce invariants F-R1..F-R9 (to be authored during the implementation sprint, not this architecture doc sprint):

### `tests/architecture/test_frontend_layering.ts`

```typescript
// Enforces F-R1: no adapter import from component files
// Enforces F-R2: SDK imports only under adapters/
// Enforces F-R3: one interface per ports/ module
// Enforces F-R8: no SDK type in ports/, translators/, transport/, wire/
```

Approach: walk `frontend/` import graph using `ts-morph`; assert that:

- No file outside `frontend/lib/adapters/` imports a package listed in `THIRD_PARTY_SDK_PACKAGES`.
- No file under `frontend/lib/ports/` imports from `frontend/lib/adapters/`.
- No file under `frontend/lib/translators/` imports from `frontend/lib/adapters/`.
- No file under `frontend/lib/wire/` or `frontend/lib/trust-view/` imports anything outside stdlib and Zod.

### `tests/architecture/test_middleware_layering.py`

```python
# Enforces M1: nothing in the four-layer backend imports from middleware/
# Enforces the middleware composition-root import boundary
```

Approach: walk `middleware/` import graph using `importlib`; assert that:

- `middleware/` may import from: `agent_ui_adapter/`, `trust/`, stdlib, third-party SDKs (under `middleware/adapters/` only).
- `middleware/` may NOT import from: `components/`, `orchestration/`, `governance/`, `services/` (direct module import).
- None of `services/`, `trust/`, `components/`, `orchestration/`, `governance/`, `agent_ui_adapter/` may import from `middleware/`.

---

## Phase Progression

The frontend ring grows in two phases. In each phase, the eight port interfaces and the `wire/` shapes remain stable — only the adapters and the downstream wiring change.


| Phase                        | Adapter profile                                              | Infrastructure                                                          | Upgrade mechanism                                                                                   |
| ---------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **V3-Dev-Tier (current)**    | Free-tier adapters per substrate-swap matrix                 | Cloudflare Pages, Cloud Run min=0, Neon Free, Mem0/Langfuse Cloud Hobby | V3 adapters wired in `composition.ts` and `middleware/composition.py`                               |
| **V2-Frontier (graduated)**  | Production adapters per substrate-swap matrix                | Cloud SQL HA, self-hosted Mem0 + Langfuse, Cloud Run min=1              | Swap `ARCHITECTURE_PROFILE=v2`; composition roots select V2 adapters; no port or translator changes |
| **Multi-runtime (Phase 3+)** | Second `AgentRuntimeClient` adapter for multi-region routing | Route 53 / Cloud DNS weighted records; second runtime target            | New adapter added to `adapters/runtime/`; routing logic belongs in composition root only            |


The abstraction-introduction principle applies: do not create `adapters/voice/` until a second voice backend arrives; do not add a new `ports/` interface until two implementations compete.

---

## Where to Go Next

- **Understanding every port and concrete adapter** — read `docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md`.
- **Understanding the wire kernels, translators, and SSE transport** — read `docs/Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md`.
- **Understanding the `agent_ui_adapter` ring this frontend ring drives** — read `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md`.
- **Adding a new concrete adapter** — follow the same pattern as `docs/contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md` (a frontend-equivalent handbook will be authored during the implementation sprint).
- **V2/V3 substrate plans** — `docs/plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md` and `docs/plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md`.

