# Deploy Piece C — memory recall/store ON (no-traffic) + thread-table migration

> Companion to [`scripts/deploy_piece_c.sh`](../../scripts/deploy_piece_c.sh). This doc holds the **config changes the script can't make for you** (a Terraform env-var add) and the exact run/rollback sequence. Posture chosen 2026-06-18: **`MEMORY_ENABLED=true` only** (recall+store live; auto-capture stays in shadow) on a **`--tag` no-traffic** revision (prod untouched).

> **Scope note (BFF sidebar is a SEPARATE step in this guide — §BFF).** Piece C's core is the **backend** memory deploy + the threads-table migration. Making the chat **sidebar** persist is a distinct follow-up: bind `DATABASE_URL` on the `agent-frontend` BFF. As of 2026-06-18 the option-B `pg` adapter is **code complete**, so that bind is now **safe to run** (a `/cloudsql/` DSN routes to `pg`, not the Neon driver). Full procedure — prerequisites, the bind, and verification — is in **§BFF**; until you run it, the BFF stays on the in-memory thread repo and the sidebar renders empty. Plan/Terraform-durable form: [`docs/plans/bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md).

> **Service names (read first).** The **real prod agent backend is
> `agent-backend-combined`** (the BFF's `MIDDLEWARE_URL` points at it; all
> e2e/stress/GoalJudge target it). `agent-middleware` is an **orphaned**
> V3-dev-tier service on the `hello` placeholder — **do not deploy to it.** The
> prod **BFF is `agent-frontend` on Cloud Run**, *not* Cloudflare Pages (Cloudflare
> was removed 2026-06-18). The deploy script now defaults `SERVICE=agent-backend-combined`.

## TL;DR

```bash
# 0a. BUILD + PUSH the agent image (REQUIRED — see §0). docker build + push
#     (the way deploy_gcp.sh does it); `gcloud builds submit` has no -f flag.
IMG="us-central1-docker.pkg.dev/agent-prod-gcp-dev/agent-backend/agent-backend:$(git rev-parse --short HEAD)"
docker build --platform linux/amd64 -f Dockerfile.backend -t "$IMG" . && docker push "$IMG"
# 0b. one config edit (see §1) — add MEMORY_ENABLED to the Cloud Run env block
# 1. run the script (pull DATABASE_URL → migrate → tag deploy; NO tofu apply)
GCP_PROJECT_ID=agent-prod-gcp-dev MIDDLEWARE_IMAGE="$IMG" bash scripts/deploy_piece_c.sh
# 2. verify backend selection + exercise the tag URL (§3)
# 3. promote when satisfied (§4); rollback is one command (§5)
# 4. (optional) make the chat sidebar durable — bind DATABASE_URL on agent-frontend
#    (now SAFE: option-B pg adapter is in). Prereqs + bind + verify in §BFF.
```

## 0. Build + push the agent image — REQUIRED FIRST (don't skip)

> **⚠ The existing `mem` tag (`agent-backend-combined-00083-wal`) is STALE — rebuild it.**
> That revision's image was built before the `middleware/app_prod.py` memory-wiring
> fix (2026-06-18). It had `MEMORY_ENABLED=true` but its graph was built from a
> narrow `AgentComponents` that dropped `memory_service` → recall/store NEVER fired;
> an authenticated run emitted **zero** memory carriers even though everything
> *looked* configured (flag on, real user_id, `memory backend: mem0 (durable)`
> logged). `MEMORY_ENABLED=true` is necessary but **not sufficient** — you MUST
> redeploy from an image that contains the fix (built after that commit), and then
> verify carriers actually appear (§3d). Building a fresh `$IMG` below from current
> `HEAD` is exactly what picks the fix up. The regression guard
> `tests/middleware/test_app_prod_memory_wiring.py` now pins that the prod graph is
> built with a non-None `memory_service`, so this class of silent drop can't recur.

> **Why the script REQUIRES `MIDDLEWARE_IMAGE`.** A `gcloud run deploy` **without**
> `--image` re-deploys whatever image the service currently has. If you ever point
> the script at a freshly-Terraform-created service (whose `middleware_image`
> defaults to the `hello` placeholder, `infra/dev-tier/variables.tf`), an
> `--image`-less deploy would set `MEMORY_ENABLED=true` on a placeholder that runs
> no agent — a green-looking no-op (a bare health endpoint returns 200 from the
> placeholder too). The script now requires `MIDDLEWARE_IMAGE`, passes `--image`, and asserts
> the agent health body `"runtime":"langgraph"` so that can't happen silently.
> (The live `agent-backend-combined` already runs a real image; this guard matters
> for fresh services and for the orphaned `agent-middleware`.)

Build the agent image from `Dockerfile.backend`, push it to Artifact Registry, and
pass its URI to the deploy script via `MIDDLEWARE_IMAGE`:

```bash
IMG="$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/agent-backend/agent-backend:$(git rev-parse --short HEAD)"
docker build --platform linux/amd64 -f Dockerfile.backend -t "$IMG" .
docker push "$IMG"
export MIDDLEWARE_IMAGE="$IMG"
```

> The `middleware_image` tfvar belongs to the **orphaned `infra/dev-tier`** stack
> (`agent-middleware`) — it does **not** govern `agent-backend-combined`, which is
> deployed from **`infra/gcp/`** where the image is set on the backend service
> directly. So a no-traffic `--tag` revision via this script (`gcloud --image`) is
> the right mechanism for the immediate deploy; for a **durable** prod promotion,
> update the backend image in `infra/gcp/` and apply *that* stack — not a dev-tier
> tfvar. (Build + push uses `docker build -f` + `docker push` like `deploy_gcp.sh`;
> `gcloud builds submit` has no `-f` flag.)

**Verify it's the agent, not the placeholder**, after deploy:
`GET <url>/health` must return `{"runtime":"langgraph",...}` (the script asserts this,
probing `/health` first then `/healthz` — externally `/healthz` currently 404s through
the router on `agent-backend-combined`; `/health` is the live one); the boot log must
NOT say `Hello from Cloud Run!` (that string == placeholder).

---

## 1. Config update — make `MEMORY_ENABLED` durable in Terraform

The live `agent-backend-combined` already maps `DATABASE_URL` (secret `database-url`) and `MEM0_API_KEY` (secret `mem0-api-key`), and the `mem` tag already carries `MEMORY_ENABLED=true` (the deploy script's `--update-env-vars` set it on the tagged revision). The remaining step is to make the flag **durable** so the next Terraform apply doesn't wipe it.

`agent-backend-combined` is deployed from **`infra/gcp/`** (not `infra/dev-tier/` — that's the orphaned `agent-middleware`). Add `MEMORY_ENABLED` to the Cloud Run env block for the backend service in `infra/gcp/` alongside the other plain envs (next to `MEM0_BASE_URL` / `ARCHITECTURE_PROFILE`):

```hcl
      env {
        name  = "MEMORY_ENABLED"
        value = "true"
      }
      # NOTE: MEMORY_AUTOCAPTURE_ENABLED is intentionally NOT set here — it
      # defaults to false (shadow). Write-back is gated on the Phase-2 eval
      # calibration clearing the Stage-6 enable-policy. Do not add it until then.
```

> **Why TF and not just `gcloud --update-env-vars`?** A gcloud-only override is wiped by the next `tofu apply`. The script passes `--update-env-vars=MEMORY_ENABLED=true` so the no-traffic tag works immediately; land the TF edit so the flag survives a re-apply. The gcloud flag is the belt-and-suspenders for the immediate tag.

After the edit, run `cd infra/gcp && tofu validate` (credential-free).

## 2. Run the deploy script

```bash
GCP_PROJECT_ID=agent-prod-gcp-dev \
GCP_REGION=us-central1 \
MIDDLEWARE_IMAGE="$IMG" \
bash scripts/deploy_piece_c.sh
```

It runs: pulls `DATABASE_URL` from the `database-url` secret (never printed) → applies `0000_init_threads.sql` via `psql` (auto-skipped with proxy guidance if it's a Cloud SQL socket — see note) → `gcloud run deploy agent-backend-combined --image $MIDDLEWARE_IMAGE --tag mem --no-traffic … MEMORY_ENABLED=true` → smoke-checks the agent health body (asserts `runtime:langgraph`, probing `/health` then `/healthz`) on the tag URL. **Because the tag is `--no-traffic`, the prod URL keeps serving the current prod revision throughout.** No Terraform apply (the prod DB secret already exists; the old dev-tier Neon apply was removed — see §DB).

> **§DB — `database-url` is Cloud SQL, `neon-database-url` is a different (abandoned) DB.** The prod backend reads **`database-url`**, a **Cloud SQL** Postgres connection (`postgresql://…@/agent?host=/cloudsql/agent-prod-gcp-dev:us-central1:agent-db`). The dev-tier `neon-database-url` secret is a **Neon** string (`…neon.tech/neondb`) that the running service **never** reads — it belongs to the same abandoned `infra/dev-tier` stack as `agent-middleware`/Cloudflare. **They are NOT the same string and must NOT be synced** — copying Neon→`database-url` would repoint the live backend onto a different, empty database. The script migrates the *same* secret the runtime opens (`DB_SECRET`, default `database-url`). Because that DSN is a `/cloudsql/` unix socket, `psql` from a workstation needs the **Cloud SQL Auth Proxy** (the script detects this and prints the exact command); or run the migration as a one-off Cloud Run job / via Cloud SQL Studio.

## 3. Verify (after the script)

```bash
# (a) durable backend selected? — the composition root logs this at boot
gcloud run services logs read agent-backend-combined \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION | grep "memory backend"
#   expect:  memory backend: mem0 (durable)

# (b) threads table exists — via the Cloud SQL Auth Proxy (the secret DSN is a
#     /cloudsql/ socket; psql can't open it directly):
cloud-sql-proxy --unix-socket /tmp/cloudsql \
  agent-prod-gcp-dev:us-central1:agent-db &
psql "host=/tmp/cloudsql/agent-prod-gcp-dev:us-central1:agent-db dbname=agent user=agent_runtime" \
  -c "SELECT count(*) FROM threads;"

# (c) memory roundtrip against the TAG url (BEARER AUTH REQUIRED — /run/stream and
#     /agent/memory both 401 without a WorkOS JWT), then restart-survives:
#     POST /agent/memory  →  GET /agent/memory  →  redeploy tag  →  GET again (still there)
#   Tag URL: https://mem---agent-backend-combined-<hash>-uc.a.run.app

# (d) CARRIERS ACTUALLY FIRED — the check that catches a memory-blind graph.
#     After ONE authenticated /run/stream on the tag (a "remember" turn), confirm
#     the run emitted memory carriers. Cheapest source = Cloud Logging (not
#     rate-limited, unlike the Langfuse public API):
gcloud run services logs read agent-backend-combined \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION --limit=200 \
  | grep -iE "memory\.recall|memory\.store|memory\.(recall|store) degraded"
#   expect at least one recall/store line. ZERO lines after a from-step-0 authed
#   run = the graph is memory-blind (the §0 stale-image trap) — rebuild + redeploy.
#   Then fetch the trace for the audit:
.venv/bin/python scripts/fetch_memory_trace.py --since "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ)"
#   exit 0 = carriers found (path printed); exit 2 = none (see the stale-image trap).
```

> **`MEMORY_ENABLED=true` is necessary but NOT sufficient.** A green health body and
> the `memory backend: mem0 (durable)` boot log do NOT prove recall/store ran — both
> are true even when the graph was built memory-blind. The ONLY proof is a carrier
> from an authenticated run (§3d). Always run §3d before declaring the deploy good.

> **Audit gate (plan Verification 4) — ✅ PASSED 2026-06-18.** After one authenticated
> run on the rebuilt tag, carriers fired (§3d) and the `governance-trace-audit` skill
> returned **COMPLIANT WITH FINDINGS** on trace `ef236f95`. History: the first authed
> run (rev `00083-wal`) emitted **zero** carriers — root-caused to the `app_prod.py`
> wiring drop (now fixed + guarded); audit was blocked on it, not on auth. Reports:
> [`governance_audit_memory_on_2026-06-18.md`](../reviews/governance_audit_memory_on_2026-06-18.md),
> [`governance_audit_ef236f95_2026-06-18.md`](../reviews/governance_audit_ef236f95_2026-06-18.md);
> full per-case validation (prompt→expected→actual→trace):
> [`memory_layer_validation_walkthrough_2026-06-18.md`](../reviews/memory_layer_validation_walkthrough_2026-06-18.md).

## §BFF — make the chat sidebar durable (option B is in; the bind is now SAFE)

**Status (2026-06-18): the option-B `pg` adapter is CODE COMPLETE** (uncommitted). The
prior "do NOT bind — it would crash" warning is **resolved**. The chat sidebar persists
via `selectThreadRepo()` in `frontend/lib/bff/server_composition.ts`, which runs in the
**BFF ring** — in prod the **`agent-frontend` Cloud Run service** (Cloudflare Pages was
removed 2026-06-18; the BFF is on Cloud Run), a **separate service** from
`agent-backend-combined`. The backend's `DATABASE_URL` feeds the LangGraph checkpointer
and does **not** reach the BFF; `agent-frontend` has **no** `DATABASE_URL` today
(verified 2026-06-18), so `selectThreadRepo` falls back to `InMemoryThreadRepo` and the
sidebar renders empty (the component IS mounted — this is the empty-state placeholder,
not missing code).

**What changed.** `selectThreadRepo` now picks the driver by DSN
([`neon_thread_repo.ts` `selectThreadRepo`](../../frontend/lib/adapters/thread_store/neon_thread_repo.ts)
→ [`classifyDsn`](../../frontend/lib/adapters/thread_store/pg_thread_repo.ts)):
a `/cloudsql/` socket DSN (or any generic TCP Postgres) routes to the new
`pgDrizzleDb` seam (`pg` + `drizzle-orm/node-postgres` over the unix socket); only a
`.neon.tech` host uses the old Neon HTTP driver. So binding the prod `database-url`
secret (a `/cloudsql/` DSN) on `agent-frontend` now reaches the right driver instead of
throwing. Plan + research basis: [`docs/plans/bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md).

### Prerequisites (do these once, in order)

```bash
# 0. Commit the option-B code, then build + push a NEW agent-frontend image that
#    INCLUDES the `pg` dependency. The bind is inert until this image is live —
#    the running revision predates the pg adapter. Build via the normal frontend
#    image path (frontend/Dockerfile.frontend; deploy_gcp.sh builds agent-frontend:<ver>).

# 1. Grant the frontend runtime service account Cloud SQL Client (so it can open
#    the /cloudsql/ socket) and read access to the database-url secret. Today the
#    frontend SA only has the WorkOS secret accessors (infra/gcp/cloud-run-frontend.tf).
FRONTEND_SA="$(gcloud run services describe agent-frontend \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --format='value(spec.template.spec.serviceAccountName)')"

gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:$FRONTEND_SA" --role="roles/cloudsql.client"

gcloud secrets add-iam-policy-binding database-url \
  --project="$GCP_PROJECT_ID" \
  --member="serviceAccount:$FRONTEND_SA" --role="roles/secretmanager.secretAccessor"
```

### The bind (now safe to run)

```bash
gcloud run services update agent-frontend \
  --project="$GCP_PROJECT_ID" --region="$GCP_REGION" \
  --update-secrets="DATABASE_URL=database-url:latest" \
  --add-cloudsql-instances="agent-prod-gcp-dev:us-central1:agent-db"
```

`--add-cloudsql-instances` mounts the `/cloudsql/agent-prod-gcp-dev:us-central1:agent-db`
socket into the container; `pg` dials it via the `host=/cloudsql/…` in the DSN. (Node
runtime, not edge — the BFF route handlers already run on Node 20, which `pg` needs.)

### Verify it took

```bash
# Create a thread in the UI, restart the BFF revision, confirm the sidebar still
# lists it. Or hit the route directly (401 = route present but unauthed; an
# authenticated 200 with a thread list = durable persistence working):
curl -s -o /dev/null -w '%{http_code}\n' "$FRONTEND_URL/api/threads"
# And confirm no thread-store error in logs:
gcloud logging read \
  'resource.labels.service_name=agent-frontend AND textPayload:ThreadStoreError' \
  --project="$GCP_PROJECT_ID" --freshness=10m --limit=5
# (zero rows = healthy; the migration already created the threads table in Piece C.)
```

> **Durable form (survives `tofu apply`).** The `gcloud` update above is imperative and a
> later Terraform apply would wipe it. To make it durable, mirror the backend's pattern in
> `infra/gcp/cloud-run-frontend.tf`: add a `DATABASE_URL` `value_source.secret_key_ref`
> (secret `database-url`), the Cloud SQL volume + `run.googleapis.com/cloudsql-instances`
> annotation, the `roles/cloudsql.client` binding on `google_service_account.frontend_runtime`,
> and a `database-url` secret accessor for it — exactly as `cloud-run-backend.tf` declares
> them for the backend. (Tracked in [`bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md) §Deferred.)

> **Local dev.** With the option-B adapter, `frontend/.env.local`'s `DATABASE_URL` can now
> point at the Cloud SQL Auth Proxy socket
> (`postgresql://…@/agent?host=/tmp/cloudsql/agent-prod-gcp-dev:us-central1:agent-db` after
> `cloud-sql-proxy --unix-socket /tmp/cloudsql …`) and `classifyDsn` routes it to `pg`. Leave
> it unset for the ephemeral in-memory repo.

The Cloud SQL DB serves both rings; the threads migration omits the checkpoint tables
(IR-NEON-5), so the BFF threads table and LangGraph's checkpoints coexist in the same
instance without collision.

## 4. Promote (when satisfied)

```bash
gcloud run services update-traffic agent-backend-combined --to-tags=mem=100 \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION
```

## 5. Rollback

```bash
# memory flag off → instant return to no-recall/no-store (graph shape unchanged).
# The mem tag is --no-traffic, so prod already serves the current prod revision.
# To drop the tag entirely:
gcloud run services update-traffic agent-backend-combined --remove-tags=mem \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION
# If you DID promote, point traffic back to the prior prod revision. Look it up
# dynamically rather than hardcoding (revision suffixes change every deploy):
PREV="$(gcloud run revisions list --service=agent-backend-combined \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION \
  --format='value(metadata.name)' --filter='NOT metadata.name~mem' --limit=2 \
  | sed -n '2p')"   # [1]=just-promoted, [2]=the one before it
gcloud run services update-traffic agent-backend-combined \
  --to-revisions="${PREV}=100" \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION
# DATABASE_URL / the migration are additive + safe to leave (threads table is
# unused until the BFF binding lands).
```

## What this unblocks for the Phase-2 eval (the other parallel track)

Running with `MEMORY_ENABLED=true` makes the loop emit `MEMORY_RECALLED`/`MEMORY_STORED` carriers, and (because auto-capture runs post-run in **shadow**) one `MEMORY_STORED` carrier per **proposed** typed item with `proposed_only: true` + `{user_id,key,type,salience}`. **Those shadow carriers, exported to Langfuse, are the Stage-0 trace corpus the Phase-2 calibration codes.** Export them (Langfuse → filter `event=memory.stored` / `proposed_only=true`) and hand the JSONL to the calibration harness (`scripts/eval/memory_extractor_calibrate.py`) — see its `--help`.
