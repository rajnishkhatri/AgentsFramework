#!/usr/bin/env bash
# scripts/deploy_gcp.sh — Deploy-only orchestrator for GCP Tier A.
#
# Wraps existing Recipe 0-7 deployment commands into deterministic phases.
# This script intentionally stops at human gates (DB migration + WorkOS redirect).
#
# Usage:
#   ./scripts/deploy_gcp.sh <phase>
#
# Phases:
#   preflight | foundations | data | secrets | images | backend | frontend
#   workos | observability | smoke | all | preview
#
# Environment flags:
#   DRY_RUN=1            Print commands without applying mutations
#   AUTO_APPROVE=1       Skip interactive confirmation before tofu apply
#   VERSION=v1           Image tag used in images phase (default: DEPLOY_VERSION)
#   WRITE_TFVARS=1       Update infra/gcp/terraform.tfvars with pinned image digests
#   BASE_REF=origin/main Base ref for change detection (preview phase)
#   DEPLOY_VERSION=      CalVer version (default: YYYY.0M.0); used in image tags + DEPLOY_ID
#   ENV=prod             Environment name embedded in DEPLOY_ID

set -euo pipefail
IFS=$'\n\t'

PHASE="${1:-}"
DRY_RUN="${DRY_RUN:-}"
AUTO_APPROVE="${AUTO_APPROVE:-}"
VERSION="${VERSION:-}"
WRITE_TFVARS="${WRITE_TFVARS:-}"
BASE_REF="${BASE_REF:-origin/main}"
DEPLOY_VERSION="${DEPLOY_VERSION:-}"
ENV="${ENV:-prod}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra/gcp"
TFVARS="${INFRA_DIR}/terraform.tfvars"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}INFO${NC}: $*"; }
pass() { echo -e "${GREEN}PASS${NC}: $*"; }
warn() { echo -e "${YELLOW}WARN${NC}: $*"; }
fail() { echo -e "${RED}FAIL${NC}: $*"; exit 1; }

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy_gcp.sh <phase>

Phases:
  preflight | foundations | data | secrets | images | backend | frontend
  workos | observability | smoke | all | preview

Flags:
  DRY_RUN=1            Print commands only
  AUTO_APPROVE=1       Skip apply confirmation prompts
  VERSION=vX           Docker image tag (default: DEPLOY_VERSION)
  WRITE_TFVARS=1       Write digest-pinned image refs to terraform.tfvars
  BASE_REF=origin/main Base ref for change detection (preview phase)
  DEPLOY_VERSION=      CalVer version (default: YYYY.0M.0)
  ENV=prod             Environment name in DEPLOY_ID
EOF
}

run_cmd() {
  local printable
  printable="$(printf '%q ' "$@")"
  echo "+ ${printable% }"
  if [[ -z "${DRY_RUN}" ]]; then
    "$@"
  fi
}

run_source() {
  local script_path="$1"
  echo "+ source \"${script_path}\""
  if [[ -z "${DRY_RUN}" ]]; then
    # shellcheck source=/dev/null
    source "${script_path}"
  fi
}

run_in_infra() {
  local printable
  printable="$(printf '%q ' "$@")"
  echo "+ (cd \"${INFRA_DIR}\" && ${printable% })"
  if [[ -z "${DRY_RUN}" ]]; then
    (
      cd "${INFRA_DIR}"
      "$@"
    )
  fi
}

run_in_infra_to_file() {
  local outfile="$1"
  shift
  local printable
  printable="$(printf '%q ' "$@")"
  echo "+ (cd \"${INFRA_DIR}\" && ${printable% } > ${outfile})"
  if [[ -z "${DRY_RUN}" ]]; then
    (
      cd "${INFRA_DIR}"
      "$@" > "${outfile}"
    )
  fi
}

tfvars_value() {
  local key="$1"
  grep -E "^[[:space:]]*${key}[[:space:]]*=" "${TFVARS}" 2>/dev/null \
    | sed -E 's/^[^=]*=[[:space:]]*"([^"]*)".*/\1/' \
    | head -1
}

require_paths() {
  [[ -d "${INFRA_DIR}" ]] || fail "Missing infra dir: ${INFRA_DIR}"
  [[ -f "${TFVARS}" ]] || fail "Missing ${TFVARS}. Create it from terraform.tfvars.example first."
}

load_env_from_tfvars() {
  export PROJECT="${PROJECT:-$(tfvars_value gcp_project_id)}"
  export REGION="${REGION:-$(tfvars_value gcp_region)}"
  [[ -n "${PROJECT:-}" ]] || fail "gcp_project_id is not set in ${TFVARS}"
  [[ -n "${REGION:-}" ]] || export REGION="us-central1"
}

require_cmds() {
  local cmds=("$@")
  local cmd
  for cmd in "${cmds[@]}"; do
    command -v "${cmd}" >/dev/null 2>&1 || fail "Required command not found: ${cmd}"
  done
}

CANONICAL_PHASES=(preflight foundations data secrets images backend frontend workos observability smoke)

declare -a CHANGED_FILES=()
declare -a AFFECTED_PHASES=()
REBUILD_BACKEND=""
REBUILD_FRONTEND=""

detect_changes() {
  local base_sha
  if ! base_sha="$(git rev-parse --verify "${BASE_REF}" 2>/dev/null)"; then
    warn "BASE_REF '${BASE_REF}' not found locally; fetching origin/main..."
    git fetch origin main 2>/dev/null || true
    if ! base_sha="$(git rev-parse --verify "${BASE_REF}" 2>/dev/null)"; then
      warn "Could not resolve ${BASE_REF} — treating all phases as affected (fail-safe)."
      AFFECTED_PHASES=("${CANONICAL_PHASES[@]}")
      REBUILD_BACKEND=1
      REBUILD_FRONTEND=1
      return 0
    fi
  fi

  CHANGED_FILES=()
  while IFS= read -r line; do
    [[ -n "${line}" ]] && CHANGED_FILES+=("${line}")
  done < <(git diff --name-only "${BASE_REF}...HEAD" 2>/dev/null || true)
  if [[ ${#CHANGED_FILES[@]} -eq 0 ]]; then
    info "No file changes detected vs ${BASE_REF}."
    return 0
  fi

  local _ps_preflight="" _ps_foundations="" _ps_data="" _ps_secrets=""
  local _ps_images="" _ps_backend="" _ps_frontend="" _ps_workos=""
  local _ps_observability="" _ps_smoke=""
  REBUILD_BACKEND=""
  REBUILD_FRONTEND=""

  local f
  for f in "${CHANGED_FILES[@]}"; do
    case "${f}" in
      infra/gcp/foundations.tf|infra/gcp/secret-manager.tf)
        _ps_foundations=1; _ps_secrets=1 ;;
      infra/gcp/data.tf)
        _ps_data=1 ;;
      infra/gcp/cloud-run-backend.tf)
        _ps_backend=1 ;;
      infra/gcp/cloud-run-frontend.tf)
        _ps_frontend=1 ;;
      infra/gcp/observability.tf|infra/gcp/meta.tf)
        _ps_observability=1 ;;
      infra/gcp/variables.tf|infra/gcp/outputs.tf|infra/gcp/versions.tf|infra/gcp/backend.tf|infra/gcp/terraform.tfvars)
        _ps_foundations=1; _ps_data=1; _ps_backend=1; _ps_frontend=1; _ps_observability=1 ;;
      Dockerfile.backend|agent/*|services/*|components/*|orchestration/*|trust/*|meta/*|prompts/*|middleware/*)
        REBUILD_BACKEND=1; _ps_images=1; _ps_backend=1 ;;
      Dockerfile.frontend|frontend/*)
        REBUILD_FRONTEND=1; _ps_images=1; _ps_frontend=1 ;;
    esac
  done

  # Forward-dependency: if foundations changed, downstream infra phases are affected
  if [[ -n "${_ps_foundations}" ]]; then
    _ps_data=1; _ps_backend=1; _ps_frontend=1; _ps_observability=1
  fi

  AFFECTED_PHASES=()
  if [[ -n "${_ps_preflight}" ]];     then AFFECTED_PHASES+=(preflight);     fi
  if [[ -n "${_ps_foundations}" ]];   then AFFECTED_PHASES+=(foundations);   fi
  if [[ -n "${_ps_data}" ]];          then AFFECTED_PHASES+=(data);          fi
  if [[ -n "${_ps_secrets}" ]];       then AFFECTED_PHASES+=(secrets);       fi
  if [[ -n "${_ps_images}" ]];        then AFFECTED_PHASES+=(images);        fi
  if [[ -n "${_ps_backend}" ]];       then AFFECTED_PHASES+=(backend);       fi
  if [[ -n "${_ps_frontend}" ]];      then AFFECTED_PHASES+=(frontend);      fi
  if [[ -n "${_ps_workos}" ]];        then AFFECTED_PHASES+=(workos);        fi
  if [[ -n "${_ps_observability}" ]]; then AFFECTED_PHASES+=(observability); fi
  if [[ -n "${_ps_smoke}" ]];         then AFFECTED_PHASES+=(smoke);         fi
}

compute_deploy_identity() {
  if [[ -z "${DEPLOY_VERSION}" ]]; then
    DEPLOY_VERSION="$(date -u +%Y.%m).0"
  fi
  SHORT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
  DEPLOY_ID="tierA-${ENV}-${DEPLOY_VERSION}-${SHORT_SHA}"

  # Backward compat: if VERSION was not set explicitly, derive from DEPLOY_VERSION
  if [[ -z "${VERSION}" ]]; then
    VERSION="${DEPLOY_VERSION}"
  fi
}

confirm_apply() {
  if [[ -n "${AUTO_APPROVE}" ]]; then
    warn "AUTO_APPROVE=1 set; applying without prompt"
    return 0
  fi
  read -r -p "Apply tfplan now? Type 'apply' to continue: " answer
  [[ "${answer}" == "apply" ]] || fail "Apply cancelled."
}

tofu_init_backend() {
  run_in_infra tofu init "-backend-config=bucket=${PROJECT}-tofu-state" "-backend-config=prefix=infra/gcp"
}

tofu_gate() {
  run_in_infra tofu plan -out=tfplan -var-file=terraform.tfvars
  run_in_infra_to_file tfplan.txt tofu show -no-color tfplan
  echo "+ (cd \"${INFRA_DIR}\" && conftest test --policy policies/ --parser hcl2 --all-namespaces --combine *.tf)"
  if [[ -z "${DRY_RUN}" ]]; then
    (
      cd "${INFRA_DIR}"
      conftest test --policy policies/ --parser hcl2 --all-namespaces --combine *.tf
    )
  fi
  run_in_infra_to_file tfplan.json tofu show -json tfplan
  run_in_infra terraform-compliance -p tfplan.json -f features/

  if [[ -n "${DRY_RUN}" ]]; then
    warn "DRY_RUN=1 set; skipping tofu apply"
    return 0
  fi

  confirm_apply
  run_in_infra tofu apply tfplan
}

phase_preflight() {
  require_cmds bash
  run_source "${REPO_ROOT}/scripts/bootstrap_gcp_env.sh"
}

phase_foundations() {
  require_cmds tofu conftest terraform-compliance
  load_env_from_tfvars
  tofu_init_backend
  tofu_gate
  pass "Foundations phase complete."
}

phase_data() {
  require_cmds tofu conftest terraform-compliance
  load_env_from_tfvars
  tofu_gate
  pass "Data phase infrastructure applied."

  local connection_name
  connection_name="$(tofu -chdir="${INFRA_DIR}" output -raw cloud_sql_connection_name 2>/dev/null || true)"

  echo
  warn "STOP GATE: Manual database-url secret update and Postgres checkpointer migration required."
  echo "Next commands (after setting your Cloud SQL password):"
  echo "  CONNECTION_NAME=\"${connection_name:-PROJECT:REGION:INSTANCE}\""
  echo "  echo -n \"postgresql+asyncpg://agent_runtime:<PASSWORD>@/agent?host=/cloudsql/\${CONNECTION_NAME}\" \\"
  echo "    | gcloud secrets versions add database-url --project=\"${PROJECT}\" --data-file=-"
  echo
  echo "  cloud-sql-proxy \"\${CONNECTION_NAME}\" &"
  echo "  PROXY_PID=\$!"
  echo "  DATABASE_URL=\"postgresql+asyncpg://agent_runtime:<PASSWORD>@localhost:5432/agent\" python3 -c \""
  echo "import asyncio"
  echo "from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver"
  echo "async def main():"
  echo "    async with AsyncPostgresSaver.from_conn_string(\\\"\${DATABASE_URL}\\\") as saver:"
  echo "        await saver.setup()"
  echo "asyncio.run(main())"
  echo "print('Postgres checkpointer schema ready')"
  echo "\""
  echo "  kill \"\$PROXY_PID\" 2>/dev/null || true"
  return 20
}

verify_secret_non_placeholder() {
  local secret="$1"
  local latest_name latest_value
  latest_name="$(gcloud secrets versions list "${secret}" --project="${PROJECT}" --limit=1 --format='value(name)' 2>/dev/null || true)"
  [[ -n "${latest_name}" ]] || fail "Secret '${secret}' has no versions."

  latest_value="$(gcloud secrets versions access latest --secret="${secret}" --project="${PROJECT}" 2>/dev/null || true)"
  [[ -n "${latest_value}" ]] || fail "Secret '${secret}' latest version is empty."

  if [[ "${latest_value}" == *"REPLACE_WITH"* ]] || [[ "${latest_value}" == *"placeholder"* ]]; then
    fail "Secret '${secret}' still appears to be a placeholder value."
  fi
}

phase_secrets() {
  require_cmds gcloud
  load_env_from_tfvars
  local secrets=(
    workos-api-key
    openai-api-key
    anthropic-api-key
    deepseek-api-key
    langfuse-public-key
    langfuse-secret-key
    mem0-api-key
    database-url
    agent-facts-secret
    workos-cookie-password
  )
  local secret
  for secret in "${secrets[@]}"; do
    verify_secret_non_placeholder "${secret}"
    pass "Secret '${secret}' has a non-placeholder latest version."
  done
  pass "Secrets phase complete."
}

write_image_pins_to_tfvars() {
  local backend_ref="$1"
  local frontend_ref="$2"
  local backup="${TFVARS}.bak"

  cp "${TFVARS}" "${backup}"
  pass "Backup created at ${backup}"

  python3 - "$TFVARS" "$backend_ref" "$frontend_ref" <<'PY'
import pathlib
import re
import sys

tfvars_path = pathlib.Path(sys.argv[1])
backend = sys.argv[2]
frontend = sys.argv[3]
content = tfvars_path.read_text()

def upsert(key: str, value: str, body: str) -> str:
    pattern = re.compile(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*=.*$")
    replacement = f'{key} = "{value}"'
    if pattern.search(body):
        return pattern.sub(replacement, body, count=1)
    if not body.endswith("\n"):
        body += "\n"
    return body + replacement + "\n"

content = upsert("backend_image", backend, content)
content = upsert("frontend_image", frontend, content)
tfvars_path.write_text(content)
PY

  pass "Updated backend_image/frontend_image in ${TFVARS}"
}

phase_images() {
  require_cmds tofu gcloud docker
  load_env_from_tfvars
  compute_deploy_identity

  info "DEPLOY_ID: ${DEPLOY_ID}"

  local ar_url registry_host
  ar_url="$(tofu -chdir="${INFRA_DIR}" output -raw artifact_registry_url)"
  registry_host="${ar_url%%/*}"

  run_cmd gcloud auth configure-docker "${registry_host}" --quiet

  local ver_tag="agent-backend:${DEPLOY_VERSION}"
  local sha_tag="agent-backend:sha-${SHORT_SHA}"

  echo "+ (cd \"${REPO_ROOT}\" && docker build --platform linux/amd64 -f Dockerfile.backend -t \"${ver_tag}\" -t \"${sha_tag}\" .)"
  if [[ -z "${DRY_RUN}" ]]; then
    (cd "${REPO_ROOT}" && docker build --platform linux/amd64 -f Dockerfile.backend -t "${ver_tag}" -t "${sha_tag}" .)
  fi
  run_cmd docker tag "${ver_tag}" "${ar_url}/${ver_tag}"
  run_cmd docker tag "${sha_tag}" "${ar_url}/${sha_tag}"
  run_cmd docker push "${ar_url}/${ver_tag}"
  run_cmd docker push "${ar_url}/${sha_tag}"

  local fver_tag="agent-frontend:${DEPLOY_VERSION}"
  local fsha_tag="agent-frontend:sha-${SHORT_SHA}"

  echo "+ (cd \"${REPO_ROOT}\" && docker build --platform linux/amd64 -f frontend/Dockerfile.frontend -t \"${fver_tag}\" -t \"${fsha_tag}\" ./frontend)"
  if [[ -z "${DRY_RUN}" ]]; then
    (cd "${REPO_ROOT}" && docker build --platform linux/amd64 -f frontend/Dockerfile.frontend -t "${fver_tag}" -t "${fsha_tag}" ./frontend)
  fi
  run_cmd docker tag "${fver_tag}" "${ar_url}/${fver_tag}"
  run_cmd docker tag "${fsha_tag}" "${ar_url}/${fsha_tag}"
  run_cmd docker push "${ar_url}/${fver_tag}"
  run_cmd docker push "${ar_url}/${fsha_tag}"

  # ── SearXNG sidecar image (Cloud Run settings baked in) ─────────────────
  # Build from Dockerfile.searxng (port 8888 + JSON/limiter-off settings) and
  # push to Artifact Registry so Cloud Run avoids Docker Hub rate limits.
  local searxng_tag="searxng:latest"
  info "Building SearXNG sidecar image..."
  echo "+ (cd \"${REPO_ROOT}\" && docker build --platform linux/amd64 -f Dockerfile.searxng -t \"${searxng_tag}\" .)"
  if [[ -z "${DRY_RUN}" ]]; then
    (cd "${REPO_ROOT}" && docker build --platform linux/amd64 -f Dockerfile.searxng -t "${searxng_tag}" .)
  fi
  run_cmd docker tag "${searxng_tag}" "${ar_url}/${searxng_tag}"
  run_cmd docker push "${ar_url}/${searxng_tag}"
  pass "SearXNG image pushed to ${ar_url}/${searxng_tag}"

  if [[ -n "${DRY_RUN}" ]]; then
    warn "DRY_RUN=1 set; skipping digest lookup and tfvars updates."
    echo "Set these after a real push:"
    echo "  backend_image  = \"${ar_url}/agent-backend@sha256:<BACKEND_DIGEST>\""
    echo "  frontend_image = \"${ar_url}/agent-frontend@sha256:<FRONTEND_DIGEST>\""
    info "DEPLOY_ID: ${DEPLOY_ID}"
    return 0
  fi

  local backend_digest frontend_digest backend_ref frontend_ref
  backend_digest="$(gcloud artifacts docker images describe "${ar_url}/agent-backend:${DEPLOY_VERSION}" --project="${PROJECT}" --format='value(image_summary.digest)')"
  frontend_digest="$(gcloud artifacts docker images describe "${ar_url}/agent-frontend:${DEPLOY_VERSION}" --project="${PROJECT}" --format='value(image_summary.digest)')"

  [[ -n "${backend_digest}" ]] || fail "Could not resolve backend image digest."
  [[ -n "${frontend_digest}" ]] || fail "Could not resolve frontend image digest."

  backend_ref="${ar_url}/agent-backend@${backend_digest}"
  frontend_ref="${ar_url}/agent-frontend@${frontend_digest}"

  pass "backend_image digest pin: ${backend_ref}"
  pass "frontend_image digest pin: ${frontend_ref}"
  info "DEPLOY_ID: ${DEPLOY_ID}"

  if [[ -n "${WRITE_TFVARS}" ]]; then
    write_image_pins_to_tfvars "${backend_ref}" "${frontend_ref}"
  else
    warn "WRITE_TFVARS not set. Paste these into ${TFVARS}:"
    echo "backend_image  = \"${backend_ref}\""
    echo "frontend_image = \"${frontend_ref}\""
  fi
}

phase_backend() {
  require_cmds tofu conftest terraform-compliance curl
  tofu_gate

  if [[ -n "${DRY_RUN}" ]]; then
    return 0
  fi

  local backend_url health
  backend_url="$(tofu -chdir="${INFRA_DIR}" output -raw backend_url)"
  health="$(curl -sf "${backend_url}/healthz" || curl -sf "${backend_url}/health")" || fail "Backend health check failed."
  echo "${health}" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' || fail "Backend health response missing status=ok."
  pass "Backend phase complete: ${backend_url}"
}

phase_frontend() {
  require_cmds tofu conftest terraform-compliance curl

  # FR-F3 / ADR-0034: migrate_engine.mjs BEFORE tofu apply. Cloud Run traffic is
  # TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST 100% on apply — running migrate after
  # apply is not pre-traffic. Schema+seed must be ready before the new revision
  # takes traffic. Uses the same DATABASE_URL secret the frontend service binds
  # (secret exists from secret-manager; bind is apply-time only).
  # Bind↔runner pairing: cloud-run-frontend.tf env DATABASE_URL + this step.
  # Never at Cloud Run boot (cold starts must not race a migration).
  load_env_from_tfvars
  if [[ -n "${DRY_RUN}" ]]; then
    info "[dry-run] would run: gcloud secrets versions access database-url | DATABASE_URL=… node frontend/scripts/migrate_engine.mjs (before tofu apply / traffic)"
  else
    require_cmds gcloud node
    info "Pre-apply: applying frontend engine migrations (migrate_engine.mjs)"
    local db_url
    db_url="$(gcloud secrets versions access latest --secret=database-url --project="${PROJECT}")" \
      || fail "Could not read database-url secret for pre-apply migrate."
    (
      cd "${REPO_ROOT}/frontend"
      DATABASE_URL="${db_url}" node scripts/migrate_engine.mjs
    ) || fail "frontend migrate_engine.mjs failed — aborting before frontend apply/traffic."
  fi

  tofu_gate

  if [[ -n "${DRY_RUN}" ]]; then
    return 0
  fi

  local frontend_url status_code
  frontend_url="$(tofu -chdir="${INFRA_DIR}" output -raw frontend_url)"
  status_code="$(curl -s -o /dev/null -w '%{http_code}' "${frontend_url}/")"
  if [[ "${status_code}" != "200" && "${status_code}" != "307" && "${status_code}" != "308" ]]; then
    fail "Frontend root returned HTTP ${status_code}, expected 200/307/308."
  fi
  pass "Frontend phase complete: ${frontend_url} (HTTP ${status_code})"
}

phase_workos() {
  require_cmds tofu
  local redirect
  redirect="$(tofu -chdir="${INFRA_DIR}" output -raw frontend_workos_redirect_uri 2>/dev/null || true)"
  [[ -n "${redirect}" ]] || fail "frontend_workos_redirect_uri not available in tofu outputs."
  echo
  warn "STOP GATE: Add redirect URI in WorkOS Dashboard before continuing."
  echo "  ${redirect}"
  echo
  echo "WorkOS path: Authentication -> Redirects -> Add URI -> Save"
  return 20
}

phase_observability() {
  require_cmds tofu conftest terraform-compliance
  tofu_gate

  if [[ -n "${DRY_RUN}" ]]; then
    return 0
  fi

  local dashboard_id
  dashboard_id="$(tofu -chdir="${INFRA_DIR}" output -raw monitoring_dashboard_name 2>/dev/null || true)"
  if [[ -n "${dashboard_id}" ]]; then
    pass "Observability phase complete. Dashboard: ${dashboard_id}"
  else
    warn "Observability applied; dashboard output not found."
  fi
}

phase_smoke() {
  require_cmds bash
  compute_deploy_identity
  info "DEPLOY_ID: ${DEPLOY_ID}"
  run_cmd "${REPO_ROOT}/scripts/smoke_gcp.sh"
}

phase_preview() {
  compute_deploy_identity
  detect_changes

  echo
  info "=== Deploy Preview ==="
  echo "  Base ref:        ${BASE_REF}"
  echo "  HEAD:            $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
  echo "  DEPLOY_VERSION:  ${DEPLOY_VERSION}"
  echo "  SHORT_SHA:       ${SHORT_SHA}"
  echo "  DEPLOY_ID:       ${DEPLOY_ID}"
  echo

  if [[ ${#CHANGED_FILES[@]} -gt 0 ]]; then
    info "Changed files (${#CHANGED_FILES[@]}):"
    local f
    for f in "${CHANGED_FILES[@]}"; do
      echo "    ${f}"
    done
  else
    info "No changed files detected."
  fi

  echo
  if [[ ${#AFFECTED_PHASES[@]} -gt 0 ]]; then
    info "Affected phases: $(IFS=' '; echo "${AFFECTED_PHASES[*]}")"
  else
    info "Affected phases: (none)"
  fi

  echo "  Rebuild backend image:  ${REBUILD_BACKEND:-no}"
  echo "  Rebuild frontend image: ${REBUILD_FRONTEND:-no}"
  echo
  info "This is advisory only. No mutations performed."
}

run_phase() {
  local phase="$1"
  case "${phase}" in
    preflight) phase_preflight ;;
    foundations) phase_foundations ;;
    data) phase_data ;;
    secrets) phase_secrets ;;
    images) phase_images ;;
    backend) phase_backend ;;
    frontend) phase_frontend ;;
    workos) phase_workos ;;
    observability) phase_observability ;;
    smoke) phase_smoke ;;
    preview) phase_preview ;;
    *)
      usage
      fail "Unknown phase: ${phase}"
      ;;
  esac
}

run_all() {
  local phases=(
    preflight
    foundations
    data
    secrets
    images
    backend
    frontend
    workos
    observability
    smoke
  )
  local phase rc
  for phase in "${phases[@]}"; do
    info "=== Phase: ${phase} ==="
    set +e
    run_phase "${phase}"
    rc=$?
    set -e
    if [[ "${rc}" -eq 20 ]]; then
      warn "Stopped at manual gate in phase '${phase}'. Complete the gate, then rerun from the next phase."
      return 0
    fi
    if [[ "${rc}" -ne 0 ]]; then
      fail "Phase '${phase}' failed."
    fi
  done
}

main() {
  case "${PHASE}" in
    preview)
      run_phase preview
      ;;
    all)
      require_paths
      run_all
      ;;
    preflight|foundations|data|secrets|images|backend|frontend|workos|observability|smoke)
      require_paths
      run_phase "${PHASE}"
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
