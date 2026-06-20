---
type: runbook
title: 'Walkthrough — one authenticated memory run on the `mem` tag → trace fetch → governance audit'
description: '/run/stream verifies a real WorkOS RS256 JWT against WorkOS''s live JWKS'
tags: [deploy]
---

# Walkthrough — one authenticated memory run on the `mem` tag → trace fetch → governance audit

> Goal: get **one** authenticated run through the memory-ON backend that emits
> `memory.recalled` + `memory.stored` carriers, then fetch its Langfuse trace and
> run the four-pillar governance audit. This is the single thing gating the
> governance audit, the Phase-2 shadow corpus, and the calibration run.
>
> Companion to [`DEPLOY_PIECE_C.md`](DEPLOY_PIECE_C.md). The deploy itself is already
> done (`mem` tag on `agent-backend-combined`, rev `00083-wal`, `MEMORY_ENABLED=true`,
> `--no-traffic`). What's missing is **one authenticated exercise** — the only hit so
> far was a 401.

---

## The auth reality (why you can't just `curl` with a fake token)

`/run/stream` verifies a **real WorkOS RS256 JWT** against WorkOS's live JWKS
([`workos_jwt_verifier.py:149`](../../middleware/adapters/auth/workos_jwt_verifier.py)):
it checks the signature, `iss`, `exp`, and `expected_client_id`. **There is no
local-mint path and no dev bypass in prod.** So the token must be issued by WorkOS.

Two ways to get one:
- **Path A (recommended): drive the run through the deployed frontend UI**, which logs
  you in via WorkOS and forwards the token automatically. You just point the BFF at the
  `mem` tag for one session.
- **Path B (raw curl): extract a live WorkOS access token from a logged-in browser
  session** and call the tag URL directly. More control, but the token is short-lived.

Both produce the same carriers. Pick A unless you specifically want the curl.

---

## Prerequisites (once)

```bash
export PROJECT=agent-prod-gcp-dev
export REGION=us-central1

# Resolve the mem tag URL (don't hardcode the hash — it changes per deploy):
TAG_URL="$(gcloud run services describe agent-backend-combined \
  --project="$PROJECT" --region="$REGION" \
  --format='value(status.traffic)' | tr ';' '\n' | grep -i 'mem' | grep -oE 'https://[^ ,]+' | head -1)"
echo "mem tag URL: $TAG_URL"
# Expected form: https://mem---agent-backend-combined-<hash>-uc.a.run.app
```

Pick a **stable `user_id`/thread** so the recall turn can find the remember turn.
Memory is namespaced by `identity.owner` (the JWT `sub`), so both turns MUST use the
**same logged-in user**. The thread_id only needs to be stable enough to be one logical
conversation; a fresh uuid per turn is fine because recall is cross-thread (per-user),
but using one thread keeps it simple.

```bash
export MEM_THREAD="mem-audit-$(date +%Y%m%d-%H%M)"
```

---

## Path A — through the frontend UI (recommended)

The frontend's BFF (`agent-frontend`) forwards your WorkOS token to whatever
`MIDDLEWARE_URL` it has. To make ONE session hit the memory backend, point a
throwaway frontend revision's `MIDDLEWARE_URL` at the `mem` tag (no-traffic, so prod
is untouched), log in, and chat.

### A1. Spin a no-traffic frontend revision pointed at the mem tag

```bash
gcloud run deploy agent-frontend \
  --project="$PROJECT" --region="$REGION" \
  --image="$(gcloud run services describe agent-frontend --project=$PROJECT --region=$REGION --format='value(spec.template.spec.containers[0].image)')" \
  --tag=memui --no-traffic \
  --update-env-vars="MIDDLEWARE_URL=${TAG_URL}" \
  --quiet
# Reuses the CURRENT frontend image; only MIDDLEWARE_URL differs. --no-traffic +
# --tag memui = prod frontend URL is untouched; you reach this via the memui tag URL.

MEMUI_URL="$(gcloud run services describe agent-frontend \
  --project=$PROJECT --region=$REGION \
  --format='value(status.traffic)' | tr ';' '\n' | grep -i 'memui' | grep -oE 'https://[^ ,]+' | head -1)"
echo "open this in a browser: $MEMUI_URL"
```

> If WorkOS rejects the login redirect on the `memui---…` host (callback-URL
> allow-list), add that tag URL to the WorkOS AuthKit redirect URIs, OR use Path B.

### A2. Do the remember-turn, then the recall-turn

In the browser at `$MEMUI_URL`, log in (WorkOS), then send **two** messages in the
**same** chat:

1. **Remember turn:** `Remember that I prefer all measurements in metric units.`
2. **Recall turn** (same session, same user): `What measurement units do I prefer?`

The second turn should recall the first. Watch for the recall indicator ("Recalled N
memories") if the UI surfaces it. Note the approximate wall-clock time — you'll use it
as the `--since` filter when fetching the trace.

```bash
export RUN_SINCE="$(date -u -v-10M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)"
echo "fetch traces since: $RUN_SINCE"
```

### A3. Tear down the throwaway frontend tag (after the trace is captured)

```bash
gcloud run services update-traffic agent-frontend --remove-tags=memui \
  --project=$PROJECT --region=$REGION
```

---

## Path B — raw curl with a captured WorkOS token

### B1. Get a live WorkOS access token

Log into the real frontend in a browser, open DevTools → Network, trigger any
authenticated action (send a chat message), find the request to `/api/run/stream`,
and copy the token. The BFF reads it via `getAccessToken()`
([`run/stream/route.ts:39`](../../frontend/app/api/run/stream/route.ts)); depending on
the AuthKit setup it's in the session cookie or a forwarded header. Easiest: in the
Network tab, the **upstream** call isn't visible (server-side), so instead grab it from
the WorkOS session — e.g. a `/api/auth/token`-style route if present, or decode the
session cookie. If your AuthKit exposes the access token to the client, copy it there.

```bash
export WORKOS_JWT='eyJ...'   # the real RS256 access token (short-lived, ~minutes)
# Sanity: it must be a 3-part JWT and NOT expired. Peek at the payload (no secret):
python3 -c "import base64,json,sys; p=sys.argv[1].split('.')[1]; print(json.dumps(json.loads(base64.urlsafe_b64decode(p+'=='*(-len(p)%4))),indent=2))" "$WORKOS_JWT"
# Confirm: 'sub' (your user id), 'iss' contains workos, 'exp' in the future.
```

### B2. Remember turn → recall turn (same `sub`, same thread)

```bash
# Remember
curl -sN -X POST "${TAG_URL}/run/stream" \
  -H "Authorization: Bearer ${WORKOS_JWT}" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "{\"thread_id\":\"${MEM_THREAD}\",\"input\":{\"messages\":[{\"role\":\"user\",\"content\":\"Remember that I prefer all measurements in metric units.\"}]}}" \
  | sed -n '1,40p'

# (If the token expired between turns, re-capture it.)

# Recall (same thread, same user)
curl -sN -X POST "${TAG_URL}/run/stream" \
  -H "Authorization: Bearer ${WORKOS_JWT}" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "{\"thread_id\":\"${MEM_THREAD}\",\"input\":{\"messages\":[{\"role\":\"user\",\"content\":\"What measurement units do I prefer?\"}]}}" \
  | sed -n '1,80p'
```

The body shape is exactly what the BFF sends: `{ thread_id, input: { messages:
[{role, content}] } }`. `build_run_stream_context`
([`run_stream_context.py:42`](../../middleware/run_stream_context.py)) reads
`input.messages[-1].content` as the task. A `200` SSE stream (events flowing) = success;
a `401` = bad/expired token.

```bash
export RUN_SINCE="$(date -u -v-10M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)"
```

---

## Step 2 — fetch the trace

`scripts/fetch_memory_trace.py` (read-only) queries Langfuse for the most recent
`memory.recalled` / `memory.stored` carrier and dumps that trace's observation array —
exactly the shape the audit skill consumes. It reads `LANGFUSE_*` from `.env`.

```bash
cd /Users/rajnishkhatri/Documents/AgentsFramework/agent
.venv/bin/python scripts/fetch_memory_trace.py --since "$RUN_SINCE"
```

Outcomes:
- **Exit 0** → prints `{"trace_id": ..., "out": "/tmp/memory_trace_<id8>.json",
  "memory_carriers": ["memory.recalled","memory.stored"]}`. Note the `out` path.
- **Exit 2** ("no carriers") → the run didn't emit memory carriers. Most likely causes:
  the run hit prod (not the `mem` tag), `MEMORY_ENABLED` wasn't on, the two turns used
  different users, or Langfuse hasn't ingested yet (wait ~30–60s and retry). Confirm the
  tag actually served the run:
  ```bash
  gcloud run services logs read agent-backend-combined --project=$PROJECT --region=$REGION \
    --limit=200 | grep -iE "memory backend|memory.recalled|memory.stored|MEMORY_ENABLED"
  ```
- If you already know the exact `trace_id` (e.g. from an SSE event), skip discovery:
  `.venv/bin/python scripts/fetch_memory_trace.py --trace-id <ID>`.

---

## Step 3 — run the governance audit

The skill ([`docs/skills/governance-trace-audit/SKILL.md`](../skills/governance-trace-audit/SKILL.md))
audits the trace JSON against the four pillars (Recording / Identity / Validation /
Reasoning), corrupt-success check first, and writes a verdict report.

Two ways to invoke it:
- **In Claude Code:** ask me to "run the governance-trace-audit skill on
  `/tmp/memory_trace_<id8>.json`" — I'll load the skill and produce the report.
- **The acceptance bar** the audit must clear for this work
  (from `memory_layer_wiring.plan.md` Verification 4):
  - `memory.recalled` (count, query_len) and `memory.stored` (key) carriers **present**;
    **content absent** (privacy check).
  - Four-pillar verdict **COMPLIANT** (or COMPLIANT-WITH-FINDINGS only for pre-existing
    run-level findings — never a new memory-induced FAIL).
  - `identity.owner` on the memory carriers == the run subject (no cross-user leak).
  - No `source:"carrier_gate"` / `would_enforce:true` alert attributable to memory.

The report lands at `docs/reviews/governance_audit_<wf8>_<date>.md`. Update
[`docs/reviews/governance_audit_memory_on_2026-06-18.md`](../reviews/governance_audit_memory_on_2026-06-18.md)
from PENDING → the real verdict, and flip Verification 4 in the plan.

---

## After this run

- This same trace is the **first row of the Phase-2 shadow corpus** (the deploy also
  emits one `memory.stored` per *proposed* typed item with `proposed_only:true`). Keep
  exercising the tag to grow toward the ≥100 shadow traces the calibration needs
  (`04_calibration_runbook.md` Stage 0).
- Tear down any throwaway tags (`memui` on the frontend) once the trace is captured.

---

## Quick failure map

| Symptom | Cause | Fix |
|---|---|---|
| `401` on `/run/stream` | missing/expired/wrong-audience token | re-capture a fresh WorkOS token; confirm `exp` in the future + `iss` is workos |
| stream returns 200 but `fetch_memory_trace.py` exits 2 (no carriers) | **most likely the stale-image trap:** the tag's image predates the `app_prod.py` memory-wiring fix → graph built memory-blind (recall/store never ran). Also possible: hit prod not the tag; two different users; or Langfuse ingest lag. | grep backend logs for `memory.recall`/`memory.store` (DEPLOY_PIECE_C §3d) — **zero lines = memory-blind graph, rebuild + redeploy the tag with a current-HEAD image**; else confirm `$TAG_URL`/one login; wait 30–60s for Langfuse |
| `fetch_memory_trace.py` 429-storms / exits 2 mid-scan | Langfuse public API rate limit (Hobby = 1000 req/min, per-org); the fallback trace-scan bursts | not a real "no carriers" verdict — corroborate with Cloud Logging (§3d); wait ~60s and re-run name-query; don't trust exit-2 during a 429 storm |
| recall turn doesn't recall | different `sub` between turns, or store hadn't completed | same user both turns; the store fires at run-end, so do them sequentially |
| WorkOS login fails on the `memui` tag host | callback URL not allow-listed | add the tag URL to WorkOS AuthKit redirect URIs, or use Path B |
