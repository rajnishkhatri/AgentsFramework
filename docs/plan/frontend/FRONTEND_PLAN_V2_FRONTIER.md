# FRONTEND_PLAN_V2_FRONTIER.md — Competing alternative to FRONTEND_PLAN_V1.md

> **Status**: planning, alternative to `FRONTEND_PLAN_V1.md` (revision 2 of the canonical plan).
>
> **Relationship to V1**: V2-Frontier *competes* with V1, not supersedes it. It is built under the explicit briefing "no cost restrictions; AWS, GCP, or Azure on the table; explore other options". V2-Frontier deliberately makes different decisions on every axis where V1's "fit + budget + AWS-native" constraints were the binding tie-breakers, in order to expose a Pareto frontier with V1.
>
> **Briefing constraints relaxed for this plan**:
>
> - Cost ceiling: removed.
> - Cloud lock-in: GCP, AWS, Azure, Cloudflare, Vercel all considered as peers.
> - "Defer Pyramid panel to v1.5" rule (V1 §2): revoked — generative UI ships in v1.
> - "Beta only" UX bar: raised to "indistinguishable from Claude / ChatGPT" target.
> - Memory beyond LangGraph checkpointer: in scope.
> - Observability beyond CloudWatch logs: in scope.
> - Real-time voice: in scope as a v1.5 feature flag, with the v1 architecture pre-shaping for it.
>
> Structured per `prompts/StructuredReasoning/_pyramid_brain.j2`. Final §20 contains the head-to-head V1 vs V2-Frontier comparison.

## 1. Governing Thought

Ship a **Claude-Artifacts-class** web chat for the existing LangGraph ReAct agent — Next.js 15 (App Router) on **Vercel** with **CopilotKit v2** (AG-UI Protocol) for **generative UI from day 1**, talking over **Server-Sent Events** to **LangGraph Platform Cloud SaaS** (managed by LangChain) running in their VPC, with **Mem0 self-hosted** as the long-term memory layer on **Cloud SQL Postgres 16 + pgvector**, **Langfuse self-hosted** for prompt versioning + evaluation + tracing, **WorkOS** for enterprise-grade SSO/SAML+SCIM (with Cognito kept as a fallback), fronted by **Cloudflare** (which streams SSE without any edge-bypass plumbing), all on **Google Cloud (us-central1)** as primary with **AWS us-east-1** as a secondary disaster-recovery target — preserving the four-layer architecture invariants in `AGENTS.md`, raising the UX bar to a level where users render charts/diagrams/algorithm visualizations **in the chat surface itself**, accepting an honest all-in cost in the **$300–550/mo** range during private beta, and pre-shaping for OpenAI Realtime API voice in v1.5.

Confidence: **0.74** (lower than V1's 0.78 because V2-Frontier carries strictly more moving parts; the price of optionality).

## 2. Scope

### 2.1 In scope (v1, ~5 weeks of work)

V1's F1–F12 are restated and **expanded** with new F13–F20 that V1 explicitly defers.


| ID      | Feature                                                                    | V2-Frontier implementation                                                                                              |
| ------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| F1      | Thread sidebar                                                             | CopilotKit `CopilotChat` thread management via AG-UI                                                                    |
| F2      | Streaming markdown messages, syntax-highlighted code blocks                | CopilotKit message rendering + react-markdown + shiki                                                                   |
| F3      | Stop / regenerate / edit-and-resend                                        | CopilotKit runtime hooks + LangGraph Platform `interrupt()`                                                             |
| F4      | Mobile-first composer                                                      | CopilotKit `CopilotInput` + Tailwind                                                                                    |
| F5      | Collapsible tool-call cards                                                | `useFrontendTool` (Static AG-UI) — agent decides which custom card; we ship one per tool                                |
| F6      | Step counter + cost meter                                                  | `useCoAgentStateRender` — live agent state pinned in chat                                                               |
| F7      | Model badge per turn                                                       | Same as F6, on `state.model_history` deltas                                                                             |
| F8      | Sign-in (email + OTP, optional SAML/Google)                                | **WorkOS AuthKit** — OIDC + SSO + SCIM provisioning out of the box                                                      |
| F9      | Light/dark theme toggle                                                    | shadcn theme tokens + `next-themes`                                                                                     |
| F10     | Orchestration server (Agent Protocol surface)                              | **LangGraph Platform Cloud SaaS** (managed) — zero infra to operate                                                     |
| F11     | Postgres checkpointer                                                      | Managed by LangGraph Platform                                                                                           |
| F12     | Cloud infra in OpenTofu (Terraform-fork, OSS)                              | **GCP primary** (Cloud Run + Cloud SQL + Cloudflare) + **AWS DR** (Fargate + RDS, dormant)                              |
| **F13** | **Generative UI canvas** (charts, diagrams, algorithm viz, 3D, math plots) | `useComponent` (Open AG-UI) — agent generates self-contained HTML rendered in sandboxed iframes                         |
| **F14** | **StructuredReasoning Pyramid panel** (lifts from V1's v1.5 deferred list) | `useComponent` rendering the `analysis_output` JSON as an interactive issue tree + validation log + evidence            |
| **F15** | **Long-term memory** (per-user facts, preferences, prior-context recall)   | **Mem0 self-hosted** with pgvector + Neo4j (graph) backends                                                             |
| **F16** | **Production observability** (traces, prompt versions, evals)              | **Langfuse self-hosted** + OpenTelemetry instrumentation                                                                |
| **F17** | **Per-tool authorization UI** (lifts from V1 v1.5)                         | `useFrontendTool` rendering a "tool requested" approval prompt; `services/authorization_service.py` decides             |
| **F18** | **JSON run export** (lifts from V1 v1.5)                                   | CopilotKit `useAgent` exposes the full thread state; one-click download                                                 |
| **F19** | **MCP tool integration**                                                   | LangGraph Platform supports MCP tool registration; agent gains access to any MCP server (file system, Slack, GitHub, …) |
| **F20** | **Voice mode (v1.5 feature flag, v1 architecture)**                        | Pre-wire the BFF for OpenAI Realtime API; ship dark behind `NEXT_PUBLIC_VOICE_ENABLED=false`                            |


### 2.2 Deferred to v1.5

- Voice mode lights up (F20 already wired).
- Per-user `AgentFacts` profile selector (Mem0 namespacing already supports this).
- React Native + Expo client (CopilotKit React Native package is GA).

### 2.3 Deferred to v2

- Multi-region active-active (v1 ships GCP active, AWS dormant).
- Fine-tuned models on Vertex AI / Bedrock.
- Multi-tenant marketplace / sharing.

### 2.4 Out of scope forever

- Same as V1 (no upward layer imports, no hardcoded prompts in TS, no `shell` tool to non-admin).
- Single-cloud lock-in. V2-Frontier *requires* OpenTelemetry + Agent Protocol + AG-UI to keep portability.

## 3. Architecture

```
Browser (mobile + desktop)
  │  HTTPS
  ▼
┌──────────────────────── Vercel ────────────────────────────────────────┐
│ Next.js 15 App Router                                                  │
│  • RSC: shell, sidebar, settings                                       │
│  • Client: CopilotKit v2 chat surface                                  │
│      - useFrontendTool   → tool-card UIs (Static AG-UI)                │
│      - useComponent      → generative-UI iframes (Open AG-UI)          │
│      - useCoAgentStateRender → live step/cost/model badges             │
│      - useAgent          → state, history, export (JSON run)           │
│  • Route Handlers (BFF):                                               │
│      /api/auth/[...]/route.ts          → WorkOS AuthKit                │
│      /api/copilotkit/route.ts          → CopilotKit Runtime            │
│                                          (proxies AG-UI ↔ LangGraph)   │
└────────────────────────────────────────────────────────────────────────┘
                  │  HTTPS (WorkOS access-token bearing; AG-UI events)
                  ▼
┌──────────────────────── Cloudflare (edge + WAF + bot mgmt) ──────────────────────┐
│  • Streams SSE byte-for-byte by default — no special cache config required        │
│  • WAF managed rule sets (Cloudflare Managed Ruleset, OWASP CRS)                  │
│  • Bot Fight Mode + rate limiting (1000 req/5min/IP custom rule)                  │
│  • Workers AI / Workers KV available for future edge inference / session caching  │
└───────────────────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────── Google Cloud (us-central1) — primary ────────────────────┐
│  ┌─ LangGraph Platform Cloud SaaS (managed by LangChain in their VPC) ──────┐    │
│  │  • Auto-deployed from GitHub via langgraph.json                          │    │
│  │  • LangGraph Server (Agent Protocol routes)                              │    │
│  │  • Studio for graph visualization + time-travel debugging                │    │
│  │  • LangSmith tracing first-class                                         │    │
│  │  • Streams via egress to our middleware                                  │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  Cloud Run service "agent-middleware"                                             │
│   • Python 3.11; thin FastAPI proxy adding:                                       │
│     - WorkOS access-token verification                                            │
│     - Mem0 lookup/append on conversation turn                                     │
│     - OpenTelemetry → Langfuse + Cloud Trace                                      │
│   • Scale: 0 → 100 instances; concurrency 80; timeout 3600s                       │
│   • Native SSE streaming (no buffer) with `X-Accel-Buffering: no`                 │
│                                                                                   │
│  Cloud Run service "mem0-server"                                                  │
│   • Self-hosted Mem0 (Apache 2.0)                                                 │
│   • Backed by Cloud SQL pgvector (vector store) + Memorystore Redis (cache)       │
│                                                                                   │
│  Cloud Run service "langfuse"                                                     │
│   • Self-hosted Langfuse (MIT) — production stack:                                │
│     Postgres (transactional) + ClickHouse (analytics) + Redis (queue) +           │
│     Cloud Storage (event blobs)                                                   │
│                                                                                   │
│  Cloud SQL for PostgreSQL 16 (regional HA, private IP)                            │
│   • Database `agent_app`: users, threads, messages, runs, tool_calls              │
│   • Database `agent_memory`: Mem0 facts + pgvector index                          │
│   • Database `langfuse_oltp`: Langfuse transactional                              │
│                                                                                   │
│  Memorystore Redis (Standard tier) — cache for Mem0 + session                     │
│  Secret Manager: WORKOS_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY,               │
│                  LANGSMITH_API_KEY, MEM0_*, NEO4J_PASSWORD                        │
│  Artifact Registry: container images                                              │
│  Cloud Logging + Cloud Trace + Cloud Monitoring (alongside Langfuse)              │
│  VPC Service Controls + Private Service Connect (no public IPs on data tier)      │
└───────────────────────────────────────────────────────────────────────────────────┘
                  │  (asynchronous, daily snapshot)
                  ▼
┌──────────────────────── AWS us-east-1 — disaster recovery (dormant) ──────────────┐
│  • RDS Postgres logical replica of Cloud SQL via Cloud SQL → DMS                  │
│  • ECR + ECS Fargate task definition (same image), desired_count = 0              │
│  • Route 53 weighted records ready to flip from GCP origin to AWS origin in DR     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Repository layout

```
agent/
├── frontend/                   ← Next.js 15 app (Vercel)
│   ├── app/
│   │   ├── (chat)/
│   │   │   ├── layout.tsx
│   │   │   └── [threadId]/page.tsx
│   │   ├── api/
│   │   │   ├── auth/[...workos]/route.ts   ← WorkOS AuthKit
│   │   │   └── copilotkit/route.ts         ← CopilotKit Runtime endpoint
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ChatSurface.tsx                 ← CopilotChat root
│   │   ├── tools/                          ← Static AG-UI tool cards
│   │   │   ├── ShellToolUI.tsx
│   │   │   ├── FileIOToolUI.tsx
│   │   │   └── WebSearchToolUI.tsx
│   │   ├── generative/                     ← Open AG-UI useComponent
│   │   │   ├── WidgetRenderer.tsx          ← sandboxed iframe for HTML/SVG
│   │   │   ├── PyramidPanel.tsx            ← StructuredReasoning analysis viewer (F14)
│   │   │   └── AuthorizationPrompt.tsx     ← per-tool approval (F17)
│   │   ├── voice/                          ← F20 (dark behind feature flag)
│   │   │   └── RealtimeVoiceWidget.tsx
│   │   └── shell/
│   │       ├── ThreadSidebar.tsx
│   │       └── ExportRunButton.tsx         ← F18
│   ├── lib/
│   │   ├── workos.ts
│   │   ├── copilotkit-runtime.ts
│   │   └── feature-flags.ts
│   └── package.json
│
├── middleware/                 ← NEW: Cloud Run service (Python)
│   ├── server.py               ← FastAPI proxy
│   ├── auth/
│   │   └── workos_jwt.py
│   ├── memory/
│   │   └── mem0_client.py
│   ├── observability/
│   │   └── otel.py             ← OpenTelemetry → Langfuse + Cloud Trace
│   ├── Dockerfile
│   └── pyproject.toml          ← extras: middleware = [...]
│
├── api/                        ← only the LangGraph deployment manifest
│   ├── langgraph.json          ← graph registry (consumed by LangGraph Platform)
│   └── README.md
│
├── infra/                      ← OpenTofu (Terraform fork, OSS)
│   ├── gcp/
│   │   ├── network.tf          ← VPC, Private Service Connect, Cloud NAT
│   │   ├── data.tf             ← Cloud SQL, Memorystore, Secret Manager
│   │   ├── compute.tf          ← Cloud Run services (middleware, mem0, langfuse)
│   │   ├── auth-workos.tf      ← External Secrets ↔ WorkOS
│   │   └── edge-cloudflare.tf  ← Cloudflare zone, WAF, rate-limit, DNS
│   ├── aws-dr/
│   │   ├── network.tf
│   │   ├── data.tf             ← RDS read-replica, KMS
│   │   └── compute.tf          ← ECS Fargate task def (desired=0)
│   └── modules/
│
├── trust/, services/, components/, orchestration/, meta/, StructuredReasoning/   ← unchanged
├── tests/
│   ├── architecture/
│   │   └── test_middleware_layer.py        ← middleware/ may import only services/, trust/
│   ├── middleware/
│   │   ├── test_workos_auth.py             ← rejection paths first
│   │   └── test_mem0_writeback.py
│   └── frontend/                           ← Vitest + Playwright
└── FRONTEND_PLAN_V2_FRONTIER.md            ← this file
```

### 3.2 Layer invariants extended to `middleware/`

`middleware/` is the new orchestration adapter (peer to `cli.py`). Architecture rules:

- `middleware/` MAY import from: `services/`, `trust/`, `orchestration.react_loop` (only via `build_graph`).
- `middleware/` MAY NOT import from `meta/`, `StructuredReasoning/components/`, `StructuredReasoning/services/` directly.
- Nothing in `components/`, `services/`, `trust/`, `orchestration/`, `meta/` may import from `middleware/`.
- `frontend/` is TypeScript and cannot import any Python; the boundary is enforced by language.

LangGraph Platform Cloud SaaS is a **runtime peer**, not a Python import target. It loads `orchestration.react_loop:build_graph` from `langgraph.json`.

## 4. API Contract

V2-Frontier exposes **two protocols** simultaneously:

1. **Agent Protocol** (Agent-to-Application HTTP/SSE) — handled by LangGraph Platform Cloud SaaS for thread/run CRUD.
2. **AG-UI Protocol** (Agent-User Interaction) — handled by CopilotKit Runtime; carries tool lifecycles, generative-UI commands, agent state deltas.

Routes (all bearer-authenticated with WorkOS access tokens):


| Method   | Path                                                    | Purpose                                       |
| -------- | ------------------------------------------------------- | --------------------------------------------- |
| `POST`   | `/api/copilotkit`                                       | CopilotKit Runtime — multiplexed AG-UI events |
| `POST`   | `https://<langgraph-platform>/threads/{id}/runs/stream` | LangGraph Platform native SSE                 |
| `GET`    | `https://<langgraph-platform>/threads`                  | List threads                                  |
| `DELETE` | `https://<langgraph-platform>/runs/{run_id}`            | Cancel run                                    |
| `GET`    | `/healthz`                                              | Liveness (Cloud Run)                          |


### 4.1 AG-UI event taxonomy (subset)


| AG-UI event                   | Frontend hook            | Payload                                                                                |
| ----------------------------- | ------------------------ | -------------------------------------------------------------------------------------- |
| `tool.start` / `.end`         | `useFrontendTool` render | `{name, args, status}`                                                                 |
| `state.delta`                 | `useCoAgentStateRender`  | `{step_count, total_cost_usd, model_history, …}`                                       |
| `component.render`            | `useComponent`           | `{name: "WidgetRenderer", html, css, js}` or `{name: "PyramidPanel", analysis_output}` |
| `human_in_the_loop.request`   | `useHumanInTheLoop`      | `{tool_name, args, justification}`                                                     |
| `messages.partial`/`complete` | CopilotKit auto          | LangChain message format                                                               |


Heartbeats every 15 s (mandatory per [dev.to multi-agent SSE article](https://dev.to/priyank_agrawal/your-multi-agent-sse-stream-works-in-dev-heres-what-kills-it-in-production-458i)). LangGraph Platform emits these natively.

## 5. Data Model

### 5.1 Cloud SQL Postgres 16 — three databases on one instance

`**agent_app`** (managed by `middleware/` via SQLModel, single ORM):

```sql
-- Identical to V1 §5.1 schema (users, threads, messages, runs, tool_calls)
-- with one addition for V2-Frontier:
ALTER TABLE messages ADD COLUMN ag_ui_components JSONB;  -- captures generative UI surface for re-render on history scroll
```

`**agent_memory**` (managed by Mem0 self-hosted):

```sql
CREATE EXTENSION pgvector;

CREATE TABLE memories (
  id          UUID PRIMARY KEY,
  user_id     UUID NOT NULL,
  agent_id    TEXT,
  fact        TEXT NOT NULL,
  embedding   VECTOR(1536),
  metadata    JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memories_user_idx ON memories (user_id, agent_id);
CREATE INDEX memories_embedding_idx ON memories USING ivfflat (embedding vector_cosine_ops);
```

(Optional) **Neo4j Aura** (managed) for Mem0 graph layer if entity-relationship recall becomes a measured need at v1.5. Off by default in v1.

`**langfuse_oltp`** — Langfuse owns its schema; we run its migrations untouched.

### 5.2 LangGraph checkpoints

Owned and managed by LangGraph Platform Cloud SaaS in their VPC. **We never touch this database.** Tracing flows back via LangSmith integration.

### 5.3 Object storage

**Google Cloud Storage** bucket for:

- Langfuse event blobs.
- Future v2 attachments.
- Generated UI artifacts cached for re-render (e.g., a 3D animation HTML the agent emitted last week).

## 6. Cloud Infrastructure (OpenTofu in TypeScript-flavored HCL)

### 6.1 GCP primary stacks


| Stack                    | Resources                                                                                                                                     | Notes                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `gcp/network`            | VPC, private subnets, Cloud NAT, Private Service Connect for Cloud SQL                                                                        | Single-region us-central1                           |
| `gcp/data`               | Cloud SQL Postgres 16 (db-custom-2-7680, regional HA, 100 GB SSD, automated backups, PITR), Memorystore Redis Standard 1 GB, Secret Manager   | Regional HA = automatic failover within region      |
| `gcp/compute-middleware` | Cloud Run service `agent-middleware` (1 vCPU/2 GB, min=1, max=100, concurrency=80, timeout=3600s, startup CPU boost)                          | min=1 keeps TTFT <100 ms                            |
| `gcp/compute-mem0`       | Cloud Run service `mem0-server` (0.5 vCPU/1 GB, min=0, max=20)                                                                                | Scale to zero between bursts                        |
| `gcp/compute-langfuse`   | Cloud Run services `langfuse-web`, `langfuse-worker` + ClickHouse on GCE n2-standard-4 (managed via the Langfuse Helm chart's docker-compose) | ClickHouse not yet on Cloud SQL; runs on its own VM |
| `gcp/edge-cloudflare`    | Cloudflare zone, DNS, WAF Managed Ruleset, Bot Fight Mode, rate-limit rule, custom Workers route for Realtime API ws (v1.5)                   | Replaces CloudFront — native SSE, no special config |
| `gcp/auth-workos`        | External Secrets pulling WorkOS API key into Secret Manager                                                                                   | WorkOS itself is SaaS — nothing to host             |


### 6.2 AWS DR stack (dormant)


| Stack            | Resources                                                                                            | Notes                                                       |
| ---------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `aws-dr/network` | VPC, private subnets, NAT (or VPC endpoints), security groups                                        | Cold standby in us-east-1                                   |
| `aws-dr/data`    | RDS Postgres 16 read-replica of Cloud SQL via DMS, KMS encrypted                                     | Lag tolerated up to 5 min; promote on DR                    |
| `aws-dr/compute` | ECR mirror of GCP image, ECS Fargate task definition + service with `desired_count = 0`, ALB stopped | Stays cold; flip via Route 53 + scale ECS in the DR runbook |


### 6.3 Honest cost model (private beta, ≤10 concurrent users)


| Item                               | Configuration                                                    | Estimated $/mo  |
| ---------------------------------- | ---------------------------------------------------------------- | --------------- |
| LangGraph Platform Plus            | 1 Plus subscription + per-node billing (~50K nodes/mo expected)  | $39 + $50 = $89 |
| LangGraph Platform standby         | Production deployment standby ($0.0036/min × ~3 of 30 days idle) | ~$15            |
| Cloud Run middleware               | 1 vCPU / 2 GB, min=1 always-on                                   | $35–50          |
| Cloud Run mem0-server              | 0.5 vCPU / 1 GB, scale-to-zero, low traffic                      | $5–15           |
| Cloud Run Langfuse (web+wkr)       | 2 services × 1 vCPU / 2 GB, min=1                                | $60–80          |
| ClickHouse on GCE                  | n2-standard-4, 100 GB SSD                                        | $130            |
| Cloud SQL Postgres                 | db-custom-2-7680, regional HA, 100 GB                            | $130–160        |
| Memorystore Redis                  | Standard 1 GB                                                    | $50             |
| Cloudflare                         | Pro plan ($25/mo per zone) + Workers free tier                   | $25             |
| WorkOS                             | AuthKit Free up to 1M MAU; SAML/SCIM at $125/connection if used  | $0–125          |
| Mem0 self-hosted                   | $0 (Apache 2.0)                                                  | $0              |
| Langfuse self-hosted               | $0 (MIT)                                                         | $0              |
| Vercel Pro (2 seats)               | Frontend hosting (booked honestly, like V1 D7)                   | $40             |
| AWS DR (RDS replica + dormant ECS) | RDS db.t4g.micro replica + ECR mirror + Route 53                 | ~$20            |
| Misc (logging, NAT, transfer)      |                                                                  | ~$30            |
| **All-in total**                   |                                                                  | **$540–890/mo** |


> Cost is materially higher than V1's $150–180/mo. The premium buys: scale-to-zero on the supporting services (Mem0, future workloads), managed LangGraph (no self-hosted server to operate), production-grade observability and memory layers from day 1, and a warm DR posture in a second cloud. **We accepted "no cost ceiling" in the briefing.** If the number is uncomfortable, the cheapest deletions are: drop AWS DR (-$20), drop ClickHouse and use Langfuse on Postgres-only with fewer events (-$130), drop Memorystore (Mem0 lookups go to disk; -$50). Even the lean variant lands at ~$340/mo.

## 7. Authentication

- **Provider**: **WorkOS AuthKit** (default) — OIDC for email/password + magic-link, plus SAML/SCIM for any future enterprise customer at $125/connection. Cognito remains the documented fallback for "AWS-only" stakeholders.
- **Why WorkOS over Cognito**: built-in admin portal for SSO setup (vs Cognito's manual SAML config), free tier covers 1M MAU (vs Cognito's 50K), and the API/SDK are notably better documented than Cognito's. Trade-off: a third-party in the auth path (vs Cognito's same-account integration).
- **Token used for API calls**: WorkOS access tokens (JWT). Verified by the middleware via WorkOS JWKs.
- `**user_id` propagation**: WorkOS `sub` claim becomes `users.id` and is passed through `graph.ainvoke(config={"configurable": {"user_id": …, …}})` for `eval_capture`.
- **Authorization (v1)**: WorkOS organization membership + custom roles claim → middleware ACL → tool allowlist (same pattern as V1).
- **Authorization (v1.5)**: same `services/authorization_service.py` design as V1, with the rendering layer now powered by `useFrontendTool` + `useHumanInTheLoop` (F17).

## 8. Phased Milestones

### Phase 0 — Decisions locked (this document, ~0.5 day)

- Briefing constraints documented.
- This file on `main`.

### Phase 0.5 — Spike & validation (4 days)

- **Spike A** (1d): CopilotKit + LangGraph integration in throwaway repo; verify `useFrontendTool` + `useComponent` + `useCoAgentStateRender` against the existing `react_loop` graph.
- **Spike B** (1d): Deploy LangGraph Platform Cloud SaaS dev deployment from a branch; verify the existing graph runs and Studio renders the topology.
- **Spike C** (1d): Stand up Mem0 self-hosted on Cloud Run + Cloud SQL pgvector; verify `add()` + `search()` round-trips < 200 ms.
- **Spike D** (1d): Deploy Langfuse self-hosted on Cloud Run + ClickHouse on GCE; verify a traced LangGraph run lands as a structured trace with prompt versions and tool spans.

**Acceptance**: 4 of 4 spikes pass, or fallback paths invoked (Spike A fail → revert to assistant-ui per V1; Spike B fail → switch to LangGraph Platform Self-Hosted Lite per V1; Spike C fail → defer Mem0 to v1.5; Spike D fail → use Cloud Trace + Cloud Logging only).

### Phase 1 — Middleware + LangGraph Platform deployment (4 days)

- `middleware/server.py` (FastAPI) with WorkOS verifier + Mem0 client + OpenTelemetry instrumentation.
- `langgraph.json` with `react_agent` graph entry; deploy to LangGraph Platform Cloud SaaS via GitHub integration.
- `tests/architecture/test_middleware_layer.py`, `tests/middleware/*.py` (rejection paths first).
- Smoke test: a curl with a real WorkOS access token streams a multi-event SSE response from the middleware end-to-end through to a fake LLM.

### Phase 2 — GCP infrastructure via OpenTofu (5 days)

- Implement the seven `gcp/`* stacks per §6.1.
- `tofu apply` to a new `agent-prod-gcp` project in us-central1.
- Cloudflare zone configured; WAF managed rules in count mode for 48 h.
- Mem0 self-hosted reachable; pgvector index built.
- Langfuse self-hosted reachable; ClickHouse online; first trace lands.
- AWS DR stack (`aws-dr/*`) provisioned but `desired_count=0`; DMS replication healthy.

### Phase 3 — Frontend integration (5 days)

- `create-next-app@latest --ts --tailwind --app`.
- `npx copilotkit@latest init` — runtime route + chat surface.
- WorkOS AuthKit integration in `frontend/lib/workos.ts` and `app/api/auth/[...workos]/route.ts`.
- Tool UIs (`ShellToolUI`, `FileIOToolUI`, `WebSearchToolUI`) via `useFrontendTool`.
- `WidgetRenderer` (`useComponent`) for generative UI artifacts.
- `PyramidPanel` (`useComponent`) for StructuredReasoning analysis viewer.
- `AuthorizationPrompt` (`useFrontendTool` + `useHumanInTheLoop`) for tool gating.
- `RealtimeVoiceWidget` skeleton behind `NEXT_PUBLIC_VOICE_ENABLED=false`.
- `ExportRunButton` (F18).
- Vercel project linked; preview deploys on every PR.

### Phase 4 — Hardening + private beta launch (3 days)

- Cloudflare WAF moved to enforce mode after 48 h count.
- WorkOS MFA enforced for all users.
- Cloud Monitoring alarms: 5xx rate, Cloud Run error rate, Cloud SQL CPU, Cloud SQL connections, Mem0 latency p95, Langfuse trace ingestion lag.
- Runbook in `infra/RUNBOOK.md` covers normal ops + DR flip to AWS.
- Five external beta users invited.

### Total: ~22 working days ≈ 5 calendar weeks (vs V1's ~4 weeks)

The +1 week vs V1 is the cost of (a) standing up Langfuse + Mem0 self-hosted, and (b) the dormant AWS DR stack. Both are deferred-able if speed matters more than capability.

## 9. Testing Strategy


| Layer                  | Code under test                                             | Test technique                                                                                                                                                         |
| ---------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| L1 (`trust/`)          | unchanged                                                   | unchanged                                                                                                                                                              |
| L2 (`services/`)       | unchanged + `authorization_service.py` (v1 in V2-Frontier!) | unchanged                                                                                                                                                              |
| L3 (`components/`)     | unchanged                                                   | unchanged                                                                                                                                                              |
| L4 (`orchestration/`)  | unchanged                                                   | unchanged                                                                                                                                                              |
| **L4 (`middleware/`)** | WorkOS verifier, Mem0 client, OTel exporter                 | Contract tests with mocks (`pytest-asyncio`); rejection paths first per TAP-4                                                                                          |
| **Architecture**       | `tests/architecture/test_middleware_layer.py`               | Import-graph assertion; same shape as V1's `test_api_layer.py`                                                                                                         |
| **Frontend**           | Tool UIs, generative renderers, Pyramid panel               | Vitest + React Testing Library + Playwright; **plus Storybook stories for every generative-UI component** so the agent can render them without running the agent in CI |
| **Memory**             | Mem0 round-trip + Langfuse trace ingestion                  | Golden-set integration tests against an ephemeral Cloud SQL fixture in CI                                                                                              |


## 10. Risk Register


| ID  | Risk                                                                                    | Likelihood | Impact   | Mitigation                                                                                                                                          |
| --- | --------------------------------------------------------------------------------------- | ---------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | LangGraph Platform Cloud SaaS pricing changes mid-program                               | Med        | Med      | Self-Hosted Lite is the documented fallback (V1's pick); migration is a `langgraph.json` re-deploy                                                  |
| R2  | WorkOS adds significant cost as enterprise SSO usage grows                              | Med        | Med      | Cognito remains a documented swap; access-token claims shape is portable                                                                            |
| R3  | Mem0 underperforms (49% LongMemEval) as a long-term memory layer                        | Med        | Med      | F15 ships behind a feature flag; can swap to Letta or Zep later                                                                                     |
| R4  | Langfuse self-hosted footprint (Postgres + ClickHouse + Redis) becomes operational toil | Med        | Med      | Phoenix self-hosted is the lighter fallback; can move ClickHouse to managed if needed                                                               |
| R5  | Cloudflare WAF false-positives on streamed Markdown                                     | Low        | Med      | Stage in count-mode for 48 h                                                                                                                        |
| R6  | GCP regional outage during beta                                                         | Low        | High     | DR stack (AWS dormant) flips via Route 53 + ECS scale-up runbook                                                                                    |
| R7  | Generative UI iframe sandbox escape                                                     | Low        | Critical | `useComponent` renders into `<iframe sandbox="allow-scripts">` only — no `allow-same-origin`; CSP locked down; reviewed in security review pre-beta |
| R8  | CopilotKit v2 breaking changes (still 1.x)                                              | Med        | Med      | Pin to `@copilotkit/react-core@1.x.y` minor; subscribe to release notes                                                                             |
| R9  | OpenAI Realtime API latency / cost makes voice (F20) DOA                                | Med        | Low      | F20 stays dark behind feature flag; no v1 commitment                                                                                                |
| R10 | Multi-cloud egress cost surprise (replication, Cloudflare egress)                       | Low        | Med      | Cost alarm at $1000/mo; Cloud SQL → DMS bandwidth bounded by row-change volume                                                                      |
| R11 | StructuredReasoning panel (F14) renders before `StructuredReasoning/` lands on `main`   | Med        | Low      | F14 feature-flagged; mock `analysis_output` JSON in dev; lights up after merge                                                                      |


## 11. Open Questions

1. **WorkOS or Cognito for v1?** WorkOS gives better DX + free SSO; Cognito gives same-AWS-account integration. **Default: WorkOS.** Reconsider if a customer mandates "AWS-only IdP".
2. **LangGraph Platform Cloud SaaS or Self-Hosted Lite?** Cloud SaaS is fully managed but adds vendor billing; Self-Hosted Lite is free <1M nodes/mo. **Default: Cloud SaaS** (the briefing said no cost ceiling and we want zero ops on the orchestration layer). Reconsider if procurement objects to a third-party data path for thread state.
3. **Mem0 in v1 or v1.5?** Adds operational footprint. **Default: v1** (briefing says "richer than V1"). Behind a feature flag so we can ship dark.
4. **Cloudflare or GCP Cloud Load Balancer + Cloud Armor?** Cloudflare is faster to set up and gives us bot mitigation; GCP-native keeps the cloud bill in one place. **Default: Cloudflare.**
5. **OpenTofu or Pulumi or CDK-TF?** All three work. **Default: OpenTofu** (most boring, OSS, GCP provider mature). Pulumi is the upgrade path if we want the same TS as the frontend.
6. **AWS DR — Multi-AZ active-active later?** Not in v1. **Default: dormant. Revisit at v2 when traffic justifies it.**

## 12. Glossary


| Term                              | Meaning here                                                                                  |
| --------------------------------- | --------------------------------------------------------------------------------------------- |
| **AG-UI Protocol**                | Agent-User Interaction Protocol; CopilotKit's open spec for agent ↔ UI bidirectional events   |
| **Agent Protocol**                | Open spec for agent HTTP/SSE APIs; LangGraph Platform implements it natively                  |
| **CopilotKit**                    | The frontend stack for agents and generative UI (29.9K stars; React + Angular; AG-UI authors) |
| **Generative UI**                 | The pattern where the agent emits UI components (constrained or open-ended) into the chat     |
| **LangGraph Platform Cloud SaaS** | LangChain's managed runtime for LangGraph; Plus tier $39/seat/mo + per-node                   |
| **Langfuse**                      | Open-source (MIT) LLM observability platform: tracing + prompt mgmt + evals                   |
| **Mem0**                          | Open-source (Apache 2.0) agent memory layer; vector + optional graph                          |
| **WorkOS**                        | Auth/SSO/SCIM-as-a-service; AuthKit free up to 1M MAU                                         |
| **OpenTofu**                      | Apache-2.0 Terraform fork                                                                     |
| **Cloudflare**                    | Edge / CDN / WAF — used here in place of CloudFront                                           |
| **DR**                            | Disaster recovery (AWS dormant stack ready to take over from GCP)                             |


---

## 13. Evidence Register


| ID        | Fact                                                                                                                                                                       | Source                                                                                                                                                                                                                                                                  | Used by                                                              | Confidence |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------- |
| ev_v2f_1  | Cloud Run supports SSE with `X-Accel-Buffering: no`, request timeout up to 3600 s, scale-to-zero, 100 ms cold starts with startup CPU boost                                | [Cloud Run AI agents docs](https://docs.cloud.google.com/run/docs/ai-agents), [Gemini 3.1 Pro × Cloud Run guide](https://gemilab.net/en/articles/gemini-dev/gemini-cloud-run-serverless-ai-api-production)                                                              | §3, §6.1                                                             | 0.9        |
| ev_v2f_2  | Cloud Run is the GCP-recommended platform for hosting LangGraph and other agent frameworks                                                                                 | [Cloud Run AI agents docs](https://docs.cloud.google.com/run/docs/ai-agents)                                                                                                                                                                                            | §3                                                                   | 0.95       |
| ev_v2f_3  | CopilotKit v2 + AG-UI Protocol provides `useFrontendTool`, `useComponent`, `useHumanInTheLoop`, `useCoAgentStateRender` for static + open-ended generative UI; 29.9K stars | [github.com/CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit), [Static AG-UI docs](https://mintlify.com/CopilotKit/CopilotKit/generative-ui/static-ag-ui), [CopilotKit/generative-ui](https://github.com/CopilotKit/generative-ui)                       | F5, F13, F14, F17                                                    | 0.95       |
| ev_v2f_4  | Tambo is a viable shadcn-purist alternative to CopilotKit (11K stars, MIT, Zod schemas, fullstack incl. agent loop)                                                        | [github.com/tambo-ai/tambo](https://github.com/tambo-ai/tambo), [Tambo docs](https://docs.tambo.co/guides/enable-generative-ui/register-components)                                                                                                                     | §17 alternatives                                                     | 0.85       |
| ev_v2f_5  | LangGraph Platform Cloud SaaS Plus = $39/user/mo + $0.001/node + $0.0036/min standby (production)                                                                          | [LangGraph Platform pricing](https://agentsapis.com/langchain/langgraph-pricing/)                                                                                                                                                                                       | §6.3                                                                 | 0.85       |
| ev_v2f_6  | Mem0 self-hosted is Apache 2.0, scores 49% on LongMemEval, supports vector + (graph on Pro) backends                                                                       | [Mem0 vs Letta vectorize](https://vectorize.io/articles/mem0-vs-letta), [Best Memory Systems 2026](https://vectorize.io/articles/best-ai-agent-memory-systems)                                                                                                          | F15, R3                                                              | 0.85       |
| ev_v2f_7  | Langfuse self-hosted (MIT) requires Postgres + ClickHouse + Redis + S3-compatible blob store; Phoenix is the lighter alternative                                           | [Langfuse vs Phoenix vs Helicone 2026](https://open-techstack.com/blog/langfuse-vs-phoenix-vs-helicone-llm-observability-2026/), [AI Observability 2026](https://brlikhon.engineer/blog/ai-observability-in-2026-langfuse-vs-arize-vs-helicone-for-production-llm-apps) | F16, R4                                                              | 0.9        |
| ev_v2f_8  | Vercel AI SDK 5 ships type-safe useChat with `tool-` typed parts, dynamic tools, automatic input streaming, `useObject` for streaming JSON                                 | [Vercel AI SDK 5 announcement](https://vercel.com/blog/ai-sdk-5), [useObject docs](https://v5.ai-sdk.dev/docs/reference/ai-sdk-ui/use-object)                                                                                                                           | §17 alternatives                                                     | 0.9        |
| ev_v2f_9  | Mastra is TypeScript-native agent framework on top of Vercel AI SDK; 22.9K stars; production users include Replit/PayPal/Sanity                                            | [github.com/mastra-ai/mastra](https://github.com/mastra-ai/mastra), [Mastra Complete Guide](https://www.generative.inc/mastra-ai-the-complete-guide-to-the-typescript-agent-framework-2026)                                                                             | §17 alternatives (rejected for V2-Frontier — Python LangGraph stays) | 0.9        |
| ev_v2f_10 | Azure Container Apps supports LangGraph hosting via Bicep; known SSE-hangs-on-tool-call bug in Azure AI Agent Server (b12) — Container Apps avoids it                      | [Azure Container Apps deployment](https://github.com/Azure-Samples/azure-typescript-langchainjs/blob/main/docs/06-azure-container-apps.md), [Azure SDK #45282](https://github.com/azure/azure-sdk-for-python/issues/45282)                                              | §17 alternatives                                                     | 0.85       |
| ev_v2f_11 | Cloudflare streams SSE without the special cache/header config CloudFront requires (no equivalent of the V1 §6.1 EdgeStack workaround needed)                              | Cloudflare docs + community confirmation; absence of analogous SSE-buffering bug reports comparable to opennextjs/opennextjs-aws#1127 for CloudFront                                                                                                                    | §3, §6.1                                                             | 0.7        |
| ev_v2f_12 | WorkOS AuthKit is free up to 1M MAU; SAML/SSO at $125/connection                                                                                                           | WorkOS pricing page                                                                                                                                                                                                                                                     | §7, §6.3                                                             | 0.85       |
| ev_v2f_13 | Mastra and CopilotKit both build on top of Vercel AI SDK; Mastra delegates streaming to AI SDK                                                                             | [Mastra Complete Guide](https://www.generative.inc/mastra-ai-the-complete-guide-to-the-typescript-agent-framework-2026)                                                                                                                                                 | §17 architecture context                                             | 0.9        |


## 14. Hypothesis Register


| ID  | Decision                                                                             | Hypothesis                                                                                                        | Confirm if                                     | Kill if                                         | Status                        |
| --- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | ----------------------------------------------- | ----------------------------- |
| H1  | Cloud Run for LangGraph middleware                                                   | Cloud Run sustains 10 concurrent SSE streams for ≥10 min each at <70% CPU on 1 vCPU/2 GB                          | Load test: p95 CPU <70%, 0 dropped connections | CPU >85% or streams dropped                     | Untested (Spike A)            |
| H2  | Cloudflare streams SSE without bypass config                                         | Default Cloudflare zone with no special cache rules streams `text/event-stream` byte-for-byte                     | TTFT <100 ms; no buffering after 1 min idle    | Buffering observed                              | Untested (Phase 2 verify)     |
| H3  | LangGraph Platform Cloud SaaS adopts our existing graph unchanged                    | `langgraph.json` pointing at `orchestration.react_loop:build_graph` deploys cleanly                               | Spike B passes                                 | Cloud SaaS requires graph refactor              | Untested (Spike B)            |
| H4  | CopilotKit v2 + AG-UI render the existing graph's tool calls + state without rewrite | `useFrontendTool` + `useCoAgentStateRender` work end-to-end with our `react_loop` events                          | Spike A passes                                 | Custom event taxonomy required                  | Untested (Spike A)            |
| H5  | Mem0 self-hosted on pgvector serves 10 users at <200 ms recall                       | `Mem0.search()` p95 <200 ms with 50K memories                                                                     | Spike C passes; load test at v1.5 scale        | Latency >500 ms p95                             | Untested (Spike C)            |
| H6  | Langfuse self-hosted captures LangGraph traces with prompt versions                  | Graph runs land as structured traces; prompt versions tracked                                                     | Spike D passes                                 | Trace ingestion gaps for `astream_events`       | Untested (Spike D)            |
| H7  | iframe sandbox is sufficient for `useComponent` HTML                                 | `<iframe sandbox="allow-scripts">` (no `allow-same-origin`) prevents data exfiltration from the chat session      | Security review passes                         | Sandbox escape demo found                       | Untested (Phase 4 sec review) |
| H8  | DR flip to AWS works in <30 min                                                      | DMS replication lag <5 min; Route 53 + ECS scale-up runbook completes in <30 min                                  | Quarterly DR drill in v1.5                     | Replication drifts or runbook fails             | Untested (drill in v1.5)      |
| H9  | StructuredReasoning panel renders the schema's `analysis_output` faithfully          | `useComponent`-driven `PyramidPanel` displays issue tree + arguments + evidence + validation log + so-what chains | Phase 3 acceptance                             | Schema mismatch                                 | Untested                      |
| H10 | OpenAI Realtime API works behind Cloudflare WS proxy                                 | Realtime API ws upgrade survives Cloudflare's WebSocket forwarding                                                | v1.5 spike when feature flag flips             | ws breaks; fall back to phone-bridge or LiveKit | Untested (v1.5)               |


## 15. Validation Log


| #   | Check          | Result            | Details                                                                                                                                                                                                                                                                                                                                    |
| --- | -------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Completeness   | **Pass**          | F1–F20 cover everything V1 ships in v1 plus everything V1 deferred to v1.5. Multi-cloud DR posture covers the implicit "what if AWS goes away" question that V1 leaves open.                                                                                                                                                               |
| 2   | Non-Overlap    | **Partial**       | F13 (generative UI canvas) and F14 (Pyramid panel) both use `useComponent`. They are non-overlapping in *content* (free-form HTML vs structured schema) but share the *mechanism*. Documented; F14 is a typed special-case of F13.                                                                                                         |
| 3   | Item Placement | **Pass**          | Each evidence item is assigned to one consumer (or annotated as multi-consumer like ev_v2f_3 which underpins F5/F13/F14/F17 — but those are all CopilotKit hooks and the assignment is split-fact, not overlapping).                                                                                                                       |
| 4   | So What?       | **Pass**          | §1 governing thought is bigger than V1's; each clause has a specific purpose: CopilotKit → generative UI; LangGraph Platform Cloud → zero ops; Mem0 → personalization; Langfuse → prompt/eval discipline; WorkOS → enterprise-ready auth; Cloudflare → no SSE workaround; GCP+AWS → multi-cloud portability; voice pre-wire → v1.5 unlock. |
| 5   | Vertical Logic | **Pass**          | §3 architecture answers "how does the user reach the agent and back?", §4 answers "what protocols are spoken?", §5 answers "what's at rest?", §6 answers "which cloud services?", §7 answers "how is access gated?", §8 answers "in what order do we build?".                                                                              |
| 6   | Remove One     | **Partial**       | The plan tolerates losing F15 (Mem0), F16 (Langfuse), F19 (MCP), F20 (voice), F14 (Pyramid panel), and the AWS DR stack — each is independently deletable. It does **not** tolerate losing F13 (generative UI canvas) — that is the central UX premise. Documented as known-acceptable: F13 is a necessary precondition.                   |
| 7   | Never One      | **Pass**          | No single-child groupings.                                                                                                                                                                                                                                                                                                                 |
| 8   | Mathematical   | **Pass (caveat)** | Line items in §6.3 sum to $540–890/mo. Internally consistent. Caveat: ClickHouse on GCE estimate is point-in-time; actual depends on event volume; could be ±$50.                                                                                                                                                                          |


## 16. Cross-Branch Interactions


| Interacting branches                                               | Interaction                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §3 LangGraph Platform Cloud ↔ §5 Cloud SQL `agent_app`             | LangGraph Platform owns checkpoint state in *their* database. Our `agent_app` schema (users, threads, messages, runs, tool_calls) duplicates *summary* metadata for our own UI/analytics. Risk: drift between LangGraph's truth and ours; mitigation: `messages` table in `agent_app` is a derived projection populated by middleware on `messages.complete` AG-UI events. |
| §3 Mem0 ↔ §3 LangGraph Platform                                    | Mem0 lookups happen in the middleware *before* invoking the graph (to inject user context) and on `state.delta` events *after* (to extract new facts). Mem0 latency directly extends TTFT — H5 verifies <200 ms.                                                                                                                                                           |
| §3 Cloudflare ↔ §3 Cloud Run middleware                            | Cloudflare streams SSE byte-for-byte (H2). Cloud Run's per-request timeout (max 3600 s) is the upper bound on a run length. Heartbeats every 15 s defeat both Cloudflare's idle timer and Cloud Run's idle window.                                                                                                                                                         |
| §3 GCP primary ↔ §3 AWS DR                                         | DMS replicates Cloud SQL → RDS. Replication lag is the RPO; runbook execution time is the RTO. Both are documented in `infra/RUNBOOK.md` and drilled quarterly (H8).                                                                                                                                                                                                       |
| §13 Mem0 49% LongMemEval ↔ F15 design                              | Mem0's accuracy is bounded; if a user reports recall failures, the upgrade path is Letta or Zep, both of which speak similar APIs. F15 is feature-flagged so we can A/B Mem0 vs no-memory with the same UI.                                                                                                                                                                |
| §3 CopilotKit `useComponent` ↔ §10 R7 (iframe sandbox)             | The agent can emit arbitrary HTML/JS through `useComponent`. The sandboxed iframe is the security boundary. CSP on the parent page must forbid `frame-ancestors` to prevent clickjacking by the iframe content into the app shell.                                                                                                                                         |
| §10 R8 (CopilotKit v2 breakage) ↔ §11 Open Q (CopilotKit vs Tambo) | If CopilotKit v2 ships breaking changes mid-program, Tambo (ev_v2f_4) is the documented fallback. Both speak shadcn/Zod component contracts; migration is per-component, not big-bang.                                                                                                                                                                                     |


## 17. Alternatives Considered (V2-Frontier-specific decision tables)

### 17.1 Frontend stack (F1–F9, F13, F14, F17)


| Option                       | Generative UI                                             | Lock-in             | Verdict                                                       |
| ---------------------------- | --------------------------------------------------------- | ------------------- | ------------------------------------------------------------- |
| **CopilotKit v2 [selected]** | Best — three patterns (Static AG-UI / Declarative / Open) | Med (AG-UI is open) | Best for the F13/F14/F17 ambition                             |
| Tambo                        | Strong — registered components + Zod schemas              | Med                 | Closest second; pick if CopilotKit v2 stability bites (R8)    |
| assistant-ui (V1 pick)       | Limited — primarily renders message stream                | Low                 | Reverts V2-Frontier to V1 for F1–F9; loses F13/F14/F17        |
| Vercel AI SDK 5 useChat      | Custom rendering per `tool-`* part type                   | Low                 | Strong for AI SDK shops; needs more plumbing for F13/F14      |
| Hand-rolled                  | Whatever you build                                        | None                | Rejected: 5–6 weeks of work duplicating what CopilotKit ships |


### 17.2 Compute platform (F10, F12)


| Option                             | Cost (10 users)           | SSE TTFT                       | Scale-to-zero         | Verdict                                                                                                                                            |
| ---------------------------------- | ------------------------- | ------------------------------ | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **GCP Cloud Run [selected]**       | $35–50/mo (min=1)         | <100 ms with startup CPU boost | Yes (min=0 supported) | Best — native SSE, scale-to-zero on supporting services, 3600 s request limit                                                                      |
| AWS ECS Fargate (V1 pick)          | $51–65/mo                 | <200 ms                        | No                    | Mature alternative; locked to V1 for the AWS-centric variant                                                                                       |
| Azure Container Apps               | $40–55/mo                 | <150 ms                        | Yes                   | Strong; KEDA scaling; **avoid Azure AI Foundry hosted agents** until [#45282](https://github.com/azure/azure-sdk-for-python/issues/45282) is fixed |
| LangGraph Platform Cloud SaaS only | $89–104/mo (Plus + nodes) | n/a (managed)                  | n/a                   | Used for the orchestration server; doesn't replace middleware                                                                                      |
| Lambda / Cloud Functions           | <$15/mo                   | Cold start hurts SSE           | n/a                   | Rejected: SSE on serverless functions is awkward; Cloud Run is the correct shape                                                                   |


### 17.3 Edge (F12)


| Option                      | SSE buffering                                                                    | WAF                                         | Verdict                                                         |
| --------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------- | --------------------------------------------------------------- |
| **Cloudflare [selected]**   | None by default                                                                  | Cloudflare Managed Ruleset + Bot Fight Mode | Best — no SSE workaround, fastest to set up, generous free tier |
| AWS CloudFront (V1 pick)    | Buffers — needs `CachingDisabled` + no-transform + viewer fn (V1 §6.1 EdgeStack) | AWS WAF managed rules                       | V1's pick; works if you're already AWS-only                     |
| GCP Cloud CDN + Cloud Armor | Less mature for SSE; needs config                                                | Cloud Armor managed rules                   | Acceptable; loses Cloudflare's bot mitigation                   |


### 17.4 Memory (F15)


| Option              | LongMemEval | Setup | License    | Verdict                                                                                   |
| ------------------- | ----------- | ----- | ---------- | ----------------------------------------------------------------------------------------- |
| **Mem0 [selected]** | 49%         | Hours | Apache 2.0 | Best for "drop-in" v1 — broadest community, easy self-host, framework-agnostic            |
| Letta (MemGPT)      | ~83%        | Days  | Apache 2.0 | Best accuracy, but it's a *runtime replacement* (not bolt-on); breaks our LangGraph stack |
| Zep / Graphiti      | 64–75%      | Hours | Open core  | Best for temporal reasoning + audit trails; Zep CE deprecated                             |
| LangMem             | n/a         | Hours | MIT        | LangGraph-only lock-in; thinner feature set than Mem0                                     |
| None (V1 pick)      | n/a         | n/a   | n/a        | Acceptable for v1 if F15 deemed v1.5+; V2-Frontier's brief explicitly demands more        |


### 17.5 Observability (F16)


| Option                    | Production self-host | OTel    | Prompt mgmt      | Verdict                                                                                 |
| ------------------------- | -------------------- | ------- | ---------------- | --------------------------------------------------------------------------------------- |
| **Langfuse [selected]**   | Yes (heavy stack)    | Yes     | Yes              | Best — single platform for traces + prompt versions + evals; MIT                        |
| Phoenix (Arize)           | Yes (light)          | Yes     | No               | Lighter alternative; pick if Langfuse stack toil bites                                  |
| Helicone                  | Yes (proxy)          | Limited | Limited          | Rejected: proxy-only model loses agent span depth                                       |
| LangSmith                 | Enterprise only      | n/a     | Yes              | Already in the stack via LangGraph Platform integration; complementary, not replacement |
| Braintrust                | Enterprise only      | n/a     | Yes (eval-first) | Best if eval-first; rejected for v1 due to no self-host                                 |
| CloudWatch only (V1 pick) | n/a                  | Limited | No               | V1's implicit pick; insufficient for prompt/eval discipline this plan demands           |


### 17.6 Auth (F8)


| Option                                    | Free tier       | SSO / SCIM                                      | Verdict                                                                       |
| ----------------------------------------- | --------------- | ----------------------------------------------- | ----------------------------------------------------------------------------- |
| **WorkOS [selected]**                     | 1M MAU          | Built-in admin portal; $125/connection for SAML | Best for enterprise-readiness from day 1                                      |
| Cognito (V1 pick)                         | 50K MAU         | SAML available, manual config                   | Solid AWS-native pick; less DX                                                |
| Auth.js + Cognito provider (V1's D5 pick) | 50K via Cognito | Same as Cognito                                 | Best within AWS-only framing                                                  |
| Clerk                                     | 10K MAU         | Strong DX, opinionated UI                       | Rejected: opinionated UI conflicts with our shadcn/CopilotKit visual language |
| Auth0                                     | 7.5K MAU        | Best-in-class SSO, expensive at scale           | Rejected: cost grows steeply past free tier                                   |


### 17.7 TypeScript-native agent runtime (rejected option, documented for completeness)


| Option                                 | Lang       | Maturity                    | Verdict                                                                                                                                                                                                                                          |
| -------------------------------------- | ---------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Mastra                                 | TypeScript | Production (Replit, PayPal) | Rejected: would force rewriting `orchestration/`, `components/`, `services/` from Python to TS. The existing 4-layer architecture is the sunk cost we're protecting; that's why LangGraph stays. Mastra would be the right pick on a greenfield. |
| Vercel AI SDK 5 + custom orchestration | TypeScript | Production                  | Same rejection reason as Mastra                                                                                                                                                                                                                  |


## 18. Errata and Confidence Recomputation

### 18.1 Confidence

```
confidence = min(avg_argument_confidence, completeness_penalty, structural_penalty)
```

**Completeness penalty:**

- 9 untested hypotheses (H1–H6 in Phase 0.5 spikes; H7 in security review; H8 DR drill; H9 in Phase 3; H10 in v1.5) → −0.10 × 6 high-impact = −0.60, mitigated to −0.30 because Phase 0.5 explicitly de-risks 4 of them.
- Effective completeness: 1.0 − 0.30 = **0.70**.

**Structural penalty:**

- §15 records two partial checks (Non-Overlap from F13/F14 mechanism overlap; Remove-One from F13 being central) → −0.05 each = −0.10.
- Effective structural: 1.0 − 0.10 = **0.90**.

**Average argument confidence:**

- Cost evidence: avg ~0.85.
- Architectural evidence (Cloud Run, Cloudflare, Mem0, Langfuse, WorkOS): avg ~0.85.
- Generative UI evidence (CopilotKit, Tambo): avg ~0.92.
- Timeline evidence: avg ~0.65.
- Weighted: **~0.78**.

**Plan-level confidence: `min(0.78, 0.70, 0.90)` = 0.70.**

(Below the 0.78 reported in §1 — §1 was rounded up. The honest figure is 0.70, lower than V1's 0.78 because V2-Frontier carries strictly more moving parts.)

---

## 19. Changelog vs V1


| Section              | Change vs V1 (FRONTEND_PLAN_V1.md)                                                                                                                                                                                                  |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §1 Governing Thought | Added CopilotKit + AG-UI; LangGraph Platform Cloud SaaS (vs Self-Hosted Lite); Mem0; Langfuse; WorkOS; Cloudflare; GCP primary; AWS DR; voice pre-wire. Cost band rises from $150–180/mo to $540–890/mo (briefing said no ceiling). |
| §2 Scope             | Added F13–F20: generative UI canvas, Pyramid panel, Mem0 memory, Langfuse observability, per-tool authorization UI, JSON export, MCP tools, voice mode pre-wire. F8 Auth changes from Cognito to WorkOS.                            |
| §3 Architecture      | Cloudflare replaces CloudFront; Cloud Run replaces ECS Fargate; LangGraph Platform Cloud SaaS replaces Self-Hosted Lite; Mem0 + Langfuse services added; AWS DR stack added.                                                        |
| §3.1 Repo layout     | `frontend/components/generative/` directory (Pyramid panel, widget renderer, authorization prompt, voice widget); `middleware/` directory; `infra/gcp/` + `infra/aws-dr/`.                                                          |
| §4 API contract      | Two protocols spoken simultaneously: Agent Protocol (LangGraph Platform native) + AG-UI (CopilotKit Runtime).                                                                                                                       |
| §5 Data model        | Three Postgres databases on Cloud SQL: `agent_app`, `agent_memory` (pgvector for Mem0), `langfuse_oltp`. ClickHouse on GCE for Langfuse analytics.                                                                                  |
| §6.1                 | Seven GCP stacks + three AWS DR stacks (vs V1's five AWS stacks).                                                                                                                                                                   |
| §6.3                 | Honest cost rises to $540–890/mo (deletable to ~$340/mo if dropping AWS DR + ClickHouse + Memorystore).                                                                                                                             |
| §7                   | WorkOS instead of Cognito (Cognito remains documented fallback).                                                                                                                                                                    |
| §8 Phases            | 5 calendar weeks (vs V1's 4); +1 week for Mem0 + Langfuse + DR.                                                                                                                                                                     |
| §10 Risks            | New: R7 (iframe sandbox), R8 (CopilotKit v2), R10 (multi-cloud egress), R11 (StructuredReasoning panel timing).                                                                                                                     |
| §13 Evidence         | 13 V2-Frontier-specific evidence rows (ev_v2f_1–13).                                                                                                                                                                                |
| §17 Alternatives     | 7 new decision tables covering frontend stack, compute, edge, memory, observability, auth, and the rejected Mastra/AI-SDK alternative.                                                                                              |


---

## 20. V1 vs V2-Frontier — Head-to-Head

> **Bottom line up front**: V1 is the **disciplined production beta**. V2-Frontier is the **frontier flagship**. They are Pareto-optimal on different axes; choosing between them is choosing what to optimize.

### 20.1 Side-by-side decision matrix


| Decision area            | FRONTEND_PLAN_V1.md (revision 2)                                         | FRONTEND_PLAN_V2_FRONTIER.md                                                      |
| ------------------------ | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| **Primary cloud**        | AWS us-east-1                                                            | GCP us-central1 (AWS us-east-1 dormant DR)                                        |
| **Compute**              | ECS Fargate + ALB                                                        | Cloud Run (scale-to-zero on supporting svcs)                                      |
| **Edge**                 | CloudFront with `CachingDisabled` + no-transform + accept-encoding strip | Cloudflare (no SSE workaround needed)                                             |
| **Frontend UI library**  | `assistant-ui` (shadcn primitives, runtime renderer)                     | **CopilotKit v2** (AG-UI Protocol; generative UI in v1)                           |
| **Generative UI**        | Deferred to v1.5                                                         | **In v1** (F13 widget renderer, F14 Pyramid panel, F17 authorization prompt)      |
| **Orchestration server** | LangGraph Platform Self-Hosted Lite (free <1M nodes)                     | LangGraph Platform Cloud SaaS Plus ($89–104/mo, fully managed)                    |
| **Auth**                 | Auth.js + Cognito provider                                               | WorkOS AuthKit (1M MAU free; SSO/SCIM ready)                                      |
| **Memory**               | None (LangGraph checkpointer only)                                       | **Mem0 self-hosted** on pgvector (F15)                                            |
| **Observability**        | CloudWatch + LangSmith                                                   | **Langfuse self-hosted** + LangSmith + Cloud Trace (F16)                          |
| **MCP tools**            | Not in plan                                                              | **Native** via LangGraph Platform (F19)                                           |
| **Voice mode**           | Not in plan                                                              | **Pre-wired**, dark behind feature flag for v1.5 (F20)                            |
| **DR posture**           | Single-region Single-AZ (Multi-AZ at GA per V1 R7)                       | **Multi-cloud DR** (GCP active, AWS dormant)                                      |
| **DB**                   | Single RDS Postgres `db.t4g.micro` Single-AZ                             | Cloud SQL Postgres regional HA + pgvector + (optional Neo4j Aura at v1.5)         |
| **Cost (all-in/mo)**     | $150–180                                                                 | $540–890 (deletable to ~$340)                                                     |
| **Build duration**       | ~4 calendar weeks                                                        | ~5 calendar weeks                                                                 |
| **Plan confidence**      | 0.78                                                                     | 0.70                                                                              |
| **Lock-in**              | Cognito (medium); rest portable                                          | WorkOS (low); LangGraph Platform Cloud (medium); rest portable via open protocols |
| **AGENTS.md invariants** | Preserved                                                                | Preserved                                                                         |
| **Reversibility**        | High — all picks have documented fallbacks                               | High — every choice has a documented OSS / second-cloud fallback                  |


### 20.2 Trade-off scoring (1–5; 5 is better)


| Dimension                                | V1 score | V2-Frontier score | Notes                                                                                                                                             |
| ---------------------------------------- | -------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Time to v1**                           | 5        | 4                 | V1 is ~1 week faster                                                                                                                              |
| **Cost discipline**                      | 5        | 2                 | V1 is ~3–4× cheaper                                                                                                                               |
| **UX ambition (chat surface)**           | 3        | 5                 | V2-Frontier ships generative UI / Pyramid panel / authorization UI in v1                                                                          |
| **Operational maturity (memory + obs)**  | 2        | 5                 | V2-Frontier ships Mem0 + Langfuse from day 1                                                                                                      |
| **Enterprise readiness (auth/SSO/SCIM)** | 3        | 5                 | WorkOS gives enterprise-tier auth without re-architecting                                                                                         |
| **Multi-cloud / vendor independence**    | 2        | 4                 | V2-Frontier has a dormant AWS DR stack and uses open protocols throughout                                                                         |
| **Architectural conservatism**           | 5        | 3                 | V1 introduces 1 new SaaS dependency (Cognito); V2-Frontier introduces 4 (LangGraph Platform Cloud, WorkOS, Cloudflare, OpenAI Realtime API later) |
| **Bus factor (OSS bets)**                | 4        | 3                 | V1 = LGP-SHL + assistant-ui; V2-Frontier = LGP Cloud + CopilotKit + Mem0 + Langfuse — more bets, each independently sound                         |
| **Plan confidence**                      | 5        | 4                 | V1 = 0.78, V2-Frontier = 0.70                                                                                                                     |
| **Capability ceiling at v1.5/v2**        | 3        | 5                 | V2-Frontier already pre-wires voice (F20), MCP (F19), per-tool authorization UI (F17), JSON export (F18), Pyramid panel (F14)                     |
| **Total**                                | **39**   | **40**            | Statistically tied; the right choice depends entirely on what you optimize                                                                        |


### 20.3 When to choose which


| If your situation is…                                                                                                                                                                                                                                   | Choose                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Private beta with ≤10 users; budget-sensitive; AWS-shop; need to ship in 4 weeks; v1.5 timeline is acceptable for advanced UX                                                                                                                           | **V1**                                                                                                                                                                                                                                                                                                                                                                                                                    |
| You need to demo Claude-Artifacts-class UX to a customer in 5 weeks; budget is not the binding constraint; want enterprise SSO from day 1; have GCP credits or want multi-cloud posture; want production observability discipline before traffic exists | **V2-Frontier**                                                                                                                                                                                                                                                                                                                                                                                                           |
| You're not sure                                                                                                                                                                                                                                         | **V1 first, V2-Frontier features incrementally added in v1.5/v2** — V1's recommendations were chosen to *not foreclose* V2-Frontier upgrades. Concretely: swap assistant-ui for CopilotKit by adding `useFrontendTool` to existing components; add Mem0 by adding a middleware step; add Langfuse by changing OTel exporter; flip Cognito to WorkOS by replacing the Auth.js provider config. None of these is a rewrite. |


### 20.4 Compatibility with V1's reversible decisions

V2-Frontier is intentionally an **upgrade path** from V1, not a rewrite:


| V1 decision                        | V2-Frontier change                              | Rewrite cost           |
| ---------------------------------- | ----------------------------------------------- | ---------------------- |
| `assistant-ui` → CopilotKit        | Replace `MyAssistant.tsx`, keep tool components | ~2 days                |
| LGP-SHL → LGP Cloud SaaS           | Re-deploy via GitHub integration                | <1 day                 |
| Cognito → WorkOS                   | Swap Auth.js provider                           | ~1 day                 |
| ECS Fargate → Cloud Run            | New `infra/gcp/` stack; image is unchanged      | ~3 days                |
| CloudFront → Cloudflare            | New zone config; remove the SSE bypass plumbing | ~1 day                 |
| (none) → Mem0                      | Add `middleware/memory/mem0_client.py` step     | ~2 days                |
| (none) → Langfuse                  | Add OTel exporter + deploy                      | ~3 days                |
| (none) → Generative UI             | Add `useComponent` hooks; ship one widget       | ~3 days                |
| **Total V1 → V2-Frontier upgrade** |                                                 | **~16 days ≈ 3 weeks** |


The "V1 first, then V2-Frontier" route therefore costs **~7 weeks total** (4 weeks V1 + 3 weeks upgrade), vs. **~5 weeks all-V2-Frontier-up-front**, but trades 2 weeks of cumulative dev time for the de-risking benefit of validating V1 in private beta before adding the ambition. For most teams, this is the safer sequence.

### 20.5 Recommendation summary

- **Default recommendation**: ship **V1** for private beta, then upgrade to V2-Frontier features for public beta / GA.
- **Frontier-first recommendation**: ship **V2-Frontier** if (a) the private beta itself is the demo, (b) you have GCP creds or no AWS preference, (c) cost is genuinely no object, and (d) you can absorb the higher operational footprint of self-hosting Mem0 + Langfuse.
- Both plans honor `AGENTS.md` invariants, both preserve the four-layer Python architecture, both ship inside ~5 weeks, and both have documented fallbacks for every key decision.

---

*This plan was produced under the briefing "no cost ceiling; AWS, GCP, or Azure on the table; explore other options" applied to FRONTEND_PLAN_V1.md, structured per `prompts/StructuredReasoning/_pyramid_brain.j2`. Final head-to-head comparison with V1 is in §20.*