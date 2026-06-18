# `infra/dev-tier/` — V3-Dev-Tier OpenTofu Stack

> Sprint 2 deliverable. See `[docs/plan/frontend/SPRINT_BOARD.md](../../docs/plan/frontend/SPRINT_BOARD.md)` §Epic 2.1 for the four user stories this stack implements.

> **⚠ Hosting note (2026-06-18): Cloudflare removed — the BFF runs on Cloud Run, not Cloudflare Pages.**
> The Sprint-2 plan hosted the Next.js BFF on Cloudflare Pages, but production
> (Tier A) never cut over: the BFF is the `agent-frontend` **Cloud Run** service
> (`infra/gcp/` + `scripts/deploy_gcp.sh`, `Dockerfile.frontend`), serving on its
> `*.run.app` URL, pointed at `agent-backend-combined` via `MIDDLEWARE_URL`. The
> `cloudflare-pages.tf` / `cloudflare-edge.tf` stack + the `cloudflare_*`
> variables/outputs/provider have been **deleted**. The one live artifact that
> was applied — the unused `agent-frontend-dev` Pages project — should be retired
> with `tofu state rm`/dashboard delete (see "Retiring the Pages project" below).
> Cloudflare-Pages references in the sections/cost tables below are **historical**.
> Edge WAF/DDoS, if wanted later, is **Cloud Armor + an external HTTPS LB** on GCP.

This stack provisions the GCP + Neon substrate that the agent runs on. It is the **only** infrastructure boundary; everything app-side is wired through `composition` roots (`middleware/composition.py`, `frontend/lib/composition.ts`) that read the secrets and URLs this stack publishes.

---

## What lives here


| File                       | Sprint story | Provisions                                                                                                                             |
| -------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `versions.tf`              | —            | Provider pins (google, neon, postgresql, random) + provider configs                                                                    |
| `variables.tf`             | —            | All inputs; secret-bearing vars are `sensitive = true`                                                                                 |
| `backend.tf`               | —            | GCS remote state (bucket injected via `-backend-config`)                                                                               |
| `cloud-run.tf`             | **S2.1.1**   | `agent-middleware` Cloud Run v2 service (min=0, 1 vCPU/2 GB, 3600 s timeout, startup CPU boost, /healthz probe) + dedicated runtime SA |
| `neon.tf`                  | **S2.1.2**   | Neon Free project (import-existing) + `neondb` database (adopted default) + pgvector extension via `cyrilgdn/postgresql` provider       |
| ~~`cloudflare-pages.tf`~~  | ~~S2.1.3~~   | **Removed 2026-06-18** — BFF on Cloud Run (`agent-frontend`), not Pages                                                                |
| ~~`cloudflare-edge.tf`~~   | ~~S2.1.3~~   | **Removed 2026-06-18** — see Hosting note above                                                                                        |
| `secret-manager.tf`        | **S2.1.4**   | 7 secrets (workos, openai, anthropic, langfuse public+secret, mem0, neon DB URL) + IAM accessor bindings to the runtime SA             |
| `outputs.tf`               | —            | Cross-stack handoff: `middleware_url`, `secret_ids`                                                                                    |
| `policies/*.rego`          | deep TDD     | Conftest/OPA policies — same invariants as the pytest suite, in Rego                                                                   |
| `features/*.feature`       | deep TDD     | terraform-compliance BDD scenarios (run during apply phase)                                                                            |
| `.tflint.hcl`              | deep TDD     | tflint rule config (terraform + google rulesets)                                                                                       |
| `terraform.tfvars.example` | —            | Template for the gitignored `terraform.tfvars`                                                                                         |


---

## Local prereqs (first-time setup)

```bash
brew install opentofu tflint conftest
pip install python-hcl2 terraform-compliance pytest-bdd

# Optional: gcloud CLI for state-bucket creation + SA key download
brew install --cask google-cloud-sdk
```

---

## Account setup checklist

These are the cloud accounts the stack needs *before* `tofu apply` will succeed. Detailed walkthroughs in the chat-history; capture the values listed under each so they're ready to paste into `terraform.tfvars`.

### 1. GCP

1. Create project `agent-prod-gcp-dev-<your-suffix>` in `us-central1`.
2. Enable APIs: `run.googleapis.com`, `secretmanager.googleapis.com`, `iam.googleapis.com`, `cloudresourcemanager.googleapis.com`, `artifactregistry.googleapis.com`, `monitoring.googleapis.com`, `logging.googleapis.com`.
3. Create a `tofu-deployer` service account with these 7 roles, then download a JSON key:
  - `roles/run.admin` — Cloud Run service lifecycle
  - `roles/iam.serviceAccountUser` — *use* the runtime SA for `actAs` checks
  - `roles/iam.serviceAccountAdmin` — *create* the dedicated runtime SA (added 2026-04-23 after first apply hit `iam.serviceAccounts.create denied`)
  - `roles/secretmanager.admin` — secret + version + IAM lifecycle
  - `roles/serviceusage.serviceUsageAdmin` — list / verify enabled APIs
  - `roles/artifactregistry.admin` — for the future Cloud Run image push
  - `roles/storage.admin` — read/write the Tofu state bucket
4. Create the Tofu state bucket:
  ```bash
   gsutil mb -p $PROJECT -l us-central1 gs://${PROJECT}-tofu-state
   gsutil versioning set on gs://${PROJECT}-tofu-state
  ```

**Capture:** project ID, path to the SA key JSON.

### 2. Neon

1. Sign up at [https://console.neon.tech](https://console.neon.tech) (GitHub login fastest).
2. Create API key under Account Settings → API Keys.

**Capture:** API key.

### 3. ~~Cloudflare~~ — REMOVED (no longer required)

> **2026-06-18:** Cloudflare is no longer part of this stack — no account, zone,
> Pro upgrade, or API token is needed. The BFF runs on Cloud Run. The steps below
> are kept struck-through for historical context only; skip them.

~~1. Sign up at https://dash.cloudflare.com / add a domain / upgrade to Pro /
create a Pages+Zone API token.~~ **(skip — not used)**

#### Retiring the already-applied Pages project

A `tofu apply` created one live Cloudflare resource: the `agent-frontend-dev`
Pages project (in remote state as `cloudflare_pages_project.frontend`). Since the
`.tf` is now deleted, remove it from state so the next plan doesn't error on the
missing provider, and delete the project itself (it serves no traffic):

```bash
# from infra/dev-tier, after `tofu init` against the live backend:
tofu state rm cloudflare_pages_project.frontend data.cloudflare_zone.agent
# then delete the project in the Cloudflare dashboard (Workers & Pages →
# agent-frontend-dev → Settings → Delete), or via API/wrangler.
```

(The WAF ruleset was never applied — nothing to remove there.)

**Cost note**: Cloudflare Pro is the one substrate that breaks the V3-Dev-Tier "all free" promise. The sprint board's "Stage A → $5-30/mo" range assumes Cloudflare Pro is in. Without it, you can run on Free but lose WAF observability + cache-rule control on streaming routes.

### 4. WorkOS / Mem0 / Langfuse

Reuse Sprint 0/1 keys. Capture: `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `MEM0_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.

### 5. LLM providers

Capture: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (already in `.env`).

---

## Apply workflow

> Sprint 2 was authored under the `**validate_now_apply_later`** scope (per the user clarification turn). The HCL is fully validated, lint-clean, and Rego-policy-clean **without** any cloud credentials. Apply happens here once accounts are ready.

```bash
cd infra/dev-tier

# 1. Copy the tfvars template and fill in the live values from the
#    account-setup checklist above. NEVER commit terraform.tfvars.
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars

# 2. Authenticate Tofu's google provider.
export GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/gcloud/tofu-deployer-key.json

# 3. Initialise with the GCS backend bucket name.
tofu init \
  -backend-config="bucket=${GCP_PROJECT_ID}-tofu-state"

# 4. Plan + review.
tofu plan -out=tfplan

# 5. Run the deep-TDD apply-time checks against the resolved plan.
tofu show -json tfplan > tfplan.json
terraform-compliance -p tfplan.json -f features/

# 6. Apply.
tofu apply tfplan

# 7. Post-apply smoke checks.
curl -s "$(tofu output -raw middleware_url)/healthz"   # expect: {"status":"ok","profile":"v3"}
gcloud secrets list --project=$GCP_PROJECT_ID          # expect: 7 secrets
```

---

## Static (no-credential) test pipeline

Run anytime, no cloud creds needed. CI will run all four:

```bash
# (a) HCL syntax + provider type-check
cd infra/dev-tier
tofu init -backend=false
tofu validate

# (b) tflint (HCL hygiene + google-provider rule pack)
tflint --init
tflint

# (c) Conftest / OPA Rego policies
conftest test --policy policies/ --parser hcl2 --all-namespaces *.tf

# (d) pytest invariants (parsed-HCL assertions; failure-paths-first)
cd ../..
pytest tests/infra/ -m infra
```

Expected output: `38 passed` (pytest) + `108 tests, 108 passed` (conftest) + `Success! The configuration is valid.` (tofu) + clean tflint exit.

---

## Test layering — how this fits the agentic TDD pyramid

Per `[research/tdd_agentic_systems_prompt.md](../../research/tdd_agentic_systems_prompt.md)`, IaC tests sit at **L2 Reproducible** — contract-driven, mock-deterministic, every commit. Specifically:


| Layer               | Pyramid level | Where it lives                              | Triggered by    |
| ------------------- | ------------- | ------------------------------------------- | --------------- |
| HCL parse contract  | L1-style      | `tests/infra/test_*.py` (python-hcl2)       | every commit    |
| Resource policy     | L1/L2 hybrid  | `policies/*.rego` (Conftest)                | every commit    |
| Static lint         | L1            | `tflint`                                    | every commit    |
| Provider type check | L2            | `tofu validate`                             | every commit    |
| Plan-resolved BDD   | L2            | `features/*.feature` (terraform-compliance) | apply-time only |
| Live infra smoke    | L4            | `curl /healthz`, `gcloud secrets list`      | post-apply only |


**Failure-paths-first (TAP-4)** is preserved: every pytest assertion phrases the rejection invariant before the acceptance one. Mutation testing (try `secret_data = "literal"` or `startup_cpu_boost = false` and watch both pytest and conftest fire) confirms the policies aren't tautological (TAP-1).

---

## V3 → V2-Frontier graduation triggers

Each substrate's upgrade path is composition-root-only per `FRONTEND_ARCHITECTURE.md` §F3. See the SPRINT_BOARD §V2-Frontier Graduation Triggers table; the only files that change in this directory during graduation are listed under the "Swap File" column.


| Component               | Trigger                                                         | This-stack file to edit                                                        |
| ----------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Cloud Run min=0 → min=1 | Cold-start p95 > 500 ms after caching all reasonable code paths | `cloud-run.tf` `scaling.min_instance_count`                                    |
| Neon Free → Pro         | Storage > 0.5 GB OR CU-hr exhausted                             | `neon.tf` (drop the project_settings overrides) + `terraform.tfvars` plan tier |
| Edge WAF/DDoS (if ever) | Public exposure needs L7 filtering                              | **Cloud Armor + external HTTPS LB** (GCP) — Cloudflare removed 2026-06-18      |
| Self-hosted runtime     | >100 K LangGraph nodes/mo                                       | (out of scope here — switch profile in `frontend/lib/composition.ts`)          |


