---
type: runbook
title: 'GCP Deployment Architecture'
description: 'Scope: Deployment topology, infrastructure mapping, and cloud-native service alignment for the LangGraph-based AgentsFramework ReAct agent on Google Cloud Platform (GCP).'
tags: [architecture]
---

# GCP Deployment Architecture

**Scope:** Deployment topology, infrastructure mapping, and cloud-native service alignment for the LangGraph-based AgentsFramework ReAct agent on Google Cloud Platform (GCP).

**Audience:** Cloud Architects, DevOps Engineers, and Backend Developers responsible for deploying and operating the multi-ring agent architecture in production.

**Related documents:**
- `docs/Architectures/BACKEND_SOLUTION_ARCHITECTURE.md` — Backend architecture, layer invariants, and current state cache/storage contracts.
- `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md` — Outer adapter ring overview.
- `docs/Architectures/AWS_DEPLOYMENT_ARCHITECTURE.md` — AWS Deployment Architecture equivalent.

---

## 1. Governing Thought

> The GCP deployment mirrors the logical boundaries of the **multi-ring agent architecture**. We map the Next.js Frontend Ring to edge-optimized serverless hosting, the BFF and Backend Rings to elastic containerized compute with long-lived connection support (SSE), and stateful artifacts (checkpoints, immutable agent facts, trace logs) to managed GCP data stores (Cloud SQL, GCS, Pub/Sub) rather than local file systems.

### Situation, Complication, Question, Answer

- **Situation:** The local architecture relies on local SQLite checkpointers, JSONL file sinks, and local `.env` files to maintain agent state, trace governance, and API keys. The Next.js UI relies on Server-Sent Events (SSE) to stream real-time agent thoughts.
- **Complication:** Containerized deployments in GCP (e.g., Cloud Run/GKE) have ephemeral file systems. Standard API gateways have strict timeout limits that can break long-running SSE streams. The offline Meta Ring must process massive amounts of trace data asynchronously without impacting the real-time agent loops.
- **Question:** How do we map the four-layer ReAct grid and its rings to GCP managed services to ensure high availability, security, and persistence without violating the architectural invariants?
- **Answer:** Deploy compute on **Cloud Run** (Frontend, BFF, and Backend). Swap SQLite for **Cloud SQL (PostgreSQL)**, local file logs for **Google Cloud Storage (GCS) via Pub/Sub**, and local `.env` configurations for **Secret Manager**.

---

## 2. Infrastructure Mapping

The current state of the backend heavily utilizes the local `cache/` and `logs/` directories. We must adapt these to GCP Native services.

| Local Concept | GCP Managed Service | Implementation Notes |
|---|---|---|
| `cache/checkpoints.db` (SQLite) | **Cloud SQL for PostgreSQL** / **AlloyDB** | The adapter ring's LangGraph checkpointer must swap from SQLite to the Postgres-based `AsyncPostgresSaver`. |
| `cache/black_box_recordings/*.jsonl` | **Pub/Sub** → **Cloud Storage (GCS)** | `services/trace_sinks/` needs a `gcs_sink.py` or `pubsub_sink.py`. Pub/Sub Cloud Storage subscriptions micro-batch streams of `TrustTraceRecord` events into GCS. |
| `cache/agent_facts/*.json` | **Google Cloud Storage (GCS)** | Immutable trust identity cards. IAM roles restrict the Backend service account to `roles/storage.objectViewer` only. |
| `cache/.agent_offload/` & `cache/.agent_plans/` | **Filestore** (NFS) | Filestore volumes mounted directly to Cloud Run instances via Direct VPC Egress to mimic standard file paths for tool offloading. |
| `logs/*.log` | **Cloud Logging** | Handled natively by Cloud Run routing standard output/error to Cloud Logging. |
| `.env` variables | **Secret Manager** | Securely mounted as volumes or exposed as environment variables in Cloud Run containers at startup. |

---

## 3. Compute and Networking Rings

To support the streaming nature of LangGraph agents (SSE), we utilize Global HTTP(S) Load Balancers which support configurable backend timeouts to allow long-lived SSE streams.

### 3.1 Topologies

1. **Browser Ring (Frontend)**
   - **Service:** Cloud Run (or Firebase Hosting combined with Cloud Run for SSR).
   - **Role:** Hosts the Next.js 15 App Router application. Supports native edge caching (Cloud CDN) and streaming responses.

2. **Middleware Ring (BFF / FastAPI)**
   - **Service:** Cloud Run + Global HTTP(S) Load Balancer.
   - **Role:** Handles authentication (WorkOS), rate-limiting, and SDK telemetry (Langfuse, Mem0). Bridges the frontend to the internal agent infrastructure. Timeout settings on the Load Balancer are extended for SSE.
   - **Langfuse export:** The `/run/stream` endpoint emits domain events to Langfuse Cloud via `telemetry_bridge.py` → `LangfuseCloudExporter`. Each agent run produces a Langfuse trace keyed by `trace_id`, with child spans for tool calls, LLM messages, and run lifecycle events. The `LANGFUSE_ENABLED=false` kill switch disables export without affecting SSE (O1 rule). Langfuse Cloud Hobby tier: 50K observation units/mo free.

3. **Adapter & Four-Layer Backend Ring**
   - **Service:** Cloud Run (Internal Ingress) + Internal HTTP(S) Load Balancer.
   - **Role:** Runs the `agent_ui_adapter/server.py` FastAPI app. Executes the LangGraph ReAct and Pyramid topologies.
   - **Scaling Strategy:** Autoscaling based on concurrent requests and CPU utilization. Max instances configured to control costs and database connection limits.

4. **Offline Meta Ring (Governance & Optimizer)**
   - **Service:** Cloud Scheduler + Cloud Run Jobs.
   - **Role:** Runs `meta/run_eval.py`, judges, and drift detection.
   - **Execution:** Cloud Scheduler triggers Cloud Run Jobs on a cron schedule (e.g., nightly) to pull from the GCS Trust Traces bucket, run eval over traces, and write metrics back.

---

## 4. Architecture Diagram

```mermaid
flowchart TD
    subgraph Edge ["GCP Edge"]
        Frontend[Cloud Run<br/>Next.js 15 UI]
    end

    subgraph PublicVPC ["External Networking"]
        BFF_LB[Global HTTP(S) LB<br/>Extended Timeout]
    end

    subgraph PrivateVPC ["VPC Network"]
        BFF[Cloud Run: BFF<br/>FastAPI + WorkOS]
        Internal_LB[Internal HTTP(S) LB<br/>Extended Timeout]
        Backend[Cloud Run: Backend<br/>Internal Ingress Only]

        Meta[Cloud Run Jobs: Meta Ring<br/>run_eval.py]
    end

    subgraph Data ["GCP Data & State"]
        CloudSQL[(Cloud SQL<br/>PostgreSQL Checkpointer)]
        GCS_Facts[(Cloud Storage<br/>AgentFacts Cache)]
        Filestore[(Filestore NFS<br/>Agent Offload/Plans)]
        PubSub[Pub/Sub Topic<br/>Trace Sinks]
        GCS_Traces[(Cloud Storage<br/>TrustTraceRecords)]
    end

    Frontend -- "HTTPS / SSE" --> BFF_LB
    BFF_LB --> BFF
    BFF -- "HTTPS / SSE" --> Internal_LB
    Internal_LB --> Backend

    Backend -- "read/write state" --> CloudSQL
    Backend -- "read identity" --> GCS_Facts
    Backend -- "read/write files" --> Filestore
    Backend -- "emit traces" --> PubSub
    PubSub -- "Cloud Storage Subscription" --> GCS_Traces

    Meta -- "read traces" --> GCS_Traces
    Meta -- "evaluate/tune" --> Backend
```

---

## 5. Security & Defense in Depth on GCP

The backend's defense-in-depth model aligns with GCP IAM (Identity and Access Management) primitives.

1. **Least Privilege Service Accounts:**
   - The **Backend Cloud Run Service Account** is strictly scoped:
     - `roles/storage.objectViewer` on the Agent Facts bucket.
     - `roles/pubsub.publisher` on the trace delivery topic.
     - `roles/secretmanager.secretAccessor` for `OPENAI_API_KEY` and `AGENT_FACTS_SECRET`.
   - The **Meta Cloud Run Job Service Account** is scoped:
     - `roles/storage.objectViewer` on the Trace bucket to run offline evaluations.
2. **VPC Service Controls & Internal Ingress:**
   - The Backend Ring and Data Tier reside in a Virtual Private Cloud (VPC) network. Cloud Run for the Backend is configured for **Internal Ingress Only**, making it inaccessible from the public internet. The BFF acts as the sole authorized ingress proxy.
3. **Load Balancer Timeout Configuration:**
   - Default backend timeouts (30s) are extended on the Global and Internal HTTP(S) Load Balancers to support long-running LangGraph SSE streams.

---

## 6. Required Code Refactoring for GCP Readiness

To transition from local execution to GCP, the following adapters and ports must be built. These additions adhere strictly to the Four-Layer Architecture rules.

1. **Postgres Checkpointer Adapter:**
   - Ensure `agent_ui_adapter/adapters/runtime/postgres_saver.py` exists and supports connecting via Cloud SQL Auth Proxy or Direct VPC Egress.
   - Modifies the composition root (`server.py`) to inject the `AsyncPostgresSaver` into the `LangGraphRuntime` when `GCP_EXECUTION_ENV` is present.
2. **Pub/Sub / GCS Trace Sink:**
   - Add `services/trace_sinks/pubsub_sink.py` implementing the trace emission interface.
   - Binds to `google-cloud-pubsub` to stream `TrustTraceRecord` dicts to a Pub/Sub topic.
3. **Agent Facts GCS Registry:**
   - Update or extend `services/governance/agent_facts_registry.py` to support `gs://` URIs, fetching signed JSON blobs using `google-cloud-storage`.
4. **Cloud Providers Migration:**
   - Add GCP identity mapping alongside AWS. Create `services/cloud_providers/gcp_identity.py` for GCP Workload Identity to AgentFacts mapping.

**Implementation status:** Recipes 0–8 in [`docs/recipes/gcp/`](../recipes/gcp/) implement **Tier A** (~$12–15/mo). The adapters in §6 are built; Tier A wires `gcs_sink.py` (direct GCS) and a combined Cloud Run backend. For the **Tier B** upgrade path (split BFF + backend, Pub/Sub traces, HA Postgres, edge hardening), see [`docs/recipes/gcp/TIER_B_FUTURE.md`](../recipes/gcp/TIER_B_FUTURE.md).
