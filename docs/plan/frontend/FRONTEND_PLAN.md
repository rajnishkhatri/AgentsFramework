# FRONTEND_PLAN.md — Web Chat UI for the ReAct Agent

> **Status**: planning. No code written yet. This document is the source of truth for v1 frontend + AWS backend exposure work. It is structured using the Pyramid Principle (`prompts/StructuredReasoning/_pyramid_brain.j2`).

## 1. Governing Thought

Ship a Claude-style web chat for the existing LangGraph ReAct agent — Next.js 15 (App Router) on **Vercel** with Tailwind + shadcn/ui, talking over **Server-Sent Events** to a new FastAPI adapter that runs the unchanged agent on **AWS App Runner** (us-east-1), gated by **Amazon Cognito**, persisting to **RDS Postgres**, fronted by **CloudFront + WAF** — preserving the four-layer architecture (the FastAPI adapter is a thin orchestration adapter exactly like `cli.py`), keeping monthly AWS spend in the $60–90 range, and deferring the StructuredReasoning Pyramid panel and per-tool authorization UI to v1.5.

Confidence: **0.82**.

## 2. Scope

### In scope (v1, ~6 weeks of frontend work)


| ID  | Feature                                                                                                     | Backend hook                               |
| --- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| F1  | Thread sidebar (rename / archive / delete / search-by-title)                                                | LangGraph `thread_id`                      |
| F2  | Streaming markdown messages, syntax-highlighted code blocks, copy/download                                  | `messages[]` + LangGraph `astream_events`  |
| F3  | Stop / regenerate / edit-and-resend last message                                                            | `DELETE /runs/{id}` + checkpoint rewind    |
| F4  | Mobile-first responsive composer (Tailwind + shadcn)                                                        | n/a (FE)                                   |
| F5  | Collapsible tool-call cards (shell / file_io / web_search)                                                  | `services/tools/registry.py`               |
| F6  | Step counter + cost meter                                                                                   | `state.step_count`, `state.total_cost_usd` |
| F7  | Model badge per turn (`fast` / `capable`)                                                                   | `ModelProfile.tier`                        |
| F8  | Cognito sign-in (email + OTP), `cognito:sub` → `user_id`                                                    | `eval_capture.record(user_id=…)`           |
| F9  | Light/dark theme toggle                                                                                     | n/a (FE)                                   |
| F10 | New `api/` FastAPI adapter exposing `/chat/stream`, `/chat/cancel`, `/threads`, `/runs`, `/agents`          | `orchestration.react_loop.build_graph`     |
| F11 | LangGraph checkpointer migration `AsyncSqliteSaver` → `AsyncPostgresSaver`                                  | `langgraph-checkpoint-postgres`            |
| F12 | AWS infra in CDK (TS): App Runner, RDS Postgres, Cognito, CloudFront, WAF, Secrets Manager, ECR, CloudWatch | `infra/`                                   |


### Deferred to v1.5 (next 4 weeks)

- StructuredReasoning Pyramid panel (`AnalysisOutput` viewer) — wait for `StructuredReasoning/` to land on `main`.
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

### Out of scope forever

- `shell` tool exposed to non-admin users on the public surface (always behind admin role + feature flag).
- Hardcoded prompts in TS — system prompts continue to be `.j2` files rendered by `PromptService` (architecture invariant H1).
- Anything that imports from `orchestration/` into `components/` or `services/` (architecture invariant).

## 3. Architecture

```
Browser (mobile + desktop)
  │  HTTPS
  ▼
┌──────────────────────── Vercel ──────────────────────────┐
│ Next.js 15 App Router                                    │
│  • RSC: shell, sidebar, settings                         │
│  • Client: composer, message list, tool-call cards       │
│  • Route Handlers (BFF):                                 │
│      /api/auth/[...]      → Amplify Auth (Cognito OIDC)  │
│      /api/threads/*       → Drizzle → RDS Postgres       │
│      /api/run/stream      → SSE proxy → App Runner       │
│      /api/run/cancel      → DELETE proxy → App Runner    │
└──────────────────────────────────────────────────────────┘
                  │  HTTPS (JWT-bearing)
                  ▼
┌──────────────────────── AWS account: agent-prod / us-east-1 ──────────────┐
│  CloudFront + WAF (managed rules: AWSManagedRulesCommonRuleSet,           │
│                    AWSManagedRulesKnownBadInputsRuleSet,                  │
│                    AWSManagedRulesAmazonIpReputationList)                 │
│      │                                                                    │
│      ▼                                                                    │
│  App Runner service "agent-api" (1 vCPU / 2 GB, min=1, max=3)             │
│   • FastAPI image from ECR (Python 3.11 slim)                             │
│   • Endpoints: /chat/stream (SSE), /chat/cancel, /threads, /runs,         │
│                /agents, /healthz                                          │
│   • Verifies Cognito JWT (RS256, JWKs cached 24h)                         │
│   • Reads secrets via task IAM role from Secrets Manager                  │
│   • VPC connector → private subnets                                       │
│      │                                                                    │
│      ▼                                                                    │
│  RDS Postgres 16 (db.t4g.micro, Single-AZ, KMS encrypted, private subnet) │
│   • LangGraph checkpoints (AsyncPostgresSaver schema)                     │
│   • App schema: users, threads, messages, runs, tool_calls                │
│                                                                           │
│  Cognito User Pool "agent-users"                                          │
│   • Email sign-in, OTP MFA, no self-signup (admin invites for beta)       │
│                                                                           │
│  Secrets Manager: OPENAI_API_KEY, AGENT_FACTS_SECRET, DB_URL              │
│  ECR: agent-api image repo                                                │
│  CloudWatch: log group /aws/apprunner/agent-api  + custom metrics         │
└───────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Repository layout (monorepo subdirectories)

```
agent/
├── frontend/                   ← Next.js 15 app (deploy target = Vercel)
│   ├── app/
│   │   ├── (chat)/             ← chat route group
│   │   │   ├── layout.tsx
│   │   │   └── [threadId]/page.tsx
│   │   ├── api/
│   │   │   ├── auth/[...nextauth]/route.ts   ← Amplify-backed handler
│   │   │   ├── threads/route.ts
│   │   │   ├── threads/[id]/route.ts
│   │   │   ├── run/stream/route.ts           ← SSE proxy
│   │   │   └── run/cancel/route.ts
│   │   └── layout.tsx
│   ├── components/             ← shadcn/ui + custom: Composer, MessageList,
│   │                             ToolCallCard, ModelBadge, ThreadSidebar
│   ├── lib/
│   │   ├── amplify.ts          ← AWS Amplify Auth config
│   │   ├── db/                 ← Drizzle schema + client
│   │   └── sse-client.ts       ← typed EventSource wrapper
│   ├── drizzle.config.ts
│   ├── tailwind.config.ts
│   ├── package.json
│   └── README.md
│
├── api/                        ← NEW FastAPI orchestration adapter
│   ├── __init__.py
│   ├── main.py                 ← uvicorn entry; builds graph (same factory as cli.py)
│   ├── deps.py                 ← Cognito JWT verification, DB session
│   ├── routes/
│   │   ├── chat.py             ← /chat/stream (SSE), /chat/cancel
│   │   ├── threads.py
│   │   ├── runs.py
│   │   └── agents.py
│   ├── sse.py                  ← LangGraph events → SSE event taxonomy
│   ├── models/                 ← SQLModel mirrors of Drizzle schema
│   └── README.md
│
├── infra/                      ← NEW AWS CDK app (TypeScript)
│   ├── bin/agent-infra.ts
│   ├── lib/
│   │   ├── network-stack.ts    ← VPC, subnets, security groups
│   │   ├── data-stack.ts       ← RDS, Secrets Manager, KMS
│   │   ├── auth-stack.ts       ← Cognito User Pool + Hosted UI domain
│   │   ├── app-stack.ts        ← ECR, App Runner, IAM
│   │   └── edge-stack.ts       ← CloudFront + WAF
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
│   │   └── test_api_layer.py   ← NEW: api/ may import only from orchestration/, services/, trust/
│   └── api/
│       ├── test_chat_stream_contract.py
│       └── test_jwt_verification.py
└── FRONTEND_PLAN.md            ← this file
```

### 3.2 Layer invariants extended to `api/`

`api/` is treated identically to `cli.py` — a **thin orchestration adapter**. New architecture test (`tests/architecture/test_api_layer.py`):

- `api/` MAY import from: `orchestration/`, `services/`, `trust/`, `components/` (only via the `build_graph` factory).
- `api/` MAY NOT import from: `meta/`, `StructuredReasoning/components/`, `StructuredReasoning/services/` directly.
- Nothing in `components/`, `services/`, `trust/`, `orchestration/`, `meta/` may import from `api/`.

## 4. API Contract (FastAPI adapter)

All endpoints require a valid Cognito JWT (`Authorization: Bearer <jwt>`) verified via Cognito JWKs. `cognito:sub` is mapped to `user_id` and threaded through to `eval_capture`.


| Method   | Path                     | Purpose                                           | Notes                                                   |
| -------- | ------------------------ | ------------------------------------------------- | ------------------------------------------------------- |
| `POST`   | `/chat/stream`           | Start a new run on an existing thread; stream SSE | Body: `{thread_id, task_input, agent_id?, model_tier?}` |
| `DELETE` | `/runs/{run_id}`         | Request cancellation of an in-flight run          | Sets cancel flag in checkpoint metadata                 |
| `GET`    | `/threads`               | List user's threads                               | Pagination via `?cursor=`                               |
| `POST`   | `/threads`               | Create a thread                                   | Returns `thread_id`                                     |
| `PATCH`  | `/threads/{id}`          | Rename / archive                                  |                                                         |
| `DELETE` | `/threads/{id}`          | Soft-delete                                       |                                                         |
| `GET`    | `/threads/{id}/messages` | Replay messages from checkpoint                   | For initial page load                                   |
| `GET`    | `/agents`                | List agents the user owns (`AgentFactsRegistry`)  |                                                         |
| `GET`    | `/healthz`               | Liveness                                          | Public, no auth                                         |
| `GET`    | `/readyz`                | Readiness (DB + Secrets reachable)                | Public                                                  |


### 4.1 SSE event taxonomy on `/chat/stream`

LangGraph `astream_events` types are mapped 1:1 to named SSE events. Every event carries `id: <run_id>:<seq>` so `EventSource` reconnect via `Last-Event-ID` resumes mid-stream.


| SSE `event:`    | Payload                                               | Source LangGraph event       |
| --------------- | ----------------------------------------------------- | ---------------------------- |
| `run.started`   | `{run_id, thread_id, model, started_at}`              | `on_chain_start` (root)      |
| `token`         | `{delta: string}`                                     | `on_chat_model_stream`       |
| `tool.start`    | `{tool_call_id, name, input}`                         | `on_tool_start`              |
| `tool.end`      | `{tool_call_id, output, error?, duration_ms}`         | `on_tool_end`                |
| `model.switch`  | `{from_tier, to_tier, reason}`                        | `state.model_history` append |
| `step`          | `{step_count, total_cost_usd, tokens_in, tokens_out}` | per-node end                 |
| `run.completed` | `{final_message, step_count, total_cost_usd}`         | `on_chain_end` (root)        |
| `run.error`     | `{error_type, message, retryable}`                    | error path                   |
| `run.cancelled` | `{at_step}`                                           | cancel flag observed         |


## 5. Data Model

### 5.1 RDS Postgres schema (app-owned; LangGraph owns its own checkpoint tables)

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
  id            UUID PRIMARY KEY,
  thread_id     UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  user_id       UUID NOT NULL REFERENCES users(id),
  workflow_id   TEXT NOT NULL,                    -- mirrors AgentState.workflow_id
  task_id       TEXT NOT NULL,
  status        TEXT NOT NULL,                    -- running|completed|cancelled|error
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  step_count    INT NOT NULL DEFAULT 0,
  total_cost_usd NUMERIC(10, 6) NOT NULL DEFAULT 0
);

CREATE TABLE messages (
  id            UUID PRIMARY KEY,
  run_id        UUID REFERENCES runs(id) ON DELETE SET NULL,
  thread_id     UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  role          TEXT NOT NULL,                    -- user|assistant|tool|system
  content       JSONB NOT NULL,                   -- LangChain message payload
  model         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_thread_created_idx ON messages (thread_id, created_at);

CREATE TABLE tool_calls (
  id              UUID PRIMARY KEY,
  message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  tool_name       TEXT NOT NULL,                  -- shell|file_io|web_search
  input           JSONB NOT NULL,
  output          JSONB,
  error           TEXT,
  duration_ms     INT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 5.2 LangGraph checkpointer

Replace `AsyncSqliteSaver` with `AsyncPostgresSaver` (from `langgraph-checkpoint-postgres`). Pool managed by `psycopg_pool.AsyncConnectionPool`. Connection string from Secrets Manager.

### 5.3 Drizzle schema mirror

`frontend/lib/db/schema.ts` mirrors the SQL above for the BFF Route Handlers. Migrations live in `frontend/drizzle/`. Generation: `drizzle-kit push` against the same RDS instance.

## 6. AWS Infrastructure (CDK in TypeScript)

### 6.1 Stacks


| Stack          | Resources                                                                                                                                                                                                                                    | Notes                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `NetworkStack` | VPC (2 AZs), public + private subnets, NAT, security groups                                                                                                                                                                                  | Reused by data + app stacks               |
| `DataStack`    | RDS Postgres 16 (`db.t4g.micro`, 20 GB gp3, Single-AZ, deletion protection ON), KMS key, Secrets Manager secrets (`openai_api_key`, `agent_facts_secret`, `db_url`)                                                                          | RDS in private subnet, no public endpoint |
| `AuthStack`    | Cognito User Pool, Hosted UI domain, app client (PKCE, no client secret for SPA), groups: `admin`, `beta`                                                                                                                                    | No self-signup; admin invites only        |
| `AppStack`     | ECR repo `agent-api`, App Runner service (1 vCPU / 2 GB, **min=1**, max=3, auto-deploy on ECR push), VPC connector to private subnets, instance role with read access to secrets + RDS IAM auth, observability config                        | min=1 keeps cold start out of user path   |
| `EdgeStack`    | CloudFront distribution → App Runner origin, AWS WAF WebACL with managed rules: `AWSManagedRulesCommonRuleSet` + `AWSManagedRulesKnownBadInputsRuleSet` + `AWSManagedRulesAmazonIpReputationList`, custom rate-limit rule (1000 req/5min/IP) | WAF in `us-east-1` for CloudFront         |


### 6.2 IAM least-privilege highlights

- App Runner instance role: `secretsmanager:GetSecretValue` (3 named secrets), `rds-db:connect` (specific user), `logs:CreateLogStream` + `PutLogEvents` (its own log group only), `cognito-idp:GetUser` (for JWT verification only if not using JWKs caching).
- BFF (Vercel) → AWS only via JWT-bearing HTTPS to CloudFront; **no AWS credentials in Vercel env**.

### 6.3 Cost model (private-beta, ≤10 concurrent users)


| Item            | Configuration                                  | Estimated $/mo                     |
| --------------- | ---------------------------------------------- | ---------------------------------- |
| App Runner      | 1 vCPU / 2 GB, min=1 always-on, 5% utilization | $35–50                             |
| RDS Postgres    | `db.t4g.micro`, 20 GB gp3, Single-AZ           | $15–18                             |
| CloudFront      | 50 GB egress, 5M requests                      | $5–8                               |
| AWS WAF         | 1 WebACL + 3 managed rule groups + 5M requests | $12–18                             |
| Cognito         | <50,000 MAUs (free tier)                       | $0                                 |
| Secrets Manager | 3 secrets                                      | $1.20                              |
| ECR             | <1 GB stored                                   | $0.10                              |
| CloudWatch      | logs + custom metrics                          | $2–5                               |
| NAT Gateway     | 1 AZ, low traffic                              | **$32** (largest single line item) |
| Data transfer   | misc                                           | $2–4                               |
| **Total**       |                                                | **$104–137/mo**                    |


> **Budget tension**: under-$100 target is tight with NAT Gateway included. Mitigation options, ranked: (a) drop NAT and use VPC endpoints for ECR/Secrets/CloudWatch (saves ~$32/mo, adds 3 endpoint cost ~$22/mo for net ~$10 saved), (b) accept ~$110/mo as private-beta steady state, (c) reduce CloudFront/WAF coverage by skipping WAF for v1 (saves $12–18/mo but contradicts "edge protection from day 1" decision). **Plan recommendation**: take option (a) — VPC endpoints for ECR + Secrets Manager + CloudWatch Logs — settling at **$80–95/mo**.

## 7. Authentication

- **Provider**: Amazon Cognito User Pool, OIDC.
- **Client library**: AWS Amplify Auth (`aws-amplify`) on the Next.js frontend. Hosted-UI sign-in flow disabled; we render our own forms calling `signIn()` / `confirmSignIn()`.
- **Token verification**: FastAPI verifies JWT signature against Cognito JWKs (cached 24h), checks `iss`, `aud`, `exp`, and `token_use === "id"`. Library: `python-jose` or `pyjwt[crypto]`.
- `**user_id` propagation**: `cognito:sub` UUID becomes `users.id` and is passed into every `graph.ainvoke(config={"configurable": {"user_id": ..., "task_id": ..., "thread_id": ...}})` call, satisfying the `eval_capture.record(user_id, task_id)` invariant from `AGENTS.md`.
- **Authorization (v1)**: bootstrap user (Cognito group `beta`) gets all tools allowed inside the FastAPI adapter. Hard-coded gate in `api/routes/chat.py`.
- **Authorization (v1.5)**: new `services/authorization_service.py` returns `PolicyDecision` per `(user_id, agent_id, tool_name)`, backed by `Capability` records in the trust kernel. The FastAPI adapter is the only consumer.

## 8. Phased Milestones

### Phase 0 — Decisions locked (this document, ~0.5 day)

- Pyramid analyses (compute, transport, UI features)
- AWS service selection (App Runner, RDS, Cognito, CloudFront+WAF)
- Repo layout
- FRONTEND_PLAN.md merged

**Acceptance**: this file is on `main`.

### Phase 1 — FastAPI adapter on top of existing graph (1 week)

- Add `fastapi`, `uvicorn[standard]`, `psycopg[binary,pool]`, `langgraph-checkpoint-postgres`, `python-jose[cryptography]`, `sqlmodel` to `pyproject.toml` `[project.optional-dependencies] api`.
- Create `api/main.py` that builds the graph using **the same factory as `cli.py`** (extract `build_graph_for_user(user_id)` helper to remove duplication; both `cli.py` and `api/main.py` call it).
- `api/sse.py`: typed translator from LangGraph events to the SSE taxonomy in §4.1.
- `api/routes/chat.py`: `POST /chat/stream`, `DELETE /runs/{id}`.
- `api/routes/threads.py`, `api/routes/runs.py`, `api/routes/agents.py`.
- `api/deps.py`: Cognito JWT verifier.
- `tests/architecture/test_api_layer.py`: enforce import boundaries for `api/`.
- `tests/api/test_chat_stream_contract.py`: SSE contract test (mocked LLM, verifies event sequence).
- `tests/api/test_jwt_verification.py`: rejection paths first (missing, expired, wrong issuer, wrong audience), then acceptance.
- Local Docker compose: FastAPI + Postgres + minimal Cognito mock (LocalStack).

**Acceptance**: `pytest tests/api/ -q` green; `curl -N` against local FastAPI streams a multi-event SSE response with mocked LLM; existing `pytest tests/ -q` still green; existing `python -m agent.cli "…"` still works unchanged.

### Phase 2 — AWS infrastructure via CDK (1 week)

- `cd infra && npm init`, install CDK + constructs.
- Implement five stacks per §6.1.
- `cdk synth` produces clean CloudFormation.
- `cdk deploy --all` to a new `agent-prod` account in `us-east-1`.
- ECR push of FastAPI image; App Runner picks it up.
- CloudFront distribution returns 200 from `/healthz` end-to-end.
- Cognito User Pool created; admin invite to one beta user works.
- CloudWatch log group has structured JSON entries from a test request.

**Acceptance**: from a laptop, `curl -H "Authorization: Bearer <real Cognito JWT>" https://<cf-domain>/threads` returns `[]`; AWS Cost Explorer projects ≤$100/mo at current usage.

### Phase 3 — Next.js scaffold + auth + threads (1.5 weeks)

- `frontend/` scaffolded with `create-next-app@latest --ts --tailwind --app`.
- shadcn/ui installed; theme tokens calibrated to a Claude-desktop-like palette (off-white `#f9f7f5` light, near-black `#1f1e1d` dark).
- `frontend/lib/amplify.ts` wires Cognito (User Pool ID + App Client ID from Vercel env).
- Sign-in and OTP confirmation pages.
- Drizzle schema + first migration applied to RDS via SSH tunnel for now (not exposed publicly).
- Route handlers: `GET/POST /api/threads`, `GET /api/threads/[id]/messages` (proxies to FastAPI).
- `ThreadSidebar` component (rename / archive / delete).
- Empty chat shell renders for an authenticated user.
- Vercel project linked; preview deploy on every PR.

**Acceptance**: deploying a PR to Vercel preview, an invited beta user can sign in and create / rename / delete a thread. End-to-end happy path.

### Phase 4 — Streaming chat (1.5 weeks)

- `frontend/lib/sse-client.ts`: typed `EventSource` wrapper, reconnect with `Last-Event-ID`, dispatches typed events to a Zustand store.
- `app/api/run/stream/route.ts`: SSE proxy from BFF → App Runner. Forwards `Authorization`, sets `text/event-stream`, `X-Accel-Buffering: no`.
- `Composer` component (multiline, ⌘↩ / Ctrl↩ to send, mobile-keyboard-friendly).
- `MessageList` component, streaming markdown via `react-markdown` + `remark-gfm` + `rehype-highlight` + per-code-block copy button.
- `ToolCallCard` component (collapsible, name + JSON input + output, error highlighted).
- `ModelBadge` component (`fast` ⚡ / `capable` 🧠).
- Step counter + cost meter in the message footer.
- `Stop` button → `DELETE /runs/{id}`.
- `Regenerate` button → new run on same thread, drops the last assistant message.
- Light/dark theme toggle persists in `localStorage`.
- Mobile layout reviewed on iOS Safari + Android Chrome.

**Acceptance**: an invited beta user signs in on mobile, asks `"What is the capital of France?"`, sees streamed markdown answer with a model badge and final cost, then asks `"List files in /etc"` and sees a collapsible `shell` tool-call card with output. Stop button cancels mid-run.

### Phase 5 — Hardening + private beta launch (0.5 week)

- WAF managed rules tuned (no false positives on chat traffic).
- Cognito MFA enforced for all users.
- CloudWatch alarms: 5xx rate, App Runner CPU, RDS CPU, RDS connections, NAT bytes.
- Runbook documented in `infra/RUNBOOK.md`.
- Five external beta users invited.

**Acceptance**: 7 days of production usage with no Sev-2 incident; AWS Cost Explorer shows actual spend within ±20% of projection.

## 9. Testing Strategy (aligned with `AGENTS.md`)


| Layer                 | Code under test                               | Test technique                                                                                                        | Marker |
| --------------------- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------ |
| L1 (`trust/`)         | unchanged                                     | unchanged                                                                                                             | none   |
| L2 (`services/`)      | unchanged + `authorization_service.py` (v1.5) | unchanged                                                                                                             | none   |
| L3 (`components/`)    | unchanged                                     | unchanged                                                                                                             | none   |
| L4 (`orchestration/`) | unchanged                                     | unchanged                                                                                                             | none   |
| **L4 (`api/`)**       | route handlers, JWT verifier, SSE translator  | Contract tests with mocked LLM (`pytest-asyncio`); rejection paths first for JWT verifier (TAP-4 mitigation)          | none   |
| **Architecture**      | `tests/architecture/test_api_layer.py`        | Import-graph assertion: `api/` may not be imported by `components/`, `services/`, `trust/`, `orchestration/`, `meta/` | none   |
| **Frontend**          | components                                    | Vitest + React Testing Library (unit), Playwright (a few smoke E2Es against Vercel preview)                           | n/a    |


**Architecture test addition** (sketch):

```python
# tests/architecture/test_api_layer.py
def test_api_does_not_import_from_meta() -> None:
    forbidden = collect_imports("api/", forbidden_prefixes=["meta", "StructuredReasoning.components", "StructuredReasoning.services"])
    assert forbidden == []

def test_lower_layers_do_not_import_from_api() -> None:
    for layer in ("components", "services", "trust", "orchestration", "meta"):
        offenders = imports_matching(layer, "api")
        assert offenders == [], f"{layer}/ imports from api/: {offenders}"
```

## 10. Risk Register


| ID  | Risk                                                         | Likelihood    | Impact   | Mitigation                                                                           |
| --- | ------------------------------------------------------------ | ------------- | -------- | ------------------------------------------------------------------------------------ |
| R1  | App Runner cold start with min=0 ruins SSE first-token UX    | High if min=0 | High     | min=1 always-on; documented in cost model                                            |
| R2  | NAT Gateway cost pushes monthly above $100 budget            | High          | Med      | Replace with VPC endpoints (ECR, Secrets, Logs) — net saves ~$10/mo                  |
| R3  | `shell` tool reachable through Cognito beta user             | Med           | Critical | v1 hard-codes "tools allowed list" per Cognito group; `shell` only for `admin` group |
| R4  | LangGraph schema drift breaks `AsyncPostgresSaver` migration | Low           | Med      | Pin `langgraph` + `langgraph-checkpoint-postgres` versions; smoke-test in Phase 1    |
| R5  | Amplify Auth bundle size hurts mobile load                   | Med           | Low      | Tree-shake to `aws-amplify/auth`, defer import past first paint                      |
| R6  | WAF managed rules false-positive on Markdown content         | Low           | Med      | Stage in count-mode for 48h before enforce                                           |
| R7  | RDS Single-AZ outage during beta                             | Low           | High     | Acceptable for private beta; switch to Multi-AZ at GA                                |
| R8  | StructuredReasoning module merges late, blocking v1.5        | Med           | Low      | v1.5 panel is feature-flagged off; ships dark and lights up after merge              |


## 11. Open Questions for Future Decision

1. **Custom domain**: do we register one (e.g., `app.example.com` → Vercel, `api.example.com` → CloudFront) before launch, or use `*.vercel.app` + `*.cloudfront.net` for v1? Default: defer to Phase 5.
2. **AWS account boundary**: single `agent-prod` for v1; do we add `agent-dev` (AWS Organizations) at v1.5 or v2? Default: v2.
3. **LangSmith integration**: keep current LangSmith tracing in the FastAPI adapter, or rely on CloudWatch Logs only? Default: keep LangSmith; it's already wired.
4. **Eval-capture exposure in UI**: do beta users see their own eval logs (D2 — JSON export)? Currently v1.5.
5. **Per-project system-prompt override** (D4): nice-to-have; default v2.

## 12. Glossary


| Term             | Meaning here                                                                    |
| ---------------- | ------------------------------------------------------------------------------- |
| **Agent**        | The unchanged Python LangGraph ReAct agent in this repo                         |
| **API adapter**  | New `api/` FastAPI server; thin orchestration adapter, peer to `cli.py`         |
| **BFF**          | Backend-for-Frontend: Next.js Route Handlers proxying to the API adapter        |
| **Run**          | A single `graph.ainvoke` execution on a thread; has UUID `run_id`               |
| **Thread**       | Conversation; equivalent to LangGraph `thread_id`                               |
| **SSE taxonomy** | Named SSE events in §4.1, in 1:1 correspondence with LangGraph `astream_events` |
| **Trust kernel** | `trust/` package; pure types with zero outward dependencies                     |


---

## 13. Evidence Register

Every quantitative claim in this plan is listed below with its source so that Check 8 (Mathematical) is auditable.


| ID         | Fact                                                                     | Source                                                                                                                 | Used by                          | Confidence |
| ---------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ---------- |
| ev_cost_1  | App Runner 1 vCPU / 2 GB, min=1, ~5% utilization ≈ $35–50/mo             | [AWS App Runner pricing](https://aws.amazon.com/apprunner/pricing/) (retrieved 2026-04-21)                             | §6.3 cost model                  | 0.8        |
| ev_cost_2  | RDS `db.t4g.micro`, 20 GB gp3, Single-AZ ≈ $15–18/mo                     | [Amazon RDS pricing](https://aws.amazon.com/rds/pricing/) (retrieved 2026-04-21)                                       | §6.3 cost model                  | 0.85       |
| ev_cost_3  | CloudFront 50 GB egress + 5 M requests ≈ $5–8/mo                         | [CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/) (retrieved 2026-04-21)                                | §6.3 cost model                  | 0.8        |
| ev_cost_4  | AWS WAF 1 WebACL + 3 managed rule groups + 5 M requests ≈ $12–18/mo      | [AWS WAF pricing](https://aws.amazon.com/waf/pricing/) (retrieved 2026-04-21)                                          | §6.3 cost model                  | 0.75       |
| ev_cost_5  | Cognito <50,000 MAUs = free tier ($0)                                    | [Cognito pricing](https://aws.amazon.com/cognito/pricing/) (retrieved 2026-04-21)                                      | §6.3 cost model                  | 0.95       |
| ev_cost_6  | Secrets Manager 3 secrets ≈ $1.20/mo                                     | [Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/) (retrieved 2026-04-21)                      | §6.3 cost model                  | 0.95       |
| ev_cost_7  | ECR <1 GB stored ≈ $0.10/mo                                              | [ECR pricing](https://aws.amazon.com/ecr/pricing/) (retrieved 2026-04-21)                                              | §6.3 cost model                  | 0.95       |
| ev_cost_8  | CloudWatch logs + custom metrics ≈ $2–5/mo                               | [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/) (retrieved 2026-04-21)                                | §6.3 cost model                  | 0.7        |
| ev_cost_9  | NAT Gateway 1 AZ, low traffic ≈ $32/mo (largest single line item)        | [VPC pricing](https://aws.amazon.com/vpc/pricing/) (retrieved 2026-04-21)                                              | §6.3 cost model, R2 mitigation   | 0.9        |
| ev_cost_10 | 3 VPC endpoints (ECR, Secrets, Logs) ≈ $22/mo, net saving ~$10/mo vs NAT | [VPC pricing](https://aws.amazon.com/vpc/pricing/) (retrieved 2026-04-21)                                              | §6.3 footnote recommendation (a) | 0.7        |
| ev_cost_11 | Data transfer misc ≈ $2–4/mo                                             | [AWS data transfer pricing](https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer) (retrieved 2026-04-21)        | §6.3 cost model                  | 0.6        |
| ev_time_1  | Phase 1 (FastAPI adapter) = 1 week                                       | Internal estimate — comparable CLI adapter took <3 days; SSE + JWT + tests double the scope                            | §8 Phase 1                       | 0.65       |
| ev_time_2  | Phase 2 (CDK infra) = 1 week                                             | Internal estimate — 5 stacks, prior CDK experience assumed                                                             | §8 Phase 2                       | 0.6        |
| ev_time_3  | Phase 3 (Next.js scaffold + auth + threads) = 1.5 weeks                  | Internal estimate — scaffolding + Cognito + Drizzle setup; shadcn theming adds 2 days                                  | §8 Phase 3                       | 0.6        |
| ev_time_4  | Phase 4 (Streaming chat) = 1.5 weeks                                     | Internal estimate — SSE client + 6 components; mobile QA adds 2 days                                                   | §8 Phase 4                       | 0.55       |
| ev_time_5  | Phase 5 (Hardening + beta launch) = 0.5 week                             | Internal estimate — WAF tuning + alarms + runbook; contingent on no Sev-2 rework                                       | §8 Phase 5                       | 0.5        |
| ev_arch_1  | `langgraph-checkpoint-postgres` `AsyncPostgresSaver` is GA               | `[langgraph-checkpoint-postgres` PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) (retrieved 2026-04-21) | §5.2, F11                        | 0.9        |


## 14. Hypothesis Register

Each locked decision is recast as a falsifiable hypothesis with explicit confirm/kill thresholds. This restores Phase 2 visibility and makes future spike work auditable.


| ID  | Decision                                            | Hypothesis                                                                                                                               | Confirm if                                                                                                                            | Kill if                                                                                                                                                                        | Status                                                                          |
| --- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| H1  | App Runner for SSE workload                         | App Runner sustains 10 concurrent SSE streams for ≥5 min each at <70% CPU on 1 vCPU / 2 GB                                               | Load test shows p95 CPU <70%, 0 dropped connections at 10 concurrent streams                                                          | CPU exceeds 85% or streams are dropped at 5+ concurrent clients                                                                                                                | Untested                                                                        |
| H2  | SSE through CloudFront + WAF                        | Tokens stream end-to-end with TTFT <200 ms after CloudFront + WAF managed rules                                                          | Local test through CloudFront origin: TTFT <200 ms, no response buffering, idle timeout >120 s                                        | CloudFront buffers responses (>1 s TTFT), or WAF managed rules false-positive on streamed Markdown, or idle timeout severs streams between slow tokens                         | Untested                                                                        |
| H3  | Cognito ID token for API auth                       | ~~FastAPI verifier accepts `token_use === "id"` and validates `aud~~`                                                                    | ~~AWS docs confirm ID tokens are correct for API authorization~~                                                                      | AWS docs state access tokens are required for API authorization; ID token `aud` differs from access token `client_id`                                                          | **Killed** — see §18.1                                                          |
| H4  | Dual-ORM (Drizzle BFF + SQLModel API) on shared RDS | Both ORMs read/write the same schema without migration drift when `drizzle-kit push` is the single migration authority                   | 5 sequential deploy cycles with schema changes produce zero drift between Drizzle migrations and SQLModel model introspection         | `drizzle-kit push` destructively alters a table that SQLModel or LangGraph's checkpointer depends on; or SQLModel auto-generates DDL that conflicts with Drizzle-owned columns | Untested                                                                        |
| H5  | Replace NAT with VPC endpoints                      | 3 VPC endpoints (ECR, Secrets Manager, CloudWatch Logs) save net ~$10/mo vs NAT Gateway                                                  | Cost Explorer shows endpoint charges <$22/mo and NAT charge drops to $0                                                               | Endpoint hourly charges exceed $22/mo at actual traffic, or a service that needs NAT (e.g., LangSmith HTTPS egress) is broken by removing NAT                                  | Partially confirmed (arithmetic checks out; egress path for LangSmith untested) |
| H6  | App Runner request-duration limit                   | App Runner's per-request timeout (default 120 s) accommodates p95 ReAct run duration                                                     | p95 run length measured in local benchmarks is <100 s                                                                                 | p95 run length exceeds 120 s, or App Runner silently terminates SSE connections before run completes                                                                           | Untested                                                                        |
| H7  | Mobile Safari EventSource + Last-Event-ID           | iOS Safari reconnects cleanly with `Last-Event-ID` header after network interruption                                                     | Manual test on iOS Safari 18+: drop Wi-Fi for 5 s, stream resumes from correct `seq`                                                  | Safari drops `Last-Event-ID` on reconnect or silently resets the stream; no chunked-HTTP fallback exists                                                                       | Untested                                                                        |
| H8  | RDS connection budget                               | `db.t4g.micro` (~100 max connections) supports 3 concurrent pools: psycopg async pool (API), Drizzle pool (BFF), AsyncPostgresSaver pool | Sum of pool `max_size` settings ≤80 (leaving headroom); no `too many connections` errors under 10 concurrent users                    | Total pool demand exceeds ~80 at 10 users, or LangGraph checkpointer opens connections outside the managed pool                                                                | Untested                                                                        |
| H9  | LangGraph `astream_events` API version              | Event names in §4.1 SSE taxonomy match the pinned `astream_events` v2 output                                                             | `on_chat_model_stream`, `on_tool_start`, `on_tool_end`, `on_chain_start`, `on_chain_end` names are stable across pinned version range | LangGraph changes event names or payload shapes across minor versions; §4.1 mapping breaks without code changes                                                                | Untested                                                                        |


## 15. Validation Log

The eight self-validation checks required by the Pyramid Principle protocol (`prompts/StructuredReasoning/_pyramid_brain.j2`), applied honestly against this plan. This replaces the former single-sentence "all pass" assertion.


| #   | Check          | Result            | Details                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --- | -------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Completeness   | **Fail**          | The footer claims three Pyramid analyses (compute, transport, UI features) were performed, but none of the three issue trees appear in the document. The analyses are asserted, not shown. §2 is a flat feature list (F1–F12), not a MECE decomposition.                                                                                                                                                                                                                                                  |
| 2   | Non-Overlap    | **Fail**          | F1–F12 in §2 is a 12-row flat list exceeding the protocol's 5-branch-per-level maximum. Several items could be regrouped (e.g., F5/F6/F7 are all observability; F1/F8/F9 are account-scoped). Without an explicit tree structure, overlap cannot be formally tested.                                                                                                                                                                                                                                      |
| 3   | Item Placement | **Partial**       | Individual features (F1–F12) can each be placed in exactly one row, so placement mechanically works. However, without key-argument groupings to place them *into*, the test is incomplete — there is no inductive structure to validate against.                                                                                                                                                                                                                                                          |
| 4   | So What?       | **Fail**          | §1 Governing Thought packs ~10 commitments into one sentence. No so-what chains exist linking evidence (§6.3 costs, §8 time estimates) upward through key arguments to the governing thought. The vertical chain from any evidence item to the apex is implicit, not demonstrated.                                                                                                                                                                                                                        |
| 5   | Vertical Logic | **Partial**       | Sections §3–§7 follow a deductive descent (architecture → API → data → infra → auth). Each section answers questions raised by the previous one. However, the top-level structure is deductive, not inductive — a single challenged premise (e.g., "App Runner can sustain SSE") could collapse the chain. This is Anti-Pattern 5 (Deduction at the Wrong Level).                                                                                                                                         |
| 6   | Remove One     | **Fail**          | The multi-clause governing thought (§1) bundles technology choices so tightly that removing any single clause (e.g., drop "Cognito" or drop "CloudFront + WAF") changes the commitment. The protocol requires that the governing thought survive the loss of any single key argument. Known weakness: §3.2 claims `api/` is "thin" (identical to `cli.py`), but SSE translation, JWT verification, DB sessions, and cancel plumbing accumulate non-trivial logic — a buried conditional (Anti-Pattern 1). |
| 7   | Never One      | **Pass**          | No single-child groupings exist at any level of §2–§12. Every list and table has ≥2 items.                                                                                                                                                                                                                                                                                                                                                                                                                |
| 8   | Mathematical   | **Pass (caveat)** | Cost arithmetic in §6.3 is internally consistent: summing ev_cost_1 through ev_cost_11 yields $104–137/mo, matching the stated total. However, per-row source confidence varies (see §13 Evidence Register), and Vercel hosting cost ($20/seat/mo Pro plan + bandwidth) is absent from the model.                                                                                                                                                                                                         |


**Known weaknesses documented here (not fixable without restructuring §1–§12):**

- The three original Pyramid analyses should be published as appendices to make Check 1 auditable.
- §2 features (F1–F12) should be regrouped into ≤5 inductive dimensions (e.g., Conversational, Observability, Account, Backend Surface) to satisfy Check 2.
- §1 governing thought should be compressed to one sentence with a separate commitments table to satisfy Check 6.
- §3–§7 should be reframed as inductive pillars (Cost, Velocity, Architectural Fit, Risk) to satisfy Check 5.

These are flagged for a future structural revision; the current plan preserves §1–§12 as the v1 commitment record.

## 16. Cross-Branch Interactions

Silent interactions between plan branches that the MECE decomposition (§3–§7) does not surface. Per the protocol (Anti-Pattern 3), these must be explicitly documented to prevent silo-based reasoning.


| Interacting branches                                                                  | Interaction                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Mitigation owner                                                                             | Tracked in           |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------- |
| EdgeStack (§6.1) ↔ SSE transport (§4.1)                                               | CloudFront default origin-response timeout (~30 s) and idle-timeout behavior can sever SSE streams between slow tokens. `X-Accel-Buffering: no` is set in the BFF (§8 Phase 4) but CloudFront's own buffering behavior is independent of this header. WAF managed rules may also false-positive on streamed Markdown content.                                                                                                                               | Phase 2 owner (CDK) + Phase 4 owner (SSE client)                                             | H2 in §14, R6 in §10 |
| AppStack (§6.1) ↔ `/chat/stream` (§4)                                                 | App Runner enforces a per-request duration limit (default 120 s). Multi-tool ReAct runs with slow external tool calls (e.g., web search, large file reads) may exceed this. The SSE stream would be terminated server-side with no client-side indication of cause.                                                                                                                                                                                         | Phase 1 owner (FastAPI adapter)                                                              | H6 in §14            |
| DataStack (§6.1) ↔ Frontend BFF + API + LangGraph checkpointer                        | Three concurrent connection pools target the same RDS `db.t4g.micro` (~100 max connections): `psycopg_pool.AsyncConnectionPool` (API), Drizzle/`node-postgres` pool (BFF Route Handlers), and `AsyncPostgresSaver`'s internal pool. Without explicit pool-size budgeting, concurrent SSE streams could exhaust the connection cap.                                                                                                                          | Phase 1 owner (pool config) + Phase 3 owner (Drizzle pool)                                   | H8 in §14            |
| Frontend `lib/db/` (Drizzle) ↔ API `models/` (SQLModel) ↔ LangGraph checkpoint tables | Two ORMs target the same RDS instance. `drizzle-kit push` is the stated migration authority (§5.3), but it performs destructive sync — it will attempt to modify or drop tables it does not recognize, including LangGraph's checkpointer-owned tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`). SQLModel introspection adds a third schema view that may drift from Drizzle's.                                                             | Phase 1 owner (checkpoint schema isolation) + Phase 3 owner (Drizzle config: `tablesFilter`) | H4 in §14            |
| NAT-vs-VPC-endpoints recommendation ↔ §6.1 stack design ↔ §6.3 cost table             | The §6.3 footnote recommends option (a) — VPC endpoints — but §6.1 `NetworkStack` still describes NAT. If option (a) is adopted, `NetworkStack` must drop NAT and add 3 interface endpoints, and the cost table total should read $80–95/mo, not $104–137/mo. Additionally, removing NAT blocks any HTTPS egress from private subnets (e.g., LangSmith tracing, OpenAI API calls) unless those endpoints are added or the service moves to a public subnet. | Phase 2 owner (CDK)                                                                          | H5 in §14, R2 in §10 |


## 17. Alternatives Considered

Each locked decision below was evaluated against the same four dimensions. The chosen option is marked with **[selected]**. This section converts "decisions locked" (§0) into "decisions justified."

### 17.1 Compute platform


| Option                    | Cost (10 users, us-east-1)    | Velocity (time to first deploy)        | Architectural fit                                                                                                           | Risk                                                                                                                | Verdict                                                       |
| ------------------------- | ----------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **App Runner [selected]** | $35–50/mo (min=1)             | ~2 days (ECR push → auto-deploy)       | Good — managed service, no cluster config; SSE needs validation (H1, H6)                                                    | Cold start mitigated by min=1; request-timeout limit is a risk                                                      | Best balance of simplicity and cost for private beta          |
| ECS Fargate               | $40–70/mo (0.25 vCPU task)    | ~4 days (task def + ALB + service)     | Good — more control over networking, health checks, timeout                                                                 | Over-provisioning risk; ALB adds $16/mo                                                                             | Rejected: higher cost and operational surface for beta scale  |
| Lambda + RDS Proxy        | $5–15/mo (pay per invocation) | ~3 days (API Gateway + Lambda + layer) | Poor — SSE is not natively supported; response streaming requires Lambda Web Adapter or Function URLs with chunked encoding | Cold start on every request (no min=1 equivalent without Provisioned Concurrency at ~$30/mo); RDS Proxy adds $15/mo | Rejected: SSE incompatibility is a blocker                    |
| Lightsail container       | $7–10/mo (micro)              | ~1 day                                 | Moderate — simple but no auto-scaling, limited observability                                                                | No VPC connector to private subnets; RDS would need public endpoint or VPC peering                                  | Rejected: security model incompatible with private-subnet RDS |


### 17.2 Transport protocol


| Option                                | Complexity (FE + BE)                                            | Reconnect / resume                              | Proxy-friendliness (CloudFront, WAF)                                                      | Browser support                                     | Verdict                                                                                         |
| ------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **SSE [selected]**                    | Low — native `EventSource` + `text/event-stream`                | Built-in `Last-Event-ID`                        | Good — standard HTTP; needs buffering disabled                                            | Universal (all modern browsers)                     | Best simplicity-to-capability ratio; validate H2, H7                                            |
| WebSockets                            | Medium — requires `ws://` upgrade, ping/pong, reconnect library | Manual — must implement resume-from-seq         | Poor — CloudFront supports WS but WAF cannot inspect WS frames; ALB or API Gateway needed | Universal                                           | Rejected: WAF bypass is a security regression; operational complexity disproportionate for beta |
| Chunked HTTP (fetch + ReadableStream) | Medium — custom client parser, no `Last-Event-ID` equivalent    | Manual — must implement retry + offset tracking | Good — standard HTTP                                                                      | Good (no IE11; Safari fetch streaming since iOS 15) | Rejected: reimplements SSE without the standard; viable as fallback for H7 if Safari SSE fails  |


### 17.3 Auth provider


| Option                 | Cost (≤50 users)     | AWS integration                                              | Velocity (time to wire) | Lock-in risk                                                                                      | Verdict                                                                                              |
| ---------------------- | -------------------- | ------------------------------------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Cognito [selected]** | $0 (free tier)       | Native — IAM roles, App Runner JWT verification, Amplify SDK | ~2 days                 | Medium — Cognito-specific token claims; migration to another IdP requires rewriting `api/deps.py` | Best cost and AWS integration for beta; accept lock-in for v1                                        |
| Auth0                  | $0 (free ≤7.5K MAUs) | External — requires JWKS fetch + custom claims mapping       | ~1.5 days               | Low — standard OIDC; easy migration                                                               | Rejected: no cost advantage, adds external dependency; revisit if Cognito limits bite in v1.5        |
| Clerk                  | $0 (free ≤10K MAUs)  | External — REST API for user management; no native IAM       | ~1 day (excellent DX)   | Low — standard OIDC                                                                               | Rejected: no IAM integration; better DX does not outweigh operational simplicity of Cognito for beta |
| WorkOS                 | $0 (free ≤1M MAUs)   | External — SAML/SSO focused                                  | ~2 days                 | Low — enterprise SSO focus                                                                        | Rejected: enterprise-SSO features are over-specified for a beta with ≤10 users                       |


### 17.4 DB access pattern


| Option                                    | Schema consistency                       | Complexity                                                   | Performance                                                          | Deployment coupling                                                    | Verdict                                                                                                                                |
| ----------------------------------------- | ---------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Drizzle BFF + SQLModel API [selected]** | Risk of drift between two ORMs (§16, H4) | High — two schema definitions to maintain                    | Good — each tier uses idiomatic ORM                                  | Low — BFF and API deploy independently                                 | Selected with caveat: must configure `drizzle-kit` `tablesFilter` to exclude LangGraph checkpoint tables; validate H4 in Phase 1 spike |
| FastAPI-only (no BFF DB access)           | Single ORM (SQLModel)                    | Low — BFF passes all DB calls through to FastAPI             | Moderate — BFF → API round-trip adds ~5–15 ms per thread list/create | High — BFF depends on API availability for thread CRUD                 | Rejected for v1: thread CRUD latency from Vercel → CloudFront → App Runner → RDS is unnecessary; revisit if H4 is killed               |
| Drizzle-only via FastAPI HTTP             | Single ORM (Drizzle, TS)                 | Medium — requires TS-based API or API wrapping Drizzle calls | Good — single schema source of truth                                 | Medium — FastAPI would need to be rewritten in TS or call a TS sidecar | Rejected: Python agent and FastAPI are existing choices; rewriting in TS is out of scope                                               |


### 17.5 Frontend hosting


| Option                          | Cost                                               | DX (preview deploys, CI)                               | AWS integration                                    | CDN / edge                          | Verdict                                                                                                                                 |
| ------------------------------- | -------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Vercel [selected]**           | $20/seat/mo Pro (not included in §6.3 — see §18.2) | Excellent — Git push → preview URL; built-in analytics | External — no AWS credentials in Vercel env (§6.2) | Global edge, automatic ISR          | Best DX for rapid frontend iteration; cost is acceptable for ≤3 seats                                                                   |
| CloudFront + S3 (static export) | $5–8/mo (included in existing CF budget)           | Poor — manual CI/CD pipeline; no SSR                   | Native — same AWS account                          | Global edge via existing CloudFront | Rejected: Next.js App Router with RSC requires SSR; static export loses server components                                               |
| AWS Amplify Hosting             | $0–5/mo (build minutes)                            | Good — Git push → preview; supports Next.js SSR        | Native — IAM, Cognito integration                  | CloudFront-backed                   | Rejected: Amplify SSR support for Next.js 15 App Router is lagging; build config is brittle for monorepo; revisit when Amplify improves |


## 18. Errata and Confidence Recomputation

### 18.1 Erratum: Cognito token type (supersedes §7 "Token verification")

**Current text in §7** (incorrect):

> *"FastAPI verifies JWT signature against Cognito JWKs (cached 24h), checks `iss`, `aud`, `exp`, and `token_use === "id"`."*

**Correction** per [AWS Cognito access-token documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html) (verified 2026-04-21):

1. **Use access tokens** (`token_use === "access"`) for API authorization — not ID tokens.
2. Access tokens carry `**client_id`**, not `aud`. The verifier must check `client_id === <app_client_id>` (not `aud`).
3. Access tokens carry `**cognito:groups**` (e.g., `["beta", "admin"]`), which the §7 v1 authorization gate (`api/routes/chat.py`) needs for the per-group tool allowlist.
4. Access tokens carry `**scope**` (e.g., `"openid profile email"`), enabling future fine-grained authorization in v1.5.
5. **ID tokens** are for client-side identity (rendering email, display name in the UI) and must **never** be sent as a bearer token to the API.

**Impact on `api/deps.py` (Phase 1):**

```python
# Corrected verification logic (sketch)
if claims["token_use"] != "access":
    raise HTTPException(status_code=401, detail="Expected access token")
if claims["client_id"] != settings.cognito_app_client_id:
    raise HTTPException(status_code=401, detail="Invalid client_id")
user_id = claims["sub"]          # cognito:sub → user_id
groups = claims.get("cognito:groups", [])
```

No architectural impact. The erratum affects only the JWT-verification dependency (`api/deps.py`) and the corresponding test (`tests/api/test_jwt_verification.py`).

### 18.2 Confidence recomputation

The protocol computes plan-level confidence as:

```
confidence = min(avg_argument_confidence, completeness_penalty, structural_penalty)
```

**Completeness penalty:**

- Three untested high-impact hypotheses (H1 App Runner SSE, H2 CloudFront SSE, H6 request timeout) → −0.10 each = −0.30.
- One killed hypothesis (H3 Cognito token type) requiring Phase 1 fix → −0.05 (fix is straightforward, low residual risk).
- Effective completeness score: 1.0 − 0.30 − 0.05 = **0.65**.

**Structural penalty:**

- Three failed validation checks in §15 (Completeness, Non-Overlap, So What?) → −0.15.
- One additional fail (Remove One) does not stack further per protocol.
- Effective structural score: 1.0 − 0.15 = **0.85**.

**Average argument confidence:**

- Cost evidence (ev_cost_*): avg ~0.80.
- Timeline evidence (ev_time_*): avg ~0.58.
- Architecture evidence (ev_arch_1): 0.90.
- Weighted average (cost and timeline dominate): **~0.70**.

**Plan-level confidence: `min(0.70, 0.65, 0.85)` = 0.65.**

This is lower than the original 0.82 but honest. The confidence is expected to rise to ~0.75 once Phase 1 spike work resolves H1, H2, and H6 (the three untested high-impact hypotheses), and to ~0.82 once the validation-log failures are addressed by restructuring §1–§2 (deferred to a future plan revision).

**Vercel cost omission:** §6.3 cost model does not include Vercel Pro ($20/seat/mo). At 2 seats, this adds $40/mo, bringing the all-in total to **$120–135/mo** (with VPC endpoints) or **$144–177/mo** (with NAT). This should be added to §6.3 in a future revision.

---

*This plan was produced via three Pyramid Principle analyses (compute, transport, UI features) per `prompts/StructuredReasoning/_pyramid_brain.j2`. Validation log in §15, gap analysis in §14 hypothesis register and §16 cross-branch interactions, errata in §18.*