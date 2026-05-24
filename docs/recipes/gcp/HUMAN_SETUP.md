# GCP Tier A — Human Setup Runbook

> **First live deploy?** Start with **[LIVE_DEPLOYMENT.md](LIVE_DEPLOYMENT.md)** — the consolidated Day-0 / Day-1 / Day-2 operator runbook that sequences Recipes 0–8 end-to-end. Return here for account, billing, and credential steps referenced from Day-0 §0.2.

Before OpenTofu can build the GCP workshop in Recipe 1, a human has to unlock the front gate: create the project, attach billing, create the state bucket, and hand the deployer a credential. These are intentionally manual steps. GCP requires human or org-admin approval for billing-linked projects and service account key download, and those actions should not be hidden inside an automated agent loop.

Complete this runbook **before** running `tofu init` for Recipe 1.

---

## Operator Boundary

The agent can write OpenTofu files, tests, policies, and recipe docs. The operator owns the actions that cross account or billing boundaries:

- Creating or selecting the GCP project.
- Linking a billing account.
- Creating the remote-state bucket that OpenTofu will use before it has state.
- Creating and storing the `tofu-deployer` service account key.
- Populating `terraform.tfvars` with real secrets.

Think of this runbook as the preflight checklist. Once it is complete, Recipe 1 can be applied repeatably from code.

---

## Step 1 — Create a GCP project with billing

This is the one step OpenTofu cannot safely bootstrap for us. The project is the workshop; billing is the power connection. Without both, every later API enablement or resource creation will fail.

```bash
# Pick a project ID (globally unique, must match gcp_project_id in terraform.tfvars)
export PROJECT="agent-prod-gcp-dev"   # or your preferred suffix

gcloud projects create $PROJECT --name "AgentsFramework GCP Dev"
gcloud billing projects link $PROJECT --billing-account=XXXXXXX-XXXXXXX-XXXXXXX
```

> **Note:** If your org has a billing account policy, use the GCP Console instead:
> IAM & Admin → Resource Manager → Create Project → Link Billing.

---

## Step 2 — Create the Tofu state bucket (once per project)

OpenTofu needs somewhere durable to write its first deployment ledger. Because Recipe 1 creates Secret Manager versions, state can contain secret material; keep this bucket restricted and versioned.

```bash
gsutil mb -p $PROJECT -l us-central1 gs://${PROJECT}-tofu-state
gsutil versioning set on gs://${PROJECT}-tofu-state
```

GCS versioning protects against accidental state corruption. The bucket name is injected at `tofu init` time via `-backend-config="bucket=..."` — it is never hardcoded in HCL.

---

## Step 3 — Create the deployer service account + key

The `tofu-deployer` SA is the identity OpenTofu uses to provision all Tier A resources. It is the construction crew badge: broad enough to build the foundations, but separate from the future runtime identity (`agent-backend-runtime`) that the app uses after deployment.

It requires broad project permissions during initial provisioning; tighten after initial deploy if desired.

```bash
gcloud iam service-accounts create tofu-deployer \
  --project=$PROJECT \
  --display-name="OpenTofu Deployer (Recipe 1–8)"

# Grant minimum permissions for Recipe 1–5 provisioning
for ROLE in \
  roles/iam.serviceAccountAdmin \
  roles/iam.projectIAMAdmin \
  roles/artifactregistry.admin \
  roles/secretmanager.admin \
  roles/run.admin \
  roles/cloudsql.admin \
  roles/storage.admin \
  roles/monitoring.admin \
  roles/serviceusage.serviceUsageAdmin \
  roles/resourcemanager.projectIamAdmin; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:tofu-deployer@${PROJECT}.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Download the key — store securely, NEVER commit to git
gcloud iam service-accounts keys create ~/tofu-deployer-key.json \
  --iam-account="tofu-deployer@${PROJECT}.iam.gserviceaccount.com"

export GOOGLE_APPLICATION_CREDENTIALS="$HOME/tofu-deployer-key.json"
```

Add `export GOOGLE_APPLICATION_CREDENTIALS=...` to your shell profile so it persists across sessions. In CI, store the JSON content as an encrypted secret and inject via the runner environment.

---

## Step 4 — Populate terraform.tfvars

`terraform.tfvars` is the sealed envelope that feeds sensitive values into Secret Manager. It is gitignored and must stay that way. Recipe 1 reads these values into `google_secret_manager_secret_version` resources; the values then live in Secret Manager and in the restricted GCS state bucket.

```bash
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars   # terraform.tfvars is gitignored
```

Edit `infra/gcp/terraform.tfvars` with real values:

| Variable | Where to get it |
|----------|-----------------|
| `gcp_project_id` | The project ID from Step 1 |
| `workos_client_id` | WorkOS Dashboard → Applications → Client ID |
| `workos_api_key` | WorkOS Dashboard → API Keys → Secret Key |
| `openai_api_key` | platform.openai.com → API Keys |
| `anthropic_api_key` | console.anthropic.com → API Keys |
| `langfuse_public_key` | cloud.langfuse.com → Settings → API Keys |
| `langfuse_secret_key` | cloud.langfuse.com → Settings → API Keys |
| `mem0_api_key` | app.mem0.ai → API Keys |
| `agent_facts_secret` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `workos_cookie_password` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` (Recipe 5 frontend BFF) |
| `database_url` | Leave as default placeholder for Recipe 1; updated in Recipe 2 |
| `billing_account_id` | `gcloud billing accounts list` (Recipe 7 budget alerts) |
| `alert_notification_email` | Operator email for Cloud Monitoring alerts (Recipe 7, optional) |

---

## Step 5 — Init and apply Recipe 1

At this point the human preflight is done. OpenTofu can now take over: initialize against the remote state bucket, plan the foundation resources, and apply them.

```bash
cd infra/gcp

tofu init \
  -backend-config="bucket=${PROJECT}-tofu-state" \
  -backend-config="prefix=infra/gcp"

tofu plan -out=tfplan
tofu apply tfplan
```

**Verify:**

```bash
# APIs enabled
gcloud services list --project=$PROJECT --filter="state:ENABLED" | grep -E "artifactregistry|run|secretmanager|sqladmin|storage"

# Artifact Registry repo
gcloud artifacts repositories describe agent-backend \
  --project=$PROJECT \
  --location=us-central1

# Runtime SA
gcloud iam service-accounts describe \
  agent-backend-runtime@${PROJECT}.iam.gserviceaccount.com \
  --project=$PROJECT

# Secrets
gcloud secrets list --project=$PROJECT
```

---

## Step 6 (Recipe 5 only) — Update WorkOS redirect URIs

This step is intentionally deferred. After Recipe 5 deploys the frontend Cloud Run service, the `*.run.app` URL is known. Return here and add the URL to WorkOS:

1. WorkOS Dashboard → Authentication → Redirects
2. Add: `https://<frontend-url>.run.app/api/auth/callback`
   (or copy `tofu output -raw frontend_workos_redirect_uri` after Recipe 5 apply)
3. Save

The agent will remind you of this step when running Recipe 5.

---

## Step 7 (optional) — Custom domain

Tier A uses `*.run.app` URLs. To use a custom domain:

```bash
gcloud beta run domain-mappings create \
  --service=agent-backend-combined \
  --domain=api.yourdomain.com \
  --region=us-central1
```

Add the CNAME record your DNS registrar requires. This is not needed for Tier A functionality.

---

## Step 8 (Recipe 7) — Billing budget permissions

Recipe 7 creates a project-scoped billing budget when `billing_account_id` is set in `terraform.tfvars`. The deployer SA needs billing-account-level permission (not a project IAM role):

```bash
export BILLING_ACCOUNT="XXXXXX-XXXXXX-XXXXXX"   # gcloud billing accounts list

gcloud billing accounts add-iam-policy-binding $BILLING_ACCOUNT \
  --member="serviceAccount:tofu-deployer@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/billing.admin"
```

Then add to `terraform.tfvars`:

```hcl
billing_account_id       = "XXXXXX-XXXXXX-XXXXXX"
alert_notification_email = "ops@example.com"   # optional
monthly_budget_usd       = 50
```

---

## Ongoing maintenance

| Task | Command |
|------|---------|
| Rotate a secret | `gcloud secrets versions add <secret-id> --data-file=-` |
| Update database_url after Recipe 2 | `gcloud secrets versions add database-url --data-file=-` |
| Review Cloud SQL backups | `gcloud sql backups list --instance=<instance-name>` |
| Check billing | `gcloud billing budgets list` |
| Teardown (Recipe 8) | See `docs/recipes/gcp/08_cleanup.md` |

---

## Security notes

- The `tofu-deployer` SA key should be stored in a password manager or CI secrets vault, never on shared drives.
- Rotate the key every 90 days: `gcloud iam service-accounts keys delete <old-key-id>` then create a new one.
- After initial provisioning, consider replacing the JSON key with [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation) for CI (eliminates key files entirely).
