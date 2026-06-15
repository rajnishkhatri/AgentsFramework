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

## Tiered-Loops Stress Revision (loops-on, prod untouched)

The planning-pipeline tiered loops (Phases 1–3: plan-and-execute, reflexion,
escalation) ship **dark by default** — `composition.py` reads
`REFLEXION_ENABLED`, `PLANNING_PLAN_SOURCE`, `MAX_REFLEXION_ATTEMPTS` (Step 0,
2026-06-14) and they default OFF for prod parity. The e2e stress run
(`frontend/e2e/full-stack/planning-stress.spec.ts`) needs a **loops-on** backend
without disturbing prod.

**These three env vars are NOT in `infra/gcp/cloud-run-backend.tf`.** A normal
`backend` phase apply will NOT enable the loops. Two paths:

1. **Stress run — out-of-band tagged revision (recommended; prod untouched).**
   Deploy a zero-traffic tagged revision from the *current* digest-pinned image
   with the flags flipped, then point the stress spec at the tagged URL. This
   intentionally bypasses the OpenTofu/policy workflow because it mutates no
   managed infra (no traffic, throwaway):

   ```bash
   # Reuse the live image digest; serve 0% traffic under the "stress" tag.
   IMG=$(gcloud run revisions describe \
     "$(gcloud run services describe agent-backend-combined --region us-central1 \
        --format='value(status.latestReadyRevisionName)')" \
     --region us-central1 --format='value(spec.containers[0].image)')

   gcloud run services update agent-backend-combined --region us-central1 \
     --image "$IMG" --tag stress --no-traffic \
     --update-env-vars REFLEXION_ENABLED=1,PLANNING_PLAN_SOURCE=generated,MAX_REFLEXION_ATTEMPTS=2
   ```

   The tagged URL is `https://stress---agent-backend-combined-<hash>-uc.a.run.app`.
   The Playwright spec hits the **frontend**, and the frontend reaches the backend
   via its `MIDDLEWARE_URL` env. So a loops-on run needs a matching zero-traffic
   **frontend** stress revision whose `MIDDLEWARE_URL` points at the stress
   backend tag:

   ```bash
   FE_IMG=$(gcloud run revisions describe \
     "$(gcloud run services describe agent-frontend --region us-central1 \
        --format='value(status.latestReadyRevisionName)')" \
     --region us-central1 --format='value(spec.containers[0].image)')

   gcloud run services update agent-frontend --region us-central1 \
     --image "$FE_IMG" --tag stress --no-traffic \
     --update-env-vars MIDDLEWARE_URL=https://stress---agent-backend-combined-<hash>-uc.a.run.app
   ```

   Then auto-fill the tagged frontend URL into the `stress` profile (reads the
   real URL off the service traffic map — never hand-guess the hash):

   ```bash
   python scripts/fill_stress_profile_url.py   # writes stress base_url in testing.profiles.yml
   ```

   …and run with the profile instead of a hand-assembled `BASE_URL`:

   ```bash
   TEST_PROFILE=stress STRESS_SMOKE=1 pnpm test:e2e:stress   # one case/phase first
   TEST_PROFILE=stress pnpm test:e2e:stress                  # full corpus
   ```

   Clean up after both runs:
   `gcloud run services update-traffic agent-backend-combined --region us-central1 --remove-tags stress`
   and the same for `agent-frontend`.

2. **Promote to prod — Terraform (gated).** Only when evidence justifies it: add
   `REFLEXION_ENABLED` / `PLANNING_PLAN_SOURCE` / `MAX_REFLEXION_ATTEMPTS` `env`
   blocks to `cloud-run-backend.tf` (mirror the `GOAL_JUDGE_ENABLED` block, wired
   to Terraform vars defaulting OFF), then run the full gate order below and the
   `backend` phase. This is a separate, evidence-gated decision — the
   shadow→consume discipline from the GoalJudge rollout.

Never flip these flags on the prod-traffic revision as a shortcut — that is a
silent prod behavior change with no policy gate.

## Deep Reference

For phase-to-recipe mapping, human gates, and troubleshooting pointers, read:

- [reference.md](reference.md)
- [Recipe 09: Change Detection](../../../docs/recipes/gcp/09_change_detection.md)
- E2E stress plan + Step 0 carriers/flags:
  [planning_pipeline_e2e_stress_and_trace_analysis.plan.md](../../../docs/plans/planning_pipeline_e2e_stress_and_trace_analysis.plan.md)
