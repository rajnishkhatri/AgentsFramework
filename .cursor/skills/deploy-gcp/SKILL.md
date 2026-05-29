---
name: deploy-gcp
description: Deploys this workspace to GCP Tier A (Cloud Run backend and frontend, Cloud SQL, Secret Manager) through phased OpenTofu automation. Use when the user asks to deploy to GCP, run infra/gcp apply steps, ship to Cloud Run, or execute the GCP deployment workflow with policy gates and smoke checks.
disable-model-invocation: true
paths:
  - infra/gcp/**
  - docs/recipes/gcp/**
  - scripts/*gcp*.sh
---

# Deploy GCP

Use this skill to run the deploy-only GCP workflow for this repository with deterministic gates.

## Scope

- Covers: preflight -> phased infra apply -> image push -> smoke.
- Uses existing infra and scripts; does not re-document recipe internals.
- Stops at mandatory human gates:
  - Database URL + Postgres checkpointer migration after `data`
  - WorkOS redirect URI update after `workos`

## Primary Command

Run phases through:

```bash
./scripts/deploy_gcp.sh <phase>
```

Valid phases:

- `preflight`
- `foundations`
- `data`
- `secrets`
- `images`
- `backend`
- `frontend`
- `workos`
- `observability`
- `smoke`
- `all`
- `preview` — advisory change detection (no mutations; not included in `all`)

## Non-Negotiable Gate Order

For infra phases, preserve this order:

1. `tofu plan -out=tfplan -var-file=terraform.tfvars`
2. `tofu show -no-color tfplan > tfplan.txt`
3. `conftest test --policy policies/ --parser hcl2 --all-namespaces *.tf`
4. `tofu show -json tfplan > tfplan.json`
5. `terraform-compliance -p tfplan.json -f features/`
6. `tofu apply tfplan`

Never skip policy checks before apply.

## Execution Workflow

1. Confirm prerequisites and credentials:
   - `./scripts/deploy_gcp.sh preflight`
2. Apply foundations:
   - `./scripts/deploy_gcp.sh foundations`
3. Apply data resources:
   - `./scripts/deploy_gcp.sh data`
4. Complete the DB human gate printed by the script, then continue.
5. Verify secrets:
   - `./scripts/deploy_gcp.sh secrets`
6. Build/push images and compute digest pins:
   - `./scripts/deploy_gcp.sh images`
7. Deploy backend and frontend:
   - `./scripts/deploy_gcp.sh backend`
   - `./scripts/deploy_gcp.sh frontend`
8. Complete WorkOS human gate:
   - `./scripts/deploy_gcp.sh workos`
9. Apply observability and run smoke tests:
   - `./scripts/deploy_gcp.sh observability`
   - `./scripts/deploy_gcp.sh smoke`

## Common Flags

- `DRY_RUN=1` prints commands and skips apply/mutations.
- `AUTO_APPROVE=1` skips tofu apply prompt.
- `VERSION=vX` sets Docker tag for images phase (default: `DEPLOY_VERSION`).
- `WRITE_TFVARS=1` writes digest-pinned image refs to `infra/gcp/terraform.tfvars`.
- `BASE_REF=origin/main` base ref for change detection in `preview` phase.
- `DEPLOY_VERSION=YYYY.0M.0` CalVer version for image tags and deploy ID.
- `ENV=prod` environment name embedded in `DEPLOY_ID`.

Example:

```bash
DRY_RUN=1 ./scripts/deploy_gcp.sh foundations
```

## Safety Rules

- Never commit `infra/gcp/terraform.tfvars` or secret values.
- Treat `preflight` failures as hard blockers.
- If a phase fails, stop and resolve before proceeding.
- Use digest-pinned image references for Cloud Run.

## Deep Reference

For phase-to-recipe mapping, human gates, and troubleshooting pointers, read:

- [reference.md](reference.md)
- [Recipe 09: Change Detection](../../../docs/recipes/gcp/09_change_detection.md)
