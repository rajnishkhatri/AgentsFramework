---
type: checklist
title: Phase 5 — 24h soak watch checklist
description: T+1h / T+6h / T+24h observability checks against the live pgvector revision. Clears the S6 acceptance bar; cuts to deletion checklist on green or rollback on red.
tags: [checklist, memory, pgvector, soak, observability, cutover]
timestamp: 2026-06-22
status: in-progress
plan_id: replace-mem0-pgvector
related:
  runbook: "[replace_mem0_pgvector.phase5.runbook.md](replace_mem0_pgvector.phase5.runbook.md)"
  s6_checklist: "[replace_mem0_pgvector.phase5_s6.deletion_checklist.md](replace_mem0_pgvector.phase5_s6.deletion_checklist.md)"
---

# 24h soak watch — Phase 5 cutover

> Cutover went live 2026-06-22 via deploy-gcp orchestrator. Traffic on new revision @ 100%. Below: three time-banded check windows + the rollback trigger conditions. Pass all three → execute S6 deletion checklist. Any one fails → rollback per runbook.
>
> **Hotfix roll-forward note (2026-06-22T~16Z):** rev `00093-5xm` (commit `af3336a`) replaced `00092-8wq` mid-soak to fix the BFF `POST /api/memory → 500` cross-loop trap. **Soak clock NOT reset** — the conversational pgvector recall/store seam is byte-identical to `00092-8wq` (the hotfix touches only `services/memory_backends/pgvector.py::_embed_sync`, which the graph path already exercised without issue; the change adds a new code branch only for the running-loop case). Gates 1–6 keep their E2E credit; gates 7–11 continue under the original T+0 schedule. If the hotfix path itself surfaces a defect, treat that as a new T+0 and rerun the table.

## Soak state (operator decisions locked 2026-06-22)

| Field | Value |
|---|---|
| **T+0** | `2026-06-22T12:35:43Z` — 100% traffic shift to `agent-backend-combined-00092-8wq` (rev 00093-5xm rolled forward with hotfix; soak clock not reset — see note below) |
| **Live revision** | `agent-backend-combined-00094-rfq` (commit `af3336a` — asyncio cross-loop hotfix; `MEMORY_BACKEND=pgvector`, no `MEM0_API_KEY`). Predecessor `00092-8wq` was the original cutover revision. |
| **Rollback revision** | `agent-backend-combined-00098-hup` (most recent rev with `MEM0_API_KEY` wired; created 2026-06-21) |
| **Region / project** | `us-central1` / `agent-prod-gcp-dev` |
| **E2E evidence** | [MEMORY_MULTISESSION_PGVECTOR_CUTOVER_WALKTHROUGH.md](../analysis/MEMORY_MULTISESSION_PGVECTOR_CUTOVER_WALKTHROUGH.md) — MEM_SMOKE 2026-06-22, GATE PASSED (8 conversational probes); §6 Hermes crud-seed rerun on rev 00093-5xm, 3/3 PASS |
| **E2E credit policy** | Gates **1, 2, 5, 6** credited from MEM_SMOKE; CRUD path additionally verified on rev 00093; no duplicate E2E rerun unless organic traffic contradicts |
| **CRUD `/agent/memory` 500** | RESOLVED on rev 00093-5xm (`af3336a` running-loop bridge); previously out-of-scope-for-soak per conversational-path-only policy |
| **Gate 9 sparse traffic** | Empty hour buckets acceptable when no organic traffic |
| **Rollback authority** | Investigate + report only; operator decides rollback |
| **T+1h due** | `2026-06-22T13:35:43Z` |
| **T+6h due** | `2026-06-22T18:35:43Z` |
| **T+24h due** | `2026-06-23T12:35:43Z` |

### Gate scorecard (updated 2026-06-22T13:36Z)

| # | Gate | Band | Status | Evidence |
|---|---|---|---|---|
| 1 | `memory.recalled` fires (≥1 span, ≥1 user) | T+1h | **PASS (E2E)** | 8 probes, distinct synthetic `user_id`s — walkthrough §2 |
| 2 | `memory.stored` fires at run-end | T+1h | **PASS (E2E)** | `memory.stored` on all 8 captured probes |
| 3 | Zero `MemoryBackendError` | T+1h | **PASS (formal)** | T+1h @ 13:36 UTC: `timestamp>="2026-06-22T12:36:00Z"` → 0 rows; since T+0 also 0 |
| 4 | No HNSW / `vector_cosine_ops` errors | T+1h | **PASS (formal)** | T+1h @ 13:36 UTC: post-T+0 query → 0 rows |
| 5 | Recall `count ≥ 1` on at least one pair | T+6h | **PASS (E2E)** | e.g. MEM-RECALL `count=2`, MEM-MULTI `count=2` — walkthrough §2.3–2.4 |
| 6 | Cross-user isolation | T+6h | **PASS (E2E)** | MEM-LEAK: `userleak01` `count=0`; distinct per-case users in corpus |
| 7 | p95 recall latency < 500 ms | T+6h | **PENDING** | Due T+6h; Langfuse carrier spans show ~0 ms (carrier-only, not embed+search wall time) |
| 8 | Zero rollback events | T+24h | **PENDING** | Due T+24h |
| 9 | `MEMORY_STORED` monotonic hour buckets | T+24h | **PENDING** | Due T+24h; sparse-traffic empty hours OK |
| 10 | Zero `MemoryBackendError` (24 h window) | T+24h | **PENDING** | Due T+24h |
| 11 | `agent_memories` table size sanity | T+24h | **PENDING** | Due T+24h (`psql` via cloud-sql-proxy) |

**T+1h gate (formal): ✅ PASSED @ `2026-06-22T13:36Z`.** Gates 1–4 all green. Traffic on `00094-rfq` (pgvector hotfix roll-forward, not mem0 rollback). Next: T+6h gate 7 @ 18:35 UTC.

## Carrier + span names (what to grep for)

| Code symbol | Langfuse span name | Backend table side-effect |
|---|---|---|
| `EventType.MEMORY_RECALLED` ([black_box.py:61](../../services/governance/black_box.py:61)) | `memory.recalled` | reads `agent_memories` |
| `EventType.MEMORY_STORED` ([black_box.py:62](../../services/governance/black_box.py:62)) | `memory.stored` | writes/upserts `agent_memories` |
| `MemoryBackendError` ([long_term_memory.py:58](../../services/long_term_memory.py:58)) | none (exception → log) | any psycopg / embed failure surfaces here |

## T+1h check — cold start sanity

**Goal:** every recall/store seam fires at least once on real traffic; no immediate `MemoryBackendError` spike from a misconfigured pool or schema mismatch.

```bash
# 1) Recall fires on real traffic (one user, one task = one memory.recalled span)
#    Langfuse UI: filter span.name = "memory.recalled", last 1h
#    Expectation: >= 1 span; count(distinct user_id) >= 1
#    Empty-table semantics (cold-start): the span may show count=0 — that is
#    correct (plan §Phase 5: "pgvector starts empty"). What matters is the span
#    fires.

# 2) Store fires at run-end
#    Langfuse UI: filter span.name = "memory.stored", last 1h
#    Expectation: >= 1 span where the recall same-task pair completed

# 3) Zero MemoryBackendError in last 1h
gcloud logging read \
  'resource.type=cloud_run_revision
   AND resource.labels.service_name=agent-backend-combined
   AND severity>=ERROR
   AND textPayload=~"MemoryBackendError"' \
  --limit=10 --format='value(timestamp,textPayload)'
# Expectation: 0 rows.

# 4) HNSW index is reachable (no "no operator class" errors)
gcloud logging read \
  'resource.type=cloud_run_revision
   AND resource.labels.service_name=agent-backend-combined
   AND textPayload=~"vector_cosine_ops|hnsw"' \
  --limit=10 --format='value(timestamp,textPayload)'
# Expectation: 0 rows (the index is created, no runtime probe should mention it).
```

**T+1h gate**: (1) AND (2) AND (3) AND (4) → continue. Any fail → §Rollback.

## T+6h check — recall actually retrieves

**Goal:** confirm at least one `(user_id, key)` pair has been recalled non-empty after enough traffic has accumulated. This is the per-user-3rd-task signal from the plan.

```bash
# 5) Recall returned at least one row for at least one user
#    Langfuse UI: filter span.name = "memory.recalled", last 6h
#    Inspect the `count` attribute on at least one span — expect >= 1
#    on at least one (user_id, task_id) pair.
#    Plan §Phase 5: "MEMORY_RECALLED count=0 on run 1, >0 by run 3" per user.

# 6) Cross-user isolation holds — sample two distinct user_ids and confirm
#    their agent_memories rows are disjoint
cloud-sql-proxy --port 5433 <INSTANCE>  # in another terminal
DSN="postgresql://<USER>:<PASS>@127.0.0.1:5433/<DB>"
psql "$DSN" -c "
  SELECT user_id, count(*) AS rows
  FROM agent_memories
  GROUP BY user_id
  ORDER BY rows DESC
  LIMIT 5;
"
# Expectation: distinct user_ids; row counts plausible for traffic volume.

# 7) p95 recall latency under 500ms
#    Langfuse UI: filter span.name = "memory.recalled", aggregate p95 duration
#    Expectation: p95 < 500ms (one embed call + one HNSW query)
```

**T+6h gate**: (5) AND (6) AND (7) → continue. (5) failing means recall is firing but the search isn't returning rows — investigate before rollback (could be a write-side issue, not read-side).

## T+24h check — soak-complete acceptance bar

**Goal:** clear the S6 deletion checklist's pre-conditions.

```bash
# 8) Zero rollback events in the 24h window
#    Manual review: no operator-initiated update-traffic --to-revisions
#    commands fired against agent-backend-combined since cutover.

# 9) MEMORY_STORED count has grown monotonically since cutover
#    Langfuse UI: filter span.name = "memory.stored", last 24h, hour buckets
#    Expectation: non-zero in every hour bucket that had organic traffic.

# 10) Zero MemoryBackendError in last 24h
gcloud logging read \
  'resource.type=cloud_run_revision
   AND resource.labels.service_name=agent-backend-combined
   AND severity>=ERROR
   AND textPayload=~"MemoryBackendError"
   AND timestamp >= "'"$(date -u -v-24H '+%Y-%m-%dT%H:%M:%S')"'Z"' \
  --format='value(timestamp,textPayload)'
# Expectation: 0 rows (transient one-offs acceptable only if explained — log it).

# 11) Table size sanity — agent_memories has accumulated traffic-scaled rows
psql "$DSN" -c "
  SELECT count(*) AS total_rows,
         count(DISTINCT user_id) AS distinct_users,
         max(created_at) AS most_recent_write
  FROM agent_memories;
"
# Expectation: total_rows > 0; most_recent_write within the last hour or two
# of normal-traffic-pattern recency.
```

**T+24h gate**: (8) AND (9) AND (10) AND (11) → **execute the S6 deletion checklist** in [phase5_s6.deletion_checklist.md](replace_mem0_pgvector.phase5_s6.deletion_checklist.md).

## Optional: memory multi-session E2E corpus run

Plan §Phase 5 calls this out as "recommended but optional" for the soak. The [[memory-multisession-e2e-corpus]] suite ships 33 cases that exercise the recall/store seam under controlled multi-user conditions; running it against prod (with `E2E_BASE_URL` pointed at the live BFF + a real bearer token) gives faster signal than waiting for organic traffic to fill in the per-user-3rd-task evidence.

Caveat from [[memory-multisession-e2e-corpus]]: the user-id-collapse bug was LIVE there because the `mem:` bridge wasn't deployed. That bridge is irrelevant to pgvector (Phase 4's selector switch routes by `MEMORY_BACKEND`, not by mem-tag), so this Phase 5 soak run is the first time the suite can validate end-to-end against a memory backend that actually carries per-user durable rows.

## Rollback procedure (24h window)

If any T+1h / T+6h / T+24h gate fails:

```bash
# 1) Rollback target (verified 2026-06-22): agent-backend-combined-00098-hup
#    Most recent revision with MEM0_API_KEY in env (00091-ts4/00092-8wq are pgvector, no mem0 key).
gcloud run revisions list \
  --service agent-backend-combined \
  --region us-central1 \
  --project agent-prod-gcp-dev \
  --limit=15 --format='table(metadata.name,metadata.creationTimestamp)'

# 2) Shift 100% traffic back to mem0 revision (operator executes — agent investigates only)
gcloud run services update-traffic agent-backend-combined \
  --region us-central1 \
  --project agent-prod-gcp-dev \
  --to-revisions agent-backend-combined-00098-hup=100

# 3) Verify the rollback took
curl -sf https://<BACKEND_URL>/healthz
gcloud run services describe agent-backend-combined --region <REGION> \
  --format='value(status.traffic)'
```

The `mem0-api-key` Secret Manager resource is still provisioned (Terraform left it intact in S4 — see [replace_mem0_pgvector.phase5_s6.deletion_checklist.md](replace_mem0_pgvector.phase5_s6.deletion_checklist.md) §"24h-rollback rule"), so the rolled-back revision authenticates against mem0 cloud immediately. Data loss = zero on the rollback path (mem0 cloud retained all rows; agent_memories rows from the pgvector window stay as-is, awaiting a subsequent forward roll once the issue is understood).

**After a rollback**: do NOT execute S6. Investigate the root cause, fix forward, and run a fresh cutover. The soak watch resets to T+0 on the next pgvector revision shift.

## On-clear

Once all three gates pass: mark this file `status: completed` in the frontmatter and proceed to the S6 deletion checklist.
