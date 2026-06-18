#!/usr/bin/env bash
# =============================================================================
# deploy_piece_c.sh — materialize DATABASE_URL + apply the thread migration +
# deploy a NO-TRAFFIC tagged Cloud Run revision with memory recall/store ON
# (auto-capture stays in SHADOW). Prod URL stays byte-identical until you
# promote the tag.
#
# WHAT THIS DOES (and what it deliberately does NOT):
#   1. (No Terraform apply.) The prod backend's DATABASE_URL secret
#      (`database-url`, a CLOUD SQL connection) is already provisioned by
#      infra/gcp — there is nothing to synthesize. (The old version ran
#      infra/dev-tier tofu apply, which writes a NEON string into a DIFFERENT
#      secret the service never reads — removed; see DB_SECRET note below.)
#   2. Pulls DATABASE_URL back from Secret Manager ($DB_SECRET, never printed).
#   3. Applies the hand-authored thread-table migration via psql (skipped with
#      guidance if DATABASE_URL is a Cloud SQL /cloudsql/ socket — needs the
#      Cloud SQL Auth Proxy).
#   4. Deploys a `--tag mem --no-traffic` revision of `agent-backend-combined`
#      with MEMORY_ENABLED=true (recall+store ON) and MEMORY_AUTOCAPTURE_ENABLED
#      left at its default false (shadow — write-back still gated on the
#      Phase-2 eval). Prod traffic is untouched.
#   5. Smoke-checks the tagged revision (asserts the agent health body).
#
#   It does NOT: serve traffic from the new revision, enable auto-capture
#   write-back, touch prod, sync the Neon↔Cloud-SQL secrets, or wire
#   DATABASE_URL into the BFF (see §BFF in DEPLOY_PIECE_C.md).
#
# PREREQUISITES (you, once):
#   - gcloud + psql installed (`brew install libpq` + link for psql).
#   - gcloud auth with access to Secret Manager + Cloud Run on the project.
#   - For the migration against prod Cloud SQL: the Cloud SQL Auth Proxy
#     (`cloud-sql-proxy`) — the prod DATABASE_URL is a /cloudsql/ unix socket
#     psql can't open directly (the script detects this and prints the proxy
#     command). Not needed for a TCP DSN (e.g. a dev-tier/Neon DB_SECRET).
#   - MIDDLEWARE_IMAGE points at a *real* pushed agent image (NOT the bootstrap
#     `hello` placeholder). Build + push first the SAME way deploy_gcp.sh does
#     (docker build -f Dockerfile.backend + docker push — NOT `gcloud builds
#     submit`, which has no -f flag), e.g.:
#       IMG="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/agent-backend/agent-backend:$(git rev-parse --short HEAD)"
#       docker build --platform linux/amd64 -f Dockerfile.backend -t "$IMG" .
#       docker push "$IMG"
#       export MIDDLEWARE_IMAGE="$IMG"
#     A `gcloud run deploy` WITHOUT --image re-deploys whatever image the service
#     currently has (a no-op for the agent if that's a placeholder), so this
#     script REQUIRES MIDDLEWARE_IMAGE and passes it through (see step 4).
#
# RUN:  MIDDLEWARE_IMAGE=<pushed-uri> bash scripts/deploy_piece_c.sh
# Idempotent: re-runs are safe (CREATE TABLE IF NOT EXISTS; the tag is reused).
# =============================================================================
set -euo pipefail

# --- config (override via env) ----------------------------------------------
: "${GCP_PROJECT_ID:?set GCP_PROJECT_ID (e.g. agent-prod-gcp-dev-xxxx)}"
: "${GCP_REGION:=us-central1}"
# MIDDLEWARE_IMAGE is REQUIRED: a real pushed agent image. Without --image,
# gcloud run deploy re-deploys the current (placeholder) image — a no-op for the
# agent. Guard against the `hello` placeholder explicitly.
: "${MIDDLEWARE_IMAGE:?set MIDDLEWARE_IMAGE to a pushed agent image (NOT the hello placeholder); see header for the build+push command}"
case "$MIDDLEWARE_IMAGE" in
  *cloudrun/container/hello*)
    echo "!! MIDDLEWARE_IMAGE is the Cloud Run 'hello' placeholder — build + push the agent image first (see script header)."; exit 1 ;;
esac
# SERVICE: the REAL prod agent backend is `agent-backend-combined` (the BFF's
# MIDDLEWARE_URL points at it; all e2e/stress target it). `agent-middleware` is
# an orphaned V3-dev-tier service on the `hello` placeholder — do NOT deploy to
# it. Override only if your topology differs.
SERVICE="${SERVICE:-agent-backend-combined}"
TAG="${TAG:-mem}"
# DB_SECRET: the SAME Secret Manager secret the deployed service reads as
# DATABASE_URL. On prod (infra/gcp) that is `database-url` — a CLOUD SQL Postgres
# connection (unix socket /cloudsql/PROJECT:REGION:agent-db), NOT Neon. The
# `neon-database-url` secret belongs to the abandoned infra/dev-tier (Neon) stack
# and the running backend NEVER reads it — do NOT sync neon→database-url, that
# would repoint the live service onto a different, empty DB. Migrate the SAME
# secret the runtime opens. (Var name was NEON_SECRET; renamed to avoid the
# Neon implication. NEON_SECRET still honored as a fallback for old callers.)
DB_SECRET="${DB_SECRET:-${NEON_SECRET:-database-url}}"
MIGRATION="frontend/lib/adapters/thread_store/db/migrations/0000_init_threads.sql"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Project=$GCP_PROJECT_ID Region=$GCP_REGION Service=$SERVICE Tag=$TAG"

# --- 1. (Terraform apply removed) -------------------------------------------
# The prod backend's DATABASE_URL (`database-url`) is provisioned by infra/gcp
# from the Cloud SQL instance and already exists; there is nothing to synthesize
# here. The old step ran `infra/dev-tier` tofu apply, which synthesizes a NEON
# string into `neon-database-url` — a DIFFERENT database the service doesn't use.
# That mismatch (migrate Neon, run against Cloud SQL) is exactly why this step
# was removed. If you genuinely intend a dev-tier/Neon deploy, set
# DB_SECRET=neon-database-url and run that stack's apply yourself, deliberately.
echo "==> [1/5] (skipping Terraform apply — DATABASE_URL already provisioned by infra/gcp)"

# --- 2. Pull DATABASE_URL from Secret Manager (no echo of the value) --------
echo "==> [2/5] Resolving DATABASE_URL from Secret Manager ($DB_SECRET)"
DATABASE_URL="$(gcloud secrets versions access latest \
  --secret="$DB_SECRET" --project="$GCP_PROJECT_ID")"
if [ -z "$DATABASE_URL" ]; then
  echo "!! empty DATABASE_URL from $DB_SECRET"; exit 1
fi
# PSQL_CONN is the connection string the migration step actually uses. By default
# it's DATABASE_URL verbatim; for a Cloud SQL socket DSN it's REWRITTEN to point at
# the local proxy socket (see below) — because `psql "$DATABASE_URL"` would use the
# DSN's own host=/cloudsql/... and a workstation PGHOST env var would NOT override it.
PSQL_CONN="$DATABASE_URL"

# Detect a Cloud SQL unix-socket DSN (host=/cloudsql/...): psql cannot open that
# directly from a workstation — it needs the Cloud SQL Auth Proxy. Fail loudly
# with the fix rather than emit a confusing connection error.
case "$DATABASE_URL" in
  *"/cloudsql/"*)
    INSTANCE="$(printf '%s' "$DATABASE_URL" | sed -E 's|.*host=/cloudsql/([^&?]+).*|\1|')"
    echo "    DATABASE_URL is a CLOUD SQL socket DSN (instance=$INSTANCE)."
    if [ -z "${CLOUDSQL_PROXY_RUNNING:-}" ]; then
      cat <<EOF
!! psql can't open a /cloudsql/ unix socket directly. Start the Cloud SQL Auth
   Proxy first, then re-run with CLOUDSQL_PROXY_RUNNING=1 (and PROXY_SOCKET_DIR if
   you didn't use /tmp/cloudsql), e.g.:
     cloud-sql-proxy --unix-socket /tmp/cloudsql "$INSTANCE" &
     CLOUDSQL_PROXY_RUNNING=1 bash scripts/deploy_piece_c.sh
   (Or run the migration as a one-off Cloud Run / Cloud SQL Studio job.)
   Skipping the local migration step; the deploy (steps 4-5) still proceeds.
EOF
      SKIP_MIGRATION=1
    else
      # Proxy IS running: rebuild a connection that targets the PROXY socket dir
      # instead of /cloudsql/. We carry over user/password/dbname parsed from the
      # original DSN and swap only the host. (libpq reads the socket dir as host.)
      PROXY_SOCKET_DIR="${PROXY_SOCKET_DIR:-/tmp/cloudsql}"
      DB_USER="$(printf '%s' "$DATABASE_URL" | sed -E 's|^[a-z]+://([^:/@]+).*|\1|')"
      DB_NAME="$(printf '%s' "$DATABASE_URL" | sed -E 's|^[a-z]+://[^/]+/([^?]+).*|\1|')"
      # Password is optional. Extract it only when the authority is user:pass@…
      # (portable — BSD/macOS sed has no `t` branch label). Strip scheme first,
      # then take everything between the first ':' and the '@'.
      DB_PASS=""
      _AUTH="${DATABASE_URL#*://}"; _AUTH="${_AUTH%%@*}"
      case "$_AUTH" in
        *:*) DB_PASS="${_AUTH#*:}" ;;
      esac
      # keyword/value conninfo → host is the proxy's per-instance socket dir.
      PSQL_CONN="host=${PROXY_SOCKET_DIR}/${INSTANCE} dbname=${DB_NAME} user=${DB_USER}"
      # NOTE: DB_PASS is taken verbatim from the DSN authority. If the secret's
      # password is URL-encoded (e.g. %21 for '!'), set PGPASSWORD yourself to the
      # DECODED value before running, or use the documented one-off conninfo in
      # DEPLOY_PIECE_C.md §3 — this script does not URL-decode.
      [ -n "$DB_PASS" ] && export PGPASSWORD="$DB_PASS"
      echo "    proxy running → migrating via ${PROXY_SOCKET_DIR}/${INSTANCE} (db=$DB_NAME user=$DB_USER)"
    fi
    ;;
  *)
    echo "    got DATABASE_URL (len=${#DATABASE_URL}, host=$(echo "$DATABASE_URL" | sed -E 's|.*@([^/]+)/.*|\1|'))"
    ;;
esac

# --- 3. Apply the thread-table migration ------------------------------------
if [ -n "${SKIP_MIGRATION:-}" ]; then
  echo "==> [3/5] migration SKIPPED (see Cloud SQL proxy note above)"
else
  echo "==> [3/5] Applying thread migration: $MIGRATION"
  psql "$PSQL_CONN" -v ON_ERROR_STOP=1 -f "$MIGRATION"
  echo "    migration applied (idempotent: threads + index + thread_messages)"
  psql "$PSQL_CONN" -c "\dt threads" -c "\dt thread_messages"
fi

# --- 4. Deploy a NO-TRAFFIC tagged revision with MEMORY_ENABLED=true --------
# IMPORTANT: --no-traffic + --tag means the prod URL keeps serving the current
# revision. You reach the new one only via the tag URL printed below.
# Auto-capture is intentionally NOT enabled (shadow stays on).
echo "==> [4/5] Deploying $SERVICE revision (tag=$TAG, NO traffic)"
echo "    image: $MIDDLEWARE_IMAGE"
# DATABASE_URL is already mapped on the prod service by infra/gcp; we pass it
# with $DB_SECRET so the tagged revision reads the SAME DB we migrated. (If you
# overrode DB_SECRET to a dev-tier/Neon secret, this correctly points the new
# revision there too — a deliberate, single-DB choice, not a silent mismatch.)
gcloud run deploy "$SERVICE" \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --image="$MIDDLEWARE_IMAGE" \
  --tag="$TAG" --no-traffic \
  --update-secrets="DATABASE_URL=${DB_SECRET}:latest,MEM0_API_KEY=mem0-api-key:latest" \
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
  # Probe /health FIRST: on agent-backend-combined the externally-routed health
  # endpoint is /health (returns {"runtime":"langgraph",...}); /healthz currently
  # 404s through the external router (routing discrepancy — fix separately). Fall
  # back to /healthz so this still works on services where only that is exposed.
  HEALTH=""; HEALTH_PATH=""
  for p in /health /healthz; do
    if HEALTH="$(curl -fsS "${TAGGED}${p}" 2>/dev/null)" && [ -n "$HEALTH" ]; then
      HEALTH_PATH="$p"; break
    fi
  done
  echo "    GET ${TAGGED}${HEALTH_PATH:-/health}:"
  echo "    $HEALTH"
  # The Cloud Run 'hello' placeholder ALSO answers health with 200 (plain text).
  # Assert the AGENT's health body so a placeholder deploy fails loudly instead
  # of looking green (see app_prod.py health: {"runtime":"langgraph",...}).
  case "$HEALTH" in
    *'"runtime":"langgraph"'*|*'"runtime": "langgraph"'*)
      echo "    ✓ agent health signature present (runtime=langgraph)" ;;
    *)
      echo "!! neither /health nor /healthz returned the agent body — the revision"
      echo "   is likely running the placeholder image, not the agent. Check"
      echo "   MIDDLEWARE_IMAGE and the boot log ('Hello from Cloud Run' == placeholder)."
      echo "   (If both 404, also check external routing — /healthz is known to 404"
      echo "    through the router on agent-backend-combined; /health is the live one.)"
      exit 1 ;;
  esac
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
  * BFF sidebar persistence is NOT handled by this script — it's a separate
    follow-up. As of 2026-06-18 the option-B pg adapter is code complete, so
    binding DATABASE_URL on agent-frontend is now SAFE (a /cloudsql/ DSN routes
    to pg, not the Neon driver). Procedure (rebuild frontend image w/ pg, grant
    the frontend SA cloudsql.client + database-url accessor, then the bind +
    --add-cloudsql-instances) is in DEPLOY_PIECE_C.md §BFF.
    Plan / Terraform-durable form: docs/plans/bff_cloudsql_thread_repo.plan.md.
EOF
