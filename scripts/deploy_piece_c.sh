#!/usr/bin/env bash
# =============================================================================
# deploy_piece_c.sh — materialize DATABASE_URL + apply the thread migration +
# deploy a NO-TRAFFIC tagged Cloud Run revision with memory recall/store ON
# (auto-capture stays in SHADOW). Prod URL stays byte-identical until you
# promote the tag.
#
# WHAT THIS DOES (and what it deliberately does NOT):
#   1. tofu apply under infra/dev-tier/ → adopts the existing Neon project,
#      synthesizes the connection string, lands it in Secret Manager as
#      `neon-database-url`, enables pgvector.  (control plane → data plane)
#   2. Pulls DATABASE_URL back from Secret Manager (never printed to a log).
#   3. Applies the hand-authored thread-table migration via psql.
#   4. Deploys a `--tag mem --no-traffic` revision of `agent-middleware` with
#      MEMORY_ENABLED=true (recall+store ON) and MEMORY_AUTOCAPTURE_ENABLED
#      left at its default false (shadow — write-back still gated on the
#      Phase-2 eval). Prod traffic is untouched.
#   5. Smoke-checks the tagged revision.
#
#   It does NOT: serve traffic from the new revision, enable auto-capture
#   write-back, touch prod, or wire DATABASE_URL into the BFF (see §BFF below).
#
# PREREQUISITES (you, once):
#   - opentofu, gcloud, psql installed; `brew install opentofu libpq` (+ link).
#   - .env has: NEON_API_KEY / TF_VAR_neon_api_key, NEON_DATABASE_NAME,
#     MEM0_API_KEY, and the other tfvars seeds (see terraform.tfvars.example).
#   - gcloud auth + a tofu-deployer SA key (README §account-setup).
#   - The GCS state bucket exists (README §state-bucket).
#
# RUN:  bash scripts/deploy_piece_c.sh
# Idempotent: re-runs are safe (tofu converges; CREATE TABLE IF NOT EXISTS;
# the tag is reused).
# =============================================================================
set -euo pipefail

# --- config (override via env) ----------------------------------------------
: "${GCP_PROJECT_ID:?set GCP_PROJECT_ID (e.g. agent-prod-gcp-dev-xxxx)}"
: "${GCP_REGION:=us-central1}"
SERVICE="${SERVICE:-agent-middleware}"
TAG="${TAG:-mem}"
NEON_SECRET="${NEON_SECRET:-neon-database-url}"
MIGRATION="frontend/lib/adapters/thread_store/db/migrations/0000_init_threads.sql"
INFRA_DIR="infra/dev-tier"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Project=$GCP_PROJECT_ID Region=$GCP_REGION Service=$SERVICE Tag=$TAG"

# --- 1. Terraform: adopt Neon + synthesize DATABASE_URL into Secret Manager --
# The MEMORY_ENABLED env var is added to the Cloud Run env block in
# cloud-run.tf by the companion config patch (see DEPLOY_PIECE_C.md §1); if you
# instead set it via gcloud below, you can skip touching the TF env block.
echo "==> [1/5] tofu init + plan + apply (infra/dev-tier)"
( cd "$INFRA_DIR"
  tofu init -backend-config="bucket=${GCP_PROJECT_ID}-tofu-state"
  tofu plan -out=tfplan
  # Apply-time deep-TDD checks (BDD policy) before mutating cloud state.
  tofu show -json tfplan > tfplan.json
  terraform-compliance -p tfplan.json -f features/ || {
    echo "!! terraform-compliance failed — aborting before apply"; exit 1; }
  tofu apply tfplan
)

# --- 2. Pull DATABASE_URL from Secret Manager (no echo of the value) --------
echo "==> [2/5] Resolving DATABASE_URL from Secret Manager ($NEON_SECRET)"
DATABASE_URL="$(gcloud secrets versions access latest \
  --secret="$NEON_SECRET" --project="$GCP_PROJECT_ID")"
if [ -z "$DATABASE_URL" ]; then
  echo "!! empty DATABASE_URL from $NEON_SECRET — did tofu apply create it?"; exit 1
fi
echo "    got DATABASE_URL (len=${#DATABASE_URL}, host=$(echo "$DATABASE_URL" | sed -E 's|.*@([^/]+)/.*|\1|'))"

# --- 3. Apply the thread-table migration ------------------------------------
echo "==> [3/5] Applying thread migration: $MIGRATION"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$MIGRATION"
echo "    migration applied (idempotent: threads + index + thread_messages)"
psql "$DATABASE_URL" -c "\dt threads" -c "\dt thread_messages"

# --- 4. Deploy a NO-TRAFFIC tagged revision with MEMORY_ENABLED=true --------
# IMPORTANT: --no-traffic + --tag means the prod URL keeps serving the current
# revision. You reach the new one only via the tag URL printed below.
# Auto-capture is intentionally NOT enabled (shadow stays on).
echo "==> [4/5] Deploying $SERVICE revision (tag=$TAG, NO traffic)"
gcloud run deploy "$SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --tag="$TAG" --no-traffic \
  --update-secrets="DATABASE_URL=${NEON_SECRET}:latest,MEM0_API_KEY=mem0-api-key:latest" \
  --update-env-vars="MEMORY_ENABLED=true" \
  --quiet

TAG_URL="$(gcloud run services describe "$SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --format='value(status.traffic)' | tr ';' '\n' | grep -i "$TAG" || true)"
TAG_URL="$(gcloud run revisions list --service="$SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --format='value(metadata.name)' --limit=1)"

# --- 5. Smoke-check the tagged revision -------------------------------------
echo "==> [5/5] Smoke-checking the tagged revision"
BASE="$(gcloud run services describe "$SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --format='value(status.url)')"
# Tagged URL form: https://<tag>---<service>-<hash>.<region>.run.app
TAGGED="$(gcloud run services describe "$SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --format="value(status.traffic.url)" | tr ';' '\n' | grep -i "$TAG" | head -1 || true)"
echo "    prod URL (unchanged): $BASE"
echo "    tagged URL:          ${TAGGED:-<inspect: gcloud run services describe $SERVICE>}"
if [ -n "${TAGGED:-}" ]; then
  echo "    GET ${TAGGED}/healthz:"
  curl -fsS "${TAGGED}/healthz" || echo "    (healthz non-200 — check logs)"
fi

cat <<EOF

==> DONE (Piece C, no-traffic).
    - DATABASE_URL is in Secret Manager + mapped on the tagged revision.
    - threads table migrated.
    - MEMORY_ENABLED=true on the tag ONLY (prod untouched, autocapture shadow).

NEXT (manual, your call):
  * Verify selection in logs of the tagged revision:
      gcloud run services logs read $SERVICE --project=$GCP_PROJECT_ID \\
        --region=$GCP_REGION | grep "memory backend"
      # expect: memory backend: mem0 (durable)
  * Exercise via the tagged URL (bearer auth), then promote when satisfied:
      gcloud run services update-traffic $SERVICE --to-tags=$TAG=100 \\
        --project=$GCP_PROJECT_ID --region=$GCP_REGION
  * BFF (Cloudflare Pages) ALSO needs DATABASE_URL for NeonThreadRepo —
    see DEPLOY_PIECE_C.md §BFF (it is a SEPARATE secret-binding, not this script).
EOF
