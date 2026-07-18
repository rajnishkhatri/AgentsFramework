---
type: design
title: Eng-Coach AWS Production — System Architecture
status: draft
stage: post-brainstorm (bridge to sdd-spec)
date: 2026-07-15
related:
  - docs/plan/eng-coach-aws-deploy.brainstorm.md   # Stage-1: inventory, mapping, FR/NFR
  - docs/plan/eng-coach-aws-deploy.stacks.md        # Stack A/B framing (parallel session)
  - docs/Architectures/AWS_DEPLOYMENT_ARCHITECTURE.md
  - docs/Architectures/CLOUD_PROVIDER_COMPARISON.md
decisions:
  - single-AZ, NO Multi-AZ HA (2026-07-14)
  - minimal cost (Tier-A posture, same as GCP-dev)
  - DB = Neon serverless (dev==prod parity)
  - two app services only (backend-combined + frontend); agent-middleware orphan NOT ported
  - compute engine UNDECIDED — App Runner vs Fargate+ALB, gated on the 3600s-SSE spike
---

# Eng-Coach AWS Production — System Architecture

> **Where this sits in the lifecycle.** Stage 1 (brainstorm) is complete: the
> [brainstorm doc](eng-coach-aws-deploy.brainstorm.md) inventoried the live GCP
> stack, mapped every component to AWS (§2), derived 46 FR + 32 NFR (§4), and
> landed the decisions in this doc's frontmatter. This document is the **bridge to
> sdd-spec**: it draws *the chosen architecture* end-to-end — one topology, its
> data flows, its trust/security boundaries, and its failure modes — instead of
> six candidate directions. It bakes in every locked decision and isolates the
> **one** axis still open (compute engine) as an explicit, well-scoped fork.
>
> **Nothing here is new evidence.** Every box, arrow, and constraint traces to a
> requirement already adversarially verified in brainstorm §4 (81 derived → 81
> survived). This doc *composes* those verified facts into a picture; it does not
> introduce claims the brainstorm didn't check. Requirement IDs (`FR-*`, `NFR-*`)
> are cited inline so each design choice is traceable to its acceptance criterion.

---

## 0. Design tenets (what the picture must honor)

The architecture is the *intersection* of five locked decisions plus the hard
constraints from brainstorm §4.3. Read these first — every later section is
downstream of them.

| # | Tenet | Source | What it forbids |
|---|---|---|---|
| T1 | **Single-AZ, no Multi-AZ HA** | decision 2026-07-14; `NFR-AVAIL-1` | No synchronous standby, no cross-AZ failover in scope. DR = restore-from-backup. |
| T2 | **Minimal cost (Tier-A posture)** | decision 2026-07-14; `NFR-COST-1/2` | No EFS/FSx, no NAT Gateway, no always-on meta worker, no warm-floor mandate. |
| T3 | **Neon serverless Postgres** | decision 2026-07-14; `FR-D8`, `NFR-PARITY-MEM-1` | One DB engine carries checkpointer + thread-store + pgvector; no separate vector DB; no RDS as primary. |
| T4 | **Exactly two app services** | `FR-C5`, `FR-M2`, drift check §1.2b | backend-combined (+ searxng sidecar) and frontend-BFF only. The `agent-middleware` orphan is **not** ported. |
| T5 | **Cloud-SDK confinement (4-file radius)** | `NFR-PORT-1/2`, `FR-M1/M5`, constraint §4.3#7 | boto3 appears only in the 4 adapter seams + composition root. `trust/` and `components/` stay cloud-free. |
| **T6** | **SSE ≥ 3600 s on every ingress hop** | `FR-C1/C3`, `NFR-PARITY-SSE-1`, constraint §4.3#1 | Any ingress that idle-caps below 3600 s is disqualified. This is the axis that forks the compute tier. |

**The single open decision.** T6 is why the compute tier is drawn *twice* below.
App Runner is the cost-lean, Cloud-Run-closest engine, **but its 3600 s SSE hold
is unproven** (`NFR-SCALE-2`, brainstorm §4.4#2). Fargate + ALB is the
no-kill-criterion spine (ALB idle timeout ~4000 s clears 3600 s). Rather than pick
before the spike, this doc gives **one shared data/security/trust plane** and
**two compute-tier variants** that plug into it. The spike result selects the
variant; nothing else in the architecture moves.

---

## 1. The system in one view (shared invariant plane)

Everything *except* the compute engine is fixed. This is the plane both variants
share — the data stores, the trust boundaries, the external SaaS, the identity
model. §2 then shows the two compute tiers that dock onto it.

```text
                          ┌──────────────────────────────────────────────┐
   Clients               │  EXTERNAL SaaS (unchanged — NOT migrated)      │
 ┌──────────────┐        │  ┌────────────┐   ┌─────────────┐              │
 │ Browser      │        │  │  WorkOS    │   │  Langfuse   │              │
 │ Tauri (mac)  │──┐     │  │  (authN)   │   │  Cloud      │  FR-M8/O10   │
 │ Capacitor(iOS)│  │     │  └─────▲──────┘   └──────▲──────┘             │
 └──────────────┘  │     └────────┼─────────────────┼────────────────────┘
                   │ HTTPS         │ OIDC/session     │ egress + 2 secrets
                   ▼               │                  │ (trace export, in-process relay)
        ╔══════════╪═══════════════╪══════════════════╪═══════════════════╗
        ║  AWS — single region (US), single-AZ, one VPC                    ║
        ║          │               │                  │                    ║
        ║   ┌──────▼──────────┐    │                  │                    ║
        ║   │  COMPUTE TIER   │    │   (see §2 — App Runner OR Fargate+ALB) ║
        ║   │  ┌───────────┐  │◄───┘                  │                    ║
        ║   │  │ Frontend  │  │  WorkOS @ BFF         │                    ║
        ║   │  │ BFF (Next)│  │  FR-M4/M9/M10         │                    ║
        ║   │  └─────┬─────┘  │                       │                    ║
        ║   │        │ Bearer forward (no cloud creds in BFF)  T5          ║
        ║   │  ┌─────▼──────────────────┐             │                    ║
        ║   │  │ Backend-combined       │  in-process │                    ║
        ║   │  │  ├ middleware+agent     │  relay ─────┘                    ║
        ║   │  │  └ searxng sidecar      │  FR-C8                          ║
        ║   │  └──┬────┬────┬────┬───────┘                                 ║
        ║   └─────┼────┼────┼────┼──────────────────────────────────────┐ ║
        ║         │    │    │    │  DATA PLANE (shared, single-AZ)        │ ║
        ║   ┌─────▼┐ ┌─▼──┐ ┌▼───┐ ┌▼──────────┐  ┌──────────────────┐   │ ║
        ║   │ Neon │ │ S3 │ │ S3 │ │ SSM Param  │  │ ephemeral /tmp   │   │ ║
        ║   │ PG + │ │facts│ │trace│ │ Store      │  │ (offload +       │   │ ║
        ║   │pgvec │ │ FR- │ │ FR- │ │ SecureStr  │  │  blackbox)       │   │ ║
        ║   │ T3   │ │D2/D6│ │D3/D7│ │ FR-S2 T2   │  │ FR-C7/D4  NO EFS │   │ ║
        ║   └──────┘ └────┘ └────┘ └────────────┘  └──────────────────┘   │ ║
        ║      ▲ 3 loads: checkpointer + thread-store + pgvector (one URL) │ ║
        ║      └────────────────────────────────────────────────────────┘ ║
        ║                                                                  ║
        ║   IDENTITY: per-service IAM task roles (least privilege)  T5     ║
        ║     • frontend role → 2 WorkOS secrets ONLY  (NFR-SEC-1)         ║
        ║     • backend role  → DB/LLM/facts/traces; NOT workos-cookie-pw   ║
        ║   OBSERVABILITY: CloudWatch 3 alarms + AWS Budgets  (NFR-OBS-1)  ║
        ║   REGISTRY: ECR (digest-pinned deploys)  (NFR-DEPLOY-1)          ║
        ╚══════════════════════════════════════════════════════════════════╝
```

**What the picture asserts (all from verified FR/NFR):**

- **Two app services, one sidecar.** Frontend BFF and backend-combined; searxng is
  a co-located container in the backend task, not a third service (`FR-C5`, `T4`).
- **One Postgres, three loads.** Neon carries checkpointer + durable thread-store
  + pgvector memory over a single `DATABASE_URL` (`FR-D8`, `NFR-PARITY-MEM-1`,
  `T3`). This concentrates data-plane availability on one engine — an accepted
  single-AZ trade (`NFR-AVAIL-1`), bounded by backups + PITR (`NFR-RESIL-1`).
- **BFF holds no cloud credentials.** It authenticates the user via WorkOS and
  forwards a Bearer token to the backend; DB/LLM/facts/trace credentials never
  reach the BFF (`NFR-SEC-1`, frontend-ring invariant, `T5`).
- **External SaaS stays external.** WorkOS and Langfuse are reached by egress + two
  secrets each; neither is re-hosted or proxied (`FR-M8`, `FR-O10`).
- **Ephemeral disk only.** Offload + blackbox recordings live in container-local
  `/tmp`; no EFS/FSx is provisioned (`FR-C7`, `FR-D4`, `NFR-COST-1`, `T2`). The
  BlackBox→Langfuse relay runs **in-process** in the backend lifespan (`FR-C8`).

---

## 2. The compute tier — drawn twice (the open fork)

Both variants dock onto the §1 plane unchanged. They differ only in the ingress +
compute engine. The **SSE spike** (`NFR-SCALE-2`) selects between them.

### 2.A Variant A — App Runner (cost-lean, PENDING SSE proof)

App Runner is the closest AWS analogue to Cloud Run: managed, scale-to-zero-ish,
no ALB hours, no VPC plumbing for public ingress. It is the **cheaper** substrate
and the better dev↔prod-shape match — *if it holds a 3600 s SSE stream*.

```text
  Client ──HTTPS──► App Runner (Frontend BFF)  ──► App Runner (Backend + searxng)
                    scale-to-zero-ish              combined service
                    WorkOS @ BFF                   request timeout posture 3600s ??
                          │                              │
                          └── VPC connector (egress) ────┴──► Neon / S3 / SSM
```

- **Ingress/SSE:** App Runner terminates TLS and holds the connection; **the open
  question is whether it will hold `/run/stream` idle for ≥ 3600 s without
  truncating** (`NFR-SCALE-2`, `NFR-PARITY-SSE-1`). This is the spike.
- **Sidecar risk:** App Runner's single-container model may not run the searxng
  sidecar in-task. If not, searxng becomes a second App Runner service (a
  *supporting* service, still within the two-*app*-service bound of `FR-M2`) or the
  variant flips to Fargate. (brainstorm §4.4#4, stacks §1.4)
- **Scale-in flush:** App Runner min=0 hard-kills on scale-in; the in-process relay
  must drain during graceful shutdown or lose unflushed `/tmp` recordings
  (`FR-D5` treats them as non-durable; `FR-C8` relay must honor shutdown —
  brainstorm §4.4#4).
- **Cost:** lowest fixed floor (no ALB, no NAT). stacks §1.6 bands it ~$35–70/mo.
- **Kill-criterion:** SSE < 3600 s **or** unworkable sidecar/shutdown → fall back
  to Variant B, keeping Neon and the entire §1 plane (stacks calls this the "A′"
  intermediate).

### 2.B Variant B — Fargate + ALB (no unresolved kill-criterion)

The boring, proven spine. ALB idle timeout (configurable up to ~4000 s) clears the
3600 s SSE bar outright, and a Fargate task natively runs the searxng sidecar as a
second container — a 1:1 port of the live GCP topology.

```text
  Client ──HTTPS──► ALB (idle ≥3601s) ──► Fargate svc: Frontend BFF (desiredCount≥1 or 0*)
                    TLS @ 443              │
                          │ (internal)     └── Bearer forward
                    ALB (idle ≥3601s) ──► Fargate svc: Backend task
                                             ├ container: middleware+agent (app_prod)
                                             └ container: searxng sidecar     FR-C5
                                                   │
                                                   └──► Neon / S3 / SSM  (via subnet route)
  * min-instances: NFR-AVAIL-2 allows 0 (cold-start accepted) to minimize cost;
    warm floor min-1 is an opt-in future lever, not baseline (T2).
```

- **Ingress/SSE:** ALB idle timeout set ≥ 3601 s → `FR-C1`/`NFR-PARITY-SSE-1`
  satisfied with no open question. This is why B carries **no** unresolved
  kill-criterion (brainstorm §5 D1, §6).
- **Sidecar:** native multi-container Fargate task; searxng ports 1:1 (`FR-C5`).
- **p95 alarm caveat:** the ALB/target p95 alarm **must exclude** the `/run/stream`
  route or long streams trip the 5000 ms latency alarm (`FR-O5`, `NFR-OBS-1` —
  new obligation vs the live GCP policy; brainstorm §4.4#8).
- **Cost:** adds ALB hours (~$16–22/mo/ALB) over Variant A; stacks bands the
  Fargate-early path ~$75–120/mo. Still single-AZ, still Neon.

### 2.C The minimal single-AZ VPC (applies to whichever variant lands)

Cost tenet T2 dictates the network topology: **avoid the NAT Gateway** (~$32/mo +
data processing), which is the silent budget-killer in naive AWS VPC designs.

```text
  VPC (single region, single AZ used)
   └─ public subnet (one AZ)
        ├─ compute tasks: assignPublicIp=true  → reach internet via IGW (egress:
        │    LLM providers, WorkOS, Langfuse, Neon control-plane)   NFR-COST-1
        ├─ Internet Gateway (IGW)               → free
        └─ S3 gateway endpoint                  → free; keeps S3 traffic off IGW
   NO NAT Gateway. NO private-subnet+NAT for egress at this tier.
```

- **Public subnet + `assignPublicIp` + IGW** gives outbound internet with zero NAT
  cost. The **S3 gateway endpoint** (free) keeps facts/traces traffic on the AWS
  backbone (`NFR-COST-1`, `T2`).
- **Trade-off named:** tasks in a public subnet get public IPs. Ingress is still
  gated (App Runner/ALB in front; security groups deny direct task ingress except
  from the load balancer). This is the same public-ingress + app-layer-auth posture
  as GCP today (`FR-M9`, constraint §4.3#6) — **not** a regression.
- **`NFR-SEC-4` (data tier reachable by 0 public principals)** is the *one*
  net-new hardening the brainstorm flagged as direction-dependent (§4.4#3). At the
  minimal-cost baseline, Neon is reached over TLS with a scoped connection string;
  **PrivateLink to Neon is a documented future lever**, not baseline — calling it
  out here so the single-AZ/no-NAT choice is a conscious cost trade, not an
  oversight.

---

## 3. Data-flow walkthroughs (the two paths that define the system)

Two request paths carry all the architectural risk. Drawing them explicitly is how
we prove the plane in §1 actually satisfies the SSE + data-plane requirements.

### 3.1 The SSE run path (`POST /run/stream`) — the load-bearing flow

```text
1. Client → BFF:  POST /run/stream, Authorization: Bearer <token>
2. BFF:           WorkOS validates session; forwards Bearer to backend
                  (BFF holds NO db/llm creds — T5, NFR-SEC-1)
3. Backend:       app_prod.py — 401 if no Bearer (FR-M9); else JWT verify (FR-C3)
4. Backend:       opens ONE long-lived text/event-stream, held ≥ 3600s (FR-C1/C3)
                  ├ checkpointer  → Neon  (thread state)      ┐
                  ├ pgvector      → Neon  (memory recall)     ├ one DATABASE_URL (T3)
                  ├ thread-store  → Neon  (durable record)    ┘
                  ├ searxng       → sidecar (in-task/second svc)
                  ├ LLM/embedding → LiteLLM → provider APIs (cloud-independent, FR-M7)
                  └ blackbox recs → /tmp (ephemeral, FR-C7)
5. Relay (async): /tmp blackbox → Langfuse Cloud, in-process (FR-C8)
6. Ingress hop:   BOTH BFF→client AND backend→BFF must hold ≥3600s (NFR-PARITY-SSE-1)
```

**Why this is the fork point:** step 4's "held ≥ 3600 s" is exactly what App Runner
(Variant A) has not been proven to do and ALB (Variant B) provably does. Every
other step is identical across variants.

### 3.2 The trust-traces write path (append-only, tamper-evident)

```text
Backend runtime → S3 trust-traces bucket
  • runtime role: create/append ONLY — no read, no list, no delete (FR-D3)
  • AWS realization: unique object keys + versioning/Object-Lock, NOT bare PutObject
  • lifecycle: object age 90d → infrequent-access class (FR-D7, NFR-DR-1)
  • S3 is inherently multi-AZ within the region at no extra cost — the single-AZ
    compute/DB decision does NOT reduce object durability (NFR-DR-1, T1)
```

This is the one place the single-AZ decision *doesn't* cost us: object durability
is 11-nines regardless, because S3 is multi-AZ by construction and free
(`NFR-DR-1`). The AgentFacts store (`FR-D2`/`FR-D6`) mirrors this with
public-access-blocked + versioned buckets.

---

## 4. Trust, security & identity plane

The security model is a *parity* requirement, not a redesign — match GCP's
least-privilege split with IAM task roles, keep app-layer auth, add only the
hardening the brainstorm explicitly scoped.

| Boundary | GCP today | AWS realization | Requirement |
|---|---|---|---|
| **Frontend identity** | frontend SA → WorkOS secrets only | frontend IAM task role → exactly 2 WorkOS SSM params; 0 backend secrets | `FR-S1`, `NFR-SEC-1` |
| **Backend identity** | backend SA → DB/LLM/facts/traces | backend IAM task role → DB/LLM/facts/traces; **NOT** `workos-cookie-password` | `FR-S1`, `NFR-SEC-1` |
| **Traces write scope** | `objectCreator` (write-only) | S3 policy: create/append only, deny read/list/delete | `FR-D3` |
| **Facts public-access** | public-access prevention enforced | S3 Block Public Access + bucket-owner-enforced | `FR-D2`, `NFR-DATA-FACTS-INTEGRITY-1` |
| **Secrets at rest** | Secret Manager | **SSM Parameter Store SecureString** (≤$5/mo — free tier; `NFR-COST-2`, `T2`) | `FR-S2`, `NFR-SEC-2` |
| **Ingress TLS** | Cloud Run edge TLS | App Runner edge TLS **or** ALB:443, HTTPS-only, 0 cleartext | `NFR-SEC-3` |
| **Auth model** | app-layer WorkOS, public ingress, 401 pre-run | identical — do NOT relocate auth to a network gateway | `FR-M9`, constraint §4.3#6 |
| **Encryption-at-rest** | provider-default (no explicit KMS) | **decide at spec:** SSE-S3 (default, free) vs SSE-KMS; DB storage-encryption key ownership | brainstorm §4.4#6 (gap) |

**Identity resolver caveat (verified catch, brainstorm §2.4):** the AWS identity
seam (`aws_identity.py`, `FR-M5`) must resolve the caller from the **IAM role ARN**,
not a display-name string — the naive port that reads a display name silently
mis-identifies. This is a spec-time correctness note, flagged here so it isn't lost.

---

## 5. Failure modes & the single-AZ blast radius

The single-AZ decision (T1) makes the failure model *simpler but sharper*: fewer
moving parts, but a component loss is a real outage, not a transparent failover.
Naming each failure and its accepted recovery is how we make single-AZ a conscious
choice rather than a hidden risk.

| Failure | Blast radius | Recovery (single-AZ baseline) | Requirement |
|---|---|---|---|
| **Neon primary lost / AZ outage** | All stateful requests (checkpointer + memory + thread store — one engine, T3) | **Restore-from-backup**, not failover: RPO ≤ 5 min (PITR), RTO ≤ 60 min. Accepted downtime for minimal cost. | `NFR-RESIL-1`, `NFR-AVAIL-1` |
| **Compute cold-start after scale-to-zero** | First SSE request after idle waits on cold start | Accepted (`NFR-AVAIL-2`, min-0 default). Warm floor min-1 removes it — **future lever**, not baseline. | `NFR-AVAIL-2` |
| **Backend instance dies mid-stream** | That one SSE connection drops; unflushed `/tmp` blackbox lost | Client reconnects (new run); recordings are non-durable by design. | `FR-D5` |
| **Scale-in kills instance before relay flush** | Unflushed recordings in `/tmp` lost | Graceful-shutdown drain (Variant A must verify; Variant B has task-stop grace). | `FR-C8`, §4.4#4 |
| **DB connection pool exhaustion** | New requests queue then fail-one (not crash) | Bounded wait → pool-exhaustion error on the one request; process survives. Aggregate pool cap ≤ (`max_connections` − headroom). | `FR-D1`, `NFR-DATA-CONN-1` |
| **S3 / object store** | — | S3 is multi-AZ + 11-nines; single-AZ decision does not touch it. RPO=0 for written objects. | `NFR-DR-1` |
| **External SaaS (WorkOS/Langfuse) down** | Auth or trace-export degraded | WorkOS down blocks new auth (hard dep); Langfuse down loses trace export but not request correctness (relay is best-effort). | `FR-M8`, `FR-O10` |

**Connection-ceiling arithmetic (verified catch, brainstorm §2.4).** At Variant-B
max-scale, ~8 conns/task × up-to-10 tasks = 80 > the 50 ceiling. Mitigation at
minimal-cost baseline: **cap task count ≤ 6** (48 conns < 50) *or* enable a
connection pooler (Neon pooler / RDS-Proxy-equivalent). `NFR-SCALE-1` explicitly
allows deferring the pooler until scale-out is enabled — so the baseline is
"cap tasks," and the pooler is the first lever when traffic grows.

---

## 6. The code-refactor surface (what must be built)

The architecture is only realizable once the AWS variants of the four adapter seams
exist. This is the `T5` portability radius — **bounded to 4 files + composition-root
wiring**, which is the modularity win to preserve, not erode (`NFR-PORT-1/2`,
`FR-M5`). Every item below is currently **unbuilt** (`git grep AWS_EXECUTION_ENV` =
docs only, brainstorm §4.4#7).

| Seam | File (approx.) | AWS variant to build | Requirement |
|---|---|---|---|
| Postgres checkpointer | `agent_ui_adapter/adapters/runtime/postgres_saver.py` | env-gate on `AWS_EXECUTION_ENV`; Neon `DATABASE_URL` (already works — Neon is just Postgres) | `FR-M5` |
| Trace sink | `services/trace_sinks/` | S3 sink (or keep GCS-equivalent S3 relay); **not** Kinesis (in-process relay, `FR-C8`) | `FR-M5`, §4.4#7 |
| AgentFacts registry | `services/governance/agent_facts_*_registry.py` | `s3://` URI support alongside `gs://` | `FR-M5`, `FR-D6` |
| Cloud identity | `services/cloud_providers/aws_identity.py` | resolve from IAM **role ARN** (not display-name) | `FR-M5`, §4 caveat |
| **Confinement test** | `tests/architecture/` | **new** test: fail the gate if a cloud SDK is imported outside the 4 seams | `FR-M1` (unbuilt) |
| Composition-root switch | shared comp root | `AWS_EXECUTION_ENV` selects AWS variant of each seam; GCP-dev keeps native; no app-code fork | `FR-M5`, `NFR-MAINT-1` |

**Anti-slop guardrail (`FR-M1`, `T5`).** The confinement test is the *class-level*
fix: it doesn't just add boto3 to four files, it makes the next accidental
cloud-SDK import outside the radius fail CI. Without it, the 4-file boundary is a
convention that erodes; with it, it's enforced. This is the one net-new
architecture test the port requires.

---

## 7. What this architecture deliberately does NOT decide

Kept out so sdd-spec resolves them with the spike/probe results, not assumption:

1. **Compute engine (App Runner vs Fargate+ALB)** — the §2 fork. Resolved by the
   3600 s SSE spike (`NFR-SCALE-2`). First thing to settle at spec.
2. **Encryption-at-rest key ownership** — SSE-S3 vs SSE-KMS; DB storage-encryption
   key (brainstorm §4.4#6).
3. **Region + any DR-secondary** — pick a US region satisfying `FR-M3`; single-AZ
   means no standby, but the region choice + optional cross-region backup copy is
   spec work (§4.4#5).
4. **Pooler-now vs cap-tasks** — `NFR-SCALE-1` allows deferring the pooler; the
   baseline caps tasks ≤ 6. Spec picks the trigger to enable pooling.
5. **Prod-tier value re-baselining** — $50 budget, `max_connections`, 50-conn alarm
   are dev defaults; re-tune once the DB tier is fixed (§4.4#9).
6. **The future HA levers** — Multi-AZ flip, warm floor min-1, PrivateLink to Neon,
   cross-region replica. Each is a documented one-knob change (§4.4#10) so
   single-AZ is reversible, not a dead-end. **Explicitly out of current scope.**

---

## 8. Reconciliation with the two prior docs

| This doc says | brainstorm §5/§6 | stacks A/B | Agreement? |
|---|---|---|---|
| Two compute variants, one shared plane | D1 lead + D2 tweaks; D2 gated on SSE spike | Stack A (App Runner) / Stack B (Fargate) | ✅ — this doc *is* the merged single-topology view of both |
| Neon DB (T3) | D4 evaluated as the Postgres choice | Neon in both A and B | ✅ locked |
| Single-AZ, minimal cost (T1/T2) | §4.2 re-baselined; constraint §4.3#11 | Stack A "single-AZ/SaaS DB acceptable" | ✅ locked |
| Two app services (T4) | §6, `FR-C5`/`FR-M2` | combined backend, FE BFF | ✅ locked |
| Compute UNDECIDED | §4.4#2 first kill-criterion | A→B flip triggers §3 | ✅ — same open axis, drawn as a fork |

**Net:** this architecture doc collapses the brainstorm's six directions and the
stacks doc's A/B framing into **one topology with one open fork** (compute), so
sdd-spec has a single picture to write acceptance criteria against — with the
Stack A→B *transition* (stacks §3) available as the documented upgrade path if the
minimal-cost baseline later needs HA.

---

## 9. Next step

**→ sdd-spec**, in this order:

1. **Run the App Runner 3600 s SSE spike** (`NFR-SCALE-2`). This is a
   kill-criterion, not a preference — it *selects* the §2 variant. Everything else
   is ready to spec regardless of outcome.
2. **Write EARS acceptance criteria** for the shared plane (§1), the selected
   compute variant (§2), the security split (§4), and the CloudWatch/Budgets
   observability (§4 table) — the brainstorm §4 FR/NFR are the substrate.
3. **Author the 4 adapter seams + the confinement test** (§6) red/green — the test
   was *seen to fail first* before boto3 lands anywhere.
4. **ADR triggers to expect at spec:** the confinement architecture test (new
   architecture test), the S3 trace-sink adapter (new abstraction on the trace
   path), and the `AWS_EXECUTION_ENV` composition-root switch — each is an
   `⚠️ Ask first` item that needs an ADR when specified.
