# Deploy Piece C — persistent Neon ThreadStore + memory recall/store ON (no-traffic)

> Companion to [`scripts/deploy_piece_c.sh`](../../scripts/deploy_piece_c.sh). This doc holds the **config changes the script can't make for you** (a Terraform env-var add + the BFF secret-binding) and the exact run/rollback sequence. Posture chosen 2026-06-18: **`MEMORY_ENABLED=true` only** (recall+store live; auto-capture stays in shadow) on a **`--tag` no-traffic** revision (prod untouched).

## TL;DR

```bash
# 0. one config edit (see §1) — add MEMORY_ENABLED to the Cloud Run env block
# 1. run the script (does tofu apply → pull DATABASE_URL → migrate → tag deploy)
GCP_PROJECT_ID=agent-prod-gcp-dev-XXXX bash scripts/deploy_piece_c.sh
# 2. verify backend selection + exercise the tag URL (§3)
# 3. wire the BFF separately (§BFF) so the chat sidebar persists too
# 4. promote when satisfied (§4); rollback is one command (§5)
```

---

## 1. Config update — add `MEMORY_ENABLED` to the Cloud Run env block (Terraform)

`DATABASE_URL` and `MEM0_API_KEY` are **already** mapped in `infra/dev-tier/cloud-run.tf` (secret refs at lines ~205/215), so `tofu apply` wires the durable Mem0 backend + the checkpointer DB on its own. The **only** missing piece is the memory flag. Add this env block alongside the other plain envs (next to `MEM0_BASE_URL`, ~line 144 of `cloud-run.tf`):

```hcl
      env {
        name  = "MEMORY_ENABLED"
        value = "true"
      }
      # NOTE: MEMORY_AUTOCAPTURE_ENABLED is intentionally NOT set here — it
      # defaults to false (shadow). Write-back is gated on the Phase-2 eval
      # calibration clearing the Stage-6 enable-policy. Do not add it until then.
```

> **Why TF and not just `gcloud --update-env-vars`?** The script *also* passes `--update-env-vars=MEMORY_ENABLED=true` so the no-traffic tag works even before this edit lands. But putting it in TF makes it durable across the next `tofu apply` (a gcloud-only override is wiped by the next apply). Land the TF edit so the flag survives; the gcloud flag is the belt-and-suspenders for the immediate tag.

After the edit, run `cd infra/dev-tier && tofu validate` (the layering/policy tests are credential-free).

## 2. Run the deploy script

```bash
GCP_PROJECT_ID=agent-prod-gcp-dev-XXXX \
GCP_REGION=us-central1 \
bash scripts/deploy_piece_c.sh
```

It runs: `tofu init/plan/terraform-compliance/apply` → pulls `DATABASE_URL` from the `neon-database-url` secret (never printed) → `psql … -f 0000_init_threads.sql` → `gcloud run deploy agent-middleware --tag mem --no-traffic … MEMORY_ENABLED=true` → smoke-checks `/healthz` on the tag URL. **Prod traffic stays on the current revision throughout.**

## 3. Verify (after the script)

```bash
# (a) durable backend selected? — the composition root logs this at boot
gcloud run services logs read agent-middleware \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION | grep "memory backend"
#   expect:  memory backend: mem0 (durable)

# (b) threads table exists + is empty
psql "$(gcloud secrets versions access latest --secret=neon-database-url)" \
  -c "SELECT count(*) FROM threads;"

# (c) memory roundtrip against the TAG url (bearer auth), then restart-survives:
#     POST /agent/memory  →  GET /agent/memory  →  redeploy tag  →  GET again (still there)
```

## §BFF — the chat sidebar needs `DATABASE_URL` too (separate binding)

**This is the gotcha.** `selectThreadRepo()` is called in `frontend/lib/bff/server_composition.ts`, which runs in the **BFF ring** (Cloudflare Pages), *not* the `agent-middleware` Cloud Run service. So:

- The Cloud Run `DATABASE_URL` (set above) feeds the **LangGraph checkpointer** — it does **not** reach the BFF.
- For `NeonThreadRepo` to activate (threads persist in the sidebar), the **BFF** must also see `DATABASE_URL`.

Cloudflare Pages takes **non-secret** env in `cloudflare-pages.tf`; a connection string is a secret, so bind it as a **Pages secret**, not a plain env var:

```bash
# Pull the value, then set it as an ENCRYPTED Pages env var (production env).
DBURL="$(gcloud secrets versions access latest --secret=neon-database-url)"
# Dashboard: Workers & Pages → <pages-project> → Settings → Environment variables
#   → Add → type "Secret" → name DATABASE_URL → paste $DBURL → Production
# (or via API/wrangler: wrangler pages secret put DATABASE_URL --project-name <name>)
```

Until the BFF has `DATABASE_URL`, `selectThreadRepo` falls back to `InMemoryThreadRepo` and the sidebar won't persist across BFF restarts — **the Cloud Run deploy alone does not make threads durable**. (The same Neon DB serves both; the migration omits the checkpoint tables, IR-NEON-5, so they coexist.)

> **Local dev equivalent:** `echo "DATABASE_URL=$DBURL" >> frontend/.env.local` (git-ignored).

## 4. Promote (when satisfied)

```bash
gcloud run services update-traffic agent-middleware --to-tags=mem=100 \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION
```

## 5. Rollback

```bash
# memory flag off → instant return to no-recall/no-store (graph shape unchanged)
gcloud run services update-traffic agent-middleware --to-latest \
  --project=$GCP_PROJECT_ID --region=$GCP_REGION   # if you promoted, point back
# or just leave the tag un-promoted — prod never moved.
# DATABASE_URL / the migration are additive + safe to leave (threads table is
# unused until the BFF binding lands).
```

## What this unblocks for the Phase-2 eval (the other parallel track)

Running with `MEMORY_ENABLED=true` makes the loop emit `MEMORY_RECALLED`/`MEMORY_STORED` carriers, and (because auto-capture runs post-run in **shadow**) one `MEMORY_STORED` carrier per **proposed** typed item with `proposed_only: true` + `{user_id,key,type,salience}`. **Those shadow carriers, exported to Langfuse, are the Stage-0 trace corpus the Phase-2 calibration codes.** Export them (Langfuse → filter `event=memory.stored` / `proposed_only=true`) and hand the JSONL to the calibration harness (`scripts/eval/memory_extractor_calibrate.py`) — see its `--help`.
