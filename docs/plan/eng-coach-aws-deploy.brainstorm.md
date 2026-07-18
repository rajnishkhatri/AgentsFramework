---
type: brainstorm
name: Eng-Coach AWS Production Deployment
stage: sdd-stage-1-brainstorm
status: draft-for-review
overview: >
  SDD Stage 1 (brainstorm) for deploying the eng-coach to AWS as the production
  target while GCP remains the dev target. Part 1 is a ground-truth inventory of
  the stack currently defined in `infra/gcp/*.tf` (source of truth, not the
  aspirational architecture docs). Part 2 maps each GCP component to AWS
  candidates. Part 3 frames the whole decision around the quality attributes
  (the "-ilities": availability, scalability, manageability, extensibility,
  modularity, security, observability, portability, cost-efficiency). Part 4 is
  the system requirements — 46 functional (EARS) + 32 non-functional (measurable
  targets), all direction-independent and verified against repo evidence. Part 5
  lists ~6 candidate deployment directions to carry into sdd-spec. NO IaC, NO code
  in this document — requirements + directions + evidence only.
related:
  - docs/plan/eng-coach-aws-deploy.stacks.md               # Stack A/B + A→B transition (post-review posture)
  - docs/plans/cloud_cost_comparison_pyramids.plan.md      # the cost study this anchors to
  - docs/Architectures/CLOUD_PROVIDER_COMPARISON.md         # generic AWS/GCP/Azure cost comparison
  - docs/analysis/CLOUD_COMPARISON_PYRAMID_ANALYSIS.md      # pyramid evidence behind the comparison
  - docs/Architectures/AWS_DEPLOYMENT_ARCHITECTURE.md       # aspirational AWS topology (pre-dates live GCP IaC)
  - docs/Architectures/GCP_DEPLOYMENT_ARCHITECTURE.md       # aspirational GCP topology
  - infra/gcp/                                              # LIVE GCP IaC = the real inventory
  - infra/dev-tier/                                         # (RETIRED via ADR-0031 during this work) Neon-backed dev-tier IaC
---

# Eng-Coach AWS Production Deployment — Stage 1 Brainstorm

> **Status: DRAFT FOR YOUR REVIEW.** This is the artifact you asked me to save
> *before* answering the scope questions. It does the inventory and the AWS
> mapping study framed on the "-ilities". Two decisions are still open (see
> §0 Open Scope Questions) — I have **not** assumed answers; I flag where each
> answer would change the recommendation.

---

## 0. Scope decisions (ANSWERED 2026-07-14)

- **Q1 — Deploy scope → WHOLE STACK** (frontend + BFF + backend mirrored on AWS).
  *Consequence:* the compute topology is the full footprint. Directions **D1, D2,
  D4** are in play. **D3 (split combined backend) and D5 (carve out eng-coach)
  are deprioritized** — they described sub-scopes the user did not pick — but are
  retained in §5 as future levers, not current candidates.
- **Q2 — Inventory depth → IaC + LIVE `gcloud` DRIFT CHECK.** Done — see §1.2b.
  Verdict: IaC and live state are **in sync except one orphan** (`agent-middleware`
  placeholder) and two extra secrets. The orphan means the "whole stack" is
  really **two** app services (backend-combined + frontend), not three.

---

## 1. Ground-truth GCP inventory (from `infra/gcp/*.tf`)

**Method:** enumerated directly from the live Terraform, not from
`GCP_DEPLOYMENT_ARCHITECTURE.md` (which is aspirational and pre-dates this IaC).
Every row cites the file it came from. This is the "check all the tech stack
currently on GCP" step.

### 1.1 What is actually deployed today (Tier-A / dev posture)

| # | Component | GCP service (live) | Key config (from IaC) | Evidence |
|---|---|---|---|---|
| C1 | **Combined backend** (middleware auth/ACL **+** agent SSE runtime in ONE service) | Cloud Run v2 `agent-backend-combined` | min 0 / max 10 instances, 1 vCPU / 2 GiB, request timeout **3600 s** (SSE), gen2, `cpu_idle=true`, scale-to-zero | `cloud-run-backend.tf:174-215` |
| C2 | **SearXNG web-search** | Sidecar container in the same Cloud Run service, port 8888, no ingress | 0.5 vCPU / 512 MiB, shares scale-to-zero lifecycle | `cloud-run-backend.tf:448-480` |
| C3 | **Frontend / BFF** (Next.js 15 SSR + WorkOS session) | Cloud Run v2 `agent-frontend` | min 0 / max 10, 1 vCPU / 512 MiB, timeout 3600 s, proxies to backend via `MIDDLEWARE_URL` | `cloud-run-frontend.tf:544-643` |
| C4 | **Postgres** (LangGraph checkpointer + pgvector memory + thread store) | Cloud SQL for PostgreSQL 15 | `db-f1-micro` shared-core, 10 GB PD_SSD, **ZONAL (single-AZ)**, `max_connections=50`, backups on, deletion-protection **off** (dev) | `data.tf:706-742` |
| C5 | **AgentFacts store** (signed trust identity docs) | GCS bucket `<project>-agent-facts` | versioned, uniform access, public-access **enforced** | `data.tf:765-785` |
| C6 | **Trust-traces sink** (BlackBox JSONL) | GCS bucket `<project>-trust-traces` | 90-day lifecycle → Nearline, write-only SA role | `data.tf:795-825` |
| C7 | **Secrets** (9) | Secret Manager | workos-api-key, openai, anthropic, deepseek, langfuse-public, langfuse-secret, database-url, agent-facts-secret, workos-cookie-password; `secretAccessor` scoped to runtime SA only | `secret-manager.tf:1446-1591` |
| C8 | **Meta / eval ring** (nightly) | Cloud Run **Job** + Cloud Scheduler (cron `0 6 * * *`) | **disabled by default** (`enable_meta_ring=false`); reads golden-set from GCS, runs `python -m meta.run_eval` | `meta.tf:975-1066` |
| C9 | **Observability** | Cloud Monitoring dashboard + 3 alert policies (5xx rate, p95 latency, SQL connections) + optional billing budget | thresholds: 5% 5xx, 5000 ms p95, 50 SQL conns, $50/mo budget | `observability.tf:1122-1428` |
| C10 | **Image registry** | Artifact Registry (Docker, `us-central1`) | single repo `agent-backend` | `foundations.tf:62-76` |
| C11 | **Identity** | 3 runtime service accounts (`agent-backend-runtime`, `agent-frontend-runtime`, `agent-meta-runtime`) | least-privilege; frontend SA gets WorkOS secrets **only**, never DB/LLM keys | `foundations.tf:87-153`, `meta.tf:902-911` |

### 1.2 Cross-cutting runtime facts that constrain the AWS mapping

These are the "gotchas" that a naive lift-and-shift would miss — pulled from the
env-var wiring, not guessed:

- **SSE is the hard constraint.** Backend request timeout is **3600 s**
  (`backend_request_timeout_seconds`). Any AWS ingress that caps below this
  breaks agent streaming. (API Gateway's 29–30 s cap is why the existing AWS doc
  routes SSE through ALBs — `AWS_DEPLOYMENT_ARCHITECTURE.md:132-133`.)
- **Offload is ephemeral `/tmp`, not NFS.** `AGENT_OFFLOAD_DIR=/tmp/agent_offload`
  and `BLACKBOX_STORAGE_DIR=/tmp/agent_offload/black_box_recordings`
  (`cloud-run-backend.tf:254-271`). The live stack does **not** mount Filestore
  — it uses container-local `/tmp` + a GCS relay. **This is significant for
  cost:** the Filestore/EFS "1 TiB minimum" trap flagged in the pyramid study
  (`CLOUD_PROVIDER_COMPARISON.md:45`) is already sidestepped. AWS mapping should
  preserve this (ephemeral disk + S3 relay), not introduce EFS.
- **Trace relay runs in-process.** `BLACKBOX_RELAY_MODE=in_process` — the
  BlackBox→Langfuse relay is an asyncio task inside the backend lifespan, not a
  separate service. No Pub/Sub topic is provisioned at this tier
  (`data.tf:690-692`).
- **Memory backend is pgvector on the same Postgres.** `MEMORY_BACKEND=pgvector`,
  `EMBEDDING_MODEL=text-embedding-3-small` (`cloud-run-backend.tf:325-338`). mem0
  was cut over. So Postgres carries **three** loads: checkpointer + thread store
  + vector memory. This concentrates the data-plane availability risk on one
  instance.
- **LLM providers are provider-independent (LiteLLM).** openai / anthropic /
  deepseek keys are all injected; `MODEL_PROFILE_SET` selects the registry
  (`cloud-run-backend.tf:385-388`). Token spend is **cloud-independent** — it
  does not move when we change clouds (confirms `CLOUD_PROVIDER_COMPARISON.md:21`).
- **Telemetry is external SaaS.** Langfuse Cloud (`cloud.langfuse.com`) and
  WorkOS are third-party — **they do not migrate**. AWS only needs egress + the
  same two secrets.
- **Auth is app-layer, ingress is public.** Cloud Run `allUsers` invoker +
  WorkOS JWT/session at the app layer (`cloud-run-backend.tf:509-515`). There is
  no network-level gateway auth today.

### 1.2b Live `gcloud` drift check (Q2 answer — verified 2026-07-14)

Ran read-only `gcloud` against project **`agent-prod-gcp-dev`** (region
`us-central1`) and diffed against `infra/gcp/*.tf`. Findings:

| Check | IaC declares | Live state | Verdict |
|---|---|---|---|
| Backend service | `agent-backend-combined`, min0/max10, 1vCPU/2Gi, 3600s, gen2 + searxng sidecar | **matches exactly** (image pinned by digest `@sha256:e0f4642…`, sidecar `searxng:latest` present, 3600s, throttling on) | ✅ in sync |
| Frontend service | `agent-frontend`, min0/max10 | **matches** (min0/max10) | ✅ in sync |
| **`agent-middleware`** | **NOT in `infra/gcp/*.tf`** | **LIVE** — running placeholder `us-docker.pkg.dev/cloudrun/container/hello`, min0/max10, 100% traffic to `agent-middleware-00002-bsz` | ⚠️ **DRIFT — orphan** |
| Cloud SQL | `agent-db`, PG15, `db-f1-micro`, ZONAL, 10 GB | **matches** (RUNNABLE, ZONAL single-AZ) | ✅ in sync |
| GCS buckets | `-agent-facts`, `-trust-traces` | both present (+ `-tofu-state`, `_cloudbuild` bootstrap buckets — expected, not app data) | ✅ in sync |
| Secrets | 9 declared | **11 live** — the 9 + **`neon-database-url`** (dev-tier bleed) + `mem0-api-key` (kept for rollback window per `cloud-run-backend.tf:318-324`) | ⚠️ minor drift |
| Meta ring (job + scheduler) | disabled by default (`enable_meta_ring=false`) | **no Cloud Run Job, no Scheduler job** live | ✅ consistent (disabled) |

**Two drift items that matter for the AWS migration:**

1. **`agent-middleware` is a deployed-but-empty orphan** (placeholder `hello`
   image, taking 100% traffic on its own URL but serving nothing real). This
   confirms the prior finding that middleware was folded **into**
   `agent-backend-combined` (the "combined" in the name), and the standalone
   `agent-middleware` service was never decommissioned. **Do not port this to
   AWS.** It also means the answer to "whole stack" scope (Q1) is really *two*
   live app services (backend-combined + frontend), not three — the AWS topology
   should have **two** Fargate services, not three.
2. **`neon-database-url` secret exists in the prod project** — the dev-tier Neon
   path (§1.3) has already touched this project. This *strengthens* Direction D4
   (Neon-on-AWS): the Neon connection secret is already a live artifact here, so
   dev↔prod DB parity via Neon is less hypothetical than it looked.

> **Recommendation surfaced by the drift check (out of scope for this brainstorm,
> flagged for a separate task):** the orphan `agent-middleware` Cloud Run service
> should be decommissioned on GCP — it serves a placeholder, costs nothing at
> min0 but is a legibility/security footprint (public URL, own revision history).

### 1.3 The dev-tier variant (`infra/dev-tier/`) — do NOT confuse with prod path

There is a **second** IaC stack: `infra/dev-tier/` runs the middleware on Cloud
Run but points Postgres at **Neon Serverless (Free)** with pgvector, adopted via
`import {}` (`dev-tier/neon.tf:1-40`). This is relevant because **Neon runs on
AWS too** — it is a portable data-plane option that could make the dev→prod DB
story identical across clouds (called out as Direction D in §5).

---

## 2. GCP → AWS component mapping (the study)

### 2.1 Service-level mapping with candidates

For each live component, the AWS-native equivalent(s). Where more than one AWS
option exists, I list them because the choice is a §5 direction, not a foregone
conclusion.

| GCP (live) | Primary AWS candidate | Alternatives | Notes / SSE + cost caveats |
|---|---|---|---|
| Cloud Run backend (C1) | **ECS Fargate + ALB** | App Runner; EKS; Lambda (❌ SSE) | ALB idle timeout up to 4000 s clears the 3600 s SSE bar (`AWS_DEPLOYMENT_ARCHITECTURE.md:50`). App Runner is the closest "Cloud-Run-like" scale-to-zero-ish managed option but has weaker SSE/timeout story — **verify before choosing**. Lambda is out (15-min cap + streaming limits vs long SSE). |
| SearXNG sidecar (C2) | **2nd container in same Fargate task** | separate service | Fargate task = multi-container, so the sidecar model ports 1:1. |
| Cloud Run frontend/BFF (C3) | **ECS Fargate + ALB** or **Amplify Hosting** | App Runner; Vercel | Amplify gives edge/SSR but splits the deploy model from the backend. Keeping BFF on Fargate keeps one deploy substrate (modularity vs simplicity trade-off). |
| Cloud SQL PG15 (C4) | **RDS for PostgreSQL** | Aurora Serverless v2; Aurora PG; **Neon-on-AWS** | pgvector supported on RDS PG and Aurora. Aurora Serverless v2 gives scale-to-zero-ish + auto-scaling ACUs (good for dev-like idle). Neon keeps dev==prod. **This is the single biggest -ility lever** (availability + scalability + cost). |
| GCS agent-facts (C5) | **S3** | — | Bucket policy → `s3:GetObject` only for backend role. 1:1. |
| GCS trust-traces (C6) | **S3 + lifecycle to Glacier-IA** | Firehose→S3 if streaming | Lifecycle rule → cheaper class mirrors the Nearline rule. In-process relay means **no Firehose needed** at this tier. |
| Secret Manager (C7) | **AWS Secrets Manager** | SSM Parameter Store (cheaper) | Parameter Store SecureString is ~free vs Secrets Manager $0.40/secret/mo; 9 secrets = trivial either way. Injected into Fargate task def. |
| Meta Cloud Run Job + Scheduler (C8) | **ECS Scheduled Task (EventBridge Scheduler)** | AWS Batch; Step Functions | Nightly cron → EventBridge rule → run-task. Disabled-by-default posture ports directly. |
| Cloud Monitoring + alerts (C9) | **CloudWatch dashboards + alarms** | Managed Grafana | Same 3 signals (5xx, p95, DB conns) + AWS Budgets for the $50 cap. |
| Artifact Registry (C10) | **ECR** | — | 1:1. |
| GCP service accounts (C11) | **IAM task roles** | — | Same least-privilege split: frontend task role gets WorkOS secrets only. Maps to the 4th refactor `services/cloud_providers/aws_identity.py` (`AWS_DEPLOYMENT_ARCHITECTURE.md:149-150`). |
| Langfuse Cloud / WorkOS | **unchanged (external SaaS)** | — | Do not migrate. Egress + 2 secrets only. |
| LiteLLM model calls | **unchanged (provider APIs)** | — | Cloud-independent spend. |

### 2.2 The known code-refactor surface (already documented — bounded)

The existing docs already enumerate the swap-out as **four adapter files**
(`CLOUD_PROVIDER_COMPARISON.md:162-171`, `AWS_DEPLOYMENT_ARCHITECTURE.md:137-150`):
Postgres checkpointer injection (env-gated on `AWS_EXECUTION_ENV`), trace sink
(`kinesis_sink.py` **or** keep the GCS-equivalent S3 relay), AgentFacts registry
(`s3://` URIs), and cloud-provider identity (IAM→AgentFacts). Backend invariant
**I-9** confines all cloud SDKs to `agent_ui_adapter/adapters/runtime/`, so the
**portability radius is 4 files + composition-root wiring** — this is the
modularity/extensibility win we should preserve, not erode.

---

## 3. The decision framed on the "-ilities"

This is the lens you asked for: judge each direction against the quality
attributes, not just the monthly bill. Below, each "-ility" gets (a) what the
GCP stack does today, (b) what AWS must at least match, (c) the lever that moves
it.

| -ility | Where GCP is today | AWS parity bar | The lever (what to decide in §5) |
|---|---|---|---|
| **Availability** | Single-AZ Cloud SQL (C4), scale-to-zero compute (cold-start risk on first SSE) | Multi-AZ Postgres for prod; min-1 compute so first SSE isn't a cold start | RDS Multi-AZ vs Aurora vs Neon; Fargate min-instances ≥ 1 |
| **Scalability** | Cloud Run autoscale 0→10 on requests | Fargate autoscale on ALB conns / CPU; DB connection ceiling (currently 50) is the real limit | Aurora Serverless v2 auto-ACU vs fixed RDS; RDS Proxy for connection pooling |
| **Manageability** | Fully managed serverless; one `tofu apply`; 3 alerts + budget | Keep it managed — Fargate/RDS/managed services, not EKS/self-hosted; same IaC discipline | Fargate+RDS (managed) vs EKS (powerful, heavier ops) |
| **Extensibility** | New provider = new secret + `MODEL_PROFILE_SET`; new sink = new adapter | Preserve the I-9 4-file adapter boundary; don't leak `boto3` outside `adapters/runtime/` | Any direction must keep the adapter seam intact |
| **Modularity** | Combined backend = middleware+agent in one service (C1); BFF separate | Decide: keep combined (simple) or split (isolates blast radius, enables independent scale) | Q1 scope answer + combined-vs-split |
| **Security** | App-layer WorkOS auth, public ingress, per-SA least privilege, enforced no-public-buckets | Match least-privilege via IAM task roles; consider WAF/private subnets for prod | ALB+WAF+private subnets vs App Runner public; Secrets Mgr vs SSM |
| **Observability** | Langfuse (external, unchanged) + Cloud Monitoring 3 alerts | Langfuse unchanged; re-create the 3 CloudWatch alarms + budget | 1:1 CloudWatch mapping |
| **Portability / lock-in** | Bounded to 4 adapter files (I-9) | Keep the radius at 4 files; Neon would make the DB itself cloud-neutral | Neon-on-AWS (Direction D) vs RDS (AWS-native) |
| **Cost-efficiency** | Tier-A ~$12–35/mo (pyramid study); scale-to-zero + `/tmp` (no NFS) + Cloud Logging free tier | Tier-A AWS ~$60–90 (pyramid `CLOUD_PROVIDER_COMPARISON.md:45`) — AWS is structurally pricier at idle; the gap shrinks at prod tiers | Fargate min-instances, Aurora Serverless idle, SSM-over-SecretsMgr, ephemeral-disk-not-EFS |
| **Resilience / DR** | Single region, backups on, no cross-region | Prod: Multi-AZ minimum; cross-region replica if RPO/RTO demands | RDS Multi-AZ (+ optional cross-region read replica); Aurora Global if RPO<1s |

**The cost headline from the anchored study, restated for AWS specifically:**
at **dev/idle tier AWS is the most expensive** of the three clouds (no true
scale-to-zero for HTTP + ALB hours), but the gap **narrows sharply at
small-prod** where AWS Fargate's per-vCPU list price actually *wins*
(`CLOUD_PROVIDER_COMPARISON.md:46`, AWS ~$260 vs GCP ~$310 vs Azure ~$345). Since
**prod is the AWS target and dev stays on GCP**, we are deploying AWS into
precisely the tier where it is competitive — the free-tier penalty largely does
not apply to us. This is the key reconciliation with the pyramid study.

---

## 4. System requirements (functional + non-functional)

> **How this section was produced.** 6 parallel agents derived requirements from
> 6 evidence lenses (compute/SSE, data-plane, security/identity, observability/
> ops, the -ilities, migration/parity); **every** requirement was then
> adversarially verified against the actual repo files (81 derived → 81 survived,
> 61 amended to fix citations/measurability, **0 rejected**). The amendments were
> almost all citation-line corrections — the "context-blindness" check the
> sdd-brainstorm skill mandates, working as intended. **All requirements are
> DIRECTION-INDEPENDENT** — they hold for D1, D2, and D4 alike (§5). Where a
> requirement's *mechanism* differs per direction, it is written outcome-based
> and the mechanism is routed to §4.4 Gaps.
>
> Functional requirements use **EARS** syntax (`docs/plan/_spec_template.md`).
> Every NFR carries a **measurable target**. These become the acceptance-criteria
> substrate at sdd-spec. IDs are draft ids; sdd-spec renumbers.

### 4.1 Functional requirements (EARS)

Grouped: **C** = compute/SSE, **D** = data-plane, **S** = security/identity,
**O** = observability/ops, **M** = migration/parity. Failure-path (`IF…THEN`)
requirements are marked ⚠.

#### C — Compute & SSE ingress

| ID | Requirement | Evidence |
|---|---|---|
| **FR-C1** ⚠ | IF the chosen ingress enforces a request/idle timeout below 3600 s for `/run/stream` THEN THE SYSTEM SHALL fail deployment validation rather than silently truncate SSE; equivalently the ingress timeout SHALL be ≥ 3600 s. | `variables.tf` SSE-timeout guard (==3600); prod SSE surface `app_prod.py:601`. API GW (29–30 s) & Lambda (15 min) disqualified; ALB idle ~4000 s clears it. |
| **FR-C2** ⚠ | IF the backend has scaled to zero and a `/run/stream` request arrives THEN THE SYSTEM SHALL complete cold-start and begin emitting SSE frames while the ingress holds the connection open (idle timeout ≥ 3600 s) so the first request after idle does not fail. | `cloud-run-backend.tf` scaling+GEN2+`cpu_idle`, startup_probe cold-start tolerance; `variables.tf` `backend_min_instances==0`. |
| **FR-C3** | WHEN a client POSTs `/run/stream` with a valid JWT-verified Bearer token THE SYSTEM SHALL stream the response as SSE (`text/event-stream`) over one long-lived connection held ≥ 3600 s. | `app_prod.py:601` (`StreamingResponse`), :607-608 (401 no-Bearer), :614 (JWT verify), :739-741 (media type). |
| **FR-C4** | WHEN the platform probes `GET /healthz` or `/health` THE SYSTEM SHALL respond **pre-auth** with 200 + JSON so the probe needs no WorkOS token. | `app_prod.py:331-341` (pre-auth probe, no auth dependency). |
| **FR-C5** | THE SYSTEM SHALL deploy exactly two app services (backend-combined incl. searxng sidecar; frontend) and SHALL NOT deploy the orphaned `agent-middleware` placeholder. | `cloud-run-backend.tf` (backend + searxng 2nd container), `cloud-run-frontend.tf` (frontend); drift orphan not in Terraform. |
| **FR-C6** | WHILE inbound volume exceeds running capacity THE SYSTEM SHALL horizontally autoscale each service between a scale-to-zero-equivalent idle floor and a per-service, independently-tunable burst ceiling (baseline max 10). | `cloud-run-backend.tf`/`cloud-run-frontend.tf` scaling; `variables.tf` min0/max10 per service. |
| **FR-C7** | THE SYSTEM SHALL provide each backend instance ephemeral local paths for `AGENT_OFFLOAD_DIR=/tmp/agent_offload` and `BLACKBOX_STORAGE_DIR=/tmp/agent_offload/black_box_recordings` and SHALL NOT mount NFS (EFS/Filestore) for offload. | `cloud-run-backend.tf` (`/tmp` offload dirs; sole volume is cloudsql); no `google_filestore` anywhere. |
| **FR-C8** | WHILE the backend runs THE SYSTEM SHALL run the BlackBox→Langfuse relay in-process (asyncio task in lifespan), require no separate Pub/Sub-equivalent at this tier, and set the relay tail dir = recorder write path so it never tails an empty dir. | `app_prod.py:231-247,300-308` (in-process relay), `cloud-run-backend.tf` (`BLACKBOX_RELAY_MODE=in_process`). |

#### D — Data plane

| ID | Requirement | Evidence |
|---|---|---|
| **FR-D1** ⚠ | THE SYSTEM SHALL bound aggregate DB connections (instances × per-process pool, summed over checkpointer + pgvector + thread-store pools) to ≤ the DB `max_connections` ceiling; IF a pool saturates THEN queue with a bounded wait and, on timeout, surface pool-exhaustion and fail the one request (not crash the process). | `data.tf` (`max_connections=50`); `postgres_saver.py` + `pgvector.py` pools (max_size=4 each); `variables.tf` max_instances=10. |
| **FR-D2** ⚠ | IF a config change would make the agent-facts bucket/objects publicly readable THEN THE SYSTEM SHALL block it and keep public-access prevention enforced. | `data.tf` (agent_facts: uniform access, public-access enforced, versioned). |
| **FR-D3** ⚠ | IF the backend runtime attempts read/list/delete on trust-traces THEN THE SYSTEM SHALL deny it; the runtime SHALL hold create/append only (append-only, tamper-evident). *AWS: unique keys + Object Lock/versioning or deny-if-exists, not bare `s3:PutObject`.* | `data.tf` (`objectCreator` write-only; "never reads or deletes"; versioning off = create-only). |
| **FR-D4** | THE SYSTEM SHALL provide offload + BlackBox dirs as instance-local ephemeral disk under `/tmp` and SHALL NOT mount a shared network filesystem. | `cloud-run-backend.tf` (`/tmp` dirs); `data.tf` (Filestore not provisioned). |
| **FR-D5** ⚠ | IF a backend instance terminates/scales-to-zero before the relay flushes pending recordings from `/tmp` THEN THE SYSTEM SHALL treat them as lost and SHALL NOT depend on their durability for request correctness. | `cloud-run-backend.tf` (ephemeral + in-process relay); `variables.tf` min0. |
| **FR-D6** | THE SYSTEM SHALL enable object versioning on the AgentFacts store so any overwrite (auto-provision on first-request KeyError; suspend/restore/update in-place) or non-permanent delete is recoverable to the prior version. | `data.tf` (versioning on agent_facts); `agent_facts_gcs_registry.py` overwrite paths; `app_prod.py:357-378` auto-provision. |
| **FR-D7** | WHEN a trust-traces object reaches 90 days THE SYSTEM SHALL transition it to a cheaper infrequent-access class. | `data.tf` lifecycle (age 90 → cheaper class). |
| **FR-D8** | WHERE memory backend = pgvector THE SYSTEM SHALL store/query embeddings in the same primary Postgres (via `DATABASE_URL`) and SHALL NOT require a separate vector DB. | `cloud-run-backend.tf` (`MEMORY_BACKEND=pgvector`, `EMBEDDING_MODEL=text-embedding-3-small`). |

#### S — Security & identity

| ID | Requirement | Evidence |
|---|---|---|
| **FR-S1** ⚠ | THE SYSTEM SHALL restrict the frontend/BFF identity's secret-read set to exactly {WorkOS API key, WorkOS cookie-password}; IF granted any secret outside that set (DB/LLM/agent-facts) THEN block the grant (deploy-time or runtime deny). | `foundations.tf` (frontend SA WorkOS-only); `secret-manager.tf` (only two frontend grants). |
| **FR-S2** ⚠ | IF any facts/traces bucket is set to permit public read/write THEN THE SYSTEM SHALL block it at provision time. | `data.tf` (public-access enforced + uniform access on both buckets). |
| **FR-S3** ⚠ | IF a request reaches the prod run/stream, thread-CRUD, or memory-CRUD surface without a valid WorkOS session/JWT THEN THE SYSTEM SHALL reject it at the app layer and SHALL NOT rely on network-gateway auth. | `app_prod.py` (app-layer WorkOS; public ingress). |
| **FR-S4** | THE SYSTEM SHALL inject every runtime secret from a managed secret store at container start (10 declared + live rollback secrets) and SHALL NOT bake any secret into an image, task-def literal, or IaC state. | `secret-manager.tf` (secret shells) + `cloud-run-backend.tf` (`secret_key_ref`); `test_secret_manager.py`. |
| **FR-S5** | THE SYSTEM SHALL grant the backend role read access per-secret (individually enumerated) and SHALL NOT grant store-wide/wildcard secret read. | `secret-manager.tf` (one iam_member per secret, backend member; never project-wide). |
| **FR-S6** | THE SYSTEM SHALL grant the trust-traces role write-only and SHALL NOT grant read/list/delete on that bucket. | `data.tf` (`objectCreator` only; meta SA is the sole reader). |
| **FR-S7** | THE SYSTEM SHALL run backend and frontend under two distinct non-shared IAM identities and SHALL NOT share/broaden roles. | `foundations.tf` (disjoint backend/frontend SAs); distinct service bindings. |
| **FR-S8** | WHERE target = AWS THE SYSTEM SHALL resolve identity→AgentFacts via the AWS identity adapter and confine every AWS SDK import to the 4 sanctioned seams (runtime adapter, trace sink, facts registry, cloud-identity). | `utils/cloud_providers/aws_identity.py` (boto3, imports `trust.cloud_identity`); `test_dependency_rules.py` PLANNED_FILES. |
| **FR-S9** | WHILE the backend holds the searxng sidecar THE SYSTEM SHALL keep it without external ingress, reachable only over localhost. | `cloud-run-backend.tf` (searxng port 8888, no ingress, reached via `SEARXNG_URL=http://localhost:8888`). |

#### O — Observability & ops

| ID | Requirement | Evidence |
|---|---|---|
| **FR-O1** ⚠ | IF a deploy references a **primary app service** image by mutable tag (not `@sha256:…`) THEN THE SYSTEM SHALL reject it; a co-located sidecar (searxng) MAY waive digest-pin if it carries no external ingress. | `deploy_gcp.sh` (backend+frontend → digest; searxng deliberately `:latest`). |
| **FR-O2** | WHILE the backend is starting THE SYSTEM SHALL gate readiness on pre-auth `/healthz` and SHALL NOT route traffic until it returns 200. | `app_prod.py:331-333`; `variables.tf` placeholder-fails-`/healthz`. |
| **FR-O3** | WHEN a running instance stops returning 200 from `/healthz` for the failure window THE SYSTEM SHALL restart/replace it. | `app_prod.py:331` (liveness probe). |
| **FR-O4** ⚠ | IF backend 5xx rate > 5% sustained over 5 min THEN THE SYSTEM SHALL alert the notification channel. | `observability.tf` (backend_5xx_rate, 5-min); `variables.tf` default 0.05. |
| **FR-O5** ⚠ | IF backend p95 latency (non-streaming series, **excluding** the long-lived `/run/stream` path) > 5000 ms over 5 min THEN THE SYSTEM SHALL alert. *(SSE exclusion is new — the live policy has none.)* | `observability.tf` (p95 policy, no SSE exclusion today); `variables.tf` default 5000. |
| **FR-O6** ⚠ | IF active DB connections > the ceiling threshold (default 50) over 5 min THEN THE SYSTEM SHALL alert. | `observability.tf` (cloud_sql_connections); `variables.tf` default 50. |
| **FR-O7** | WHEN MTD spend reaches 50%/90% of the monthly budget, and forecast reaches 100%, THE SYSTEM SHALL emit budget-threshold alerts at each. | `observability.tf` (0.5/0.9 CURRENT, 1.0 FORECASTED); `variables.tf` default $50. |
| **FR-O8** | THE SYSTEM SHALL write backend+frontend logs to stdout/stderr, collected as structured records queryable by service, revision, and severity. | `observability.tf` (revision-log triage); `app_prod.py:167` stdlib logging. |
| **FR-O9** | WHERE the meta/eval ring is enabled THE SYSTEM SHALL run `python -m meta.run_eval` on the configured cron (default 06:00 UTC); disabled by default it provisions no scheduler/job. | `meta.tf` (enable gate, cron, command). |
| **FR-O10** | THE SYSTEM SHALL keep exporting traces to external Langfuse Cloud unchanged and SHALL NOT re-host/migrate/proxy it — only the two Langfuse secrets + egress are provisioned. | `secret-manager.tf` (langfuse keys); `cloud-run-backend.tf` (`LANGFUSE_HOST`). |
| **FR-O11** ⚠ | WHEN a promoted revision fails `/healthz` or trips the 5xx alert during rollout THEN THE SYSTEM SHALL provide an operator rollback to the prior healthy digest-pinned revision within 5 min, no rebuild. | `variables.tf` health-gated promotion; `cloud-run-backend.tf` per-revision pin. |

#### M — Migration & parity

| ID | Requirement | Evidence |
|---|---|---|
| **FR-M1** ⚠ | IF a module outside the cloud-adapter seam set imports a cloud SDK (boto3/google-cloud/azure) THEN THE SYSTEM SHALL fail a dedicated `tests/architecture/` confinement test and block the gate. *(This test does not exist yet — new work.)* | Live import map (google.cloud in trace_sinks/governance/runtime-config); `test_dependency_rules.py`; boto3 under `aws=[…]` (`pyproject.toml`). |
| **FR-M2** ⚠ | IF the AWS IaC declares more than two **application** services THEN THE SYSTEM SHALL fail the IaC policy gate (bounds app-service count only, not data/secrets/observability infra). | `infra/gcp/` = exactly two `cloud_run_v2_service`; searxng is a sidecar; `policies/*.rego` precedent. |
| **FR-M3** ⚠ | IF the AWS-prod region for data-at-rest is not a US region THEN THE SYSTEM SHALL be rejected (GCP-dev baseline us-central1; prod must not widen residency). | Ground-truth `us-central1`; Cloud SQL + GCS are residency-bearing. |
| **FR-M4** | THE SYSTEM SHALL expose the `app_prod.py` prod surface (`/run/stream` SSE, `/healthz`+`/health`, `/agent/threads` CRUD, `/agent/memory` CRUD) with identical paths/methods/status/media-types/JSON schemas so the BFF needs zero changes; SHALL NOT substitute the dev `server.py` surface (`/agent/runs/stream`). | `app_prod.py` (prod routes, response_model-typed); dev surface `server.py:475` divergent path. |
| **FR-M5** | WHERE `AWS_EXECUTION_ENV` is set THE SYSTEM SHALL select the AWS variant of each of the 4 seams at the shared composition root, with GCP-dev keeping its native variant and no application-code fork. | `postgres_saver.py`, `agent_facts_registry.py` (+S3 variant TBD), `aws_identity.py`; `AWS_EXECUTION_ENV` switch unbuilt (docs only). |
| **FR-M6** | THE SYSTEM SHALL preserve the ephemeral-disk offload contract on every direction and SHALL NOT introduce EFS/Filestore for offload/blackbox. | `cloud-run-backend.tf` offload env; only volume is cloudsql; Filestore un-chosen. |
| **FR-M7** | THE SYSTEM SHALL route all LLM+embedding calls through LiteLLM (registry from `MODEL_PROFILE_SET`) so the call path is byte-identical across clouds; the only cloud difference is the secret-store binding for the keys. | `cloud-run-backend.tf` (`MODEL_PROFILE_SET`, provider keys); `services/llm_config.py`. Token spend cloud-independent. |
| **FR-M8** | THE SYSTEM SHALL keep reaching Langfuse Cloud + WorkOS as external SaaS via egress + two secrets each and SHALL NOT migrate/self-host either. | `cloud-run-backend.tf` (`LANGFUSE_HOST`); `secret-manager.tf` (workos + langfuse secrets). |
| **FR-M9** ⚠ | THE SYSTEM SHALL enforce app-layer WorkOS auth with public ingress; IF `/run/stream` carries a missing/non-`Bearer ` Authorization header THEN reject with 401 before any run, byte-identically to GCP. Parity does NOT require relocating auth to a network gateway. | `app_prod.py:607-608` (401), :614 (verify); public ingress `cloud-run-backend.tf` (allUsers invoker + INGRESS_TRAFFIC_ALL). |
| **FR-M10** | THE SYSTEM SHALL preserve the least-privilege secret split (frontend → WorkOS only; never DB/LLM). | Parity restatement of FR-S1; `foundations.tf` frontend SA. |

### 4.2 Non-functional requirements (every target measurable)

> **⚙ COST/AZ DECISION (2026-07-14): single-AZ + minimal cost.** The user chose
> **one availability zone (no Multi-AZ HA)** and **minimize cost** for the AWS
> prod target. This is the same posture GCP-dev runs today (Cloud SQL `ZONAL`,
> scale-to-zero). The availability/resilience NFRs below are **re-baselined to
> single-AZ**: HA-premium items (Multi-AZ standby, warm min-1 floor) are relaxed
> to their cost-minimal form, and the availability we *give up* is stated
> explicitly rather than hidden. **DR now rests on backups + PITR, not on a hot
> standby** — an AZ outage means restore-from-backup (minutes-to-an-hour of
> downtime), which is the accepted trade for minimal cost. Multi-AZ remains a
> documented **future upgrade lever** (§4.4), not current scope.

| ID | -ility | Measurable target | Direction note |
|---|---|---|---|
| **NFR-AVAIL-1** ⤵ | availability | **Single-AZ (revised).** Primary Postgres in **one AZ**, no synchronous standby. Target endpoint availability = the single-instance managed-service SLA (**~99.5% monthly**, e.g. RDS single-AZ), **not** 99.95%. On instance/AZ loss, recovery is restore-from-backup (see NFR-RESIL-1), **not** sub-minute failover. *Accepted downtime trade for minimal cost.* | single-AZ; Multi-AZ = future lever (§4.4) |
| **NFR-AVAIL-2** ⤵ | availability | **Cost-minimal floor (revised).** Prod services MAY run **min-instances = 0** (scale-to-zero) to minimize idle cost — matching GCP-dev — accepting a cold-start on the first request after idle. WHERE a warm floor is later funded, min-1 removes the cold-start on time-to-first-SSE-byte (≤ 1000 ms p95). Default: **min-0, cold-start accepted.** | cost-minimal; warm-floor = opt-in |
| **NFR-SCALE-1** | scalability | Backend autoscales up to a configurable ceiling (baseline max 10); a cross-instance connection pooler (RDS Proxy / Aurora / Neon pooler) keeps aggregate server-side DB conns ≤ (`max_connections` − ≥ 5 admin headroom). *At minimal-cost single-instance baseline the pooler may be deferred until scale-out is enabled (see §4.4).* | pooler deferrable at min-cost |
| **NFR-SCALE-2** | scalability | Ingress sustains `/run/stream` with idle/request timeout **≥ 3600 s**, no cap below. API GW/Lambda disqualified; **App Runner 3600s-SSE support is UNVERIFIED** and must be proven pre-selection. | D2 kill-criterion |
| **NFR-SCALE-3** | scalability | Each backend instance accepts up to **80 concurrent** in-flight requests before the autoscaler adds one (matches live Cloud Run concurrency; AWS: ALB target-group / App Runner MaxConcurrency). | dir-independent |
| **NFR-RESIL-1** ⤵ | resilience/DR | **Backup-based DR (single-AZ).** Automated daily DB backups retained ≥ 7 days + continuous PITR. On primary/AZ loss the recovery path is **restore-from-backup** (no hot standby): target **RPO ≤ 5 min** (PITR), **RTO ≤ 60 min** (restore + reconnect). This is the load-bearing DR control now that Multi-AZ is out of scope. | single-AZ; restore-not-failover |
| **NFR-DR-1** | resilience/DR | Prod object stores: S3-Standard-class 11-nines durability (S3 is inherently multi-AZ within a region **at no extra cost** — object durability is NOT affected by the single-AZ compute/DB decision); preserve 90-day→cold lifecycle on traces + versioning on facts; object-store RPO = 0 for written objects. | dir-independent (S3 multi-AZ is free) |
| **NFR-PORT-1** | portability | **0** new cloud-SDK imports outside the provider/trace-sink/registry modules + 4-file radius; trust/ and components/ get 0 cloud-SDK imports. Verified: `test_dependency_rules.py` green, 0 new violations. | dir-independent |
| **NFR-PORT-2** | portability | Dev+prod built from one unchanged source tree; cloud switch = 0 app-source changes outside ≤ 4 adapter files + a cloud-extra swap (`.[aws]` vs `.[gcp]`). *(Images NOT byte-identical — boto3 vs google-cloud is a build-time dep; digest parity is not a valid target.)* | dir-independent |
| **NFR-COST-1** | cost-efficiency | Offload confined to ephemeral `/tmp`; **0** `aws_efs_*`/`aws_fsx_*` resources in the plan (no ~1 TiB provisioned-minimum trap). | dir-independent |
| **NFR-COST-2** | cost-efficiency | Budget alerts at 50%/90%/100% of a USD ceiling (dev default $50/mo); secret-store line item **≤ $5/mo** at small-prod (SSM SecureString $0 or Secrets Manager ~$4/mo both satisfy). | dir-independent |
| **NFR-COST-META-1** | cost-efficiency | Meta ring disabled (default) adds **$0/mo** standing compute — no always-on scheduler/worker. | dir-independent |
| **NFR-RESOURCE-1** | cost-efficiency | Compute floors: backend ≥ 1 vCPU/2 GiB; searxng ≥ 0.5 vCPU/512 MiB; frontend ≥ 1 vCPU/512 MiB (match live GCP). | dir-independent |
| **NFR-MANAGE-1** | manageability | Prod uses only fully-managed compute (Fargate/App Runner-class), **0 self-managed nodes**; EKS out of scope. | excludes D6 |
| **NFR-MANAGE-2** | manageability | Meta ring = scheduled job (EventBridge cron 06:00 UTC → `python -m meta.run_eval`), disabled by default behind one flag, **$0** while off. | dir-independent |
| **NFR-SEC-1** | security | Per-service least-privilege IAM: frontend role reads exactly 2 WorkOS secrets, 0 backend-only; backend reads its secrets but NOT `workos-cookie-password`. CI IAM set-assertion. | dir-independent |
| **NFR-SEC-2** | security | 100% of secret material via secret-store refs; **0** plaintext secrets in image/task-def/IaC/state; scan (gitleaks + no-plaintext HCL) finds 0. | dir-independent |
| **NFR-SEC-3** | security | Prod ingress terminates TLS at the edge; prod surface served **HTTPS-only** (0 cleartext listeners, TLS 443) while holding SSE idle ≥ 3600 s. | dir-independent |
| **NFR-SEC-4** | security | Data tier + searxng reachable by **0 public internet principals** (private subnet / private endpoint). **Net-new hardening** (GCP Cloud SQL still has public IPv4). | dir-**dependent** control → gap |
| **NFR-OBS-1** | observability | Re-create the 3 alerts as CloudWatch alarms at parity thresholds/5-min windows; 5xx (>5%) + p95 (>5000 ms, SSE-excluded) carry verbatim; connections threshold re-anchors to the pooled ceiling (dev's 50 doesn't transfer). | dir-independent |
| **NFR-OBS-2** | observability | Each alert fires only after threshold holds over 300 s with 60 s alignment (matches GCP), so false-positive rate stays equivalent. | dir-independent |
| **NFR-OBS-PROBE-1** | observability | `/healthz` responds **< 1 s p95**, needs 0 auth, and its handler makes **0 LLM calls, 0 DB round-trips** so probe polling never hits the hot path. | dir-independent |
| **NFR-DATA-CONN-1** | scalability | DB max-connections ceiling ≥ 50 (matches live); aggregate pool cap ≤ (ceiling − ≥ 3 admin headroom). | dir-independent |
| **NFR-DATA-BACKUP-1** | recoverability | Automated DB backups, retention ≥ 7 days, PITR to any point in window. | dir-independent |
| **NFR-DATA-STORAGE-1** | scalability | DB ≥ 10 GB SSD-class, configured to autogrow before free space < 10% (avoid write-stall). | dir-independent |
| **NFR-DATA-FACTS-INTEGRITY-1** | compliance | Facts+traces stores enforce uniform/bucket-owner access + block-public-access; scan finds 0 ACL-exposed objects, 0 public buckets. *(At-rest encryption tracked separately — see gap.)* | dir-independent |
| **NFR-DEPLOY-1** | deployability | Primary app images deployed only by digest (`@sha256`); 0 mutable-tag promotions (sidecar `:latest` waived if no ingress); rollback re-serves prior healthy digest ≤ 5 min, no rebuild. | dir-independent |
| **NFR-TEST-1** | testability | AWS IaC validatable pre-apply with **0 live-cloud calls**; dev guards (SSE==3600, disk≥10 GB) preserved as prod-tier plan assertions. | dir-independent |
| **NFR-MAINT-1** | maintainability | Cloud selection entirely via runtime env + composition-root injection; AWS port touches exactly the ≤ 4 seams, **0** cloud branches in trust/, components/, non-provider services/. | dir-independent |
| **NFR-PARITY-ENVVAR-1** | portability | **100%** of behavior-selecting env vars identical dev↔prod (offload/relay/memory/embedding/profile/search/judge/memory/arch flags); cloud-coupled locators (`MIDDLEWARE_URL`, `DATABASE_URL` host, bucket names, exec-env) may differ in value but stay behavior-equivalent. | dir-independent |
| **NFR-PARITY-SSE-1** | reliability | AWS-prod ingress holds one `/run/stream` connection **≥ 3600 s** without idle termination, on **both** backend and frontend-BFF hops (GCP pins both). | dir-independent |
| **NFR-PARITY-MEM-1** | portability | Prod Postgres carries all **three** loads (checkpointer + durable thread store + pgvector) on one engine via one `DATABASE_URL`, `MEMORY_BACKEND=pgvector`, 0 composition-root change. Any Postgres-with-pgvector target satisfies it. | dir-independent |

### 4.3 Hard constraints (bound every direction)

These are the non-negotiable bounds every candidate in §5 must respect:

1. **SSE ≥ 3600 s** ingress hold on `/run/stream` — API Gateway (~29 s) and Lambda streaming (15 min) **disqualified**; ALB (~4000 s) clears it.
2. **Prod surface is `middleware/app_prod.py`** (not the dev `server.py`) — route/method/status/media-type/JSON contract preserved so the BFF changes zero.
3. **Exactly two app services** (backend-combined incl. searxng sidecar; frontend). The `agent-middleware` orphan is **not** ported.
4. **Ephemeral `/tmp` offload — no EFS/FSx/Filestore/NFS** (avoids the ~1 TiB minimum trap); relay stays **in-process**, no SQS/Pub-Sub at this tier.
5. **pgvector on the SAME primary Postgres** (one `DATABASE_URL`, three co-located loads) — no separate vector DB.
6. **App-layer WorkOS auth, public ingress** — 401 before any run on `/run/stream`; do not relocate auth to a network gateway as a parity requirement.
7. **Cloud-SDK confinement** to the 4 seams; trust/ and components/ get 0 cloud-SDK imports. *(No literal `I-9` string in the repo — enforced by `test_dependency_rules.py`; a dedicated confinement test is new work.)*
8. **Fully-managed only** (Fargate/App Runner-class); EKS/self-managed K8s out of scope.
9. **External SaaS unchanged** (Langfuse Cloud, WorkOS) — egress + two secrets each. LLM spend cloud-independent via LiteLLM.
10. **US data residency** for prod data-at-rest (GCP-dev baseline `us-central1`); prod must not widen it.
11. **GCP = dev, AWS = prod — BOTH single-AZ, cost-minimal (2026-07-14 decision).** Prod does **not** add Multi-AZ HA or a mandatory warm floor; it keeps the same Tier-A cost posture as dev (single-AZ Postgres, scale-to-zero-capable compute, small budget). The **one** prod-over-dev hardening kept is **backups + PITR + ≥ 7-day retention** (NFR-RESIL-1), since that is the DR control once there's no standby. Multi-AZ / warm-floor / cross-region are **future upgrade levers**, not current scope (§4.4 #10).
12. **Secret hygiene:** managed store at container start, 0 plaintext; backend per-secret grants; frontend reads only the 2 WorkOS secrets; trust-traces role write-only; distinct per-service IAM identities.

### 4.4 Gaps — direction-dependent / needs-probe (resolve at sdd-spec)

Requirements above are direction-independent; these choices are **not**, and are deliberately left for sdd-spec so no direction is baked in prematurely:

1. **Postgres engine UNDECIDED (single-AZ, cost-minimal variants)** — D1 RDS **single-AZ** `db.t4g.micro`/`small` (native pgvector, cheapest), D2 Aurora Serverless v2 (min-ACU floor — pricier at idle, scales better), or D4 Neon-on-AWS free/launch tier (scale-to-zero DB, cheapest at idle). Pick the cheapest that meets NFR-RESIL-1 backups+PITR; failover topology is out of scope (single-AZ).
2. **Compute engine UNDECIDED** — D1 Fargate+ALB vs D2 App Runner. **App Runner's 3600 s SSE hold is UNVERIFIED** (NFR-SCALE-2 / NFR-PARITY-SSE-1) — the first spec kill-criterion; failing it disqualifies D2 for the SSE surface.
3. **NFR-SEC-4 network isolation is direction-dependent** (in-VPC private subnet for D1/D2 vs Neon PrivateLink for D4) — and is **net-new hardening** over current GCP (Cloud SQL still exposes public IPv4).
4. **Lifespan-flush on scale-in** (FR-C8/FR-D5) — engines that hard-kill on scale-in (App Runner min=0) must let the in-process relay drain during shutdown or lose unflushed recordings. Verify graceful shutdown for the chosen engine (D2 flag).
5. **Cross-region DR pair** unspecified — pick the US region + any DR-secondary at spec (must satisfy US-residency).
6. **Encryption-at-rest** is provider-default today (no explicit KMS in live IaC) — decide SSE-KMS vs SSE-S3 and DB storage-encryption key ownership for prod.
7. **New work to author** — the FR-M1 cloud-SDK confinement test, `AWS_EXECUTION_ENV` gating, the S3/Kinesis trace sink, and `agent_facts` `s3://` support are all **unbuilt** (`git grep AWS_EXECUTION_ENV` = docs only).
8. **FR-O5 SSE-exclusion** from the p95 alert is a **new obligation** (live policy has none) — design the metric split so long streams don't trip the 5000 ms alarm.
9. **Prod-tier re-baselining** — the $50 budget, `max_connections=50`, and 50-conn alert threshold are dev defaults; re-tune prod values once the engine/DB choice is fixed.
10. **Future HA upgrade levers (deferred by the 2026-07-14 single-AZ+cost-minimal decision, NOT dropped)** — flip RDS to Multi-AZ (~2× DB cost), set compute warm floor min-1 (removes cold-start, adds idle cost), add a cross-region replica / cross-AZ read path. Each is a one-knob change when availability needs outgrow the cost ceiling; documented here so the single-AZ choice is reversible, not a dead-end.

> **Note on `infra/dev-tier` (Neon):** the dev-tier Neon stack was **retired via
> ADR-0031** during this work. That does not affect these requirements or
> Direction D4 (Neon-on-AWS remains a live *option* for the AWS prod DB) — it only
> means there is no longer a separate dev-tier Neon IaC to mirror; the
> `neon-database-url` secret's continued presence in the prod project is tracked
> by the orphan-cleanup task.

---

## 5. Candidate deployment directions (~6, for sdd-spec)

Each is a coherent end-to-end posture, with the -ility it optimizes and the
evidence/risk. These are **candidates to choose among**, not a plan. Every
direction must satisfy the direction-independent requirements in §4; they differ
only on the §4.4 gap axes.

### D1 — Faithful lift-and-shift: Fargate + ALB + RDS Multi-AZ
Mirror the combined-backend topology 1:1 on ECS Fargate behind ALBs, RDS
PostgreSQL Multi-AZ, S3 for facts+traces, Secrets Manager, EventBridge for meta.
- **Optimizes:** manageability, availability, lowest surprise. Matches the
  existing `AWS_DEPLOYMENT_ARCHITECTURE.md` almost exactly.
- **Risk:** RDS Multi-AZ carries a 2× HA premium; min-1 Fargate removes idle
  savings. Highest baseline cost of the six.
- **Best when:** small-prod, want proven/boring, commit-discount posture later.

### D2 — Cost-lean serverless: App Runner + Aurora Serverless v2
Use App Runner (Cloud-Run-closest managed compute) + Aurora Serverless v2
(auto-scaling ACUs, near-idle floor) to preserve the scale-to-zero-ish economics.
- **Optimizes:** cost-efficiency, scalability (auto-ACU), manageability.
- **Risk:** **must verify App Runner's SSE/long-timeout support against the
  3600 s bar** — this is the kill-criterion. Aurora Serverless v2 has a minimum
  ACU floor (not truly zero).
- **Best when:** spiky/low-baseline prod, want least ops.

### D3 — Split the combined backend: middleware service ‖ agent service
Break C1 into two Fargate services (auth/ACL vs agent SSE runtime) so they scale
and fail independently; BFF stays a third.
- **Optimizes:** modularity, availability (blast-radius isolation),
  scalability (scale the LLM-bound agent tier separately from cheap auth).
- **Risk:** more moving parts, more IaC, higher manageability cost; only pays off
  at higher tiers. Directly depends on the **Q1 scope answer**.
- **Best when:** eng-coach is expected to scale hard and you want independent
  autoscaling.

### D4 — Cloud-neutral data plane: Neon-on-AWS (dev==prod DB)
Keep compute on Fargate/App Runner but use **Neon Serverless** (already the
dev-tier DB, `dev-tier/neon.tf`) as the Postgres for prod too. Neon runs on AWS.
- **Optimizes:** portability (DB no longer cloud-locked), manageability (one DB
  vendor for dev **and** prod), scale-to-zero DB economics.
- **Risk:** Neon is a managed-SaaS dependency (not AWS-native); branching/HA/SLA
  posture at prod scale needs validation; connection model vs RDS Proxy.
- **Best when:** you value dev↔prod parity and DB portability over AWS-native
  consolidation.

### D5 — Carve out eng-coach as its own service
Deploy **only** the eng-coach (its agent runtime + item-bank/eval data) as a
standalone AWS service, leaving the rest of the monorepo on GCP or out of scope.
- **Optimizes:** modularity (product-level isolation), extensibility (independent
  release cadence), smallest blast radius.
- **Risk:** requires eng-coach to actually be separable — **needs a code scout**
  to confirm it isn't entangled with the shared backend. Directly the third
  option in **Q1**.
- **Best when:** eng-coach has an independent lifecycle/SLA from the rest.

### D6 — Kubernetes (EKS) for maximum control
Run everything on EKS.
- **Optimizes:** scalability ceiling, extensibility (any workload), portability
  (K8s is cloud-neutral).
- **Risk:** **worst manageability** — heavy ops burden, contradicts the current
  "one `tofu apply`, fully managed" posture. Almost certainly over-engineered for
  the current tier (violates the repo's anti-slop "simplest thing" rule unless
  scale demands it).
- **Best when:** you're already standardized on K8s org-wide, or Tier-C multi-
  workload scale. **Listed for completeness; not recommended at current tier.**

### Direction comparison at a glance

| Dir | Compute | Postgres | Optimizes | Kill-criterion to check first |
|---|---|---|---|---|
| D1 | Fargate + ALB | RDS Multi-AZ | availability, manageability | none major (boring/proven) |
| D2 | App Runner | Aurora Serverless v2 | cost, scalability | **App Runner SSE @ 3600 s?** |
| D3 | 2× Fargate split | RDS Multi-AZ | modularity, availability | Q1 scope; is split worth the ops? |
| D4 | Fargate/App Runner | **Neon on AWS** | portability, parity | Neon prod HA/SLA at scale |
| D5 | eng-coach only | its own DB/schema | modularity, isolation | **is eng-coach separable?** (code scout) |
| D6 | EKS | RDS/Aurora | scale ceiling, control | manageability cost — likely over-built |

---

## 6. Preliminary lean (now that Q1=whole-stack, Q2=drift-checked)

With scope = **whole stack** and the drift check showing **two** live app
services, the field narrows to **D1 / D2 / D4** (D3, D5, D6 deferred). The
recommendation to carry into sdd-spec:

- **Lead with D1 (Fargate + ALB + RDS Multi-AZ) as the spine**, because:
  - It is the only direction with **no unresolved kill-criterion** (D2 still
    needs App Runner's SSE/3600s support proven).
  - "Whole stack, prod target" lands in the tier where AWS is cost-competitive
    (`CLOUD_PROVIDER_COMPARISON.md:46`), so the D1 baseline isn't a cost penalty.
  - ALB's 4000 s idle timeout is the proven answer to the 3600 s SSE bar.
- **Fold in the cheap D2-flavored tweaks** (no new direction, just cost hygiene):
  SSM Parameter Store instead of Secrets Manager for the 9–11 secrets, S3
  lifecycle mirroring the Nearline rule, **ephemeral `/tmp` not EFS** (the live
  stack already proves this works — §1.2), Fargate min-instances tuned to avoid
  cold-start SSE.
- **Evaluate D4 (Neon-on-AWS) as the Postgres choice within D1**, not a separate
  path — the `neon-database-url` secret is *already live in the prod project*
  (§1.2b), so dev↔prod DB parity is a low-friction option worth pricing in the
  spec against RDS Multi-AZ / Aurora Serverless v2.
- **Two AWS Fargate app services, not three** — mirror only
  `agent-backend-combined` (+ searxng sidecar container) and `agent-frontend`.
  Do **not** recreate the `agent-middleware` orphan.
- **D2 stays a live contender** *if* a quick spike confirms App Runner holds a
  3600 s SSE stream — then it becomes the cheaper/simpler substrate for D1's
  topology. That spike is the first thing to settle in sdd-spec.
- **D3 / D5 / D6 deferred** (anti-slop: no split, no carve-out, no EKS without a
  failure that justifies it).

## 7. What this brainstorm deliberately did NOT do

- No IaC, no code (that's sdd-spec / sdd-implement).
- **The §4 requirements are Stage-1 EARS candidates, not the approved spec.** They
  are direction-independent and evidence-verified, but the formal EARS acceptance
  criteria (with the §4.4 gap axes resolved) belong to sdd-spec.
- No dollar re-derivation — reused the anchored pyramid study rather than
  recomputing (`CLOUD_PROVIDER_COMPARISON.md` §4).
- No App Runner SSE spike — that's the first sdd-spec kill-criterion for D2.
- No decommission of the `agent-middleware` orphan — flagged for a separate task
  (§1.2b), not part of the AWS migration scope.
- ✅ Live `gcloud` drift check — **done** (§1.2b), per the Q2 answer.
- ✅ System requirements (functional + non-functional) — **done** (§4): 46 FR +
  32 NFR, every one verified against repo evidence.

---

## 8. Next step

Scope (Q1=whole-stack) and inventory (Q2=drift-checked) are settled. The path
forward:

1. **Move to sdd-spec** with **D1 as the spine** + D2 tweaks + D4 evaluated as
   the Postgres choice (per §5). Write EARS acceptance criteria for: two Fargate
   services behind ALBs (3600 s SSE), Postgres choice (RDS Multi-AZ vs Aurora
   Serverless v2 vs Neon), S3 for facts+traces, SSM/Secrets for the 9–11
   secrets, EventBridge for the meta ring, CloudWatch for the 3 alerts + budget.
2. **First spec kill-criterion:** prove (or refute) App Runner holding a 3600 s
   SSE stream — decides whether the compute substrate is App Runner (D2) or
   Fargate+ALB (D1).
3. **Optional parallel task (not migration scope):** decommission the orphan
   `agent-middleware` Cloud Run service on GCP.
