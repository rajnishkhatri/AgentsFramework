# Frontend — Ports and Adapters Deep Dive

**Scope:** `frontend/lib/ports/`, `frontend/lib/adapters/`, `middleware/ports/`, `middleware/adapters/`
**Related documents:**

- `docs/Architectures/FRONTEND_ARCHITECTURE.md` — big-picture view of the full frontend ring
- `docs/Architectures/AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md` — the equivalent deep-dive for the backend adapter ring
- `docs/Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md` — exhaustive spec for wire kernels, translators, and SSE transport
- `docs/Architectures/FRONTEND_PORT_DEVIATIONS_V3.md` — **canonical** Sprint-3 refinements to `AgentRuntimeClient`, `AuthProvider`, `ThreadStore` (this document is the original Sprint-0 spec; the deviations doc supersedes §4.1, §4.2, §4.3 below)

> **Reader note (Sprint 3, V3-Dev-Tier).** The interface signatures shown
> for `AgentRuntimeClient` (§4.1), `AuthProvider` (§4.2), and `ThreadStore`
> (§4.3) describe the Sprint 0 spec and are preserved here for historical
> context. The implemented and reviewed Sprint 3 surfaces deviate
> deliberately — see [`FRONTEND_PORT_DEVIATIONS_V3.md`](./FRONTEND_PORT_DEVIATIONS_V3.md)
> for the canonical signatures, deltas, and rationale per port. The
> remaining five ports (`MemoryClient`, `TelemetrySink`,
> `FeatureFlagProvider`, `ToolRendererRegistry`, `UIRuntime`) match this
> document verbatim and are unaffected.

---

## Governing Thought

The four-layer backend (`trust/`, `services/`, `components/`, `orchestration/`) and the `agent_ui_adapter/` ring are framework-agnostic. The frontend ring must stay equally agnostic at its core. This means that CopilotKit, Mem0, Langfuse, WorkOS, and LangGraph client SDKs must never appear in `ports/`, `wire/`, `translators/`, or `transport/`. They are allowed in exactly one place: `adapters/`.

This is the same principle that confines `langgraph` to `agent_ui_adapter/adapters/runtime/langgraph_runtime.py`. Adapter isolation bounds migration cost: swapping Mem0 Cloud Hobby for a self-hosted Mem0 requires changing one file under `adapters/memory/` and one line in `composition.ts`. Nothing else moves.

The single-interface-per-`ports/`-module rule (F-R3) ensures the frontend never grows its own domain model. Eight ports means exactly eight `ports/` modules. If two ports look similar enough to merge, the merge belongs in a translator, not a combined port.

---

## Architectural Identity

`adapters/` is the **driven (right-hand) side** of the browser+BFF hexagon and the middleware hexagon. In hexagonal terms:

- The **port** is any interface file under `frontend/lib/ports/` (TypeScript) or `middleware/ports/` (Python Protocol).
- The **adapter** is any module under `frontend/lib/adapters/` or `middleware/adapters/` that satisfies the port.
- The **composition root** (`frontend/lib/composition.ts` or `middleware/composition.py`) decides which adapter to inject at construction time.

Because TypeScript interfaces are structural (`implements` is optional), conformance is checked via the conformance test bundle rather than the type system alone — exactly as the Python `@runtime_checkable` Protocol pattern works in `agent_ui_adapter/`.

```
  frontend/lib/composition.ts  (composition root — driving side)
       │
       │  adapters: <8 port interfaces>  (provided via React context)
       ▼
  frontend/lib/ports/<port>.ts
  ┌─────────────────────────────────────────────┐
  │  interface AgentRuntimeClient               │
  │    stream(req): AsyncIterable<AgUIEvent>    │
  │    cancel(runId): Promise<void>             │
  │    getState(threadId): Promise<ThreadState> │
  └─────────────────────────────────────────────┘
            ▲                    ▲
            │                    │
  adapters/runtime/              adapters/runtime/
  self_hosted_langgraph_dev_*    langgraph_platform_saas_*
  (V3 default)                   (V2 graduation)
```

---

## The Adapter Grid

The full directory tree, including named-but-empty slots for adapter families that will exist at V2 graduation or Phase 3. No empty-slot directory is created until the second concrete backend arrives.

```
frontend/lib/
├── ports/                                (exactly 8 modules)
│   ├── agent_runtime_client.ts
│   ├── auth_provider.ts
│   ├── thread_store.ts
│   ├── memory_client.ts
│   ├── telemetry_sink.ts
│   ├── feature_flag_provider.ts
│   ├── tool_renderer_registry.ts
│   └── ui_runtime.ts
│
└── adapters/
    ├── runtime/                          (current: 2 implementations)
    │   ├── self_hosted_langgraph_dev_client.ts   V3 default
    │   └── langgraph_platform_saas_client.ts     V2 graduation
    ├── auth/                             (current: 1 implementation)
    │   └── workos_authkit_adapter.ts
    ├── thread_store/                     (current: 2 implementations)
    │   ├── neon_free_thread_store.ts             V3 default
    │   └── cloud_sql_thread_store.ts             V2 graduation
    ├── memory/                           (current: 2 implementations)
    │   ├── mem0_cloud_hobby_adapter.ts           V3 default
    │   └── self_hosted_mem0_adapter.ts           V2 graduation
    ├── observability/                    (current: 2 implementations)
    │   ├── langfuse_cloud_hobby_adapter.ts       V3 default
    │   └── self_hosted_langfuse_adapter.ts       V2 graduation
    ├── ui_runtime/                       (current: 1 implementation)
    │   └── copilotkit_ui_runtime.ts
    ├── tool_renderer/                    (current: 1 implementation)
    │   └── copilotkit_registry.ts
    └── flags/                            (current: 1 implementation)
        └── env_var_flags.ts

middleware/
├── ports/                                (4 Python Protocols)
│   ├── jwt_verifier.py
│   ├── tool_acl.py
│   ├── memory_client.py
│   └── telemetry_exporter.py
│
└── adapters/
    ├── auth/
    │   └── workos_jwt_verifier.py
    ├── acl/
    │   └── workos_role_acl.py                    V3 default
    ├── memory/
    │   ├── mem0_cloud_hobby_client.py            V3 default
    │   └── self_hosted_mem0_client.py            V2 graduation
    └── observability/
        ├── langfuse_cloud_hobby_exporter.py      V3 default
        └── self_hosted_langfuse_exporter.py      V2 graduation
```

---

## The Eight Driven Ports

### 4.1 `AgentRuntimeClient` — `frontend/lib/ports/agent_runtime_client.ts`

**Purpose:** The single contract between the browser+BFF sub-ring and the downstream middleware/`agent_ui_adapter` SSE surface. This is the TypeScript-side analogue of `AgentRuntime` in `agent_ui_adapter/ports/agent_runtime.py`. All event streaming, cancellation, and state retrieval go through this interface.

**Interface signature:**

```typescript
interface AgentRuntimeClient {
  /** Start a new run on an existing thread; returns an async iterable of AG-UI events. */
  stream(req: RunCreateRequest): AsyncIterable<AGUIEvent>;

  /** Best-effort, idempotent cancellation. Must not throw for unknown runId. */
  cancel(runId: string): Promise<void>;

  /** Returns the persisted thread state for initial page load. */
  getState(threadId: string): Promise<ThreadState>;
}
```

**Behavioral contract:**

1. The last event yielded by `stream()` must be either `RunCompletedEvent` or `RunErrorEvent`. No other terminal condition is valid.
2. Every event yielded by `stream()` must carry the same `trace_id`. The value comes from the backend runtime adapter and must be forwarded verbatim; this adapter must never generate a `trace_id`.
3. `cancel()` must not throw for unknown or already-finished `runId` values.
4. No SDK type (CopilotKit message, LangGraph raw event dict) may appear in the return type of any method.
5. If the underlying SSE connection drops, the adapter must attempt reconnection using `Last-Event-ID` before surfacing an error to the caller.

**Conformance test sketch:**

```typescript
// frontend/tests/architecture/test_port_conformance.ts
describe("AgentRuntimeClient conformance", () => {
  for (const AdapterClass of [SelfHostedLangGraphDevClient, LangGraphPlatformSaaSClient]) {
    it(`${AdapterClass.name} last event is terminal`, async () => { ... });
    it(`${AdapterClass.name} all events carry same trace_id`, async () => { ... });
    it(`${AdapterClass.name} cancel is idempotent`, async () => { ... });
  }
});
```

**V3 adapter:** `SelfHostedLangGraphDevClient`
**V2 adapter:** `LangGraphPlatformSaaSClient`
**Cross-port interaction:** depends on `AuthProvider` for the bearer token attached to each request.

---

### 4.2 `AuthProvider` — `frontend/lib/ports/auth_provider.ts`

**Purpose:** Abstraction over the OIDC/SSO authentication layer. Provides session management, token retrieval, and sign-in/sign-out flows. The only port that may interact with browser cookies and local storage.

**Interface signature:**

```typescript
interface AuthProvider {
  /** Returns the current authenticated session, or null if unauthenticated. */
  getSession(): Promise<Session | null>;

  /** Returns a valid access token for use as Authorization: Bearer <token>. */
  getAccessToken(): Promise<string>;

  /** Initiates the sign-in flow (redirects or opens modal). */
  signIn(options?: SignInOptions): Promise<void>;

  /** Signs out and clears session state. */
  signOut(): Promise<void>;
}
```

**Behavioral contract:**

1. `getAccessToken()` must return an unexpired token. If the current token is within 60 seconds of expiry, the adapter must refresh it before returning.
2. `getSession()` must return `null` rather than throw when no session exists.
3. `signOut()` must clear all local auth state (cookies, storage) before resolving.
4. No WorkOS SDK type may appear in the `Session` type — `Session` is defined in `wire/agent_protocol.ts`.

**V3 adapter:** `WorkOSAuthKitAdapter` (WorkOS AuthKit, free ≤1M MAU)
**V2 adapter:** `WorkOSAuthKitAdapter` (same adapter; tier is a billing configuration, not a code change)
**Cross-port interaction:** `AgentRuntimeClient` calls `AuthProvider.getAccessToken()` to attach the bearer token to each run request.

---

### 4.3 `ThreadStore` — `frontend/lib/ports/thread_store.ts`

**Purpose:** Abstraction over thread CRUD (create, list, rename, archive, delete). Decouples the UI from the underlying database (Neon Free serverless Postgres in V3, Cloud SQL HA in V2).

**Interface signature:**

```typescript
interface ThreadStore {
  list(options?: ListOptions): Promise<Thread[]>;
  create(input: CreateThreadInput): Promise<Thread>;
  update(id: string, patch: ThreadPatch): Promise<Thread>;
  archive(id: string): Promise<void>;
  delete(id: string): Promise<void>;
  getMessages(threadId: string, options?: PaginationOptions): Promise<Message[]>;
}
```

**Behavioral contract:**

1. `delete()` performs a soft delete (sets `archived_at`; does not purge LangGraph checkpoints).
2. `list()` returns threads ordered by `updated_at DESC`; supports cursor-based pagination.
3. `getMessages()` replays messages from the LangGraph checkpoint store; ordering is `created_at ASC`.
4. All methods must surface a typed `ThreadStoreError` rather than a raw HTTP status code.

**V3 adapter:** `NeonFreeThreadStore` (Neon Serverless Postgres, scale-to-zero)
**V2 adapter:** `CloudSQLThreadStore` (Cloud SQL Postgres 16, regional HA)
**Cross-port interaction:** Thread `id` values are LangGraph `thread_id` values; `AgentRuntimeClient` uses them directly in `RunCreateRequest`.

---

### 4.4 `MemoryClient` — `frontend/lib/ports/memory_client.ts`

**Purpose:** Abstraction over the long-term memory layer (per-user facts, preferences, prior-context recall). Decouples the UI from Mem0's retrieval API.

**Interface signature:**

```typescript
interface MemoryClient {
  /** Search memories relevant to the current turn. */
  search(query: string, userId: string): Promise<MemoryResult[]>;

  /** Append memories extracted from the current conversation turn. */
  add(memories: MemoryInput[], userId: string): Promise<void>;

  /** Delete all memories for a user (GDPR right-to-erasure support). */
  deleteAll(userId: string): Promise<void>;
}
```

**Behavioral contract:**

1. `search()` must return an empty array rather than throw when no memories match.
2. `add()` must be idempotent under repeated identical input (Mem0's deduplication handles this; the adapter must not suppress the Mem0 call).
3. `deleteAll()` must be atomic from the caller's perspective — either all memories are removed or a typed `MemoryError` is thrown.
4. No Mem0 SDK type may appear in `MemoryResult` or `MemoryInput` — these are defined in `wire/ui_runtime_events.ts`.

**V3 adapter:** `Mem0CloudHobbyAdapter` (Mem0 Cloud, 10K adds + 1K retrievals/mo free)
**V2 adapter:** `SelfHostedMem0Adapter` (Cloud Run service `mem0-server` backed by pgvector)
**Note:** `MemoryClient` is called from the **middleware** side, not the browser side — the BFF never holds Mem0 credentials (F-R9). The frontend `MemoryClient` port is therefore wired in `middleware/composition.py`; the browser receives pre-injected memory context in the initial `RunCreateRequest`.

---

### 4.5 `TelemetrySink` — `frontend/lib/ports/telemetry_sink.ts`

**Purpose:** Abstraction over the observability layer (traces, spans, prompt evaluation). Decouples middleware telemetry emission from Langfuse's specific SDK and endpoint format.

**Interface signature:**

```typescript
// TypeScript (frontend/lib — browser-side RUM only; heavy tracing lives in middleware)
interface TelemetrySink {
  /** Record a browser-side span (page load, SSE first-token latency). */
  span(name: string, attributes: Record<string, string | number>): void;

  /** Record a client-side error. */
  error(name: string, message: string, context?: Record<string, unknown>): void;
}
```

```python
# Python (middleware/ports/telemetry_exporter.py — server-side traces)
@runtime_checkable
class TelemetryExporter(Protocol):
    def start_span(self, name: str, trace_id: str, attributes: dict) -> "Span": ...
    def finish_span(self, span: "Span", outcome: str, error: str | None = None) -> None: ...
    def flush(self) -> None: ...
```

**Behavioral contract:**

1. `span()` / `start_span()` must be non-blocking; telemetry must never delay the SSE stream.
2. If the telemetry backend is unavailable, the adapter must swallow the error and log it locally. A failing telemetry call must never interrupt a run.
3. The `trace_id` passed to `start_span()` in the middleware adapter must be the same `trace_id` propagated from the Python runtime (rule F-R7).

**V3 adapter:** `LangfuseCloudHobbyAdapter` / `LangfuseCloudHobbyExporter` (50K units/mo free)
**V2 adapter:** `SelfHostedLangfuseAdapter` / `SelfHostedLangfuseExporter` (Cloud Run + ClickHouse)
**Cross-port interaction:** The middleware `TelemetryExporter` receives `trace_id` from the `AgentRuntimeClient` response stream.

---

### 4.6 `FeatureFlagProvider` — `frontend/lib/ports/feature_flag_provider.ts`

**Purpose:** Abstraction over runtime feature flags. Enables dark-launching features (voice mode F20, Pyramid panel F14) without code changes.

**Interface signature:**

```typescript
interface FeatureFlagProvider {
  /** Returns the boolean value of a flag, or the default if not defined. */
  isEnabled(flag: FeatureFlag, userId?: string): boolean;

  /** Returns the string/number variant value of a flag. */
  variant<T>(flag: FeatureFlag, defaultValue: T, userId?: string): T;
}

type FeatureFlag =
  | "voice_mode"
  | "pyramid_panel"
  | "per_tool_authorization"
  | "json_run_export";
```

**Behavioral contract:**

1. `isEnabled()` must be synchronous — flags are read at render time and must not trigger async re-renders.
2. The adapter must read flags at construction time (in the composition root) and cache them; no runtime HTTP calls.
3. Unknown flag names must return the default value, not throw.

**V3 adapter:** `EnvVarFlagsAdapter` (reads `NEXT_PUBLIC_`* env vars; no backend call)
**V2 adapter:** `EnvVarFlagsAdapter` (same; Cloudflare KV integration deferred to Phase 3)

---

### 4.7 `ToolRendererRegistry` — `frontend/lib/ports/tool_renderer_registry.ts`

**Purpose:** Registry mapping tool names (as they appear in `wire/ag_ui_events.ts` `ToolCallEvent.toolName`) to CopilotKit React render components. This is the F5/F13 generative-UI surface.

**Interface signature:**

```typescript
interface ToolRendererRegistry {
  /** Returns the React component for the given tool name, or null if not registered. */
  getRenderer(toolName: string): ToolRenderer | null;

  /** Registers a renderer for a tool name. Called by the composition root only. */
  register(toolName: string, renderer: ToolRenderer): void;
}

type ToolRenderer = React.ComponentType<ToolRendererProps>;

interface ToolRendererProps {
  toolCallId: string;
  toolName: string;
  input: unknown;          // typed per-tool in each renderer component
  output: unknown | null;
  status: "running" | "done" | "error";
}
```

**Behavioral contract:**

1. `getRenderer()` must return `null` (not throw) for unregistered tool names; the fallback is a generic JSON viewer component.
2. `register()` must be called only from the composition root. Components must never call `register()` directly.
3. The `input` and `output` fields are typed `unknown` at the registry interface level; each renderer component is responsible for narrowing the type with Zod.

**V3 and V2 adapter:** `CopilotKitRegistryAdapter` (CopilotKit `useFrontendTool` + `useComponent`)
**Known tool renderers to register at launch:** `shell`, `file_io`, `web_search`, plus a catch-all generic JSON viewer.

---

### 4.8 `UIRuntime` — `frontend/lib/ports/ui_runtime.ts`

**Purpose:** Abstraction over the chat UI framework (CopilotKit today; potentially `assistant-ui` at v1.5 or beyond). Isolates the component tree from framework-specific message-list APIs, composer hooks, and thread management hooks.

**Interface signature:**

```typescript
interface UIRuntime {
  /** Returns a React context provider that injects the runtime into the component tree. */
  Provider: React.ComponentType<{ children: React.ReactNode }>;

  /** Hook: returns actions for sending messages, stopping, and regenerating. */
  useThread(): ThreadActions;

  /** Hook: returns the current streaming message state. */
  useMessages(): MessageState;

  /** Hook: returns a function to register a tool renderer. */
  useToolRenderer(toolName: string, renderer: ToolRenderer): void;
}
```

**Behavioral contract:**

1. `Provider` must not perform any side effects at render time beyond establishing the React context.
2. `useThread()` and `useMessages()` must be stable across re-renders (referential equality for returned objects when state has not changed).
3. The adapter must translate framework-specific events into `wire/ag_ui_events.ts` types before returning them from any hook.

**V3 and V2 adapter:** `CopilotKitUIRuntime` (CopilotKit v2 `CopilotKit` + `useCopilotChatSuggestions` + `useCoAgentStateRender`)
**V1.5 potential swap:** `AssistantUIRuntime` (`assistant-ui` primitives; same interface, different implementation)

---

## Concrete Adapter Specifications

### 5.1 `SelfHostedLangGraphDevClient` (V3)

**File:** `frontend/lib/adapters/runtime/self_hosted_langgraph_dev_client.ts`
**Wraps:** LangGraph JavaScript client SDK (`@langchain/langgraph-sdk`, pin to `^0.0.x`)
**Port implemented:** `AgentRuntimeClient`

**Constructor parameters:**


| Parameter      | Type           | Purpose                                                      |
| -------------- | -------------- | ------------------------------------------------------------ |
| `baseUrl`      | `string`       | URL of the `middleware/` Cloud Run service                   |
| `authProvider` | `AuthProvider` | Injected at construction time; provides bearer tokens        |
| `fetchImpl`    | `typeof fetch` | Optional; defaults to global `fetch`; injectable for testing |


**Translation contract:**


| `AgentRuntimeClient` method | Underlying call                                    | Notes                                                                           |
| --------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------- |
| `stream(req)`               | `POST {baseUrl}/agent/runs/stream` with AG-UI body | Parses SSE frames into `AGUIEvent` union via `wire/ag_ui_events.ts` Zod schemas |
| `cancel(runId)`             | `DELETE {baseUrl}/agent/runs/{runId}`              | Returns `void`; ignores 404 (idempotent)                                        |
| `getState(threadId)`        | `GET {baseUrl}/agent/threads/{threadId}/state`     | Parses response into `ThreadState` wire shape                                   |


**Error translation:**


| HTTP status     | Thrown error type                                                        |
| --------------- | ------------------------------------------------------------------------ |
| 401             | `AgentAuthError` — triggers `AuthProvider.signIn()` flow                 |
| 403             | `AgentAuthorizationError` — surface as toast; do not retry               |
| 429             | `AgentRateLimitError` — back off with exponential retry (max 3 attempts) |
| 5xx             | `AgentServerError` — surface as toast; log to `TelemetrySink`            |
| Network timeout | `AgentNetworkError` — attempt SSE reconnect with `Last-Event-ID`         |


**Trust-trace boundaries:** This adapter is the TypeScript entry point; `trace_id` flows in from the Python runtime. The adapter must never generate a `trace_id`; it reads the field from each received SSE event and attaches it to the `AgentRuntimeClient` stream items.

---

### 5.2 `LangGraphPlatformSaaSClient` (V2)

**File:** `frontend/lib/adapters/runtime/langgraph_platform_saas_client.ts`
**Wraps:** LangGraph Platform SDK (`@langchain/langgraph-sdk`, same pin as V3)
**Port implemented:** `AgentRuntimeClient`

**Constructor parameters:**


| Parameter         | Type           | Purpose                                                                            |
| ----------------- | -------------- | ---------------------------------------------------------------------------------- |
| `platformUrl`     | `string`       | LangGraph Platform Cloud SaaS HTTPS URL                                            |
| `authProvider`    | `AuthProvider` | Injected at construction time                                                      |
| `langGraphApiKey` | `string`       | LangGraph Platform API key (loaded from server-side env; never exposed to browser) |


**Translation contract:** identical to `SelfHostedLangGraphDevClient` — same AG-UI wire format, same error translation table. The endpoint URL differs; everything else is the same.

**Substrate-swap note:** Both V3 and V2 clients implement the same `AgentRuntimeClient` interface. The composition root swaps them by reading `ARCHITECTURE_PROFILE`. No caller changes when the profile changes.

---

### 5.3 `WorkOSAuthKitAdapter`

**File:** `frontend/lib/adapters/auth/workos_authkit_adapter.ts`
**Wraps:** `@workos-inc/authkit-nextjs` (pin to `^2`)
**Port implemented:** `AuthProvider`

**Constructor parameters:** none — WorkOS AuthKit is configured via `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_COOKIE_PASSWORD`, and `NEXT_PUBLIC_WORKOS_REDIRECT_URI` Next.js env vars, read at module load by the SDK. (`WORKOS_REDIRECT_URI` is not read by AuthKit; the redirect must match the callback route and the WorkOS dashboard allowlist.)

**Translation contract:**


| `AuthProvider` method | WorkOS AuthKit call                                                                   |
| --------------------- | ------------------------------------------------------------------------------------- |
| `getSession()`        | `getSession()` from `@workos-inc/authkit-nextjs`; maps to `Session` wire shape        |
| `getAccessToken()`    | Extracts `accessToken` from session; calls `refreshSession()` if within 60s of expiry |
| `signIn()`            | `signIn()` with optional redirect URL                                                 |
| `signOut()`           | `signOut()`                                                                           |


**SDK type boundary:** `WorkOSSession` (SDK type) is converted to `Session` (wire type) inside the adapter. No `WorkOSSession` appears in any return type.

---

### 5.4 `NeonFreeThreadStore` (V3)

**File:** `frontend/lib/adapters/thread_store/neon_free_thread_store.ts`
**Wraps:** `@neondatabase/serverless` (pin to `^0.x`) + Drizzle ORM (`drizzle-orm ^0.x`)
**Port implemented:** `ThreadStore`
**Runs in:** Next.js Route Handler (BFF) — server-side only; never in browser bundle.

**Constructor parameters:**


| Parameter          | Type     | Purpose                                               |
| ------------------ | -------- | ----------------------------------------------------- |
| `connectionString` | `string` | Neon serverless Postgres connection string (from env) |
| `maxPoolSize`      | `number` | Default: 5 (Neon Free has connection limits)          |


**Schema ownership:** Drizzle owns migrations (`frontend/drizzle/`). `drizzle-kit push` is the single migration authority. The `tablesFilter` option in `drizzle.config.ts` must exclude LangGraph checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) — these are owned by the Python `AsyncPostgresSaver` and must not be touched.

---

### 5.5 `CloudSQLThreadStore` (V2)

**File:** `frontend/lib/adapters/thread_store/cloud_sql_thread_store.ts`
**Wraps:** `@neondatabase/serverless` (compatible with Cloud SQL's `pgbouncer` endpoint) or `pg` pool
**Port implemented:** `ThreadStore`

**Key difference from V3:** Uses a Cloud SQL HA instance with `sslmode=require` and a connection pool backed by Cloud SQL Auth Proxy or Private Service Connect. `maxPoolSize` is 10 (Cloud SQL `db.f1-micro` supports ~25 connections).

---

### 5.6 `Mem0CloudHobbyAdapter` (V3) and `SelfHostedMem0Adapter` (V2)

**Files:** `frontend/lib/adapters/memory/mem0_cloud_hobby_adapter.ts` / `self_hosted_mem0_adapter.ts`
**Wraps:** `mem0ai` JS SDK (pin to `^1.x`)
**Port implemented:** `MemoryClient`
**Runs in:** middleware Python process (`middleware/adapters/memory/`) — not the browser.

**Translation contract:**


| `MemoryClient` method   | Mem0 call                                                    |
| ----------------------- | ------------------------------------------------------------ |
| `search(query, userId)` | `client.search(query, { userId })` → map to `MemoryResult[]` |
| `add(memories, userId)` | `client.add(memories, { userId })`                           |
| `deleteAll(userId)`     | `client.deleteAll({ userId })`                               |


**V3 difference:** `baseUrl` points to `https://api.mem0.ai`; API key from Secret Manager.
**V2 difference:** `baseUrl` points to the internal Cloud Run `mem0-server` URL; no public API key.

---

### 5.7 `LangfuseCloudHobbyAdapter` (V3) and `SelfHostedLangfuseAdapter` (V2)

**Files:** Python adapters in `middleware/adapters/observability/`
**Wraps:** `langfuse` Python SDK (pin to `^2.x`)
**Port implemented:** `TelemetryExporter` (Python Protocol)

**Constructor parameters:**


| Parameter    | Type  | Purpose                                                          |
| ------------ | ----- | ---------------------------------------------------------------- |
| `public_key` | `str` | Langfuse public key from Secret Manager                          |
| `secret_key` | `str` | Langfuse secret key from Secret Manager                          |
| `host`       | `str` | `https://cloud.langfuse.com` (V3) or internal Cloud Run URL (V2) |


**Trust-trace integration:** `start_span()` receives the `trace_id` from the run and creates a Langfuse trace with that ID as the external ID. This ensures Langfuse traces are correlated with `TrustTraceRecord` events on the Python side.

**Failure isolation:** identical to the Python `_emit_trace` failure isolation rule — a failing Langfuse call is caught, logged, and swallowed; it must never interrupt the SSE stream.

---

### 5.8 `CopilotKitUIRuntime`

**File:** `frontend/lib/adapters/ui_runtime/copilotkit_ui_runtime.ts`
**Wraps:** `@copilotkit/react-core` and `@copilotkit/react-ui` (pin to `^1.x`)
**Port implemented:** `UIRuntime`

**Key wiring decisions:**

- The `Provider` wraps the Next.js layout with `<CopilotKit runtimeUrl="/api/copilotkit">` so all CopilotKit hooks work downstream.
- `useThread()` wraps CopilotKit's `useCopilotChatSuggestions()` and maps to the `ThreadActions` wire shape.
- `useToolRenderer()` calls `useFrontendTool()` (Static AG-UI) for structured tool-call cards and `useComponent()` (Open AG-UI) for generative-UI iframes.

---

### 5.9 `CopilotKitRegistryAdapter`

**File:** `frontend/lib/adapters/tool_renderer/copilotkit_registry.ts`
**Wraps:** `@copilotkit/react-core` `useFrontendTool` and `useComponent`
**Port implemented:** `ToolRendererRegistry`

**Built-in registrations (composition root wires these):**


| Tool name               | Renderer component  | AG-UI mode                                                                             |
| ----------------------- | ------------------- | -------------------------------------------------------------------------------------- |
| `shell`                 | `ShellToolUI`       | Static AG-UI (`useFrontendTool`)                                                       |
| `file_io`               | `FileIOToolUI`      | Static AG-UI                                                                           |
| `web_search`            | `WebSearchToolUI`   | Static AG-UI                                                                           |
| `analysis_output` (F14) | `PyramidPanel`      | Open AG-UI (`useComponent`) — feature-flagged off until `pyramid_panel` flag is `true` |
| `*` (catch-all)         | `GenericJsonToolUI` | Static AG-UI fallback                                                                  |


---

### 5.10 `EnvVarFlagsAdapter`

**File:** `frontend/lib/adapters/flags/env_var_flags.ts`
**Port implemented:** `FeatureFlagProvider`

Reads `NEXT_PUBLIC_FF_*` environment variables at module load time. Returns defaults for unknown flags. Is synchronous and has no async dependencies. Upgraded to a Cloudflare KV-backed adapter only when runtime flag evaluation (per-user overrides) is required.

---

## Hexagonal Dependency Rules for `adapters/`

Every module under `frontend/lib/adapters/` and `middleware/adapters/` must satisfy the following import table. These rules are enforced by `tests/architecture/test_frontend_layering.ts` and `test_middleware_layering.py`.


| From `adapters/`**       | To                                                          | Allowed?                             | Rationale                                                                                                            |
| ------------------------ | ----------------------------------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| adapter module           | `frontend/lib/ports/`                                       | **Yes**                              | Adapter implements the port; must import the interface                                                               |
| adapter module           | `frontend/lib/wire/`                                        | **Yes**                              | Adapter returns wire-shape values                                                                                    |
| adapter module           | `frontend/lib/trust-view/`                                  | **Yes**                              | Adapter may read identity viewer shapes                                                                              |
| adapter module           | third-party SDK                                             | **Yes — `adapters/` only**           | This is the designated SDK boundary                                                                                  |
| adapter module           | another `adapters/` module                                  | **FORBIDDEN**                        | Adapters are siblings; cross-adapter coupling prevents individual swaps                                              |
| adapter module           | `frontend/lib/translators/`                                 | **FORBIDDEN**                        | Translators consume adapter output; reversing the arrow breaks the dependency direction                              |
| adapter module           | `frontend/lib/transport/`                                   | **FORBIDDEN**                        | Transport is downstream of adapters                                                                                  |
| adapter module           | `frontend/lib/composition.ts`                               | **FORBIDDEN**                        | Composition root is the outermost layer; nothing imports it                                                          |
| `middleware/adapters/`** | `agent_ui_adapter/`                                         | **FORBIDDEN** (direct module import) | The middleware talks to `agent_ui_adapter` via HTTP only; never at module scope                                      |
| `middleware/adapters/`** | `services/`, `components/`, `orchestration/`, `governance/` | **FORBIDDEN**                        | Middleware adapter ring sits above the four-layer backend; accessed only through the `agent_ui_adapter` HTTP surface |


---

## Composition-Root Wiring Pattern

The composition root is the **only** file that knows which concrete adapter implements each port. All other code receives adapters through the port interface only.

### TypeScript (`frontend/lib/composition.ts`)

```typescript
// frontend/lib/composition.ts
import type { AgentRuntimeClient } from "./ports/agent_runtime_client";
// ... other port imports

// V3 adapters
import { SelfHostedLangGraphDevClient } from "./adapters/runtime/self_hosted_langgraph_dev_client";
// V2 adapters
import { LangGraphPlatformSaaSClient } from "./adapters/runtime/langgraph_platform_saas_client";
// Shared adapters (same for V2 and V3)
import { WorkOSAuthKitAdapter } from "./adapters/auth/workos_authkit_adapter";
import { CopilotKitUIRuntime } from "./adapters/ui_runtime/copilotkit_ui_runtime";
import { CopilotKitRegistryAdapter } from "./adapters/tool_renderer/copilotkit_registry";
import { EnvVarFlagsAdapter } from "./adapters/flags/env_var_flags";

const profile = process.env.ARCHITECTURE_PROFILE ?? "v3";

export function buildAdapters() {
  const auth = new WorkOSAuthKitAdapter();
  const flags = new EnvVarFlagsAdapter();
  const toolRegistry = new CopilotKitRegistryAdapter();
  const uiRuntime = new CopilotKitUIRuntime();

  const runtime: AgentRuntimeClient =
    profile === "v2"
      ? new LangGraphPlatformSaaSClient({
          platformUrl: process.env.LANGGRAPH_PLATFORM_URL!,
          authProvider: auth,
          langGraphApiKey: process.env.LANGGRAPH_API_KEY!,
        })
      : new SelfHostedLangGraphDevClient({
          baseUrl: process.env.MIDDLEWARE_URL!,
          authProvider: auth,
        });

  // Thread store is BFF-only (server component / Route Handler context)
  // Memory client is middleware-only — not wired here

  return { runtime, auth, flags, toolRegistry, uiRuntime };
}
```

### Python (`middleware/composition.py`)

```python
# middleware/composition.py
import os
from dataclasses import dataclass
from middleware.ports.jwt_verifier import JwtVerifier
from middleware.ports.tool_acl import ToolAclProvider
from middleware.ports.memory_client import MemoryClient
from middleware.ports.telemetry_exporter import TelemetryExporter

@dataclass(frozen=True)
class MiddlewareAdapters:
    profile: str
    jwt_verifier: JwtVerifier
    tool_acl: ToolAclProvider
    memory_client: MemoryClient
    telemetry_exporter: TelemetryExporter

def build_adapters(*, env=None) -> MiddlewareAdapters:
    e = dict(env) if env is not None else dict(os.environ)
    profile = e.get("ARCHITECTURE_PROFILE", "v3")

    from middleware.adapters.auth.workos_jwt_verifier import WorkOSJwtVerifier
    from middleware.adapters.acl.workos_role_acl import WorkOSRoleAcl
    verifier = WorkOSJwtVerifier(
        jwks_url=e.get("WORKOS_JWKS_URL", ...),
        expected_issuer=...,
        expected_client_id=e["WORKOS_CLIENT_ID"],
    )
    acl = WorkOSRoleAcl(role_to_tools=..., known_tools=...)

    if profile == "v2":
        from middleware.adapters.memory.self_hosted_mem0_client import SelfHostedMem0Client
        from middleware.adapters.observability.self_hosted_langfuse_exporter import SelfHostedLangfuseExporter
        memory = SelfHostedMem0Client(base_url=e["MEM0_URL"])
        telemetry = SelfHostedLangfuseExporter(...)
    else:
        from middleware.adapters.memory.mem0_cloud_hobby_client import Mem0CloudHobbyClient
        from middleware.adapters.observability.langfuse_cloud_hobby_exporter import LangfuseCloudHobbyExporter
        memory = Mem0CloudHobbyClient(api_key=e["MEM0_API_KEY"])
        telemetry = LangfuseCloudHobbyExporter(...)

    return MiddlewareAdapters(
        profile=profile,
        jwt_verifier=verifier,
        tool_acl=acl,
        memory_client=memory,
        telemetry_exporter=telemetry,
    )
```

**Rule C1 enforcement:** These two files are the only files in the entire codebase that contain `if profile == "v2"` adapter selection logic. Architecture tests assert that no other file contains such conditionals on `ARCHITECTURE_PROFILE`. The `MiddlewareAdapters` typed bag (rule C2) ensures downstream consumers receive port instances only.

---

## Conformance Test Bundle

Every port-adapter pair added to `frontend/lib/adapters/` must be registered in the parametrized conformance suite at `frontend/tests/architecture/test_port_conformance.ts`. The suite tests:

1. **Structural conformance** — the adapter's TypeScript type satisfies the port interface (compile-time check via `tsc --noEmit`).
2. **Behavioral contract** — the numbered behavioral rules from §4.x are tested against a scripted server or mock.
3. **Error-translation table** — each HTTP error code produces the correct typed error class.
4. **Idempotency** — `cancel()` called twice on the same `runId` does not throw.
5. **SDK type boundary** — no method return value contains an SDK-specific type (enforced via Zod parse of the return against the wire schema).

For Python middleware adapters, the equivalent suite lives at `middleware/tests/test_adapter_conformance.py` and follows the same pattern as `tests/agent_ui_adapter/adapters/runtime/test_conformance.py`.

---

## Logging Convention

Each adapter has its own log channel, mirroring the `logging.json` per-stream routing in the four-layer backend:


| Adapter family            | TS log namespace                | Python log name                     |
| ------------------------- | ------------------------------- | ----------------------------------- |
| `adapters/runtime/`       | `frontend:adapter:runtime`      | n/a                                 |
| `adapters/auth/`          | `frontend:adapter:auth`         | `middleware.adapters.auth`          |
| `adapters/thread_store/`  | `frontend:adapter:thread_store` | n/a                                 |
| `adapters/memory/`        | n/a (browser-side calls absent) | `middleware.adapters.memory`        |
| `adapters/observability/` | `frontend:adapter:telemetry`    | `middleware.adapters.observability` |
| `adapters/ui_runtime/`    | `frontend:adapter:ui_runtime`   | n/a                                 |


Log messages must not include access tokens, memory content, or LLM output text (PII boundary). They may include `trace_id`, `run_id`, `thread_id`, adapter name, and error type.

---

## Three-Phase Extension Roadmap

The adapter grid grows in the same three phases as `agent_ui_adapter/adapters/`.


| Phase                      | New adapter families                                                                                         | Trigger                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| **Current (V3/V2)**        | `runtime/`, `auth/`, `thread_store/`, `memory/`, `observability/`, `ui_runtime/`, `tool_renderer/`, `flags/` | Initial build                                                                    |
| **Phase 2 (V1.5)**         | Possibly `adapters/voice/` if `VoiceRuntime` port is introduced; `adapters/storage/` if attachments land     | Second concrete voice backend arrives; second attachment storage backend arrives |
| **Phase 3 (multi-region)** | `adapters/routing/` for multi-runtime `AgentRuntimeClient` selection                                         | Second `AgentRuntimeClient` backend (e.g., AWS Fargate endpoint) added           |


**Abstraction-introduction principle:** do not create `adapters/voice/` until two voice backends exist; do not add a new `ports/` interface until two implementations compete. A single backend is constructed directly in the composition root without an adapter directory.

---

## Relationship to Four-Layer Architecture and `agent_ui_adapter`

The frontend adapter ring sits above the `agent_ui_adapter` ring in exactly the same way that the `agent_ui_adapter` ring sits above the four-layer backend: additive, non-invasive, removable. The dependency chain is:

```
  frontend/lib/adapters/runtime/*
       │  HTTP/SSE (process boundary)
       ▼
  middleware/
       │  HTTP/SSE (process boundary)
       ▼
  agent_ui_adapter/server.py      ← existing composition root (unchanged)
       │  Python method call
       ▼
  agent_ui_adapter/ports/agent_runtime.py
       │  Python method call
       ▼
  agent_ui_adapter/adapters/runtime/langgraph_runtime.py
       │  LangGraph SDK call
       ▼
  Four-Layer Backend
```

Every process boundary is crossed via HTTP/SSE. No layer reaches across a process boundary at module scope. The trust foundation (`trust/`) is the only Python package that participates on both sides of the seam — the middleware imports `trust/` models for identity shape definitions, but never for service calls.