#!/usr/bin/env bash
# Regenerate wire artifacts: openapi.yaml + frontend/lib/wire-types.ts.
#
# Per AGENT_UI_ADAPTER_SPRINTS.md S8 (US-8.1, US-8.2, US-8.3). Run this
# locally after changing anything under agent_ui_adapter/wire/, then
# commit BOTH the regenerated openapi.yaml AND wire-types.ts. The
# wire-codegen CI job re-runs this script on every PR and fails on drift.
#
# Idempotent: running twice with no upstream change produces no diff.
#
# Exit codes:
#   0  artifacts regenerated successfully (no claim about whether they changed)
#   1  python or node toolchain missing / codegen failed
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OPENAPI_PATH="$REPO_ROOT/openapi.yaml"
FRONTEND_DIR="$REPO_ROOT/frontend"
WIRE_TYPES_PATH="$FRONTEND_DIR/lib/wire-types.ts"

echo "[regen] repo root: $REPO_ROOT"

# ── Step 1: Python OpenAPI export ────────────────────────────────────
if ! command -v python >/dev/null 2>&1; then
  echo "[regen] ERROR: python not on PATH" >&2
  exit 1
fi
echo "[regen] (1/2) regenerating openapi.yaml from agent_ui_adapter.wire.export_openapi"
# -W ignore so an unrelated logfire / opentelemetry warning never bleeds
# into the YAML artifact (warnings go to stderr; we drop them anyway).
python -W ignore -m agent_ui_adapter.wire.export_openapi > "$OPENAPI_PATH" 2>/dev/null
echo "[regen]   wrote $(wc -l < "$OPENAPI_PATH") lines -> openapi.yaml"

# ── Step 2: TypeScript wire-types codegen via openapi-typescript ─────
if ! command -v npx >/dev/null 2>&1 && [ ! -x "$FRONTEND_DIR/node_modules/.bin/openapi-typescript" ]; then
  echo "[regen] WARNING: Node/npx not available and openapi-typescript not installed; skipping TS codegen." >&2
  echo "[regen]          Install Node 20+ and run \`cd frontend && npm install\` to enable." >&2
  exit 0
fi

mkdir -p "$FRONTEND_DIR/lib"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "[regen]   installing frontend dev deps (one-time): cd frontend && npm install"
  (cd "$FRONTEND_DIR" && npm install --silent --no-audit --no-fund --no-progress)
fi

echo "[regen] (2/2) regenerating frontend/lib/wire-types.ts from openapi.yaml"
(cd "$FRONTEND_DIR" && npx --no-install openapi-typescript ../openapi.yaml -o lib/wire-types.ts)
echo "[regen]   wrote $(wc -l < "$WIRE_TYPES_PATH") lines -> frontend/lib/wire-types.ts"

echo "[regen] done. Commit BOTH openapi.yaml and frontend/lib/wire-types.ts if either changed."
