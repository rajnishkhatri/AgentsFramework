---
type: runbook
title: 'Recipe 2 — Data Tier (Cloud SQL + GCS Buckets)'
description: 'Provision the Tier A data tier: Cloud SQL PostgreSQL + GCS buckets.'
tags: [recipe, gcp]
---

# Recipe 2 — Data Tier (Cloud SQL + GCS Buckets)

**Goal:** Provision the stateful layer for Tier A: a Cloud SQL PostgreSQL 15 instance for LangGraph checkpoints, two GCS buckets (agent-facts for signed identity documents, trust-traces for governance JSONL), and the IAM bindings that let the runtime service account reach them. After this recipe, the backend has somewhere to persist conversations and governance artifacts.

**Status:** Complete | Tests passing | Tier A cost: ~$12/mo (Cloud SQL dominates)

---

## Before We Start: A Story

Recipe 1 built the workshop foundations: unlocked doors (APIs), an image shelf (Artifact Registry), a robot badge (runtime SA), and locked envelopes (Secret Manager). But the workshop floor is still bare. There is no workbench and no filing cabinet.

Think about what happens when a user sends a message to the agent. The agent thinks, calls tools, and streams an answer back. Along the way, it produces two kinds of data that must survive a container restart:

1. **Checkpoint data.** LangGraph saves the conversation graph state after each step so it can resume if the container restarts mid-turn. On your laptop, this lives in SQLite. In Cloud Run, the container is ephemeral — SQLite vanishes on every cold start. We need a durable database. That is Cloud SQL.

2. **Governance artifacts.** The trust kernel writes signed identity documents (AgentFacts) and trust traces. On your laptop, these are local JSON and JSONL files. In Cloud Run, we need cloud storage. That is GCS.

This recipe creates the workbench (Cloud SQL) and the filing cabinet (two GCS buckets). It also gives the runtime SA just enough access to use them — read identity documents, write traces, connect to the database.

```mermaid
flowchart LR
    BackendCR[Cloud Run Backend<br/>Recipe 4]
    CloudSQL[(Cloud SQL Postgres 15<br/><b>agent-db</b><br/>10 GB, single-AZ)]
    GCSFacts[(GCS agent-facts<br/>versioned, read-only)]
    GCSTraces[(GCS trust-traces<br/>90-day → Nearline)]
    RuntimeSA["agent-backend-runtime SA"]

    BackendCR -->|"AsyncPostgresSaver<br/>roles/cloudsql.client"| CloudSQL
    BackendCR -->|"agent_facts_gcs_registry<br/>roles/storage.objectViewer"| GCSFacts
    BackendCR -->|"gcs_sink<br/>roles/storage.objectCreator"| GCSTraces
    RuntimeSA -.->|"IAM grants"| CloudSQL
    RuntimeSA -.->|"IAM grants"| GCSFacts
    RuntimeSA -.->|"IAM grants"| GCSTraces
```

---

## Prerequisites

- Recipe 1 complete (foundations applied, all 33+ tests passing).
- `infra/gcp/terraform.tfvars` updated with Cloud SQL variables (see `terraform.tfvars.example`).
- Generate a secure database password:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

---

## The Four Data Tier Lessons

---

### Lesson 1 — The Vanishing Workbench Problem

**`infra/gcp/data.tf` — Cloud SQL**

> "The agent remembers conversations on my laptop. Why does it forget everything in Cloud Run?"

On your laptop, LangGraph uses `AsyncSqliteSaver` — a file-based database in `cache/`. Every cold start in Cloud Run wipes the container filesystem. The conversation state vanishes.

Recipe 0 built `PostgresCheckpointer` (the code adapter). This recipe creates the actual database it connects to: a Cloud SQL PostgreSQL 15 instance.

```hcl
resource "google_sql_database_instance" "main" {
  name                = var.cloud_sql_instance_name  # "agent-db"
  database_version    = "POSTGRES_15"
  deletion_protection = false  # Tier A dev; Tier B enables this

  settings {
    tier              = var.cloud_sql_tier  # "db-f1-micro" (~$7.67/mo)
    disk_size         = var.cloud_sql_disk_size_gb  # 10 GB
    disk_type         = "PD_SSD"
    availability_type = "ZONAL"  # single-AZ; Tier B upgrades to REGIONAL

    backup_configuration {
      enabled = true
    }
  }
}
```

Key decisions:

- **`db-f1-micro`** is the smallest tier (~$7.67/mo sustained). It shares a vCPU with other tenants, which is fine for dev traffic. Tier B recipe B3 upgrades to a dedicated-core tier.
- **`deletion_protection = false`** lets Recipe 8 tear down without manual console intervention. This is a dev-only setting.
- **`disk_autoresize = false`** caps costs at 10 GB. At Tier A traffic, checkpoint data grows slowly.
- **Backups are enabled** because losing conversation state is worse than the negligible backup cost on a 10 GB instance.
- **`ZONAL` availability** means a single zone. If that zone goes down, the database is unavailable. Tier B recipe B3 upgrades to `REGIONAL` (multi-AZ HA, ~$310/mo).

> **Why PostgreSQL 15 specifically?** It is the version the `langgraph-checkpoint-postgres` package targets. Using 14 or 16 would work but is untested in this stack's CI.

**Checkpoint question:** What happens to in-flight conversations if the Cloud SQL instance restarts?

*Answer: LangGraph's `AsyncPostgresSaver` persists after each graph step. A restart loses at most the current in-progress step; the conversation resumes from the last committed checkpoint.*

---

### Lesson 2 — The Filing Cabinet Problem

**`infra/gcp/data.tf` — GCS buckets**

> "The trust kernel writes identity documents and traces to files. Where do those go in the cloud?"

Two buckets, two purposes:

**`agent-facts` bucket** — stores signed AgentFacts JSON documents. These are the agent's identity card: who it is, what capabilities it has, what policies apply. The `agent_facts_gcs_registry.py` adapter (Recipe 0) reads them at startup.

```hcl
resource "google_storage_bucket" "agent_facts" {
  name                        = "${var.gcp_project_id}-agent-facts"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true  # dev-only

  versioning {
    enabled = true
  }
}
```

Versioning is enabled because identity rollback should be a metadata operation. If a bad AgentFacts document is published, the operator reverts to the previous version instead of re-signing and re-deploying.

**`trust-traces` bucket** — stores JSONL trust trace files written by `gcs_sink.py` (Recipe 0). These are the governance audit trail: every LLM call, every tool invocation, every policy decision.

```hcl
resource "google_storage_bucket" "trust_traces" {
  name                        = "${var.gcp_project_id}-trust-traces"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true  # dev-only

  lifecycle_rule {
    condition { age = 90 }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}
```

The 90-day lifecycle rule moves old traces to Nearline storage class. At Tier A volume (<1 GB/mo), the cost difference is negligible, but the pattern is correct for Tier B where trace volume grows.

Both buckets enforce:

- **`uniform_bucket_level_access = true`** — disables legacy ACLs; all access is controlled by IAM.
- **`public_access_prevention = "enforced"`** — prevents accidental `allUsers` grants. Even a project admin cannot make these buckets public without first changing this setting.
- **`force_destroy = true`** — dev-only; lets `tofu destroy` remove non-empty buckets. Recipe 8 documents the teardown sequence.

**Checkpoint question:** Why does the agent-facts bucket have versioning but the trust-traces bucket does not?

*Answer: Agent-facts documents are identity records that may need rollback. Trust traces are append-only audit logs — there is no rollback scenario, and versioning would double storage cost for no operational benefit.*

---

### Lesson 3 — The Narrow Badge Problem

**`infra/gcp/data.tf` — IAM bindings**

> "The runtime SA exists from Recipe 1. How does it reach the database and buckets?"

Three new IAM bindings:

| Binding | Role | Scope | Why this narrow |
|---------|------|-------|-----------------|
| Cloud SQL connector | `roles/cloudsql.client` | Project | Required by Cloud Run's built-in Cloud SQL connector (Unix socket) |
| Agent-facts read | `roles/storage.objectViewer` | Bucket | Read-only: runtime reads signed facts, never writes them |
| Trust-traces write | `roles/storage.objectCreator` | Bucket | Write-only: runtime appends traces, never reads or deletes them |

```hcl
resource "google_project_iam_member" "backend_runtime_cloudsql_client" {
  role   = "roles/cloudsql.client"
  member = local.backend_runtime_member
}

resource "google_storage_bucket_iam_member" "agent_facts_reader" {
  bucket = google_storage_bucket.agent_facts.name
  role   = "roles/storage.objectViewer"
  member = local.backend_runtime_member
}

resource "google_storage_bucket_iam_member" "trust_traces_writer" {
  bucket = google_storage_bucket.trust_traces.name
  role   = "roles/storage.objectCreator"
  member = local.backend_runtime_member
}
```

`roles/cloudsql.client` is a project-level role (not instance-level) because the Cloud Run built-in connector needs project-wide Cloud SQL access to establish the Unix domain socket. This is the documented minimum for the connector.

The bucket IAM roles are deliberately asymmetric:

- **objectViewer** (facts) = `storage.objects.get` + `storage.objects.list`. The runtime can read any fact document.
- **objectCreator** (traces) = `storage.objects.create` only. The runtime can write new trace files but cannot read, list, or delete existing ones. If the backend is compromised, the attacker cannot exfiltrate or tamper with the audit trail.

> **Why not `roles/storage.objectAdmin` for simplicity?** Because blast radius matters. `objectAdmin` includes delete permissions. A compromised runtime with objectAdmin on the traces bucket could destroy the governance audit trail.

**Checkpoint question:** If the runtime SA needs to both read and write to a bucket, which role should it get?

*Answer: `roles/storage.objectUser` — the narrowest role that includes both `get` and `create`. But neither of our buckets needs that: facts is read-only, traces is write-only.*

---

### Lesson 4 — The Connection String Problem

**`terraform.tfvars.example` and Secret Manager**

> "Recipe 1 created a `database-url` secret with a placeholder. How does it get the real value?"

After `tofu apply` creates the Cloud SQL instance, the operator constructs the connection string and updates the Secret Manager secret. The format for Cloud Run's built-in connector is:

```
postgresql+asyncpg://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE
```

The `@/` (no hostname) is intentional — Cloud Run's connector provides the database via a Unix domain socket at `/cloudsql/PROJECT:REGION:INSTANCE`.

```bash
# After tofu apply, construct and update the DATABASE_URL secret:
CONNECTION_NAME=$(tofu output -raw cloud_sql_connection_name)
echo -n "postgresql+asyncpg://agent_runtime:YOUR_PASSWORD@/agent?host=/cloudsql/${CONNECTION_NAME}" \
  | gcloud secrets versions add database-url --data-file=-
```

This is a **human review gate** step because the password is involved. The operator constructs the URL from the Tofu output (connection name) and their known password (from `terraform.tfvars`), then writes it to Secret Manager.

Alternatively, if `database_url` is set directly in `terraform.tfvars`, Tofu will create the secret version. But most operators prefer the manual `gcloud secrets versions add` approach to avoid having the full connection URL in the tfvars file.

**Checkpoint question:** Why does the connection string use a Unix socket path instead of a TCP IP address?

*Answer: Cloud Run's built-in Cloud SQL connector provides a secure Unix domain socket via the `cloud_sql_instances` annotation (Recipe 4). This eliminates the need for a public IP allowlist and encrypts the connection without an SSL certificate. The `@/` with no host triggers asyncpg to use the `host=` query parameter as the socket directory.*

---

## Agent Steps

These steps provision the stateful layer. We test the blueprint first, initialize the same remote state backend from Recipe 1, apply the Cloud SQL and GCS resources, then update the runtime's database secret after the connection name exists.

### 1. Update terraform.tfvars

Add Cloud SQL variables to your gitignored `terraform.tfvars`:

```bash
# Run from the repo root.
export PROJECT=$(grep gcp_project_id infra/gcp/terraform.tfvars | awk -F'"' '{print $2}')

# Generate a secure password
PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "cloud_sql_password = \"${PASSWORD}\"" >> infra/gcp/terraform.tfvars
```

If `cloud_sql_password` already exists in `terraform.tfvars`, replace it instead of appending a duplicate line.

### 2. Run HCL/pytest gates

```bash
# Run from the repo root.
pytest tests/infra/gcp/ -q -m infra_gcp
```

All tests must pass before applying. The suite now includes data tier tests validating:

- Cloud SQL Postgres 15 with correct shape (ZONAL, backups, deletion_protection=false).
- Two GCS buckets with uniform access and public access prevention.
- IAM bindings: cloudsql.client, objectViewer, objectCreator.
- No literal passwords in HCL.
- No overly broad storage IAM roles.

### 3. OpenTofu init

```bash
cd infra/gcp

tofu init \
  -backend-config="bucket=${PROJECT}-tofu-state" \
  -backend-config="prefix=infra/gcp"
```

If Recipe 1 was applied from this checkout, `tofu init` should simply confirm the existing backend and provider setup. Running it again is harmless and makes this recipe self-contained for a new operator.

### 4. Plan and review

```bash
tofu plan -out=tfplan 2>&1 | tee /tmp/recipe2-plan.txt
```

Expected plan: **~8–10 resources to add** on top of Recipe 1:

- `google_sql_database_instance` x 1
- `google_sql_database` x 1
- `google_sql_user` x 1
- `google_storage_bucket` x 2
- `google_project_iam_member` x 1 (cloudsql.client)
- `google_storage_bucket_iam_member` x 2

### 5. Apply

```bash
tofu apply tfplan
```

Apply takes approximately 5–10 minutes (Cloud SQL instance creation is the slow step).

### 6. Capture outputs

```bash
tofu output -json > /tmp/recipe2-outputs.json
```

Key outputs for downstream recipes:

- `cloud_sql_connection_name` — Recipe 4 Cloud Run `cloud_sql_instances` annotation
- `agent_facts_bucket` — Recipe 4 `GCS_FACTS_BUCKET` env var
- `trust_traces_bucket` — Recipe 4 `GCS_TRACES_BUCKET` env var

### 7. Update DATABASE_URL secret

```bash
CONNECTION_NAME=$(tofu output -raw cloud_sql_connection_name)
PASSWORD="<your cloud_sql_password from terraform.tfvars>"

echo -n "postgresql+asyncpg://agent_runtime:${PASSWORD}@/agent?host=/cloudsql/${CONNECTION_NAME}" \
  | gcloud secrets versions add database-url --data-file=-
```

### 8. Run AsyncPostgresSaver migration (optional now, required before Recipe 4)

If you have the Cloud SQL Auth Proxy installed locally:

```bash
# Start the proxy
cloud-sql-proxy $(tofu output -raw cloud_sql_connection_name) &

# Run the migration
DATABASE_URL="postgresql+asyncpg://agent_runtime:${PASSWORD}@localhost:5432/agent" \
  python -c "
import asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
async def migrate():
    saver = AsyncPostgresSaver.from_conn_string('$DATABASE_URL')
    await saver.setup()
    print('Migration complete')
asyncio.run(migrate())
"
```

Alternatively, the `PostgresCheckpointer` adapter (Recipe 0) calls `setup()` on first connection, so the migration runs automatically when the backend starts in Cloud Run (Recipe 4).

---

## Human Review Gate

After `tofu apply`, the operator verifies:

- [ ] **Cloud SQL instance:** `gcloud sql instances describe agent-db --project=$PROJECT` shows `POSTGRES_15`, `RUNNABLE` state.
- [ ] **Database exists:** `gcloud sql databases list --instance=agent-db --project=$PROJECT` shows `agent`.
- [ ] **GCS buckets exist:** `gsutil ls -p $PROJECT` shows both `gs://${PROJECT}-agent-facts` and `gs://${PROJECT}-trust-traces`.
- [ ] **Agent-facts versioning:** `gsutil versioning get gs://${PROJECT}-agent-facts` shows `Enabled`.
- [ ] **Public access prevention:** `gsutil pap get gs://${PROJECT}-agent-facts` shows `enforced`.
- [ ] **DATABASE_URL secret updated:** `gcloud secrets versions list database-url --project=$PROJECT` shows version 2 (version 1 was the placeholder).
- [ ] **No broad IAM:** `gcloud projects get-iam-policy $PROJECT --flatten="bindings[].members" --filter="bindings.members:agent-backend-runtime" --format="table(bindings.role)"` shows only `logWriter`, `metricWriter`, and `cloudsql.client`.

---

## For A General Audience

If you are adapting this recipe for another Next.js + LangGraph stack:

- Replace `agent-db` with your Cloud SQL instance name.
- Replace `agent` with your application database name.
- Replace `agent_runtime` with your database user name.
- Adjust `cloud_sql_tier` based on your traffic: `db-f1-micro` for dev, `db-custom-1-3840` for light production, `db-custom-2-7680` for moderate load.
- Replace the bucket names (`agent-facts`, `trust-traces`) with your application's equivalents.
- If your stack does not use signed identity documents, drop the agent-facts bucket.
- If your stack uses a different trace sink (e.g., BigQuery, Pub/Sub), replace the trust-traces bucket with the appropriate resource.
- The `roles/cloudsql.client` binding pattern is Cloud Run-specific (built-in connector). If you use Cloud SQL Auth Proxy sidecar or a different connector, adjust accordingly.

The reusable pattern is: database first, object storage second, narrow IAM third, connection string last.

---

## Verify

```bash
# 1. Cloud SQL instance status
gcloud sql instances describe $(tofu output -raw cloud_sql_instance_name) \
  --project=$PROJECT --format="value(state)"
# Expected: RUNNABLE

# 2. Database exists
gcloud sql databases list --instance=$(tofu output -raw cloud_sql_instance_name) \
  --project=$PROJECT --format="value(name)" | grep agent
# Expected: agent

# 3. GCS buckets exist
gsutil ls -p $PROJECT | grep -E "agent-facts|trust-traces"
# Expected: two bucket URLs

# 4. Agent-facts versioning enabled
gsutil versioning get gs://$(tofu output -raw agent_facts_bucket)
# Expected: Enabled

# 5. Local proxy connectivity test (requires cloud-sql-proxy)
cloud-sql-proxy $(tofu output -raw cloud_sql_connection_name) &
PGPASSWORD="$PASSWORD" psql -h localhost -U agent_runtime -d agent -c "SELECT 1;"
# Expected: returns 1

# 6. HCL test suite (re-run)
pytest tests/infra/gcp/ -q -m infra_gcp
```

---

## Rollback

Recipe 2 provisions stateful resources. Destroy order matters:

```bash
cd infra/gcp

# Cloud SQL instance deletion requires deletion_protection=false (already set)
# GCS buckets require force_destroy=true (already set) to remove non-empty buckets
tofu destroy -target=google_storage_bucket_iam_member.agent_facts_reader \
             -target=google_storage_bucket_iam_member.trust_traces_writer \
             -target=google_project_iam_member.backend_runtime_cloudsql_client \
             -auto-approve

tofu destroy -target=google_sql_user.agent \
             -target=google_sql_database.agent \
             -auto-approve

tofu destroy -target=google_sql_database_instance.main \
             -target=google_storage_bucket.agent_facts \
             -target=google_storage_bucket.trust_traces \
             -auto-approve
```

Or, if tearing down the full stack: `tofu destroy -auto-approve` (safe because `deletion_protection=false` and `force_destroy=true`).

**Warning:** Cloud SQL instance names cannot be reused for 7 days after deletion. If you destroy and recreate, use a different name or wait.

---

## Cost Note (Tier A)

| Resource | Monthly cost |
|----------|-------------|
| Cloud SQL `db-f1-micro` (10 GB SSD, single-AZ) | ~$7.67 |
| Cloud SQL automated backups (7 retained × ~10 GB) | ~$1.00 |
| GCS Standard (< 1 GB combined) | ~$0.02 |
| GCS Nearline (lifecycle, minimal) | ~$0.00 |
| IAM, bucket metadata | $0.00 |
| **Recipe 2 subtotal** | **~$8.70/mo** |
| **Cumulative (Recipe 1 + 2)** | **~$9.20/mo** |

Cloud SQL dominates the bill. At Tier A dev traffic, the always-free GCS tier covers bucket operations. The cumulative cost remains well under the ~$12–15/mo target.
