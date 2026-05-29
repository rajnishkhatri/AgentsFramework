# GCP Tier A — Live Deployment Operator Runbook

**Audience:** Solo operator on a laptop with `gcloud`, OpenTofu, Docker, and repo checkout.  
**Stack:** Combined backend + Next.js frontend on Cloud Run, Cloud SQL Postgres, GCS traces/facts, Secret Manager, Cloud Monitoring.  
**Time:** Day-0 preflight ~30 min · Day-1 first deploy ~60–90 min · Day-2 ops reference (ongoing).

This runbook stitches [Recipes 0–8](.) into a single top-to-bottom walkthrough. Each step is a copy-paste block plus a link to the deep recipe for the *why*. For account setup (project, billing, deployer SA), start with [HUMAN_SETUP.md](HUMAN_SETUP.md).

---

## Table of Contents

- [Architecture](#architecture)
- [Day-0 — Preflight](#day-0--preflight-no-gcp-resources-yet)
  - [0.1 Local toolchain](#01-local-toolchain-check)
  - [0.2 Account + billing](#02-account--billing-prerequisites)
  - [0.3 Quota check](#03-quota-check)
  - [0.4 Secret values gathered](#04-secret-values-gathered)
  - [0.5 Bootstrap script gate](#05-source-scriptsbootstrap_gcp_envsh)
- [Day-1 — First production deploy](#day-1--first-production-deploy)
  - [1.1 Environment block](#11-set-environment-block)
  - [1.2 Adapter sanity](#12-adapter-sanity)
  - [1.3 Phase 1: Foundations](#13-phase-1-foundations)
  - [1.4 Phase 2: Data tier](#14-phase-2-data-tier)
  - [1.5 Phase 3: Verify secrets](#15-phase-3-verify-secrets)
  - [1.6 Phase 4: Build + push images](#16-phase-4-build--push-images-by-digest)
  - [1.7 Phase 5: Backend Cloud Run](#17-phase-5-backend-cloud-run)
  - [1.8 Phase 6: Frontend Cloud Run](#18-phase-6-frontend-cloud-run)
  - [1.9 Phase 7: WorkOS human gate](#19-phase-7-human-gate--workos-redirect-uri)
  - [1.10 Phase 8: Observability + smoke](#110-phase-8-observability--smoke)
  - [1.11 Phase 9: Meta ring (optional)](#111-phase-9-meta-ring-optional)
  - [1.12 Go-live acceptance gate](#112-go-live-acceptance-gate)
- [Day-2 — Ongoing operations](#day-2--ongoing-operations)
  - [2.1 Push a new build](#21-push-a-new-build-default-tofu-managed)
  - [2.2 Advanced: revision tags](#22-advanced-live-cutover-with-revision-tags)
  - [2.3 Rollback](#23-rollback)
  - [2.4 Rotate a secret](#24-rotate-a-secret)
  - [2.5 Scale knobs](#25-scale-knobs)
  - [2.6 SSE production gotchas](#26-sse-production-gotchas)
  - [2.7 View logs](#27-view-logs--debug-a-failed-request) — see also [LOG_PIPELINE_GUIDE.md](LOG_PIPELINE_GUIDE.md)
  - [2.8 Database backup](#28-database-backup--inspect)
  - [2.9 Cost check](#29-cost-check)
  - [2.10 Teardown](#210-teardown)
- [Reference](#reference)
  - [3.1 Troubleshooting matrix](#31-troubleshooting-matrix)
  - [3.2 Best-practice callouts](#32-best-practice-callouts)
  - [3.3 Glossary + escalation](#33-glossary--escalation)
- [Appendices](#appendices)

---

## Architecture

Tier A topology (Option A backend + separate frontend):

```mermaid
flowchart LR
    Browser[Browser]
    FrontendCR[CloudRun_Frontend<br/>agent-frontend min=0]
    BackendCR[CloudRun_Combined<br/>agent-backend-combined min=0]
    CloudSQL[(CloudSQL_Postgres<br/>agent-db 10GB)]
    GCSFacts[(GCS_AgentFacts)]
    GCSTraces[(GCS_TrustTraces)]
    Secrets[SecretManager]
    Logging[CloudLogging]

    Browser -->|HTTPS *.run.app| FrontendCR
    FrontendCR -->|HTTPS+SSE MIDDLEWARE_URL| BackendCR
    BackendCR -->|AsyncPostgresSaver| CloudSQL
    BackendCR -->|storage.objectViewer| GCSFacts
    BackendCR -->|direct PutObject| GCSTraces
    BackendCR -->|secretAccessor| Secrets
    BackendCR --> Logging
    FrontendCR --> Logging
```

**Service names (from `infra/gcp/`):**

| Resource | Name / ID |
|----------|-----------|
| Backend Cloud Run | `agent-backend-combined` |
| Frontend Cloud Run | `agent-frontend` |
| Cloud SQL instance | `agent-db` (default, overridable in tfvars) |
| Artifact Registry repo | `agent-backend` |
| GCS buckets | `${PROJECT}-agent-facts`, `${PROJECT}-trust-traces` |
| Runtime SAs | `agent-backend-runtime@…`, `agent-frontend-runtime@…` |

---

## Day-0 — Preflight (no GCP resources yet)

Complete every subsection before `tofu apply`. **Hard gate at §0.5:** do not proceed to Day-1 if bootstrap reports any red `FAIL`.

### 0.1 Local toolchain check

From repo root:

```bash
cd /path/to/agent

# Install Python deps + IaC test tools
pip install -e ".[dev]"

# Version sanity (minimums)
gcloud version
tofu version          # need >= 1.6
docker version
python3 --version     # need >= 3.10
pytest --version
conftest --version
terraform-compliance --version

# Architecture boundary tests (fast, no cloud creds)
pytest tests/architecture/ -q
```

Expected: all architecture tests pass. Fix any import/layer violations before touching GCP.

### 0.2 Account + billing prerequisites

Complete [HUMAN_SETUP.md](HUMAN_SETUP.md) Steps 1–4 before continuing:

1. GCP project + billing linked  
2. Remote state bucket `${PROJECT}-tofu-state`  
3. `tofu-deployer` SA + key → `GOOGLE_APPLICATION_CREDENTIALS`  
4. `infra/gcp/terraform.tfvars` populated (gitignored)

One-shot auth + billing preflight:

```bash
export PROJECT="$(grep gcp_project_id infra/gcp/terraform.tfvars | awk -F'"' '{print $2}')"

gcloud auth list --format='table(account,status)'
gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"
gcloud config get-value project
gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)'
# Expect: True
```

If billing is not enabled:

```bash
gcloud billing projects link "$PROJECT" --billing-account=XXXXXX-XXXXXX-XXXXXX
```

### 0.3 Quota check

Warn-only — surfaces capacity limits before you provision Cloud SQL:

```bash
gcloud compute project-info describe --project="$PROJECT" \
  --format='table(quotas.metric, quotas.limit, quotas.usage)' \
  | grep -E 'CLOUD_SQL|CPUS_ALL_REGIONS'
```

**Future capacity gotcha:** Cloud Run instances connecting via the built-in Cloud SQL connector are limited to **100 connections per instance** ([Cloud SQL quotas](https://cloud.google.com/sql/docs/postgres/quotas)). At Tier A dev traffic this is rarely hit; note it before scaling `max_instances` or concurrency.

### 0.4 Secret values gathered

Collect these **out of band** (password manager, provider dashboards). **Never commit** values to git.

| Secret ID | Source |
|-----------|--------|
| `workos-api-key` | WorkOS Dashboard → API Keys |
| `openai-api-key` | platform.openai.com |
| `anthropic-api-key` | console.anthropic.com |
| `langfuse-public-key` / `langfuse-secret-key` | cloud.langfuse.com |
| `mem0-api-key` | app.mem0.ai |
| `agent-facts-secret` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `workos-cookie-password` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `database-url` | Placeholder until Phase 2 (connector format) |

Optional local store (gitignored):

```bash
cat > .env.gcp <<'EOF'
WORKOS_API_KEY=sk_live_...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
MEM0_API_KEY=m0-...
AGENT_FACTS_SECRET=...
WORKOS_COOKIE_PASSWORD=...
EOF
chmod 600 .env.gcp
```

Primary path: put real values in `infra/gcp/terraform.tfvars` (Recipe 1 creates Secret Manager versions from tfvars). Use `.env.gcp` only if you prefer manual `gcloud secrets versions add` in §1.5.

### 0.5 Source `scripts/bootstrap_gcp_env.sh`

```bash
source ./scripts/bootstrap_gcp_env.sh
```

Or run as a gate:

```bash
./scripts/bootstrap_gcp_env.sh
```

Expected: green `Preflight PASSED`. Exports `PROJECT`, `REGION`, and (when state exists) `BACKEND_URL` / `FRONTEND_URL`.

**Do not proceed to Day-1 if any line shows red `FAIL`.**

---

## Day-1 — First production deploy

> **Prefer an autopilot?** The phases below can be driven one at a time by the `deploy-gcp` skill and [`scripts/deploy_gcp.sh`](../../../scripts/deploy_gcp.sh), which enforce the plan -> policy -> apply gate order and stop at the two human gates automatically. See [SKILL_DEPLOY_GUIDE.md](SKILL_DEPLOY_GUIDE.md). The manual commands below remain the source of truth for what each phase does.

Every snippet below assumes you have sourced the bootstrap script (or exported the variables in [Appendix A](#appendix-a-copy-paste-env-block)).

### 1.1 Set environment block

Declare once per shell session:

```bash
export PROJECT="$(grep gcp_project_id infra/gcp/terraform.tfvars | awk -F'"' '{print $2}')"
export REGION="${REGION:-us-central1}"
export VERSION="v1"   # bump on each intentional release
export REPO_ROOT="$(pwd)"
export INFRA="${REPO_ROOT}/infra/gcp"
```

### 1.2 Adapter sanity

GCP runtime adapters (no cloud calls):

```bash
pytest tests/services/trace_sinks \
       tests/agent_ui_adapter/adapters/runtime \
       tests/services/cloud_providers \
       tests/services/governance -q
```

Deep dive: [00_adapters.md](00_adapters.md).

### 1.3 Phase 1: Foundations

```bash
cd "$INFRA"

tofu init \
  -backend-config="bucket=${PROJECT}-tofu-state" \
  -backend-config="prefix=infra/gcp"

tofu plan -out=tfplan -var-file=terraform.tfvars
tofu show -no-color tfplan > tfplan.txt

# Static Rego on HCL + plan-resolved BDD
conftest test --policy policies/ --parser hcl2 --all-namespaces *.tf
tofu show -json tfplan > tfplan.json
terraform-compliance -p tfplan.json -f features/

tofu apply tfplan
```

**Verify:**

```bash
gcloud services list --project="$PROJECT" --filter="state:ENABLED" \
  | grep -E 'artifactregistry|run|secretmanager|sqladmin|storage|monitoring|cloudbilling|cloudscheduler'

gcloud artifacts repositories list --project="$PROJECT" --location="$REGION"

gcloud iam service-accounts list --project="$PROJECT" \
  --filter="email:agent-backend-runtime"

gcloud secrets list --project="$PROJECT"
# Expect 9 secrets: workos-api-key, openai-api-key, anthropic-api-key,
# langfuse-public-key, langfuse-secret-key, mem0-api-key, database-url,
# agent-facts-secret, workos-cookie-password
```

Capture outputs:

```bash
tofu output -raw artifact_registry_url
tofu output -raw backend_runtime_service_account_email
```

Deep dive: [01_foundations.md](01_foundations.md).

### 1.4 Phase 2: Data tier

Ensure `cloud_sql_password` and related variables are in `terraform.tfvars` (see `terraform.tfvars.example`).

```bash
cd "$INFRA"

pytest tests/infra/gcp/ -q -m infra_gcp

tofu plan -out=tfplan -var-file=terraform.tfvars
tofu show -no-color tfplan > tfplan.txt
conftest test --policy policies/ --parser hcl2 --all-namespaces *.tf
tofu show -json tfplan > tfplan.json
terraform-compliance -p tfplan.json -f features/
tofu apply tfplan
```

Apply takes ~5–10 minutes (Cloud SQL creation).

**Verify:**

```bash
gcloud sql instances describe agent-db --project="$PROJECT" \
  --format='yaml(databaseVersion,state,settings.tier)'

gcloud sql databases list --instance=agent-db --project="$PROJECT"

gsutil ls -p "$PROJECT" | grep -E 'agent-facts|trust-traces'
```

**Update `database-url` to Cloud SQL connector format:**

```bash
cd "$INFRA"
CONNECTION_NAME="$(tofu output -raw cloud_sql_connection_name)"
PASSWORD='<cloud_sql_password from terraform.tfvars>'

echo -n "postgresql+asyncpg://agent_runtime:${PASSWORD}@/agent?host=/cloudsql/${CONNECTION_NAME}" \
  | gcloud secrets versions add database-url --project="$PROJECT" --data-file=-

gcloud secrets versions list database-url --project="$PROJECT"
# Expect version 2+ (version 1 was placeholder)
```

**Postgres schema migration (required before backend traffic):**

```bash
# Option A: Cloud SQL Auth Proxy from laptop
cloud-sql-proxy "$(tofu -chdir="$INFRA" output -raw cloud_sql_connection_name)" &
PROXY_PID=$!

DATABASE_URL="postgresql+asyncpg://agent_runtime:${PASSWORD}@localhost:5432/agent" \
python3 -c "
import asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
async def main():
    async with AsyncPostgresSaver.from_conn_string('${DATABASE_URL}') as saver:
        await saver.setup()
asyncio.run(main())
print('Postgres checkpointer schema ready')
"

kill "$PROXY_PID" 2>/dev/null || true
```

Deep dive: [02_data.md](02_data.md).

### 1.5 Phase 3: Verify secrets

Recipe 1 creates Secret Manager versions from `terraform.tfvars`. Confirm every secret has a non-placeholder latest version:

```bash
for secret in \
  workos-api-key openai-api-key anthropic-api-key \
  langfuse-public-key langfuse-secret-key mem0-api-key \
  database-url agent-facts-secret workos-cookie-password; do
  echo "=== $secret ==="
  gcloud secrets versions list "$secret" --project="$PROJECT" --limit=3
done
```

If any secret still holds a placeholder and you maintain values in `.env.gcp`:

```bash
set -a; source .env.gcp; set +a

echo -n "$WORKOS_API_KEY"       | gcloud secrets versions add workos-api-key --project="$PROJECT" --data-file=-
echo -n "$OPENAI_API_KEY"       | gcloud secrets versions add openai-api-key --project="$PROJECT" --data-file=-
echo -n "$ANTHROPIC_API_KEY"    | gcloud secrets versions add anthropic-api-key --project="$PROJECT" --data-file=-
echo -n "$LANGFUSE_PUBLIC_KEY"  | gcloud secrets versions add langfuse-public-key --project="$PROJECT" --data-file=-
echo -n "$LANGFUSE_SECRET_KEY"  | gcloud secrets versions add langfuse-secret-key --project="$PROJECT" --data-file=-
echo -n "$MEM0_API_KEY"         | gcloud secrets versions add mem0-api-key --project="$PROJECT" --data-file=-
echo -n "$AGENT_FACTS_SECRET"   | gcloud secrets versions add agent-facts-secret --project="$PROJECT" --data-file=-
echo -n "$WORKOS_COOKIE_PASSWORD" | gcloud secrets versions add workos-cookie-password --project="$PROJECT" --data-file=-
```

> **Never commit** `.env.gcp` or paste secrets into shell history on shared machines.

### 1.6 Phase 4: Build + push images by digest

```bash
cd "$REPO_ROOT"

AR_URL="$(tofu -chdir="$INFRA" output -raw artifact_registry_url)"
REGISTRY_HOST="${AR_URL%%/*}"

gcloud auth configure-docker "${REGISTRY_HOST}" --quiet

# Backend
docker build -f Dockerfile.backend -t "agent-backend:${VERSION}" .
docker run --rm -d --name backend-smoke -p 8080:8080 \
  -e GCP_EXECUTION_ENV=cloudrun \
  "agent-backend:${VERSION}" || true
sleep 5
curl -sf http://localhost:8080/healthz | grep -q '"status"' && echo "backend local /healthz OK" || echo "WARN: local healthz needs full env"
docker stop backend-smoke 2>/dev/null || true

docker tag "agent-backend:${VERSION}" "${AR_URL}/agent-backend:${VERSION}"
docker push "${AR_URL}/agent-backend:${VERSION}"

export BACKEND_IMAGE_DIGEST="$(gcloud artifacts docker images describe \
  "${AR_URL}/agent-backend:${VERSION}" \
  --project="$PROJECT" \
  --format='value(image_summary.digest)')"
echo "BACKEND_IMAGE_DIGEST=${BACKEND_IMAGE_DIGEST}"

# Frontend
docker build -f Dockerfile.frontend -t "agent-frontend:${VERSION}" ./frontend
docker tag "agent-frontend:${VERSION}" "${AR_URL}/agent-frontend:${VERSION}"
docker push "${AR_URL}/agent-frontend:${VERSION}"

export FRONTEND_IMAGE_DIGEST="$(gcloud artifacts docker images describe \
  "${AR_URL}/agent-frontend:${VERSION}" \
  --project="$PROJECT" \
  --format='value(image_summary.digest)')"
echo "FRONTEND_IMAGE_DIGEST=${FRONTEND_IMAGE_DIGEST}"
```

> **Sidebar — tag mutability:** The Artifact Registry repo is created without `--immutable-tags` (Tier A dev choice). **Always pin by digest in production** (`image@sha256:…`). For belt-and-suspenders tag immutability, see [TIER_B_FUTURE.md](TIER_B_FUTURE.md).

Set in `infra/gcp/terraform.tfvars`:

```hcl
backend_image  = "us-central1-docker.pkg.dev/YOUR_PROJECT/agent-backend/agent-backend@sha256:BACKEND_DIGEST"
frontend_image = "us-central1-docker.pkg.dev/YOUR_PROJECT/agent-backend/agent-frontend@sha256:FRONTEND_DIGEST"
```

Replace `YOUR_PROJECT` and digests with values from the push step.

Deep dive: [03_containerize.md](03_containerize.md).

### 1.7 Phase 5: Backend Cloud Run

**Prerequisite:** Upload at least one signed AgentFacts JSON to `gs://${PROJECT}-agent-facts/` (see [04_backend_cloudrun.md](04_backend_cloudrun.md) prerequisites).

```bash
cd "$INFRA"

tofu plan -out=tfplan -var-file=terraform.tfvars
tofu show -no-color tfplan > tfplan.txt
conftest test --policy policies/ --parser hcl2 --all-namespaces *.tf
tofu show -json tfplan > tfplan.json
terraform-compliance -p tfplan.json -f features/
tofu apply tfplan
```

**Verify:**

```bash
export BACKEND_URL="$(tofu output -raw backend_url)"
curl -sf "${BACKEND_URL}/healthz"
# Expect: {"status":"ok",...}
```

Authenticated SSE is deferred to Phase 8 (WorkOS token required).

Deep dive: [04_backend_cloudrun.md](04_backend_cloudrun.md).

### 1.8 Phase 6: Frontend Cloud Run

Ensure `frontend_image` digest is set in `terraform.tfvars` (§1.6).

```bash
cd "$INFRA"

tofu plan -out=tfplan -var-file=terraform.tfvars
tofu show -json tfplan > tfplan.json
terraform-compliance -p tfplan.json -f features/
tofu apply tfplan
```

**Verify:**

```bash
export FRONTEND_URL="$(tofu output -raw frontend_url)"
curl -s -o /dev/null -w '%{http_code}\n' "${FRONTEND_URL}/"
# Expect: 200, 307, or 308
```

Deep dive: [05_frontend_cloudrun.md](05_frontend_cloudrun.md).

### 1.9 Phase 7: HUMAN GATE — WorkOS redirect URI

> **STOP — human action required.** First deploy often succeeds at the GCP layer but fails user-facing auth until WorkOS knows the callback URL.

```bash
tofu -chdir="$INFRA" output -raw frontend_workos_redirect_uri
```

1. Open WorkOS Dashboard → Authentication → Redirects  
2. Add the URI (format: `https://agent-frontend-….run.app/api/auth/callback`)  
3. Save  
4. Browser: open `FRONTEND_URL`, sign in  
5. DevTools → Network → copy Bearer JWT from an authenticated API call  

Keep the JWT for §1.10.

### 1.10 Phase 8: Observability + smoke

Grant billing budget permission if not done ([HUMAN_SETUP.md](HUMAN_SETUP.md) Step 8):

```bash
export BILLING_ACCOUNT="XXXXXX-XXXXXX-XXXXXX"
gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT" \
  --member="serviceAccount:tofu-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/billing.admin"
```

Add to `terraform.tfvars`:

```hcl
billing_account_id       = "XXXXXX-XXXXXX-XXXXXX"
alert_notification_email = "ops@example.com"
monthly_budget_usd       = 50
```

Apply:

```bash
cd "$INFRA"
tofu plan -out=tfplan -var-file=terraform.tfvars
tofu show -json tfplan > tfplan.json
terraform-compliance -p tfplan.json -f features/
tofu apply tfplan
```

**Verify dashboard + budget:**

```bash
tofu output -raw monitoring_dashboard_name
gcloud billing budgets list --billing-account="$BILLING_ACCOUNT"
```

**End-to-end smoke:**

```bash
export BACKEND_URL="$(tofu -chdir="$INFRA" output -raw backend_url)"
export FRONTEND_URL="$(tofu -chdir="$INFRA" output -raw frontend_url)"
export BEARER_TOKEN="<WorkOS JWT from §1.9>"

./scripts/smoke_gcp.sh
```

Acceptance: `/healthz` PASS, frontend root PASS (if `FRONTEND_URL` set), `/run/stream` SSE PASS (if `BEARER_TOKEN` set).

Deep dive: [07_observability.md](07_observability.md).

### 1.11 Phase 9: Meta ring (optional)

Skip by default (`enable_meta_ring = false`). To enable:

```hcl
enable_meta_ring = true
meta_cron_schedule = "0 6 * * *"
meta_golden_set_gcs_uri = "gs://${PROJECT}-trust-traces/golden/eval.jsonl"
```

Upload golden set, apply, trigger job manually:

```bash
gcloud run jobs execute "$(tofu -chdir="$INFRA" output -raw meta_job_name)" \
  --region="$REGION" --project="$PROJECT"
```

Deep dive: [06_meta_ring.md](06_meta_ring.md).

### 1.12 Go-live acceptance gate

Operator sign-off checklist:

- [ ] `curl ${BACKEND_URL}/healthz` returns `"status":"ok"`
- [ ] `./scripts/smoke_gcp.sh` all executed checks green (with Bearer token)
- [ ] Cloud Monitoring dashboard shows request metrics
- [ ] Billing budget alert configured and visible
- [ ] All 9 secrets have non-placeholder latest versions
- [ ] No unexpected `allUsers` IAM bindings (Tier A documents two: backend + frontend `run.invoker`)
- [ ] WorkOS redirect URI saved and browser sign-in works
- [ ] Every phase verify step above recorded (copy command output to run log)

**You are live.** Estimated Tier A cost: ~$12–15/mo.

---

## Day-2 — Ongoing operations

### 2.1 Push a new build (default: tofu-managed)

```bash
source ./scripts/bootstrap_gcp_env.sh

export VERSION="v2"
AR_URL="$(tofu -chdir="$INFRA" output -raw artifact_registry_url)"

docker build -f Dockerfile.backend -t "agent-backend:${VERSION}" .
docker tag "agent-backend:${VERSION}" "${AR_URL}/agent-backend:${VERSION}"
docker push "${AR_URL}/agent-backend:${VERSION}"

DIGEST="$(gcloud artifacts docker images describe "${AR_URL}/agent-backend:${VERSION}" \
  --project="$PROJECT" --format='value(image_summary.digest)')"

# Update backend_image = "...@sha256:${DIGEST}" in terraform.tfvars

cd "$INFRA"
tofu plan -out=tfplan -var-file=terraform.tfvars
tofu apply tfplan
```

`cloud-run-backend.tf` uses `TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST` — apply shifts 100% traffic to the new revision automatically.

Repeat for frontend with `Dockerfile.frontend` and `frontend_image`.

### 2.2 Advanced: live cutover with revision tags

> **Decision:** Tier A default is §2.1 (tofu-managed). Use this sidebar only when you need smoke on a revision before cutover.

Google's recommended pattern ([Cloud Run rollouts](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)):

```bash
# Deploy new revision with no traffic, tag for smoke URL
gcloud run deploy agent-backend-combined \
  --image="${AR_URL}/agent-backend@${DIGEST}" \
  --region="$REGION" --project="$PROJECT" \
  --no-traffic --tag=green

# Smoke against tag URL: https://green---agent-backend-combined-….run.app/healthz

gcloud run services update-traffic agent-backend-combined \
  --to-tags=green=100 --region="$REGION" --project="$PROJECT"
```

**Trade-off:** Traffic changes outside OpenTofu cause **state drift** (Tofu thinks LATEST has 100%; gcloud may pin a tagged revision). Reconcile with an immediate `tofu apply`, or switch to percentage-based traffic blocks (Tier B).

### 2.3 Rollback

Five primitives, best-first:

| # | Method | When | Command |
|---|--------|------|---------|
| a | Instant traffic rollback | Bad revision still deployed | `gcloud run services update-traffic agent-backend-combined --to-revisions=PREV_REV=100 --region=$REGION` |
| b | Tag rollback | You used tags in §2.2 | `gcloud run services update-traffic agent-backend-combined --to-tags=blue=100 --region=$REGION` |
| c | Tofu re-apply previous digest | Known-good image in AR | Set prior `@sha256:…` in tfvars → `tofu apply tfplan` |
| d | Targeted destroy | Emergency only; causes drift | `tofu destroy -target=google_cloud_run_v2_service.backend_combined` |
| e | Cloud SQL restore | Data corruption | `gcloud sql backups restore …` (≥10 min) |

List revisions:

```bash
gcloud run revisions list --service=agent-backend-combined \
  --region="$REGION" --project="$PROJECT"
```

### 2.4 Rotate a secret

```bash
echo -n 'NEW_VALUE' | gcloud secrets versions add openai-api-key \
  --project="$PROJECT" --data-file=-
```

**Env-var-injected secrets (current Tier A pattern)** require a **Cloud Run redeploy** to pick up the new version (`tofu apply` or `gcloud run services update … --update-secrets`). Volume-mounted secrets refresh automatically (Tier B option).

### 2.5 Scale knobs

Tier A defaults (`variables.tf` / `cloud-run-backend.tf`):

| Knob | Tier A default | When to bump |
|------|----------------|--------------|
| `backend_min_instances` | `0` | SSE freezes, cold-start UX unacceptable (~+$117/mo for min=1) |
| `backend_max_instances` | `10` | Sustained traffic > free tier |
| `backend_cpu` | `1000m` | CPU-bound agent loops |
| `backend_memory` | `2Gi` | OOM on long contexts |
| `backend_request_timeout_seconds` | `3600` | Already max for SSE |
| `--no-cpu-throttling` | off (cpu_idle=true) | SSE mid-stream stalls (see §2.6) |

Change via `terraform.tfvars` + `tofu apply`, or ad hoc:

```bash
gcloud run services update agent-backend-combined \
  --max-instances=20 --concurrency=80 \
  --region="$REGION" --project="$PROJECT"
```

Ad hoc changes drift from Tofu — prefer tfvars for durable config.

### 2.6 SSE production gotchas

Current Tier A: `timeout=3600s`, `cpu_idle=true`, `min_instances=0` (cost-optimized).

If users report SSE freezes mid-stream:

1. Set `--min-instances=1` and `--no-cpu-throttling` on backend  
2. Ensure responses send `X-Accel-Buffering: no`  
3. Send 20–30s heartbeats from the stream handler  

Trade-off: `min_instances=1` adds ~$117/mo compute — defer unless symptoms appear. See [TIER_B_FUTURE.md](TIER_B_FUTURE.md) for production SSE posture.

### 2.7 View logs / debug a failed request

For a full step-by-step walkthrough of the browser → BFF → backend → Postgres/GCS pipeline (auth, auto-provision, `stream_ended`, trace correlation), see **[LOG_PIPELINE_GUIDE.md](LOG_PIPELINE_GUIDE.md)**.

Quick queries:

```bash
# Backend errors (last hour)
gcloud logging read \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="agent-backend-combined"
   severity>=ERROR' \
  --project="$PROJECT" --limit=20 --freshness=1h

# Cloud SQL connection issues
gcloud logging read \
  'resource.labels.service_name="agent-backend-combined"
   textPayload=~"cloudsql|postgres|asyncpg"' \
  --project="$PROJECT" --limit=20

# By trace ID (from response header)
gcloud logging read \
  'trace="projects/'"$PROJECT"'/traces/TRACE_ID"' \
  --project="$PROJECT" --limit=50
```

Frontend service: replace `service_name` with `agent-frontend`.

### 2.8 Database backup + inspect

```bash
gcloud sql backups list --instance=agent-db --project="$PROJECT"

# On-demand backup before schema migration
gcloud sql backups create --instance=agent-db --project="$PROJECT"

# Point-in-time restore (example — adjust time)
gcloud sql instances clone agent-db agent-db-restored \
  --point-in-time='2026-05-24T12:00:00Z' \
  --project="$PROJECT"
```

### 2.9 Cost check

```bash
gcloud billing budgets list --billing-account="$BILLING_ACCOUNT"
```

If alert fires, check:

- Cloud SQL disk autogrowth (Tier A caps at 10 GB with `disk_autoresize = false`)  
- Accidental `min_instances >= 1` on backend or frontend  
- Runaway LLM loop (5xx/latency alerts in dashboard)  

### 2.10 Teardown

See [08_cleanup.md](08_cleanup.md):

```bash
# Partial (~$0.60/mo retained — AR + secrets)
CONFIRM=1 MODE=partial ./scripts/teardown_gcp.sh

# Full stack destroy
CONFIRM=1 MODE=full ./scripts/teardown_gcp.sh
```

Remote state bucket `${PROJECT}-tofu-state` is outside the Tofu stack — delete manually if removing the project.

---

## Reference

### 3.1 Troubleshooting matrix

| Symptom | Likely cause | Diagnostic | Mitigation | Recipe |
|---------|--------------|------------|------------|--------|
| `Billing must be enabled for activation` | Project not linked to billing | `gcloud billing projects describe $PROJECT` | Link billing account | [HUMAN_SETUP.md](HUMAN_SETUP.md) |
| `SERVICE_DISABLED` on apply | API not enabled | `gcloud services list --enabled --filter="…"` | `gcloud services enable API` or bootstrap script | [01_foundations.md](01_foundations.md) |
| `permission denied` on `tofu apply` | Deployer SA missing role | `gcloud projects get-iam-policy $PROJECT` | Grant roles per HUMAN_SETUP §3 | [HUMAN_SETUP.md](HUMAN_SETUP.md) |
| `Revision … not ready` | Secret access or bad image | `gcloud run revisions describe REV --region=$REGION` | Fix secret IAM / image URI | [04_backend_cloudrun.md](04_backend_cloudrun.md) |
| `Image not found` | Wrong digest or AR path | `gcloud artifacts docker images list $AR_URL` | Re-push image; fix `@sha256` in tfvars | [03_containerize.md](03_containerize.md) |
| `/healthz` 503 | Cloud SQL not RUNNABLE or startup crash | `gcloud sql instances describe agent-db`; Cloud Run logs | Wait for SQL; fix `DATABASE_URL` format | [02_data.md](02_data.md) |
| `/run/stream` 500 `relation "checkpoints" does not exist` | Schema migration skipped | Connect via proxy; `\dt` in psql | Run `AsyncPostgresSaver.setup()` | [04_backend_cloudrun.md](04_backend_cloudrun.md) |
| SSE stops after ~30s | CPU throttling on idle | Cloud Run metrics; `cpu_idle=true` | `--no-cpu-throttling`, `min_instances=1` | §2.6 |
| SSE events batched / delayed | Response buffering | Inspect response headers | `X-Accel-Buffering: no`; heartbeats | §2.6 |
| Stale secret after rotation | Env-var injection caches version | `gcloud secrets versions list SECRET` | Redeploy Cloud Run service | §2.4 |
| `tofu destroy` hangs on Cloud SQL | Deletion protection / connections | `gcloud sql instances describe agent-db` | Stop Cloud Run first; Recipe 8 order | [08_cleanup.md](08_cleanup.md) |
| WorkOS redirect URI mismatch | Callback not in dashboard | Compare `tofu output frontend_workos_redirect_uri` | Add URI in WorkOS | [05_frontend_cloudrun.md](05_frontend_cloudrun.md) |
| Frontend cannot reach backend | Wrong `MIDDLEWARE_URL` | `gcloud run services describe agent-frontend` env | Re-apply frontend tf; check backend URL | [05_frontend_cloudrun.md](05_frontend_cloudrun.md) |
| `Exceeded 100 connections` | Too many instances × pool size | Cloud SQL metrics connections | Lower concurrency / max_instances | §0.3 |

### 3.2 Best-practice callouts

- Always `tofu plan -out=tfplan` then `tofu apply tfplan` ([Terraform plan docs](https://developer.hashicorp.com/terraform/cli/commands/plan)).
- Pin images by **digest** in production; tags are mutable ([AR image names](https://cloud.google.com/artifact-registry/docs/docker/names)).
- `--immutable-tags` on Artifact Registry is Tier B belt-and-suspenders (current repo omits it).
- Revision tagging + `--no-traffic` for canary; Tier A default uses tofu-managed 100%-LATEST.
- Workload Identity Federation > JSON SA keys for CI handoff (future recipe).
- Verify after each phase — do not chain applies without smoke checks passing.
- Tier B: `deletion_policy = "DISABLE"` on secrets for audit trail; Tier A uses `ABANDON`.

### 3.3 Glossary + escalation

| Term | Meaning |
|------|---------|
| **Deployer SA** | `tofu-deployer@…` — OpenTofu provisioning identity (broad IAM) |
| **Runtime SA** | `agent-backend-runtime@…` / `agent-frontend-runtime@…` — what containers run as |
| **Tag URL** | `https://green---SERVICE-HASH-REGION.a.run.app` — revision-tagged smoke endpoint |
| **Primary URL** | `tofu output -raw backend_url` / `frontend_url` |

**Escalation:**

- GCP billing / org policy → org admin or [GCP Support](https://cloud.google.com/support)
- WorkOS auth → WorkOS Dashboard support
- Repo / recipe bugs → file issue in project tracker with `tofu plan` output and redacted logs

**Where next:** [TIER_B_FUTURE.md](TIER_B_FUTURE.md) — HA Postgres, internal LB, Pub/Sub pipeline, custom domain.

---

## Chat 401 Triage

If the chat UI shows a 401 or "Session expired" after WorkOS sign-in, use Cloud Run logs to isolate the failing layer:

| Log signal | Layer | Action |
|------------|-------|--------|
| `hasClaim: false`, `hasSessionHdr: false` | BFF middleware | Verify `handleAuthkitHeaders()` composable pattern in `frontend/middleware.ts` |
| `hasClaim: true`, `upstreamStatus: 401`, `auth_reject reason=invalid_token_use` | Backend JWT | Check AuthKit token claims vs verifier — absent `token_use` should be treated as access |
| `auth_reject reason=invalid_issuer` | Backend JWT | Align `WORKOS_ISSUER` / `client_id` env with the token's `iss` claim |
| `upstreamStatus: 500`, `relation "checkpoints" does not exist` | Runtime / DB | Run Postgres saver schema setup (Recipe 4 gotcha — `PostgresSaver.setup()`) |

**Quick log queries:**

```bash
# BFF: check if session headers reach route handler
gcloud logging read \
  'resource.labels.service_name="agent-frontend" AND textPayload:"route.ts:POST"' \
  --project=$PROJECT --limit=5

# Backend: auth_ok vs auth_reject
gcloud logging read \
  'resource.labels.service_name="agent-backend-combined" AND (textPayload:"auth_ok" OR textPayload:"auth_reject")' \
  --project=$PROJECT --limit=10
```

---

## Appendices

### Appendix A: Copy-paste env block

```bash
export PROJECT="$(grep gcp_project_id infra/gcp/terraform.tfvars | awk -F'"' '{print $2}')"
export REGION="us-central1"
export VERSION="v1"
export REPO_ROOT="$(pwd)"
export INFRA="${REPO_ROOT}/infra/gcp"
export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/tofu-deployer-key.json}"
source ./scripts/bootstrap_gcp_env.sh
```

### Appendix B: Pre-flight script

Full source: [`scripts/bootstrap_gcp_env.sh`](../../../scripts/bootstrap_gcp_env.sh). Run:

```bash
./scripts/bootstrap_gcp_env.sh
```

See §0.5 for expected output.

### Appendix C: Citations

**Day-0 / Day-1 / Day-2 framing**

- [Spacelift — Day 0, 1, 2 operations](https://spacelift.io/blog/day-0-day-1-day-2-operations)
- [Octopus — Day 0 vs Day 1 vs Day 2](https://octopus.com/blog/difference-between-day-0-1-2-operations)

**Runbook template**

- [Skelton Thatcher run-book template](https://github.com/SkeltonThatcher/run-book-template/blob/master/run-book-template.md)

**GCP operations**

- [Cloud Run request timeout](https://cloud.google.com/run/docs/configuring/request-timeout)
- [Cloud Run rollouts and rollbacks](https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)
- [Cloud SQL Postgres quotas](https://cloud.google.com/sql/docs/postgres/quotas)
- [Artifact Registry Docker names](https://cloud.google.com/artifact-registry/docs/docker/names)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)

**IaC**

- [Terraform plan command](https://developer.hashicorp.com/terraform/cli/commands/plan)
