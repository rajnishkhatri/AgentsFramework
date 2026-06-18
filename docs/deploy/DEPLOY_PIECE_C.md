# Deploy Piece C — memory recall/store ON (no-traffic) + thread-table migration

> Companion to [`scripts/deploy_piece_c.sh`](../../scripts/deploy_piece_c.sh). This doc holds the **config changes the script can't make for you** (a Terraform env-var add) and the exact run/rollback sequence. Posture chosen 2026-06-18: **`MEMORY_ENABLED=true` only** (recall+store live; auto-capture stays in shadow) on a **`--tag` no-traffic** revision (prod untouched).

> **Scope note (BFF sidebar is NOT in this deploy).** Piece C ships the **backend** memory deploy + the threads-table migration. Making the chat **sidebar** persist needs a `DATABASE_URL` binding on the `agent-frontend` BFF — but that is **not deploy-ready today** (the only prod `ThreadRepo` uses the Neon HTTP driver, which can't reach the Cloud SQL socket DSN; see §BFF). The BFF stays on the in-memory thread repo until the option-B adapter lands ([`docs/plans/bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md)).

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
# (BFF sidebar persistence is a SEPARATE, not-yet-ready follow-up — see §BFF.)
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

> **Audit gate (plan Verification 4):** after one authenticated from-step-0 run on
> the tag (a "remember" turn + a "recall" turn with the same `user_id`), confirm
> carriers fired (§3d), then run the `governance-trace-audit` skill on that trace.
> See [`docs/reviews/governance_audit_memory_on_2026-06-18.md`](../reviews/governance_audit_memory_on_2026-06-18.md).
> History: the first authed run (2026-06-18, rev `00083-wal`) emitted **zero**
> carriers — root-caused to the `app_prod.py` wiring drop (now fixed); audit was
> blocked on it, not on auth. Re-run on a rebuilt tag before auditing.

## §BFF — the chat sidebar is NOT durable yet (do not bind `DATABASE_URL` on `agent-frontend`)

**⚠ This step is blocked on a code change — do NOT run a bind command here.** The chat
sidebar persists via `selectThreadRepo()` in `frontend/lib/bff/server_composition.ts`,
which runs in the **BFF ring** — in prod the **`agent-frontend` Cloud Run service**
(Cloudflare Pages was removed 2026-06-18; the BFF is on Cloud Run), a **separate
service** from `agent-backend-combined`. The backend's `DATABASE_URL` feeds the
LangGraph checkpointer and does **not** reach the BFF; `agent-frontend` has **no**
`DATABASE_URL` today (verified 2026-06-18), so `selectThreadRepo` falls back to
`InMemoryThreadRepo` and the sidebar doesn't persist across BFF restarts.

**Why you can't just bind the secret (correction to an earlier version of this doc).**
The only prod `ThreadRepo`, `NeonThreadRepo`, is **hard-wired to the Neon HTTP driver**
— [`neon_thread_repo.ts:139`](../../frontend/lib/adapters/thread_store/neon_thread_repo.ts)
calls `neon(databaseUrl)` from `@neondatabase/serverless`, which speaks Neon's
HTTP/WebSocket protocol over a `…neon.tech` URL. It **cannot dial a Cloud SQL
`/cloudsql/` unix socket.** `selectThreadRepo` picks `NeonThreadRepo` whenever
`DATABASE_URL` is set, so binding `database-url` (a Cloud SQL DSN) on `agent-frontend`
— even *with* `--add-cloudsql-instances` — would make the BFF **throw on the first
thread query**. (The earlier "`NeonThreadRepo` opens whatever `DATABASE_URL` it's
handed" claim was wrong; the driver is Neon-specific.)

**What unblocks it: option B.** Add a Cloud SQL–compatible thread repo (`pg` +
`drizzle-orm/node-postgres`) behind `selectThreadRepo`, so a `/cloudsql/` socket DSN
routes to the new driver. Full plan + research basis:
[`docs/plans/bff_cloudsql_thread_repo.plan.md`](../plans/bff_cloudsql_thread_repo.plan.md).
**Once that lands**, the bind below becomes safe:

```bash
# ⚠ DO NOT RUN until the option-B pg adapter is merged (it would crash today).
gcloud run services update agent-frontend \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION \
  --update-secrets="DATABASE_URL=database-url:latest" \
  --add-cloudsql-instances="agent-prod-gcp-dev:us-central1:agent-db"
# (durable form: add the secret env + the cloudsql volume/annotation to
#  agent-frontend in infra/gcp/, mirroring how cloud-run-backend.tf declares
#  them for the backend service.)
```

Until then the sidebar is in-memory only — **the backend deploy alone does not make
threads durable**, and that is the intended Piece C boundary. (The Cloud SQL DB serves
both rings once option B lands; the migration omits the checkpoint tables, IR-NEON-5,
so they coexist.)

> **Local dev caveat:** the same constraint applies — pointing `frontend/.env.local`'s
> `DATABASE_URL` at the Cloud SQL proxy socket won't work with the Neon driver either.
> A real `…neon.tech` URL is the only thing the current driver accepts; otherwise leave
> it unset (in-memory) until option B.

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
