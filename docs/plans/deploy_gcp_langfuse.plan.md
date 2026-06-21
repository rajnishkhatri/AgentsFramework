---
type: plan
name: Deploy to GCP Dev
overview: Build new Docker images with the Langfuse integration (Phases 1-5 code), push to Artifact Registry, update terraform.tfvars with new digests, tofu apply, and run the smoke test including the new Langfuse health check.
todos:
  - id: deploy-env
    content: Set environment variables (PROJECT, REGION, VERSION, INFRA)
    status: pending
  - id: deploy-tests
    content: Run middleware + architecture tests before building
    status: pending
  - id: deploy-build
    content: Docker build backend image with Dockerfile.backend
    status: pending
  - id: deploy-push
    content: Tag and push image to Artifact Registry
    status: pending
  - id: deploy-digest
    content: Get image digest and update terraform.tfvars
    status: pending
  - id: deploy-apply
    content: Tofu plan + apply to create new Cloud Run revision
    status: pending
  - id: deploy-verify
    content: Verify /healthz and run smoke_gcp.sh
    status: pending
isProject: false
---

# Deploy Latest Changes to GCP Dev

The deployment follows the Day-2 "Push a new build" workflow from [LIVE_DEPLOYMENT.md](docs/recipes/gcp/LIVE_DEPLOYMENT.md) section 2.1. Phase 6 changes were docs + smoke script (not containerized), but the Langfuse integration code from Phases 1-5 needs a new backend image.

## What Gets Deployed

- **Backend image rebuild** -- includes `middleware/telemetry_bridge.py`, `middleware/adapters/observability/langfuse_cloud_exporter.py`, `middleware/ports/telemetry_exporter.py`, and the wiring in `middleware/app_prod.py` and `middleware/__main__.py`
- **No frontend rebuild needed** -- Phases 1-6 did not touch `frontend/` code
- **No infra changes** -- Langfuse secrets (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) were already provisioned in Recipe 1/4. No new Terraform resources required.
- **Smoke script runs locally** -- the updated `scripts/smoke_gcp.sh` with Langfuse check runs from your laptop, not inside the container

## Target Environment

- **Project:** `agent-prod-gcp-dev`
- **Region:** `us-central1`
- **Service:** `agent-backend-combined`
- **Registry:** `us-central1-docker.pkg.dev/agent-prod-gcp-dev/agent-backend`

## Deployment Steps

### Step 1: Set environment variables

```bash
export PROJECT="agent-prod-gcp-dev"
export REGION="us-central1"
export VERSION="v2"
export REPO_ROOT="$(pwd)"
export INFRA="${REPO_ROOT}/infra/gcp"
```

### Step 2: Run tests before building

```bash
pytest tests/middleware/ tests/architecture/ -q -p no:logfire
```

Confirms all Langfuse + architecture tests pass locally before shipping.

### Step 3: Build backend image

```bash
docker build -f Dockerfile.backend -t "agent-backend:${VERSION}" .
```

Uses [Dockerfile.backend](Dockerfile.backend) -- multi-stage Python 3.11-slim with `[gcp]` extra.

### Step 4: Push to Artifact Registry

```bash
AR_URL="$(tofu -chdir="$INFRA" output -raw artifact_registry_url)"
REGISTRY_HOST="${AR_URL%%/*}"
gcloud auth configure-docker "${REGISTRY_HOST}" --quiet

docker tag "agent-backend:${VERSION}" "${AR_URL}/agent-backend:${VERSION}"
docker push "${AR_URL}/agent-backend:${VERSION}"
```

### Step 5: Get the image digest

```bash
export BACKEND_IMAGE_DIGEST="$(gcloud artifacts docker images describe \
  "${AR_URL}/agent-backend:${VERSION}" \
  --project="$PROJECT" \
  --format='value(image_summary.digest)')"
echo "BACKEND_IMAGE_DIGEST=${BACKEND_IMAGE_DIGEST}"
```

### Step 6: Update terraform.tfvars with new digest

Update the `backend_image` line in [infra/gcp/terraform.tfvars](infra/gcp/terraform.tfvars):

```hcl
backend_image = "us-central1-docker.pkg.dev/agent-prod-gcp-dev/agent-backend/agent-backend@sha256:<NEW_DIGEST>"
```

### Step 7: Tofu plan + apply

```bash
cd "$INFRA"
tofu plan -out=tfplan -var-file=terraform.tfvars
tofu apply tfplan
```

This creates a new Cloud Run revision and shifts 100% traffic automatically.

### Step 8: Verify health

```bash
export BACKEND_URL="$(tofu -chdir="$INFRA" output -raw backend_url)"
curl -sf "${BACKEND_URL}/healthz" | python3 -m json.tool
```

### Step 9: Run smoke test (includes new Langfuse check)

```bash
export FRONTEND_URL="$(tofu -chdir="$INFRA" output -raw frontend_url)"
export GCP_PROJECT="$PROJECT"
# Optional: export BEARER_TOKEN="<WorkOS JWT>" for full SSE check
./scripts/smoke_gcp.sh
```

The updated smoke script now includes the Langfuse init failure check (Step 5 in the script).

## Rollback

If the new revision is unhealthy, revert `backend_image` in terraform.tfvars to the previous digest and re-apply:

```hcl
backend_image = "us-central1-docker.pkg.dev/agent-prod-gcp-dev/agent-backend/agent-backend@sha256:124be2bb2c676629df8d691b29ae045967d1098a32c8b598318486377904a698"
```

```bash
tofu plan -out=tfplan -var-file=terraform.tfvars && tofu apply tfplan
```
