---
type: architecture
title: 'Frontend Port Deviations — V3-Dev-Tier (Canonical)'
description: 'Status: Accepted (as of Sprint 3, V3-Dev-Tier).'
tags: [architecture]
---

# Frontend Port Deviations — V3-Dev-Tier (Canonical)

**Status:** Accepted (as of Sprint 3, V3-Dev-Tier).
**Supersedes for the listed ports:** [`FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md` §4.1, §4.2, §4.3](./FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md).
**Audience:** Architects and code reviewers comparing the implemented `frontend/lib/ports/` to the original deep-dive spec.

---

## Why this document exists

The Sprint 3 implementation of `frontend/lib/ports/` deviates from the
interface signatures shown in
[`FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md`](./FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md)
in three ports:

- `AgentRuntimeClient` — `stream()` split into `createRun()` + `streamRun()`; `getState()` removed.
  **Revised 2026-06-11 (D-V3-P1-R1, below):** re-merged to a single `streamRun(req)`; `createRun()` removed.
- `AuthProvider` — `signIn()` removed; `getSession()` returns `IdentityClaim` instead of `Session`.
- `ThreadStore` — `update()` / `delete()` / `getMessages()` removed; `get()` / `rename()` added; every method takes an `IdentityClaim` first.

After the Sprint 3 architectural review the deviations were classified
as **deliberate refinements**, not regressions. This document promotes
the implementation to canonical for V3-Dev-Tier and explains the
rationale per port. The deep-dive doc retains its Sprint 0 signatures
for historical context; reviewers should rely on **this** document and
the live `frontend/lib/ports/*.ts` files.

The unchanged ports (`MemoryClient`, `TelemetrySink`, `FeatureFlagProvider`,
`ToolRendererRegistry`, `UIRuntime`) match the deep-dive spec verbatim
and are out of scope here.

All deviations preserve **F-R3** (one interface per file), **F-R8** (no
SDK type past adapter boundary), and **A4** (port methods accept and
return `wire/` or `trust-view/` types only).

---

## D-V3-P1 — `AgentRuntimeClient`: split `stream()` into `createRun()` + `streamRun()`; remove `getState()`

### Spec (per deep-dive §4.1)

```typescript
interface AgentRuntimeClient {
  stream(req: RunCreateRequest): AsyncIterable<AGUIEvent>;
  cancel(runId: string): Promise<void>;
  getState(threadId: string): Promise<ThreadState>;
}
```

### Implemented (canonical)

```typescript
interface AgentRuntimeClient {
  createRun(req: RunCreateRequest): Promise<RunStateView>;
  streamRun(runId: string): AsyncIterable<UIRuntimeEvent>;
  cancel(runId: string): Promise<void>;
}
```

### Delta

| Change | Rationale |
|--------|-----------|
| `stream()` → `createRun()` + `streamRun()` | The two-step flow lets the caller obtain a `run_id` before subscribing to its event stream, which is required for: (a) `Last-Event-ID` resumption (the client must know the run id before reconnecting), (b) telemetry attaching the run id to spans before the first frame arrives, (c) UI showing "running" state immediately rather than after the first SSE byte. |
| Yields `UIRuntimeEvent` (post-translation) instead of `AGUIEvent` (raw wire) | Keeps the AG-UI → UIRuntime translation inside the adapter ring (assembled by the composition root via `openUIRuntimeStream` injection per Rule **A3**) so component code never observes raw wire events. Pure `wire/` types still cross the boundary; `UIRuntimeEvent` is also a `wire/` type so **A4** is satisfied. |
| `getState(threadId)` removed | Thread-state retrieval is the responsibility of the **`ThreadStore`** port (`get(identity, threadId)`), not the runtime. The original spec accidentally split a single concern across two ports. With `getState()` removed from `AgentRuntimeClient`, each port has exactly one responsibility: `AgentRuntimeClient` owns *runs*; `ThreadStore` owns *threads*. |

### Trust-trace boundary preserved

`trace_id` still flows verbatim from the backend through every yielded
event. The browser still never generates one (FE-AP-7 **AUTO-REJECT**).
Transport-level errors (parse error, heartbeat timeout) where no real
`trace_id` is available use a documented sentinel `"no-trace"` —
synthesized in the composition root, not in the adapter, and never
confused with a backend trace.

### Behavioral contract additions

The behavioral contract from the deep-dive is preserved verbatim with
two additions specific to the split:

1. `createRun(req)` resolves with `status: "running"` and **must not**
   block on first event delivery. The SSE stream is the single source of
   truth for run progress.
2. `streamRun(runId)` always terminates with either a `run_completed`
   or `run_error` UIRuntime event (Runtime Contract §1: terminal event
   always emitted).

---

## D-V3-P1-R1 (2026-06-11) — `AgentRuntimeClient`: single-POST protocol; `streamRun(req)`, `createRun()` removed

**Status:** Accepted; supersedes the D-V3-P1 signature above. Decided
during the eval-UI trajectory phase
(`docs/plans/goaljudge_eval_ui_trajectory_phase.plan.md` §8.6-F).

### Implemented (canonical)

```typescript
interface AgentRuntimeClient {
  streamRun(req: RunCreateRequest): AsyncIterable<UIRuntimeEvent>;
  cancel(runId: string): Promise<void>;
}
```

### Why the split was reversed

The D-V3-P1 two-step flow (`createRun` → `streamRun(runId)`) assumed
the middleware exposed a run-creation endpoint separate from the event
stream. The live middleware protocol has no such endpoint: the only
run-starting route is `POST /run/stream`, and **the HTTP response body
of that POST is the SSE stream itself**. There is no moment at which a
`run_id` exists before the first frame; the `run_id` arrives inside
the first `RUN_STARTED` event. Keeping `createRun()` would have forced
the adapter to fabricate a `RunStateView` (a lie at the port boundary)
or to open the stream early and buffer it (hidden state across two
port calls).

The D-V3-P1 rationale items fall away with it:

| D-V3-P1 rationale | Status under single-POST |
|---|---|
| `Last-Event-ID` resumption needs run id before reconnect | Resumption is not part of the middleware protocol; reconnect = new run. Dropped. |
| Telemetry attaches run id to spans before first frame | Run id does not exist before the first frame; spans attach on `RUN_STARTED`. |
| UI shows "running" immediately | The UI renders its `connecting` phase from the moment of send; no port support needed. |

### What is preserved

- Yields `UIRuntimeEvent` (post-translation), never raw `AGUIEvent` or
  an SDK type (**F-R8**, **A4**) — unchanged from D-V3-P1.
- Runtime Contract §1: the iterable always terminates with
  `run_completed` or `run_error`; if the underlying stream ends without
  a terminal event, the composition-root stream synthesizes
  `run_error{network_error}`.
- `trace_id` forwarded verbatim from the backend on every event
  (**F-R7**); browser-side transport reads the stream via
  `fetch` + `ReadableStream` (`lib/transport/fetch_sse_client.ts`),
  never `EventSource`.
- The browser-bundle wiring lives in the `lib/composition_browser.ts`
  composition root (keeps server-only SDK adapters out of the client
  bundle); `lib/composition.ts` remains the server-side root.

---

## D-V3-P2 — `AuthProvider`: remove `signIn()`; return `IdentityClaim` from `getSession()`

### Spec (per deep-dive §4.2)

```typescript
interface AuthProvider {
  getSession(): Promise<Session | null>;
  getAccessToken(): Promise<string>;
  signIn(options?: SignInOptions): Promise<void>;
  signOut(): Promise<void>;
}
```

### Implemented (canonical)

```typescript
interface AuthProvider {
  getSession(): Promise<IdentityClaim | null>;
  getAccessToken(): Promise<string>;
  signOut(): Promise<void>;
}
```

### Delta

| Change | Rationale |
|--------|-----------|
| `signIn()` removed | WorkOS AuthKit (the V3 implementation) and Next.js 15 are both redirect-based: sign-in is initiated by navigating to `/api/auth/sign-in`. The `<a href="/api/auth/sign-in">` pattern in `app/page.tsx` is the idiomatic Next 15 + WorkOS flow. An imperative port method that wraps `window.location.assign(...)` would be a leaky abstraction over a redirect, and would also make the port stateful (server-side routes have no `window`). Future non-redirect adapters (e.g. modal-based) can reintroduce `signIn()` without breaking the existing redirect adapter — the methods would be added with default-noop implementations. |
| `Session` → `IdentityClaim` in `getSession()` return | The deep-dive's `Session` shape included `access_token` and `expires_at`. Returning the access token through a structured port surface makes accidental logging much easier (one careless `JSON.stringify(session)` and the bearer is in a Cloud Logging line). `IdentityClaim` is from `trust-view/identity.ts` and exposes only `{ sub, org_id, roles, email }` — exactly what UI needs to render. The access token is only ever returned via the dedicated `getAccessToken()` method, which the React tree never invokes directly (only the BFF auth-forwarder does). This is a **stricter** trust boundary than the original spec. |

### Cross-port interaction unchanged

`AgentRuntimeClient` still calls `AuthProvider.getAccessToken()` to
attach the bearer token to each run request. The deep-dive's
"`AgentAuthError → triggers AuthProvider.signIn() flow`" note now reads
"`AgentAuthError → return 401 to BFF, which redirects to /api/auth/sign-in`"
— the user-facing behavior is identical.

### Storage policy unchanged

JWTs **never** land in `localStorage`/`sessionStorage` (FE-AP-18
**AUTO-REJECT**). The HttpOnly + Secure + SameSite=Strict cookie set by
the WorkOS Next.js middleware remains the only storage surface.

---

## D-V3-P3 — `ThreadStore`: identity-scoped methods; semantic `rename`/`get`; defer `update`/`delete`/`getMessages`

### Spec (per deep-dive §4.3)

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

### Implemented (canonical)

```typescript
interface ThreadStore {
  create(identity: IdentityClaim, req: ThreadCreateRequest): Promise<ThreadState>;
  get(identity: IdentityClaim, threadId: string): Promise<ThreadState | null>;
  list(identity: IdentityClaim, options?: { cursor?: string | null; limit?: number }): Promise<ThreadListPage>;
  rename(identity: IdentityClaim, threadId: string, newTitle: string): Promise<ThreadState>;
  archive(identity: IdentityClaim, threadId: string): Promise<void>;
}
```

### Delta

| Change | Rationale |
|--------|-----------|
| Every method now takes `identity: IdentityClaim` as the first parameter | Defense in depth. Even if a Route Handler forgets to call `await auth.getSession()`, the store still filters to the caller's `sub`. The port surface itself enforces ownership — there is no "admin god mode" code path possible. This raises the bar for accidental cross-user data leaks from "Route Handler must remember to authenticate" to "an attacker would have to forge an `IdentityClaim` Zod-valid value", which is much harder. |
| `get()` added | Thread-state rehydration on initial page load. Replaces the spec's `AgentRuntimeClient.getState()` (see D-V3-P1) at the correct port. |
| `update()` → `rename()` | The only field UI mutates is the title. A generic `update(id, patch)` invites schema drift (any patch shape becomes valid TypeScript). A specialized `rename(identity, threadId, newTitle)` keeps the surface narrow and the validation explicit. Future per-field operations (e.g. `setMetadata`) follow the same one-method-per-mutation pattern. |
| `delete()` removed | The deep-dive's behavioral contract says `delete()` "performs a soft delete (sets `archived_at`...)" — which is **exactly what `archive()` does**. Having both methods with identical semantics is a footgun (the wrong one will get called eventually). The implementation collapses them into the single `archive()` method. Hard delete is intentionally not exposed; LangGraph checkpoint cleanup is operations-only. |
| `getMessages()` removed | `ThreadState.messages` is part of the row returned by `get()` and `list()`. This is correct for v1: messages live in the same Postgres row as the thread metadata (Drizzle JSON column). If/when message volume justifies a separate `messages` table with cursor-based pagination, `getMessages(identity, threadId, opts)` will be added — but only then. **YAGNI** for v1. |
| Spec used `Thread` / `ThreadPatch`; impl uses `ThreadState` / `ThreadCreateRequest` | The wire schemas already define `ThreadState` (read shape) and `ThreadCreateRequest` (write shape) — distinct types per W7. The spec's `Thread` was a placeholder; the implementation uses the real wire shapes. |
| `list()` returns `ThreadListPage` instead of `Thread[]` | Cursor-based pagination from day one (the spec's behavioral contract already required it; the implementation surfaces it in the type system). |

### Existence-oracle prevention preserved

`get()` returns `null` for both "not found" and "not the owner" so the
URL space cannot be used to discover other users' thread IDs. This was
not in the original spec but is documented as part of the port contract
in the implementation (`ports/thread_store.ts` JSDoc) and tested in
`neon_free_thread_store.test.ts`.

---

## Summary table

| Port | Status vs spec | Methods preserved | Methods removed | Methods added |
|------|----------------|-------------------|-----------------|---------------|
| `AgentRuntimeClient` | refined (R1 2026-06-11) | `cancel` | `stream`, `getState`, `createRun` (added then removed by R1) | `streamRun(req)` |
| `AuthProvider` | refined | `getAccessToken`, `signOut` | `signIn` | — (redirect-based flow replaces it) |
| `AuthProvider.getSession` return type | tightened | — | `Session` | `IdentityClaim` (stricter; no token leak) |
| `ThreadStore` | refined + scoped | `create`, `list`, `archive` | `update`, `delete`, `getMessages` | `get`, `rename` (and identity scoping on every method) |
| `MemoryClient` | matches spec | all | — | — |
| `TelemetrySink` | matches spec | all | — | — |
| `FeatureFlagProvider` | matches spec | all | — | — |
| `ToolRendererRegistry` | matches spec | all | — | — |
| `UIRuntime` | matches spec | all | — | — |

---

## When (if ever) the spec re-becomes canonical

A future deviation note may revisit these decisions if any of the
following triggers hit:

| Trigger | Re-add | Likely deviation reversal |
|---------|--------|---------------------------|
| Message volume per thread > ~100 messages typical | `ThreadStore.getMessages(identity, threadId, opts)` | Yes — split messages from thread row |
| Non-redirect auth UX (e.g. embedded modal) | `AuthProvider.signIn(options?)` with default-noop on redirect adapters | Partial — additive only |
| Generic thread metadata UI (tags, custom fields) | `ThreadStore.update(identity, threadId, patch)` with Zod-validated patch | Possible — but `setMetadata` / `setTags` per-concern preferred |
| Hard-delete required for legal compliance (GDPR right-to-erasure) | `ThreadStore.purge(identity, threadId)` (note: not `delete`) | Yes — additive, never replacing `archive` |

The identity-scoped `ThreadStore` methods are **not** scheduled for
reversal under any foreseen trigger. The `createRun` + `streamRun`
split **was** reversed (D-V3-P1-R1, 2026-06-11) once the live
middleware protocol showed run creation and streaming are one POST; a
future deviation could reintroduce a two-step flow only if the
middleware grows a separate run-creation endpoint (e.g. for
`Last-Event-ID` resumption).

---

## See also

- [`FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md`](./FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) — the original spec; reads as Sprint 0 source-of-truth for the unchanged ports
- [`FRONTEND_ARCHITECTURE.md`](./FRONTEND_ARCHITECTURE.md) — frontend ring big-picture (F-R1..F-R9 invariants)
- `frontend/lib/ports/*.ts` — live port interfaces (canonical)
- `frontend/lib/adapters/<family>/README.md` — per-family swap triggers and SDK pins
- `frontend/tests/architecture/test_port_conformance.test.ts` — structural rules enforced for every port (P1, P2, P3, P5, P6, P7)
