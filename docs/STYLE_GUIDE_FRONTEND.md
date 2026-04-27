# Style Guide: Frontend Ring for Agentic Systems

A prescriptive style guide for the cross-process Frontend Ring that sits above `agent_ui_adapter/` and the four-layer backend. Codifies the layering rules, design patterns, tech-stack picks, and code-review checklists for the Next.js 15 + React 19 + CopilotKit v2 + AG-UI + Zod + Tailwind v4/shadcn + WorkOS + LangGraph SDK stack used by the V2-Frontier and V3-Dev-Tier substrate profiles.

**Related documents:**

- [STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md) -- backend four-layer style guide that this mirrors
- [STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md) -- backend pattern catalog (H1-H7, V1-V6) that the W/P/A/T/X/U/C/S/O families here mirror
- [Architectures/FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) -- big-picture spec for the Frontend Ring
- [Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) -- exhaustive per-port spec
- [Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md) -- wire kernels, translators, transport
- [plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md](plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md) -- V2-Frontier substrate profile
- [plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md](plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md) -- V3-Dev-Tier substrate profile
- [`frontend/lib/README.md`](../frontend/lib/README.md) -- sealed-envelope rule

---

## Table of Contents

- [0. How to Use This Guide](#0-how-to-use-this-guide)
- [1. Core Principle: Three Composition Roots, Five Sub-Packages per Process](#1-core-principle-three-composition-roots-five-sub-packages-per-process)
- [2. Tech-Stack Prescriptions](#2-tech-stack-prescriptions)
- [3. The Two TypeScript Shared Kernels](#3-the-two-typescript-shared-kernels)
- [4. Ports Layer](#4-ports-layer)
- [5. Adapters Layer](#5-adapters-layer)
- [6. Translators Layer](#6-translators-layer)
- [7. Transport Layer](#7-transport-layer)
- [8. Composition Roots](#8-composition-roots)
- [9. Browser Process Model](#9-browser-process-model)
- [10. Cross-Process Boundary Rules](#10-cross-process-boundary-rules)
- [11. Frontend Invariants F-R1 through F-R9](#11-frontend-invariants-f-r1-through-f-r9)
- [12. Frontend Patterns Catalog](#12-frontend-patterns-catalog)
- [13. UI Component Conventions](#13-ui-component-conventions)
- [14. State Management Rules](#14-state-management-rules)
- [15. Generative UI and Sandboxing](#15-generative-ui-and-sandboxing)
- [16. Authentication, Authorization, Trust Propagation](#16-authentication-authorization-trust-propagation)
- [17. Observability and Logging](#17-observability-and-logging)
- [18. Performance and Streaming](#18-performance-and-streaming)
- [19. Security Hardening](#19-security-hardening)
- [20. Testing Strategy](#20-testing-strategy)
- [21. Build, Tooling, CI Conventions](#21-build-tooling-ci-conventions)
- [22. Anti-Patterns](#22-anti-patterns)
- [23. Code Review Checklists](#23-code-review-checklists)
- [24. Substrate Swap Procedure](#24-substrate-swap-procedure)
- [25. Recipes](#25-recipes)
- [26. Directory Structure Convention](#26-directory-structure-convention)
- [27. Glossary](#27-glossary)
- [28. Related Documents](#28-related-documents)

---

## 0. How to Use This Guide

**Audience.** Frontend engineers, code reviewers, and security reviewers working on `frontend/`, `middleware/`, or any future cross-process ring. Reviewers paste the checklists in §23 directly into PR review comments.

**What this guide enforces.** Three things, in priority order:

1. **Dependency direction.** Every arrow points inward toward the two TypeScript shared kernels (`wire/` and `trust-view/`). No layer imports from a layer above it.
2. **SDK isolation.** Third-party SDKs (CopilotKit, WorkOS, LangGraph SDK, Mem0, Langfuse, Drizzle, `@neondatabase/serverless`) appear only inside `frontend/lib/adapters/` or `middleware/adapters/`. They never leak into `ports/`, `wire/`, `trust-view/`, `translators/`, `transport/`, or any UI component.
3. **Trust propagation.** `trace_id` originates in the Python runtime adapter and flows verbatim through every layer. The browser never generates one.

**Relationship to other docs.**

| Document | Purpose | This guide's relationship |
|----------|---------|---------------------------|
| [STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md) | Backend four-layer style guide | Mirror -- the F/W/P/A/T/X/C/B/U/S/O rule families here are the frontend-ring counterparts of the backend's H/V rules |
| [STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md) | Backend pattern catalog | Mirror -- §12 of this guide is the frontend pattern catalog |
| [Architectures/FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) | Frontend ring big-picture spec | Source of truth for the architecture; this guide turns it into reviewable rules |
| [Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) | Per-port deep dive | Source of truth for individual port contracts; this guide enforces conventions across them |
| [Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md) | Wire/translator/transport deep dive | Source of truth for the kernels; this guide constrains how consumers use them |

**Code-review intent.** Every numbered rule (`Rule F1`, `Rule W3`, `Rule A5`, ...) maps to a one-line PR review comment template. A reviewer who sees a violation can write `Violates Rule A5 (error translation table)` and link here. Every anti-pattern in §22 has a stable ID (`FE-AP-7`) for the same purpose.

**Prescriptive tone.** This guide picks one library or pattern per concern and bans alternatives (§2). Adopting an alternative requires a merged Architecture Decision Record (ADR) under `docs/adr/` -- never a PR comment debate.

---

## 1. Core Principle: Three Composition Roots, Five Sub-Packages per Process

The Frontend Ring is a hexagonal outer ring that crosses process boundaries. It is composed of three sub-rings (browser+BFF, middleware, `agent_ui_adapter`), and each sub-ring mirrors the same five sub-package shape used by `agent_ui_adapter/` on the Python side: `ports/`, `adapters/`, `wire/`, `translators/`, `transport/`. The structural symmetry means a reviewer who knows the backend adapter ring can navigate the frontend ring without learning a new vocabulary.

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  COMPOSITION ROOTS (one per process; only place that names adapters) │
  │    frontend/lib/composition.ts    middleware/composition.py          │
  │    agent_ui_adapter/server.py                                        │
  └─────────────────────────────────┬────────────────────────────────────┘
                                    │
  ┌─────────────────────────────────┴────────────────────────────────────┐
  │  ADAPTERS (the only SDK boundary in the entire ring)                 │
  │    frontend/lib/adapters/    middleware/adapters/                    │
  └─────────────────────────────────┬────────────────────────────────────┘
                                    │
  ┌─────────────────────────────────┴────────────────────────────────────┐
  │  PORTS (interface definitions: TS interfaces / Python Protocols)     │
  │    frontend/lib/ports/    middleware/ports/                          │
  └─────────────────────────────────┬────────────────────────────────────┘
                                    │
  ┌─────────────────────────────────┴────────────────────────────────────┐
  │  TRANSLATORS (pure functions; no I/O, no React, no SDK)              │
  │    frontend/lib/translators/    middleware/translators/              │
  └─────────────────────────────────┬────────────────────────────────────┘
                                    │
  ┌─────────────────────────────────┴────────────────────────────────────┐
  │  TRANSPORT (SSE encode/decode, BFF proxy)                            │
  │    frontend/lib/transport/    middleware/transport/                  │
  └─────────────────────────────────┬────────────────────────────────────┘
                                    │
  ════════════════════════════════════════════════════════════════════════
                                    │
  ┌─────────────────────────────────┴────────────────────────────────────┐
  │  SHARED KERNELS (innermost; zero outward dependencies)               │
  │    frontend/lib/wire/      mirrors agent_ui_adapter/wire/            │
  │    frontend/lib/trust-view/  read-only TS view of trust/             │
  └──────────────────────────────────────────────────────────────────────┘
```

The double line at the bottom mirrors the separator the backend [STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md) uses between the trust foundation and the layers above. `wire/` and `trust-view/` are to the frontend ring what `trust/` is to the backend: the most stable artifact, depended on by every layer above, depending on nothing.

### Rules

**Rule F1: Three composition roots, no fourth.**
Substrate-selection logic (any read of `ARCHITECTURE_PROFILE` or its Python equivalent) may live only in `frontend/lib/composition.ts`, `middleware/composition.py`, or `agent_ui_adapter/server.py`. Any other file that branches on `process.env.ARCHITECTURE_PROFILE` (or `os.environ["ARCHITECTURE_PROFILE"]`) fails review.

**Rule F2: Five sub-packages per process, no sixth.**
A new top-level directory under `frontend/lib/` or `middleware/` requires either (a) merging into an existing sub-package, or (b) a merged ADR. The eight ports (per [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §"The Five Sub-Packages") cap the surface area. Growing the ring sideways is the wrong axis to grow.

**Rule F3: Substrate swaps are composition-root-only.**
V2-Frontier and V3-Dev-Tier are the same architecture with different adapters wired at the composition root. A substrate swap (Neon → Cloud SQL, Mem0 Cloud → self-hosted, Langfuse Cloud → self-hosted) must touch exactly two files: one new adapter under `adapters/<family>/`, and one selector update in `composition.ts` / `composition.py`. No other file may change. This is the acceptance test for whether your abstraction is correct -- if you find yourself touching `wire/`, `translators/`, `transport/`, or any UI component, the abstraction is wrong.

**Rule F4: The frontend ring never imports backend Python at module scope.**
The process boundary is crossed only via HTTP/SSE through the `AgentRuntimeClient` port interface. `frontend/` is TypeScript; `middleware/` may import from `trust/` and `agent_ui_adapter/wire/` for shared shapes only -- never from `services/`, `components/`, `orchestration/`, or `governance/`.

**Enforcement:** `tests/architecture/test_frontend_layering.ts` and `tests/architecture/test_middleware_layering.py` (described in [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §"Architecture Test Plan") walk the import graph and fail on violations.

---

## 2. Tech-Stack Prescriptions

This is the canonical list. Every rule, example, and anti-pattern in this document references exactly these picks. Adding a new category requires updating this table in the same PR. Replacing a row requires a merged ADR.

| Concern | Prescribed | Banned alternatives |
|---------|-----------|---------------------|
| Framework | Next.js 15 App Router | Pages Router, Remix, Vite + React Router |
| React | React 19 (use `useActionState`, await `params` / `cookies` / `headers`) | React 18 patterns (`useFormState`, sync `params`) |
| Language | TypeScript 5.x with `"strict": true`, `"noUncheckedIndexedAccess": true`, `"exactOptionalPropertyTypes": true`, `"verbatimModuleSyntax": true` | JavaScript files in `frontend/lib/` |
| Schema validation | Zod (`z.discriminatedUnion`, `safeParse` at boundaries, `parse` on already-trusted data) | Yup, io-ts, Joi, hand-written validators, JSON Schema codegen for `wire/` |
| Styling | Tailwind CSS v4 (CSS-first `@theme`) + shadcn/ui (source-owned under `components/ui/`) + `cn()` (`clsx` + `tailwind-merge`) | CSS Modules, styled-components, emotion, MUI, Chakra, JS-based Tailwind config |
| Theme switching | `next-themes` + `[data-theme="dark"]` CSS variable overrides | `useState` toggles, class-only `dark:` |
| Icons | `lucide-react` (the shadcn default) | `heroicons`, `react-icons`, custom SVG sets |
| Markdown | `react-markdown` + `shiki` | `marked`, `markdown-it`, `prism-react-renderer` |
| Date/time | native `Intl.DateTimeFormat` + ISO 8601 strings on the wire | `moment`, `dayjs`, `date-fns` |
| Chat UI runtime | CopilotKit v2 (`@copilotkit/react-core`, `@copilotkit/react-ui`) wrapped behind `UIRuntime` port | direct CopilotKit imports outside `frontend/lib/adapters/ui_runtime/` |
| Generative UI | `useFrontendTool` (static) + `useComponent` rendered into `<iframe sandbox="allow-scripts">` only | `dangerouslySetInnerHTML`, unsandboxed iframe, `allow-same-origin`, `allow-top-navigation`, `allow-forms`, `eval` |
| Auth | WorkOS AuthKit (`@workos-inc/authkit-nextjs`) wrapped behind `AuthProvider` port | NextAuth, Clerk, Auth0 SDK imports outside `adapters/auth/` |
| Agent runtime client | LangGraph SDK (`@langchain/langgraph-sdk`) wrapped behind `AgentRuntimeClient` port | direct `fetch` to LangGraph URLs from components |
| Thread storage | Drizzle ORM (`drizzle-orm`) over `@neondatabase/serverless` (V3) / Cloud SQL (V2), wrapped behind `ThreadStore` port | Prisma, Kysely, raw `pg` outside `adapters/thread_store/` |
| Memory | `mem0ai` SDK wrapped behind `MemoryClient` port (middleware-side only -- F-R9) | direct Mem0 SDK calls in BFF Route Handlers |
| Observability | Langfuse Python SDK in middleware + browser-side `TelemetrySink` for RUM only | Sentry, Datadog browser SDK, `console.*` outside `adapters/` |
| Feature flags | `EnvVarFlagsAdapter` reading `NEXT_PUBLIC_FF_*` (synchronous) | LaunchDarkly, Unleash, async flag fetches |
| HTTP fetching (server) | global `fetch` (Next.js-extended) inside Route Handlers | `axios`, `got`, `node-fetch` |
| HTTP fetching (client) | `fetch` wrapped in adapter; `EventSource` only inside `transport/sse_client.ts` | TanStack Query for SSE, `axios`, raw `XMLHttpRequest` |
| State management | RSC + Server Actions; `useState` / `useReducer` for transient UI only | Redux, Zustand, Jotai, MobX (require ADR per use) |
| Logging | per-namespace logger (`frontend:adapter:*` browser, `middleware.adapters.*` Python via `logging.json`) | `console.*` outside `adapters/` |
| Testing -- unit | Vitest + React Testing Library | Jest, Enzyme |
| Testing -- e2e | Playwright + `@axe-core/playwright` | Cypress, Puppeteer |
| Testing -- visual | Storybook stories per generative-UI component | Chromatic optional |
| Testing -- architecture | `ts-morph` import-graph walker (`tests/architecture/test_frontend_layering.ts`) | `eslint-plugin-import` rules alone |
| Testing -- accessibility | `@axe-core/react` (dev) + `eslint-plugin-jsx-a11y` (CI) | manual-only audits |
| Wire codegen | hand-authored Zod + Python JSON Schema baseline diff (per [FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md) §"Wire-Schema Drift Detection") | `openapi-typescript`, `datamodel-code-generator` for `wire/` |
| Package manager | pnpm | npm, yarn, bun |
| Node runtime | Node 20 LTS for Route Handlers; Edge runtime allowed only for `transport/edge_proxy.ts` | Node ≤18, runtime auto-detect |

---

## 3. The Two TypeScript Shared Kernels

`frontend/lib/wire/` and `frontend/lib/trust-view/` are the innermost rings of the browser+BFF sub-ring. They play the role that `trust/` plays on the Python side: the most stable kernels, with zero outward dependencies, imported by everything above.

### What belongs in `wire/`

A module belongs in `wire/` if it satisfies **all** of these criteria:

1. **Pure data shape.** Zod schema + `z.infer<typeof Schema>` type. No functions with side effects.
2. **Mirrors a Python `agent_ui_adapter/wire/` module**, OR is the frontend-only `ui_runtime_events.ts`.
3. **Imports only `zod` and stdlib.** No React, no `EventSource`, no `fetch`, no third-party SDK.

### What belongs in `trust-view/`

A module belongs in `trust-view/` if it satisfies **all** of these criteria:

1. **Read-only view of a `trust/` model.** No mutation methods, no signing, no verification.
2. **Subset, not superset.** It exposes only the fields the UI legitimately needs to render. New fields require an explicit additive decision; never copy `trust/models.py` wholesale.
3. **Imports only `zod` and stdlib.** Same constraint as `wire/`.

### Rules

**Rule W1: Pure shapes only.**
`wire/` and `trust-view/` contain no I/O, no logging, no SDK calls. A function that accepts and returns wire shapes belongs in `translators/`, not in `wire/`.

**Rule W2: Mirror the Python source of truth.**
For every module in `agent_ui_adapter/wire/`, there is exactly one matching module in `frontend/lib/wire/` (with `.py` → `.ts`). Field names use snake_case to match the Python side verbatim. Drift between the two sides is detected by the `__python_schema_baseline__.json` snapshot diff; see [FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md) §"Wire-Schema Drift Detection".

**Rule W3: Discriminated unions, not bare unions.**
Multi-variant wire types (`DomainEvent`, `AGUIEvent`) use `z.discriminatedUnion("type", […])` with `z.literal(...)` discriminators. This guarantees Zod skips invalid branches in O(1) and lets TypeScript narrow types automatically inside `switch` statements on the consumer side.

```typescript
// frontend/lib/wire/ag_ui_events.ts -- correct
export const AGUIEvent = z.discriminatedUnion("type", [
  RunStartedEvent,    // type: z.literal("run.started")
  TokenEvent,         // type: z.literal("token")
  ToolStartEvent,     // type: z.literal("tool.start")
  // ... other variants
]);
```

**Rule W4: Sealed envelopes are read-only.**
Any payload carrying a cryptographic signature (`AgentFacts`, `TrustTraceRecord`, `PolicyDecision`, anything with a `signature_hash` or `signed_metadata` field) is typed `Readonly<...>`. Never spread (`{...envelope}`), never re-serialize, never add convenience properties. Echo the original bytes. Full rule in [`frontend/lib/README.md`](../frontend/lib/README.md).

**Rule W5: `trace_id` is a structural requirement.**
Every event schema in `wire/domain_events.ts` and `wire/ag_ui_events.ts` extends a `BaseEvent` that declares `trace_id: z.string()` as required. A new event schema that omits `trace_id` fails review. This is how invariant F-R7 (trace propagation) is enforced at the type level.

**Rule W6: snake_case on the wire; camelCase only after a translator.**
Wire shapes use snake_case (`tool_call_id`, `run_id`, `trace_id`, `started_at`) to match Python. If a downstream UI consumer needs camelCase, the conversion happens in a translator -- never inline at the boundary. This keeps the schema-drift detector single-key-per-shape simple.

**Rule W7: `Schema` const + `Type` co-export.**
Every schema file exports both the runtime const and the inferred type with the same name:

```typescript
// frontend/lib/wire/agent_protocol.ts
export const RunCreateRequest = z.object({...});
export type RunCreateRequest = z.infer<typeof RunCreateRequest>;
```

Consumers can `import { RunCreateRequest }` once and use it as both the validator and the type.

**Rule W8: `trust-view/` exports only `z.infer<...>` types.**
No functions, no classes, no mutable state. The TypeScript compiler is the enforcement mechanism for invariant F-R6 (`trust-view/` is read-only). Anything that isn't a Zod schema or its inferred type belongs in a translator or an adapter.

### Anti-Patterns

**Anti-Pattern: snake-case to camelCase conversion at the wire boundary.**
```typescript
// BAD -- converting on receive
const evt = { runId: raw.run_id, traceId: raw.trace_id };
```
This breaks the schema-drift detector and creates two parallel naming worlds. Pass snake_case through `wire/` unchanged; only convert in the `translators/` layer if a downstream consumer needs camelCase.

**Anti-Pattern: importing CopilotKit message types into `wire/`.**
```typescript
// BAD
import type { Message } from "@copilotkit/react-core";
export const ChatPayload = z.object({ messages: z.array(Message) });
```
The kernel must not depend on a third-party SDK. If CopilotKit changes the `Message` shape, every `wire/` consumer breaks. Define `Message` locally in `wire/ui_runtime_events.ts`; let the adapter convert from CopilotKit's shape to ours.

**Anti-Pattern: spreading a sealed envelope.**
```typescript
// BAD
const updated = { ...agentFacts, status: "active" };
```
Spreading reorders keys and invalidates the signature. The trust gate will reject the request at the boundary. Read fields, never mutate; echo the original JSON bytes when forwarding.

---

## 4. Ports Layer

A port is a TypeScript interface (`frontend/lib/ports/`) or a Python `@runtime_checkable` Protocol (`middleware/ports/`) that defines the contract between the application core and an external dependency family.

### What belongs in `ports/`

A module belongs in `ports/` if it satisfies **all** of these criteria:

1. **Single interface.** Exactly one TypeScript interface or Python Protocol per file (rule F-R3 in [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §11).
2. **Names a capability, not a vendor.** `MemoryClient`, not `Mem0Client`. `AgentRuntimeClient`, not `LangGraphClient`. The vendor name lives in the adapter file name only.
3. **Method signatures use `wire/` types only.** No SDK types in any parameter or return type.
4. **At least one or a planned second concrete implementation exists.** A port with one implementation forever is over-abstraction; instantiate the adapter directly in the composition root and skip the port (abstraction-introduction principle from [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §"Phase Progression").

### Rules

**Rule P1: One interface per file.**
Each file under `frontend/lib/ports/` defines exactly one `interface`. A file that exports two interfaces fails review. This rule prevents ports from accreting into domain models.

**Rule P2: Vendor-neutral name.**
Port names describe the capability (`AgentRuntimeClient`, `AuthProvider`, `ThreadStore`, `MemoryClient`, `TelemetrySink`, `FeatureFlagProvider`, `ToolRendererRegistry`, `UIRuntime`). They never contain a vendor name. The vendor is encoded in the adapter file name (`workos_authkit_adapter.ts`, `mem0_cloud_hobby_adapter.ts`).

**Rule P3: Behavioral contract in JSDoc.**
The interface signature alone is not the full contract. Document the behavioral rules per port (the canonical list per port lives in [FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) §"The Eight Driven Ports") in JSDoc above the interface, then assert them in `frontend/tests/architecture/test_port_conformance.ts`.

```typescript
// frontend/lib/ports/agent_runtime_client.ts
import type { AGUIEvent, RunCreateRequest, ThreadState } from "../wire/agent_protocol";

/**
 * Streams AG-UI events for an agent run.
 *
 * Behavioral contract:
 *   1. The last event yielded must be RunCompletedEvent or RunErrorEvent.
 *   2. Every event must carry the same trace_id (forwarded from the Python runtime).
 *   3. cancel() must be idempotent.
 *   4. No SDK type may appear in any return value.
 *   5. On dropped SSE connection, attempt Last-Event-ID reconnect before surfacing error.
 *
 * @throws AgentAuthError on 401
 * @throws AgentAuthorizationError on 403
 * @throws AgentRateLimitError on 429
 * @throws AgentServerError on 5xx
 * @throws AgentNetworkError on persistent network failure
 */
export interface AgentRuntimeClient {
  stream(req: RunCreateRequest): AsyncIterable<AGUIEvent>;
  cancel(runId: string): Promise<void>;
  getState(threadId: string): Promise<ThreadState>;
}
```

**Rule P4: Typed errors.**
A port method that can fail declares a typed error class (`AgentAuthError`, `ThreadStoreError`, `MemoryError`) and lists it in the JSDoc `@throws`. Adapters translate raw HTTP / SDK errors to these typed errors; consumers `catch` on type, not on string matching.

**Rule P5: Async by default; synchronous only with documented justification.**
Browser-side ports return `Promise<T>` or `AsyncIterable<T>` unless there is a structural reason to be synchronous. The canonical exception is `FeatureFlagProvider.isEnabled()`, which is read at render time and must not trigger React re-renders -- this synchronicity is documented in the JSDoc and in the corresponding pattern in §12.

**Rule P6: No imports from `adapters/`, `translators/`, `transport/`, or `composition.ts`.**
The dependency arrow always points toward the kernels. A port file that imports an adapter is inverted. Symptom of violation: the port refers to a class name that ends in `Adapter` or `Client`.

**Rule P7: Ports come paired with a conformance test.**
A port is not "done" until `frontend/tests/architecture/test_port_conformance.ts` parametrizes the structural and behavioral conformance tests over its concrete adapters. A port without a conformance test is a candidate for deletion.

### Anti-Patterns

**Anti-Pattern: Combined `AuthAndMemoryProvider`.**
```typescript
// BAD
export interface AuthAndMemoryProvider {
  getSession(): Promise<Session>;
  searchMemories(q: string): Promise<MemoryResult[]>;
}
```
Two ports masquerading as one. Adapters cannot be swapped independently; testing requires mocking twice the surface. Split into `AuthProvider` and `MemoryClient`.

**Anti-Pattern: Returning a CopilotKit `Message` array.**
```typescript
// BAD
import type { Message } from "@copilotkit/react-core";
export interface UIRuntime {
  useMessages(): Message[];
}
```
SDK leak through the port. When CopilotKit is swapped for `assistant-ui`, every consumer breaks. Define `MessageState` in `wire/ui_runtime_events.ts` and convert inside the adapter.

---

## 5. Adapters Layer

Adapters are the **driven (right-hand) side** of the hexagon. Every concrete SDK call (CopilotKit, LangGraph SDK, WorkOS AuthKit, Mem0, Langfuse, Neon, Drizzle, Cloud SQL client, Cloudflare runtime APIs) lives here. Adapters are the **only** place in the ring where `import "@copilotkit/..."` (or any other SDK import) is permitted.

### What belongs in `adapters/`

1. **Implements exactly one port.** `WorkOSAuthKitAdapter` implements `AuthProvider`, nothing else.
2. **One file = one adapter family member.** `frontend/lib/adapters/runtime/self_hosted_langgraph_dev_client.ts` contains exactly `SelfHostedLangGraphDevClient`. Helper utilities used only by that adapter live in the same file or a co-located private file under `adapters/runtime/_helpers/`.
3. **All SDK type → wire shape conversion happens here.** A `WorkOSSession` becomes a `Session` inside the adapter, never outside it.

### Rules

**Rule A1: SDK imports are permitted only here.**
The architecture test `tests/architecture/test_frontend_layering.ts` walks the import graph and fails if any file outside `frontend/lib/adapters/` (or `middleware/adapters/`) imports a package listed in `THIRD_PARTY_SDK_PACKAGES`. The list is centralized in the test config so reviewers inherit the same enforcement automatically.

**Rule A2: Adapters do not import each other.**
`runtime/self_hosted_langgraph_dev_client.ts` may not import from `auth/workos_authkit_adapter.ts`. Cross-adapter dependencies are injected through the composition root as port instances. Symptom of violation: an adapter constructor argument typed as another concrete class instead of a port interface.

**Rule A3: Adapters depend on `ports/`, `wire/`, `trust-view/`, and SDKs only.**
No imports from `translators/` (translators consume adapter output, not the other way around). No imports from `transport/` (transport is downstream of adapters). No imports from `composition.ts` (the composition root is the outermost layer; nothing inside imports it).

**Rule A4: SDK types never escape the adapter file.**
This rule is the architectural reason F-R8 exists. Inside the adapter file, you may handle `WorkOSSession`, `LangGraphRunResult`, `Mem0Memory`, etc. The moment a value is returned from a public adapter method, it must be a `wire/` shape or a TypeScript primitive. A PR review that finds an SDK type in an exported function signature blocks merge.

**Rule A5: Error translation table.**
Every adapter that performs network I/O documents an error translation table mapping HTTP statuses (or SDK exception types) to typed port errors. The table lives in JSDoc above the adapter class and is asserted by the conformance test bundle. Example for `SelfHostedLangGraphDevClient`:

| HTTP status | Thrown error type |
|---|---|
| 401 | `AgentAuthError` |
| 403 | `AgentAuthorizationError` |
| 429 | `AgentRateLimitError` (exponential backoff, max 3 attempts) |
| 5xx | `AgentServerError` |
| Network timeout | `AgentNetworkError` (triggers `Last-Event-ID` reconnect) |

**Rule A6: Idempotency on destructive operations.**
`cancel(runId)`, `delete(threadId)`, `deleteAll(userId)` must all be safe to call twice. The adapter swallows `404`-equivalent responses and returns success. Calling code never has to track "have I cancelled this already?" state.

**Rule A7: Per-family logger namespace.**
Each adapter family writes to its own logger namespace (`frontend:adapter:runtime`, `frontend:adapter:auth`, `middleware.adapters.memory`). Log messages omit access tokens, memory content, and LLM output text -- these are PII. Log entries include `trace_id`, `run_id`, `thread_id`, adapter name, and error type only. The full namespace registry is in [FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) §"Logging Convention".

**Rule A8: `middleware/adapters/` never module-imports `agent_ui_adapter/`.**
`middleware/adapters/` may not `import agent_ui_adapter` at module load. The middleware talks to the adapter ring via HTTP only. Importing `trust/` types is fine; importing services is not.

**Rule A9: SDK pin in JSDoc.**
Every adapter declares its SDK pin in a top-of-file JSDoc tag (`@sdk @langchain/langgraph-sdk ^0.0.x`). The architecture test reads this tag and cross-checks `package.json`. A PR that bumps an SDK version must update the JSDoc tag in the same commit.

**Rule A10: Per-family README.**
Every adapter family directory (`adapters/runtime/`, `adapters/auth/`, `adapters/thread_store/`, ...) contains a `README.md` listing: the port the family implements, the current concrete implementations, the swap trigger from V3 to V2 (per [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §"Substrate-Swap Matrix"), and any abstraction-introduction notes.

### Anti-Patterns

**Anti-Pattern: SDK type leak through return value.**
```typescript
// BAD
import type { CompletionRequestResult } from "@langchain/langgraph-sdk";
export class SelfHostedLangGraphDevClient implements AgentRuntimeClient {
  async stream(req: RunCreateRequest): AsyncIterable<CompletionRequestResult> { ... }
}
```
The return type contradicts the port. The compiler may accept this if the SDK type is structurally compatible, but every consumer now silently depends on the SDK shape. Convert to `AGUIEvent` inside the adapter.

**Anti-Pattern: Cross-adapter fetch.**
```typescript
// BAD
import { WorkOSAuthKitAdapter } from "../auth/workos_authkit_adapter";
class NeonFreeThreadStore implements ThreadStore {
  private auth = new WorkOSAuthKitAdapter();   // sibling adapter, instantiated locally
}
```
Construct adapters in the composition root and inject them as port instances:
```typescript
// GOOD
class NeonFreeThreadStore implements ThreadStore {
  constructor(private connectionString: string, private auth: AuthProvider) {}
}
```

**Anti-Pattern: Business logic in a Route Handler.**
```typescript
// BAD -- frontend/app/api/run/stream/route.ts
export async function POST(req: Request) {
  const body = await req.json();
  if (body.input.includes("delete")) {            // business logic in BFF
    return new Response("denied", { status: 403 });
  }
  return forwardSSEStream({...});
}
```
The Route Handler is a composition adapter. Business decisions belong in `services/` (Python) or the agent itself. Route Handlers contain only port calls and the byte-for-byte SSE forward.

---

## 6. Translators Layer

Translators map between wire shapes. They have no I/O, no side effects, no React, and no SDK imports. They are pure functions with deterministic behavior: given the same input, they always produce the same output.

### Rules

**Rule T1: Imports only `wire/` and `trust-view/`.**
A translator that imports from `adapters/`, `transport/`, `composition.ts`, or any third-party SDK fails review. The pure-function constraint is what makes translators trivial to test (no mocks needed).

**Rule T2: Forward `trace_id` from input to output.**
Every output shape carries the `trace_id` from the input event verbatim. This is how invariant F-R7 (trace propagation) is enforced at the function level. A translator output that drops `trace_id` fails the conformance test bundle.

```typescript
// frontend/lib/translators/tool_event_to_renderer_request.ts
export function toolStartToRequest(event: ToolStartEvent): ToolRendererRequest {
  return {
    type: "tool_renderer_request",
    tool_call_id: event.tool_call_id,
    tool_name: event.name,
    input: JSON.parse(event.input as string),
    trace_id: event.trace_id,    // forwarded verbatim
  };
}
```

**Rule T3: Zero-or-many output rule -- documented in JSDoc.**
A translator may produce 0, 1, or N output shapes for a single input. The expected count is documented in JSDoc. Example: `LLMMessageStarted` → 0 outputs (internal accounting); `RunStartedEvent` → 1 output; `StateMutated` (Phase 2) → 2 outputs (`StepEvent` + `model.switch`).

**Rule T4: Table-driven Vitest tests.**
Translator tests are pure input-to-output tables. No mocks needed. Every translator file ships with a co-located `*.test.ts` containing at minimum one test per discriminated-union variant the translator handles.

```typescript
// frontend/lib/translators/ag_ui_to_ui_runtime.test.ts
describe.each([
  ["RunStartedEvent",    runStartedFixture,    { type: "run_started", ... }],
  ["TokenEvent",         tokenFixture,         { type: "token", ... }],
  ["RunCompletedEvent",  runCompletedFixture,  { type: "run_completed", ... }],
  // ... one row per AGUIEvent variant
])("agUiToUiRuntime(%s)", (_name, input, expected) => {
  it("maps to expected UI shape with trace_id forwarded", () => {
    expect(agUiToUiRuntime(input)).toEqual(expected);
    expect(agUiToUiRuntime(input).traceId).toBe(input.trace_id);
  });
});
```

### Anti-Patterns

**Anti-Pattern: Translator that touches `localStorage` / `fetch` / `document`.**
```typescript
// BAD
export function withCachedMemory(input: ComposerInput): RunCreateRequest {
  const cached = localStorage.getItem("memory");   // I/O in a translator
  return { ...input, memory: cached };
}
```
Translators are pure. Move I/O into an adapter; pass the result as a translator parameter.

**Anti-Pattern: Dropping `trace_id`.**
```typescript
// BAD
export function toRunCreateRequest(input: ComposerInput): RunCreateRequest {
  return { thread_id: input.threadId, input: { messages: [...] } };
  // trace_id was on input, but is gone from output
}
```
Forward `trace_id` to every output shape. The conformance test catches this; reviewers should too.

---

## 7. Transport Layer

Transport modules handle network I/O for the SSE connection. They import from `wire/` only -- no SDK, no React, no auth logic.

### Rules

**Rule X1: `EventSource` only in `transport/sse_client.ts`.**
The browser's `EventSource` API may be referenced in exactly one file. All other SSE consumers obtain typed `AGUIEvent` values through the `sse_client.ts` API.

**Rule X2: Zod-parse on receive.**
Every received SSE `data:` frame is parsed against the `AGUIEvent` Zod schema before yielding. A Zod parse failure is caught, logged via `TelemetrySink`, and surfaced as a synthetic `RunErrorEvent` with `error_type: "wire_parse_error"` so the UI can show an error state without crashing. Use `safeParse`, not `parse`, at this boundary.

**Rule X3: `Last-Event-ID` resumption is non-optional.**
Every adapter built on `sse_client.ts` implements `Last-Event-ID` resumption. The server sends `id: <run_id>:<seq>` on every event; the client's `EventSource` automatically replays the header on reconnect.

**Rule X4: Heartbeat detection thresholds documented and matched to Python.**
The server sends `:\n\n` comment frames every 15s; the client detects absence after 30s and triggers reconnect. Both numbers are documented in JSDoc and must match `agent_ui_adapter/transport/heartbeat.py`.

**Rule X5: Backpressure: 100-event in-memory buffer; drop-oldest after that.**
If the consumer is processing events slower than they arrive, the client buffers up to 100 events and drops oldest events after that. Changing this number requires updating both the JSDoc and the user-facing release notes.

**Rule X6: BFF strips `Accept-Encoding` on streaming routes.**
`transport/edge_proxy.ts` forwards SSE byte-for-byte. The required response headers are:

| Header | Value | Why |
|---|---|---|
| `Content-Type` | `text/event-stream; charset=utf-8` | SSE MIME type |
| `Cache-Control` | `no-cache, no-transform` | Prevents edge caching and compression |
| `X-Accel-Buffering` | `no` | Disables nginx/Vercel upstream buffering |
| `Connection` | `keep-alive` | Keeps the connection open for streaming |
| `Transfer-Encoding` | (cleared) | Prevents chunked encoding confusion |

The `Accept-Encoding` request header is **stripped** before forwarding to the middleware on streaming routes. This prevents the Cloud Run origin from attempting gzip/brotli compression on an SSE stream, which causes 502 errors on some proxy configurations. These header invariants are tested by a Vitest snapshot.

### Anti-Patterns

**Anti-Pattern: `JSON.parse` without Zod validation.**
```typescript
// BAD
sse.onmessage = (e) => onEvent(JSON.parse(e.data));
```
Invalid wire payloads crash the consumer at use-site. Use `AGUIEvent.safeParse(JSON.parse(e.data))` and synthesize `RunErrorEvent` on failure.

**Anti-Pattern: gzip on streaming route.**
```typescript
// BAD
new Response(stream, { headers: { "Content-Encoding": "gzip" } });
```
Browsers buffer gzip-encoded SSE; first token never arrives. Strip `Accept-Encoding` upstream and send identity.

---

## 8. Composition Roots

The composition root is the **only** file that knows which concrete adapter implements each port. All other code receives adapters through the port interface only.

### Rules

**Rule C1: Single profile switch.**
Composition is the only place the string `ARCHITECTURE_PROFILE` (or its Python equivalent `os.environ["ARCHITECTURE_PROFILE"]`) appears. An architecture test asserts no other file branches on this value.

**Rule C2: Inject by port.**
Composition exports `buildAdapters()` returning a typed bag of port instances. Consumers receive the bag through React context (frontend) or constructor (middleware). No consumer ever imports a concrete adapter class name.

**Rule C3: React context provision.**
On the frontend, the composition root provides adapters via a single React context (e.g., `<AdapterProvider value={adapters}>`). Hooks `useAgentRuntime()`, `useAuth()`, `useThreadStore()` read the context. Components never import adapters directly.

**Rule C4: Env reads only in composition.**
All `process.env.*` reads for adapter configuration happen in `composition.ts`. Adapters receive plain strings/numbers via constructor. This makes adapters trivially testable -- pass fixtures, no env stubbing.

**Rule C5: Composition is the only consumer of `process.env.*` for adapter wiring.**
A lint rule (or architecture test) flags any `process.env.*` (or `os.environ` in Python) read outside `composition.ts` / `composition.py` that pertains to adapter selection. UI-level env reads (e.g., `NEXT_PUBLIC_FF_*` flag values) flow through `FeatureFlagProvider`, not direct env access.

```typescript
// frontend/lib/composition.ts -- correct
const profile = process.env.ARCHITECTURE_PROFILE ?? "v3";

export function buildAdapters() {
  const auth = new WorkOSAuthKitAdapter();
  const flags = new EnvVarFlagsAdapter();
  const toolRegistry = new CopilotKitRegistryAdapter();
  const uiRuntime = new CopilotKitUIRuntime();

  const runtime: AgentRuntimeClient =
    profile === "v2"
      ? new LangGraphPlatformSaaSClient({ ... })
      : new SelfHostedLangGraphDevClient({ ... });

  return { runtime, auth, flags, toolRegistry, uiRuntime };
}
```

The full TypeScript and Python skeletons are in [FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) §"Composition-Root Wiring Pattern".

### Anti-Patterns

**Anti-Pattern: env-var read inside an adapter.**
```typescript
// BAD
class NeonFreeThreadStore implements ThreadStore {
  private dsn = process.env.NEON_DATABASE_URL!;   // hidden coupling to env shape
}
```
Pass the connection string as a constructor argument. The composition root reads env; the adapter takes data.

**Anti-Pattern: profile conditional outside composition.**
```typescript
// BAD -- in a UI component
const url = process.env.ARCHITECTURE_PROFILE === "v2"
  ? "https://prod.example.com" : "http://localhost:3000";
```
Substrate decisions belong in composition. Components consume the runtime port; the URL is the adapter's concern.

---

## 9. Browser Process Model

Mental model: **Server Component by default; `'use client'` only at the leaf**.

### Rules

**Rule B1: New components default to RSC.**
Adding `'use client'` requires a comment explaining which client-only API is needed (event handler, hook, browser API). A reviewer who sees `'use client'` without a comment asks "why" before approving.

**Rule B2: Pass Server Components to Client Components as `children`.**
This keeps the children rendered on the server. Don't pass complex data props from server to client when you can pass JSX.

```tsx
// GOOD -- ServerSidebar stays on the server even though ChatShell is a client component
<ChatShell>
  <ServerSidebar />
</ChatShell>
```

**Rule B3: Await `params`, `searchParams`, `cookies()`, `headers()`.**
Next.js 15 makes these async. A synchronous read fails the build.

```tsx
// app/(chat)/[threadId]/page.tsx -- Next 15 / React 19
export default async function Page({ params }: { params: Promise<{ threadId: string }> }) {
  const { threadId } = await params;
  // ...
}
```

**Rule B4: Server Actions for UI-triggered mutations; Route Handlers for SSE / external consumers.**
Internal form submits use Server Actions (progressive enhancement, automatic cache revalidation). External-facing endpoints (SSE proxy, webhooks) use Route Handlers. Picking the wrong one is a code-review block.

**Rule B5: `cache: 'no-store'` is the new default.**
Next.js 15 defaults `fetch()` to `no-store`. Set `cache: 'force-cache'` or `next: { revalidate }` only when the data is genuinely cacheable AND not user-scoped. User-scoped data is never cached.

**Rule B6: Route Handlers are composition adapters (rule F-R4 from architecture).**
Route Handlers contain only port calls and the byte-for-byte SSE forward. No `if/else` business logic. No data transformation. Symptom of violation: a Route Handler with a non-trivial `if` branch that isn't a port call.

**Rule B7: Edge runtime opt-in only for `transport/edge_proxy.ts`.**
The `export const runtime = 'edge'` directive appears in exactly one file by default. Other Route Handlers use Node 20 LTS so server-only adapters (Drizzle, `@neondatabase/serverless` server pool) work without edge constraints.

```typescript
// frontend/app/api/run/stream/route.ts -- correct usage
export async function POST(req: Request) {
  const token = await getAccessToken();
  return forwardSSEStream({
    upstreamUrl: `${process.env.MIDDLEWARE_URL}/agent/runs/stream`,
    upstreamHeaders: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
    body: await req.text(),
  });
}
```

### Anti-Patterns

**Anti-Pattern: `'use client'` on the root layout.**
```tsx
// BAD -- app/layout.tsx
"use client";
export default function RootLayout({ children }) { ... }
```
Forces the entire app to client-render. Defeats the purpose of RSC. Move client-only logic into a leaf provider.

**Anti-Pattern: Server Actions for SSE.**
Server Actions are RPCs, not streaming endpoints. Use Route Handlers + `ReadableStream` for any byte stream.

**Anti-Pattern: `cache: 'force-cache'` on user-scoped data.**
```typescript
// BAD
const threads = await fetch(`/api/threads?user=${userId}`, { cache: 'force-cache' });
```
User A sees user B's threads. Always `no-store` on user-scoped routes.

---

## 10. Cross-Process Boundary Rules

The frontend ring crosses three process boundaries: Browser → BFF (Next.js Route Handler) → Middleware (Cloud Run / Fargate Python) → `agent_ui_adapter` Python process. Each boundary is HTTP/SSE only.

### Browser + BFF sub-ring (`frontend/lib/`)

| Module | May import from | May NOT import from |
|--------|-----------------|---------------------|
| `ports/` | `wire/`, `trust-view/` | `adapters/`, `translators/`, `transport/`, `composition.ts` |
| `adapters/` | `ports/`, `wire/`, `trust-view/`, third-party SDKs | `translators/`, `transport/`, `composition.ts`, other `adapters/` |
| `wire/` | stdlib, Zod | Everything else in `frontend/lib/` |
| `trust-view/` | stdlib, Zod | Everything else in `frontend/lib/` |
| `translators/` | `wire/`, `trust-view/` | `adapters/`, `ports/`, `transport/`, `composition.ts`, any SDK |
| `transport/` | `wire/`, stdlib, `EventSource` | `adapters/`, `ports/`, `translators/`, `composition.ts`, any SDK |
| `composition.ts` | Everything in `frontend/lib/`, React context | Nothing (it is the root) |

### Middleware sub-ring (`middleware/`)

| Module | May import from | May NOT import from |
|--------|-----------------|---------------------|
| `ports/` | `agent_ui_adapter/wire/`, `trust/` | `adapters/`, `translators/`, `transport/`, `composition.py` |
| `adapters/` | `ports/`, `agent_ui_adapter/wire/`, `trust/`, third-party SDKs | `translators/`, `transport/`, `composition.py`, other `adapters/` |
| `translators/` | `agent_ui_adapter/wire/`, `trust/` | `adapters/`, `ports/`, `transport/`, `composition.py` |
| `transport/` | `agent_ui_adapter/wire/` | `adapters/`, `ports/`, `translators/`, `composition.py` |
| `composition.py` | Everything in `middleware/`, `agent_ui_adapter/`, `trust/` | Nothing in `components/`, `orchestration/`, `governance/`, `services/` |

### Rules

**Rule M1: Nothing in the four-layer backend imports from `middleware/`.**
The dependency arrow is one-way. A backend file that imports from `middleware/` fails `tests/architecture/test_middleware_layering.py`.

**Rule M2: BFF holds no cloud credentials (F-R9 restated).**
No AWS key, GCP service-account JSON, or provider API key (WorkOS API key, Mem0 API key, Langfuse keys) appears in a Vercel or Cloudflare Pages environment variable. All credential-bearing calls go through `middleware/`. The BFF holds only `WORKOS_CLIENT_ID` (public), `NEXT_PUBLIC_WORKOS_REDIRECT_URI` (public OAuth callback URL; required by `@workos-inc/authkit-nextjs` — not `WORKOS_REDIRECT_URI`), `MIDDLEWARE_URL` (public), and other Next.js framework secrets (`NEXT_*`).

**Rule M3: JWT-bearing HTTPS is the only cross-process call shape.**
Browser → BFF: WorkOS session cookie (HttpOnly). BFF → Middleware: `Authorization: Bearer <WorkOS access token>`. Middleware → `agent_ui_adapter`: same bearer token, re-verified server-side. No shared in-memory state, no Unix sockets, no shared filesystem, no message queues at this seam.

---

## 11. Frontend Invariants F-R1 through F-R9

These are the architectural invariants from [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §"Frontend-Side Architecture Invariants", restated here as code-review rules.

| Invariant | Statement | Enforcement | Symptom of violation |
|-----------|-----------|-------------|----------------------|
| **F-R1** | No domain logic in React components. | Code review + import-graph test | A component file imports from `adapters/` directly |
| **F-R2** | SDK imports allowed only in `adapters/`. | `tests/architecture/test_frontend_layering.ts` | `ports/`, `translators/`, `transport/`, or `wire/` file imports a third-party SDK |
| **F-R3** | One interface per `ports/` module. | Architecture test | Two `export interface` declarations in one `ports/` file |
| **F-R4** | BFF Route Handlers are composition adapters, not business logic. | Code review | Route Handler with non-trivial `if` branch that isn't a port call |
| **F-R5** | System prompts remain in `prompts/` as Jinja templates. | Code review + architecture test | Any prompt string, instruction text, or system-prompt fragment in a `.ts` / `.tsx` file |
| **F-R6** | `trust-view/` is read-only. | TypeScript compiler + Rule W8 | `trust-view/` exports a function or class with mutable state |
| **F-R7** | Every emitted event must forward `trace_id` untouched. | Rules W5 + T2 + conformance test | Translator output drops `trace_id`; new event schema omits the field |
| **F-R8** | No SDK type may escape past an adapter boundary. | Rule A4 + architecture test | Adapter exported method returns an SDK type |
| **F-R9** | BFF must never hold cloud credentials. | Rule M2 + secrets scan in CI | Vercel / Cloudflare Pages env contains a provider API key |

The code-review symptom column is the operationalization. A reviewer scanning a PR diff for these symptoms catches >90% of invariant violations without running tests.

---

## 12. Frontend Patterns Catalog

This catalog mirrors the backend's [STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md) numbered-rule format. Each pattern has: When to Use, How to Implement, Code example (cited from the architecture deep-dives where possible), Anti-patterns.

### Pattern Catalog Overview

| Family | IDs | Layer | One-line Description |
|--------|-----|-------|----------------------|
| **W** Wire | W1-W8 | `wire/`, `trust-view/` | Pure shapes, mirror Python, discriminated unions, sealed envelopes, `trace_id` everywhere |
| **P** Port | P1-P7 | `ports/` | One interface per file, vendor-neutral, behavioral contract in JSDoc, typed errors |
| **A** Adapter | A1-A10 | `adapters/` | SDK boundary, error translation, idempotent destructive ops, per-family logger |
| **T** Translator | T1-T4 | `translators/` | Pure, `trace_id` forwarding, zero-or-many output rule, table-driven tests |
| **X** Transport | X1-X6 | `transport/` | `EventSource` isolation, Zod parse on receive, `Last-Event-ID` resume, BFF byte-forward |
| **C** Composition | C1-C5 | `composition.ts/.py` | Single profile switch, inject by port, env reads only here |
| **B** Browser process | B1-B7 | `app/`, `app/api/` | RSC by default, leaf `'use client'`, Server Actions vs Route Handlers, Edge opt-in |
| **U** UI | U1-U8 | `components/` | RSC default, sandboxed iframe, ARIA live region, focus on route change, `cn()` |
| **S** Session/Auth | S1-S3 | `adapters/auth/` | Token refresh on <60s expiry, BFF holds no creds, server-side JWT verify |
| **O** Observability | O1-O4 | `adapters/observability/` | Telemetry never blocks SSE, no PII, per-adapter namespace, `trace_id` in every span |

The W, P, A, T, X, C, B rules are defined in §3-§9 above. The U, S, O rules are defined below.

### U: UI Component Patterns

**U1: RSC by default.** See Rule B1.

**U2: Leaf `'use client'`.** Push the client boundary as far down the tree as possible. A thread sidebar that is mostly server-rendered with one client-side menu trigger uses an RSC sidebar wrapping a client `<MenuTrigger />`, not a client sidebar.

**U3: Sandboxed iframe for generative UI.** See §15.

**U4: ARIA live region for streaming tokens.** A single, persistent, visually-hidden `<div role="log" aria-live="polite" aria-atomic="false">` receives every token append. Never `aria-live="assertive"` for streaming -- it interrupts screen readers mid-sentence.

```tsx
// components/chat/StreamingMessage.tsx
<div role="log" aria-live="polite" aria-atomic="false" className="sr-only">
  {streamingText}
</div>
<div aria-hidden="true">{streamingText}</div>
```

**U5: Focus moves on route change only -- never on incoming tokens.**
```tsx
// app/(chat)/[threadId]/page.tsx (RSC + client island)
useEffect(() => {
  // intentional: focus main on route change so screen readers re-announce context
  mainRef.current?.focus();
}, [threadId]);
```
Moving focus on every token destroys the user's reading flow. Move focus only on navigation, modal open, or explicit user action.

**U6: `cn()` for class merging.**
```tsx
// GOOD
<button className={cn("px-4 py-2", isPrimary && "bg-primary text-primary-fg", className)} />
```
Raw template-string conditionals (`` `px-4 ${isPrimary ? "bg-primary" : ""}` ``) are forbidden -- they don't survive Tailwind merge correctly when consumers override.

**U7: shadcn primitives over custom-built.**
The first Q for any new component: "Does shadcn have it?" If yes, install via shadcn CLI into `components/ui/` and wrap in `components/primitives/` with product-specific defaults. Custom builds require justification.

**U8: Design tokens via Tailwind v4 `@theme`.**
All color, spacing, font, and radius tokens live in `app/globals.css` under `@theme` blocks. Component code references semantic tokens (`bg-primary`, `text-fg`, `rounded-md`) -- never raw color values.

```css
/* app/globals.css */
@import "tailwindcss";

@theme {
  --color-primary: oklch(0.6 0.2 250);
  --color-primary-fg: oklch(0.98 0 0);
  --color-bg: oklch(1 0 0);
  --color-fg: oklch(0.15 0 0);
  /* ... */
}

[data-theme="dark"] {
  --color-bg: oklch(0.12 0 0);
  --color-fg: oklch(0.95 0 0);
}
```

### S: Session / Auth Patterns

**S1: Token refresh on <60s expiry.**
`AuthProvider.getAccessToken()` checks `expires_at - now() < 60s` and calls `refreshSession()` before returning. Consumers never see an expired token.

**S2: BFF holds no cloud credentials.** See Rule M2 / F-R9.

**S3: JWT verified server-side, never trusted client-side.**
Browser-side code may read `Session.user_id` for display, but every authorization decision happens after server-side JWT verification (in `middleware/` and re-verified in `agent_ui_adapter/`).

### O: Observability Patterns

**O1: Telemetry never blocks SSE.**
`TelemetrySink.span()` and `start_span()` are non-blocking and swallow errors. A failing telemetry call must never delay an SSE frame or interrupt a run. The Python middleware uses fire-and-forget tasks; the TS browser side uses `requestIdleCallback` where available, plain async otherwise.

**O2: No PII in logs.**
Logger rule. Never log: access tokens, memory content, LLM output text, user emails, full request bodies. May log: `trace_id`, `run_id`, `thread_id`, adapter name, error type, durations, HTTP status codes.

**O3: Per-adapter logger namespace.** See Rule A7.

**O4: `trace_id` propagated to every span.**
The middleware `TelemetryExporter.start_span()` receives `trace_id` from the run and sets it as the Langfuse trace external ID. This correlates Langfuse traces with `TrustTraceRecord` events emitted by the Python runtime adapter.

### Composition Examples

**Example 1: A `ToolStartEvent` flowing through the ring.**

```
SSE wire frame
    │  (data: { type: "tool.start", tool_call_id: "tc_1", trace_id: "abc", ... })
    ▼
[X] transport/sse_client.ts
    │  Zod-parse against AGUIEvent (X2); yields ToolStartEvent
    ▼
[T] translators/tool_event_to_renderer_request.ts
    │  toolStartToRequest() — pure function (T1, T4)
    │  forwards trace_id (T2)
    ▼
[U] components/tools/ShellToolUI.tsx
    │  receives ToolRendererProps, narrows input with Zod
    │  rendered via ToolRendererRegistry.getRenderer("shell")
    │  no SDK import (F-R2); no business logic (F-R1)
    │  classes via cn() (U6); shadcn primitive wrapper (U7)
    ▼
DOM
```

Five rules from five different families combine cleanly with no orchestration -- because each layer has a single responsibility.

**Example 2: Substrate swap V3 → V2 for memory.**

```
Step 1: Add middleware/adapters/memory/self_hosted_mem0_client.py
        — implements MemoryProvider (P1)
        — wraps mem0ai SDK (A1)
        — error translation table in JSDoc (A5)
        — SDK pin in JSDoc (A9)
        — middleware.adapters.memory logger (A7)
        — no import of agent_ui_adapter (A8)

Step 2: Update middleware/composition.py to pick the V2 adapter when
        ARCHITECTURE_PROFILE=v2 (C1, C2)

Step 3: Add the new adapter to middleware/tests/test_adapter_conformance.py (P7)
```

Three steps, three files. No port change, no wire change, no translator change, no UI change. This is what F3 enforces.

---

## 13. UI Component Conventions

This section is normative for everything under `frontend/components/`.

### Tailwind v4 specifics

- **CSS-first configuration.** No `tailwind.config.js`. All tokens in `app/globals.css` under `@theme` blocks (see U8).
- **Semantic tokens.** `--color-primary`, `--color-bg`, `--color-fg`, `--color-muted`, `--color-danger`, `--color-success`. Never hue-named tokens (`--color-blue-500`) at the application layer.
- **`@import "tailwindcss"`** at the top of `app/globals.css`. Replaces legacy `@tailwind base / components / utilities` directives.
- **No PostCSS plugins beyond Tailwind.** Anything else needs an ADR.

### shadcn/ui ownership

- **`components/ui/`** -- raw shadcn output. Treat as source code, not a dependency. Generated by `npx shadcn add <component>`.
- **`components/primitives/`** -- product-specific wrappers around `ui/`. This is where you set defaults, add variants, attach `data-*` state attributes.
- **Never edit `components/ui/*` files in place.** Wrap them in `primitives/`. This keeps `npx shadcn upgrade` clean.

### `cn()` helper

Rule U6 restated. The implementation is the canonical shadcn one:

```typescript
// lib/utils.ts (one of the few utilities outside frontend/lib)
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### `data-*` attributes for state

Style by attribute, not by JS conditional:

```tsx
// GOOD
<button data-loading={loading ? "true" : "false"}
        className="data-[loading=true]:opacity-50 data-[loading=true]:pointer-events-none">

// BAD
<button className={cn("...", loading && "opacity-50 pointer-events-none")}>
```

Reason: `data-*` survives style merges, is debuggable in DevTools without React, and works with CSS-only animations.

### Accessibility (WCAG 2.2 AA)

- Streaming tokens go into a single persistent `role="log"` `aria-live="polite"` `aria-atomic="false"` region (U4).
- **Never** `aria-live="assertive"` for streaming.
- Focus moves on route change only (U5). Use `useRef` + `useEffect` keyed on `pathname`.
- `<button>` for every action -- never `<div onClick>`. `<a href>` only for actual navigation.
- Every input has an associated `<label htmlFor>` or `aria-label`.
- `eslint-plugin-jsx-a11y` errors fail CI; `@axe-core/react` runs in dev; Playwright runs `@axe-core/playwright` on every page in e2e.

### Internationalization stub

All visible strings route through a `t()` helper from day 1, even when `t()` is identity:

```tsx
// components/chat/Composer.tsx
import { t } from "@/lib/i18n";
<button aria-label={t("composer.send")}>{t("composer.send_label")}</button>
```

Reason: when i18n actually ships (post-launch), no string-hunting refactor is needed. The friction is ~5 minutes per component; the cost of retrofitting i18n later is weeks.

### Markdown rendering

`react-markdown` + `shiki` for code blocks. Configure shiki theme tokens to match shadcn:

```typescript
// components/chat/Markdown.tsx
const highlighter = createHighlighter({
  themes: ["github-light", "github-dark"],
  langs: ["typescript", "python", "json", "bash"],
});
```

The theme follows `[data-theme]` so dark mode just works.

---

## 14. State Management Rules

**Default:** RSC for read state; Server Actions for mutations; `useState` / `useReducer` for transient UI state.

### Rules

1. **No Redux / Zustand / Jotai unless explicitly justified per component** -- and even then, the state must not duplicate what's already in agent state (rendered via `useCoAgentStateRender`). Redux/Zustand introduction requires an ADR.
2. **CopilotKit hooks are the source of truth for chat state.** Never shadow them in a separate store. `useMessages()`, `useThread()`, `useToolRenderer()` are the canonical reads.
3. **`useEffect` is a code smell.** Justify each one in an inline comment. Prefer derived state from props, Server Actions for mutations, and event handlers for user actions. Acceptable `useEffect` use cases: focus management on route change (U5), subscribing to `EventSource` (only inside `transport/sse_client.ts`), syncing to external systems that aren't React-aware. If you can't articulate why none of those alternatives work, you don't need the effect.
4. **No global window-level event buses.** Cross-component communication goes through React context (provided by composition root) or CopilotKit's state layer.
5. **Form state via `useActionState`** (React 19) -- never roll your own `useState` form-error reducer.

### Anti-Pattern: parallel client store mirroring CopilotKit

```typescript
// BAD
const useChatStore = create((set) => ({
  messages: [],
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
}));
// Then ALSO using CopilotKit's useMessages() — two sources of truth.
```

Pick one. CopilotKit's hook is the source of truth for chat state.

---

## 15. Generative UI and Sandboxing

The two CopilotKit generative-UI patterns and their security boundaries:

### `useFrontendTool` -- Static Generative UI

For branded, structured tool-call cards (`ShellToolUI`, `FileIOToolUI`, `WebSearchToolUI`). The agent decides which tool to call; we ship one React component per tool, registered via `ToolRendererRegistry.register("shell", ShellToolUI)` from the composition root.

```tsx
// components/tools/ShellToolUI.tsx
const ShellInput = z.object({ command: z.string() });

export function ShellToolUI({ toolCallId, input, output, status }: ToolRendererProps) {
  const parsed = ShellInput.safeParse(input);
  if (!parsed.success) return <GenericJsonToolUI ... />;
  return (
    <Card data-status={status}>
      <CodeBlock language="bash">{parsed.data.command}</CodeBlock>
      {output && <CodeBlock>{String(output)}</CodeBlock>}
    </Card>
  );
}
```

### `useComponent` -- Open-ended Generative UI

For agent-emitted HTML/SVG/Canvas artifacts (charts, diagrams, algorithm visualizations, the Pyramid panel). Rendered into a **sandboxed iframe** -- no exceptions.

```tsx
// components/generative/WidgetRenderer.tsx
export function WidgetRenderer({ html }: { html: string }) {
  return (
    <iframe
      sandbox="allow-scripts"   // NEVER allow-same-origin
      srcDoc={html}
      className="w-full h-96 border-0"
      title={t("generative.widget")}
    />
  );
}
```

### Iframe sandbox rules

- `sandbox="allow-scripts"` is the **only permitted value**. The token list is exactly that one token.
- **Forbidden tokens:** `allow-same-origin`, `allow-top-navigation`, `allow-forms`, `allow-popups`, `allow-modals`, `allow-pointer-lock`.
- The iframe content is delivered via `srcDoc` (origin: `null`), never `src` to an external URL.
- CSP `frame-src 'self'` (sandboxed `srcDoc` iframes count as same-origin for `frame-src`).
- Every `<iframe>` in the codebase has a `sandbox` attribute. A reviewer sees `<iframe>` without `sandbox` → block merge.

### `ToolRendererRegistry` rules

- `getRenderer(toolName)` returns `null` for unregistered tools; the fallback is `GenericJsonToolUI` (a read-only JSON viewer).
- `register(toolName, component)` is called only from the composition root (Rule C2).
- Every renderer narrows its `input: unknown` with its own Zod schema before rendering. No renderer trusts the input shape.

### Anti-Pattern: `dangerouslySetInnerHTML` of agent output

```tsx
// BAD
<div dangerouslySetInnerHTML={{ __html: agentEmittedHtml }} />
```

This runs the agent's HTML in the same origin as your application. The agent could read cookies, exfiltrate session tokens, and impersonate the user. Always render agent HTML in a sandboxed iframe via `useComponent`.

### Anti-Pattern: iframe with `allow-same-origin`

```tsx
// BAD
<iframe sandbox="allow-scripts allow-same-origin" srcDoc={html} />
```

`allow-same-origin` defeats the sandbox. The iframe can read cookies, `localStorage`, and call same-origin APIs. Use only `allow-scripts`.

---

## 16. Authentication, Authorization, Trust Propagation

### Auth flow

1. Browser hits a protected route. `middleware.ts` checks the WorkOS session cookie.
2. If absent or expired, redirect to `/api/auth/sign-in` (handled by `WorkOSAuthKitAdapter`).
3. After login, every request to `/api/run/*` carries the WorkOS session cookie.
4. The Route Handler reads `getAccessToken()` from `AuthProvider` and forwards as `Authorization: Bearer <token>` to the middleware.
5. The middleware verifies the JWT against WorkOS JWKs, extracts identity, then calls into `agent_ui_adapter`.

Implementation rules: S1 (refresh on <60s), S2 (BFF holds no creds), S3 (server-side verify only).

### Authorization

Decisions are made in Python (`services/authorization_service.py`). The frontend renders the decision via `PolicyDecisionView` from `trust-view/`. Per-tool approval prompts use `useFrontendTool` + `useHumanInTheLoop` (F17 in [FRONTEND_PLAN_V2_FRONTIER.md](plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md) §2.1).

### Trust propagation (F-R7 operationalized)

The full path:

```
Python runtime adapter generates trace_id = uuid4().hex
        ▼
agent_ui_adapter forwards via DomainEvent → AGUIEvent
        ▼
SSE wire (text/event-stream) -- trace_id is a field on every payload (W5)
        ▼
middleware/ SSE pass-through -- never alters or strips trace_id
        ▼
BFF edge_proxy.ts pass-through -- never alters or strips trace_id
        ▼
transport/sse_client.ts -- Zod-parsed; trace_id required field (X2, W5)
        ▼
translators/ag_ui_to_ui_runtime.ts -- forwards trace_id to every UI shape (T2)
        ▼
UI components -- pass trace_id into TelemetrySink.span() (O4)
```

Rules at each level: W5 (schema requires `trace_id`), T2 (translators forward), O4 (telemetry includes), and the architecture-level F-R7 (browser never generates).

### Sealed envelope

Restated from [`frontend/lib/README.md`](../frontend/lib/README.md):

| Action | Allowed? |
|--------|----------|
| Reading a field of a sealed envelope to render it | YES |
| Storing the envelope as a single JSON blob in component state | YES |
| Forwarding the envelope to another adapter route | YES |
| Mutating any field of the envelope (`facts.status = "active"`) | NO -- invalidates signature |
| Re-serializing via `JSON.stringify(JSON.parse(env))` | NO -- key reordering breaks signature |
| Adding "convenience" properties | NO -- changes bytes |
| Filtering fields out before sending downstream | NO -- adapter re-validates |

Type-level enforcement: every sealed envelope is typed `Readonly<T>`. Spread operations are forbidden by lint.

---

## 17. Observability and Logging

### Logger namespaces

| Stream | Browser TS namespace | Middleware Python logger |
|--------|---------------------|--------------------------|
| Runtime adapter | `frontend:adapter:runtime` | -- |
| Auth adapter | `frontend:adapter:auth` | `middleware.adapters.auth` |
| Thread store | `frontend:adapter:thread_store` | -- |
| Memory client | -- (browser does not call) | `middleware.adapters.memory` |
| Telemetry sink | `frontend:adapter:telemetry` | `middleware.adapters.observability` |
| UI runtime | `frontend:adapter:ui_runtime` | -- |
| Tool renderer | `frontend:adapter:tool_renderer` | -- |

Same per-stream routing pattern the backend uses in `logging.json` ([STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md) §"Horizontal Layer" Rule H3).

### PII boundary (Rule O2 restated)

**Never log:** access tokens, memory content, LLM output text, user emails, full request bodies, prompt contents.

**May log:** `trace_id`, `run_id`, `thread_id`, adapter name, error type, HTTP status codes, durations (ms), counts.

### Telemetry never blocks (Rule O1 restated)

A failed Langfuse call is caught, logged locally, and swallowed. The SSE stream never waits for telemetry. The Python middleware uses `asyncio.create_task()` for fire-and-forget; the TS browser side uses `void promise.catch(logLocally)`.

### `console.*` is forbidden outside `adapters/`

ESLint rule. `console.log`, `console.warn`, `console.error` outside `frontend/lib/adapters/` fails CI. Adapters use the structured logger; everything else is silent in production.

---

## 18. Performance and Streaming

### Bundle policy

**No fixed initial-load KB target on day 1. Measure first.**

The policy:

1. The first production build establishes a baseline JSON committed at `frontend/.bundle-baseline.json`. Generated by `ANALYZE=true pnpm build` (which runs `@next/bundle-analyzer` -- see [Next.js package bundling guide](https://nextjs.org/docs/app/guides/package-bundling)).
2. CI runs `ANALYZE=true pnpm build` on every PR and fails if any route's First Load JS exceeds the baseline by more than 10%.
3. CopilotKit imports use `next/dynamic` for any component not needed on first paint (Composer, MessageList, generative-UI renderers). The package has documented bundle regressions ([CopilotKit#3653](https://github.com/CopilotKit/CopilotKit/issues/3653) -- barrel files pulling in `mermaid`, `shiki`, `streamdown` add ~20MB).
4. Pin `@copilotkit/react-core` and `@copilotkit/react-ui` to a version that includes the `sideEffects` fix from issue #3653.
5. After three production releases, set a fixed budget by review.

Industry guidance for context (not a hard target):

- High-performance target: First Load JS < 200 KB gzipped.
- Acceptable for complex apps: < 500-1000 KB total client bundle.

### TTFT (time-to-first-token)

Target: < 500 ms p50 cold, < 100 ms p50 warm. SSE first byte must arrive before any UI rendering work. Enforce by Playwright timing assertion.

### Streaming hygiene

- `cache: 'no-store'` on every user-scoped route (B5).
- Strip `Accept-Encoding` on streaming routes (X6).
- `<Suspense>` boundary around every async server boundary; named `loading.tsx` for routes.

### Image optimization

`next/image` for every content image. `<img>` for content is a code-review block. Configure `images.remotePatterns` in `next.config.ts` for any external image hosts.

### Code splitting

Automatic per route. `dynamic(() => import(...))` only for heavy generative-UI components that aren't needed on first paint. Document the reason in a JSDoc comment.

---

## 19. Security Hardening

### Strict CSP with nonce strategy (mandated from day 1)

Per [Next.js CSP guide](https://nextjs.org/docs/app/guides/content-security-policy). No `'unsafe-inline'`. No `'unsafe-eval'`.

```typescript
// frontend/middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const cspHeader = `
    default-src 'self';
    script-src 'self' 'nonce-${nonce}' 'strict-dynamic';
    style-src 'self' 'nonce-${nonce}';
    img-src 'self' blob: data:;
    font-src 'self';
    connect-src 'self' https://*.workos.com;
    frame-src 'self';
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
    upgrade-insecure-requests;
  `.replace(/\s{2,}/g, " ").trim();

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", cspHeader);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", cspHeader);
  response.headers.set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  return response;
}

export const config = { matcher: "/((?!_next/static|_next/image|favicon.ico).*)" };
```

The root layout opts into dynamic rendering so the nonce is per-request:

```tsx
// app/layout.tsx
import { headers } from "next/headers";
import Script from "next/script";

export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html>
      <body>
        {children}
        <Script src="..." nonce={nonce} strategy="afterInteractive" />
      </body>
    </html>
  );
}
```

### shadcn/ui CSP compatibility matrix

shadcn primitives that inject inline `style` attributes need wrappers or alternatives under strict CSP. The matrix below tracks each primitive used; adding a new shadcn primitive requires adding it to this matrix in the same PR.

| shadcn primitive | Strict CSP compatible? | Notes / workaround |
|------------------|------------------------|---------------------|
| `Button` | Yes | Pure className; no inline style |
| `Card` | Yes | Pure className |
| `Input` | Yes | Pure className |
| `Label` | Yes | Pure className |
| `Textarea` | Yes | Pure className |
| `Tabs` | No | Radix injects positional inline styles. Wrap in a primitive that passes the nonce, OR isolate to a route excluded from the strict CSP matcher |
| `Dialog` | No | Same as Tabs (Radix portal positioning). Wrap or pass nonce via `nonce` prop where Radix supports it |
| `Sheet` | No | Same as Dialog |
| `Sonner` (toast) | No | Sonner injects styles. Use a custom toast primitive backed by `Radix Toast` with nonce, OR move out of the strict-CSP routes |
| `Command` | Partial | Requires nonce passthrough; track [shadcn-ui#4461](https://github.com/shadcn-ui/ui/issues/4461) for upstream fix |
| `Popover` | Partial | Same as Tabs; positional inline styles |
| `Tooltip` | Partial | Same as Tabs |
| `Toggle` | Yes | Pure className |
| `Separator` | Yes | Pure className |

This matrix is updated **in the same PR** as any new shadcn primitive add. Each "No" or "Partial" row links to a tracked issue or wrapper file. A PR that adds a Radix-backed shadcn primitive without addressing the CSP impact fails review.

### Other hardening

- `frame-src 'self'` -- sandboxed `srcDoc` iframes have `null` origin, counted as same-origin.
- WorkOS MFA enforced from launch.
- Cloudflare WAF in count mode for 48h, then enforce.
- Dependabot / Renovate weekly; `pnpm audit` blocks merge on high+ severity.
- Secrets scan in CI (gitleaks or equivalent).
- BFF holds no cloud credentials (M2 / F-R9).

---

## 20. Testing Strategy

### Pyramid

```
                    ┌──────────────────────┐
                    │  Visual (Storybook)  │   per generative-UI component
                    └──────────────────────┘
                  ┌──────────────────────────┐
                  │  e2e (Playwright + axe)  │   smoke + critical paths
                  └──────────────────────────┘
                ┌──────────────────────────────┐
                │  Integration (Vitest + MSW)  │   adapter happy/error paths
                └──────────────────────────────┘
              ┌────────────────────────────────────┐
              │  Architecture (ts-morph + axe-rule)│   layering + F-R1..F-R9
              └────────────────────────────────────┘
            ┌────────────────────────────────────────┐
            │  Unit (Vitest + RTL)                   │   pure functions + components
            └────────────────────────────────────────┘
```

### Required test categories

| Category | Tool | Required when |
|----------|------|---------------|
| Unit -- pure | Vitest | Any new translator, wire schema, pure helper |
| Unit -- component | Vitest + React Testing Library | Any new component |
| Integration -- adapter | Vitest + MSW for HTTP mocks | Any new adapter |
| Port conformance | Vitest parametrized over adapters | Any new port OR any new adapter implementing an existing port |
| Architecture -- layering | `ts-morph` walker | Always runs |
| Architecture -- middleware layering | `pytest` + `importlib` | Always runs |
| Wire schema drift | Python JSON Schema → committed baseline | On any `wire/` change |
| e2e | Playwright | Critical path per release |
| Accessibility -- static | `eslint-plugin-jsx-a11y` | Always runs in CI |
| Accessibility -- dynamic | `@axe-core/playwright` | On every Playwright route |
| Visual | Storybook stories | Every generative-UI component |

### Failure paths first

Mirror of the backend rule (`AGENTS.md` §"Testing Rules"). Write rejection tests before acceptance tests for every adapter:

1. 401 → `AgentAuthError`
2. 403 → `AgentAuthorizationError`
3. 429 → `AgentRateLimitError` with backoff
4. 5xx → `AgentServerError`
5. Network timeout → `AgentNetworkError` with reconnect
6. Then -- and only then -- the happy path

### No live LLM calls in CI

Mirror of `AGENTS.md`. All adapter tests use MSW mocks or scripted servers. Live calls are reserved for the `@pytest.mark.live_llm` equivalent (`describe.live` Vitest tag) and never run in CI.

### Storybook is mandatory for generative UI

Every component in `frontend/components/tools/` and `frontend/components/generative/` ships with a Storybook story. The story doubles as the development environment (no need to run the agent to render the component) and as the visual regression baseline.

---

## 21. Build, Tooling, CI Conventions

### Workspace

- **pnpm** workspace; lockfile committed.
- **Node 20 LTS** for build and Route Handlers.
- **Edge runtime** opt-in only for `transport/edge_proxy.ts` (Rule B7).

### TypeScript

`tsconfig.json` minimum:

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "moduleResolution": "bundler",
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "jsx": "preserve",
    "skipLibCheck": true
  }
}
```

Compile errors block merge.

### ESLint

Configured rules:

- `next/core-web-vitals`
- `eslint-plugin-jsx-a11y` (errors fail CI)
- `eslint-plugin-import` with architecture-style import order
- Custom rule: `no-console` outside `frontend/lib/adapters/**`
- Custom rule: `no-restricted-imports` blocking SDK packages outside `adapters/**`

### Prettier

`printWidth: 100`, `singleQuote: false`, `trailingComma: "all"`.

### Husky + lint-staged

Pre-commit: prettier + eslint on staged files. Pre-push: type-check + unit tests + architecture tests.

### CI (GitHub Actions)

Matrix on Node 20 LTS. Parallel jobs:

1. `lint` (eslint + prettier check)
2. `type-check` (`tsc --noEmit`)
3. `unit` (Vitest)
4. `architecture` (`tests/architecture/test_frontend_layering.ts` + `test_middleware_layering.py`)
5. `wire-schema-drift` (Python JSON Schema baseline diff)
6. `e2e` (Playwright headless on Chromium + Firefox)
7. `bundle-budget` (`ANALYZE=true pnpm build` + baseline diff)
8. `secrets-scan` (gitleaks)

All required to pass for merge.

### Renovate

Weekly batched dependency PRs, grouped by ecosystem (TS/Next/React, CopilotKit, WorkOS, LangGraph, testing, types).

---

## 22. Anti-Patterns

Consolidated list. Each anti-pattern has a stable ID for PR review citations.

### FE-AP-1: SDK type leak through a port

```typescript
// BAD
import type { CompletionRequestResult } from "@langchain/langgraph-sdk";
export interface AgentRuntimeClient { stream(req): AsyncIterable<CompletionRequestResult>; }
```
**Why it fails:** swap LangGraph for another runtime → every consumer breaks. **Fix:** use `AGUIEvent` from `wire/`; convert inside the adapter (Rule A4).

### FE-AP-2: Cross-adapter import

```typescript
// BAD
import { WorkOSAuthKitAdapter } from "../auth/workos_authkit_adapter";
class NeonFreeThreadStore { private auth = new WorkOSAuthKitAdapter(); }
```
**Why it fails:** prevents independent swap; testing is double-mocked. **Fix:** inject as port instance via composition root (Rule A2).

### FE-AP-3: Business logic in a Route Handler

```typescript
// BAD
export async function POST(req) {
  if ((await req.json()).input.includes("delete")) return new Response("denied", { status: 403 });
}
```
**Why it fails:** business decisions in BFF; can't be exercised from CLI; bypasses backend authorization. **Fix:** Route Handler is a composition adapter -- port calls only (Rule B6).

### FE-AP-4: `useComponent` iframe without `sandbox` (security-critical)

```tsx
// BAD
<iframe srcDoc={agentHtml} />
```
**Why it fails:** agent JS runs in your origin; reads cookies; impersonates user. **Fix:** `<iframe sandbox="allow-scripts" srcDoc={...}>` (§15).

### FE-AP-5: `aria-live="assertive"` on streaming tokens (a11y-critical)

```tsx
// BAD
<div aria-live="assertive">{streamingText}</div>
```
**Why it fails:** screen reader interrupts the user mid-sentence on every token. **Fix:** `aria-live="polite"` `aria-atomic="false"` (Rule U4).

### FE-AP-6: Mutating a sealed envelope

```typescript
// BAD
agentFacts.status = "active";
```
**Why it fails:** invalidates the signature; trust gate rejects. **Fix:** envelopes are `Readonly<T>`; produce a new envelope server-side via the trust kernel (Rule W4).

### FE-AP-7: Generating `trace_id` in the browser

```typescript
// BAD
const traceId = crypto.randomUUID();
fetch("/api/run", { body: JSON.stringify({ trace_id: traceId, ... }) });
```
**Why it fails:** breaks F-R7 propagation; trace fragments across the path. **Fix:** the Python runtime adapter generates `trace_id`; browser only forwards.

### FE-AP-8: Hardcoded model tier or URL outside composition

```typescript
// BAD
const url = "https://langgraph-platform.example.com";
```
**Why it fails:** cannot swap V2/V3 substrate; env-specific code in a shared module. **Fix:** read from composition; pass via constructor (Rules C4, C5).

### FE-AP-9: `console.log` outside an adapter

```typescript
// BAD -- in a component
console.log("user clicked send", message);
```
**Why it fails:** unstructured, not routed, leaks PII. **Fix:** structured logger inside an adapter; per-namespace stream (Rule O3).

### FE-AP-10: Parallel client store mirroring CopilotKit state

```typescript
// BAD
const useChatStore = create(...);
// AND ALSO using CopilotKit's useMessages()
```
**Why it fails:** two sources of truth; inevitable drift. **Fix:** CopilotKit hooks are the source of truth (§14 Rule 2).

### FE-AP-11: `'use client'` on the root layout

```tsx
// BAD -- app/layout.tsx
"use client";
```
**Why it fails:** entire app client-renders; defeats RSC. **Fix:** push the boundary to a leaf provider (Rules B1, U2).

### FE-AP-12: `dangerouslySetInnerHTML` of agent output

See FE-AP-4. Same root cause: agent content in your origin. Always sandbox.

### FE-AP-13: Direct CopilotKit / WorkOS / Mem0 import outside `adapters/`

```typescript
// BAD -- in a component
import { useCopilotAction } from "@copilotkit/react-core";
```
**Why it fails:** SDK leak; can't swap framework. **Fix:** route through `UIRuntime` port; import from the adapter only (Rule A1).

### FE-AP-14: Schema drift -- TS Zod schema with no matching Python baseline entry

```typescript
// BAD -- frontend/lib/wire/new_event.ts added without updating __python_schema_baseline__.json
```
**Why it fails:** wire shapes diverge silently between languages; runtime parse failures. **Fix:** Python is the source of truth; update baseline + matching Python schema in same PR (Rule W2).

### FE-AP-15: Adapter without an error-translation table

```typescript
// BAD
async stream(req) { return fetch(url).then(r => r.json()); }
```
**Why it fails:** raw HTTP errors leak to consumers; consumers can't `catch` typed errors. **Fix:** translate every documented status to a typed port error (Rule A5).

### FE-AP-16: Port without a conformance test

A new port file lands without a corresponding entry in `tests/architecture/test_port_conformance.ts`.
**Why it fails:** structural conformance never asserted; behavioral contract invisible. **Fix:** add the port to the parametrized suite in the same PR (Rule P7).

### FE-AP-17: Translator that touches `localStorage` / `fetch` / `document`

```typescript
// BAD
export function withCachedMemory(input) { return { ...input, memory: localStorage.getItem("m") }; }
```
**Why it fails:** translator no longer pure; impossible to test without mocks. **Fix:** I/O belongs in adapters (Rule T1).

### FE-AP-18: BFF holding a cloud credential

```
# BAD -- frontend Vercel env
MEM0_API_KEY=xxx
LANGFUSE_SECRET_KEY=xxx
```
**Why it fails:** browser bundle or BFF compromise exposes provider creds. **Fix:** all credential-bearing calls flow through `middleware/`; BFF holds only WorkOS public client config (Rule M2).

### FE-AP-19: Adding `'unsafe-inline'` to CSP to silence shadcn warning

```typescript
// BAD
"style-src 'self' 'unsafe-inline'"
```
**Why it fails:** opens XSS surface; defeats nonce strategy. **Fix:** wrap the offending shadcn primitive (see CSP matrix in §19) or move it to a route excluded from strict CSP (with explicit ADR).

### FE-AP-20: CopilotKit barrel import without `next/dynamic`

```typescript
// BAD
import { CopilotChat } from "@copilotkit/react-ui";
export default function Page() { return <CopilotChat />; }
```
**Why it fails:** barrel pulls in `mermaid`, `shiki`, `streamdown` -- ~20MB ([CopilotKit#3653](https://github.com/CopilotKit/CopilotKit/issues/3653)). **Fix:**
```typescript
const CopilotChat = dynamic(() => import("@copilotkit/react-ui").then(m => m.CopilotChat), { ssr: false });
```

---

## 23. Code Review Checklists

Three checklists optimized for paste-into-PR-comment use. Each box maps to a numbered rule.

### Checklist A -- Reviewing a new adapter PR

```
- [ ] Adapter implements exactly one port (P1)
- [ ] No SDK type in any exported function signature (A4 / F-R8)
- [ ] Error translation table in JSDoc (A5)
- [ ] SDK pin in JSDoc (A9)
- [ ] Conformance test parametrized to include this adapter (P7)
- [ ] Logger namespace registered (A7)
- [ ] Composition root updated; only `if profile === "X"` site (C1)
- [ ] No imports of sibling adapters (A2)
- [ ] Idempotent on destructive operations (A6)
- [ ] Per-family README updated (A10)
- [ ] Architecture test passes locally
- [ ] Failure-path tests written before happy-path tests (§20)
```

### Checklist B -- Reviewing a UI component PR

```
- [ ] RSC by default; `'use client'` justified by inline comment (B1, U2)
- [ ] No SDK import (CopilotKit, WorkOS, Mem0, etc.) -- only via port hooks (F-R2)
- [ ] All visible strings via `t()` helper (§13)
- [ ] All interactive elements are `<button>` / `<a href>`, not `<div onClick>` (§13)
- [ ] Streaming text in single persistent `role="log"` `aria-live="polite"` region (U4)
- [ ] No focus moves on incoming tokens (U5)
- [ ] All conditional classes via `cn()` (U6)
- [ ] State via `data-*` attribute, not `className` ternary (§13)
- [ ] Generative UI rendered in `<iframe sandbox="allow-scripts">` only (§15)
- [ ] Storybook story added if generative-UI component (§20)
- [ ] `@axe-core/playwright` passes for the route (§13)
- [ ] No `console.*` (O3)
- [ ] CSP matrix updated in same PR if new shadcn primitive added (§19)
- [ ] No `useEffect` without inline justification comment (§14)
```

### Checklist C -- Reviewing a wire / translator PR

```
- [ ] `wire/` mirrors a Python module (or is `ui_runtime_events.ts`) (W2)
- [ ] Field names snake_case to match Python (W6)
- [ ] `trace_id` present in every event schema (W5)
- [ ] Multi-variant types use `z.discriminatedUnion` (W3)
- [ ] `__python_schema_baseline__.json` updated; CI drift check passes (W2 / §20)
- [ ] Schema and inferred type co-exported with same name (W7)
- [ ] Translator is a pure function with no I/O (T1)
- [ ] Translator forwards `trace_id` to every output shape (T2)
- [ ] Zero-or-many output count documented in JSDoc (T3)
- [ ] Table-driven Vitest test added (T4)
- [ ] No SDK import; no React; no `localStorage` / `fetch` / `document` (T1)
```

These three checklists are encoded as the FD1-FD7 dimensions in [`prompts/codeReviewer/frontend/system_prompt.j2`](../prompts/codeReviewer/frontend/system_prompt.j2). The named `review_scope` values (`adapter_pr`, `ui_component_pr`, `wire_translator_pr`) in [`prompts/codeReviewer/frontend/review_submission.j2`](../prompts/codeReviewer/frontend/review_submission.j2) map 1:1 to Checklists A, B, and C respectively, so the same checklist used by a human reviewer is the one the validator agent runs.

---

## 24. Substrate Swap Procedure

Swapping V3 → V2 (or back) is exactly three steps. No more, no fewer.

1. **Add the new adapter file** under `frontend/lib/adapters/<family>/` or `middleware/adapters/<family>/`. Implements the existing port. Follows all A-rules.
2. **Register it in the composition root** (`frontend/lib/composition.ts` or `middleware/composition.py`) behind the `ARCHITECTURE_PROFILE` switch (Rule C1).
3. **Add the adapter to the conformance test bundle** (`frontend/tests/architecture/test_port_conformance.ts` or `middleware/tests/test_adapter_conformance.py`).

If you find yourself touching `wire/`, `translators/`, `transport/`, or any UI component, **stop**. The abstraction is wrong; file an issue rather than working around it (Rule F3).

The full V3 ↔ V2 substrate-swap matrix lives in [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §"Substrate-Swap Matrix".

---

## 25. Recipes

### Recipe 1: Adding a new port

1. Create `frontend/lib/ports/<port_name>.ts` with exactly one interface (P1), vendor-neutral name (P2), behavioral contract in JSDoc (P3), typed errors (P4).
2. Create at least one concrete adapter under `frontend/lib/adapters/<family>/` (or document that the port is a placeholder pending a second implementation).
3. Add the port to `frontend/tests/architecture/test_port_conformance.ts` parametrized over its adapters (P7).
4. Wire the port in `frontend/lib/composition.ts` (C1, C2).
5. Add the port to the eight-port table in [FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) §"The Eight Driven Ports".
6. Add the family README under `adapters/<family>/README.md` (A10).
7. Update §2 of this guide if the port introduces a new tech-stack category.

### Recipe 2: Adding a new adapter (existing port)

1. Create `frontend/lib/adapters/<family>/<vendor>_<purpose>_adapter.ts` (or `middleware/adapters/<family>/...`).
2. Add SDK pin JSDoc (A9), error translation table (A5), per-family logger namespace (A7).
3. Convert all SDK types to wire shapes inside the adapter (A4).
4. Add to the conformance test parametrization (P7).
5. Wire in the composition root behind the substrate switch (C1).
6. Update `adapters/<family>/README.md` with the new entry and swap trigger.

### Recipe 3: Adding a new translator

1. Create `frontend/lib/translators/<input>_to_<output>.ts`.
2. Imports only from `wire/` and `trust-view/` (T1).
3. Forward `trace_id` from input to every output shape (T2).
4. Document zero-or-many output count in JSDoc (T3).
5. Co-locate `frontend/lib/translators/<input>_to_<output>.test.ts` with table-driven cases per discriminated union variant (T4).

### Recipe 4: Adding a design pattern

1. Identify the family (W, P, A, T, X, C, B, U, S, O).
2. Pick the next sequential ID in that family (`U9`, `A11`, ...).
3. Add a new subsection in §12 (or in §3-§9 if the rule belongs to a layer section).
4. Include: When to Use, How to Implement, code example citing existing planned files, anti-patterns.
5. Add the pattern to the catalog overview table at the top of §12.
6. Update the relevant code review checklist (§23) if the pattern is reviewable.

### Recipe 5: Adding a new shadcn primitive

1. Run `npx shadcn add <component>` -- generates under `components/ui/`.
2. Test the primitive against the strict CSP from §19 -- in Playwright with the production CSP middleware enabled.
3. If CSP-incompatible, create a wrapper under `components/primitives/` that addresses the issue (nonce passthrough, alternative implementation, or scoped exclusion).
4. Add the primitive to the CSP compatibility matrix (§19) in the same PR.
5. Use the primitive only via `components/primitives/`, never directly from `components/ui/` (§13).

---

## 26. Directory Structure Convention

Canonical tree. Mirror of backend [STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md) §"Directory Structure Convention".

```
agent/
├── frontend/
│   ├── app/
│   │   ├── (chat)/
│   │   │   ├── layout.tsx                   # RSC
│   │   │   └── [threadId]/page.tsx          # RSC
│   │   ├── api/
│   │   │   ├── auth/[...workos]/route.ts    # Route Handler (composition adapter)
│   │   │   └── run/stream/route.ts          # SSE proxy
│   │   ├── globals.css                      # Tailwind v4 @theme tokens
│   │   └── layout.tsx                       # RSC root; reads x-nonce
│   ├── components/
│   │   ├── ui/                              # raw shadcn (do not edit)
│   │   ├── primitives/                      # product wrappers around ui/
│   │   ├── chat/                            # ChatSurface, MessageList, Composer
│   │   ├── tools/                           # Static AG-UI renderers (ShellToolUI, ...)
│   │   ├── generative/                      # Open AG-UI (sandboxed iframes, PyramidPanel)
│   │   └── shell/                           # ThreadSidebar, ExportRunButton
│   ├── lib/
│   │   ├── wire/                            # Zod schemas (mirror Python)
│   │   │   ├── domain_events.ts
│   │   │   ├── agent_protocol.ts
│   │   │   ├── ag_ui_events.ts
│   │   │   ├── ui_runtime_events.ts
│   │   │   └── __python_schema_baseline__.json
│   │   ├── trust-view/                      # Read-only trust shapes
│   │   ├── ports/                           # 8 TS interfaces (one per file)
│   │   ├── adapters/                        # SDK boundary
│   │   │   ├── runtime/
│   │   │   ├── auth/
│   │   │   ├── thread_store/
│   │   │   ├── memory/                      # (browser side absent in V3/V2)
│   │   │   ├── observability/
│   │   │   ├── ui_runtime/
│   │   │   ├── tool_renderer/
│   │   │   └── flags/
│   │   ├── translators/                     # Pure functions
│   │   ├── transport/                       # SSE client + edge proxy
│   │   ├── composition.ts                   # The only profile switch
│   │   ├── i18n.ts                          # t() helper (identity initially)
│   │   └── README.md                        # Sealed-envelope rule
│   ├── middleware.ts                        # CSP nonce middleware
│   ├── tests/
│   │   ├── architecture/                    # ts-morph layering + port conformance
│   │   ├── unit/                            # Vitest + RTL
│   │   ├── e2e/                             # Playwright + axe
│   │   └── stories/                         # Storybook (per generative-UI component)
│   ├── .bundle-baseline.json                # First Load JS baseline (per route)
│   ├── package.json                         # pnpm
│   ├── tsconfig.json                        # strict + noUncheckedIndexedAccess
│   ├── next.config.ts
│   └── eslint.config.mjs
│
├── middleware/
│   ├── ports/                               # 3 Python Protocols
│   ├── adapters/
│   │   ├── auth/
│   │   ├── memory/
│   │   └── observability/
│   ├── translators/
│   ├── transport/
│   ├── composition.py                       # Profile switch
│   ├── server.py                            # FastAPI entry point
│   ├── tests/
│   │   ├── architecture/
│   │   ├── adapters/
│   │   └── conftest.py
│   └── pyproject.toml
│
└── docs/
    ├── STYLE_GUIDE_LAYERING.md              # backend (existing)
    ├── STYLE_GUIDE_PATTERNS.md              # backend (existing)
    ├── STYLE_GUIDE_FRONTEND.md              # this doc
    ├── adr/                                 # Architecture Decision Records
    └── Architectures/
        ├── FRONTEND_ARCHITECTURE.md
        ├── FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md
        └── FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md
```

Structural signals to look for in code review:

- `frontend/lib/wire/` and `frontend/lib/trust-view/` import nothing from sibling sub-packages.
- `frontend/lib/composition.ts` is the only file containing `process.env.ARCHITECTURE_PROFILE`.
- `frontend/lib/adapters/<family>/` is the only place SDK packages are imported.
- Every `frontend/lib/ports/` file exports exactly one interface.

---

## 27. Glossary

| Term | Meaning here |
|------|--------------|
| **ADR** | Architecture Decision Record (file under `docs/adr/`) -- the only way to deviate from a §2 prescription |
| **AG-UI** | Agent-User Interaction Protocol; CopilotKit's open spec for agent ↔ UI bidirectional events |
| **Agent Protocol** | Open spec for agent HTTP/SSE APIs; LangGraph Platform implements it natively |
| **a11y** | Accessibility (WCAG 2.2 AA target) |
| **BFF** | Backend-for-Frontend; the Next.js Route Handler layer |
| **CopilotKit** | Frontend stack for agents and generative UI; AG-UI authors |
| **CSP** | Content Security Policy (HTTP header) |
| **F-R#** | Frontend invariant rule from [FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) §11 |
| **FE-AP-#** | Frontend anti-pattern from §22 of this guide |
| **HITL** | Human-in-the-Loop (approval flow for tools requiring user consent) |
| **HSTS** | HTTP Strict Transport Security |
| **JWKS** | JSON Web Key Set (public keys for JWT verification) |
| **JWT** | JSON Web Token |
| **LangGraph** | LangChain's stateful graph-based agent runtime |
| **Langfuse** | Open-source LLM observability platform: tracing + prompt mgmt + evals |
| **Last-Event-ID** | SSE header for resumption after disconnect |
| **MAU** | Monthly Active Users |
| **Mem0** | Open-source agent memory layer; vector + optional graph |
| **MFA** | Multi-Factor Authentication |
| **MSW** | Mock Service Worker (HTTP mocking for tests) |
| **OIDC** | OpenID Connect |
| **PEP** | Policy Enforcement Point (NIST 800-207 ZTA) |
| **PII** | Personally Identifiable Information |
| **RSC** | React Server Component |
| **RUM** | Real User Monitoring |
| **SCIM** | System for Cross-domain Identity Management (enterprise user provisioning) |
| **shadcn/ui** | Component library; copied into `components/ui/` as source code |
| **SSE** | Server-Sent Events (HTTP streaming protocol) |
| **TTFT** | Time-To-First-Token |
| **WAF** | Web Application Firewall |
| **WorkOS** | Auth/SSO/SCIM-as-a-service; AuthKit free up to 1M MAU |
| **Zod** | TypeScript-first schema validation library |

---

## 28. Related Documents

| Document | Relationship |
|----------|--------------|
| [STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md) | Backend four-layer style guide that this mirrors. The H/V rule families on the backend correspond to the W/P/A/T/X/C/B/U/S/O families here. |
| [STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md) | Backend pattern catalog (H1-H7, V1-V6). §12 of this guide is the frontend analogue. |
| [Architectures/FRONTEND_ARCHITECTURE.md](Architectures/FRONTEND_ARCHITECTURE.md) | Big-picture spec for the Frontend Ring. Source of the F-R1..F-R9 invariants restated in §11. |
| [Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md](Architectures/FRONTEND_PORTS_AND_ADAPTERS_DEEP_DIVE.md) | Per-port and per-adapter deep dive. Source for §4 and §5. |
| [Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md](Architectures/FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE.md) | Wire kernels, translators, transport spec. Source for §3, §6, §7. |
| [Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md](Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md) | The middle adapter ring this frontend ring drives. |
| [Architectures/FOUR_LAYER_ARCHITECTURE.md](Architectures/FOUR_LAYER_ARCHITECTURE.md) | The innermost backend ring; trust foundation source of truth. |
| [plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md](plan/frontend/FRONTEND_PLAN_V2_FRONTIER.md) | V2-Frontier substrate profile (Cloud SQL HA, self-hosted Mem0/Langfuse). |
| [plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md](plan/frontend/FRONTEND_PLAN_V3_DEV_TIER.md) | V3-Dev-Tier substrate profile (free-tier; same architecture). |
| [`frontend/lib/README.md`](../frontend/lib/README.md) | Sealed-envelope rule (W4 source). |
| [AGENTS.md](../AGENTS.md) | Workspace conventions; the Frontend conventions subsection links here. |

**To-be-written follow-ups:**

- `docs/contributing/FRONTEND_ADAPTERS_HANDBOOK.md` -- step-by-step recipe handbook (mirror of [contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md](contributing/AGENT_UI_ADAPTER_ADAPTERS_HANDBOOK.md)).
- `docs/adr/0000-template.md` -- ADR template required by §2 for substrate or library swaps.
