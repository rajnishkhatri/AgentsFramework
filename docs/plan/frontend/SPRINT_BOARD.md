# Frontend Sprint Board

> **Status**: active sprint board.
>
> **Base plan**: [FRONTEND_PLAN_V3_DEV_TIER.md](FRONTEND_PLAN_V3_DEV_TIER.md) — same architecture as V2-Frontier on free-tier substrates.
>
> **Fallback**: [FRONTEND_PLAN_V1.md](FRONTEND_PLAN_V1.md) — assistant-ui + Auth.js + Cognito + AWS ECS, activated if Sprint 0 spikes fail.
>
> **Architecture source of truth**: [docs/Architectures/FRONTEND_ARCHITECTURE.md](../../Architectures/FRONTEND_ARCHITECTURE.md)
>
> **Style guide**: [docs/STYLE_GUIDE_FRONTEND.md](../../STYLE_GUIDE_FRONTEND.md)
>
> **Code review prompt**: [prompts/codeReviewer/frontend/](../../../prompts/codeReviewer/frontend/)
>
> **Total duration**: ~15.5 working days across 5 sprints aligned to the plan's phases.

---

## Table of Contents

- [Sprint 0 — Decisions Locked + Spike Validation](#sprint-0--decisions-locked--spike-validation-35-days)
- [Sprint 1 — Middleware + Self-Hosted LangGraph](#sprint-1--middleware--self-hosted-langgraph-3-days)
- [Sprint 2 — Dev-Tier Infrastructure](#sprint-2--dev-tier-infrastructure-2-days)
- [Sprint 3 — Frontend Integration](#sprint-3--frontend-integration-5-days)
- [Sprint 4 — Hardening + Private Beta Launch](#sprint-4--hardening--private-beta-launch-2-days)
- [Cross-Cutting Definition of Done](#cross-cutting-definition-of-done)
- [V2-Frontier Graduation Triggers](#v2-frontier-graduation-triggers)
- [V1 Fallback Paths](#v1-fallback-paths)

---

## Sprint 0 — Decisions Locked + Spike Validation (3.5 days)

**Goal**: Lock decisions, validate all four critical integration hypotheses before committing to implementation.

### Epic 0.1: Decision Lock (0.5 day)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S0.1.1** | As an **architect**, I want the V3-Dev-Tier plan committed to `main`, so that all team members have a single source of truth for frontend decisions. | **Architecture**: Plan references `AGENTS.md` invariants; four-layer architecture preserved. **Style Guide**: Plan references `STYLE_GUIDE_FRONTEND.md` tech-stack prescriptions (§2). **Code Review**: N/A (documentation). **Test**: N/A. **DoD**: `FRONTEND_PLAN_V3_DEV_TIER.md` merged to `main`; all D1-D8 decisions from V1 carried forward; V2 graduation triggers documented in §6.5/6.6. |
| **S0.1.2** | As a **developer**, I want GCP project `agent-prod-gcp-dev` registered in `us-central1`, so that infrastructure provisioning can begin in Sprint 2. | **Architecture**: N/A. **Style Guide**: N/A. **Code Review**: N/A. **DoD**: GCP project created; billing account linked; Secret Manager API enabled; Cloud Run API enabled; necessary IAM roles assigned. |

### Epic 0.2: CopilotKit + LangGraph Integration Spike — Spike A (1 day)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S0.2.1** | As a **developer**, I want to verify that CopilotKit v2 `useFrontendTool` renders tool-call cards from the existing `react_loop` graph's SSE events, so that we can commit to CopilotKit for F5 (tool cards). | **Architecture**: Validates H4 in V2-Frontier (CopilotKit↔ReAct graph compatibility). Spike runs in a throwaway repo — no production code committed. CopilotKit SDK types must be confinable to `adapters/` **[A1, F-R2]**. **Style Guide**: N/A (spike). **Code Review [FD2.U1]**: Validates CopilotKit components as client-only feasibility. **Test**: Manual verification — `useFrontendTool` renders `shell`, `file_io`, `web_search` tool cards with correct `input`/`output` fields. **DoD**: Throwaway repo demonstrates end-to-end render; spike report documents any impedance mismatches; **PASS** → proceed with CopilotKit; **FAIL** → revert to `assistant-ui` per V1. |
| **S0.2.2** | As a **developer**, I want to verify that CopilotKit `useComponent` renders generative-UI HTML in a sandboxed iframe, so that we can commit to F13 (canvas) and F14 (Pyramid panel). | **Architecture**: Validates H7 (iframe sandbox sufficient) **[F-R1, U3]**. **Style Guide**: iframe must use `sandbox="allow-scripts"` only **[U3]**; no `allow-same-origin` **[FE-AP-4 AUTO-REJECT]**. **Code Review [FD3.SBX1, FD3.SBX2]**: Validates sandboxing feasibility. **Test**: Manual — `useComponent` renders HTML via `srcDoc` in `<iframe sandbox="allow-scripts">`; no cross-origin access possible. **DoD**: Spike demonstrates sandboxed rendering; security boundary confirmed. |
| **S0.2.3** | As a **developer**, I want to verify that `useCoAgentStateRender` renders live step/cost/model data from custom SSE events, so that F6 (step meter) and F7 (model badge) can use CopilotKit. | **Architecture**: Custom SSE events flow through AG-UI protocol into CopilotKit hooks without modification to `wire/` shapes **[W1]**. **Style Guide**: State render must not introduce domain logic in components **[F-R1]**. **Code Review [FD2]**: Validates pattern adherence for custom event rendering. **Test**: Manual — `StepMeter` and `ModelBadge` components update in real-time as custom events arrive. **DoD**: Custom events render correctly; no CopilotKit modification needed. |

### Epic 0.3: Self-Hosted LangGraph Developer Spike — Spike B (0.5 day)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S0.3.1** | As a **developer**, I want to verify that self-hosted LangGraph Developer can be embedded in a FastAPI app and serve the Agent Protocol on `/agent/*` routes, so that we can avoid LangGraph Platform Cloud SaaS Plus costs. | **Architecture**: Validates H10 (LGP-SHL↔existing graph) and H11 (self-hosted in Cloud Run). Embedded server loads `orchestration.react_loop:build_graph` via `langgraph.json` — never by importing `orchestration/` directly **[F4, M1]**. **Style Guide**: `middleware/` may only import from `services/`, `trust/`, `agent_ui_adapter/wire/` **[§3.2]**. **Code Review [FD1]**: `middleware/` → `orchestration/` import is FORBIDDEN (accessed via `langgraph.json` config only). **Test**: `curl -N` against local FastAPI streams multi-event SSE response; checkpoints land in local Postgres. **DoD**: Agent Protocol routes serve events from the existing graph; **PASS** → use self-hosted; **FAIL** → switch to LGP Cloud SaaS Plus per V2-Frontier. |

### Epic 0.4: Mem0 Cloud Hobby Spike — Spike C (0.5 day)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S0.4.1** | As a **developer**, I want to verify that Mem0 Cloud Hobby `add()` + `search()` round-trips complete in <200ms from Cloud Run, so that F15 (memory) does not degrade TTFT. | **Architecture**: Validates H5 (Mem0 <200ms recall). Mem0 client must be in `middleware/adapters/memory/` only **[A1, F-R2, F-R9]**. BFF must never hold Mem0 credentials. **Style Guide**: Memory client must implement `MemoryClient` port **[P1, P2]**; no Mem0 SDK types in return values **[A4, F-R8]**. **Code Review [FD1.A1, FD3.SEC1]**: SDK isolation; no `MEM0_API_KEY` in `NEXT_PUBLIC_*`. **Test**: Timed round-trip test; p95 <200ms with 100 memories. **DoD**: Mem0 Cloud Hobby serves within latency budget; quota consumption documented; **FAIL** → defer F15 to v1.5. — **Outcome (2026-04-23)**: ⚠️ measurement FAILED (search p95 = 447.6 ms) but **ACCEPTED with documented latency debt** per Decision **D-S0-8** (V1 fallback **not** invoked). Mem0 stays in v1; alternatives shortlist preserved at [spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md](spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md). See [spike_reports/SPIKE_C.md §6](spike_reports/SPIKE_C.md#6-decision-update--accepted-with-latency-debt-2026-04-23). |

### Epic 0.5: Langfuse Cloud Hobby Spike — Spike D (1 day)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S0.5.1** | As a **developer**, I want to verify that Langfuse Cloud Hobby SDK captures a traced LangGraph run as a structured trace with prompt versions and tool spans, so that F16 (observability) works on the free tier. | **Architecture**: Validates H6 (Langfuse traces with prompt versions). Langfuse exporter must be in `middleware/adapters/observability/` only **[A1, F-R2]**. Telemetry must never block SSE **[O1]**. **Style Guide**: `TelemetryExporter` port must swallow failures silently **[O1]**; `trace_id` propagated from Python runtime **[F-R7, O4]**. **Code Review [FD1.A1, FD2.O1-O4]**: SDK isolation; observability rules. **Test**: A traced run lands in Langfuse Cloud with correct `trace_id`, tool spans, and node hierarchy. **DoD**: Trace lands correctly; quota consumption documented; **FAIL** → use Cloud Trace + Cloud Logging only. |

---

## Sprint 1 — Middleware + Self-Hosted LangGraph (3 days)

**Goal**: Stand up the Python middleware with WorkOS auth verification, tool ACL, and the self-hosted LangGraph Developer runtime.

### Epic 1.1: Middleware Server + LangGraph Embedding

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S1.1.1** | As a **developer**, I want `middleware/server.py` to boot a FastAPI app embedding the self-hosted LangGraph Developer with the `react_loop` graph registered via `langgraph.json`, so that the Agent Protocol surface is available over HTTP. | **Architecture**: `middleware/` is a thin orchestration adapter, peer to `cli.py` **[§3.2]**. Loads graph via `langgraph.json` config — never by Python module import of `orchestration/` **[F4, M1]**. Composition root is `middleware/composition.py` **[C1]**. **Style Guide**: Only `middleware/composition.py` may read `ARCHITECTURE_PROFILE` **[F1, C1, C5]**. `middleware/` may import from `services/`, `trust/`, `agent_ui_adapter/wire/` only **[M1]**. **Code Review [FD1.F1, FD1.F4, FD1.dep]**: All files pass dependency checks. No `orchestration/` import **[FD7.AP13 equivalent]**. **Test**: `tests/architecture/test_middleware_layer.py` passes (import-graph assertion). `curl -N` against running server streams SSE events. Existing `pytest tests/ -q` still green. `python -m agent.cli "…"` unchanged. **DoD**: Server boots; graph loads via config; Agent Protocol routes respond; architecture test green; existing tests unchanged. |
| **S1.1.2** | As a **developer**, I want `middleware/composition.py` to wire V3-Dev-Tier adapters (WorkOS verifier, Mem0 Cloud client, Langfuse Cloud exporter) with a `v2`/`v3` profile switch, so that substrate swaps are composition-root-only. | **Architecture**: Single profile switch in composition root **[C1, F3]**. Adapters injected by port interface only **[C2]**. **Style Guide**: `if _profile == "v2"` appears only in `middleware/composition.py` **[C1]**. Env reads only here **[C4, C5]**. **Code Review [FD1.F1, FD2.C1-C5]**: No `ARCHITECTURE_PROFILE` outside composition root. **Test**: Composition function returns correctly typed `(JwtVerifier, MemoryProvider, TelemetryExporter)` tuple for both profiles. **DoD**: Both V3 and V2 adapter wiring works via profile switch; no env reads outside composition root. |

### Epic 1.2: WorkOS Auth Middleware

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S1.2.1** | As a **security engineer**, I want `middleware/adapters/auth/workos_jwt_verifier.py` to verify WorkOS access tokens against JWKs, rejecting invalid/expired/wrong-issuer tokens, so that all API calls are authenticated. | **Architecture**: Implements `JwtVerifier` protocol in `middleware/ports/jwt_verifier.py` **[P1, P2]**. WorkOS SDK import only in `middleware/adapters/auth/` **[A1, F-R2]**. No WorkOS SDK types in return values **[A4, F-R8]**. **Style Guide**: Rejection paths tested first per TAP-4 **[FD6.ADAPTER]**. Error translation table in docstring **[A5]**. Idempotent behavior **[A6]**. Per-adapter logger `middleware.adapters.auth` **[A7, O3]**. **Code Review [FD1.A1, FD2.A4-A9, FD3.SEC2, FD6.ADAPTER]**: SDK isolation; no JWT in localStorage; rejection-first tests. **Test**: `tests/middleware/test_workos_auth.py` — rejection paths FIRST: (1) missing token → 401, (2) expired token → 401, (3) wrong issuer → 401, (4) wrong `client_id` → 401, (5) wrong `token_use` → 401, THEN (6) valid token → acceptance. All 5 rejection tests before happy path. **DoD**: 5+ rejection tests pass before 1 acceptance test; architecture constraints met; adapter conformance test registered. |

### Epic 1.3: Tool ACL Middleware

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S1.3.1** | As a **security engineer**, I want `middleware/` to enforce per-WorkOS-group tool allowlists (admin → all tools; beta → no `shell`), so that the `shell` tool is never exposed to non-admin users **[R3]**. | **Architecture**: Tool ACL is a middleware concern, not a component or service concern **[§3.2]**. WorkOS organization membership + custom roles claim drives the decision. **Style Guide**: No domain logic leaks into components **[F-R1]**. Tool gating is adapter-level **[A1]**. **Code Review [FD3, FD7.AP3]**: Security (tool gating); no business logic in Route Handlers — tool ACL is in middleware, not BFF. **Test**: `tests/middleware/test_tool_acl.py` — rejection paths FIRST: (1) beta user calling `shell` → 403, (2) unknown group → 403, THEN (3) admin user calling `shell` → 200, (4) beta user calling `file_io` → 200. **DoD**: Shell tool blocked for non-admin; rejection tests pass first; architecture test passes. |

### Epic 1.4: Architecture Tests (Python)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S1.4.1** | As an **architect**, I want `tests/architecture/test_middleware_layer.py` to enforce that `middleware/` does not import from `components/`, `orchestration/`, `governance/`, or `services/` directly, and that nothing in the four-layer backend imports from `middleware/`, so that the dependency direction is enforced. | **Architecture**: Enforces **M1**, **F4**. Walks import graph using `importlib`. **Style Guide**: Mirrors backend `test_api_layer.py` pattern. **Code Review**: This IS the enforcement mechanism for **FD1** layering checks. **Test**: Self-referential — the test IS the test. Must pass `pytest tests/architecture/ -q`. **DoD**: Architecture test exists, passes, and is in CI. Any import violation fails the build. |

---

## Sprint 2 — Dev-Tier Infrastructure (2 days)

**Goal**: Provision all V3-Dev-Tier cloud infrastructure via OpenTofu.

### Epic 2.1: Dev-Tier OpenTofu Stacks

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S2.1.1** | As a **DevOps engineer**, I want `infra/dev-tier/cloud-run.tf` to provision Cloud Run service `agent-middleware` with `min=0`, 1 vCPU/2 GB, timeout=3600s, startup CPU boost, so that the middleware runs on GCP free tier. | **Architecture**: Cloud Run min=0 accepts ~100ms cold start **[H11]**. Timeout=3600s accommodates long ReAct runs **[H6']**. **Style Guide**: N/A (infrastructure). **Code Review**: N/A (Terraform/OpenTofu). **Test**: `tofu plan` succeeds; `tofu apply` creates the service; `/healthz` returns 200. **DoD**: Cloud Run service running; SSE streams byte-for-byte; cold start <200ms with startup CPU boost. |
| **S2.1.2** | As a **DevOps engineer**, I want `infra/dev-tier/neon.tf` to provision 1 Neon Free project for `agent_app` with pgvector enabled, so that the database is ready for checkpoints and app schema. | **Architecture**: Neon Free provides 0.5 GB + 100 CU-hr; scale-to-zero after 5 min **[H14]**. `tablesFilter` in Drizzle config must exclude LangGraph checkpoint tables. **Style Guide**: N/A. **Code Review**: N/A. **Test**: Connection succeeds; pgvector extension available; LangGraph checkpoint migration runs. **DoD**: Neon project live; connection string in Secret Manager; pgvector ready. |
| **S2.1.3** | As a **DevOps engineer**, I want `infra/dev-tier/cloudflare-pages.tf` + `cloudflare-edge.tf` to provision Cloudflare Pages project + Free zone with basic WAF, so that the frontend has a hosting target with native SSE streaming support. | **Architecture**: Cloudflare streams SSE without special cache config **[H2, ev_v2f_11]** — no `CachingDisabled` workaround needed (unlike V1 CloudFront). **Style Guide**: N/A. **Code Review**: N/A. **Test**: `wrangler pages deploy` succeeds; WAF managed ruleset active in count mode; SSE test endpoint streams byte-for-byte. **DoD**: Cloudflare Pages + edge configured; WAF in count mode for 24h. |
| **S2.1.4** | As a **DevOps engineer**, I want secrets (WorkOS, OpenAI, Anthropic, Langfuse, Mem0, Neon) stored in GCP Secret Manager and referenced by the Cloud Run service, so that no credentials are hardcoded. | **Architecture**: All credential-bearing calls flow through `middleware/` **[F-R9, S2]**. BFF holds only public env vars (`WORKOS_CLIENT_ID`, `MIDDLEWARE_URL`). **Style Guide**: No `NEXT_PUBLIC_*` containing `*KEY*`, `*SECRET*`, `*TOKEN*` **[FD3.SEC1, FE-AP-18 AUTO-REJECT]**. **Code Review [FD3.SEC1]**: No secrets in public env. **Test**: Cloud Run service reads secrets at runtime; env dump confirms no secret in frontend env. **DoD**: All secrets in Secret Manager; Cloud Run accesses them via IAM role; no secrets in frontend env. |

---

## Sprint 3 — Frontend Integration (5 days)

**Goal**: Build the Next.js 15 frontend with CopilotKit, WorkOS auth, all tool UIs, generative UI, and the full port/adapter/wire/translator architecture.

### Epic 3.1: Wire Kernels + Trust-View

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.1.1** | As a **developer**, I want `frontend/lib/wire/domain_events.ts`, `agent_protocol.ts`, `ag_ui_events.ts`, and `ui_runtime_events.ts` to define all TypeScript Zod schemas mirroring the Python `agent_ui_adapter/wire/` modules, so that the frontend has a pure shared kernel. | **Architecture**: `wire/` is the innermost ring; imports only `zod` and stdlib **[W1]**. Every event extends `BaseEvent` with `trace_id` **[W5]**. Mirrors Python source of truth **[W2]**. **Style Guide**: `z.discriminatedUnion("type", [...])` for multi-variant types **[W3]**. snake_case on wire **[W6]**. Schema const + inferred type co-export **[W7]**. No SDK, no React, no I/O **[W1]**. **Code Review [FD1.dep, FD2.W1-W8, FD7.AP14]**: Wire imports nothing outward; all wire rules pass; no schema drift. **Test**: `check_wire_purity` passes on all 4 files. `__python_schema_baseline__.json` committed alongside. `tsc --noEmit` clean **[FD6.TSC]**. Vitest unit tests per discriminated-union variant **[T4]**. **DoD**: All 4 wire modules exist; Zod schemas match Python baseline; no outward imports; baseline JSON committed; unit tests pass. |
| **S3.1.2** | As a **developer**, I want `frontend/lib/trust-view/identity.ts` to define read-only Zod schemas for `IdentityClaim`, `AgentFactsView`, `PolicyDecisionView`, and `RunIdentity`, so that the frontend can display trust information without mutation capability. | **Architecture**: `trust-view/` exports only `z.infer<...>` types **[W8, F-R6]**. No functions, no mutable state. Imports only `zod` **[W1]**. **Style Guide**: Read-only subset of `trust/models.py` — no signing, no verification **[§4 FRONTEND_WIRE_AND_TRANSLATORS_DEEP_DIVE]**. **Code Review [FD1.dep, FD2.W8, FD7.AP6]**: No sealed envelope mutation. **Test**: `check_wire_purity` passes. `tsc --noEmit` clean. **DoD**: Trust-view module exists; read-only shapes only; no outward imports. |

### Epic 3.2: Port Interfaces

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.2.1** | As a **developer**, I want the 8 port interfaces (`AgentRuntimeClient`, `AuthProvider`, `ThreadStore`, `MemoryClient`, `TelemetrySink`, `FeatureFlagProvider`, `ToolRendererRegistry`, `UIRuntime`) defined in `frontend/lib/ports/`, so that all adapter wiring goes through vendor-neutral contracts. | **Architecture**: One interface per file **[P1, F-R3]**. Vendor-neutral names **[P2]**. Method signatures use `wire/` types only **[A4, F-R8]**. Behavioral contracts in JSDoc **[P3]**. **Style Guide**: Async by default **[P5]**. Typed errors via `@throws` **[P4]**. No imports from `adapters/`, `translators/`, `transport/`, `composition.ts` **[P6]**. **Code Review [FD1.dep, FD2.P1-P7, FD6.PORT]**: Port imports only wire/+trust-view/; all port rules pass; conformance test presence. **Test**: `check_port_conformance` passes for each port. Each port has a corresponding entry in `frontend/tests/architecture/test_port_conformance.ts` **[P7, FD6.PORT]**. `tsc --noEmit` clean. **DoD**: 8 port files, each with 1 interface, JSDoc contracts, typed errors; conformance test skeleton registered for each. |

### Epic 3.3: Adapters

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.3.1** | As a **developer**, I want `SelfHostedLangGraphDevClient` (V3) and `LangGraphPlatformSaaSClient` (V2) adapters implementing `AgentRuntimeClient`, so that the runtime can be swapped between self-hosted and managed by changing the profile. | **Architecture**: SDK imports only in `adapters/runtime/` **[A1, F-R2]**. No SDK types in return values — all returns are `wire/` shapes **[A4, F-R8]**. No cross-adapter imports **[A2]**. `trace_id` forwarded from backend, never generated browser-side **[F-R7, FE-AP-7 AUTO-REJECT]**. `cancel()` idempotent **[A6]**. Last event is `RunCompletedEvent` or `RunErrorEvent` **[Runtime Contract §1]**. **Style Guide**: Error translation table in JSDoc **[A5]**. SDK pin in JSDoc **[A9]**. Per-family logger `frontend:adapter:runtime` **[A7, O3]**. No PII in logs **[O2]**. `Last-Event-ID` reconnection **[X3]**. **Code Review [FD1.A1, FD2.A1-A10, FD3.TRUST2, FD6.ADAPTER, FD7.AP1/AP2/AP7/AP13/AP15]**: All adapter rules; no browser trace_id generation; rejection-paths-first tests. **Test**: Failure-paths-first: (1) 401→`AgentAuthError`, (2) 403→`AgentAuthorizationError`, (3) 429→`AgentRateLimitError`, (4) 5xx→`AgentServerError`, (5) timeout→`AgentNetworkError` BEFORE happy-path. Port conformance tests pass. Idempotent cancel test. `tsc --noEmit` clean. **DoD**: Both adapters exist; error translation tested; SDK types confined; conformance suite passes; rejection tests before happy path. |
| **S3.3.2** | As a **developer**, I want `WorkOSAuthKitAdapter` implementing `AuthProvider`, so that authentication is handled via WorkOS with auto-refresh on token expiry. | **Architecture**: WorkOS SDK import only in `adapters/auth/` **[A1, F-R2]**. `getAccessToken()` refreshes if <60s to expiry **[S1]**. `getSession()` returns `null` not throws **[behavioral contract]**. `signOut()` clears all local state. **Style Guide**: No WorkOS SDK type (`WorkOSSession`) in any return — convert to `Session` wire shape **[A4, F-R8]**. JWT verified server-side **[S3]**. **Code Review [FD1.A1, FD2.A4, FD3.SEC2]**: No JWT in localStorage. **Test**: Rejection-paths-first; token refresh test; session-null test. **DoD**: Adapter works; no SDK type leakage; token refresh verified. |
| **S3.3.3** | As a **developer**, I want `NeonFreeThreadStore` (V3) and `CloudSQLThreadStore` (V2) adapters implementing `ThreadStore`, so that thread CRUD works against the database. | **Architecture**: Drizzle + `@neondatabase/serverless` in `adapters/thread_store/` only **[A1]**. `tablesFilter` in `drizzle.config.ts` excludes LangGraph checkpoint tables. Runs in BFF Route Handler — server-side only. **Style Guide**: Soft delete (sets `archived_at`) **[behavioral contract]**. Cursor-based pagination. Typed `ThreadStoreError` on all errors **[P4]**. **Code Review [FD1.A1, FD2.A4-A5, FD6.ADAPTER]**: SDK isolation; error translation; failure-paths-first. **Test**: Failure-paths-first; CRUD operations verified; pagination test. **DoD**: Both adapters exist; Drizzle migration excludes checkpoint tables; tests pass. |
| **S3.3.4** | As a **developer**, I want `CopilotKitUIRuntime` implementing `UIRuntime` and `CopilotKitRegistryAdapter` implementing `ToolRendererRegistry`, so that the chat UI framework is adapter-isolated. | **Architecture**: CopilotKit SDK imports only in `adapters/ui_runtime/` and `adapters/tool_renderer/` **[A1, F-R2]**. Provider wraps layout with `<CopilotKit runtimeUrl="/api/copilotkit">`. Built-in tool registrations: `shell`→`ShellToolUI`, `file_io`→`FileIOToolUI`, `web_search`→`WebSearchToolUI`, `analysis_output`→`PyramidPanel` (feature-flagged), `*`→`GenericJsonToolUI`. **Style Guide**: `useToolRenderer()` wraps `useFrontendTool` (Static AG-UI) and `useComponent` (Open AG-UI) **[§5.8/5.9 PORTS_AND_ADAPTERS_DEEP_DIVE]**. Provider must not perform side effects at render time. **Code Review [FD1.A1, FD2.A4, FD7.AP10/AP13/AP20]**: No parallel client store; SDK isolation; barrel import via `next/dynamic`. **Test**: Port conformance; tool registration; rendering test. **DoD**: CopilotKit confined to adapters; tool registration works; no SDK type leakage. |
| **S3.3.5** | As a **developer**, I want `EnvVarFlagsAdapter` implementing `FeatureFlagProvider`, so that features (voice, pyramid_panel, per_tool_authorization, json_run_export) can be dark-launched via env vars. | **Architecture**: Synchronous reads **[P5 exception documented]**. Reads `NEXT_PUBLIC_FF_*` at module load time. Unknown flags return default. **Style Guide**: No async dependencies **[C4, C5]** — env reads only in composition. **Code Review [FD2.P5]**: Sync justification documented. **Test**: Flag presence/absence tests; unknown flag returns default. **DoD**: Feature flags work; pyramid_panel and voice_mode off by default. |

### Epic 3.4: Translators

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.4.1** | As a **developer**, I want the 4 translator modules (`ag_ui_to_ui_runtime.ts`, `ui_input_to_agent_request.ts`, `sealed_envelope.ts`, `tool_event_to_renderer_request.ts`) in `frontend/lib/translators/`, so that wire shapes are converted to UI shapes via pure functions. | **Architecture**: Imports only `wire/` and `trust-view/` **[T1]**. No I/O, no SDK, no React **[T1]**. `trace_id` forwarded from input to every output shape **[T2, F-R7]**. Zero-or-many output rule documented **[T3]**. **Style Guide**: Table-driven Vitest tests co-located as `*.test.ts` **[T4]**. One test per discriminated-union variant. Pure functions: given same input, always same output. **Code Review [FD1.dep, FD2.T1-T4, FD7.AP17]**: Translators → wire/trust-view/ only; all translator rules; no localStorage/fetch/document access. **Test**: Each translator has co-located `*.test.ts`. Every AG-UI event type has a test case mapping to the expected UI output. `trace_id` forwarding verified for every mapping. `tsc --noEmit` clean. **DoD**: 4 translator modules; all pure; trace_id forwarded everywhere; table-driven tests pass; no I/O or SDK imports. |

### Epic 3.5: Transport

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.5.1** | As a **developer**, I want `frontend/lib/transport/sse_client.ts` with typed `EventSource`, `Last-Event-ID` resumption, heartbeat detection (15s/30s), backpressure (100-event buffer), and retry policy, so that SSE streaming is reliable. | **Architecture**: Imports from `wire/` only **[X1]**. `EventSource` only in this file **[X1, FD2.X1]**. Zod-parse on receive **[X2]** — failures synthesize `RunErrorEvent` with `error_type: "wire_parse_error"`. **Style Guide**: `Last-Event-ID` non-optional **[X3]**. Heartbeat thresholds match Python `transport/heartbeat.py` **[X4]**. Backpressure: 100-event buffer, drop-oldest **[X5]**. **Code Review [FD2.X1-X5, FD5.STREAM, FD5.HDR]**: All transport rules. **Test**: Unit tests for reconnect, heartbeat timeout, backpressure overflow, Zod parse failure. **DoD**: SSE client handles all edge cases; heartbeat/backpressure/resumption all tested. |
| **S3.5.2** | As a **developer**, I want `frontend/lib/transport/edge_proxy.ts` as a BFF Route Handler helper that forwards SSE byte-for-byte, setting required headers and stripping `Accept-Encoding`, so that streaming works through Cloudflare. | **Architecture**: Runs server-side only (BFF) **[B7]**. Sets `Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, `Connection: keep-alive` **[X6]**. Strips `Accept-Encoding` on streaming routes **[X6]**. **Style Guide**: Edge runtime opt-in only for this file **[B7]**. No business logic **[B6, F-R4]**. **Code Review [FD5.HDR, FD5.STREAM, FD2.B6-B7]**: Header verification. **Test**: Header verification test; Accept-Encoding strip test. **DoD**: Proxy sets all required headers; Cloudflare streams without buffering. |

### Epic 3.6: Composition Root

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.6.1** | As a **developer**, I want `frontend/lib/composition.ts` to wire all 8 port implementations based on `ARCHITECTURE_PROFILE` (v3 default, v2 graduation), and provide them via React context, so that all downstream code receives adapters through port interfaces only. | **Architecture**: The ONLY file that names concrete adapter classes **[C1]**. Single profile switch **[C1, F1]**. Exports `buildAdapters()` returning typed port bag **[C2]**. React context provision via `<AdapterProvider>` **[C3]**. All env reads happen here **[C4, C5]**. **Style Guide**: No other file may contain `process.env.ARCHITECTURE_PROFILE` **[F1, C1, FD1.F1]**. **Code Review [FD1.F1, FD2.C1-C5]**: `search_codebase("ARCHITECTURE_PROFILE", "frontend/**/*.ts")` returns only `composition.ts`. **Test**: Architecture test: no other file imports adapters directly. Both profiles wire correctly. **DoD**: Composition root is the single wiring point; profile switch works; context provides all adapters. |

### Epic 3.7: App Scaffold + Auth

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.7.1** | As a **user**, I want to sign in via WorkOS AuthKit (email + OTP) on the Next.js 15 app, so that I can access the chat interface. | **Architecture**: Auth handled by `WorkOSAuthKitAdapter` behind `AuthProvider` port. BFF Route Handler `/api/auth/[...workos]/route.ts` is a composition adapter **[F-R4, B6]**. **Style Guide**: `'use client'` only on sign-in form components with inline justification **[B1, U2]**. `await cookies()` and `await headers()` per Next.js 15 contract **[B3]**. JWT stored in `HttpOnly, Secure, SameSite=Strict` cookies **[FD3.SEC2]** — NEVER localStorage. **Code Review [FD3.SEC2, FD3.HDR1, FD2.B1-B6, FD7.AP18]**: No JWT in localStorage; security headers; BFF no credentials. **Test**: Sign-in flow works end-to-end against WorkOS; OTP verification; session persistence; sign-out clears state. **DoD**: Auth flow works; JWT in HttpOnly cookies; security headers set in `middleware.ts`. |
| **S3.7.2** | As a **security engineer**, I want `frontend/middleware.ts` to set strict CSP headers (nonce-based, no `unsafe-inline`, no `unsafe-eval`) and security headers (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy), so that the app is hardened against XSS. | **Architecture**: CSP nonce generated per request; root `app/layout.tsx` calls `await headers()` **[FD3.CSP3]**. **Style Guide**: CSP template per §19 of STYLE_GUIDE_FRONTEND.md. No `'unsafe-inline'` **[FE-AP-19 AUTO-REJECT]**. No `'unsafe-eval'`. `frame-ancestors 'none'`. **Code Review [FD3.CSP1, FD3.CSP2, FD3.HDR1]**: All AUTO-REJECT hypotheses. `check_csp_strict` must PASS. **Test**: `check_csp_strict("frontend/middleware.ts")` passes. Security header presence verified. **DoD**: CSP strict; all security headers present; no unsafe-inline/eval. |

### Epic 3.8: Chat UI Components

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.8.1** | As a **user**, I want to see a streaming markdown chat with syntax-highlighted code blocks, copy button, model badge, and step/cost meter, so that I have a Claude-class chat experience **[F2, F6, F7]**. | **Architecture**: Components receive typed props and render — no domain logic **[F-R1]**. `StepMeter` (F6, ~50 LOC) and `ModelBadge` (F7, ~30 LOC) are custom components reading from `useCoAgentStateRender`. CopilotKit SDK used only in adapters **[F-R2]**. **Style Guide**: RSC by default **[B1, U1]**. `'use client'` only with justification **[B1]**. `cn()` for class merging **[U6]**. shadcn primitives **[U7]**. Design tokens via Tailwind v4 `@theme` **[U8]**. `next-themes` for dark mode **[§2]**. **Code Review [FD2.U1-U8, FD2.B1, FD4.U4, FD4.U5, FD5.BUDGET, FD7.AP5/AP10/AP11]**: UI rules; use-client justification; ARIA live; focus management; bundle budget. **Test**: Vitest + React Testing Library unit tests. `eslint-plugin-jsx-a11y` passes **[FD4.JSX]**. Storybook story exists **[FD6.STORY]**. `tsc --noEmit` clean. **DoD**: Chat renders streaming markdown; model badge and step meter update in real-time; dark/light theme works; ARIA live region is `aria-live="polite"` (never `assertive` **[FE-AP-5]**); a11y lint clean. |
| **S3.8.2** | As a **user**, I want collapsible tool-call cards for `shell`, `file_io`, and `web_search` with JSON input/output rendering, so that I can see what tools the agent used **[F5]**. | **Architecture**: Tool cards registered via `ToolRendererRegistry` port **[§5.9]**. Each card is a `useFrontendTool` (Static AG-UI) component. Input narrowed with Zod per-tool **[ToolRendererProps contract]**. **Style Guide**: Tool cards under `frontend/components/tools/` **[§3.1]**. Each has a sibling `*.stories.tsx` **[FD6.STORY]**. No CopilotKit import in the component itself — CopilotKit is in the adapter **[F-R2, A1]**. **Code Review [FD2.A4, FD6.STORY, FD7.AP13]**: No SDK type in props; Storybook coverage; no direct CopilotKit import. **Test**: Storybook stories for each tool card. Unit tests with mock `ToolRendererProps`. `eslint-plugin-jsx-a11y` passes. **DoD**: 3 tool cards + 1 generic fallback; each with Storybook story; collapsible UI; no SDK imports outside adapters. |
| **S3.8.3** | As a **user**, I want a generative-UI canvas (F13) rendering agent-generated HTML in a sandboxed iframe, so that the agent can produce charts, diagrams, and visualizations. | **Architecture**: `useComponent` (Open AG-UI) renders into `<iframe sandbox="allow-scripts">` ONLY **[U3]**. No `allow-same-origin` **[FE-AP-4 AUTO-REJECT]**. Content via `srcDoc` **[§19]**. CSP `frame-src 'self'`. **Style Guide**: No `dangerouslySetInnerHTML` **[FE-AP-12 AUTO-REJECT]**. Component under `frontend/components/generative/` with Storybook story **[FD6.STORY]**. **Code Review [FD3.SBX1, FD3.SBX2, FD7.AP4, FD7.AP12]**: AUTO-REJECT if sandbox tokens wrong or dangerouslySetInnerHTML used. **Test**: `check_iframe_sandbox` passes. Storybook story renders sandboxed content. XSS attempt test (script in srcDoc cannot access parent). **DoD**: Generative UI renders in sandboxed iframe; sandbox has ONLY `allow-scripts`; Storybook story exists; XSS boundary verified. |
| **S3.8.4** | As a **user**, I want a Pyramid panel (F14) rendering `StructuredReasoning` analysis output as an interactive issue tree, so that I can see the agent's reasoning structure. | **Architecture**: Feature-flagged behind `pyramid_panel` **[FeatureFlag]**. Rendered via `useComponent` → `PyramidPanel`. Under `frontend/components/generative/`. **Style Guide**: Same sandbox rules as F13 **[U3, FE-AP-4]**. Feature flag checked synchronously **[P5]**. **Code Review**: Same as S3.8.3 plus **FD2** pattern checks. **Test**: Storybook story with mock `analysis_output` JSON. Feature flag off → not rendered. **DoD**: Pyramid panel renders; feature-flagged off by default; sandboxed; Storybook story exists. |
| **S3.8.5** | As a **user**, I want a mobile-first responsive composer with ⌘↩ / Ctrl↩ to send and mobile-keyboard-friendly behavior, so that I can chat comfortably on any device **[F4]**. | **Architecture**: Composer provided by CopilotKit via `UIRuntime` port adapter **[§5.8]**. **Style Guide**: Tailwind responsive utilities **[U8]**. `cn()` for class merging **[U6]**. **Code Review [FD2.U1-U8]**: UI rules. **Test**: Vitest unit tests. Mobile layout reviewed on iOS Safari + Android Chrome. **DoD**: Composer works on desktop and mobile; keyboard shortcuts work; responsive breakpoints verified. |
| **S3.8.6** | As a **user**, I want a thread sidebar with rename, archive, delete, and search-by-title, so that I can manage my conversations **[F1]**. | **Architecture**: Thread sidebar reads from `ThreadStore` port **[§4.3]**. CopilotKit `CopilotChat` thread management via AG-UI. **Style Guide**: RSC for the sidebar shell **[B1, U1]**. `'use client'` pushed to leaf interactive elements only **[U2]**. **Code Review [FD2.U1-U2, FD2.B1]**: RSC by default; leaf client boundary. **Test**: Unit tests for CRUD operations; search test. **DoD**: Thread sidebar works; rename/archive/delete functional; search by title works. |
| **S3.8.7** | As a **user**, I want stop/regenerate/edit-and-resend-last-message controls, so that I can manage my conversations interactively **[F3]**. | **Architecture**: CopilotKit `useThreadRuntime()` actions (built-in) via `UIRuntime` port **[§5.8]**. Stop → `AgentRuntimeClient.cancel()` (idempotent **[A6]**). **Style Guide**: N/A. **Code Review [FD2.A6]**: Idempotent cancel. **Test**: Stop cancels mid-run. Regenerate creates new run. Edit-and-resend works. **DoD**: All three controls work end-to-end. |
| **S3.8.8** | As a **user**, I want light/dark theme toggle persisted in localStorage, so that my preference is remembered **[F9]**. | **Architecture**: `next-themes` + `[data-theme="dark"]` CSS variable overrides **[§2]**. **Style Guide**: Design tokens via Tailwind v4 `@theme` **[U8]**. Claude-desktop-like palette (off-white `#f9f7f5` light, near-black `#1f1e1d` dark). **Code Review [FD2.U8]**: Theme tokens. **Test**: Theme toggles correctly; persists across reload. **DoD**: Theme toggle works; persists in localStorage; palette matches spec. |

### Epic 3.9: BFF Route Handlers

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.9.1** | As a **developer**, I want BFF Route Handlers (`/api/threads/*`, `/api/run/stream`, `/api/run/cancel`) that proxy to the middleware with SSE byte-forwarding, so that the browser communicates with the backend via the BFF. | **Architecture**: Route Handlers are composition adapters — port calls and SSE byte-forward only **[F-R4, B6]**. No business logic `if/else` **[FE-AP-3]**. `edge_proxy.ts` used for SSE forwarding **[X6]**. `Authorization: Bearer <token>` forwarded **[S2]**. **Style Guide**: `cache: 'no-store'` on user-scoped routes **[B5]**. Server Actions for UI-triggered mutations **[B4]**. **Code Review [FD2.B4-B6, FD5.CACHE, FD5.STREAM, FD5.HDR, FD7.AP3]**: Browser process rules; cache policy; streaming headers; no business logic in Route Handler. **Test**: Route handler tests with mocked middleware responses. SSE streaming test. **DoD**: All routes work; SSE streams byte-for-byte; no business logic in handlers; cache policy correct. |

### Epic 3.10: Architecture Test Suite (TypeScript)

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.10.1** | As an **architect**, I want `tests/architecture/test_frontend_layering.ts` using `ts-morph` to walk the import graph and enforce F-R1, F-R2, F-R3, F-R8, so that architectural violations are caught in CI. | **Architecture**: Enforces the §10 dependency direction table from FRONTEND_ARCHITECTURE.md **[F-R1, F-R2, F-R3, F-R8]**. This IS the **FD1** enforcement mechanism. **Style Guide**: Mirrors the `THIRD_PARTY_SDK_PACKAGES` list from §2. **Code Review**: This IS the `check_frontend_dependency_rules` tool's backing logic. **Test**: Self-referential — test must pass on the current codebase. Intentionally wrong import in a test fixture must fail. **DoD**: Architecture test exists; catches SDK imports outside adapters; catches cross-layer violations; runs in CI; `tsc --noEmit` clean. |

### Epic 3.11: Wire Schema Drift Detection

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S3.11.1** | As a **developer**, I want a CI job that diffs `frontend/lib/wire/__python_schema_baseline__.json` against live Python JSON Schema exports, so that TypeScript/Python wire schema drift is caught before merge. | **Architecture**: Python side is the single source of truth **[W2]**. Hand-authored TS (not codegen) — explicit human review required **[§8 WIRE_AND_TRANSLATORS_DEEP_DIVE]**. **Style Guide**: `make wire-schema-snapshot` regenerates baseline; both files committed together **[W2]**. **Code Review [FD6.DRIFT, FD7.AP14]**: This IS the `check_wire_drift` tool's backing mechanism. **Test**: Baseline committed; CI diff script exits non-zero on drift. **DoD**: Baseline JSON committed; CI job configured; drift detected and blocked. |

---

## Sprint 4 — Hardening + Private Beta Launch (2 days)

**Goal**: Harden security, set up monitoring, and invite beta users.

### Epic 4.1: Security Hardening

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S4.1.1** | As a **security engineer**, I want Cloudflare Free WAF moved from count mode to enforce mode after 24h observation, WorkOS MFA enforced for all users, and `next.config.ts` hardened (`productionBrowserSourceMaps: false`, explicit `images.remotePatterns`), so that the app is production-ready. | **Architecture**: N/A (operational). **Style Guide**: `productionBrowserSourceMaps: false` **[FD3.SEC3]**. `images.remotePatterns` explicit allowlist **[FD3.SEC4]**. **Code Review [FD3.SEC3, FD3.SEC4]**: Config verification. **Test**: `next.config.ts` inspection confirms settings. WAF enforce mode verified. MFA required for all users. **DoD**: WAF enforcing; MFA on; source maps off; image patterns locked down. |

### Epic 4.2: Monitoring + Alerting

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S4.2.1** | As a **DevOps engineer**, I want Cloud Monitoring alarms for 5xx rate, Cloud Run error rate, Langfuse Cloud Hobby quota at 80%, Mem0 Cloud Hobby quota at 80%, and Neon CU-hr at 80%, so that quota exhaustion and errors are caught before impacting users. | **Architecture**: Neon quota exhaustion (R16) triggers Stage A→B graduation **[§16 cross-branch interaction]**. **Style Guide**: N/A. **Code Review**: N/A. **Test**: Alarms fire on test threshold breach. **DoD**: 5+ alarms configured; quota alarms at 80% trigger notifications; runbook documents Stage A→B upgrade procedure. |

### Epic 4.3: Runbook + Beta Launch

| Story ID | User Story | Acceptance Criteria |
|----------|-----------|---------------------|
| **S4.3.1** | As an **operator**, I want `infra/RUNBOOK.md` documenting normal ops and the Stage A→B→C→D upgrade procedure for each component, so that operations are repeatable. | **Architecture**: Documents the substrate-swap matrix from FRONTEND_ARCHITECTURE.md §7. **Style Guide**: Each component swap is composition-root-only **[F3]**. **Code Review**: N/A (documentation). **Test**: N/A. **DoD**: Runbook covers: Neon quota upgrade, Mem0 Hobby→Starter, Langfuse Hobby→Core, Cloud Run min=0→min=1, Cloudflare Free→Pro, and full V3→V2-Frontier graduation. |
| **S4.3.2** | As a **product owner**, I want 5 external beta users invited, each able to sign in, chat with the agent, see streamed markdown with tool cards and generative UI, and experience <500ms p50 TTFT, so that the private beta is launched. | **Architecture**: All F1-F20 features working (with F14 Pyramid panel and F20 voice dark behind feature flags). **Style Guide**: Mobile layout reviewed on iOS Safari + Android Chrome **[§8 Phase 3 acceptance]**. **Code Review**: Full `ui_component_pr` scope passes on all components. **Test**: End-to-end Playwright smoke test: sign in → create thread → send message → see streamed response with model badge + step meter → see tool card → stop mid-run → regenerate. Mobile responsive check. **DoD**: 5 beta users can use the app; no Sev-2 incident for 7 days; GCP billing shows spend within ±20% of $5-30/mo Stage A projection. |

---

## Cross-Cutting Definition of Done

Every story must satisfy these cross-cutting criteria before being marked complete:

| Category | Requirement | Rule Source |
|----------|------------|-------------|
| **Architecture** | No file outside `adapters/` imports a third-party SDK | F-R2, A1, FD1.A1 |
| **Architecture** | `trace_id` forwarded verbatim through every layer | F-R7, W5, T2, O4 |
| **Architecture** | No domain logic in React components | F-R1 |
| **Architecture** | BFF holds no cloud credentials | F-R9, S2, FE-AP-18 |
| **Architecture** | System prompts in `.j2` files only, not in `.ts` | F-R5 |
| **Architecture** | `trust-view/` is read-only — no mutation | F-R6 |
| **Architecture** | No SDK type escapes past adapter boundary | F-R8, A4 |
| **Style** | `tsc --noEmit` passes with strict settings | FD6.TSC |
| **Style** | No `console.*` outside adapters | FE-AP-9, O3 |
| **Style** | `cn()` for all conditional classes (no template-string ternaries) | U6 |
| **Style** | snake_case on wire; camelCase only after translator | W6 |
| **Security** | No `'unsafe-inline'` or `'unsafe-eval'` in CSP | FE-AP-19 AUTO-REJECT |
| **Security** | All iframes use `sandbox="allow-scripts"` only | U3, FE-AP-4 AUTO-REJECT |
| **Security** | No secrets in `NEXT_PUBLIC_*` env vars | FD3.SEC1, FE-AP-18 AUTO-REJECT |
| **Security** | No `dangerouslySetInnerHTML` on agent output | FE-AP-12 AUTO-REJECT |
| **Security** | No browser-side `trace_id` generation | FE-AP-7 AUTO-REJECT |
| **Security** | No sealed envelope mutation (spread/re-serialize) | FE-AP-6 AUTO-REJECT |
| **Testing** | Rejection paths tested before happy paths (adapters) | FD6.ADAPTER |
| **Testing** | `eslint-plugin-jsx-a11y` passes on all components | FD4.JSX |
| **Testing** | Architecture tests pass (`test_frontend_layering.ts`, `test_middleware_layering.py`) | FD6.ARCH |
| **Testing** | Storybook story for every component under `tools/` and `generative/` | FD6.STORY |
| **A11y** | Streaming text uses `aria-live="polite"`, never `assertive` | U4, FE-AP-5 |
| **A11y** | Focus moves on route change only — never on incoming tokens | U5 |

---

## V2-Frontier Graduation Triggers

These triggers document when each V3-Dev-Tier component should be upgraded to its V2-Frontier paid equivalent. Every upgrade is a composition-root-only change **[F3]** — no `ports/`, `wire/`, `translators/`, or `transport/` files change.

| Component | V3 Adapter | V2 Adapter | Trigger | Swap File |
|-----------|-----------|-----------|---------|-----------|
| Runtime | `SelfHostedLangGraphDevClient` | `LangGraphPlatformSaaSClient` | >100K nodes/mo | `frontend/lib/composition.ts` |
| Thread Store | `NeonFreeThreadStore` | `CloudSQLThreadStore` | DB >0.5 GB or CU-hr exhausted | `frontend/lib/composition.ts` |
| Memory | `Mem0CloudHobbyAdapter` | `SelfHostedMem0Adapter` | >10K adds/mo | `middleware/composition.py` |
| Telemetry | `LangfuseCloudHobbyAdapter` | `SelfHostedLangfuseAdapter` | >50K units/mo or >30-day retention | `middleware/composition.py` |
| Frontend Host | Cloudflare Pages free | Vercel Pro $20/seat | Vercel DX desired | DNS + deploy config |
| Edge | Cloudflare Free | Cloudflare Pro $25/mo | Image optimization needed | `infra/dev-tier/cloudflare-edge.tf` |

---

## V1 Fallback Paths

If any Sprint 0 spike fails, these fallback paths activate:

| Spike | Failure Condition | Fallback | Impact | Sprint 0 outcome |
|-------|-------------------|----------|--------|------------------|
| Spike A (CopilotKit) | CopilotKit doesn't render existing graph's events | Revert to `assistant-ui` per V1 | Lose F13/F14/F17 (generative UI) — defer to v1.5 | ✅ **PASS** (2026-04-23). Fallback not invoked. See [spike_reports/SPIKE_A.md](spike_reports/SPIKE_A.md). |
| Spike B (Self-hosted LangGraph) | Graph doesn't boot in embedded FastAPI | Switch to LGP Cloud SaaS Plus per V2-Frontier | +$89-104/mo cost | ➖ **SKIPPED** per Decision **D-S0-5** — already proven by `agent_ui_adapter/server.py`. See [spike_reports/SPIKE_B.md](spike_reports/SPIKE_B.md). |
| Spike C (Mem0 Cloud) | Latency >500ms p95 | Defer F15 (memory) to v1.5 | No long-term memory in v1 | ⚠️ **PASS (accepted with documented latency debt)** per Decision **D-S0-8** (2026-04-23). Measurement was FAIL (search p95 = 447.6 ms vs 200 ms budget) but Mem0 is **retained in v1**; the V1 fallback was **not invoked**. Alternatives shortlist preserved at [spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md](spike_reports/SPIKE_C_ALTERNATIVES_RESEARCH.md) for future swap. See [spike_reports/SPIKE_C.md §6](spike_reports/SPIKE_C.md#6-decision-update--accepted-with-latency-debt-2026-04-23). |
| Spike D (Langfuse Cloud) | Traces don't land correctly | Use Cloud Trace + Cloud Logging only | Lose prompt versioning in v1 | ➖ **SKIPPED** per Decision **D-S0-6** — V1 fallback (Cloud Trace + Cloud Logging) is the v1 path. See [spike_reports/SPIKE_D.md](spike_reports/SPIKE_D.md). |

---

## Story Summary

| Sprint | Duration | Stories | Key Deliverable |
|--------|----------|---------|-----------------|
| Sprint 0 | 3.5 days | 7 stories | Decisions locked; 4 spikes validated |
| Sprint 1 | 3 days | 5 stories | Python middleware with auth + ACL + LangGraph |
| Sprint 2 | 2 days | 4 stories | GCP + Cloudflare + Neon infrastructure live |
| Sprint 3 | 5 days | 17 stories | Full Next.js frontend with all architecture layers |
| Sprint 4 | 2 days | 4 stories | Security hardened; beta launched |
| **Total** | **15.5 days** | **37 stories** | **Private beta with 5 users** |

---

*This sprint board was produced from [FRONTEND_PLAN_V3_DEV_TIER.md](FRONTEND_PLAN_V3_DEV_TIER.md) (base plan), [FRONTEND_ARCHITECTURE.md](../../Architectures/FRONTEND_ARCHITECTURE.md) (architecture source of truth), [STYLE_GUIDE_FRONTEND.md](../../STYLE_GUIDE_FRONTEND.md) (code-review style guide), and [prompts/codeReviewer/frontend/](../../../prompts/codeReviewer/frontend/) (automated review dimensions FD1-FD7). Every acceptance criterion references specific rule IDs from these documents.*
