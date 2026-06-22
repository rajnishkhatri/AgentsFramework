---
type: runbook
title: Replace mem0 with pgvector — Phase 5 cutover runbook
description: Step-by-step S1–S6 procedure for the live Cloud SQL migration, no-traffic Cloud Run revision, traffic shift, 24h soak, and mem0 retirement.
tags: [runbook, memory, pgvector, cloud-sql, cloud-run, cutover]
timestamp: 2026-06-22
status: ready
plan_id: replace-mem0-pgvector
related:
  plan: "[replace_mem0_pgvector.plan.md](replace_mem0_pgvector.plan.md)"
  precedent: "[[bff-threads-cloudsql-driver-gap]]"
---

# Phase 5 cutover runbook

> **This is the irreversible step of the mem0→pgvector swap.** Phase 4.5 EXIT gate is clear (640 passed / 0 fail). The pre-deploy pytest gate at S5 was rerun green on 2026-06-22. Below is the exact command sequence the operator runs against live Cloud SQL + Cloud Run. The agent does NOT execute any of these — they touch shared prod infra and require human authorization per the agent execution contract.

## S1 — Apply the SQL migration to Cloud SQL

The migration file lives at:

  [services/memory_backends/migrations/0000_init_agent_memories.sql](../../services/memory_backends/migrations/0000_init_agent_memories.sql)

It is **byte-equivalent** to the Phase 4.5 typed-memory superset DDL constant in [services/memory_backends/pgvector.py:104](../../services/memory_backends/pgvector.py:104) after the `{dim}` placeholder is substituted with `1536` (the default `EMBEDDING_DIMENSION` for `text-embedding-3-small`). Parity verified by the agent on 2026-06-22 (7 statements, byte-equal after whitespace normalization).

### Pre-conditions

- `cloud-sql-proxy` binary installed and authenticated (`gcloud auth application-default login`).
- The Cloud SQL **instance connection name** is the same one BFF threads use today — see [[bff-threads-cloudsql-driver-gap]]. Format: `<PROJECT>:<REGION>:<INSTANCE>`.
- `DATABASE_URL` secret in Secret Manager (`projects/<PROJECT>/secrets/database_url`) is the dsn for the same instance. Use `gcloud secrets versions access latest --secret=database_url` to read the user/password/db.

### Commands

```bash
# Terminal 1 — open the proxy (leave running)
cloud-sql-proxy --port 5433 <PROJECT>:<REGION>:<INSTANCE>

# Terminal 2 — apply the migration
DSN="postgresql://<USER>:<PASS>@127.0.0.1:5433/<DB>"
psql "$DSN" -f services/memory_backends/migrations/0000_init_agent_memories.sql
```

### Verification (paste output into PR)

```bash
psql "$DSN" -c "\d agent_memories"
```

Expected output MUST show:

- Columns (10): `id`, `user_id`, `key`, `mem_type`, `payload`, `metadata`, `embed_text`, `embedding`, `created_at`, `ts`
- `mem_type` column with default `'semantic'::text`
- `ts` column as `tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, COALESCE(payload->>'text'::text, ''::text))) STORED`
- 6 indexes:
  1. `agent_memories_pkey` (PRIMARY KEY, btree, `id`)
  2. `agent_memories_user_id_key_key` (UNIQUE, btree, `(user_id, key)`)
  3. `agent_memories_user_idx` (btree, `user_id`)
  4. `agent_memories_user_type_idx` (btree, `(user_id, mem_type)`)
  5. `agent_memories_hnsw_idx` (hnsw, `embedding vector_cosine_ops`)
  6. `agent_memories_ts_idx` (gin, `ts`)

If anything is missing, do NOT proceed to S2 — re-run the apply or inspect for partial errors.

## S2 — Deploy a no-traffic Cloud Run revision

Goal: ship the keyless build (`memory_backend=pgvector` + no `MEM0_API_KEY` reference) to a no-traffic tag for smoke testing without affecting live traffic.

### Terraform delta (apply before deploy)

The required infra deltas are documented in the §S4 section below. **Apply Terraform FIRST** so the revision Cloud Run actually deploys carries the new env wiring.

### Deploy command

```bash
# Build + push image (mirrors existing deploy-gcp pattern)
gcloud builds submit --tag gcr.io/<PROJECT>/agent-backend-combined:phase5 .

# No-traffic revision with the pgvector tag
gcloud run deploy agent-backend-combined \
  --image gcr.io/<PROJECT>/agent-backend-combined:phase5 \
  --region <REGION> \
  --tag pgvector \
  --no-traffic \
  --update-env-vars MEMORY_BACKEND=pgvector,EMBEDDING_MODEL=text-embedding-3-small,EMBEDDING_DIMENSION=1536 \
  --remove-env-vars MEM0_BASE_URL
```

> **Why `--remove-env-vars MEM0_BASE_URL` only**: `MEM0_API_KEY` is bound via `value_source.secret_key_ref` (not `value`), so it cannot be dropped from a `gcloud run deploy` CLI alone — Terraform must drop it as a configured env. The Terraform delta in §S4 removes both. Until Terraform applies, the keyless build silently ignores `MEM0_API_KEY` because composition selects backend via `MEMORY_BACKEND=pgvector` (see [middleware/composition.py:862](../../middleware/composition.py:862)).

### Verification (paste into PR)

```bash
# 1) Revision is healthy
gcloud run services describe agent-backend-combined --region <REGION> \
  --format="value(status.traffic)" | head

# 2) Hit the tagged URL (no traffic yet — uses the `--tag pgvector` host)
REV_URL="$(gcloud run services describe agent-backend-combined --region <REGION> \
  --format='value(status.traffic[?tag=`pgvector`].url)')"
curl -sf "$REV_URL/health" | jq .runtime  # expect "langgraph"
```

## S3 — Smoke run + stress E2E against the no-traffic revision

Per plan §Phase 5 gate:

1. Run the [[memory-multisession-e2e-corpus]] suite pointed at the tagged URL.
   - First task per user MUST emit `MEMORY_RECALLED count=0` (empty pgvector at cutover, per user decision).
   - By the 3rd task per user, `MEMORY_RECALLED count > 0` (recall picks up the prior `MEMORY_STORED` rows).
2. Confirm the carrier-gate audit ([[governance-carrier-gate-phase1]]) is GREEN — `MEMORY_RECALLED` and `MEMORY_STORED` carriers present in trace.
3. Confirm zero cross-user bleed: pick two distinct `user_id`s from the trace, query `agent_memories` directly, assert disjoint row sets.

If any of (1–3) fail: hold S4. Roll back the no-traffic revision and re-investigate.

## S4 — Terraform deltas (drop MEM0_* env vars, add MEMORY_BACKEND wiring)

Apply these BEFORE S2's `gcloud run deploy`. They land in two tiers — dev + prod — and have identical shape.

### `infra/dev-tier/cloud-run.tf` and `infra/gcp/cloud-run-backend.tf`

Remove these blocks:

```hcl
# DELETE
env {
  name  = "MEM0_BASE_URL"
  value = "https://api.mem0.ai"
}

# DELETE
env {
  name = "MEM0_API_KEY"
  value_source {
    secret_key_ref {
      secret  = google_secret_manager_secret.mem0_api_key.secret_id
      version = "latest"
    }
  }
}
```

Add these three plain-text env blocks (alongside `MEMORY_ENABLED`):

```hcl
env {
  name  = "MEMORY_BACKEND"
  value = "pgvector"
}

env {
  name  = "EMBEDDING_MODEL"
  value = "text-embedding-3-small"
}

env {
  name  = "EMBEDDING_DIMENSION"
  value = "1536"
}
```

Remove the depends_on line referring to `mem0_api_key_accessor`:

```hcl
depends_on = [
  google_secret_manager_secret_iam_member.workos_api_key_accessor,
  google_secret_manager_secret_iam_member.openai_api_key_accessor,
  google_secret_manager_secret_iam_member.anthropic_api_key_accessor,
  google_secret_manager_secret_iam_member.langfuse_public_key_accessor,
  google_secret_manager_secret_iam_member.langfuse_secret_key_accessor,
  # DELETE: google_secret_manager_secret_iam_member.mem0_api_key_accessor,
  google_secret_manager_secret_iam_member.neon_database_url_accessor,
]
```

> **DO NOT delete the `mem0-api-key` Secret Manager resource yet.** Per the 24h-rollback rule, the secret stays live so a prior revision (still wired to it) remains rollback-capable. Phase 5 S6 deletes the secret + secret-manager.tf block + variables.tf entry + outputs.tf reference AFTER the soak.

### `infra/dev-tier/terraform.tfvars.example` and `infra/gcp/terraform.tfvars*`

```diff
- mem0_api_key        = "m0-REPLACE_ME"
```

(Same line in `infra/gcp/terraform.tfvars` if present.) **Do not commit this delete to `terraform.tfvars` proper until S6** — the 24h-rollback path needs the variable wired through. Only update the `.example` template now.

### Verification

```bash
cd infra/gcp && tofu plan -out=phase5.plan
tofu show phase5.plan | grep -E "MEM0_|MEMORY_BACKEND|EMBEDDING_"
```

Plan output MUST show:

- `MEM0_BASE_URL` env removed
- `MEM0_API_KEY` env removed
- `MEMORY_BACKEND=pgvector` env added
- `EMBEDDING_MODEL=text-embedding-3-small` env added
- `EMBEDDING_DIMENSION=1536` env added
- `mem0_api_key` secret resource UNCHANGED (kept for 24h-rollback)

## S5 — Shift traffic to the pgvector revision

After S3 smoke is green:

```bash
gcloud run services update-traffic agent-backend-combined \
  --region <REGION> \
  --to-tags pgvector=100
```

Watch for:

- `EventType.MEMORY_RECALLED` carrier present in every recall path of every trace (was the bug from [[mem-tag-run-emitted-no-carriers]] — now must be back).
- `MEMORY_STORED` count grows with task completion rate.
- p95 latency on the recall seam ≤ 500ms (one embed + one HNSW query).

**24h soak begins now.** Keep `mem0_api_key` secret live. Do NOT proceed to S6 until 24 hours have elapsed AND no rollback events occurred.

## S6 — mem0 retirement (post-soak only)

After 24h of stable pgvector traffic:

### Code deletions

- `services/memory_backends/mem0.py` — delete file
- `tests/services/memory_backends/test_mem0_backend.py` — delete (`_FakeMem0Sdk` goes with it)
- `pyproject.toml` — drop the `"mem0ai>=2.0,<3"` line (line 28)

### Infra deletions

- `infra/dev-tier/secret-manager.tf` lines 177–199: `mem0_api_key` secret + version + accessor IAM
- `infra/dev-tier/variables.tf:178` — `variable "mem0_api_key" { ... }` block
- `infra/dev-tier/outputs.tf:57` — `mem0_api_key` field on the secrets output map
- `infra/gcp/secret-manager.tf` lines 195–212 (and below — full mem0 block)
- `infra/gcp/outputs.tf:48` — same field on prod outputs map
- `infra/RUNBOOK.md` lines 132–133, 309 — drop the mem0-renewal procedure rows

### Docs cleanup

- `infra/dev-tier/README.md:33` — drop mem0 from the secret-manager rotation list
- `infra/dev-tier/README.md:115` — drop `MEM0_API_KEY` from the sprint-0/1 reuse list

### Verification

```bash
grep -r "mem0\|mem0ai" --include="*.py" --include="*.toml" --include="*.tf" --include="*.md"
```

MUST return zero matches.

```bash
.venv/bin/python -m pytest tests/architecture/ -q
```

The new "no mem0 imports anywhere" architecture assertion (Phase 5 S6 commit) MUST pass.

## Rollback procedure (24h window)

If anything regresses between S5 and S6:

```bash
# Identify the prior known-good revision
gcloud run revisions list --service agent-backend-combined --region <REGION>

# Shift 100% traffic back
gcloud run services update-traffic agent-backend-combined \
  --region <REGION> \
  --to-revisions <PRIOR_REVISION>=100
```

Because `MEM0_API_KEY` is still live in Secret Manager and the prior revision was deployed wired to it, recall + store route through mem0 again with zero data loss (mem0 cloud retained the rows). The agent_memories table on Cloud SQL keeps the new rows; they become read-only until a subsequent forward roll.

## Post-Phase-5 (housekeeping, in the soak-completion commit)

- Append `2026-MM-DD — replace-mem0-pgvector phase 5 done` to [docs/plans/log.md](log.md)
- Update [docs/plans/index.md](index.md) front-matter status if shipped
- Author a memory under `~/.claude/projects/.../memory/` summarizing what was *non-obvious* about the cutover (per the auto-memory rules — only surprises)
