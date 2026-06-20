---
type: runbook
title: 'Recipe 3 — Containerize Backend + Frontend'
description: 'Build production Docker images for the combined backend and Next.js frontend.'
tags: [recipe, gcp]
---

# Recipe 3 — Containerize Backend + Frontend

**Goal:** Create production Docker images for the combined Python backend and the Next.js frontend, suitable for deployment on Cloud Run (Recipes 4 & 5). After this recipe, we have shipping crates ready to push to the Artifact Registry shelf from Recipe 1.

**Status:** Complete | 16 tests passing | No cloud cost (local images only)

---

## Before We Start: A Story

Recipe 0 taught the code how to speak GCP. Recipe 1 built the workshop: unlocked doors (APIs), an image shelf (Artifact Registry), a robot badge (runtime SA), and locked envelopes (Secret Manager). Recipe 2 added the workbench (Cloud SQL) and the filing cabinet (two GCS buckets).

But Cloud Run does not run Python source code — it runs **containers**. We have adapters and infrastructure, but nothing to ship. The workshop has a workbench and filing cabinet, but no crate to carry the app to the loading dock.

Recipe 1's Artifact Registry is the **shelf** waiting for images. Recipe 3 builds those images locally. Recipe 4 pushes them to the shelf and starts the service.

Think about what happens when a user sends a message:

1. **The frontend** (Next.js on port 3000) handles sign-in and renders the chat UI. It forwards authenticated requests to the backend via `MIDDLEWARE_URL`.
2. **The backend** (combined FastAPI on port 8080) verifies the JWT, loads AgentFacts from GCS, streams the agent response over SSE, writes checkpoints to Cloud SQL, and appends trust traces to GCS.
3. **Cloud Run** pulls a container image, starts the process, probes `/healthz`, and routes traffic. It never sees your repo — only the image you built.

This recipe builds the shipping crates: two multi-stage Dockerfiles and a combined production entry point that packages everything the backend needs into one image.

```mermaid
flowchart LR
    subgraph build [Recipe 3 Local Build]
        AppProd["middleware/app_prod.py<br/>combined FastAPI"]
        DFB["Dockerfile.backend<br/>Python 3.11 multi-stage"]
        DFF["Dockerfile.frontend<br/>Node 20 standalone"]
    end

    subgraph registry [Recipe 1 Shelf]
        AR["Artifact Registry<br/>agent-backend"]
    end

    subgraph deploy [Recipe 4 Future]
        BackendCR["Cloud Run Backend<br/>port 8080"]
        FrontendCR["Cloud Run Frontend<br/>port 3000"]
    end

    AppProd --> DFB
    DFB -->|"docker build/push"| AR
    DFF -->|"docker build/push"| AR
    AR -.->|"Recipe 4 deploy"| BackendCR
    AR -.->|"Recipe 4 deploy"| FrontendCR
    FrontendCR -->|"MIDDLEWARE_URL + SSE"| BackendCR
```

---

## Prerequisites

- Recipe 2 complete (Cloud SQL + GCS buckets provisioned; `DATABASE_URL` secret updated).
- Docker installed locally.
- `pyproject.toml` already has the `[gcp]` optional extra (Recipe 0).
- Recipe 1 Artifact Registry repository exists (images will be pushed there in Recipe 4).

---

## The Four Containerization Lessons

---

### Lesson 1 — The Shipping Crate Problem

**`Dockerfile.backend` and `frontend/Dockerfile.frontend`**

> "Cloud Run can't `pip install` my repo. What does it actually run?"

Cloud Run runs a container image — a frozen filesystem snapshot with your code, dependencies, and a startup command. It does not clone your git repo, run `pip install`, or execute `pnpm build` at deploy time. Everything must be baked into the image before push.

We build two images:

| Image | Dockerfile | Base | Port | Startup |
|-------|-----------|------|------|---------|
| Backend | `Dockerfile.backend` | Python 3.11-slim | 8080 | `uvicorn ... --factory` |
| Frontend | `frontend/Dockerfile.frontend` | Node 20-alpine | 3000 | `node server.js` |

Both images will be pushed to the Artifact Registry repository created in Recipe 1 (`agent-backend`). Recipe 4 wires the image URLs into Cloud Run services.

Key decisions:

- **Port 8080 for backend** — Cloud Run's default HTTP port. The platform injects `PORT` but we set it explicitly for clarity.
- **Port 3000 for frontend** — Next.js standalone server default. Cloud Run maps external HTTPS to this port.
- **Separate images** — backend and frontend deploy as independent Cloud Run services (Recipes 4 & 5). They scale, restart, and roll back independently.
- **No secrets in images** — API keys, database URLs, and WorkOS credentials are injected at runtime via Secret Manager (Recipe 4). The image contains code and dependencies only.

> **Why not one image for everything?** Python and Node have different base images, dependency managers, and runtime sizes. Combining them would produce a bloated image (~800MB+) with two process managers. Separate images keep each crate lean and deployable on its own schedule.

**Checkpoint question:** What does Cloud Run receive when you deploy — source code or a container image?

*Answer: A container image. Cloud Run pulls the image from Artifact Registry, starts the `CMD` process, and probes `/healthz`. It never accesses your git repo or runs build tools.*

---

### Lesson 2 — The Two-Ring Problem

**`middleware/app_prod.py` — Tier A Option A**

> "Locally I run middleware and agent separately. Why one combined app in production?"

During local development, you may run the middleware BFF and the agent runtime as separate processes — different ports, different reload cycles, easy debugging. In production at Tier A, we combine them into a single FastAPI application served by one uvicorn process.

This is **Tier A Option A** (documented in [`docs/plans/gcp_deployment_recipes.plan.md`](../../plans/gcp_deployment_recipes.plan.md)): one Cloud Run service hosts both the auth/ACL middleware surface and the agent SSE runtime.

```python
# middleware/app_prod.py — uvicorn factory target
# uvicorn middleware.app_prod:build_combined_app --factory --port 8080
```

What `build_combined_app()` composes:

1. **`middleware/server.py`** — WorkOS JWT auth + tool ACL routes, mounted at `/middleware/*`.
2. **`/run/stream`** — SSE streaming endpoint that the frontend BFF calls. Requires a Bearer token; returns 401 without one.
3. **`/healthz`** — pre-auth liveness probe. Cloud Run checks this before routing traffic.
4. **`lifespan` hook** — opens the `PostgresCheckpointer` (Recipe 0 adapter) before graph compilation, so Cloud SQL is ready on first request.
5. **`GcsTraceSink` + `AgentFactsGcsRegistry`** — wires Recipe 0 adapters to the GCS buckets from Recipe 2.

Env wiring (all injected at Cloud Run runtime, never baked into the image):

| Variable | Source (Recipe 4) | Purpose |
|----------|-------------------|---------|
| `GCP_EXECUTION_ENV=cloudrun` | Env var | Triggers GCP adapter wiring |
| `DATABASE_URL` | Secret Manager | Postgres checkpointer (Recipe 2) |
| `GCS_FACTS_BUCKET` | Env var | AgentFacts registry (Recipe 2) |
| `GCS_TRACES_BUCKET` | Env var | Trust trace sink (Recipe 2) |
| `WORKOS_*`, `MEM0_*`, `LANGFUSE_*`, `OPENAI_API_KEY` | Secret Manager | Auth, memory, observability, LLM |

Key decisions:

- **Single process** — one uvicorn worker handles auth, ACL, and SSE. Simpler ops at Tier A; fewer Cloud Run services to manage and pay for.
- **Factory pattern** — `build_combined_app()` is called by uvicorn with `--factory`, so the app is constructed fresh on each worker start (including lifespan hooks).
- **Pre-auth `/healthz`** — Cloud Run probes before JWT validation. If healthz required auth, every probe would fail with 401 and the service would never become ready.

> **Tier B future:** When traffic grows or teams need independent deploy cycles, Option B splits the BFF and backend into separate Cloud Run services with separate Dockerfiles. See [`docs/recipes/gcp/TIER_B_FUTURE.md`](TIER_B_FUTURE.md) for the decoupled topology and B1–B5 upgrade path.

**Checkpoint question:** Why does `/healthz` not require a Bearer token?

*Answer: Cloud Run's liveness and readiness probes call `/healthz` before any user traffic arrives. Requiring auth would cause every probe to return 401, and Cloud Run would mark the service unhealthy and stop routing traffic.*

---

### Lesson 3 — The Layer Cake Problem

**Multi-stage Dockerfiles, `next.config.ts`, and `.dockerignore`**

> "Why three Docker stages instead of one big `COPY . .`?"

A single-stage Dockerfile that copies everything and installs dependencies on every code change is slow. Multi-stage builds cache the expensive layers separately from the application code.

**Backend (`Dockerfile.backend`) — two stages:**

```dockerfile
# Stage 1 (deps): python:3.11-slim + [gcp] extra + uvicorn[standard]
FROM python:3.11-slim AS deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[gcp]" uvicorn[standard] python-multipart

# Stage 2 (runtime): slim image, copies site-packages, app code
FROM python:3.11-slim AS runtime
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
RUN pip install --no-cache-dir --no-deps -e .
```

- **Stage 1 (`deps`)** installs Python packages. This layer is cached until `pyproject.toml` changes.
- **Stage 2 (`runtime`)** copies installed packages and application code. Code changes rebuild only this stage.
- **`libpq5`** in runtime — PostgreSQL client library required by `psycopg` for the Cloud SQL checkpointer.
- **`[gcp]` extra** — pulls in `google-cloud-storage`, `google-cloud-pubsub`, and other GCP SDK dependencies from Recipe 0.

**Frontend (`frontend/Dockerfile.frontend`) — three stages:**

```dockerfile
# Stage 1 (deps): pnpm install --frozen-lockfile
# Stage 2 (builder): pnpm build → produces .next/standalone
# Stage 3 (runner): node server.js on port 3000
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
CMD ["node", "server.js"]
```

- **Stage 1 (`deps`)** installs Node modules. Cached until `pnpm-lock.yaml` changes.
- **Stage 2 (`builder`)** runs `pnpm build`. Cached until source changes.
- **Stage 3 (`runner`)** copies only the standalone output — a minimal `server.js` plus traced dependencies. No source maps, no dev dependencies, no TypeScript compiler.

The standalone output requires one config change in `frontend/next.config.ts`:

```typescript
const config: NextConfig = {
  output: "standalone",  // ← produces self-contained server.js + minimal node_modules
  reactStrictMode: true,
  ...
};
```

Without `output: "standalone"`, `pnpm build` produces a `.next/` directory that requires the full `node_modules/` tree at runtime — roughly 500MB instead of ~150MB.

**`.dockerignore` files** keep the build context lean:

Root `.dockerignore` (backend context):
- Excludes `node_modules/`, `frontend/.next/`, `tests/`, `docs/`, `.git`, `infra/`

`frontend/.dockerignore` (frontend context):
- Excludes `node_modules`, `.next`, `e2e`, `test-results`, `.env*`

Key decisions:

- **Separate build contexts** — backend builds from repo root (needs `middleware/`, `agent_ui_adapter/`, `services/`). Frontend builds from `frontend/` (needs only Next.js app files).
- **Non-root frontend user** — the runner stage creates `nextjs:nodejs` (1001:1001) and runs `server.js` as that user. Defense in depth if the container is compromised.
- **No `.env` in context** — both `.dockerignore` files exclude `.env*`. Secrets arrive via Cloud Run env/Secret Manager at runtime (FE-AP-18).

**Checkpoint question:** Why does the frontend Dockerfile have three stages but the backend has only two?

*Answer: Next.js requires a compile step (`pnpm build`) that produces static assets and a standalone server bundle. Python does not have an equivalent compile step — `pip install` is the only dependency layer, so two stages (deps + runtime) suffice.*

---

### Lesson 4 — The Probe and Stream Problem

**`/healthz`, keep-alive timeout, HEALTHCHECK, and runtime secrets**

> "Cloud Run kills idle connections and probes `/healthz` before auth. How do we survive?"

Cloud Run has two behaviors that break naive container setups:

1. **Health probes.** Before routing traffic, Cloud Run sends HTTP requests to your liveness/readiness endpoint. If it gets non-200 responses, the revision is marked unhealthy.
2. **Idle connection timeout.** Cloud Run closes idle HTTP connections after 600 seconds by default. SSE streams can last longer than that — the connection must stay alive.

Our defenses:

**Pre-auth `/healthz`:**

```python
@app.get("/healthz")
async def healthz():
    """Cloud Run liveness/readiness probe — pre-auth."""
    return {
        "status": "ok",
        "profile": adapters.profile,
        "runtime": "langgraph",
        "mode": "combined",
    }
```

**SSE-safe keep-alive in the backend CMD:**

```dockerfile
CMD ["uvicorn", "middleware.app_prod:build_combined_app", "--factory",
     "--host", "0.0.0.0", "--port", "8080", "--timeout-keep-alive", "620"]
```

The `--timeout-keep-alive 620` exceeds Cloud Run's 600s default idle timeout. Without this, uvicorn would close the SSE socket at 600s while the agent is still streaming, and the user would see a dropped connection mid-response. Recipe 4 also sets Cloud Run `timeout = "3600s"` on the service itself.

**HEALTHCHECK in both Dockerfiles:**

```dockerfile
# Backend
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Frontend
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1
```

Docker's built-in HEALTHCHECK runs locally during `docker run`, giving you early warning if the container fails to start. Cloud Run uses its own probe configuration (Recipe 4), but the Dockerfile HEALTHCHECK helps during local smoke tests.

**No secrets baked into images:**

- Backend Dockerfile sets only non-secret env defaults: `GCP_EXECUTION_ENV=cloudrun`, `AGENT_OFFLOAD_DIR=/tmp/agent_offload`.
- Frontend Dockerfile sets only `NODE_ENV=production`, `PORT=3000`, `HOSTNAME=0.0.0.0`.
- All credentials (`DATABASE_URL`, API keys, WorkOS secrets) are injected at Cloud Run deploy time via Secret Manager (Recipe 4).

Key decisions:

- **401 on missing Bearer for `/run/stream`** — tested in `tests/middleware/test_app_prod.py`. Unauthenticated streaming requests are rejected before any graph work begins.
- **Frontend has no secrets** — only `MIDDLEWARE_URL` and `NEXT_PUBLIC_*` vars at runtime. The frontend never holds API keys or database credentials (FE-AP-18).
- **CORS defaults to `*`** — acceptable for Tier A dev. Tighten `CORS_ORIGINS` to your production domain before going live.

**Checkpoint question:** Why is `--timeout-keep-alive` set to 620 instead of 600?

*Answer: Cloud Run's default idle connection timeout is 600 seconds. Setting uvicorn's keep-alive to 620 ensures the server-side socket stays open slightly longer than Cloud Run's cutoff, preventing premature SSE disconnects during long agent responses.*

---

## Agent Steps

These steps build the shipping crates. The implementation already exists in this repo; this section documents what was created and how to verify it.

### 3.1 — Create `middleware/app_prod.py` (combined production entry)

The production entry point composes:

- **middleware/server.py** — WorkOS JWT auth + tool ACL routes (`/middleware/*`)
- **agent_ui_adapter** — LangGraph runtime + SSE streaming (`/run/stream`)
- **Healthcheck** — pre-auth `/healthz` for Cloud Run probes

```python
# Key export
build_combined_app()  # uvicorn --factory target
```

Env wiring:

- `GCP_EXECUTION_ENV=cloudrun` → GCS sinks, Postgres checkpointer
- `GCS_FACTS_BUCKET` / `GCS_TRACES_BUCKET` — required (from Recipe 2 outputs)
- `DATABASE_URL` — injected via Secret Manager on Cloud Run (Recipe 2 secret)
- All WorkOS/Mem0/Langfuse keys via Secret Manager

### 3.2 — Create `Dockerfile.backend`

Multi-stage build at repo root:

```dockerfile
# Stage 1 (deps): python:3.11-slim + [gcp] extra + uvicorn[standard]
# Stage 2 (runtime): slim image, copies site-packages, app code
# CMD: uvicorn middleware.app_prod:build_combined_app --factory --port 8080
```

Key design choices:

- **Port 8080** — Cloud Run default
- **`--timeout-keep-alive 620`** — exceeds Cloud Run's 600s default timeout to avoid premature socket close during SSE streams
- **HEALTHCHECK** — `curl -f http://localhost:8080/healthz`
- **Non-root** — runs as default user (Cloud Run handles isolation)
- **libpq5** — runtime PostgreSQL client library for psycopg

### 3.3 — Create `frontend/Dockerfile.frontend`

Multi-stage Node 20 build from `frontend/` context:

```dockerfile
# Stage 1 (deps): pnpm install --frozen-lockfile
# Stage 2 (builder): pnpm build (produces .next/standalone)
# Stage 3 (runner): node server.js on port 3000
```

Key design choices:

- **`output: "standalone"`** in `next.config.ts` — produces a self-contained `server.js` + minimal `node_modules`
- **Non-root user** (nextjs:nodejs 1001:1001)
- **No secrets on frontend** — only public env vars (`MIDDLEWARE_URL`, `NEXT_PUBLIC_*`)

### 3.4 — Update `frontend/next.config.ts`

```typescript
const config: NextConfig = {
  output: "standalone",  // ← Added for Docker + Cloud Run
  reactStrictMode: true,
  ...
};
```

### 3.5 — Add `.dockerignore` files

**Root `.dockerignore`** (for backend):

- `node_modules/`, `frontend/.next/`, `tests/`, `docs/`, `.git`

**`frontend/.dockerignore`** (for frontend):

- `node_modules`, `.next`, `e2e`, `test-results`, `.env*`

---

## Human Review Gate

Before proceeding to Recipe 4, the operator verifies:

- [ ] **No secrets in Dockerfiles** — no `COPY .env`, no hardcoded API keys. Grep both Dockerfiles for `sk_`, `pk_`, `password`, and `.env`.
- [ ] **Image sizes reasonable** — backend ~400MB, frontend ~150MB. Run `docker images agent-backend:dev agent-frontend:dev` after building.
- [ ] **CORS review** — `CORS_ORIGINS` defaults to `*` in `app_prod.py`. Tighten to your production domain before going live.
- [ ] **Frontend has no secrets** — only `MIDDLEWARE_URL` and `NEXT_PUBLIC_*` at runtime. No API keys, no database URLs, no WorkOS secrets in the frontend image or env.
- [ ] **Tests pass** — `pytest tests/middleware/test_app_prod.py -q` reports 16 passed.

---

## Local Smoke Test

### Backend

```bash
# Build
docker build -f Dockerfile.backend -t agent-backend:dev .

# Run (requires env vars — will fail healthz without full env, but tests compilation)
docker run --rm -p 8080:8080 \
  -e GCP_EXECUTION_ENV=cloudrun \
  -e GCS_FACTS_BUCKET=test-facts \
  -e GCS_TRACES_BUCKET=test-traces \
  -e AGENT_FACTS_SECRET=dev-secret \
  -e DATABASE_URL=postgresql://test:test@host.docker.internal/test \
  -e WORKOS_CLIENT_ID=client_test \
  -e WORKOS_API_KEY=sk_test \
  -e MEM0_API_KEY=mem0_test \
  -e LANGFUSE_PUBLIC_KEY=pk_test \
  -e LANGFUSE_SECRET_KEY=sk_test \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  agent-backend:dev

# Verify (in another terminal)
curl -s http://localhost:8080/healthz | jq .
# Expected: {"status":"ok","profile":"v3","runtime":"langgraph","mode":"combined"}
```

### Frontend

```bash
# Build (from frontend/ directory context)
docker build -f Dockerfile.frontend -t agent-frontend:dev ./frontend

# Run
docker run --rm -p 3000:3000 \
  -e MIDDLEWARE_URL=http://host.docker.internal:8080 \
  agent-frontend:dev

# Verify
curl -s http://localhost:3000 | head -20
```

---

## For a General Audience

If adapting for a different Next.js + LangGraph stack:

1. Replace `middleware.app_prod:build_combined_app` with your own FastAPI factory.
2. Replace `[gcp]` extra with your cloud provider's SDK dependencies.
3. Keep `output: "standalone"` in `next.config.ts` for any Docker deployment.
4. Adjust `HEALTHCHECK` path to match your liveness endpoint.
5. Set `--timeout-keep-alive` above your platform's idle connection timeout if you use SSE streaming.

The reusable pattern is: combined production entry first, multi-stage Dockerfiles second, standalone Next.js output third, pre-auth health probe last.

---

## Verify

```bash
# Unit tests (no Docker required)
pytest tests/middleware/test_app_prod.py -q

# Docker build succeeds (no runtime needed)
docker build -f Dockerfile.backend -t agent-backend:test .
docker build -f Dockerfile.frontend -t agent-frontend:test ./frontend
docker build -f Dockerfile.backend -t agent-backend:test . --target deps
docker build -f Dockerfile.frontend -t agent-frontend:test ./frontend --target deps
```

---

## Rollback

Remove files and revert config:

```bash
rm Dockerfile.backend frontend/Dockerfile.frontend middleware/app_prod.py
git checkout frontend/next.config.ts .dockerignore
```

---

## Cost Note

No cost impact — this recipe creates local Docker images only. Cloud costs begin at Recipe 4 (Cloud Run deploy). Artifact Registry storage (Recipe 1) is ~$0.10/GB/mo and begins when images are pushed in Recipe 4.

---

## Files Created/Modified

| File | Action |
|------|--------|
| `middleware/app_prod.py` | Created — production combined backend factory |
| `Dockerfile.backend` | Created — multi-stage Python 3.11 image |
| `frontend/Dockerfile.frontend` | Created — multi-stage Node 20 image |
| `frontend/next.config.ts` | Modified — added `output: "standalone"` |
| `.dockerignore` | Modified — expanded exclusions for backend context |
| `frontend/.dockerignore` | Created — frontend build context exclusions |
| `tests/middleware/test_app_prod.py` | Created — 16 tests covering Docker assets + app factory |
