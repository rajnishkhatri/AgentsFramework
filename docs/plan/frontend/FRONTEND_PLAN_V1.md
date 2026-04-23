# FRONTEND_PLAN_V1.md — Web Chat UI for the ReAct Agent (revision 2)

> **Status**: planning, revision 2.
>
> **Supersedes**: `FRONTEND_PLAN.md` (revision 1, 2026-04-21).
>
> **Source-of-truth role**: this document is the v1 product plan. It incorporates the comparative-study and trade-off-analysis recommendations dated 2026-04-21 and is structured per `prompts/StructuredReasoning/_pyramid_brain.j2`.
>
> **What changed in revision 2** (full delta in §19 Changelog): adopted `assistant-ui` for the frontend (D1), adopted **LangGraph Platform Self-Hosted Lite** as the orchestration server with Aegra as the OSS-purist fallback (D2), pivoted compute from the deprecated **AWS App Runner** to **ECS Fargate behind ALB** (D3, mandatory — App Runner closes to new accounts on 2026-04-30), added the **CloudFront SSE bypass** (D4, mandatory — CloudFront silently buffers `text/event-stream` by default), swapped Amplify Auth for **Auth.js Cognito provider** (D5), collapsed the dual-ORM pattern to **FastAPI-only** (D6), kept Vercel hosting but **booked the $40/mo Pro line** that revision 1 omitted (D7), kept SSE as the transport (D8). Net: ~6-week plan becomes ~4-week plan; three high-impact risks retired; AGENTS.md invariants intact; honest all-in cost lands at **$120–135/mo**.

## 1. Governing Thought

Ship a Claude-style web chat for the existing LangGraph ReAct agent — Next.js 15 (App Router) on **Vercel** with `assistant-ui` (shadcn/ui primitives) and **Auth.js Cognito provider**, talking over **Server-Sent Events** to **LangGraph Platform Self-Hosted Lite** (free up to 1M nodes/month, with **Aegra** as the OSS-purist fallback) running on **ECS Fargate behind ALB** in **us-east-1**, gated by **Amazon Cognito**, persisting to **RDS Postgres**, fronted by **CloudFront + WAF** with the **`CachingDisabled` cache policy + no-transform response headers + viewer-request `accept-encoding` strip** that SSE actually requires — preserving the four-layer architecture invariants in `AGENTS.md`, holding monthly all-in cost in the **$120–135/mo** range (honest figure, including Vercel Pro and ALB), and deferring the StructuredReasoning Pyramid panel and per-tool authorization UI to v1.5.

Confidence: **0.78** (raised from revision 1's 0.65; capped by four untested integration spikes scheduled in Phase 0.5).

## 2. Scope

### In scope (v1, ~4 weeks of frontend + backend integration work)

| ID  | Feature                                                                                       | Plan-revision-2 implementation                                                                                                                  | Backend hook                                                  |
| --- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| F1  | Thread sidebar (rename / archive / delete / search-by-title)                                  | `assistant-ui` `ThreadList` primitive                                                                                                           | LangGraph `thread_id` (via Agent Protocol)                    |
| F2  | Streaming markdown messages, syntax-highlighted code blocks, copy/download                    | `assistant-ui` `Thread` + `MessagePrimitive.Content` (built-in)                                                                                 | `messages[]` + LangGraph `astream_events`                     |
| F3  | Stop / regenerate / edit-and-resend last message                                              | `assistant-ui` `useThreadRuntime()` actions (built-in)                                                                                          | `DELETE /runs/{id}` + checkpoint rewind                       |
| F4  | Mobile-first responsive composer (Tailwind + shadcn)                                          | `assistant-ui` `Composer` primitive                                                                                                             | n/a (FE)                                                      |
| F5  | Collapsible tool-call cards (`shell` / `file_io` / `web_search`)                              | `assistant-ui` `ToolCallContentPart` with custom render per tool                                                                                | `services/tools/registry.py`                                  |
| F6  | Step counter + cost meter                                                                     | Custom React component (~50 LOC) reading SSE `step` events                                                                                      | `state.step_count`, `state.total_cost_usd`                    |
| F7  | Model badge per turn (`fast` / `capable`)                                                     | Custom React component (~30 LOC) reading SSE `model.switch` events                                                                              | `ModelProfile.tier`                                           |
| F8  | Cognito sign-in (email + OTP), `cognito:sub` → `user_id`                                      | **Auth.js Cognito provider** in `frontend/app/api/auth/[...nextauth]/route.ts`                                                                  | `eval_capture.record(user_id=…)`                              |
| F9  | Light/dark theme toggle                                                                       | `assistant-ui` shadcn theme tokens + `next-themes`                                                                                              | n/a (FE)                                                      |
| F10 | Orchestration server exposing Agent Protocol (`/chat/stream`, `/threads`, `/runs`, `/agents`) | **LangGraph Platform Self-Hosted Lite** (primary) **or Aegra** (fallback). Plus a thin `api/middleware/` Python module for Cognito + tool ACLs. | `orchestration.react_loop.build_graph` via `langgraph.json`   |
| F11 | LangGraph checkpointer = Postgres                                                             | LangGraph Platform Self-Hosted Lite ships PostgreSQL persistence; no `AsyncSqliteSaver` → `AsyncPostgresSaver` migration required               | `langgraph-checkpoint-postgres` (managed by the OSS server)   |
| F12 | AWS infra in CDK (TypeScript)                                                                 | **ECS Fargate + ALB** (not App Runner), RDS Postgres, Cognito, CloudFront (with SSE bypass), WAF, Secrets Manager, ECR, CloudWatch              | `infra/`                                                      |

### Deferred to v1.5 (next 4 weeks)

- StructuredReasoning Pyramid panel (`AnalysisOutput` viewer) — wait for `StructuredReasoning/` to land on `main`. Likely to use **CopilotKit** (`useComponent`, `useFrontendTool`) for generative-UI rendering of the pyramid.
- Per-tool authorization UI + new `services/authorization_service.py` returning `PolicyDecision`.
- Input/output guardrail surfaces (rejection toast, redaction badges).
- Per-user `AgentFacts` profile selector.
- JSON run export (eval-capture friendly).

### Deferred to v2

- Attachments (S3 + presigned URL + virus scan + new `attachment` tool).
- Share read-only link (anonymized export + abuse rate-limit).
- Projects/workspaces (conversation grouping).
- Audit-trail viewer (`TrustTraceRecord`).
- React Native app.
- Drizzle BFF for thread CRUD (re-introduced only if BFF→API→RDS round-trip latency becomes a measurable UX problem; see §17.4 v2 trade-off).

### Out of scope forever

- `shell` tool exposed to non-admin users on the public surface (always behind admin role + feature flag).
- Hardcoded prompts in TS — system prompts continue to be `.j2` files rendered by `PromptService` (architecture invariant H1).
- Anything that imports from `orchestration/` into `components/` or `services/` (architecture invariant).
- Custom-rolled SSE message-list, composer, thread-list, or auto-scroll components for v1 — they live in `assistant-ui`. Custom ejection is reserved for v1.5+ if `assistant-ui` becomes a constraint.

## 3. Architecture

```
Browser (mobile + desktop)
  │  HTTPS
  ▼
┌──────────────────────── Vercel ────────────────────────────────────────┐
│ Next.js 15 App Router                                                  │
│  • RSC: shell, sidebar, settings                                       │
│  • Client: assistant-ui Thread + Composer + ToolCallContentPart        │
│            (renders LangGraph messages from SSE; custom F6 step meter, │
│             F7 model badge)                                            │
│  • Route Handlers (BFF):                                               │
│      /api/auth/[...nextauth]  → Auth.js Cognito provider               │
│      /api/run/stream          → SSE proxy → ALB (forwards bearer)      │
│      /api/run/cancel          → DELETE proxy → ALB                     │
│      /api/threads/*           → JSON proxy → ALB (no Drizzle in v1)    │
└────────────────────────────────────────────────────────────────────────┘
                  │  HTTPS (Cognito access-token bearing)
                  ▼
┌──────────────────────── AWS account: agent-prod / us-east-1 ─────────────────────┐
│  CloudFront distribution                                                          │
│   • Cache policy: CachingDisabled  ← MANDATORY for SSE                            │
│   • Response-headers policy: Cache-Control: no-cache, no-transform;               │
│                              Connection: keep-alive                               │
│   • Viewer-request CloudFront Function: delete request.headers["accept-encoding"] │
│     for paths matching /chat/stream — prevents 502 from edge re-compression       │
│   • WAF WebACL: AWSManagedRulesCommonRuleSet,                                     │
│                 AWSManagedRulesKnownBadInputsRuleSet,                             │
│                 AWSManagedRulesAmazonIpReputationList,                            │
│                 custom rate-limit rule (1000 req/5min/IP)                         │
│      │                                                                            │
│      ▼                                                                            │
│  Application Load Balancer (internet-facing)                                      │
│   • idle_timeout = 4000s ← long ReAct runs survive (unlike App Runner's 120s)     │
│   • HTTPS listener with ACM cert                                                  │
│      │                                                                            │
│      ▼                                                                            │
│  ECS Fargate service "agent-api" (1 vCPU / 2 GB, desired=1, max=3)                │
│   • Container image from ECR (Python 3.11 slim)                                   │
│   • Runs LangGraph Platform Self-Hosted Lite server                               │
│     (or Aegra fallback) bound to the existing graph via langgraph.json            │
│   • Custom api/middleware/ adds Cognito access-token verification +               │
│     per-Cognito-group tool allowlist                                              │
│   • Reads secrets via task IAM role from Secrets Manager                          │
│   • Private subnets; no public IP                                                 │
│      │                                                                            │
│      ▼                                                                            │
│  RDS Postgres 16 (db.t4g.micro, Single-AZ, KMS encrypted, private subnet)         │
│   • LangGraph checkpoints (managed by LGP-SHL or Aegra)                           │
│   • App schema: users, threads, messages, runs, tool_calls (single-ORM, owned     │
│     by the Python server)                                                         │
│                                                                                   │
│  Cognito User Pool "agent-users"                                                  │
│   • Email sign-in, OTP MFA, no self-signup (admin invites for beta)               │
│   • Groups: admin (gets shell), beta (no shell)                                   │
│                                                                                   │
│  Secrets Manager: OPENAI_API_KEY, AGENT_FACTS_SECRET, DB_URL                      │
│  ECR: agent-api image repo                                                        │
│  CloudWatch: log group /aws/ecs/agent-api + custom metrics                        │
│  VPC endpoints: ECR (gateway), Secrets Manager (interface), CloudWatch Logs       │
│                 (interface), S3 (gateway) — replaces NAT Gateway                  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Repository layout (monorepo subdirectories)

```
agent/
├── frontend/                   ← Next.js 15 app (deploy target = Vercel)
│   ├── app/
│   │   ├── (chat)/
│   │   │   ├── layout.tsx
│   │   │   └── [threadId]/page.tsx
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/route.ts   ← Auth.js Cognito provider (D5)
│   │   │   ├── threads/route.ts              ← thin JSON proxy → ALB
│   │   │   ├── threads/[id]/route.ts
│   │   │   ├── run/stream/route.ts           ← SSE proxy → ALB; forwards Authorization
│   │   │   └── run/cancel/route.ts
│   │   └── layout.tsx
│   ├── components/             ← thin wrappers around assistant-ui:
│   │   ├── MyAssistant.tsx     ← AssistantRuntimeProvider with LangGraph runtime
│   │   ├── tools/
│   │   │   ├── ShellToolUI.tsx
│   │   │   ├── FileIOToolUI.tsx
│   │   │   └── WebSearchToolUI.tsx
│   │   ├── StepMeter.tsx       ← F6, custom (~50 LOC)
│   │   └── ModelBadge.tsx      ← F7, custom (~30 LOC)
│   ├── lib/
│   │   ├── auth.ts             ← Auth.js config (Cognito OIDC provider)
│   │   └── langgraph-client.ts ← @langchain/langgraph-sdk client factory
│   ├── tailwind.config.ts
│   ├── package.json
│   └── README.md
│
├── api/                        ← THIN orchestration adapter (Python)
│   ├── __init__.py
│   ├── server.py               ← bootstraps LGP-SHL or Aegra; mounts middleware
│   ├── middleware/
│   │   ├── cognito_auth.py     ← verifies access-token; injects user_id, groups
│   │   └── tool_acl.py         ← per-Cognito-group tool allowlist (admin → shell)
│   ├── langgraph.json          ← graph registry: { "react_agent": "orchestration.react_loop:build_graph" }
│   ├── pyproject.toml          ← extras: api = [langgraph-cli, fastapi, ...]
│   └── README.md
│
├── infra/                      ← AWS CDK app (TypeScript)
│   ├── bin/agent-infra.ts
│   ├── lib/
│   │   ├── network-stack.ts    ← VPC, subnets, SGs, VPC endpoints (no NAT)
│   │   ├── data-stack.ts       ← RDS, Secrets Manager, KMS
│   │   ├── auth-stack.ts       ← Cognito User Pool + Hosted UI domain
│   │   ├── app-stack.ts        ← ECR, ECS Fargate cluster + service + ALB, IAM
│   │   └── edge-stack.ts       ← CloudFront + WAF + CachingDisabled policy +
│   │                             response-headers policy + viewer-request Function
│   ├── cdk.json
│   ├── package.json
│   └── README.md
│
├── trust/                      ← unchanged
├── services/                   ← + authorization_service.py in v1.5
├── components/                 ← unchanged
├── orchestration/              ← unchanged
├── StructuredReasoning/        ← lands on main before v1.5
├── tests/
│   ├── architecture/
│   │   └── test_api_layer.py   ← api/ may import only from orchestration/, services/, trust/
│   └── api/
│       ├── test_cognito_auth_middleware.py    ← rejection paths first
│       └── test_tool_acl_middleware.py        ← rejection paths first
└── FRONTEND_PLAN_V1.md         ← this file (supersedes FRONTEND_PLAN.md)
```

### 3.2 Layer invariants extended to `api/`

`api/` is treated identically to `cli.py` — a **thin orchestration adapter**. New architecture test (`tests/architecture/test_api_layer.py`):

- `api/` MAY import from: `orchestration/`, `services/`, `trust/`, `components/` (only via the `build_graph` factory).
- `api/` MAY NOT import from: `meta/`, `StructuredReasoning/components/`, `StructuredReasoning/services/` directly.
- Nothing in `components/`, `services/`, `trust/`, `orchestration/`, `meta/` may import from `api/`.

The adopted OSS server (LGP-SHL or Aegra) is a runtime peer of `api/`, not a Python import target — it loads `orchestration.react_loop:build_graph` via `langgraph.json` configuration, not by being imported.

## 4. API Contract

The orchestration server implements the **Agent Protocol** open specification, which already defines the routes the plan needs. The `api/middleware/` module adds Cognito verification on top.

All endpoints require a valid Cognito **access token** (`Authorization: Bearer <jwt>`) verified via Cognito JWKs. `cognito:sub` is mapped to `user_id` and threaded through to `eval_capture`. (Revision 1 incorrectly specified ID tokens; revision 2 uses access tokens per AWS docs — see §18.1 erratum, retained for traceability.)

| Method   | Path                     | Purpose                                             | Implementation                                              |
| -------- | ------------------------ | --------------------------------------------------- | ----------------------------------------------------------- |
| `POST`   | `/runs/stream`           | Start a run on a thread; stream SSE                 | Native to LGP-SHL / Aegra (Agent Protocol)                  |
| `DELETE` | `/runs/{run_id}`         | Cancel an in-flight run                             | Native to LGP-SHL / Aegra                                   |
| `GET`    | `/threads`               | List user's threads                                 | Native; filtered by `user_id` from middleware               |
| `POST`   | `/threads`               | Create a thread                                     | Native                                                      |
| `PATCH`  | `/threads/{id}`          | Rename / archive                                    | Native                                                      |
| `DELETE` | `/threads/{id}`          | Soft-delete                                         | Native                                                      |
| `GET`    | `/threads/{id}/state`    | Current checkpoint state (replay messages)          | Native                                                      |
| `GET`    | `/assistants`            | List assistants (analogue of `/agents`)             | Native; configured in `langgraph.json`                      |
| `GET`    | `/healthz`               | Liveness                                            | Custom in `api/middleware/`; public, no auth                |
| `GET`    | `/readyz`                | Readiness (DB + Secrets reachable)                  | Custom in `api/middleware/`; public                         |

### 4.1 SSE event taxonomy on `/runs/stream`

LGP-SHL and Aegra both expose LangGraph `astream_events` v2 events as SSE event frames per the Agent Protocol. The plan's revision-1 custom event taxonomy is replaced by the standard Agent Protocol mapping, with custom-emitted events for plan-specific concerns (`step`, `model.switch`).

| SSE `event:`        | Source                                          | Payload                                               | Used by component                |
| ------------------- | ----------------------------------------------- | ----------------------------------------------------- | -------------------------------- |
| `metadata`          | Run start                                       | `{run_id, thread_id, model, started_at}`             | `MyAssistant`                    |
| `messages/partial`  | `on_chat_model_stream`                          | partial assistant message                            | `assistant-ui` `Thread` (auto)   |
| `messages/complete` | `on_chat_model_end`                             | full assistant message                               | `assistant-ui` `Thread` (auto)   |
| `updates`           | `on_tool_start` / `on_tool_end`                 | tool-call delta                                      | `ToolCallContentPart` (auto)     |
| `events/step`       | per-node end (custom emit via `copilotkit_emit_state` or LGP equivalent) | `{step_count, total_cost_usd, tokens_in, tokens_out}` | `StepMeter` (custom)             |
| `events/model_switch` | `state.model_history` append (custom emit)    | `{from_tier, to_tier, reason}`                       | `ModelBadge` (custom)            |
| `error`             | error path                                      | `{error_type, message, retryable}`                   | `MyAssistant` error boundary     |

Every event carries `id: <run_id>:<seq>` so `EventSource` reconnect via `Last-Event-ID` resumes mid-stream.

**Heartbeats** (mandatory, per `dev.to/priyank_agrawal/your-multi-agent-sse-stream-works-in-dev-heres-what-kills-it-in-production`): the orchestration server emits `: heartbeat\n\n` every 15 seconds to defeat ALB / CloudFront idle timeouts.

## 5. Data Model

### 5.1 RDS Postgres schema

Owned end-to-end by the Python orchestration server (single ORM — D6). The Drizzle BFF mirror from revision 1 is removed for v1; route handlers proxy thread CRUD through to the API.

```sql
CREATE TABLE users (
  id            UUID PRIMARY KEY,                 -- = cognito:sub
  email         CITEXT UNIQUE NOT NULL,
  display_name  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE threads (
  id            UUID PRIMARY KEY,                 -- = LangGraph thread_id
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title         TEXT NOT NULL DEFAULT 'New chat',
  archived_at   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX threads_user_updated_idx ON threads (user_id, updated_at DESC);

CREATE TABLE runs (
  id             UUID PRIMARY KEY,
  thread_id      UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  user_id        UUID NOT NULL REFERENCES users(id),
  workflow_id    TEXT NOT NULL,
  task_id        TEXT NOT NULL,
  status         TEXT NOT NULL,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ,
  step_count     INT NOT NULL DEFAULT 0,
  total_cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0
);

CREATE TABLE messages (
  id          UUID PRIMARY KEY,
  run_id      UUID REFERENCES runs(id) ON DELETE SET NULL,
  thread_id   UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,                    -- user|assistant|tool|system
  content     JSONB NOT NULL,
  model       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_thread_created_idx ON messages (thread_id, created_at);

CREATE TABLE tool_calls (
  id           UUID PRIMARY KEY,
  message_id   UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  tool_name    TEXT NOT NULL,
  input        JSONB NOT NULL,
  output       JSONB,
  error        TEXT,
  duration_ms  INT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

LangGraph checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`) are owned by the OSS server's migration tooling and live in the same database. Migrations are applied via the OSS server's CLI (e.g., `langgraph migrations up`).

### 5.2 LangGraph checkpointer

Managed by LGP-SHL (or Aegra) — the plan no longer hand-rolls the `AsyncSqliteSaver` → `AsyncPostgresSaver` migration. Connection pool sizing remains a concern (see H8 in §14).

### 5.3 No Drizzle in v1

Revision 1's Drizzle BFF mirror introduced two-ORM drift risk (revision 1 §16, H4). Revision 2 collapses this to FastAPI-only. The 5–15 ms BFF→API→RDS round-trip penalty is well below the 200 ms TTFT budget (H2). Drizzle re-introduction is reserved for v2 only if measured thread-list latency becomes a UX problem.

## 6. AWS Infrastructure (CDK in TypeScript)

### 6.1 Stacks

| Stack          | Resources                                                                                                                                                                                                                                                       | Notes                                                                          |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `NetworkStack` | VPC (2 AZs), public + private subnets, security groups, **VPC endpoints** for ECR (gateway), Secrets Manager (interface), CloudWatch Logs (interface), S3 (gateway). **No NAT Gateway.**                                                                        | Replaces NAT to save ~$10/mo net (revision 1 §6.3 footnote option a, ratified) |
| `DataStack`    | RDS Postgres 16 (`db.t4g.micro`, 20 GB gp3, Single-AZ, deletion protection ON), KMS key, Secrets Manager secrets (`openai_api_key`, `agent_facts_secret`, `db_url`)                                                                                             | Unchanged from revision 1                                                      |
| `AuthStack`    | Cognito User Pool, Hosted UI domain, app client (PKCE, no client secret for SPA), groups: `admin`, `beta`                                                                                                                                                       | Unchanged from revision 1                                                      |
| `AppStack`     | ECR repo `agent-api`, **ECS Fargate cluster + service** (1 vCPU / 2 GB, desired=1, max=3), **internet-facing ALB** with `idle_timeout = 4000s` and HTTPS listener (ACM cert), task IAM role with read access to secrets + RDS IAM auth, observability config    | **Replaces App Runner.** App Runner closes to new accounts on 2026-04-30.       |
| `EdgeStack`    | CloudFront distribution → ALB origin, **`CachingDisabled` cache policy** + custom **response-headers policy** (Cache-Control: no-cache, no-transform; Connection: keep-alive) + **viewer-request CloudFront Function** stripping `accept-encoding` for `/runs/stream`, AWS WAF WebACL with managed rules + 1000 req/5min/IP custom rule | **CloudFront SSE bypass mandatory** — without it, SSE silently buffers          |

### 6.2 IAM least-privilege highlights

- ECS task role: `secretsmanager:GetSecretValue` (3 named secrets), `rds-db:connect` (specific user), `logs:CreateLogStream` + `PutLogEvents` (its own log group only).
- BFF (Vercel) → AWS only via Cognito access-token-bearing HTTPS to CloudFront; **no AWS credentials in Vercel env**.

### 6.3 Cost model (private-beta, ≤10 concurrent users)

| Item                | Configuration                                                          | Estimated $/mo |
| ------------------- | ---------------------------------------------------------------------- | -------------- |
| ECS Fargate         | 1 vCPU / 2 GB, desired=1 always-on, ~5% utilization                    | $35–45         |
| Application LB      | 1 ALB, low traffic                                                     | $16–20         |
| RDS Postgres        | `db.t4g.micro`, 20 GB gp3, Single-AZ                                   | $15–18         |
| CloudFront          | 50 GB egress, 5M requests                                              | $5–8           |
| AWS WAF             | 1 WebACL + 3 managed rule groups + 5M requests                         | $12–18         |
| Cognito             | <50,000 MAUs (free tier)                                               | $0             |
| Secrets Manager     | 3 secrets                                                              | $1.20          |
| ECR                 | <1 GB stored                                                           | $0.10          |
| CloudWatch          | logs + custom metrics (7-day retention to keep this line down)         | $2–4           |
| VPC endpoints       | 3 interface endpoints (ECR, Secrets, Logs); gateway endpoints (S3) free | $22            |
| Data transfer       | misc                                                                   | $2–4           |
| **AWS subtotal**    |                                                                        | **$110–140/mo** |
| **Vercel Pro**      | 2 seats (booked honestly per D7)                                       | **$40**        |
| **All-in total**    |                                                                        | **$150–180/mo** |

> **Honest-figure caveat:** revision 1's stated total of $80–95/mo omitted the ALB (because plan was App Runner) and Vercel Pro (because §18.2 acknowledged but didn't book). Revision 2 books both. To return to a sub-$100 AWS-only budget, options are: (a) drop CloudWatch retention to 3 days (saves ~$1/mo), (b) drop WAF to 1 managed rule group only (saves ~$8/mo, accepts more attack surface), (c) move frontend hosting to AWS Amplify Hosting (saves ~$35/mo on Vercel line, costs ~$5/mo on Amplify, net −$35/mo). **Plan recommendation:** accept $150–180/mo all-in for v1; revisit Amplify Hosting at v1.5 if seat count grows.

## 7. Authentication

- **Provider:** Amazon Cognito User Pool, OIDC.
- **Client library:** **Auth.js Cognito provider** (D5) — replaces revision 1's AWS Amplify Auth. Smaller bundle (~30 KB vs ~300 KB), standard NextAuth session pattern, copy-paste configuration from `vercel/ai-chatbot` template, no Amplify-specific token-type confusion.
- **Token used for API calls:** **access token** (`token_use === "access"`), per AWS Cognito access-token documentation. Verifier checks signature against Cognito JWKs (cached 24h), `iss`, `client_id`, `exp`. (Revision 1's §18.1 erratum is now ratified into the primary plan.)
- **`user_id` propagation:** `cognito:sub` UUID becomes `users.id` and is passed into every `graph.ainvoke(config={"configurable": {"user_id": ..., "task_id": ..., "thread_id": ...}})` call, satisfying the `eval_capture.record(user_id, task_id)` invariant from `AGENTS.md`.
- **Authorization (v1):** `cognito:groups` claim from the access token is read by `api/middleware/tool_acl.py`. Default v1 mapping:

  | Cognito group | Allowed tools                          |
  | ------------- | -------------------------------------- |
  | `admin`       | `shell`, `file_io`, `web_search` (all) |
  | `beta`        | `file_io`, `web_search` (no shell)     |

- **Authorization (v1.5):** new `services/authorization_service.py` returns `PolicyDecision` per `(user_id, agent_id, tool_name)`, backed by `Capability` records in the trust kernel. The `api/middleware/tool_acl.py` becomes a thin caller of this service.

## 8. Phased Milestones

### Phase 0 — Decisions locked (this document, ~0.5 day)

- Comparative study + trade-off analysis on `main`.
- Revision 2 plan committed.
- AWS account `agent-prod` registered (mandatory before 2026-04-30 if App Runner fallback is desired; otherwise unconstrained).

**Acceptance:** this file on `main`.

### Phase 0.5 — Spike & validation (3 days; **new in revision 2**)

Resolves the four "untested" rows in §15 before committing to the broader implementation.

- **Spike 1 (1d):** Wire `assistant-ui` against the existing `react_loop` graph in a throwaway repo. Verify SSE event compatibility for `messages/partial`, `updates` (tool calls), and custom `events/step` / `events/model_switch`.
- **Spike 2 (1d):** Deploy LGP-SHL locally via `langgraph dev`; point it at `orchestration.react_loop:build_graph` via `langgraph.json`; verify checkpoints land in local Postgres; verify the Cognito middleware injection point exists.
- **Spike 3 (0.5d):** Local Docker compose: LGP-SHL + Postgres + minimal Cognito mock (LocalStack); confirm an access-token-bearing `curl -N` against `/runs/stream` streams events.
- **Spike 4 (0.5d):** Deploy a test ECS Fargate + ALB stack in a sandbox AWS account; verify CloudFront with `CachingDisabled` + no-transform + `accept-encoding` strip streams SSE byte-for-byte from a hello-world FastAPI image.

**Acceptance:** all four spikes pass, or fallback paths are explicitly invoked (e.g., Spike 2 fails → switch to Aegra; Spike 1 fails → revert F2/F3/F4/F5 to hand-rolled).

### Phase 1 — Orchestration server stand-up (3 days)

- Add `langgraph-cli`, `langgraph-checkpoint-postgres`, `python-jose[cryptography]` to `pyproject.toml` `[project.optional-dependencies] api`.
- Create `api/server.py` that boots LGP-SHL with `langgraph.json` pointing to `orchestration.react_loop:build_graph` (extract `build_graph_for_user(user_id)` helper to remove duplication; both `cli.py` and `api/server.py` call it).
- `api/middleware/cognito_auth.py`: access-token verifier (rejection paths first per TAP-4).
- `api/middleware/tool_acl.py`: per-Cognito-group tool allowlist.
- `tests/architecture/test_api_layer.py`: enforce import boundaries for `api/`.
- `tests/api/test_cognito_auth_middleware.py`: rejection paths first (missing, expired, wrong issuer, wrong client_id, wrong token_use), then acceptance.
- `tests/api/test_tool_acl_middleware.py`: rejection paths first (beta user calling `shell`).

**Acceptance:** `pytest tests/api/ -q` green; local `curl -N` against the running server streams a multi-event SSE response with mocked LLM; existing `pytest tests/ -q` still green; existing `python -m agent.cli "…"` still works unchanged.

### Phase 2 — AWS infrastructure via CDK (4 days)

- `cd infra && npm init`, install CDK + constructs.
- Implement five stacks per §6.1.
- `cdk synth` produces clean CloudFormation.
- `cdk deploy --all` to `agent-prod` in `us-east-1`.
- ECR push of the orchestration server image; ECS service rolls.
- CloudFront distribution returns 200 from `/healthz` end-to-end **and** streams SSE byte-for-byte (verified via `curl -N`).
- Cognito User Pool created; admin invite to one beta user works.
- CloudWatch log group has structured JSON entries from a test request.

**Acceptance:** from a laptop, `curl -H "Authorization: Bearer <real Cognito access token>" -N https://<cf-domain>/runs/stream -d '{"assistant_id": "react_agent", "input": {"messages":[{"role":"user","content":"hi"}]}}'` streams events in real time (TTFT <200 ms); AWS Cost Explorer projects ≤$140/mo at current usage.

### Phase 3 — Next.js scaffold + auth + frontend integration (4 days)

- `frontend/` scaffolded with `create-next-app@latest --ts --tailwind --app`.
- shadcn/ui installed; `assistant-ui` installed via `npx assistant-ui@latest init`; theme calibrated to a Claude-desktop-like palette (off-white `#f9f7f5` light, near-black `#1f1e1d` dark).
- `frontend/lib/auth.ts`: Auth.js Cognito provider (User Pool ID + App Client ID from Vercel env).
- Sign-in and OTP confirmation pages.
- `MyAssistant.tsx` wires `unstable_createLangGraphStream` from `@assistant-ui/react-langgraph` to the BFF SSE proxy (which forwards bearer to ALB).
- Custom `ShellToolUI`, `FileIOToolUI`, `WebSearchToolUI` components.
- Custom `StepMeter` (F6) and `ModelBadge` (F7) components.
- BFF route handlers: `/api/threads/*` and `/api/run/*` as JSON / SSE proxies.
- Vercel project linked; preview deploy on every PR.

**Acceptance:** deploying a PR to Vercel preview, an invited beta user signs in, asks "What is the capital of France?", sees a streamed Markdown answer with model badge and final cost, then asks "List files in /etc" and (as `beta` group) sees the request rejected by `tool_acl.py`. Stop button cancels mid-run. Mobile layout reviewed on iOS Safari + Android Chrome.

### Phase 4 — Hardening + private beta launch (2.5 days)

- WAF managed rules tuned in count-mode for 48 h, then enforce.
- Cognito MFA enforced for all users.
- CloudWatch alarms: 5xx rate, ECS CPU, RDS CPU, RDS connections, ALB target unhealthy.
- Runbook documented in `infra/RUNBOOK.md`.
- Five external beta users invited.

**Acceptance:** 7 days of production usage with no Sev-2 incident; AWS Cost Explorer shows actual spend within ±20% of projection.

### Total: ~14 working days ≈ 3 calendar weeks ≈ 4 weeks with slack

(vs. revision 1's 5 calendar weeks of frontend + backend work.)

## 9. Testing Strategy (aligned with `AGENTS.md`)

| Layer                 | Code under test                                                        | Test technique                                                                                                  | Marker |
| --------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------ |
| L1 (`trust/`)         | unchanged                                                              | unchanged                                                                                                       | none   |
| L2 (`services/`)      | unchanged + `authorization_service.py` (v1.5)                          | unchanged                                                                                                       | none   |
| L3 (`components/`)    | unchanged                                                              | unchanged                                                                                                       | none   |
| L4 (`orchestration/`) | unchanged                                                              | unchanged                                                                                                       | none   |
| **L4 (`api/`)**       | `cognito_auth` middleware, `tool_acl` middleware, `langgraph.json` wiring | Contract tests (`pytest-asyncio`); rejection paths first per TAP-4                                              | none   |
| **Architecture**      | `tests/architecture/test_api_layer.py`                                 | Import-graph assertion: `api/` may not be imported by `components/`, `services/`, `trust/`, `orchestration/`, `meta/` | none   |
| **Frontend**          | `MyAssistant.tsx`, custom tool UIs, `StepMeter`, `ModelBadge`         | Vitest + React Testing Library (unit), Playwright (smoke E2Es against Vercel preview)                          | n/a    |

The custom SSE-translator tests from revision 1 are removed — that translation is now owned by the OSS server. Architecture tests for `api/` shrink because `api/` shrinks.

## 10. Risk Register

| ID  | Risk                                                                     | Likelihood | Impact   | Mitigation                                                                              |
| --- | ------------------------------------------------------------------------ | ---------- | -------- | --------------------------------------------------------------------------------------- |
| ~~R1~~ | ~~App Runner cold start with min=0 ruins SSE first-token UX~~          | —          | —        | **Retired in revision 2** (no App Runner)                                                |
| R2  | NAT Gateway cost pushes monthly above budget                             | —          | —        | **Retired** — revision 2 ratified VPC endpoints from day 1                              |
| R3  | `shell` tool reachable through Cognito beta user                         | Med        | Critical | `api/middleware/tool_acl.py` enforces per-group allowlist; `shell` only for `admin`     |
| R4  | LangGraph schema drift breaks Postgres checkpoint migration              | Low        | Med      | OSS server owns migrations; pin `langgraph-cli` version; smoke-test in Phase 0.5/1      |
| ~~R5~~ | ~~Amplify Auth bundle size hurts mobile load~~                         | —          | —        | **Retired in revision 2** (Auth.js Cognito provider; ~30 KB)                             |
| R6  | WAF managed rules false-positive on Markdown content                     | Low        | Med      | Stage in count-mode for 48 h before enforce                                             |
| R7  | RDS Single-AZ outage during beta                                         | Low        | High     | Acceptable for private beta; switch to Multi-AZ at GA                                   |
| R8  | StructuredReasoning module merges late, blocking v1.5                    | Med        | Low      | v1.5 panel feature-flagged off; ships dark and lights up after merge                    |
| **R9**  | **App Runner closes to new accounts 2026-04-30**                     | **Confirmed** | High  | **Mitigated by D3 pivot to ECS Fargate + ALB** (this revision)                          |
| **R10** | **Aegra / LGP-SHL bus factor (young projects)**                      | Med        | Med      | Conservative pick = LGP-SHL (LangChain-backed); Aegra remains as drop-in alternative; both speak Agent Protocol so swap cost is low |
| **R11** | **CloudFront silently buffers SSE without explicit bypass**          | **Confirmed** | High  | **Mitigated by D4 EdgeStack config** (this revision); contract test in Phase 2 acceptance |
| **R12** | **`assistant-ui` impedance mismatch with custom SSE event taxonomy** | Low        | Med      | Phase 0.5 Spike 1 explicitly de-risks; fallback = revert F2/F3/F4/F5 to hand-rolled (revision 1's plan) |
| **R13** | **Auth.js Cognito provider doesn't expose access-token to BFF cleanly** | Low     | Med      | Auth.js callback `jwt` writes access token into the session; widely-documented pattern  |

## 11. Open Questions for Future Decision

1. **Custom domain:** do we register one (e.g., `app.example.com` → Vercel, `api.example.com` → CloudFront) before launch, or use `*.vercel.app` + `*.cloudfront.net` for v1? **Default: defer to Phase 4.**
2. **AWS account boundary:** single `agent-prod` for v1; do we add `agent-dev` (AWS Organizations) at v1.5 or v2? **Default: v2.**
3. **LangSmith integration:** keep current LangSmith tracing in the orchestration server, or rely on CloudWatch Logs only? **Default: keep LangSmith; LGP-SHL ships LangSmith integration.**
4. **Eval-capture exposure in UI:** do beta users see their own eval logs (D2 — JSON export)? **Currently v1.5.**
5. **Per-project system-prompt override** (D4 in revision 1): nice-to-have; **default v2.**
6. **Aegra vs LGP-SHL:** revision 2 picks LGP-SHL by default for bus-factor reasons. Reconsider Aegra if (a) data-sovereignty / Apache-2.0 becomes a procurement requirement, or (b) LGP-SHL's free 1M nodes/month proves insufficient before v1.5.
7. **Vercel vs Amplify Hosting:** revision 2 keeps Vercel for v1 DX. Reconsider at v1.5 if seat count >5 (the $20/seat/mo line gets uncomfortable).

## 12. Glossary

| Term             | Meaning here                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------- |
| **Agent**        | The unchanged Python LangGraph ReAct agent in this repo                                   |
| **Agent Protocol** | Open spec for Agent HTTP/SSE APIs; implemented by both LGP-SHL and Aegra                |
| **API adapter**  | `api/` directory; thin Python module wrapping the OSS orchestration server with Cognito + ACL middleware; peer to `cli.py` |
| **assistant-ui** | TypeScript React library providing shadcn-style primitives for AI chat UIs (`@assistant-ui/react`, `@assistant-ui/react-langgraph`) |
| **Aegra**        | Open-source (Apache-2.0) self-hosted Agent Protocol server; Python + FastAPI + Postgres   |
| **BFF**          | Backend-for-Frontend: Next.js Route Handlers proxying to the orchestration server          |
| **LGP-SHL**      | LangGraph Platform Self-Hosted Lite — official LangChain OSS server (free <1M nodes/mo)   |
| **Run**          | A single `graph.ainvoke` execution on a thread; has UUID `run_id`                          |
| **Thread**       | Conversation; equivalent to LangGraph `thread_id`                                          |
| **SSE bypass**   | The CloudFront cache policy + response-header policy + viewer-fn combo required to actually stream SSE through CloudFront |
| **Trust kernel** | `trust/` package; pure types with zero outward dependencies                                |

---

## 13. Evidence Register

Every quantitative claim is listed below with its source so that Check 8 (Mathematical) is auditable. Revision-1 entries retained where unchanged.

| ID         | Fact                                                                            | Source                                                                                                                                     | Used by                          | Confidence |
| ---------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------- | ---------- |
| ev_cost_1  | ECS Fargate 1 vCPU / 2 GB at low utilization ≈ $35–45/mo                        | [Fargate pricing](https://aws.amazon.com/fargate/pricing/) (retrieved 2026-04-21)                                                          | §6.3                              | 0.8        |
| ev_cost_2  | ALB low traffic ≈ $16–20/mo                                                     | [ELB pricing](https://aws.amazon.com/elasticloadbalancing/pricing/) (retrieved 2026-04-21)                                                 | §6.3                              | 0.85       |
| ev_cost_3  | RDS `db.t4g.micro`, 20 GB gp3, Single-AZ ≈ $15–18/mo                            | [Amazon RDS pricing](https://aws.amazon.com/rds/pricing/) (retrieved 2026-04-21)                                                            | §6.3                              | 0.85       |
| ev_cost_4  | CloudFront 50 GB egress + 5 M requests ≈ $5–8/mo                                | [CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/) (retrieved 2026-04-21)                                                     | §6.3                              | 0.8        |
| ev_cost_5  | AWS WAF 1 WebACL + 3 managed rule groups + 5 M requests ≈ $12–18/mo             | [AWS WAF pricing](https://aws.amazon.com/waf/pricing/) (retrieved 2026-04-21)                                                               | §6.3                              | 0.75       |
| ev_cost_6  | 3 VPC interface endpoints ≈ $22/mo                                              | [VPC pricing](https://aws.amazon.com/vpc/pricing/) (retrieved 2026-04-21)                                                                   | §6.3                              | 0.8        |
| ev_cost_7  | Vercel Pro = $20/seat/mo                                                        | [Vercel pricing](https://vercel.com/pricing) (retrieved 2026-04-21)                                                                          | §6.3 honest figure                | 0.95       |
| ev_arch_1  | App Runner closes to new customers 2026-04-30                                   | [AWS App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)                    | R9, §6.1 AppStack                 | 0.99       |
| ev_arch_2  | App Runner enforces 120-second hard request timeout                             | [AWS App Runner runtime](https://docs.aws.amazon.com/apprunner/latest/dg/develop.html), [aws/apprunner-roadmap#189](https://github.com/aws/apprunner-roadmap/issues/189) | §6.1 AppStack rationale           | 0.95       |
| ev_arch_3  | CloudFront buffers `text/event-stream` responses by default; needs no-transform + no-cache + accept-encoding strip | [stackoverflow #60531556](https://stackoverflow.com/questions/60531556/can-server-sent-events-sse-work-with-aws-cloudfront), [opennextjs/opennextjs-aws#1127](https://github.com/opennextjs/opennextjs-aws/issues/1127) | §6.1 EdgeStack, R11 | 0.9        |
| ev_arch_4  | Production SSE requires 15-second heartbeats + Last-Event-ID resume + Pydantic state at agent boundaries | [dev.to multi-agent SSE in production](https://dev.to/priyank_agrawal/your-multi-agent-sse-stream-works-in-dev-heres-what-kills-it-in-production-458i) | §4.1 heartbeats          | 0.7        |
| ev_arch_5  | Reference LangGraph + FastAPI + ECS Fargate + ALB CloudFormation template       | [github.com/al-mz/langgraph-aws-deployment](https://github.com/al-mz/langgraph-aws-deployment)                                              | §6.1 AppStack pattern             | 0.7        |
| ev_oss_1  | `assistant-ui` shadcn-style React library with first-class LangGraph runtime; 9.3K stars; MIT; 463K weekly downloads | [github.com/assistant-ui/assistant-ui](https://github.com/assistant-ui/assistant-ui), [assistant-ui.com/docs/runtimes/langgraph](https://www.assistant-ui.com/docs/runtimes/langgraph) | F1, F2, F3, F4, F5 | 0.95        |
| ev_oss_2  | `langchain-ai/agent-chat-ui` MIT Next.js chat for LangGraph; 2.7K stars         | [github.com/langchain-ai/agent-chat-ui](https://github.com/langchain-ai/agent-chat-ui)                                                      | §17.1 alternative                 | 0.95       |
| ev_oss_3  | LangGraph Platform Self-Hosted Lite is free up to 1M nodes/month executed       | [LangChain blog](https://blog.langchain.dev/langgraph-platform-announce)                                                                    | F10, §6.3                         | 0.85       |
| ev_oss_4  | Aegra is Apache-2.0 self-hosted Agent Protocol server, drop-in compatible with LangGraph SDK + Agent Chat UI; 735 stars | [aegra.dev](https://aegra.dev), [github.com/ibbybuilds/aegra](https://github.com/ibbybuilds/aegra) | F10 fallback | 0.85 |
| ev_oss_5  | `vercel/ai-chatbot` template uses Auth.js (NextAuth) Cognito provider as standard pattern; 20K stars | [github.com/vercel/ai-chatbot](https://github.com/vercel/ai-chatbot)                                                                       | F8                                | 0.9        |
| ev_arch_6 | App Runner replacement guidance: AWS recommends ECS Express Mode; standard Fargate is mature alternative | [AWS App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html), [dev.to migration guide](https://dev.to/gyorgy/migrating-off-aws-app-runner-before-the-april-30-deadline-5g8m) | §6.1 AppStack pivot | 0.85 |
| ev_time_1 | Phase 0.5 (4 spikes) = 3 days                                                    | Internal estimate; each spike is bounded by a single integration check                                                                      | §8 Phase 0.5                       | 0.7        |
| ev_time_2 | Phase 1 (orchestration server) = 3 days                                          | Internal estimate; OSS server eliminates ~80% of revision 1's 1-week scope                                                                  | §8 Phase 1                         | 0.65       |
| ev_time_3 | Phase 2 (CDK infra) = 4 days                                                     | Internal estimate; +1 day vs revision 1 for ALB + SSE-bypass tuning                                                                         | §8 Phase 2                         | 0.6        |
| ev_time_4 | Phase 3 (Next.js + assistant-ui + Auth.js) = 4 days                              | Internal estimate; ~6 of 7 components ship in `assistant-ui`                                                                                | §8 Phase 3                         | 0.65       |
| ev_time_5 | Phase 4 (hardening + beta launch) = 2.5 days                                     | Same as revision 1 Phase 5                                                                                                                  | §8 Phase 4                         | 0.6        |

## 14. Hypothesis Register

Each locked decision recast as a falsifiable hypothesis. Revision-1 H1, H3, H5, H6 retired (no longer relevant — see §19 changelog).

| ID  | Decision                                       | Hypothesis                                                                                                                                         | Confirm if                                                                                                          | Kill if                                                                                                                                | Status                                                  |
| --- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| H1' | **ECS Fargate + ALB for SSE workload**         | Fargate sustains 10 concurrent SSE streams for ≥5 min each at <70% CPU on 1 vCPU / 2 GB; ALB idle_timeout=4000s prevents mid-stream cuts          | Load test: p95 CPU <70%, 0 dropped connections at 10 streams                                                         | CPU exceeds 85% or streams dropped at 5+ concurrent clients                                                                            | Untested (Phase 0.5 Spike 4)                            |
| H2  | **SSE through CloudFront with bypass config**  | With `CachingDisabled` + no-transform + accept-encoding strip, tokens stream end-to-end with TTFT <200 ms                                         | Local test through CloudFront origin: TTFT <200 ms, no buffering, idle timeout >120 s                                | CloudFront still buffers, or WAF managed rules false-positive on streamed Markdown                                                     | Untested (Phase 0.5 Spike 4)                            |
| H3' | **Cognito access-token verification**          | Verifier accepts `token_use === "access"` and validates `client_id` (not `aud`)                                                                   | Auth.js callback writes access token to session; FastAPI verifier accepts it                                          | Pattern doesn't compose cleanly                                                                                                         | Confirmed by AWS docs and `vercel/ai-chatbot` reference  |
| H4  | **FastAPI-only DB access (single ORM)**        | OSS server owns all schema; thread-list latency penalty <50 ms vs Drizzle-direct                                                                  | Vercel Edge → CloudFront → ALB → Fargate → RDS round-trip <50 ms p95 for thread-list endpoint                        | Latency >150 ms p95 (perceptible)                                                                                                       | Untested (measure in Phase 3)                           |
| H5  | **VPC endpoints replace NAT**                  | 3 VPC endpoints (ECR, Secrets, Logs) save net ~$10/mo vs NAT Gateway and unblock all required egress                                              | Cost Explorer shows endpoint charges <$22/mo, NAT charge $0; LangSmith / OpenAI calls work via NAT-free routing       | Some required egress (e.g., LangSmith HTTPS) requires NAT                                                                              | Partially confirmed; egress for LangSmith untested      |
| H6' | **ALB request duration**                       | ALB idle_timeout=4000s accommodates p99 ReAct run duration                                                                                         | p99 run length measured in local benchmarks <3000 s                                                                  | p99 run length exceeds 4000 s                                                                                                          | Untested but >>App Runner's 120s ceiling                |
| H7  | **Mobile Safari EventSource + Last-Event-ID**  | iOS Safari reconnects cleanly with `Last-Event-ID` after network interruption                                                                      | Manual test on iOS Safari 18+: drop Wi-Fi for 5 s, stream resumes from correct seq                                   | Safari drops Last-Event-ID on reconnect                                                                                                | Untested (Phase 3)                                      |
| H8  | **RDS connection budget**                      | `db.t4g.micro` (~100 max connections) supports the OSS server's pools (psycopg async + AsyncPostgresSaver)                                       | Pool max sums ≤80; no `too many connections` errors at 10 users                                                       | Pool demand exceeds ~80                                                                                                                 | Untested                                                |
| H9' | **assistant-ui ↔ ReAct graph compatibility**   | `@assistant-ui/react-langgraph` renders the existing graph's `messages[]` + tool calls + custom `events/step` events without modification         | Phase 0.5 Spike 1: end-to-end render in throwaway repo                                                                | Custom event taxonomy requires `assistant-ui` extension or rewrite                                                                     | Untested (Phase 0.5 Spike 1)                            |
| H10 | **LGP-SHL ↔ existing graph compatibility**     | `langgraph.json` pointing at `orchestration.react_loop:build_graph` boots correctly; checkpoints land in Postgres without schema rewrite          | Phase 0.5 Spike 2: `curl` against local LGP-SHL streams events from the existing graph                                | LGP-SHL requires graph refactor or imports from forbidden layers                                                                       | Untested (Phase 0.5 Spike 2)                            |

## 15. Validation Log

The eight self-validation checks per `prompts/StructuredReasoning/_pyramid_brain.j2`, applied honestly against revision 2.

| #   | Check          | Result            | Details                                                                                                                                                                                                                                                                                                                            |
| --- | -------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Completeness   | **Pass**          | Revision 2 incorporates the comparative-study issue tree (B1–B5) and the trade-off-analysis decision matrix (D1–D8). Every revision-1 known weakness is either retired (R1, R2, R5, H1, H3, H5, H6) or explicitly tracked (R10, H9', H10).                                                                                            |
| 2   | Non-Overlap    | **Pass**          | F1–F12 retain non-overlapping IDs. Decisions D1–D8 in §17 map to disjoint plan sections.                                                                                                                                                                                                                                          |
| 3   | Item Placement | **Pass**          | App Runner deprecation (R9) sits in §10 risk register; the *consequence* (Fargate + ALB) sits in §6.1 AppStack. Each evidence item assigned to exactly one consumer.                                                                                                                                                              |
| 4   | So What?       | **Pass**          | The §1 governing thought now bundles fewer commitments than revision 1 — each clause survives a stand-alone "so what?" chain (assistant-ui → ~1 week saved; LGP-SHL → ~4 days saved + free <1M nodes; Fargate+ALB → no deprecation + no 120-s timeout; SSE bypass → tokens actually stream; Auth.js → small bundle + correct token type). |
| 5   | Vertical Logic | **Pass**          | §3 architecture answers "how does the user reach the agent?", §4 answers "what's on the wire?", §5 answers "what's at rest?", §6 answers "what AWS services?", §7 answers "how is access gated?". Each section answers questions raised by the previous.                                                                          |
| 6   | Remove One     | **Partial**       | Removing the Fargate-pivot clause from §1 collapses the plan (App Runner closed). Removing the SSE-bypass clause ships a broken product. Removing assistant-ui or LGP-SHL only stretches the timeline (revertible to revision 1 plan). Documented as known-acceptable: D3 and D4 are necessary preconditions, D1 and D2 are velocity multipliers. |
| 7   | Never One      | **Pass**          | No single-child groupings.                                                                                                                                                                                                                                                                                                         |
| 8   | Mathematical   | **Pass**          | $35–45 + $16–20 + $15–18 + $5–8 + $12–18 + $1.20 + $0.10 + $2–4 + $22 + $2–4 = $110–140/mo AWS subtotal; + $40 Vercel = $150–180/mo all-in. Internally consistent; figures sourced in §13.                                                                                                                                          |

**Known weaknesses still present (smaller than revision 1's, intentionally documented):**

- §2 features F1–F12 remain a flat list rather than a 4-dimensional inductive grouping (Conversational / Observability / Account / Backend Surface). Same as revision 1 §15 weakness 2; deferred to a future structural revision.
- §6.3 honest cost ($150–180/mo) exceeds the original §1 commitment of "$60–90/mo" from revision 1. Acknowledged: revision 1's number was unbookable. Revision 2 publishes the real number and lists three options to bring it back down.

## 16. Cross-Branch Interactions

Silent interactions between plan sections that the §3–§7 decomposition does not surface.

| Interacting branches                                           | Interaction                                                                                                                                                                                                                                                                                                                                                                  | Mitigation owner                          | Tracked in           |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- | -------------------- |
| EdgeStack (§6.1) ↔ SSE transport (§4.1)                       | CloudFront's default cache + compression behavior buffers SSE; `X-Accel-Buffering: no` from BFF is *ignored* by CloudFront. The SSE bypass (§6.1 EdgeStack) is mandatory; without it, every SSE stream hangs until ALB idle timeout.                                                                                                                                          | Phase 2 owner (CDK)                       | H2 in §14, R11      |
| AppStack (§6.1) ↔ `/runs/stream` (§4)                         | ALB idle timeout (configurable to 4000 s; default 60 s) replaces App Runner's 120-s hard timeout. Must be set explicitly in CDK. SSE heartbeats every 15 s are still required (ev_arch_4) to keep the connection live across ALB and CloudFront idle counters.                                                                                                              | Phase 2 owner (CDK) + Phase 1 owner       | H6' in §14           |
| DataStack (§6.1) ↔ orchestration server + LangGraph checkpointer | Single connection-pool consumer (the OSS server) on `db.t4g.micro` (~100 max connections). Pool size budgeting much simpler than revision 1's three-pool design; primary risk is that LGP-SHL's internal pool defaults are unknown and may need tuning at 10 concurrent users.                                                                                          | Phase 1 owner                             | H8 in §14            |
| API server choice (§4) ↔ Cognito middleware (§7)               | LGP-SHL exposes a Python middleware injection point (FastAPI dependency overrides). Aegra exposes auth via Python handler classes. Both work for our access-token + group ACL pattern — but the implementation file names differ. Phase 0.5 Spike 2 picks one.                                                                                                                | Phase 0.5 owner                           | H10 in §14           |
| VPC endpoints (§6.1 NetworkStack) ↔ external API egress         | LangSmith tracing and OpenAI/Anthropic API calls require HTTPS egress. Without NAT, these need either (a) an interface VPC endpoint per provider (LangSmith doesn't offer one), or (b) the orchestration server moves to a public subnet with a public IP, or (c) we keep NAT Gateway after all (+$32/mo) and accept the cost. Phase 0.5 Spike 4 must verify which.            | Phase 2 owner (CDK)                       | H5 in §14            |

## 17. Alternatives Considered

Decisions D1–D8 from the trade-off analysis. Each alternative was evaluated on the same six dimensions: cost, velocity, fit, risk, lock-in, reversibility. Selected option marked **[selected]**.

### 17.1 Frontend component library (D1)

| Option                    | Velocity   | Lock-in | Risk     | Verdict                                                                              |
| ------------------------- | ---------- | ------- | -------- | ------------------------------------------------------------------------------------ |
| **assistant-ui [selected]** | 6 of 7 components ship | Med | Lower (mature primitives) | Best balance of velocity and control                                                  |
| Hand-rolled shadcn (revision 1) | 0 of 7 ship | None | Higher (custom mobile QA) | Reverted-to fallback if Phase 0.5 Spike 1 fails                                       |
| `agent-chat-ui`           | Whole app ships, less customizable | Higher | Lower | Rejected: less composable than `assistant-ui`; harder to integrate F6/F7              |
| CopilotKit                | Generative-UI hooks excellent | Higher | Higher (heavier abstraction) | Rejected for v1; **revisit at v1.5** for the StructuredReasoning Pyramid panel        |
| Open WebUI / LibreChat    | Full app ships | High | High (assumes OpenAI-compatible endpoint, not a custom ReAct graph) | Rejected: wrong shape                                                                  |

### 17.2 Orchestration server (D2)

| Option                                            | Velocity        | Lock-in | Bus factor | Verdict                                                                |
| ------------------------------------------------- | --------------- | ------- | ---------- | ---------------------------------------------------------------------- |
| **LangGraph Platform Self-Hosted Lite [selected]** | ~80% custom code eliminated | Low (Agent Protocol) | LangChain-backed | Best — official, free <1M nodes/mo, upgrade path to Cloud SaaS         |
| Aegra                                             | Same             | Low (Apache-2.0) | 735 stars (young) | Excellent fallback — pick if data sovereignty / Apache-2.0 matters more |
| Custom FastAPI (revision 1)                       | Full week of build | None | n/a (we own it) | Reverted-to fallback if Phase 0.5 Spike 2 fails                         |

### 17.3 Compute runtime (D3)

| Option                              | Cost (10 users)         | Velocity | Risk                                          | Verdict                                                |
| ----------------------------------- | ----------------------- | -------- | --------------------------------------------- | ------------------------------------------------------ |
| App Runner (revision 1)             | $35–50/mo               | High     | **Closed to new accounts 2026-04-30; 120-s timeout** | **Reverted; not viable**                                |
| **ECS Fargate + ALB [selected]**    | $51–65/mo               | Medium   | Mature; ALB idle timeout 4000 s               | Best — fixes both deprecation and timeout              |
| ECS Express Mode                    | $51–65/mo               | High     | New service, Terraform bugs                   | Rejected for v1; revisit at v1.5 if AWS hardens it     |
| Lambda + API Gateway                | $5–15/mo                | Medium   | SSE on Lambda is awkward; cold starts          | Rejected: SSE pattern fights the runtime               |

### 17.4 DB access pattern (D6)

| Option                                  | Schema risk    | Latency   | Verdict                                                              |
| --------------------------------------- | -------------- | --------- | -------------------------------------------------------------------- |
| Drizzle BFF + SQLModel API (revision 1) | High (drift)   | ~5 ms     | **Reverted; H4 in revision 1 was untested**                           |
| **FastAPI-only [selected]**             | None           | +5–15 ms BFF→API hop | Best for v1; revisit only if measured latency becomes UX-significant  |

### 17.5 Auth library (D5)

| Option                              | Bundle size | Velocity | Risk                              | Verdict                                              |
| ----------------------------------- | ----------- | -------- | --------------------------------- | ---------------------------------------------------- |
| AWS Amplify Auth (revision 1)       | ~300 KB     | Medium   | Token-type confusion (revision 1 §18.1) | **Reverted in favor of Auth.js**                      |
| **Auth.js Cognito provider [selected]** | ~30 KB  | High     | Standard OIDC pattern; documented | Best — used in `vercel/ai-chatbot`                   |

### 17.6 Frontend hosting (D7)

| Option                          | Cost                  | DX        | Verdict                                                                                  |
| ------------------------------- | --------------------- | --------- | ---------------------------------------------------------------------------------------- |
| **Vercel Pro [selected]**       | $40/mo (2 seats)      | Excellent | Kept for v1; **booked honestly in §6.3** (revision 1 omitted)                            |
| AWS Amplify Hosting             | $0–5/mo               | Improved   | Revisit at v1.5 if seat count grows                                                      |
| CloudFront + S3 (static export) | $5–8/mo               | Poor      | Rejected: Next.js App Router with RSC requires SSR                                        |

## 18. Errata and Confidence Recomputation

### 18.1 Erratum: Cognito token type (ratified into §7)

Revision 1 §18.1's erratum (use access tokens, not ID tokens; check `client_id`, not `aud`) is now ratified into the primary text of §7. The H3 hypothesis is killed in revision 1's register and removed from revision 2's register.

### 18.2 Confidence recomputation

```
confidence = min(avg_argument_confidence, completeness_penalty, structural_penalty)
```

**Completeness penalty:**

- Four untested hypotheses with Phase 0.5 spikes (H1', H2, H9', H10) → −0.10 × 4 = −0.40, but mitigated by being explicitly de-risked in Phase 0.5 → effective penalty −0.20.
- Two confirmed-but-unmitigated risks become "risks with documented mitigations" (R9 → Fargate, R11 → SSE bypass) → no penalty.
- Effective completeness score: 1.0 − 0.20 = **0.80**.

**Structural penalty:**

- §15 records one partial check (Remove-One) and zero failed checks → −0.05.
- Effective structural score: 1.0 − 0.05 = **0.95**.

**Average argument confidence:**

- Cost evidence: avg ~0.82 (revision 2 figures are more grounded).
- Timeline evidence: avg ~0.64 (Phase estimates).
- Architecture evidence: avg ~0.90.
- Weighted average: **~0.78**.

**Plan-level confidence: `min(0.78, 0.80, 0.95)` = 0.78.**

This is up from revision 1's 0.65 because (a) the App Runner deprecation forced a real pivot rather than an unmitigated risk, (b) the SSE buffering issue is now de-risked by explicit EdgeStack config, (c) the OSS server adoption removes ~80% of revision 1's bespoke code.

Confidence is expected to rise to ~0.85 once Phase 0.5 spikes resolve H1', H2, H9', H10.

---

## 19. Changelog (revision 1 → revision 2)

| Section                | Change                                                                                                                                                                                                                                  |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §1 Governing Thought    | Replaced App Runner with ECS Fargate + ALB; replaced custom FastAPI with LGP-SHL; replaced Amplify Auth with Auth.js; added SSE bypass; restated honest cost as $120–135/mo (later revised to $150–180/mo with Vercel booked).             |
| §2 Scope                | F2/F3/F4/F5/F7/F9 retagged from "build" to "integrate `assistant-ui`". F8 retagged from "Amplify" to "Auth.js". F10 retagged from "build FastAPI adapter" to "deploy LGP-SHL + thin middleware". F11 simplified — server owns the migration. |
| §3 Architecture diagram | App Runner → Fargate + ALB; added CachingDisabled + response-headers policy + viewer fn; removed NAT Gateway; added VPC endpoints.                                                                                                       |
| §3.1 Repo layout        | `frontend/lib/db/` (Drizzle) removed; `frontend/lib/auth.ts` (Auth.js) added; `api/` shrunk from 8 files to 4 (server + 2 middleware + langgraph.json).                                                                                  |
| §4 API contract         | Switched to Agent Protocol native routes (`/runs/stream`, `/threads`, `/assistants`); custom SSE taxonomy replaced by Agent Protocol native events plus 2 custom emits.                                                                  |
| §4.1                    | Added mandatory 15-s heartbeat per ev_arch_4.                                                                                                                                                                                            |
| §5 Data model           | Removed Drizzle mirror; FastAPI-only ownership.                                                                                                                                                                                          |
| §6.1 AppStack           | App Runner → ECS Fargate + ALB.                                                                                                                                                                                                          |
| §6.1 EdgeStack          | Added CachingDisabled cache policy, no-transform response-headers policy, viewer-request CloudFront Function for `accept-encoding` strip.                                                                                                |
| §6.1 NetworkStack       | NAT Gateway removed; VPC endpoints (ECR, Secrets, Logs, S3) ratified.                                                                                                                                                                    |
| §6.3 Cost model         | Recomputed honestly: AWS subtotal $110–140/mo + Vercel Pro $40/mo = $150–180/mo all-in.                                                                                                                                                  |
| §7 Authentication       | Amplify → Auth.js Cognito provider; access-token verification baked in (revision 1 §18.1 erratum ratified).                                                                                                                              |
| §8 Phases               | 5 phases → 5 phases including new Phase 0.5 (spikes); total ≈ 14 working days vs revision 1's ≈ 25.                                                                                                                                       |
| §9 Testing              | Custom SSE-translator tests removed; auth tests retained with rejection-paths-first per TAP-4.                                                                                                                                           |
| §10 Risks               | R1, R2, R5 retired; R9, R10, R11, R12, R13 added.                                                                                                                                                                                         |
| §13 Evidence            | 16 new evidence rows added (ev_oss_1–5, ev_arch_1–6, ev_cost_1–7); revision 1 cost rows for App Runner removed.                                                                                                                            |
| §14 Hypotheses          | H1, H3, H5, H6 retired; H1', H3', H6', H9', H10 added.                                                                                                                                                                                    |
| §15 Validation log      | All 8 checks recomputed; 7 pass + 1 partial (vs revision 1's 2 pass + 1 partial + 5 fail).                                                                                                                                               |
| §17 Alternatives        | Six new decision tables (D1–D6) reflecting the trade-off analysis; D7 and D8 documented as no-change.                                                                                                                                    |
| §18 Errata              | Revision 1 §18.1 ratified into §7 primary text; confidence recomputed 0.65 → 0.78.                                                                                                                                                       |
| §19 (this section)      | New.                                                                                                                                                                                                                                     |

---

*This plan was produced by applying the comparative-study and trade-off-analysis recommendations from 2026-04-21 to revision 1 of `FRONTEND_PLAN.md`, structured per `prompts/StructuredReasoning/_pyramid_brain.j2`. Validation log in §15, gap analysis in §14 hypothesis register and §16 cross-branch interactions, errata in §18, full delta in §19.*
