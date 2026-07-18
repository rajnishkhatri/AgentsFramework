---
type: design
title: 'Eng-Coach AWS — Stack A (lean), Stack B (HA), and A→B transition'
description: >
  Sibling to eng-coach-aws-deploy.brainstorm.md. Locks the two deploy postures
  chosen after Stage-1 review: Stack A (App Runner + Neon, ~$35–70/mo IaaS) for
  <50 customers, Stack B (Fargate + ALB + RDS Multi-AZ, ~$230–270/mo) for HA /
  minimal downtime, plus flip triggers and the phased A→B migration. Whole stack
  on AWS; Tauri macOS + Capacitor iOS + browser share one BFF origin.
related:
  - docs/plan/eng-coach-aws-deploy.brainstorm.md
  - docs/Architectures/CLOUD_PROVIDER_COMPARISON.md
  - docs/analysis/CLOUD_COMPARISON_PYRAMID_ANALYSIS.md
  - docs/adr/0001-native-shell-tauri-capacitor.md
  - infra/gcp/
status: draft
timestamp: 2026-07-14
---

# Eng-Coach AWS — Stack A (lean), Stack B (HA), and A→B transition

Sibling to [eng-coach-aws-deploy.brainstorm.md](eng-coach-aws-deploy.brainstorm.md).
Captures the post-review posture: **whole stack on AWS** (Next BFF + combined
Python backend), clients = browser / **Tauri 2** (macOS) / **Capacitor 7** (iOS)
all loading one BFF `PROD_URL`. No EFS — ephemeral `/tmp` + S3. Langfuse + WorkOS
stay external SaaS. LLM spend excluded from IaaS totals.

**Anchors:** `infra/gcp/*.tf` (live shape), `CLOUD_PROVIDER_COMPARISON.md` §4,
brainstorm directions D1 / D2 / D4.

---

## Component map (A vs B)

| Component | Stack A (lean) | Stack B (HA) |
|---|---|---|
| **Frontend / BFF** | App Runner (Next.js) | ECS Fargate + ALB (`min≥1`) |
| **Backend (combined)** | App Runner (middleware + agent) | ECS Fargate + ALB (`min≥1`), multi-container task |
| **SearXNG** | Sidecar if supported; else sibling App Runner | 2nd container in same Fargate task |
| **Ingress / SSE** | App Runner HTTPS (must clear 3600s) | ALB idle timeout ≥ 3600s |
| **Postgres** | Neon (pgvector) | RDS Multi-AZ (or Aurora) + pgvector |
| **DB HA / backups** | Neon plan backups | Multi-AZ failover + PITR + deletion protection ON |
| **AgentFacts** | S3 (versioned) | S3 (versioned) — same |
| **Trust traces** | S3 + lifecycle; in-process relay | S3 + lifecycle; in-process relay — same |
| **Offload / BlackBox disk** | `/tmp` (no EFS) | `/tmp` (no EFS) — same |
| **Secrets** | SSM (prefer) or Secrets Manager | Secrets Manager (or SSM) |
| **Images** | ECR | ECR — same |
| **Meta / eval** | Off by default | EventBridge → ECS task; off by default |
| **Observability** | Langfuse + basic CloudWatch | Langfuse + CloudWatch (5xx, p95, DB conns) + budget |
| **Auth** | WorkOS on BFF | WorkOS on BFF — same |
| **Clients** | Browser / Tauri / Capacitor → one FE URL | Same → one FE URL |
| **IaaS (approx.)** | ~$35–70/mo | ~$230–270/mo |

---

## 1. Stack A — Lean (<50 customers)

**Goal:** Lowest fixed IaaS while proving AWS + adapters. Cold starts and
single-AZ/SaaS DB acceptable.

**IaaS band:** ~**$35–70/mo** (or ~**$75–120** if App Runner fails the SSE gate
and compute moves to Fargate+ALB early — still Neon).

### 1.1 Topology

```text
Browser / Tauri / Capacitor
        │ HTTPS
        ▼
┌─────────────────────────┐
│ App Runner — Frontend   │  Next.js BFF (WorkOS, SSE proxy, 3600s)
│ (scale-to-zero-ish)     │
└───────────┬─────────────┘
            │ MIDDLEWARE_URL (same region)
            ▼
┌─────────────────────────┐
│ App Runner — Backend    │  middleware + agent + SearXNG sidecar*
│ (combined service)      │
└───────────┬─────────────┘
            │
    ┌───────┼────────┬────────────┐
    ▼       ▼        ▼            ▼
  Neon    S3 facts  S3 traces   Secrets
 (PG+     (Agent-   (BlackBox   (SSM or
 pgvector) Facts)    JSONL)      SM)
```

\*If App Runner cannot run a true sidecar, SearXNG becomes a second App Runner
service or compute flips to Fargate earlier (see §1.4).

### 1.2 Config notes

| Piece | Choice | Notes |
|---|---|---|
| Frontend | **App Runner** | Next standalone image; long SSE proxy; env: `MIDDLEWARE_URL`, WorkOS secrets only |
| Backend | **App Runner** | Combined `app_prod` image; request timeout posture **3600s** |
| Postgres | **Neon** (D4) | Same vendor story as retired `infra/dev-tier/`; pgvector; Free/Launch |
| AgentFacts | **S3** | Versioning on; role-scoped `s3:GetObject` / put as needed |
| Trust traces | **S3** + lifecycle | Mirror Nearline→IA; `BLACKBOX_RELAY_MODE=in_process` |
| Offload | **`/tmp`** | `AGENT_OFFLOAD_DIR=/tmp/agent_offload` — **no EFS** |
| Secrets | **SSM** (prefer) or Secrets Manager | FE role = WorkOS only |
| Images | **ECR** | `frontend` + `backend` (+ `searxng` if separate) |
| Meta/eval | **Off** by default | EventBridge later |
| Auth | WorkOS @ BFF | Redirect URI = FE App Runner URL; desktop/iOS deep-link pattern unchanged |

### 1.3 Runtime invariants (A)

1. SSE path: client → FE → BE; both must clear **3600s**.
2. BFF holds **no** DB/LLM cloud creds — Bearer forward only.
3. Cloud SDK changes stay in the **4-adapter + composition-root** surface
   (checkpointer, S3 facts, S3/trace sink, identity).
4. Tauri/Capacitor `PROD_URL` = FE App Runner URL.

### 1.4 Kill-criteria / fallbacks (A)

| Risk | Action |
|---|---|
| App Runner SSE/timeout < 3600s | Move FE+BE to **Fargate + ALB**; **keep Neon** (intermediate **A′**) |
| SearXNG sidecar unsupported | Second service or Fargate multi-container task |
| Neon connection storms | Pooler URL; RDS Proxy when on B |

### 1.5 What A does **not** buy

- Multi-AZ automatic DB failover
- Guaranteed no cold-start on first SSE
- AWS-native DB consolidation
- RDS-class PITR + deletion-protection story

### 1.6 Cost snapshot (A)

| Line | ~$/mo |
|---|---|
| App Runner FE + BE (idle-heavy) | $20–40 |
| Neon Free/Launch | $0–19 |
| S3 + ECR + secrets + logs | $2–8 |
| **Total** | **~$35–70** |

**Reference:** staying on GCP Tier A remains ~**$12–35/mo**
(`CLOUD_PROVIDER_COMPARISON.md` §4.1) if AWS is not required yet.

---

## 2. Stack B — HA / minimal downtime

**Goal:** Customer data durability, AZ failover, no cold-start prod UX, room to scale.

**IaaS band:** ~**$230–270/mo** list (Tier-B-like from the pyramid study, **no EFS**).

### 2.1 Topology

```text
Browser / Tauri / Capacitor
        │ HTTPS
        ▼
┌──────────────────────────────┐
│ ALB (idle timeout ≥ 3600s)   │
│  ├ target: FE Fargate (min≥1)│
│  └ target: BE Fargate (min≥1)│  ← or two ALBs; one ALB + host rules OK
└───────────────┬──────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
   FE tasks          BE tasks
   (Next BFF)     (agent+SearXNG
                  multi-container
                  task def)
        │                │
        └───────┬────────┘
                ▼
     RDS Multi-AZ PostgreSQL
     (+ pgvector; PITR; deletion
      protection ON)
                │
        S3 facts / S3 traces
        Secrets Manager
        ECR · CloudWatch · Budgets
```

**Optional inside B:** **Aurora** (provisioned or Serverless v2) instead of RDS
Multi-AZ — same HA intent, better scale lever; similar or slightly higher $ at
small size.

### 2.2 Config notes

| Piece | Choice | Notes |
|---|---|---|
| Frontend | **ECS Fargate** + ALB | `min_instances ≥ 1`; 3600s; WorkOS-only task role |
| Backend | **ECS Fargate** + ALB | `min_instances ≥ 1`; multi-container (app + SearXNG) |
| Postgres | **RDS Multi-AZ** (or Aurora) | PITR on; deletion protection on; start small (`t4g.medium` class) |
| AgentFacts / traces | **S3** | Same as A |
| Offload | **`/tmp`** | Still no EFS |
| Secrets | **Secrets Manager** (or SSM) | Injected into task defs |
| Meta | EventBridge → ECS run-task | Disable-by-default until useful |
| Observability | CloudWatch: 5xx, p95, DB connections + budget | Match GCP’s 3-signal bar |
| Deploy | Rolling / blue-green behind ALB | Drain SSE-aware where possible |

### 2.3 HA / durability bar (B)

| Concern | Control | Suggested target |
|---|---|---|
| DB AZ failure | Multi-AZ (or Aurora) | RTO ~ minutes; RPO ≈ replica lag (secs) |
| Data loss / oops | PITR + deletion protection + restore drill | RPO ≤ 5 min |
| Compute hole | `min≥1`, ≥2 tasks when budget allows | No cold-start first-session failure |
| Object durability | S3 versioning | Facts/traces recoverable |
| Deploy downtime | Rolling + health checks | Brief SSE blips OK; avoid full outage |

### 2.4 Cost snapshot (B)

| Line | ~$/mo |
|---|---|
| Fargate FE+BE min-1 | ~$72 |
| RDS Multi-AZ | ~$125 |
| ALB (+ LCU) | $23–40 |
| S3 + logs + secrets | ~$10–15 |
| **Total** | **~$230–270** |

Delta vs A: mostly **Multi-AZ DB (~$125) + always-on compute/ALB**.

---

## 3. Transition A → B

### 3.1 Flip triggers (any one can justify the move)

| ID | Trigger | Why |
|---|---|---|
| T1 | First **paying** cohort / contractual uptime | HA becomes a product promise |
| T2 | Sustained **≥~5–10 concurrent SSE** or cold starts in support | `min≥1` pays for itself in UX |
| T3 | Customer data needs **AWS-native PITR + tested restore** | Neon SLA no longer enough |
| T4 | App Runner SSE/sidecar limits already forced Fargate | Halfway; finishing B is mostly DB + min count |
| T5 | Monthly LLM/infra bill makes **+$150–200** IaaS noise | Cost objection to B weakens |

Until a trigger fires, **stay on A** (or GCP).

### 3.2 Stable across the flip (do not re-litigate)

- Combined backend topology (no D3/D5 in the same change)
- `/tmp` + S3 offload (never introduce EFS)
- In-process BlackBox relay
- WorkOS @ BFF; Langfuse external
- Four-adapter portability seam
- Tauri/Capacitor still point at **one** FE URL (DNS cutover)

### 3.3 Migration sequence

```text
Phase 0 — Prep (still on A)
  • Document RPO/RTO targets
  • Neon backups / export; take a base backup
  • Confirm images Fargate-ready
  • CloudWatch (or equivalent) baselines on A

Phase 1 — Compute lift (optional if still on App Runner)
  • ECR → Fargate task defs (FE, BE+SearXNG)
  • ALB idle timeout ≥ 3600s; health checks
  • Dual-run: weighted DNS App Runner → Fargate
  • Point Tauri/Capacitor PROD_URL only after FE healthy
  • Still on Neon → intermediate A′ (~$75–120/mo)

Phase 2 — Data plane lift (the real A→B)
  • Provision RDS Multi-AZ (or Aurora), PITR, deletion protection
  • pgvector + schema migrate
  • Logical dump/restore or continuous sync (Neon → RDS)
  • Window: freeze writes → final sync → switch DATABASE_URL
  • Verify: login, threads, coach stream, memory recall, AgentFacts
  • Keep Neon read-only ~48–72h as rollback

Phase 3 — HA hardening
  • desired/min ≥ 1 (then ≥ 2 when $ allows)
  • Alarms: 5xx, p95, DB connections, FreeStorageSpace
  • Restore drill: PITR to scratch → app smoke
  • Decommission App Runner / old Neon prod role
  • Update PROD_URL in Tauri + Capacitor release builds if hostname changed
```

### 3.4 Downtime expectations

| Phase | Expected user impact |
|---|---|
| Phase 1 (compute) | Near-zero with weighted DNS; brief SSE disconnects possible |
| Phase 2 (DB cutover) | **Planned window** — typically **~5–30 min** write freeze |
| Phase 3 | None if rolling |

**Rollback:** Phase 1 → DNS back to App Runner; Phase 2 → re-point `DATABASE_URL`
to Neon if lag was small and Neon kept.

### 3.5 Cost path

```text
A:     $35–70
A′:    $75–120     (Fargate+ALB, still Neon)     ← after Phase 1
B:     $230–270    (Multi-AZ RDS + min≥1)        ← after Phase 2–3
```

Pausing at **A′** is valid if SSE forced Fargate but Multi-AZ is not yet justified.

### 3.6 Out of scope for A→B

- Splitting middleware vs agent (D3)
- Eng-coach carve-out (D5)
- EKS (D6)
- Cross-region / Aurora Global (Tier C) unless RPO ≪ 1 min cross-region is required
- Reintroducing EFS or Firehose because the aspirational AWS arch doc mentioned them

---

## 4. Decision summary

| | Stack A | Stack B |
|---|---|---|
| **Optimize** | Cash, learning AWS | Uptime + durable customer data |
| **Compute** | App Runner (Fargate if SSE) | Fargate + ALB, min≥1 |
| **DB** | Neon | RDS Multi-AZ (or Aurora) |
| **IaaS** | ~$35–70 | ~$230–270 |
| **Clients** | Same three shells → one BFF | Same |
| **Move when** | — | T1–T5 triggers (§3.1) |

**Default path:** ship **A** → watch triggers → **Phase 1 (A′)** if needed →
**Phase 2–3 (B)** when customer data / uptime is a promise.

Costs are **list-price IaaS only** (pyramid study posture). LLM tokens, WorkOS,
Langfuse, and Apple developer fees are out of band.
