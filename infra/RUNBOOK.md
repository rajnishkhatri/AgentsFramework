# Operations Runbook — V3-Dev-Tier

> **Sprint**: 4 §S4.3.1
>
> **Audience**: Operators and on-call engineers managing the agent platform.
>
> **Architecture source of truth**: [docs/Architectures/FRONTEND_ARCHITECTURE.md](../docs/Architectures/FRONTEND_ARCHITECTURE.md)
>
> **Composition root invariant**: Every substrate swap below is a composition-root-only change [F3]. No `ports/`, `wire/`, `translators/`, or `transport/` files change during any upgrade.

---

## Table of Contents

- [1. Normal Operations](#1-normal-operations)
- [2. Stage A — Current (Free/Dev Tier)](#2-stage-a--current-freedev-tier)
- [3. Stage A → B Upgrades](#3-stage-a--b-upgrades)
- [4. Stage B → C Upgrades](#4-stage-b--c-upgrades)
- [5. Stage C → D (V2-Frontier Graduation)](#5-stage-c--d-v2-frontier-graduation)
- [6. Incident Response Playbooks](#6-incident-response-playbooks)
- [7. Secret Rotation](#7-secret-rotation)

---

## 1. Normal Operations

### 1.1 Health Checks

| Component | Health Endpoint | Expected |
|-----------|----------------|----------|
| Cloud Run middleware | `GET /healthz` | `200 OK` |
| Cloudflare Pages | `GET /` | `200 OK` with CSP headers |
| Neon Postgres | `SELECT 1` via `DATABASE_URL` | Returns `1` |
| WorkOS auth | Sign-in flow completes | Session cookie set |

```bash
# Middleware health
curl -s -o /dev/null -w "%{http_code}" "$(tofu -chdir=infra/dev-tier output -raw middleware_url)/healthz"

# Neon connectivity (requires gcloud + neon creds)
gcloud secrets versions access latest --secret=neon-database-url | \
  xargs -I{} psql "{}" -c "SELECT 1;"
```

### 1.2 Deploying a New Middleware Version

```bash
# 1. Build and push the image
docker build -t us-docker.pkg.dev/$PROJECT/agent-repo/middleware:$TAG .
docker push us-docker.pkg.dev/$PROJECT/agent-repo/middleware:$TAG

# 2. Deploy to Cloud Run
gcloud run deploy agent-middleware \
  --image=us-docker.pkg.dev/$PROJECT/agent-repo/middleware:$TAG \
  --region=us-central1 \
  --project=$PROJECT
```

### 1.3 Deploying a New Frontend Version

```bash
# From the frontend/ directory
npm run build
npx wrangler pages deploy .next --project-name=agent-frontend-dev
```

### 1.4 Viewing Logs

```bash
# Cloud Run middleware logs (last 1h)
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=agent-middleware" \
  --limit=100 --freshness=1h --project=$PROJECT

# WAF block events (Cloudflare dashboard)
# Dashboard → Security → Events → Filter: Action = Block
```

---

## 2. Stage A — Current (Free/Dev Tier)

| Component | Substrate | Tier | Limits |
|-----------|-----------|------|--------|
| Runtime | Cloud Run (self-hosted LangGraph) | Free tier | min=0, 1 vCPU, 2 GB, 3600s timeout |
| Database | Neon Free | Free | 0.5 GB storage, 100 CU-hr/mo |
| Memory | Mem0 Cloud Hobby | Free | API rate limits, p95 ~450ms |
| Telemetry | Cloud Trace + Cloud Logging | GCP default | 50 GB/mo logs, 5M spans/mo |
| Frontend Host | Cloudflare Pages | Free | 500 builds/mo, 1 concurrent build |
| Edge/CDN | Cloudflare | Pro ($20/mo) | Custom WAF rules, no 24h log mode |
| Auth | WorkOS AuthKit | Dev environment | MFA enforced for all users |
| Secrets | GCP Secret Manager | Free | 6 active versions per secret |

**Projected monthly cost**: $5–30/mo (dominated by Cloudflare Pro + minimal Cloud Run usage).

---

## 3. Stage A → B Upgrades

Each upgrade is triggered by a specific quota or performance threshold. All swaps are composition-root-only.

### 3.1 Neon Free → Neon Launch ($19/mo)

**Trigger**: Database storage > 0.5 GB OR CU-hr exhausted (80% alarm fires).

**Steps**:

1. Upgrade the Neon project plan in the [Neon Console](https://console.neon.tech) → Project Settings → Plan.
2. Update `infra/dev-tier/neon.tf` — no resource changes needed (the Neon provider reads the plan from the API).
3. Update `var.neon_region_id` if migrating to a different region for lower latency.
4. Verify: `SELECT 1` via the connection string.

**Swap file**: `infra/dev-tier/neon.tf` (plan attribute only)

**Composition root change**: None — the `NeonFreeThreadStore` adapter works unchanged on Launch.

### 3.2 Mem0 Cloud Hobby → Mem0 Cloud Starter

**Trigger**: >10K `add()` calls/mo OR p95 latency consistently >1s.

**Steps**:

1. Upgrade Mem0 plan at [mem0.ai/dashboard](https://app.mem0.ai) → Settings → Billing.
2. No code changes — the `MEM0_API_KEY` and `MEM0_BASE_URL` remain the same.
3. Verify: round-trip latency test from Cloud Run.

**Swap file**: `middleware/composition.py` (no change needed for Hobby→Starter; same adapter)

**Composition root change**: None — adapter is the same; only SaaS plan changes.

### 3.3 Cloud Run min=0 → min=1

**Trigger**: Cold-start latency unacceptable for beta users (>2s TTFT consistently).

**Steps**:

1. Update `infra/dev-tier/variables.tf`:
   - Remove the `middleware_min_instances == 0` validation.
   - Set default to `1`.
2. Run `tofu apply`.
3. Verify: `/healthz` returns 200 immediately after deploy (no cold start).

**Cost impact**: +$5–15/mo (1 always-on instance with cpu_idle=true).

**Swap file**: `infra/dev-tier/variables.tf` + `infra/dev-tier/cloud-run.tf`

### 3.4 Cloudflare Free → Cloudflare Pro ($25/mo)

**Trigger**: Image optimization needed OR WAF Advanced rules required.

**Status**: Already on Pro (upgraded during Sprint 2 for WAF custom rules).

---

## 4. Stage B → C Upgrades

### 4.1 Langfuse Cloud Hobby → Self-Hosted Langfuse

**Trigger**: >50K trace units/mo OR >30-day retention needed.

**Steps**:

1. Deploy Langfuse Docker to a new Cloud Run service.
2. Update `middleware/composition.py`:
   - Switch `ARCHITECTURE_PROFILE` check to instantiate `SelfHostedLangfuseAdapter` instead of `LangfuseCloudHobbyAdapter`.
3. Update Secret Manager: add Langfuse self-hosted DB URL, remove Langfuse Cloud keys.
4. Verify: run a traced agent session; confirm trace lands in self-hosted Langfuse.

**Swap file**: `middleware/composition.py`

### 4.2 Mem0 Cloud → Self-Hosted Mem0

**Trigger**: Latency budget requires <100ms p95 OR data residency requirements.

**Steps**:

1. Deploy Mem0 OSS to Cloud Run or GKE.
2. Update `middleware/composition.py`:
   - Instantiate `SelfHostedMem0Adapter` instead of `Mem0CloudHobbyAdapter`.
3. Migrate existing memories via Mem0 export/import API.
4. Update Secret Manager: add Mem0 self-hosted URL, remove cloud API key.
5. Verify: `add()` + `search()` round-trip from Cloud Run.

**Swap file**: `middleware/composition.py`

---

## 5. Stage C → D (V2-Frontier Graduation)

Full graduation from V3-Dev-Tier to V2-Frontier. This is the composition-root-only swap promised by architecture rule [F3].

### 5.1 Runtime: Self-Hosted → LangGraph Platform SaaS Plus

**Trigger**: >100K nodes/mo OR operational burden of self-hosted too high.

**Steps**:

1. Deploy the graph to LangGraph Platform Cloud.
2. Update `frontend/lib/composition.ts`:
   - Set `ARCHITECTURE_PROFILE=v2`.
   - `LangGraphPlatformSaaSClient` replaces `SelfHostedLangGraphDevClient`.
3. Update `MIDDLEWARE_URL` env var on Cloudflare Pages to point to LangGraph Cloud.
4. Verify: E2E smoke test passes.

**Swap file**: `frontend/lib/composition.ts`

### 5.2 Thread Store: Neon Free → Cloud SQL

**Trigger**: DB > 0.5 GB or CU-hr exhausted (if Neon Launch wasn't enough).

**Steps**:

1. Provision Cloud SQL instance via `infra/dev-tier/` or a new Tofu stack.
2. Run Drizzle migration against Cloud SQL.
3. Migrate data from Neon (pg_dump/pg_restore).
4. Update `frontend/lib/composition.ts`:
   - `CloudSQLThreadStore` replaces `NeonFreeThreadStore`.
5. Update `DATABASE_URL` in Secret Manager.
6. Verify: thread CRUD works; pagination tests pass.

**Swap file**: `frontend/lib/composition.ts`

### 5.3 Frontend Host: Cloudflare Pages → Vercel Pro

**Trigger**: Vercel DX desired for preview deployments, analytics, etc.

**Steps**:

1. Create Vercel project, link Git repo.
2. Set environment variables (public only — no secrets on frontend).
3. Update DNS to point to Vercel.
4. Update `MIDDLEWARE_URL` in Vercel project settings.
5. Verify: E2E smoke test passes on Vercel deployment.

**Swap file**: DNS + deploy config (no code change)

---

## 6. Incident Response Playbooks

### 6.1 Cloud Run 5xx Spike

1. Check logs: `gcloud logging read "resource.labels.service_name=agent-middleware AND severity>=ERROR" --limit=50`
2. Check if cold-start related (look for startup probe failures).
3. If OOM: increase `middleware_memory` in `variables.tf`, `tofu apply`.
4. If timeout: check for hung LLM calls; verify the `3600s` timeout hasn't been reduced.
5. If dependency failure: check Neon, Mem0, LLM provider status pages.

### 6.2 Neon CU-hr Exhaustion

1. Check usage: Neon Console → Project → Usage.
2. Immediate mitigation: reduce `history_retention_seconds` (currently 21600 = 6h).
3. If recurring: trigger Stage A→B upgrade (Neon Free → Launch).
4. Notify users that thread operations may be slow until upgraded.

### 6.3 WAF False Positive

1. Check Cloudflare Security Events for the blocked request.
2. If legitimate traffic, add an exception rule in `cloudflare-edge.tf`.
3. Run `tofu apply` to deploy the exception.
4. Monitor for 1h to confirm the false positive is resolved.

### 6.4 WorkOS Auth Failure

1. Check WorkOS Dashboard → Logs for auth errors.
2. If API key rotation needed: update Secret Manager, redeploy Cloud Run.
3. If MFA lockout: use WorkOS admin to reset user MFA.
4. Check that `WORKOS_CLIENT_ID` matches between Cloud Run env and WorkOS dashboard.

---

## 7. Secret Rotation

All secrets live in GCP Secret Manager. Rotation procedure:

```bash
# 1. Add a new version (old version stays active)
echo -n "NEW_SECRET_VALUE" | \
  gcloud secrets versions add SECRET_NAME --data-file=-

# 2. Redeploy Cloud Run to pick up the new version
gcloud run deploy agent-middleware --region=us-central1 --project=$PROJECT

# 3. Verify the service is healthy
curl "$(tofu -chdir=infra/dev-tier output -raw middleware_url)/healthz"

# 4. Disable the old version (optional, after confirming)
gcloud secrets versions disable OLD_VERSION_ID --secret=SECRET_NAME
```

| Secret | Rotation Trigger | Provider Dashboard |
|--------|------------------|--------------------|
| `workos-api-key` | Quarterly or on suspected compromise | [WorkOS Dashboard](https://dashboard.workos.com) |
| `openai-api-key` | Quarterly | [OpenAI Platform](https://platform.openai.com) |
| `anthropic-api-key` | Quarterly | [Anthropic Console](https://console.anthropic.com) |
| `langfuse-public-key` | On Langfuse plan change | [Langfuse Settings](https://cloud.langfuse.com) |
| `langfuse-secret-key` | On Langfuse plan change | [Langfuse Settings](https://cloud.langfuse.com) |
| `mem0-api-key` | On Mem0 plan change | [Mem0 Dashboard](https://app.mem0.ai) |
| `neon-database-url` | On Neon password rotation | [Neon Console](https://console.neon.tech) |

---

*This runbook documents the V3-Dev-Tier operations as specified in Sprint 4 §S4.3.1. Every substrate swap is a composition-root-only change per architecture rule [F3] — see the V2-Frontier Graduation Triggers table in [SPRINT_BOARD.md](../docs/plan/frontend/SPRINT_BOARD.md#v2-frontier-graduation-triggers) for the full swap matrix.*
