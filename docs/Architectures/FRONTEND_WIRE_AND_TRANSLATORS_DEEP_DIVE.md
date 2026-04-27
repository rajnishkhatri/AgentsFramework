# Frontend — Wire and Translators Deep Dive

**Scope:** `frontend/lib/wire/`, `frontend/lib/trust-view/`, `frontend/lib/translators/`, `frontend/lib/transport/`
**Related documents:**

- `docs/Architectures/FRONTEND_ARCHITECTURE.md` — big-picture view of the full frontend ring
- `docs/Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md` — exhaustive spec for ports and adapters
- `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md` — the Python `wire/`, `translators/`, and `transport/` sub-packages that these TypeScript modules mirror

---

## Governing Thought

The `agent_ui_adapter/` ring achieves framework-agnosticism in its core by keeping `wire/`, `translators/`, and `transport/` completely free of third-party SDK imports. `wire/` is a shared kernel: pure Pydantic models, no I/O. `translators/` are pure functions: deterministic, no side effects. `transport/` handles SSE encoding: one stdlib dependency.

The frontend ring applies exactly the same principle in TypeScript. `frontend/lib/wire/` is the TypeScript shared kernel: pure Zod schemas and inferred types, no network calls, no React. `frontend/lib/translators/` are pure functions with no side effects. `frontend/lib/transport/` is the SSE consumer: one `EventSource` dependency. Third-party SDK imports appear only in `adapters/` — never here.

The benefit is identical to the Python side: if CopilotKit is replaced at v1.5, `wire/`, `translators/`, and `transport/` do not change. Only the adapter and the composition root move.

---

## Architectural Identity

The two TypeScript shared kernels are the innermost rings of the browser+BFF sub-ring. They play the same role that `trust/` and `agent_ui_adapter/wire/` play on the Python side:

```
  frontend/lib/ (Browser + BFF sub-ring)

  ╔═════════════════════════════════════════════════════╗  ← composition root
  ║  composition.ts                                     ║
  ╠═════════════════════════════════════════════════════╣
  ║  adapters/          (SDK boundary)                  ║
  ╠═════════════════════════════════════════════════════╣
  ║  ports/             (interface definitions)         ║
  ╠═════════════════════════════════════════════════════╣
  ║  translators/       (pure functions)                ║
  ╠═════════════════════════════════════════════════════╣
  ║  transport/         (SSE client)                    ║
  ╠═════════════════════════════════════════════════════╣
  ║  wire/   trust-view/   (shared kernels — innermost) ║  ← no outward deps
  ╚═════════════════════════════════════════════════════╝
```

Every arrow points inward toward the two kernels. Nothing in `wire/` or `trust-view/` imports from any other layer in the frontend ring.

---

## `wire/` — Module Specification

`frontend/lib/wire/` mirrors `agent_ui_adapter/wire/` one-to-one. Each TypeScript module corresponds to a Python module; the data shapes are structurally identical (field names, field types, optionality). The single source of truth is the **Python side** — TypeScript schemas are hand-authored and CI-verified against the Python JSON Schema export (see §8).

**Import rule:** `wire/` modules may import only `zod` and each other. No React, no SDK, no browser API.

### 3.1 `wire/domain_events.ts`

Mirrors `agent_ui_adapter/wire/domain_events.py`. Defines the nine `DomainEvent` union variants emitted by the Python runtime adapter and received by the frontend over SSE.

```typescript
// frontend/lib/wire/domain_events.ts
import { z } from "zod";

const BaseEvent = z.object({
  trace_id: z.string(),
});

export const RunStartedDomain = BaseEvent.extend({
  type: z.literal("run_started_domain"),
  run_id: z.string(),
  thread_id: z.string(),
});

export const RunFinishedDomain = BaseEvent.extend({
  type: z.literal("run_finished_domain"),
  run_id: z.string(),
  thread_id: z.string(),
  error: z.string().nullable(),
});

export const LLMTokenEmitted = BaseEvent.extend({
  type: z.literal("llm_token_emitted"),
  message_id: z.string(),
  delta: z.string(),
});

export const LLMMessageStarted = BaseEvent.extend({
  type: z.literal("llm_message_started"),
  message_id: z.string(),
});

export const LLMMessageEnded = BaseEvent.extend({
  type: z.literal("llm_message_ended"),
  message_id: z.string(),
});

export const ToolCallStarted = BaseEvent.extend({
  type: z.literal("tool_call_started"),
  tool_call_id: z.string(),
  tool_name: z.string(),
  args_json: z.string(),
});

export const ToolCallEnded = BaseEvent.extend({
  type: z.literal("tool_call_ended"),
  tool_call_id: z.string(),
});

export const ToolResultReceived = BaseEvent.extend({
  type: z.literal("tool_result_received"),
  tool_call_id: z.string(),
  result: z.string(),
});

export const StateMutated = BaseEvent.extend({
  type: z.literal("state_mutated"),
  delta: z.unknown(),   // JSON Patch payload; populated in Phase 2
});

export const DomainEvent = z.discriminatedUnion("type", [
  RunStartedDomain,
  RunFinishedDomain,
  LLMTokenEmitted,
  LLMMessageStarted,
  LLMMessageEnded,
  ToolCallStarted,
  ToolCallEnded,
  ToolResultReceived,
  StateMutated,
]);

export type DomainEvent = z.infer<typeof DomainEvent>;
```

**Every event carries `trace_id`** (via `BaseEvent`). This enforces rule F-R7 at the schema level: a domain event that lacks `trace_id` will fail Zod parsing before it reaches the translators.

---

### 3.2 `wire/agent_protocol.ts`

Mirrors `agent_ui_adapter/wire/agent_protocol.py`. HTTP wire shapes for the REST/SSE surface shared between the middleware and `agent_ui_adapter`.

```typescript
// frontend/lib/wire/agent_protocol.ts
import { z } from "zod";

export const RunCreateRequest = z.object({
  thread_id: z.string(),
  input: z.record(z.unknown()),
  agent_id: z.string().optional(),
  model_tier: z.enum(["fast", "capable"]).optional(),
});
export type RunCreateRequest = z.infer<typeof RunCreateRequest>;

export const ThreadState = z.object({
  thread_id: z.string(),
  messages: z.array(z.unknown()),
  metadata: z.record(z.unknown()).optional(),
});
export type ThreadState = z.infer<typeof ThreadState>;

export const Thread = z.object({
  id: z.string(),
  title: z.string(),
  archived_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Thread = z.infer<typeof Thread>;

export const Session = z.object({
  user_id: z.string(),
  email: z.string(),
  display_name: z.string().nullable(),
  access_token: z.string(),
  expires_at: z.number(),
});
export type Session = z.infer<typeof Session>;
```

---

### 3.3 `wire/ag_ui_events.ts`

Mirrors `agent_ui_adapter/wire/ag_ui_events.py`. AG-UI protocol event types received from the SSE stream and emitted toward the UI runtime. These are the events that `adapters/runtime/*` yields from `stream()`.

```typescript
// frontend/lib/wire/ag_ui_events.ts
import { z } from "zod";

// AG-UI event type discriminant values match the SSE `event:` field names
export const RunStartedEvent = z.object({
  type: z.literal("run.started"),
  run_id: z.string(),
  thread_id: z.string(),
  model: z.string().optional(),
  started_at: z.string(),
  trace_id: z.string(),
});

export const TokenEvent = z.object({
  type: z.literal("token"),
  delta: z.string(),
  trace_id: z.string(),
});

export const ToolStartEvent = z.object({
  type: z.literal("tool.start"),
  tool_call_id: z.string(),
  name: z.string(),
  input: z.unknown(),
  trace_id: z.string(),
});

export const ToolEndEvent = z.object({
  type: z.literal("tool.end"),
  tool_call_id: z.string(),
  output: z.unknown(),
  error: z.string().nullable(),
  duration_ms: z.number(),
  trace_id: z.string(),
});

export const ModelSwitchEvent = z.object({
  type: z.literal("model.switch"),
  from_tier: z.string(),
  to_tier: z.string(),
  reason: z.string(),
  trace_id: z.string(),
});

export const StepEvent = z.object({
  type: z.literal("step"),
  step_count: z.number(),
  total_cost_usd: z.number(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  trace_id: z.string(),
});

export const RunCompletedEvent = z.object({
  type: z.literal("run.completed"),
  final_message: z.string(),
  step_count: z.number(),
  total_cost_usd: z.number(),
  trace_id: z.string(),
});

export const RunErrorEvent = z.object({
  type: z.literal("run.error"),
  error_type: z.string(),
  message: z.string(),
  retryable: z.boolean(),
  trace_id: z.string(),
});

export const RunCancelledEvent = z.object({
  type: z.literal("run.cancelled"),
  at_step: z.number(),
  trace_id: z.string(),
});

export const AGUIEvent = z.discriminatedUnion("type", [
  RunStartedEvent,
  TokenEvent,
  ToolStartEvent,
  ToolEndEvent,
  ModelSwitchEvent,
  StepEvent,
  RunCompletedEvent,
  RunErrorEvent,
  RunCancelledEvent,
]);
export type AGUIEvent = z.infer<typeof AGUIEvent>;
```

---

### 3.4 `wire/ui_runtime_events.ts`

**Not mirrored** from the Python side — this module is frontend-only. It defines the UI-side derived event types that translators produce from AG-UI events for consumption by the UI runtime and tool renderer components.

```typescript
// frontend/lib/wire/ui_runtime_events.ts
import { z } from "zod";

/** Emitted by tool_event_to_renderer_request translator when a tool starts */
export const ToolRendererRequest = z.object({
  type: z.literal("tool_renderer_request"),
  tool_call_id: z.string(),
  tool_name: z.string(),
  input: z.unknown(),
  trace_id: z.string(),
});
export type ToolRendererRequest = z.infer<typeof ToolRendererRequest>;

/** Emitted by tool_event_to_renderer_request translator when a tool ends */
export const ToolRendererUpdate = z.object({
  type: z.literal("tool_renderer_update"),
  tool_call_id: z.string(),
  output: z.unknown(),
  error: z.string().nullable(),
  duration_ms: z.number(),
  trace_id: z.string(),
});
export type ToolRendererUpdate = z.infer<typeof ToolRendererUpdate>;

/** Memory context prepended to the system input by the middleware */
export const MemoryResult = z.object({
  memory_id: z.string(),
  text: z.string(),
  score: z.number(),
  created_at: z.string(),
});
export type MemoryResult = z.infer<typeof MemoryResult>;

/** Feature flag name registry (compile-time exhaustiveness) */
export const FeatureFlag = z.enum([
  "voice_mode",
  "pyramid_panel",
  "per_tool_authorization",
  "json_run_export",
]);
export type FeatureFlag = z.infer<typeof FeatureFlag>;
```

---

## `trust-view/` — The Frontend Trust Kernel

`frontend/lib/trust-view/` is the TypeScript mirror of a **read-only subset** of `trust/models.py`. It exists so the frontend can display identity information (user ID, agent name, authorization decision outcomes) without importing Python code or enabling trust mutations from the browser.

**Import rule:** `trust-view/` modules may import only `zod`. Same constraint as `wire/`.

### What is in `trust-view/`

```typescript
// frontend/lib/trust-view/identity.ts
import { z } from "zod";

/** Read-only view of the authenticated user's identity (from the WorkOS session) */
export const IdentityClaim = z.object({
  user_id: z.string(),
  email: z.string(),
  groups: z.array(z.string()),
});
export type IdentityClaim = z.infer<typeof IdentityClaim>;

/** The agent the user is talking to (from the /agents endpoint) */
export const AgentFactsView = z.object({
  agent_id: z.string(),
  display_name: z.string(),
  capabilities: z.array(z.string()),
  certification_status: z.enum(["certified", "provisional", "failed", "expired"]),
  trust_tier: z.enum(["ring_0", "ring_1", "ring_2", "ring_3"]).optional(),
});
export type AgentFactsView = z.infer<typeof AgentFactsView>;

/** Per-tool authorization decision view (F17 — authorization UI) */
export const PolicyDecisionView = z.object({
  tool_name: z.string(),
  enforcement: z.enum(["allow", "deny", "require_approval", "throttle"]),
  reason: z.string(),
});
export type PolicyDecisionView = z.infer<typeof PolicyDecisionView>;

/** Carries trace_id + run_id for the currently active run */
export const RunIdentity = z.object({
  run_id: z.string(),
  trace_id: z.string(),
  thread_id: z.string(),
  started_at: z.string(),
});
export type RunIdentity = z.infer<typeof RunIdentity>;
```

### What is NOT in `trust-view/`

The following capabilities are **permanently excluded** from `trust-view/`:

- `compute_signature()` / `verify_signature()` — cryptographic operations belong in the Python backend only.
- `AgentFacts` mutation methods — the frontend can read agent data; it cannot update it.
- `LifecycleState` transitions — governance state machine is Python-only.
- `TrustTraceRecord` emission — the frontend never emits trust trace records directly; `trace_id` is forwarded only.
- `Capability` or `Policy` objects — the frontend receives only the derived `enforcement` decision, not the raw policy definitions.

Invariant F-R6 is implemented here: the TypeScript compiler enforces that `trust-view/` exports only `z.infer<...>` types (plain objects), never functions or classes with mutable state.

---

## `translators/` — Pure Functions

Translators map between wire shapes. They have no I/O, no side effects, no React, and no SDK imports. They are pure functions with deterministic behavior: given the same input, they always produce the same output.

**Import rule:** `translators/` modules may import from `wire/` and `trust-view/` only.

### 5.1 `translators/ag_ui_to_ui_runtime.ts`

Maps AG-UI events from the SSE stream to the shapes expected by the UI runtime (CopilotKit message-list API today; `UIRuntime` interface in the future).

**Input → Output table:**

| AG-UI input event | Output shape | Notes |
| --- | --- | --- |
| `RunStartedEvent` | `{ type: "run_started", runId, threadId, traceId }` | Signals UI to show loading indicator |
| `TokenEvent` | `{ type: "token", delta, traceId }` | Appended to the in-progress assistant message |
| `ToolStartEvent` | `ToolRendererRequest` (via `tool_event_to_renderer_request.ts`) | Delegates to the tool translator |
| `ToolEndEvent` | `ToolRendererUpdate` (via `tool_event_to_renderer_request.ts`) | Delegates to the tool translator |
| `ModelSwitchEvent` | `{ type: "model_switch", fromTier, toTier, traceId }` | Signals `ModelBadge` component to update |
| `StepEvent` | `{ type: "step", stepCount, totalCostUsd, traceId }` | Signals step counter + cost meter components |
| `RunCompletedEvent` | `{ type: "run_completed", finalMessage, stepCount, totalCostUsd, traceId }` | Finalizes the assistant message |
| `RunErrorEvent` | `{ type: "run_error", message, retryable, traceId }` | Surfaces error toast; retryable drives the Regenerate button |
| `RunCancelledEvent` | `{ type: "run_cancelled", atStep, traceId }` | Surfaces cancellation confirmation |

All output shapes carry `traceId` forwarded verbatim from the input event.

---

### 5.2 `translators/ui_input_to_agent_request.ts`

Maps Composer user input (text, optional files, optional thread) to a `RunCreateRequest` wire shape.

```typescript
// Pure function — no React, no I/O
export function toRunCreateRequest(
  input: ComposerInput,       // { text: string; threadId: string; agentId?: string }
  identity: IdentityClaim,    // from trust-view/
  memoryContext: MemoryResult[] // from MemoryClient (pre-fetched by middleware)
): RunCreateRequest {
  return {
    thread_id: input.threadId,
    input: {
      messages: [{ role: "user", content: input.text }],
      user_id: identity.user_id,
      memory_context: memoryContext,
    },
    agent_id: input.agentId,
  };
}
```

**Input → Output table:**

| `ComposerInput` field | `RunCreateRequest` field | Notes |
| --- | --- | --- |
| `text` | `input.messages[0].content` | Wrapped in `{ role: "user" }` |
| `threadId` | `thread_id` | Direct pass-through |
| `agentId` | `agent_id` | Optional; omit for default agent |
| `identity.user_id` | `input.user_id` | Threaded through to `eval_capture` |
| `memoryContext` | `input.memory_context` | Pre-fetched by middleware; injected here |

---

### 5.3 `translators/sealed_envelope.ts`

Mirrors `agent_ui_adapter/translators/sealed_envelope.py`. Wraps and unwraps HITL (Human-in-the-Loop) approval round-trips.

```typescript
export interface SealedApprovalRequest {
  envelope_id: string;
  tool_name: string;
  input: unknown;
  reason: string;
  trace_id: string;
}

export interface ApprovalDecision {
  envelope_id: string;
  approved: boolean;
  denied_reason?: string;
  trace_id: string;
}

/** Wraps a tool-start event into a HITL approval request */
export function sealApprovalRequest(event: ToolStartEvent): SealedApprovalRequest { ... }

/** Unwraps a user approval UI interaction into a decision */
export function unsealApprovalDecision(
  envelopeId: string,
  approved: boolean,
  deniedReason?: string,
  traceId: string,
): ApprovalDecision { ... }
```

This translator is invoked by the `AuthorizationPrompt` component (F17 generative UI) when a tool requires user approval. The `trace_id` is forwarded from the originating `ToolStartEvent`.

---

### 5.4 `translators/tool_event_to_renderer_request.ts`

Maps wire tool events to `ToolRendererRegistry` render requests. Called by the `ag_ui_to_ui_runtime.ts` translator for `ToolStartEvent` and `ToolEndEvent`.

**Input → Output table:**

| Wire event | Output type | `ToolRendererRequest` / `ToolRendererUpdate` fields |
| --- | --- | --- |
| `ToolStartEvent` | `ToolRendererRequest` | `toolCallId`, `toolName`, `input` (parsed from `args_json`), `traceId` |
| `ToolEndEvent` | `ToolRendererUpdate` | `toolCallId`, `output`, `error`, `durationMs`, `traceId` |

```typescript
export function toolStartToRequest(event: ToolStartEvent): ToolRendererRequest {
  return {
    type: "tool_renderer_request",
    tool_call_id: event.tool_call_id,
    tool_name: event.name,
    input: JSON.parse(event.input as string),   // args_json from wire
    trace_id: event.trace_id,
  };
}
```

The renderer component receives `ToolRendererRequest` and narrows `input` with its own Zod schema. The translator does not parse the tool-specific payload — that responsibility belongs to the renderer.

---

## `transport/` — SSE Transport

Transport modules handle network I/O for the SSE connection. They import from `wire/` only — no SDK, no React, no auth logic.

### 6.1 `transport/sse_client.ts`

Typed `EventSource` wrapper with `Last-Event-ID` resumption, backpressure, retry policy, and heartbeat detection. Mirrors `agent_ui_adapter/transport/{sse,heartbeat,backpressure,resumption}.py` in behavior.

**Key behaviors:**

| Behavior | Implementation |
| --- | --- |
| **Typed events** | Each SSE `data:` frame is parsed against `AGUIEvent` Zod schema before yielding |
| **`Last-Event-ID`** | Every received event includes an `id: <run_id>:<seq>` field; reconnect sends `Last-Event-ID` header automatically via the `EventSource` spec |
| **Retry policy** | Exponential backoff: 500ms, 1000ms, 2000ms, 4000ms; max 4 reconnect attempts; surfaces `AgentNetworkError` on max-retry exhaustion |
| **Heartbeat detection** | Server sends `:\n\n` comment frames every 15s; client detects absence after 30s as a stale connection and triggers reconnect |
| **Backpressure** | If the consumer is processing events slower than they arrive, the client buffers up to 100 events and drops oldest events after that (non-blocking consumer is the contract) |
| **Cancellation** | Returns an `AbortController`; calling `abort()` closes the `EventSource` cleanly and is idempotent |

```typescript
export interface SSEClientOptions {
  url: string;
  headers: Record<string, string>;
  lastEventId?: string;
  onEvent: (event: AGUIEvent) => void;
  onError?: (err: SSEError) => void;
  signal?: AbortSignal;
}

export function createSSEConnection(options: SSEClientOptions): () => void {
  // Returns a cleanup function that closes the connection
  ...
}
```

---

### 6.2 `transport/edge_proxy.ts`

BFF Route Handler helper that forwards SSE byte-for-byte from the middleware to the browser. Runs only in the Next.js server runtime (Vercel Edge Functions or Node.js Route Handlers) — never in the browser bundle.

**Critical headers set by the proxy:**

| Header | Value | Why |
| --- | --- | --- |
| `Content-Type` | `text/event-stream; charset=utf-8` | SSE MIME type |
| `Cache-Control` | `no-cache, no-transform` | Prevents edge caching and compression |
| `X-Accel-Buffering` | `no` | Disables nginx/Vercel upstream buffering |
| `Connection` | `keep-alive` | Keeps the connection open for streaming |
| `Transfer-Encoding` | (cleared) | Prevents chunked encoding which can confuse some proxies |

**`Accept-Encoding` strip:** For streaming routes (`/api/run/stream`), the proxy deletes the `Accept-Encoding` request header before forwarding to the middleware. This prevents the Cloud Run origin from attempting gzip/brotli compression on an SSE stream, which causes 502 errors on some proxy configurations.

```typescript
// frontend/app/api/run/stream/route.ts (usage pattern)
export async function POST(req: Request) {
  const token = await getAccessToken();
  return forwardSSEStream({
    upstreamUrl: `${process.env.MIDDLEWARE_URL}/agent/runs/stream`,
    upstreamHeaders: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: await req.text(),
  });
}
```

**Cross-substrate notes:**

- **V3-Dev-Tier (Cloudflare Pages free + Cloud Run):** Cloudflare Pages streams SSE natively without buffering. The `Cache-Control: no-transform` and `X-Accel-Buffering: no` headers are still set for defense in depth, but no Cloudflare-specific bypass configuration is required.
- **V2-Frontier (Cloudflare + Cloud Run min=1):** Same as V3 — Cloudflare does not buffer streaming responses by default.

This is the key infrastructure advantage of Cloudflare over the CloudFront + WAF stack that V1 required: Cloudflare streams SSE byte-for-byte without the `CachingDisabled` cache policy + `accept-encoding` strip + response-headers policy workaround that V1 mandated.

---

## Dependency-Direction Invariants

The complete import rule table for the frontend inner rings, enforced by `tests/architecture/test_frontend_layering.ts`:


| Module | May import from | May NOT import from |
| --- | --- | --- |
| `wire/` | `zod`, stdlib | Everything else in `frontend/lib/` |
| `trust-view/` | `zod`, stdlib | Everything else in `frontend/lib/` |
| `translators/` | `wire/`, `trust-view/` | `adapters/`, `ports/`, `transport/`, `composition.ts`, any SDK |
| `transport/` | `wire/`, stdlib | `adapters/`, `ports/`, `translators/`, `composition.ts`, any SDK except `EventSource` (browser API) |
| `ports/` | `wire/`, `trust-view/` | `adapters/`, `translators/`, `transport/`, `composition.ts` |
| `adapters/` | `ports/`, `wire/`, `trust-view/`, SDKs | `translators/`, `transport/`, `composition.ts`, other `adapters/` |
| `composition.ts` | Everything in `frontend/lib/` | Nothing (it is the root) |

The invariant: arrows always point toward `wire/` and `trust-view/` (the two innermost kernels). `composition.ts` is the outermost layer and is never imported by anything inside the package.

---

## Wire-Schema Drift Detection

The Python side (`agent_ui_adapter/wire/`) is the single source of truth for all shared event shapes. TypeScript schemas are hand-authored mirrors. CI must catch any divergence.

### Mechanism

A CI job runs on every push to `main` or any branch that touches `agent_ui_adapter/wire/` or `frontend/lib/wire/`:

```bash
# ci/check-wire-schema-drift.sh
python - <<'EOF'
from agent_ui_adapter.wire.domain_events import DomainEvent
from agent_ui_adapter.wire.agent_protocol import RunCreateRequest, ThreadState
from agent_ui_adapter.wire.ag_ui_events import AGUIEvent
import json, pathlib

schemas = {
    "domain_events": DomainEvent.model_json_schema(),
    "run_create_request": RunCreateRequest.model_json_schema(),
    "thread_state": ThreadState.model_json_schema(),
    "ag_ui_event": AGUIEvent.model_json_schema(),
}
pathlib.Path("/tmp/wire_schemas.json").write_text(json.dumps(schemas, indent=2))
EOF

# Compare against committed baseline
diff /tmp/wire_schemas.json frontend/lib/wire/__python_schema_baseline__.json
if [ $? -ne 0 ]; then
  echo "Wire schema drift detected. Update frontend/lib/wire/ TS types to match Python schemas."
  exit 1
fi
```

`frontend/lib/wire/__python_schema_baseline__.json` is a committed JSON file that contains the last known Python JSON Schema export. When Python schemas change, the developer must:

1. Run `make wire-schema-snapshot` to regenerate the baseline file.
2. Update the corresponding TypeScript Zod schema.
3. Commit both files together.

This gives a clean diff in every PR: if `__python_schema_baseline__.json` changes, the reviewer knows to look for a matching TypeScript schema update.

### Why hand-authored TS, not codegen

Codegen (`datamodel-code-generator` or similar) was evaluated and rejected for two reasons:

1. **Kernel stability.** `wire/` is a stable shared kernel. Codegen makes it a derived artifact, which means every Python schema change silently regenerates TS types. A human must review the TS delta — hand-authoring makes that review explicit and mandatory.
2. **Zod vs JSON Schema expressiveness.** Zod's `.discriminatedUnion()` (used for `DomainEvent` and `AGUIEvent`) is more ergonomic and generates better TypeScript inference than what most codegen tools produce. Maintaining Zod schemas by hand is lower friction than post-processing codegen output.

---

## AG-UI Event Translation Contract

The following table is the canonical specification of how `DomainEvent` variants (emitted by the Python runtime adapter and arriving as SSE frames) map to `AGUIEvent` variants (parsed by the TypeScript `transport/sse_client.ts`) and then to UI-runtime shapes (produced by `translators/ag_ui_to_ui_runtime.ts`).

The mapping from `DomainEvent` (Python internal type) to `AGUIEvent` (wire type on the SSE stream) is performed by the Python `agent_ui_adapter/translators/domain_to_ag_ui.py`. The mapping from `AGUIEvent` to UI-runtime shapes is performed by the TypeScript `translators/ag_ui_to_ui_runtime.ts`.


| `DomainEvent` (Python) | `AGUIEvent` on the wire | UI-runtime output shape | Renderer target |
| --- | --- | --- | --- |
| `RunStartedDomain` | `RunStartedEvent` | `{ type: "run_started", ... }` | Loading indicator |
| `LLMTokenEmitted` | `TokenEvent` | `{ type: "token", delta, traceId }` | Streaming message content |
| `LLMMessageStarted` | (internal; no AG-UI event) | — | — |
| `LLMMessageEnded` | (internal; no AG-UI event) | — | — |
| `ToolCallStarted` | `ToolStartEvent` | `ToolRendererRequest` | `ToolRendererRegistry.getRenderer(toolName)` |
| `ToolCallEnded` | — | — | — |
| `ToolResultReceived` | `ToolEndEvent` | `ToolRendererUpdate` | Same renderer component (status → `"done"`) |
| `StateMutated` | (Phase 2; `StepEvent` carries cost/step) | `{ type: "step", ... }` | Step counter + cost meter |
| `RunFinishedDomain` (no error) | `RunCompletedEvent` | `{ type: "run_completed", ... }` | Finalizes message; hides loading indicator |
| `RunFinishedDomain` (error) | `RunErrorEvent` | `{ type: "run_error", ... }` | Error toast; retryable → Regenerate button |

**Zero-to-many mapping rule:** Some `DomainEvent` variants produce zero AG-UI events (e.g., `LLMMessageStarted` is an internal accounting event). Some produce more than one in Phase 2 (e.g., `StateMutated` produces both a `StepEvent` and potentially a `model.switch` event). The TypeScript `transport/sse_client.ts` handles this by calling `onEvent` once per received SSE frame; the translation is always 1-to-1 at the wire level (the Python `to_ag_ui()` function handles the 1-to-many expansion before encoding).

---

## Trust-Trace Propagation on the Wire

`trace_id` originates in the Python runtime adapter (`agent_ui_adapter/adapters/runtime/langgraph_runtime.py`) and must travel unchanged from the Python process through the middleware to the browser.

### Propagation path

```
Python runtime adapter
    │  generates trace_id = uuid4().hex once per run
    │  attaches to every DomainEvent
    ▼
agent_ui_adapter/translators/domain_to_ag_ui.py
    │  copies trace_id into every AGUIEvent
    ▼
SSE wire (text/event-stream)
    │  trace_id is a field in every SSE data payload
    ▼
middleware/ (SSE pass-through — does NOT modify event payloads)
    │  reads trace_id from events for TelemetryExporter span correlation
    │  must not alter or strip trace_id
    ▼
BFF edge_proxy.ts (SSE pass-through — does NOT modify event payloads)
    │  must not alter or strip trace_id
    ▼
transport/sse_client.ts
    │  parses each AGUIEvent with Zod — trace_id validated as required field
    │  yields typed AGUIEvent objects with trace_id intact
    ▼
translators/ag_ui_to_ui_runtime.ts
    │  forwards trace_id into every output shape
    ▼
UI runtime + components
    │  pass trace_id into TelemetrySink.span() calls for browser RUM correlation
```

### Rules

1. **The browser must never generate a `trace_id`.** The `wire/domain_events.ts` `BaseEvent` schema does not expose a `trace_id` setter — the field is read-only by convention.
2. **Every translator must forward `trace_id` from input to output.** A translator output that drops `trace_id` fails the conformance test bundle.
3. **Zod parse failure on missing `trace_id` is surfaced as a `RunErrorEvent`.** The `transport/sse_client.ts` catches Zod parse errors, logs them via `TelemetrySink`, and emits a synthetic `RunErrorEvent` with `error_type: "wire_parse_error"` so the UI can surface an error state without crashing.
4. **The middleware must include `trace_id` in `TelemetryExporter.start_span()` calls.** This correlates Langfuse traces with the trust trace records emitted by the Python runtime adapter, enabling end-to-end run tracing across both the Python and TypeScript sides.

---

## Relationship to `agent_ui_adapter/wire/`, `/translators/`, `/transport/`

The relationship is mirror-and-extend:


| `agent_ui_adapter/` module | `frontend/lib/` mirror | Extension |
| --- | --- | --- |
| `wire/domain_events.py` | `wire/domain_events.ts` | Identical shapes; TS has Zod parse validation |
| `wire/agent_protocol.py` | `wire/agent_protocol.ts` | Identical shapes |
| `wire/ag_ui_events.py` | `wire/ag_ui_events.ts` | Identical shapes |
| (no equivalent) | `wire/ui_runtime_events.ts` | Frontend-only; no Python mirror |
| (no equivalent) | `trust-view/` | Frontend-only read-only shapes derived from `trust/` |
| `translators/domain_to_ag_ui.py` | (Python side; no TS mirror) | Python handles DomainEvent → AGUIEvent |
| (no equivalent) | `translators/ag_ui_to_ui_runtime.ts` | TypeScript-only; maps AGUIEvent → UI shapes |
| `translators/ag_ui_to_domain.py` | `translators/ui_input_to_agent_request.ts` | Inverse direction; user input → RunCreateRequest |
| `translators/sealed_envelope.py` | `translators/sealed_envelope.ts` | HITL envelope; both sides needed for round-trip |
| `transport/sse.py` | `transport/edge_proxy.ts` | Python encodes SSE; TS proxies SSE byte-for-byte |
| `transport/resumption.py` | `transport/sse_client.ts` | Python tracks Last-Event-ID; TS reconnects with it |
| `transport/backpressure.py` | `transport/sse_client.ts` | Both sides implement configurable backpressure |
| `transport/heartbeat.py` | `transport/sse_client.ts` | Both sides handle heartbeat comment frames |

The invariant: the Python side handles encoding (DomainEvent → AGUIEvent → SSE bytes); the TypeScript side handles decoding (SSE bytes → AGUIEvent → UI shapes). They meet at the wire format — `AGUIEvent` defined identically in both languages — and never import each other.
