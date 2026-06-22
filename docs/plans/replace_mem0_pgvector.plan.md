---
type: plan
title: Replace mem0 with an in-repo pgvector memory backend
description: Retire mem0 (cloud + OSS) in favor of pgvector on the existing Cloud SQL Postgres, behind the unchanged sync MemoryBackend Protocol. Phase 0 verification spike + 7 phases, no graph changes. Reviewed (B1–B10) + 14 follow-up observations validated against live code; design details (replace_mem0_pgvector.design.md) folded inline.
tags: [plan, memory, mem0, pgvector, cloud-sql, embeddings, governance, four-layer]
timestamp: 2026-06-22
status: approved
plan_id: replace-mem0-pgvector
related:
  memories:
    - "[[memory-layer-orphaned-infra]]"
    - "[[mem-tag-run-emitted-no-carriers]]"
    - "[[bff-threads-cloudsql-driver-gap]]"
    - "[[memory-multisession-e2e-corpus]]"
    - "[[memory-autocapture-enable-policy-enforced]]"
    - "[[governance-carrier-gate-phase1]]"
  repo_concepts:
    - docs/plans/replace_mem0_pgvector.design.md
    - docs/plans/typed_memory_searchability.design.md
    - docs/Architectures/FOUR_LAYER_ARCHITECTURE.md
    - docs/Architectures/BACKEND_SOLUTION_ARCHITECTURE.md
    - docs/style-guides/STYLE_GUIDE_LAYERING.md
    - docs/style-guides/STYLE_GUIDE_PATTERNS.md
    - research/tdd_agentic_systems_prompt.md
    - AGENTS.md
    - docs/CONVENTIONS_OKF.md
  skills:
    - docs/skills/llm-eval-grounded-theory/SKILL.md
    - docs/skills/agentsframework-eval-probe/SKILL.md
---

# Replace mem0 with an in-repo pgvector memory backend

> **OKF non-scope guard.** Per [`docs/CONVENTIONS_OKF.md`](../CONVENTIONS_OKF.md) §Explicit non-scope: the runtime long-term-memory subsystem (`services/long_term_memory.py`, its backends, the `memory_subject()` isolation, the content-free governance carriers) is deliberately **NOT** an OKF bundle. This plan describes how to swap one backend for another inside that subsystem; it must NOT introduce markdown ingestion, RAG over docs, or any cross-tenant content into that path. The data-native, opaque-payload, per-user-isolated model is preserved end-to-end.

> **Companion design doc.** The architecture, the layering decision matrix, the data model, and all visual diagrams (system context, four-layer placement, shared-DB pool ownership, ER + row-lifecycle, composition/recall/store sequences, rollout state machine, telemetry pipeline, test pyramid) live in [`replace_mem0_pgvector.design.md`](./replace_mem0_pgvector.design.md). This plan is the **execution source of truth**; the design is its diagram companion. The verified facts the design surfaced are folded inline below so the implementing agent never has to leave this file.

### Non-goals (hard scope guards — at a glance)

The detailed, machine-checkable guards are in §Agent execution contract. The four load-bearing ones, stated tightly (mirrors design §2):

- **No edits to `orchestration/react_loop.py`** for this backend swap (recall/store already route through `LongTermMemoryService`; Phase 6 reads existing carriers — C6).
- **No new symbols under `trust/`** (AP-1).
- **No `services/` import from `middleware/`** — M1 stays enforced (`test_middleware_layer.py:86`). The embedding port lives in `services/embedding/`, not `middleware/ports/` (C1).
- **No markdown / RAG / doc-ingestion behavior** in the runtime long-term-memory paths.

## Agent execution contract

The implementing agent MUST follow these rules. Each is machine-checkable.

### Pre-flight (block before any edit)
- [ ] **Phase 0 verification spike (C1–C6) has cleared its gate.** Phase 0 is mandatory and blocks all code. Its six decisions are recorded in `docs/plans/log.md`.
- [ ] `git status` is clean OR on a dedicated branch named `feat/replace-mem0-pgvector` (or matching `feat/*mem0*`).
- [ ] `pytest tests/architecture/ -q` is GREEN on `main` — establishes the baseline that the new architecture assertions must extend.
- [ ] `python scripts/okf_lint.py` is GREEN on `main`.
- [ ] The four `Critical files` paths in the §Critical files section all resolve (the to-be-deleted files exist; the to-be-edited files exist).
- [ ] The **Python backend's** `DATABASE_URL` (the `postgres_saver` instance — C3, NOT necessarily the Node/BFF threads DSN) is reachable via `cloud-sql-proxy`, has pgvector available, and grants `CREATE` on a table.

### Per-phase exit gate (block before starting the next phase)
Each phase below carries a §Gate subsection. The agent MUST run those commands and paste their outputs (or a one-line GREEN summary) into a PR-description draft before moving on. Phases are sequential; do not parallelize.

### Post-flight (block before requesting review)
- [ ] `pytest tests/ -q` GREEN
- [ ] `pytest tests/architecture/ -q` GREEN — including the **five new assertions** listed under §Architecture-test additions
- [ ] `grep -r "mem0\|mem0ai" --include="*.py" --include="*.toml"` returns **zero** matches anywhere in the tree
- [ ] `python scripts/okf_lint.py` GREEN (no broken links introduced)
- [ ] One live no-traffic Cloud Run revision has run the [[memory-multisession-e2e-corpus]] E2E suite with `MEMORY_RECALLED` and `MEMORY_STORED` carriers present in the trace
- [ ] mem0 keys are still live in env for 24h-rollback window — do NOT delete keys in the same PR that flips traffic
- [ ] Phase 7 eval scaffold ships **infrastructure only**: the `RECALL_RELEVANCE_JUDGE_ENABLED` flag is OFF in the composition root, the `.j2` rubric file may be empty (user fills after Stage 2 gate), and **no code or PR description suggests the judge is calibrated** — Stages 5/6 are explicitly deferred

### Output contract per phase
For each phase the agent produces, **in this order**:
1. The minimal diff (one or two files per commit; failure-paths-first test order per AGENTS.md §Testing Rules).
2. The §Gate command outputs.
3. A one-line entry appended to `docs/plans/log.md` (OKF Bundle log convention) of the form `2026-MM-DD — replace-mem0-pgvector phase N done — <gate summary>`.

### Scope guards (the agent MUST NOT)
- Touch `orchestration/react_loop.py` (recall/store calls already route through `LongTermMemoryService` — no graph changes, per §Architecture & TDD compliance, AP-5).
- Add any new symbol under `trust/` (per AGENTS.md §Trust Kernel Rules + AP-1).
- **Import from `middleware/` inside any `services/` module** (rule M1, `tests/architecture/test_middleware_layer.py:86`). The `EmbeddingClient` port lives in `services/embedding/`, not `middleware/ports/` — this was a real bug in the original plan (review finding C1).
- Add `langgraph` or `langchain` imports to `services/` (per AGENTS.md rule 4); `litellm` is the sanctioned exception for the embedding client, matching `services/llm_config.py`.
- Introduce markdown ingestion, RAG, or cross-tenant content into the LTM subsystem (per OKF §Explicit non-scope, restated above).
- Delete mem0 API keys in the same PR that flips traffic — keep them for the 24h rollback window.
- Skip the failure-paths-first test ordering (per AGENTS.md §Testing Rules + TDD §TAP-4).
- **Do open coding, axial coding, or author rubric content for the Phase 7 eval scaffold.** That is a human-first-pass step per [llm-eval-grounded-theory](../skills/llm-eval-grounded-theory/SKILL.md) cardinal rule R3 / AP-10. The agent builds infrastructure (export scripts, scaffolds, judge harness behind a default-off flag) only. See Phase 7 §Strict role split.

## Context

Mem0 is wired into the pipeline as a per-user durable memory store, accessed at two seams:
- **Sync `Mem0MemoryBackend`** (`services/memory_backends/mem0.py`) — used inside LangGraph for recall (top-3 on system-prompt build) and store (run-end).
- **Async `Mem0CloudClient`** (`middleware/adapters/memory/mem0_cloud_client.py`) — used by the BFF's `/agent/memory` CRUD routes.

The audit shows we exercise a **tiny slice** of mem0:

| What we call | What we use it for | What we DON'T use |
|---|---|---|
| `add(text, user_id, metadata, infer=False)` | Write a row, force-disable mem0's LLM extraction | `infer=True` extraction, custom categories, graph mode |
| `search(query, filters={user_id}, top_k)` | Top-K semantic recall scoped to one user | Cross-user, filters beyond user_id, hybrid search |
| `get_all(filters={user_id})` | List per-user rows for consolidation/budgeting | — |
| `delete(memory_id)` | Hard delete by opaque mem0 id | — |

We are paying for (and depending on the availability of) a hosted vector-DB-with-extras to get a per-user kNN search over embeddings, nothing more. The `LongTermMemoryService` already layers our own dedup / budget / safety-floor / soft-suppress on top — none of those depend on mem0.

Why replace:
- **Cost**: Mem0 Hobby is rate-limited; the v2 self-hosted profile is a paid graduation. A first-party backend has zero per-write cost.
- **Vendor risk**: Mem0 v2's breaking changes (top-level `user_id` → `filters={...}`, `limit` → `top_k`, paginated envelope, metadata flattening that forces JSON-string round-tripping) already cost us once. Pinning is `mem0ai>=2.0,<3`.
- **Reproducibility**: An in-repo backend is testable on L2 with no live SDK fake; the existing `_FakeMem0Sdk` exists precisely because mem0's API drifts.
- **Honesty**: we are not actually getting "agent memory" from mem0 — we are getting a kNN vector store. The agentic memory logic is already in `LongTermMemoryService`.

The `MemoryBackend` Protocol and `MemoryClient` Protocol are the swap points. Composition root selects backend based on `MEM0_API_KEY`. Nothing in the graph or UI knows about mem0 specifically.

Intended outcome: drop the `mem0ai` dependency, ship a first-party `PgVectorMemoryBackend` (durable, default in prod) and keep `InMemoryMemoryBackend` (ephemeral, dev/test default), behind the existing Protocols. No graph code changes. Cloud SQL is already provisioned (we run BFF threads on it — see [[bff-threads-cloudsql-driver-gap]]).

## Backend tradeoff analysis

We compare the three live options the user kept on the table. All three would sit behind the existing `MemoryBackend` Protocol — the graph code doesn't change.

### Option 1 — pgvector on Cloud SQL (already-provisioned Postgres)

- **Infra delta**: zero new services. We already run Cloud SQL Postgres for BFF threads ([[bff-threads-cloudsql-driver-gap]]). `CREATE EXTENSION vector;` + one new table.
- **Cost (us-central1, on-demand)**: the smallest Cloud SQL Postgres instance (`db-custom-1-3840`, 1 vCPU / 3.75 GB) is ~$30 vCPU + ~$19 RAM + ~$2 SSD ≈ **$50/mo** — and we are already paying it for threads. Marginal cost of adding the memory table: **$0**. ([Cloud SQL pricing](https://cloud.google.com/sql/pricing))
- **Performance**: pgvector HNSW handles up to ~2–3M vectors with adequate latency. We're nowhere near that — we store one row per task, per user. ([Vector DB benchmarks 2026](https://callsphere.ai/blog/vector-database-benchmarks-2026-pgvector-qdrant-weaviate-milvus-lancedb))
- **Atomicity**: one SQL transaction = put + dedup + delete + list_all. Today's mem0 path does read-find-delete-add over HTTP, which is racy and pays four round-trips.
- **Operational risk**: tiny. pgvector is BSD-licensed, in every managed Postgres, well-understood. No new auth, no new SDK.
- **Ceiling**: 2026 community consensus says pgvector is the right default "under 2–3M vectors" and that moving off it is a real migration when you cross that. We will not cross it for this app.
- **What we give up**: filtered-search ergonomics (Qdrant is stronger here), hybrid BM25+vector out of the box.

### Option 2 — Qdrant (self-hosted on GCP)

- **Infra delta**: a new always-on service. On Cloud Run, Qdrant must run with `min-instances=1` (it's a stateful vector index — scale-to-zero is wrong); on GKE, a small node pool. Either way, a new persistent disk for the index.
- **Cost**: smallest viable footprint on GCP is ~$30–60/mo for a 2-vCPU/4-GB node with attached SSD; community pricing puts the "Qdrant Cloud Standard above $96/mo, self-host wins" crossover at ~$30/mo on cheap hosts. On GCP that floor is higher. ([Qdrant pricing 2026](https://ranksquire.com/2026/04/19/qdrant-cloud-pricing-2026/))
- **Performance**: by published benchmarks Qdrant outperforms pgvector on throughput (~850 QPS p95 ~8ms at 1M vectors). For our workload — one recall per task — this is a strict overkill.
- **Operational risk**: medium. New service to monitor, back up, upgrade. New SDK. New auth surface. New failure modes during a deploy.
- **Ceiling**: very high. Filtered search, hybrid retrieval, payload indexing, snapshots — capabilities we don't need today.
- **What we give up**: simplicity. We'd be running an extra service for capability we don't exercise.

### Option 4 — Keep mem0, switch to its OSS local library

- **Infra delta**: still need a vector DB underneath mem0 (it doesn't ship one — it wraps Qdrant/Chroma/pgvector). So Option 4 is really Option 4 = (1 or 2) + mem0 as a layer on top.
- **Cost**: same as 1 or 2 underneath, plus we keep paying the engineering cost of the mem0 surface.
- **Performance**: unchanged.
- **Operational risk**: same vendor-API churn that bit us already ([[mem-tag-run-emitted-no-carriers]] — the v1→v2 breaking changes that needed `filters={...}` and `top_k`). The OSS lib has the same API surface as the cloud SDK. The "infer=False" footgun stays.
- **Ceiling**: mem0's marketed differentiator (LLM-driven extraction via `infer=True`) is exactly what we force off. We pay the abstraction tax for a feature we refuse to use.
- **Honesty**: 2026 mem0-alternatives surveys consistently put it last on retrieval quality (LongMemEval ~49% vs 63–91% for Zep/Letta/Hindsight), and the things people stay on mem0 for (graph memory) are paywalled or absent in the OSS path. ([Mem0 alternatives 2026 — Vectorize](https://vectorize.io/articles/mem0-alternatives), [EverMind comparison](https://evermind.ai/blogs/mem0-alternative))
- **What we give up**: nothing functionally — but we keep an abstraction with no business case.

### External signal — agent-memory frameworks (Zep, Letta, LangMem, Hindsight, Cognee)

These are *agent-memory layers* (temporal graphs, dual-store retrieval, self-managed memory), not vector stores. We already have the agent-memory layer — it's `LongTermMemoryService` (dedup, salience-budget, safety-floor, soft-suppress, autocapture-cert). Adopting one of these would mean ripping out our service and re-coding the policy that those frameworks bake in. They are direction-of-travel competitors to `LongTermMemoryService`, not to `MemoryBackend`. Not the right swap.

### Recommendation: **Option 1 — pgvector on Cloud SQL.**

The honest framing is: today we're paying mem0 for a vector store with a metadata blob. We already run a Postgres that can do that with one extension and one table. Option 2 is a defensible choice if we expected to grow into multi-million-vector workloads or needed filtered search, but neither is on the roadmap and we'd be paying $30–60/mo for headroom we won't use. Option 4 keeps an abstraction whose only feature we use is the wrapper itself.

## Embedding tradeoff analysis

Two finalists per the user: OpenAI `text-embedding-3-small` (managed API) vs local `sentence-transformers` (BGE-small / BGE-base / E5) on Cloud Run.

### Workload sizing (the load-bearing number)

Be honest about what we're embedding:
- **Reads (recall)**: one `embed(task_input)` per task. `task_input` ≈ 100–300 tokens.
- **Writes (store)**: one `embed("Task: X\nAnswer: Y")` per task. ≈ 300–800 tokens.
- **Total tokens per task**: ≈ 500–1000 tokens.
- **Volume**: dev + small prod. Even at 10,000 tasks/day (generous), that's ~10M embedding tokens/day ≈ 300M/month.

### Option A — OpenAI `text-embedding-3-small` (managed)

- **Cost**: $0.02 per 1M tokens. At 300M tokens/month = **$6/mo**. At 1B tokens/mo = **$20/mo**. ([text-embedding-3-small spec](https://tokenmix.ai/blog/text-embedding-3-small-developer-guide-2026))
- **Latency**: ~30–80ms per call (us-central1 → OpenAI). One call per recall, one per store. Recall is already memoized per task ([[t3-impl-stage-a-progress]]'s recall_memoized pattern). Acceptable.
- **Quality**: MTEB ~62.3. Solid for English semantic search. Not SOTA, but our retrieval is single-user-scoped — small absolute quality differences disappear inside the top-3 cut.
- **Dimension**: 1536 (or `dimensions=512` parameter to shrink). 1536 fits HNSW fine in pgvector.
- **Operational cost**: zero new infra. Reuse the existing OpenAI client + key wiring.
- **Vendor risk**: minor — OpenAI deprecated `text-embedding-ada-002`, so model lifecycle does matter. The Protocol gives us a clean swap point.

### Option C — Local `sentence-transformers` on Cloud Run

- **Model choice**: BGE-small-en-v1.5 (384-dim, ~130MB) or BGE-base-en-v1.5 (768-dim, ~440MB) or E5-small-v2. BGE-small MTEB ~62, BGE-base ~64. Comparable or marginally better than 3-small.
- **Cost**: this is the surprise. Cloud Run pricing for an always-warm embedding service:
  - You **cannot** scale to zero: cold start of a sentence-transformers model is ~10s (loading weights into RAM), which kills tail latency on recall ([Cloud Run AI cold starts](https://cloud.google.com/blog/topics/developers-practitioners/a-guide-to-ai-cold-starts-on-cloud-run)).
  - `min-instances=1` with 2 vCPU + 4 GB RAM (smallest realistic for a transformer): roughly **$35–50/mo always-on**, before egress and request CPU-seconds. ([Cloud Run pricing 2026](https://cloudpricecheck.com/gcp/cloud-run-pricing))
  - Bumping to GPU-backed Cloud Run is much more (~$0.50–1/hr).
- **Latency**: 20–50ms per call on CPU once warm. Comparable to OpenAI. **Cold start ~10s** if it ever scales down — disqualifying for a user-facing recall.
- **Quality**: BGE-base slightly better than `3-small` on MTEB; BGE-small a wash. Real-world recall delta on our corpus is unknown until measured.
- **Operational cost**: new service to monitor, container image to build, model weights to bake in (or fetch on boot), Cloud Run revision lifecycle to manage.
- **Vendor risk**: none. Pure OSS.

### Cost comparison at our scale (us-central1)

| | OpenAI 3-small | Local BGE-small on Cloud Run |
|---|---|---|
| Marginal infra | $0 | ~$35–50/mo always-on (min-instances=1) |
| Per-token cost (300M tok/mo) | $6 | $0 |
| **Total ~300M tok/mo** | **~$6** | **~$35–50** |
| Total at 3B tok/mo | ~$60 | ~$35–50 + maybe scaling cost |
| Crossover point | **~2.5B tok/mo** | (i.e. ~80,000 tasks/day) |

Below the crossover, OpenAI is cheaper AND simpler. We are nowhere near the crossover.

### Recommendation: **Option A — OpenAI `text-embedding-3-small`**, behind an `EmbeddingClient` port.

The port matters: the *moment* we cross the crossover (or want to go offline / air-gap / cut latency to LAN), we swap in a `LocalBgeEmbeddingClient` adapter with no graph changes. Defer that until we have evidence we need it.

## Architecture & TDD compliance (binding rules)

This change touches `services/`, `middleware/`, and a SQL migration. It MUST conform to the rules in [AGENTS.md](../../AGENTS.md), the four-layer model in [FOUR_LAYER_ARCHITECTURE.md](../Architectures/FOUR_LAYER_ARCHITECTURE.md), and the test pyramid in [tdd_agentic_systems_prompt.md](../../research/tdd_agentic_systems_prompt.md).

### Four-layer placement (where each new file lives)

> **CORRECTED 2026-06-22 (review finding C1).** The original placement put `EmbeddingClient` in `middleware/ports/`. That is an **M1 layering violation**: `tests/architecture/test_middleware_layer.py:86` forbids any `services/` module from importing `middleware/` (`forbidden_consumers` includes `"services"`; the dependency arrow is one-way, middleware → services). `PgVectorMemoryBackend` is a `services/` module and would have to import the port — illegal. The port and adapter move **down into `services/`**, where the sync `MemoryBackend` Protocol already lives (`services/long_term_memory.py`). The embedding adapter reuses **LiteLLM** (`litellm.aembedding`) the same way `services/llm_config.py:32` wraps `ChatLiteLLM` — the one sanctioned framework dependency in `services/` per AGENTS.md rule 4. There is **no `openai` SDK import** and **no `middleware/adapters/embedding/`** directory.

| New module | Layer | Rule that pins it there |
|---|---|---|
| `services/embedding/port.py` (`EmbeddingClient` Protocol) | Horizontal service (L2) | Lives in `services/` so the sync backend can import it without crossing M1. Stdlib + typing only; mirrors `services/tools/search/port.py` precedent. |
| `services/embedding/litellm_embedding_client.py` | Horizontal service (L2) | Uses `litellm.aembedding` — the AGENTS.md rule-4 LiteLLM exception, same path `services/llm_config.py` already uses. NOT a `middleware/adapter`. |
| `services/embedding/fake.py` (`FakeEmbeddingClient`) | Horizontal service (L2) | Deterministic hash vectors for L2 tests. |
| `services/memory_backends/pgvector.py` | Horizontal service (L2) | Same layer as the in-memory backend and the (to-be-deleted) mem0 backend. `psycopg` import is allowed in `services/memory_backends/` (precedent: `services/memory_backends/mem0.py`). Imports `EmbeddingClient` from `services/embedding/port.py` (same layer — legal). |
| `services/long_term_memory.py` | Horizontal service (L2) | Unchanged. The `MemoryBackend` + `MemoryRecord` it owns are the swap point. Both pgvector + embedding types resolve from `services/`, never `middleware/`. |
| SQL migration | Infra (Python-side apply path) | Raw SQL applied via `cloud-sql-proxy` against the **Python backend's** `DATABASE_URL` (the `postgres_saver` instance — see Phase 0 C3), NOT the Node/drizzle threads migration runner. |
| ~~`middleware/ports/embedding_client.py`~~ | ❌ REMOVED | M1 violation — see correction note above. |
| ~~`middleware/adapters/embedding/...`~~ | ❌ REMOVED | No `openai` SDK; LiteLLM lives in `services/`. |
| ~~`middleware/adapters/memory/pgvector_memory_client.py`~~ | ⚠️ CONDITIONAL — see Phase 0 C2 | Only built if Phase 0 proves the async `MemoryClient` seam has a real consumer. Current evidence (B1) says it is dead → this becomes a *deletion*, not an addition. |

### Hard rules to keep green (AGENTS.md §Architecture Invariants)

- **AP-1 — Trust types inside a service.** `MemoryRecord` already lives in the right place (`middleware/ports/memory_client.py` for the wire shape; `services/long_term_memory.py` defines the sync `MemoryBackend` Protocol). Do NOT move either. Do NOT add new "memory" types to `trust/` — they're not signed authorization data.
- **AP-2 — Horizontal-to-horizontal coupling.** `PgVectorMemoryBackend` MUST NOT import another horizontal service. It receives the `EmbeddingClient` by constructor injection from the composition root.
- **AP-3 — Hardcoded prompts.** Phase 1–6 add no prompts. **Phase 7 adds one**: the provisional recall-relevance judge rubric MUST be a `.j2` file under `prompts/codeReviewer/`, rendered via `PromptService.render_prompt()`. **NEVER** as an f-string in `services/governance/recall_relevance_judge.py`. **H1 / H3.**
- **AP-4 — Upward governance calls.** The Phase 6 probe lives under `meta/`. It MUST NOT import from `orchestration/`. It reads `eval_capture` records and `TrustTraceRecord` events emitted by the LTM service.
- **AP-5 — Domain logic in orchestration.** `react_loop.py` is unchanged — recall/store calls already route through `LongTermMemoryService`. The backend swap is invisible to orchestration.
- **Trust kernel rules.** Nothing new goes in `trust/`. The new types (`EmbeddingClient` Protocol) are infrastructure ports — they belong in `services/embedding/`, NOT `trust/` and NOT `middleware/ports/` (see C1 correction).
- **Dependency direction (rule 1 + M1).** `services/memory_backends/pgvector.py` imports `EmbeddingClient` from `services/embedding/port.py` — **same layer, legal**. It MUST NOT import from `middleware/` (M1, `test_middleware_layer.py:86`). The composition root in `middleware/composition.py` (which legally imports *down* into `services/`) constructs both the embedding client and the backend and injects one into the other. No backwards imports.
- **No `langgraph`/`langchain` in `services/` (rule 4).** `PgVectorMemoryBackend` must not pull either.
- **No peer imports between components (rule 5).** N/A — we're not touching components.

### Pattern catalog (STYLE_GUIDE_PATTERNS H/V IDs)

| ID | Application here |
|---|---|
| **H2** — Model tiers from `services/llm_config.py` | `EMBEDDING_MODEL` defaults from settings, never hardcoded inside the adapter. Mirror the LLM-tier discipline for embeddings. |
| **H4** — Per-concern log files | Backend gets its own logger (`services.memory_backends.pgvector`), already configured in `logging.json` alongside the existing memory loggers. |
| **H5** — Record every LLM call | The embedding call is an LLM call → it MUST be captured. **CORRECTED (review finding C5):** `services/eval_capture.py:20` `record()` is **`async`** and takes `(target, ai_input, ai_response, config, …)` — it reads `user_id`/`task_id` from `config["configurable"]`, NOT as kwargs. The plan's earlier `record(target=…, user_id=…, task_id=…)` call does not exist. Resolution is a Phase 0 decision (C5): either (a) thread the run `config` into the embedding call so `eval_capture.record` works unchanged, or (b) emit a lighter synchronous `embedding`-target telemetry event and keep `eval_capture` for the chat path only. Do NOT block a sync backend on an `async` capture call without resolving the await boundary. |
| **V6** — Pydantic for non-trivial outputs | `MemoryRecord` (already Pydantic) is the wire type — no new ad-hoc dicts crossing the Protocol. |

### TDD plan (research/tdd_agentic_systems_prompt.md test pyramid)

Test file → pyramid layer → pattern catalog entry:

| Test file | Layer | Pyramid protocol | Patterns used |
|---|---|---|---|
| `tests/services/embedding/test_litellm_embedding_client.py` | L2 | **Protocol B** (contract-driven, mock I/O) | Pattern 5 (record/replay over `litellm`), Pattern 6 (mock provider), Pattern 4 (consumer-driven contract — embed returns the dim it advertises) |
| `tests/services/memory_backends/test_pgvector_backend.py` | L2 | **Protocol B** (real Postgres-in-Docker; record/replay over a `FakeEmbeddingClient`) | Pattern 4 (consumer-driven contract — same suite that mem0 backend passes), Pattern 5 (record/replay), Pattern 11 (failure-mode matrix: DB down, dimension mismatch, embed timeout) |
| `tests/middleware/adapters/memory/test_pgvector_memory_client.py` | L2 | **Protocol B** | Pattern 6 |
| `tests/architecture/test_middleware_layer.py` (extend existing) | L1 | **Pattern 7** (dependency-rule enforcement) | Assert: no `mem0` import survives anywhere; `psycopg` only under `services/memory_backends/` + the BFF thread store path; `openai` (embeddings) only under `middleware/adapters/`. |
| `tests/meta/probes/test_memory_recall_probe.py` (Phase 6) | L4 | **Protocol D** | Pattern 11 (failure-mode matrix on the recall invariants), Pattern 10 (governance loop sim — degraded-recall → drift alert) |

**Failure-paths-first ordering** (AGENTS.md §Testing Rules):
- For `PgVectorMemoryBackend`, write rejection tests FIRST: dimension-mismatch, missing pgvector extension, user_id leakage between rows, embed-client raising. Acceptance (happy-path CRUD) comes second.
- For the composition-root branch, the rejection test is: "if `MEMORY_BACKEND=pgvector` but no `DATABASE_URL`, raise at composition time — never silently fall back to InMemory in prod."

**Anti-patterns to avoid** (TDD §Anti-Patterns):
- **TAP-1 Tautological tests**: don't re-implement `cosine_distance` in the test to compare with pgvector. Use known fixed vectors with hand-computed scores from a reference table.
- **TAP-2 Mock addiction**: use a real pgvector Docker fixture and `FakeEmbeddingClient`, not 4 mocks. The backend is testable end-to-end with two real, in-memory-equivalent components.
- **TAP-3 Determinism theater**: never assert exact `score` floats — assert ordering (`scores[0] >= scores[1]`) and bounds (`0 <= score <= 1`).
- **TAP-4 Gap blindness**: enforce the failure-paths-first rule with a count: rejection tests ≥ acceptance tests per file.

**L1 zero-flake**: pure architecture / Protocol tests must be deterministic and <10s. **L2**: contract-driven, mocked or in-memory I/O, <30s. **No live LLM in CI** — embeddings are stubbed via `FakeEmbeddingClient` in test runs; the live `LiteLLMEmbeddingClient` is exercised only by a `@pytest.mark.live_llm` smoke test (out of CI).

### Architecture-test additions (must pass)

Add to `tests/architecture/test_middleware_layer.py` (and the existing backend arch suite):
1. `mem0` imports: 0 occurrences anywhere in the tree post-cutover; **remove `mem0ai` from the allowlist at `test_middleware_layer.py:59`** and the four doc-comment references (B5).
2. `EmbeddingClient` Protocol: defined only in `services/embedding/port.py` (NOT `middleware/` — C1).
3. Embedding adapter uses `litellm` only (no `openai` SDK); lives under `services/embedding/`.
4. `psycopg` for the memory backend: allowed only under `services/memory_backends/pgvector.py` (plus the existing `agent_ui_adapter/adapters/runtime/postgres_saver.py` checkpointer). **Note (verified):** `services/memory_backends/` already contains `sqlite.py` (a dev/test durable backend on stdlib `sqlite3` — `sqlite.py:30`). It is **NOT** in scope for deletion and needs **no** allowlist change (stdlib import). Only `pgvector.py` introduces a `psycopg` import in this package; `in_memory.py` (re-export) and `sqlite.py` (stdlib) are untouched.
5. **M1 reinforcement:** `services/embedding/` and `services/memory_backends/pgvector.py` MUST NOT import from `middleware/` (the existing M1 test already covers all of `services/`; assert it stays GREEN after the new files land).
6. `services/memory_backends/pgvector.py` MUST NOT import from `orchestration/`, `components/`, or `agent_ui_adapter/` (build its own pool from an injected DSN — C4/B9).

### Eval-capture invariant (AGENTS.md §Development Conventions)

Every embed call goes through `eval_capture.record()` with:
- `target = "embedding"`
- `user_id` = the task's user_id (the backend already has it on the `MemoryRecord` / search args)
- `task_id` = the current task_id when invoked from the graph; `None` when invoked from the BFF (BFF must pass it through when it has one)
- model, input-token-count, latency, dim — for the drift probe to consume

This is the load-bearing data path for Phase 6's L3 drift detector.

## Implementation phases

### Phase 0 — Verification spike (BLOCKS Phase 1; read-only + one throwaway script)

Added 2026-06-22 after the honest review (B1–B10) + the seven follow-up observations, all validated against live code. Phase 0 is **read-only investigation plus one disposable spike script** — no production code is written. It must clear all six checks (C1–C6) before Phase 1 starts. Each check resolves a finding that could otherwise force a mid-implementation rewrite.

#### C1 — Layering: where does `EmbeddingClient` legally live?

- **Finding (VALIDATED, BLOCKER):** `tests/architecture/test_middleware_layer.py:86` rule **M1** forbids `services/` from importing `middleware/`. No `services/` file imports `middleware/` today; the mem0 backend gets its types from `services.long_term_memory`. Putting the port in `middleware/ports/` (original plan) is illegal.
- **Spike:** write a one-line throwaway import (`from services.embedding.port import EmbeddingClient` inside a scratch `services/` module) and run `pytest tests/architecture/test_middleware_layer.py -q`. Confirm GREEN. Then prove the *illegal* direction fails: temporarily add `from middleware.ports.x import Y` to a `services/` scratch file and confirm M1 **rejects** it.
- **Exit:** port placement is `services/embedding/port.py`; the four-layer table (corrected above) is authoritative. Delete the scratch files.

#### C2 — Consumer trace: is the async `MemoryClient` a live seam or dead code?

- **Finding (VALIDATED, BLOCKER B1):** `grep -rn "memory_client\.\(add\|search\)"` over non-test `.py` = 0 hits. Only refs are the two `composition.py` construction sites. `/agent/memory` routes use the sync `LongTermMemoryService` (`app_prod.py:363`).
- **Spike:** exhaustively trace every reference to `MiddlewareAdapters.memory_client` and to `middleware.ports.memory_client.MemoryClient`. Confirm there is no runtime caller. Check the frontend BFF too (does any Next.js route POST to a backend endpoint that lands on the async client?).
- **Exit — decision recorded in the plan:**
  - If **dead** (expected): Phase 3 is **rewritten to a deletion** — remove `middleware/adapters/memory/mem0_cloud_client.py`, the `middleware/ports/memory_client.py` port, and the `memory_client` field on `MiddlewareAdapters`. Do NOT build `PgVectorMemoryClient`. This *shrinks* the plan.
  - If **live**: document the consumer, and only then build the async pgvector client — reusing the `psycopg_pool.AsyncConnectionPool` precedent at `agent_ui_adapter/adapters/runtime/postgres_saver.py:72` (see C4).

#### C3 — DB reachability + record shape: can the Python backend own `agent_memories`?

- **Finding (VALIDATED, B2/B3/B4):** Two `MemoryRecord` types (`middleware/ports/memory_client.py:24` = `{content,score}` vs `services/long_term_memory.py:49` = `{key,payload,metadata}`). The Python backend reaches PG only via `postgres_saver.py:56` (`DATABASE_URL`), a *different* connection from the Node/drizzle threads store. pgvector availability unconfirmed.
- **Spike (one disposable script, run via `cloud-sql-proxy`):**
  1. `SELECT * FROM pg_available_extensions WHERE name='vector';` against the **Python backend's** `DATABASE_URL`. If absent → enabling pgvector is a Terraform `database_flags` + restart task; escalate into Phase 5 scope.
  2. `CREATE EXTENSION IF NOT EXISTS vector;` in a scratch schema — confirm we have the privilege.
  3. Create a scratch `agent_memories_spike` table with the **corrected** DDL (no standalone `content` column — salient text rides in `payload`; embedding computed from `payload->>'text'`), insert one row built from a real `services.long_term_memory.MemoryRecord`, round-trip it through `put`→`get`→`search`, and assert the returned object **equals** the sync `MemoryRecord` field-for-field (`key`, `payload`, `metadata` preserved; `infer=False` verbatim invariant from B6 holds trivially).
  4. Drop the scratch table.
- **Exit:** confirmed (a) pgvector available or a tracked infra task filed, (b) Python backend has `CREATE` privilege, (c) the corrected DDL produces the exact sync `MemoryRecord` shape. Phase 2 DDL is locked to this result.

#### C4 — Shared-DB consumers matrix + pool/connection budget

- **Finding (VALIDATED — and corrects the reviewer's "asyncpg"):** the checkpointer uses **`psycopg_pool.AsyncConnectionPool`** (`postgres_saver.py:11,67,72`), NOT asyncpg. Driver is consistent (psycopg 3) across Python consumers.
- **Deliverable — a short matrix committed into the plan (C4 table below), then a pool budget decision:**

  | Consumer | Ring | Driver | Pool | DSN source |
  |---|---|---|---|---|
  | LangGraph checkpointer | `agent_ui_adapter/adapters/runtime` | psycopg 3 | `AsyncConnectionPool` (`postgres_saver.py:72`) | `DATABASE_URL` |
  | **`PgVectorMemoryBackend` (new)** | `services/memory_backends` | psycopg 3 (**sync** — the graph calls it via `asyncio.to_thread`) | **DECISION: own small sync pool vs. share** | same `DATABASE_URL`? (confirm in C3) |
  | BFF thread store | `frontend/lib` (Node) | pg / Drizzle | Node pool | BFF `DATABASE_URL` (may differ) |

- **Decision to record:** the sync backend should own a **small dedicated `psycopg_pool.ConnectionPool`** (sync) sized `min_size=1, max_size=4` rather than sharing the checkpointer's *async* pool (mixing sync calls into an async pool is a footgun). Confirm the Cloud SQL instance's `max_connections` headroom covers checkpointer-async + memory-sync + Node concurrently. Cross-layer question (B9): a `services/` backend reusing pool *construction* from `agent_ui_adapter/` would cross a layer — so the memory pool is built **in `services/memory_backends/pgvector.py` itself** from a DSN string injected at the composition root, not imported from `agent_ui_adapter/`.

#### C5 — Embedding telemetry shape + whether `eval_capture.record` changes

- **Finding (VALIDATED):** `services/eval_capture.py:20` `record()` is `async` and takes `(target, ai_input, ai_response, config, …)`, reading `user_id`/`task_id` from `config["configurable"]`. The plan's `record(target="embedding", user_id=…, task_id=…)` does not type-check. Also `services/llm_config.py` is chat-only (no embed path); the embedding adapter must call `litellm.aembedding` directly.
- **Decision to record (pick one, document rationale):**
  - **(a) Reuse `eval_capture.record`** — thread the run `config` dict down to the embedding call so `configurable.{user_id,task_id}` populate. Works only where a `config` exists (the graph recall/store path has one; a bare backend unit-test does not).
  - **(b) Dedicated lightweight telemetry** — a small `embedding`-target event (model, dim, tokens_in, latency_ms, user_id) emitted by the backend, decoupled from `eval_capture`. Simpler for the sync backend; Phase 6's L3 drift probe reads *this* stream.
- **Recommendation:** **(b)** — the sync backend should not depend on threading an async-capture `config` through every call. Define the embedding-telemetry schema here so Phase 6's drift lane has a stable contract. The H5 "record every LLM call" intent is satisfied by (b).
- **`task_id` is OPTIONAL on this event (R5 — validated).** The sync `MemoryBackend.search(user_id, query, limit)` signature (`long_term_memory.py:80`) carries **no task context**; the recall call (`react_loop.py:1094`) cannot pass `task_id` through the Protocol without a signature change we are NOT making. So:
  - **Store path** (`react_loop.py:3317`, key = `task_id`): the embedding event MAY include `task_id` (it's in scope).
  - **Recall path**: `task_id` is **null/absent** on the embedding event — `user_id` + a `phase: "recall"|"store"` discriminator are the join keys. Phase 6's drift lane MUST NOT require `task_id`.
  - Do **not** widen the `MemoryBackend.search` signature to smuggle `task_id` through — that would ripple into `InMemoryMemoryBackend`, the contract suite, and the mem0 backend, for a telemetry nicety. The relaxed contract (task_id optional) is the correct fix.
- **Embedding-telemetry schema (locked):** `{event: "embedding", phase: "recall"|"store", user_id, model, dim, tokens_in, latency_ms, task_id: str|null, ts}`. Content-free (no payload text) — consistent with the `services/long_term_memory.py:10` privacy invariant.

#### C6 — react_loop probe tension (Phase 6) is real but already resolved by existing carriers

- **Finding (VALIDATED — no edit needed):** the recall seam already emits `EventType.MEMORY_RECALLED` (`react_loop.py:1150`) and `MEMORY_STORED` (`:3336`). **Both also fan out to `eval_capture.record` immediately after** (target `"memory_recall"`/`"memory_store"`, with the run `config` passed through — verified at `react_loop.py:1159-1169` and `:3343-3352`), which means Phase 6's L3 drift lane has **two independent streams** keyed by `(user_id, task_id)` — pick whichever is cheaper to consume. The backend-emitted embedding telemetry (C5b) is a third, lower-level stream with `task_id` nullable. AP-5 "no graph changes" **holds**; react_loop is not touched.
- **The only tension:** if a probe lane needs data NOT already on the carrier (e.g. per-recalled-record `score` distribution), that data must come from the **embedding telemetry stream (C5b)** or the backend's own logging — NOT from a new `react_loop` emit. Phase 6 is hereby constrained to consume existing carriers + the C5b stream only. If that proves insufficient, adding a carrier field is a *separate* AP-5-reviewed change, not part of this plan.

**Gate (Phase 0 → Phase 1):** C1 placement proven legal; C2 async-seam decision recorded (delete vs build); C3 DDL locked to the real `MemoryRecord` shape with pgvector confirmed (or infra task filed); C4 matrix + pool decision committed; C5 telemetry schema chosen; C6 probe constrained to existing carriers + C5 stream. All scratch artifacts deleted. A `docs/plans/log.md` line records the six decisions.

### Phase 0.5 — Runtime / infra compatibility (BLOCKS Phase 5 deploy; can land in parallel with Phase 1–2)

Added 2026-06-22 after a second review round (R1–R7, all validated against live code). Phase 0.5 fixes the things that make the *deploy* impossible or the *test suite* red — independent of the backend code itself. It must complete before Phase 5's no-traffic deploy.

#### R1 — `build_adapters` HARD-REQUIRES `MEM0_API_KEY` → deploying with it unset crashes at startup (🔴 BLOCKER)

- **Verified:** `middleware/composition.py` calls `_require(e, "MEM0_API_KEY")` at **both** `build_adapters` profiles (v3 ~line 181, v2 ~line 246); `_require` raises on a missing env. `app_prod.py:74` imports `build_adapters`. So Phase 5 S2 ("deploy with `MEM0_API_KEY` unset") **cannot boot** as originally written — the app dies before the new backend runs.
- **Root cause is the dead async seam (C2/B1):** the only thing demanding the key is the unused `Mem0CloudClient` constructed at `composition.py:222,282`.
- **Fix (ordering matters):**
  1. Make the async memory adapter **optional** in `build_adapters`: if C2 = Branch A (dead seam), **delete the `memory_client` construction + the `_require("MEM0_API_KEY")` calls** entirely. The async client is gone, so the key requirement goes with it.
  2. If C2 = Branch B (live seam), gate it: construct the memory adapter only when its env is present; never `_require` it.
  3. Result: `build_adapters` no longer references `MEM0_API_KEY`. A revision can boot with it unset — which is the precondition for Phase 5.
- **Test:** add a composition rejection/acceptance pair — `build_adapters` succeeds with `MEM0_API_KEY` **absent**; the graph-side `MEMORY_BACKEND=pgvector` path is what wires durable memory now.

#### R3 + R4 — Test + infra blast radius is wider than the plan named (🟠 MAJOR)

- **Verified test files assuming mem0 env/wiring (9, not 1):** `tests/middleware/test_composition.py`, `test_app_prod.py`, `test_composition_relay.py`, `test_agent_runtime_composition.py`, `test_app_prod_memory_wiring.py`, `test_server.py`; `tests/infra/test_secret_manager.py`, `tests/infra/gcp/test_secret_manager.py`, `tests/infra/test.tfvars`.
- **Verified infra (5 references):** `infra/gcp/variables.tf:101` (`variable "mem0_api_key"`), `infra/gcp/cloud-run-backend.tf:157-158` (`MEM0_BASE_URL`), `:214-217` (`MEM0_API_KEY` secret env), `:307` (`mem0_api_key_accessor` IAM), plus the `google_secret_manager_secret.mem0_api_key` resource itself.
- **Fix — add to the Phase 4/5 checklists, ordered to avoid broken deploys:**
  - **Phase 4 (code, no deploy):** update the 6 middleware tests to stop requiring mem0 env / asserting the async wiring; assert the new `MEMORY_BACKEND` branch instead. These can go green before any infra change because the code stops reading mem0 env.
  - **Phase 5 S6 (with the deploy):** remove the 5 infra references + the secret resource + IAM accessor in `cloud-run-backend.tf`/`variables.tf`, and update `tests/infra/*` (`test_secret_manager.py`, `test.tfvars`) in the **same** PR. Ordering: the keyless code revision (Phase 5 S2–S5) ships *while infra still defines the secret* (harmless — unused); the infra/secret removal is the last step (S6), after traffic is stable, so a rollback revision can still read the secret during the soak.

#### R2 — `gen_random_uuid()` extension (🟡 — already satisfied on this instance, add defensive guard)

- **Verified:** the instance is **`POSTGRES_15`** (`infra/gcp/data.tf:41`). In Postgres ≥ 13, `gen_random_uuid()` is **built into core** — no `pgcrypto` needed. The existing threads migration (`0000_init_threads.sql:32`) uses it with **no** `CREATE EXTENSION pgcrypto` and works in prod, confirming this.
- **Fix (zero-cost, future-proof):** the `agent_memories` migration adds a defensive `CREATE EXTENSION IF NOT EXISTS pgcrypto;` alongside `CREATE EXTENSION IF NOT EXISTS vector;`. On PG15 the pgcrypto line is a harmless no-op; it guards against a future engine downgrade. (Do NOT rely on it being *required* — it isn't, on PG15.)

#### R6 — Thread-safety / connection model for the sync backend (🟡 MAJOR)

- **Verified concern:** the sync backend is hit from two directions — the graph (`react_loop.py:1094,3317` via `asyncio.to_thread`) and the `/agent/memory` web routes. A single shared psycopg *connection* would be unsafe under concurrency.
- **Fix (locks the C4 decision into a tested invariant — verified Phase 0.5 by inspecting `agent_ui_adapter/adapters/runtime/postgres_saver.py:67-83`):** `PgVectorMemoryBackend` owns a **`psycopg_pool.ConnectionPool`** (sync) constructed with these exact kwargs:

  ```python
  ConnectionPool(
      dsn,
      min_size=1, max_size=4,
      open=False,                                # explicit open at __aenter__
      check=ConnectionPool.check_connection,     # MANDATORY on Cloud SQL Auth Proxy:
                                                 # idle TCP gets reset, otherwise every
                                                 # subsequent op dies with OperationalError
      kwargs={"row_factory": dict_row},          # autocommit defaults to False — we want
                                                 # transactional upserts (UNLIKE the
                                                 # checkpointer's autocommit=True saver).
  )
  ```

  The `check=ConnectionPool.check_connection` line is the load-bearing detail: `postgres_saver.py:12-18` documents why the checkpointer set it (Cloud SQL Auth Proxy resets idle connections; without the health check, every subsequent run fails). The sync pool must mirror this; default Cloud Run revisions have idle gaps long enough to trip it. The `autocommit` difference vs the checkpointer is intentional: the checkpointer uses autocommit because LangGraph's setup migrations need it; our backend needs transactional integrity for dedup-and-upsert.

  Acquire a connection per call with a context manager, never hold one across calls. **Add a concurrency test** (Pattern 11): N concurrent `to_thread` searches + writes for distinct user_ids, assert no connection reuse error and no cross-user bleed. This is a required L2 test, not optional.

**Gate (Phase 0.5 → Phase 5 deploy):**
- `build_adapters` boots with `MEM0_API_KEY` unset (R1 rejection/acceptance test GREEN).
- The 6 middleware tests pass without mem0 env (R3).
- The migration enables both `vector` and (defensively) `pgcrypto`; applies clean on the PG15 instance (R2).
- Concurrency test for the sync pool GREEN (R6).
- Infra-removal diff drafted and ordered for Phase 5 S6 (R4) — not applied until then.

### Phase 1 — Embedding port (small, isolated) — **in `services/`, not `middleware/`**

Add `services/embedding/port.py` (placement locked by Phase 0 C1):

```python
class EmbeddingClient(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

Add `services/embedding/litellm_embedding_client.py` calling `litellm.aembedding(model=…, input=texts)` — the same LiteLLM dependency `services/llm_config.py:32` already uses (AGENTS.md rule-4 exception). Default model `text-embedding-3-small`, dim 1536. Emit the C5b embedding-telemetry event per call. Add `services/embedding/fake.py` (`FakeEmbeddingClient`, deterministic hash vectors) for L2 tests.

Wire into the composition root: `middleware/composition.py` (which legally imports *down* into `services/`) constructs the embedding client and injects it into `PgVectorMemoryBackend`.

**Gate (Phase 1 → Phase 2):**
- `pytest tests/services/embedding/ -q` GREEN, ≥1 rejection test per file
- `pytest tests/architecture/test_middleware_layer.py -q` GREEN — confirms no `services/` → `middleware/` import was introduced (M1 holds)
- `grep -rn "from middleware\|import middleware" services/embedding/ services/memory_backends/` returns 0 lines
- `EmbeddingClient.dimension` matches what `embed()` returns (Pattern 4 contract test recorded)
- No `openai` SDK import anywhere; `litellm` only (consistent with `services/llm_config.py`)

### Phase 2 — `PgVectorMemoryBackend` (sync, used by the graph)

New file `services/memory_backends/pgvector.py` implementing `MemoryBackend`:

DDL locked by Phase 0 C3. Note: **no standalone `content` column** — the sync `MemoryRecord` is `{key, payload, metadata}` (B2); the salient text rides in `payload->>'text'` and is what we embed. `embed_text` below is a denormalized copy of that text kept ONLY so we can re-embed on a model swap without re-deriving it (and for debug); it is not a separate source of truth.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
-- Defensive only: on POSTGRES_15 (data.tf:41) gen_random_uuid() is core — this is a no-op.
-- Guards against a future engine downgrade. (R2)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE agent_memories (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       TEXT NOT NULL,
  key           TEXT NOT NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,   -- opaque; {task_input, answer, text}
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {score, salience, suppressed, stored_at}
  embed_text    TEXT NOT NULL,                        -- = payload->>'text'; what the embedding is over
  embedding     VECTOR(1536),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, key)
);

CREATE INDEX agent_memories_user_idx ON agent_memories (user_id);
CREATE INDEX agent_memories_embedding_idx
  ON agent_memories USING hnsw (embedding vector_cosine_ops);
```

Method mapping (sync `MemoryBackend` Protocol → SQL):

| Protocol method | SQL |
|---|---|
| `put(record)` | embed `record.payload['text']` → `INSERT … ON CONFLICT (user_id, key) DO UPDATE SET payload=…, metadata=…, embed_text=…, embedding=…` (upsert) |
| `get(user_id, key)` | `SELECT … WHERE user_id=$1 AND key=$2` → rebuild `MemoryRecord{key,payload,metadata}` |
| `search(user_id, query, limit)` | embed `query`, `SELECT *, 1 - (embedding <=> $1) AS score FROM … WHERE user_id=$2 ORDER BY embedding <=> $1 LIMIT $3`; write the cosine score into the returned record's `metadata['score']` (matches the existing recall path's read of `metadata['score']`) |
| `delete(user_id, key)` | `DELETE WHERE user_id=$1 AND key=$2 RETURNING id` |
| `list_all(user_id)` *(optional capability — see note)* | `SELECT … WHERE user_id=$1` |

> **`list_all` is NOT a Protocol method (verified `services/long_term_memory.py:76-88`).** The `MemoryBackend` Protocol declares exactly `put → None`, `get → MemoryRecord | None`, `search(..., limit=10) → list`, `delete → bool`. `list_all(user_id)` is **commented out** at `:84-88` — it is an *optional* capability that `LongTermMemoryService._list_all` (`:362-379`) detects via `getattr(self._backend, "list_all", None)` and, when absent, **emulates** with an over-fetched empty-query `search`. `PgVectorMemoryBackend` SHOULD still implement `list_all` (both `InMemoryMemoryBackend` at `:532` and `Mem0MemoryBackend` do) so consolidation/budgeting stays cheap and reliable — but conformance does **not** require it, and a contract test MUST NOT assert it as a Protocol obligation.

> **`MemoryRecord` round-trip is four fields, not column-for-column (verified `:49-53`).** The sync `MemoryRecord` carries only `{user_id, key, payload, metadata}`. The `id`, `embedding`, `created_at`, and `embed_text` columns are **DB-side only** — generated by Postgres / the backend, never present on the Pydantic record. `get`/`search` reconstruct a `MemoryRecord` from the row and **drop** those columns (`search` additionally writes the cosine score into `metadata['score']`). So the relationship is a faithful round-trip of the four record fields, not a column identity — the contract test asserts the four fields survive, not the DB-side columns.

Use `psycopg[binary]` + `psycopg-pool` (both already in `pyproject.toml:46-47` — **note: NOT the `psycopg[binary,pool]` extras string the earlier draft used**; pooling is the separate `psycopg-pool` package). The backend owns a sync `psycopg_pool.ConnectionPool` (`min_size=1, max_size=4`), one connection per call via context manager (R6). Translate driver errors to `MemoryBackendError` at the boundary, mirroring the mem0 backend's contract.

Two important details from the mem0 audit to preserve:
- **`payload` is opaque JSON** (the graph stores `{task_input, answer, text}`); keep it as `JSONB` and return verbatim — do NOT flatten.
- **`metadata` includes `score`, `salience`, `suppressed`, `stored_at`**; LTM service expects these round-trip cleanly. JSONB gets this for free; the JSON-string hack mem0 forced is gone.

**Gate (Phase 2 → Phase 3):**
**Shared contract suite — resolve the test-strategy contradiction (R5b).** The plan both says "the same contract suite mem0 passes must pass pgvector" AND "delete `test_mem0_backend.py`". These conflict if done naively — deleting the file destroys the executable baseline. **Fix:** *before* writing pgvector, **extract the backend-agnostic contract** out of `tests/services/memory_backends/test_mem0_backend.py` into a shared, **parametrized** `tests/services/memory_backends/contract.py` (fixtures: `InMemoryMemoryBackend`, `Mem0MemoryBackend` *(while it still exists)*, `PgVectorMemoryBackend`). The mem0-**specific** behaviors (`_FakeMem0Sdk` envelope quirks, `infer=False`, metadata-flattening) stay in `test_mem0_backend.py`. Then: Phase 2 = pgvector passes the shared contract; Phase 5 = delete only the mem0-specific file + drop mem0 from the contract's parametrize list. The shared contract survives the cutover.

- `pytest tests/services/memory_backends/test_pgvector_backend.py -q` GREEN against pgvector Docker fixture; failure-mode matrix covers: DB down, dimension mismatch, embed timeout, cross-user leak. Rejection tests ≥ acceptance tests.
- The **shared parametrized contract** (`contract.py`) passes against `PgVectorMemoryBackend` (Pattern 4 consumer-driven contract). If a contract test fails, the backend is wrong — do not patch the test.
- **Concurrency test (R6):** N concurrent `to_thread` searches + writes across distinct user_ids against one pool → no connection-reuse error, no cross-user bleed.
- `pytest tests/architecture/ -q` GREEN — `psycopg` import is allowed only under `services/memory_backends/pgvector.py` + the checkpointer; `PgVectorMemoryBackend` does not import `middleware/`, `orchestration/`, `components/`, `agent_ui_adapter/`, or other `services/*` modules besides the embedding port.
- Manual smoke: write 3 rows for two distinct user_ids, search each, assert zero cross-user bleed (Pattern 11 row).

### Phase 3 — Resolve the async `MemoryClient` seam (delete OR build — set by Phase 0 C2)

**This phase's shape is decided by Phase 0 C2, not assumed.** The honest review (B1) found `memory_client.{add,search}` has **zero non-test consumers** — the async `Mem0CloudClient` is constructed in `composition.py:222,282` and never invoked; `/agent/memory` routes use the sync `LongTermMemoryService`.

- **Branch A — async seam is DEAD (expected, per current evidence):** Phase 3 is a **deletion**, not an addition.
  - Delete `middleware/adapters/memory/mem0_cloud_client.py`.
  - Delete the `middleware/ports/memory_client.py` async `MemoryClient` Protocol + its `MemoryRecord` (the `{content,score}` type — distinct from the surviving sync `services/long_term_memory.MemoryRecord`).
  - Remove the `memory_client` field from `MiddlewareAdapters` and both construction sites in `composition.py`.
  - Update `tests/architecture/test_middleware_layer.py` allowlist + any test referencing the async port.
  - **Net: the plan gets smaller. No `PgVectorMemoryClient` is built.**
- **Branch B — async seam has a real consumer (only if C2 finds one):** build `middleware/adapters/memory/pgvector_memory_client.py` implementing the async port, as a thin wrapper that reuses the sync backend via `asyncio.to_thread()` (mirrors the old `Mem0CloudClient` async-offload pattern). Do NOT build a second native-async pool unless latency traces demand it.

**Gate (Phase 3 → Phase 4):**
- Branch A: `grep -rn "memory_client\|Mem0CloudClient" middleware/ --include="*.py"` returns 0 (field + class gone); `pytest tests/ -q` GREEN with the async-port tests removed; architecture suite GREEN.
- Branch B: `pytest tests/middleware/adapters/memory/test_pgvector_memory_client.py -q` GREEN; the documented real consumer exercised end-to-end; no `mem0` import survives.
- Either branch: `grep -rn "mem0" middleware/` → 0.

### Phase 4 — Composition + config

In `middleware/composition.py`:
- Replace the `if settings.mem0_api_key:` graph-backend branch (verified at **`composition.py:829`** → `Mem0MemoryBackend` else `InMemoryMemoryBackend` at `:838`) with `if settings.database_url and settings.memory_backend == "pgvector"` → construct `PgVectorMemoryBackend` (+ inject the `services/embedding` client). **Today there is no `MEMORY_BACKEND` setting** — selection is purely by *presence* of `settings.mem0_api_key`; Phase 4 introduces the setting and **replaces** (does not sit beside) the mem0 branch.
- **Transitional three-way state (Phase 4 → Phase 5 S6).** Between the config flip and the mem0 deletion, the selector is effectively three-way — `inmemory` (dev/test) · `mem0` (transitional rollback target, still on disk until S6) · `pgvector` (new default). It collapses back to two (`inmemory`/`pgvector`) once mem0 is deleted at S6. The composition root stays the **only** place a concrete backend is named, and `LongTermMemoryService` is always constructed regardless of the flag, so the graph shape never changes.
- Remove the `_require("MEM0_API_KEY")` calls in `build_adapters` (Phase 0.5 R1). If C2 = Branch A, the async `memory_client` field is deleted entirely; if Branch B, it's constructed only when its env is present (never `_require`d).
- The BFF `/agent/memory` routes already use the sync `LongTermMemoryService` (`app_prod.py:363`), so there is no separate BFF memory DSN to wire — only the graph-side `PgVectorMemoryBackend` needs the Python-backend DSN.
- Keep `InMemoryMemoryBackend` as the dev/test default when no DB is configured.

Settings (`AgentRuntimeSettings`):
- Add `memory_backend: Literal["inmemory", "pgvector"] = "inmemory"` (env `MEMORY_BACKEND`).
- Use the **Python backend's** `DATABASE_URL` (the `postgres_saver` instance, confirmed in Phase 0 C3) — NOT assumed identical to the Node/BFF threads DSN. If C3 found they differ, name the memory DSN explicitly.
- Add `EMBEDDING_MODEL` (default `text-embedding-3-small`), `EMBEDDING_DIMENSION` (default 1536) for swap-ability.
- `MEM0_API_KEY` / `MEM0_BASE_URL`: **leave in settings/Terraform until Phase 5's rollback window closes** (see locked sequence below). Code stops *reading* them at Phase 4; the env vars are removed only in the final step.

**Gate (Phase 4 → Phase 5):**
- `pytest tests/middleware/test_agent_runtime_composition.py tests/middleware/test_app_prod_memory_wiring.py -q` GREEN with the new branch — includes the **rejection test**: `MEMORY_BACKEND=pgvector` with no `DATABASE_URL` MUST raise at composition time, NOT silently fall back to `InMemoryMemoryBackend` (composition-root scope guard).
- App boots locally with `MEMORY_BACKEND=pgvector` + the proxy DSN. `MEMORY_BACKEND=inmemory` still works for tests.
- Architecture test reflects the new composition rule (no horizontal-to-horizontal coupling — see §Architecture & TDD compliance).
- mem0 code still on disk; the swap is config-driven only. Do NOT delete mem0 files yet.

### Phase 4.5 — Typed-memory forward-compatible schema (BLOCKS Phase 5 S1; schema-now / behavior-later)

Added 2026-06-22. Implements the **P0 (schema-only) slice** of
[`typed_memory_searchability.design.md`](./typed_memory_searchability.design.md)
and nothing else. This phase exists *before* Phase 5 for one reason from that
design's governing principle: **the live Cloud SQL DDL (Phase 5 S1) is the
expensive, effectively-irreversible thing; runtime behavior is a cheap code
deploy.** Folding the type-aware columns into the same migration now avoids a
*second* live `ALTER TABLE` later. The window is open precisely because Phase 5
S1 has **not** applied the `agent_memories` DDL yet (it is gated on the
user-driven `cloud-sql-proxy` apply).

**Scope — P0 ONLY (design §5, §5.1, §8).** This phase makes the *schema*
type-aware and adds two **observably-inert** write-side lines. It does **NOT**
change recall composition, the `MemoryBackend` Protocol, or any
`orchestration/`/`components/` code. The four-field `MemoryRecord` round-trip is
byte-identical, so the **shared parametrized contract suite from Phase 2 passes
unchanged** — that is the acceptance bar.

> **The deferred half is explicitly NOT in this phase.** The behavioral levers
> R1 (SQL type push-down / Protocol change — Ask-first), R2/R3 (typed-recall
> orchestrator + `embed_text` writer), R4 (hybrid RRF), R5 (semantic
> consolidation), R6 (recency/bi-temporal) all stay as follow-on plans per the
> design's §6 roadmap. Phase 4.5 only lays the schema they will later use.

#### What changes (two already-shipped Phase 2 artifacts, both in `services/memory_backends/pgvector.py`)

**(1) The `DDL` constant** becomes a superset of the Phase 2 DDL — net-new are
`mem_type` and the generated `ts` column, plus their indexes (design §5):

```sql
CREATE EXTENSION IF NOT EXISTS vector;     -- require pgvector >= 0.8.2 (CVE-2026-3172)
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- defensive no-op on POSTGRES_15 (R2)

CREATE TABLE IF NOT EXISTS agent_memories (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     TEXT NOT NULL,
  key         TEXT NOT NULL,
  mem_type    TEXT NOT NULL DEFAULT 'semantic',   -- NEW: write-derived shadow of metadata->>'type'
  payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
  embed_text  TEXT NOT NULL,
  embedding   VECTOR({dim}),                       -- stays NULLABLE (schema-now for the deferred R2 bypass)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  ts          tsvector GENERATED ALWAYS AS         -- NEW: hybrid-lexical side (future R4), auto-maintained
              (to_tsvector('english', COALESCE(payload->>'text', ''))) STORED,  -- NULL-safe (design H7)
  UNIQUE (user_id, key)
);

CREATE INDEX IF NOT EXISTS agent_memories_user_idx        ON agent_memories (user_id);
CREATE INDEX IF NOT EXISTS agent_memories_user_type_idx   ON agent_memories (user_id, mem_type);  -- NEW (Decision B)
CREATE INDEX IF NOT EXISTS agent_memories_hnsw_idx        ON agent_memories USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS agent_memories_ts_idx          ON agent_memories USING gin (ts);       -- NEW (future R4)
-- Phase 5 S1 migration MUST end with: ANALYZE agent_memories;  (design H9 — planner stats for the new low-cardinality column)
-- Phase 5 S1 HNSW build guard retained: SET max_parallel_maintenance_workers = 0 for pgvector < patched (CVE-2026-3172).
```

**(2) Two inert write-side lines in the backend** (design §5 "scope of no behavior change"):

- `put` derives `mem_type` from `record.metadata.get('type', 'semantic')` and
  writes it into the new column (extend the `INSERT … ON CONFLICT … DO UPDATE`
  at `pgvector.py:255` to set `mem_type`). The column is **write-derived and
  unread at runtime** — recall still filters on `metadata['type']` via
  `LongTermMemoryService` (the existing Python post-filter is untouched), so
  this changes nothing observable. It only pre-populates the indexed predicate
  R1 will later push down.
- `_embed_text_of` (`pgvector.py:229`) gains a **non-empty `embed_text`**
  preference ahead of the existing non-empty `text` branch, keeping the
  `repr(payload)` last-resort fallback. Mirror the current type guard
  (`isinstance(x, str) and x`) rather than a bare
  `payload.get('embed_text') or payload.get('text')` chain: an empty-string or
  non-`str` `embed_text` MUST fall through to `text` (and then `repr`), exactly
  as the existing `text` branch already treats an empty `text`. Concretely:

  ```python
  @staticmethod
  def _embed_text_of(record: MemoryRecord) -> str:
      payload = record.payload or {}
      explicit = payload.get("embed_text")
      if isinstance(explicit, str) and explicit:
          return explicit
      text = payload.get("text")
      if isinstance(text, str) and text:
          return text
      return repr(payload)
  ```

  **Verified inert:** no writer emits `embed_text` until R3, so the key is absent
  today and the function always resolves to `text` — embedding input is
  unchanged. The empty-string fall-through is the safe rule for the *future* R3
  writer: embedding `""` would otherwise produce a degenerate, signal-free
  vector with no error, so a present-but-empty key is treated as "no override,"
  not as authoritative.

#### Scope guards (the agent MUST NOT — design §5.1 / G1)

- **MUST NOT ship the procedural embedding bypass at P0.** `search`
  (`pgvector.py:311`) still kNN-ranks across **all** types (the type filter is a
  Python post-step in `LongTermMemoryService`). A NULL-embedding procedural row
  would sort last and silently drop out of recall — a behavior change that also
  fails the shared contract tests. The `embedding` column is *nullable*
  (schema-now) but `put` MUST still embed **every** type, including procedural.
  The bypass is bound to R2 (a follow-on), not this phase.
- **MUST NOT read `mem_type` at runtime.** It is a denormalized shadow; the
  single source of truth stays `metadata['type']` (round-trips in the `metadata`
  JSONB). No trigger/check-constraint is added (dead weight while unread — R1
  owns any constraint if it begins to rely on the column).
- **MUST NOT widen the `MemoryBackend` Protocol** (R1 is the Ask-first
  follow-on). `get`/`search` keep reconstructing the four-field `MemoryRecord`;
  `mem_type`, `ts`, `id`, `embed_text`, `created_at` stay DB-side-only and are
  dropped on reconstruction.
- **MUST NOT touch `orchestration/`, `components/`, or `LongTermMemoryService`**
  (the base swap's non-goals hold — design §7).

#### TDD (failure-paths-first, per AGENTS.md §Testing Rules)

- The Phase 2 **shared parametrized contract suite must pass unchanged** against
  `PgVectorMemoryBackend` — this is the load-bearing regression guard that the
  schema additions are transparent to the `MemoryRecord` round-trip.
- Add a small set of **schema-fold** tests against the pgvector Docker fixture
  (`pgvector/pgvector:pg15`), rejection-first:
  - `mem_type` defaults to `'semantic'` when `metadata['type']` is absent.
  - `mem_type` is derived verbatim from `metadata['type']` (`episodic`,
    `procedural`) on `put`, and on upsert it updates with the record.
  - `get`/`search` returned records **do not** expose `mem_type`/`ts` (four-field
    round-trip preserved — assert the reconstructed record equals the input four
    fields).
  - A `procedural`-typed record is **still embedded and still kNN-retrievable**
    (guards against an accidental bypass — the G1 correctness gate).
  - `_embed_text_of` prefers a **non-empty** `embed_text`, else non-empty
    `text`, else repr (a 4-row table test): (1) non-empty `embed_text` wins;
    (2) `embed_text=""` falls through to `text` (empty is **not** authoritative);
    (3) no `embed_text` → `text`; (4) neither → `repr(payload)`. Plus: a record
    with **no** `embed_text` embeds the same bytes as before this phase
    (inert-day-one proof).
  - `ts` is populated for a record with `payload.text` and is empty-not-NULL for
    a record whose payload lacks `text` (NULL-safety, design H7).

#### Gate (Phase 4.5 → Phase 5)

- `pytest tests/services/memory_backends/test_pgvector_backend.py -q` GREEN —
  the **Phase 2 shared contract suite passes unchanged** plus the new schema-fold
  tests (rejection ≥ acceptance per TAP-4).
- `pytest tests/architecture/ -q` GREEN — no new forbidden imports; the DDL/
  backend edits add no upward import and no `middleware/` import.
- `pytest tests/ -q` GREEN — no regression anywhere from the inert write-side
  changes.
- Manual schema check against the Docker fixture: `\d agent_memories` shows
  `mem_type`, `ts`, `agent_memories_user_type_idx`, `agent_memories_ts_idx`; a
  `procedural` row inserted via `put` has a non-NULL `embedding`.
- `python scripts/okf_lint.py` GREEN.
- Design §8 P0 readiness checklist reconciled: every box maps to a test or DDL
  line above, and the "procedural bypass deferred to R2" box is explicitly
  satisfied (bypass NOT shipped).

### Phase 5 — Cutover (no data migration) — **locked rollback sequence**

Per the user's decision: pgvector starts empty. Memories re-accumulate from cutover.

The ordering below is **strict and reversible at every step until S6**. The principle: **config flips before code deletion; env vars survive until the rollback window closes.** A revision that can still reach mem0 (keys present, code present) is the rollback target; we do not burn that bridge until pgvector has proven itself in prod.

> **Precondition (Phase 0.5 R1):** `build_adapters` must already be **keyless** (no `_require("MEM0_API_KEY")`) before S6 removes the env. If S6's env-removal lands while `build_adapters` still hard-requires the key, the keyless revision crashes at startup. Phase 0.5 makes `build_adapters` boot without `MEM0_API_KEY`; S2 can keep the key set (harmless) but the code no longer *demands* it.

| Step | Action | Reversible? | Rollback if it fails |
|---|---|---|---|
| **S0** | (Phase 0.5) `build_adapters` is keyless; 6 middleware tests green without mem0 env. **Without this, S6 is unsafe.** | Yes | revert Phase 0.5 commit |
| **S1** | Apply the SQL migration (`vector` + `pgcrypto` + the **Phase 4.5 superset `agent_memories` DDL** — incl. `mem_type`, generated `ts`, the `(user_id, mem_type)` B-tree, and the GIN index) to the **Python backend's** Cloud SQL via `cloud-sql-proxy` (C3-confirmed DSN). One migration, not two (it imports the Phase 4.5 `DDL` constant). End with `ANALYZE agent_memories` (design H9); guard the HNSW build with `SET max_parallel_maintenance_workers = 0` for pgvector < patched (CVE-2026-3172). | Yes (drop table) | drop table; no app impact |
| **S2** | Deploy a **no-traffic** Cloud Run revision: `MEMORY_BACKEND=pgvector`, **`MEM0_API_KEY` still set** (unused but present), mem0 code **still on disk**. | Yes | delete the no-traffic revision |
| **S3** | Smoke-test the no-traffic tag: authed runs assert `MEMORY_RECALLED` count=0 on run 1, >0 by run 3; carrier-gate audit GREEN; stress E2E GREEN. | Yes | fix forward on the tag; prod untouched |
| **S4** | **Shift traffic** to the pgvector revision. mem0 keys + code still present on the rollback revision. | **Yes — instant** | shift traffic back to the prior revision (still mem0-wired) |
| **S5** | **24h soak.** Watch recall carriers, error rate, drift. mem0 keys remain set the whole window. | Yes | traffic-shift back within seconds |
| **S6** | After 24h clean: **(a)** delete mem0 code (`services/memory_backends/mem0.py`, `middleware/adapters/memory/mem0_cloud_client.py`, `_FakeMem0Sdk`, the `mem0ai` line in `pyproject.toml`, the `mem0ai` allowlist entry in `test_middleware_layer.py`); **(b)** in the SAME PR, remove `MEM0_API_KEY`/`MEM0_BASE_URL` from settings + Terraform; **(c)** revoke the actual mem0 API key in the mem0 dashboard **last**, after the deploy is green. | **No** (point of no return) | none — only proceed when S5 is unambiguously clean |

**Hard rule (from the §Agent execution contract):** S6 is the only irreversible step, and its three sub-steps are ordered code-delete → env-remove → **key-revoke-last**. Never revoke the live key before the keyless revision is serving green — a revoked key + a rolled-back-to-mem0 revision = outage.

**Gate (Phase 5 → Phase 6):**
- SQL migration applied to Cloud SQL via `cloud-sql-proxy` (same pattern as [[bff-threads-cloudsql-driver-gap]])
- No-traffic Cloud Run revision is healthy: `/health` 200, the carrier-gate audit ([[governance-carrier-gate-phase1]]) is GREEN, `EventType.MEMORY_RECALLED` count = 0 on run 1, > 0 by run 3
- Stress E2E ([[memory-multisession-e2e-corpus]]) GREEN against the no-traffic revision; analyzer trace-join works
- Traffic shifted; mem0 keys remain in env for 24h
- `grep -r "mem0\|mem0ai" --include="*.py" --include="*.toml"` returns 0 matches after the deletion commit
- `pytest tests/architecture/ -q` GREEN with the "no mem0 imports anywhere" assertion live

### Phase 6 — Probe (continuous eval)

> **Method-name pin (verified `react_loop.py:1093-1096`, `long_term_memory.py:219`/`:236`).** The top-K recall path the probe observes is `memory_service.search(user_id, task_input, limit)` wrapped in `asyncio.to_thread` inside `route_node` — the universal seam every tier passes through. The service's `recall(user_id, key)` (`:219`) is a **different** method — a single-record get *by key* — and is NOT the top-K path. Relevance flooring/rendering (`filter_recall_records`, `render_recall_block`) happen in the orchestration helper, not the backend. The probe MUST read the `search` seam, not `recall`.

Use the `agentsframework-eval-probe` skill to wire a Tier-A probe on the recall seam in `react_loop.py:1080-1169`:
- **L1 deterministic**: invariant checks — every recall returns ≤ limit, every record has the requested `user_id`, `score` in [0,1], `created_at` non-null. 100% sample.
- **L2 sampled judge** (later, on demand): is the recalled content actually relevant to `task_input`? 5–10% sample.
- **L3 drift**: distribution of `score`, recall count, and recall latency over time.
- Offline CI regression: a small fixed corpus of (task_input → expected-recall-keys) on the in-memory backend.

This closes the loop: if a pgvector index degrades or the embedding model drifts, the probe flags it before it shows up as a quality regression.

**Gate (Phase 6 → done):**
- `pytest tests/meta/probes/test_memory_recall_probe.py -q` GREEN; L1 deterministic invariants asserted on 100% sample.
- Probe enable-gate is OFF by default (composition-root flag), mirroring the [[memory-autocapture-enable-policy-enforced]] precedent — never enable a probe in prod from this PR.
- Drift dashboard query against `eval_capture` shows non-zero `target="embedding"` rows from the last hour of production traffic.
- A regression-fixture row (small offline corpus on InMemory backend) is committed and exercised in CI.

### Phase 7 — Recall-relevance eval scaffold (Tier-A; post-cutover)

**Bound to skill:** [llm-eval-grounded-theory](../skills/llm-eval-grounded-theory/SKILL.md). Decisions taken (per user, this session):
- **Eval target:** recall relevance. Action-triggering class = "irrelevant-recall" (a recalled memory that is *not* useful for `task_input`).
- **Pipeline depth:** **Tier-A only.** Stages 0–2 plus a **PROVISIONAL rubric in shadow mode**. NO gold set, NO calibration, NO action-gating in this scope. Stages 3–7 are deliberately deferred — re-open when there is evidence the shadow signal warrants them.
- **Coder:** human (the user). Implementing agent builds infrastructure; **agent MUST NOT do open coding** (skill cardinal rule R3, AP-10).
- **Timing:** **after cutover.** Phase 7 starts only once Phase 5 has shifted traffic and pgvector has emitted ≥ ~100 real `MEMORY_RECALLED` carriers.

#### Strict role split

| Role | Does | Does NOT |
|---|---|---|
| **Implementing agent** | Trace export script, viewer scaffold, open-code table schema, axial-matrix template, shadow rubric harness, eval_capture wiring | Read traces and assign codes. Write taxonomy categories. Author the rubric content. Declare saturation. |
| **User (human first pass)** | Read ≥ 100 traces end-to-end, write open-code notes, decide saturation, cluster into 5–6 axial categories, pick top failure mode, author the provisional rubric | — |

This split honors skill cardinal rules **R3** (LLM proposes / human disposes), **AP-1** (do not skip open coding), **AP-10** (no LLM first pass).

#### Stage 0 — Trace collection (agent builds)

Scope guard: this is *runtime memory* telemetry, not OKF doc-plane content. Stays inside the LTM subsystem.

- New script `scripts/eval/export_recall_traces.py` that, for a date range, joins:
  - The `EventType.MEMORY_RECALLED` carrier (`user_id`, `count`, `query_len`, `keys`, `trace_id`, `task_id`)
  - The corresponding `task_input` from `eval_capture` (already keyed by `task_id`)
  - The recalled rows from `agent_memories` (`payload.text`, `metadata.score`, `metadata.salience`) **via the same `psycopg` connection the BFF uses** — read-only
  - The final answer from `eval_capture` (for "did the recall actually help" signal)
- Output: flat `recall_traces.jsonl` matching the skill's Stage 0 artifact shape — one row per `(trace_id, recall_event_idx)` with columns `trace_id`, `task_id`, `user_id`, `task_input`, `recalled_text[]`, `recalled_score[]`, `final_answer`, `open_code_note: ""` (empty for human fill-in).
- Stable IDs: `trace_id` is the Python-runtime trace_id ([[stress-harness-traceid-superposition]] precedent — never browser-generated), `task_id` carried verbatim through the stack.
- **Environment posture verifier** (skill Stage 0 R3): a sibling helper that flags rows where the recall failure was actually a DB outage, a degraded `MemoryBackendError`, or a tool-blocked task — these are *confounds* and MUST be excluded from agent-failure counts (skill Cardinal Rule 3 + AP-2).
- Trace viewer: pointer to existing Langfuse UI (skill R13: "Langfuse `TEXT` scores work well") — no new viewer code. Document the search query: `trace_id`-prefix or `task_id` filter.

#### Stage 1 — Open coding (human; agent prepares the table only)

- The implementing agent commits an *empty* `docs/research/recall-relevance/open_coding_v1.md` (OKF-excluded — under `docs/research/`, qualitative-research outputs are deliberately not a declared bundle per `CONVENTIONS_OKF.md` §Excluded directories). The agent populates the columns and one example row; the user fills the rest.
- Schema (per skill template):

  | trace_id | task_input (digest) | recalled_text_idx | open_code_note | first_failure | provenance |
  |---|---|---|---|---|---|

- The user (not the agent) annotates ≥ 100 traces; tracks saturation (~20 rows with no new code type → stop).

#### Stage 2 — Axial coding (human-led; agent assists *after* human first pass)

- The implementing agent commits `docs/research/recall-relevance/axial_v1.md` with the skill's axial-matrix scaffold and a strict comment "Do not fill until Stage 1 saturation declared by user." The agent MUST refuse to populate categories preemptively, even if asked — failing this is an AP-10 violation.
- Once the user clusters into 5–6 testable agent-behavior categories, the agent may run the **R21 optional assist** (LLM-suggests-clusters as a *check*, not a *first pass*) only on explicit invocation, and the user keeps disposal authority.
- The taxonomy MUST split: agent-behavior codes (the actual eval target) vs environment confounds (excluded from frequency counts) vs judge-reliability codes (defects in any future judge, not in the recall system).
- **Gate before any rubric work**: IAA ≥ 0.80 on category assignment, OR a pre-declared lower threshold with documented rationale. Implementing agent records the threshold; the user does the labeling.

#### Stage 4 — PROVISIONAL rubric in shadow only (split: code vs confirmation)

- This is the **only** Stage 3+ work in scope. Per skill §"Ship posture" — the rubric ships PROVISIONAL, shadow-mode, never action-gating.
- Rubric content: analytic, binary, evidence-grounded criteria. One criterion per axial category that the user picked as the top failure mode.
- Where it lives in the codebase:
  - Prompt: `prompts/codeReviewer/recallRelevanceJudge_v1.j2` (or equivalent — agent renders via `PromptService` per AGENTS.md **H1/AP-3**, **NEVER** as a Python string).
  - Tier-A probe gets a new sample handler (5–10% sample, per skill Stage 7 L2 lane; reuse the [[agentsframework-eval-probe]] scaffold from Phase 6).
  - Composition-root flag `RECALL_RELEVANCE_JUDGE_ENABLED` defaults **off**; even when on, the verdict only emits a `TrustTraceRecord` (`EventCategory.execution`) — it does NOT modify recall results.
- **Enable-policy posture** mirrors [[memory-autocapture-enable-policy-enforced]] precedent: fails SAFE to shadow until a Stage 5/6 calibration certificate exists. Since we are *not* doing Stages 5–6 in this scope, the flag stays off permanently for this PR.
- **L4 test** (`tests/meta/judges/test_recall_relevance_judge.py`): failure-paths-first matrix on rubric criteria, mocked LLM. Marked `@pytest.mark.slow` (skill §"Testing pyramid"). NO live LLM in CI (AGENTS.md §Testing Rules; skill AP-7).

#### Out of scope (explicitly)

The following are skill stages we are NOT executing in this PR. They become real plans later, gated on shadow-mode evidence:
- **Stage 3 synthetic data** — defer until shadow shows a stratum that production won't supply.
- **Stage 5 gold set** — 250 items, double-labeled, frozen test split. Multi-week. Out.
- **Stage 6 calibration + enable-policy clearance** — only after gold set exists.
- **Stage 7 full monitoring loop with action gates** — never in this PR. Phase 6 already wired the L1/L3 invariant + drift lanes; Stage 7's L2 *judging* lane stays shadow-only.

#### Anti-patterns this phase actively guards against

Mapped to the skill's AP table:
- **AP-1 (skip open coding → jump to judge)** — the role split makes this impossible: agent CANNOT author the rubric without the saturated open-code + axial output files committed by the user first. The Stage 4 prompt file MUST cite specific axial categories by name.
- **AP-2 (count environment blocks as agent failures)** — the Stage 0 environment-posture verifier is a hard prerequisite; recall failures during a `MemoryBackendError` are stripped before frequency counts.
- **AP-3 (global accuracy as gate)** — no gate in this scope. When Stage 6 ships (out of scope), the gate metric MUST be precision on `irrelevant-recall`, not accuracy.
- **AP-7 (always-pass judge in production)** — composition-root flag defaults off; even on, judge runs in shadow only (no recall mutation).
- **AP-10 (LLM first-pass open coding)** — agent execution-contract scope guard, restated in §Role split.

#### Artifacts list (what Phase 7 ships)

- `scripts/eval/export_recall_traces.py` (agent writes)
- `scripts/eval/check_environment_posture.py` (agent writes; flags confounds)
- `docs/research/recall-relevance/open_coding_v1.md` — schema only, no rows (agent writes scaffold; user fills)
- `docs/research/recall-relevance/axial_v1.md` — scaffold only (agent writes; user fills)
- `prompts/codeReviewer/recallRelevanceJudge_v1.j2` (agent writes shell + placeholders; user authors rubric content **after** Stage 2 gate clears)
- `services/governance/recall_relevance_judge.py` — judge invocation, shadow-only, behind disabled flag (agent writes)
- `tests/meta/judges/test_recall_relevance_judge.py` — L4 failure-mode matrix, mocked LLM (agent writes; failure-paths-first)
- A new memory at `~/.claude/projects/.../memory/recall-relevance-tier-a.md` recording the Stage 0 schema + the user's Stage 2 taxonomy (added by user after Stage 2 gate)

**Gate (Phase 7 → done):**
- Stage 0: `scripts/eval/export_recall_traces.py` runs against a real pgvector deployment and produces ≥ 100 rows of `recall_traces.jsonl`; environment-posture verifier excludes confound rows; column schema matches the skill template
- Stage 1: user has annotated ≥ 100 traces, saturation logged (~20 rows with no new code), open-code file committed (user, not agent)
- Stage 2: user has produced a 5–6 category axial taxonomy with confounds split out, IAA ≥ 0.80 (or pre-declared threshold) on category assignment, top failure mode selected with documented rationale (user, not agent)
- Stage 4 (shadow): provisional rubric `.j2` rendered via `PromptService` (AGENTS.md H1), judge wired behind a default-off composition flag, L4 test green, **never invoked from a path that modifies recall**
- Architecture test: `services/governance/recall_relevance_judge.py` does not import from `orchestration/` (AP-4); `psycopg` import in `scripts/eval/` permitted because it's not a service
- `pytest tests/ -q` GREEN; rejection tests ≥ acceptance tests on the L4 judge file
- A "Stage 5/6 deferred" note appended to `docs/plans/log.md` so the gold-set work is discoverable when conditions warrant it

## Where this Concept lives (OKF index updates)

When the implementation lands (NOT in this plan PR), the implementing agent appends:
- `docs/plans/log.md` — one-line entry per completed phase (newest first), per the [docs/plans/](./log.md) OKF Bundle convention.
- A new memory in the agent memory bundle (`~/.claude/projects/.../memory/`, the external OKF bundle declared in `docs/CONVENTIONS_OKF.md`) summarizing what was *non-obvious* about the cutover — only the surprises, not the things derivable from the diff. Candidate surprises: SDK-version drift killing Mem0 v1 fakes, JSONB freeing us from the JSON-string flattening hack, the `MEMORY_BACKEND=pgvector` + missing `DATABASE_URL` rejection path.

This plan file itself is the planning Concept; once the work ships, mark `status: shipped` in the frontmatter and append a `closed: 2026-MM-DD` field. Do not delete the file — the OKF model is append-only Concepts with link history.

## Critical files

Replaced / removed:
- `services/memory_backends/mem0.py` — delete
- `middleware/adapters/memory/mem0_cloud_client.py` — delete
- `tests/services/memory_backends/test_mem0_backend.py` — delete (`_FakeMem0Sdk` goes with it)
- `pyproject.toml` — drop `mem0ai>=2.0,<3`

Added:
- `services/embedding/port.py` (`EmbeddingClient` Protocol) — **in `services/`, not `middleware/`** (C1)
- `services/embedding/litellm_embedding_client.py` (LiteLLM, not `openai` SDK)
- `services/embedding/fake.py` (`FakeEmbeddingClient`)
- `services/memory_backends/pgvector.py` (owns a small sync `psycopg_pool.ConnectionPool` from an injected DSN — C4)
- New SQL migration for the `agent_memories` table + `vector` extension (Python-side `cloud-sql-proxy` apply, not the Node/drizzle runner)
- Probe registration under `meta/` per `agentsframework-eval-probe`
- Phase 7 (Tier-A eval) scaffolding: `scripts/eval/export_recall_traces.py`, `scripts/eval/check_environment_posture.py`, `services/governance/recall_relevance_judge.py`, `prompts/codeReviewer/recallRelevanceJudge_v1.j2`, `docs/research/recall-relevance/{open_coding,axial}_v1.md` (empty scaffolds — user fills body), `tests/meta/judges/test_recall_relevance_judge.py`
- **Conditional (Phase 0 C2 = Branch B only):** `middleware/adapters/memory/pgvector_memory_client.py`. Default expectation is Branch A (the async seam is deleted, not built).

Removed (Phase 3 Branch A — expected):
- `middleware/adapters/memory/mem0_cloud_client.py`
- `middleware/ports/memory_client.py` (the async `MemoryClient` Protocol + its `{content,score}` `MemoryRecord`)
- the `memory_client` field on `MiddlewareAdapters` + both `composition.py` construction sites

Edited:
- `middleware/composition.py` — branch on `MEMORY_BACKEND`; construct embedding client + pgvector backend, inject one into the other (composition legally imports *down* into `services/`)
- `services/memory_backends/pgvector.py` (**Phase 4.5**) — `DDL` constant becomes the typed-memory superset (`mem_type` + generated `ts` + `(user_id, mem_type)` B-tree + GIN index); `put` derives + writes `mem_type` from `metadata['type']`; `_embed_text_of` prefers a non-empty `payload['embed_text']`, else non-empty `payload['text']`, else repr (empty/non-str `embed_text` falls through — not authoritative). All additions observably inert day one (design §5). No Protocol change; `get`/`search` still return the four-field `MemoryRecord`.
- `services/long_term_memory.py` — no changes (sync `MemoryBackend` + `MemoryRecord` untouched; the Python type filter keeps reading `metadata['type']`)
- `orchestration/react_loop.py` — **no changes** (recall/store route through `LongTermMemoryService`; Phase 6 reads existing carriers — C6)
- Settings: `AgentRuntimeSettings` (add `memory_backend` + embedding settings; `MEM0_*` removed only at Phase 5 S6)
- Terraform: `MEMORY_BACKEND=pgvector` + Python-backend `DATABASE_URL` bound; `MEM0_*` removed at Phase 5 S6
- `tests/architecture/test_middleware_layer.py` — remove `mem0ai` from the SDK allowlist (B5)

## Reuse / patterns already in repo

- `LongTermMemoryService` — keep verbatim; it already does dedup, budgeting, safety-floor, suppress.
- Sync `MemoryBackend` Protocol + `MemoryRecord` (`services/long_term_memory.py:49,75-88`) — the swap point. (The async `middleware/ports/memory_client.py` `MemoryClient` is the *dead* seam from B1 — likely deleted, not a reuse target.)
- `InMemoryMemoryBackend` — keep as the dev/test default and as a reference implementation.
- `services/memory_backends/sqlite.py` — a stdlib-`sqlite3` durable backend (`sqlite.py:30`). **Not** a swap target and **not** in deletion scope; left as-is. It is a second reference for the `list_all`-as-optional-capability pattern.
- `agent_ui_adapter/adapters/runtime/postgres_saver.py:72` — the `psycopg_pool.AsyncConnectionPool` precedent (driver = psycopg 3, NOT asyncpg). Reuse the **pattern**, not the module (B9): the memory backend builds its own sync pool.
- `services/llm_config.py:32` — the LiteLLM-in-`services/` pattern (`ChatLiteLLM`); the embedding client mirrors it with `litellm.aembedding`.
- `services/tools/search/port.py` — precedent for a Protocol port living in `services/` with adapters beside it.

## Verification (global reference)

Truth lives in the per-phase **Gate** blocks above and the §Agent execution contract at the top. This section is a one-stop summary for reviewers.

**At end of every phase**: `pytest tests/architecture/ -q` GREEN + `pytest tests/ -q` GREEN + that phase's Gate commands.

**At end of work** (post-flight, copied from §Agent execution contract):
- `pytest tests/ -q` GREEN
- `grep -r "mem0\|mem0ai" --include="*.py" --include="*.toml"` returns 0
- `python scripts/okf_lint.py` GREEN
- One no-traffic Cloud Run revision has run the [[memory-multisession-e2e-corpus]] suite GREEN with `MEMORY_RECALLED` / `MEMORY_STORED` carriers present
- Top-3 recall on a fixed task set has ≥80% overlap with the mem0 baseline (sanity check on the embedding swap, not a gate — different embedding models give different rankings)
- mem0 keys still live in env for 24h-rollback; do NOT delete in the same PR that flips traffic

## Risks

- **Embedding cost**: `text-embedding-3-small` is $0.02/1M tokens — a typical task input + answer is ~200 tokens, so 5M memories ≈ $20. Negligible vs Mem0 Hobby quotas.
- **HNSW recall vs exact kNN**: at our scale (<100K rows/user) `lists` parameter defaults are fine; revisit if a user crosses 1M.
- **Cold start**: first query after a deploy will pay one embedding-API round-trip. Cache embeddings per-query for the run (single recall call per task already, see `recall_memoized` at `react_loop.py:1080`).
- **Empty memory at cutover**: per user decision, pgvector starts empty. First N tasks per user will recall nothing. Acceptable for current usage; revisit if this degrades a stress run ([[memory-multisession-e2e-corpus]]).
- **Embedding model lock-in via dimension**: if we ever switch from `text-embedding-3-small` (1536) to a smaller model (BGE-small 384), we have to re-embed every row. The Protocol lets us swap; the column type does not. Mitigation: keep `EMBEDDING_DIMENSION` in settings so the migration is explicit.

### Failure-mode → detection → response matrix (from design §8)

Each failure mode is tied to the phase/gate that detects it, so a reviewer can see the change is observable end-to-end:

| Failure mode | Detection signal | Immediate behavior | Mitigation |
|---|---|---|---|
| Missing `pgvector` extension | Phase 0 C3 SQL probe fails | Block Phase 1+ | Infra task (Terraform `database_flags` + restart), re-run gate |
| `MEMORY_BACKEND=pgvector` but no DSN | Composition-time check (Phase 4 rejection test) | Raise at startup — **no** silent fallback to InMemory in prod | Fix env, redeploy |
| Embedding dimension mismatch | L2 contract test + runtime assertion | Reject write/search with typed `MemoryBackendError` | Keep `EMBEDDING_DIMENSION` aligned with model |
| Cross-user leakage regression | L2 failure-mode + concurrency tests; probe invariants | Block release | Fix SQL `WHERE user_id=$…` predicates, re-run contract suite |
| `build_adapters` crash on unset `MEM0_API_KEY` | Phase 0.5 R1 acceptance test | App fails to boot | Make adapter keyless before S6 (Phase 0.5) |
| Recall quality drift | Phase 6 L3 drift lane anomaly | Alert + investigate | Compare telemetry trends; traffic rollback if needed |
| Post-cutover instability | Phase 5 S5 soak monitors (carriers, error rate) | Traffic rollback to mem0 revision | Use S4/S5 reversible window before S6 |

---

## Honest review — gaps found before implementation (2026-06-22)

This section is a critical pre-implementation audit. Each finding was **verified against the live code**, not inferred from the plan. Findings are ranked by severity. Several invalidate or rescope earlier sections of this plan — read this before starting Phase 1.

### 🔴 BLOCKER B1 — The async `MemoryClient` (BFF ring) has NO live consumer. Phase 3 may be building a replacement for a dead seam.

**Claim in plan:** Phase 3 builds `PgVectorMemoryClient` because "the BFF's `/agent/memory` CRUD routes use the async `Mem0CloudClient`."

**Verified reality:**
- `grep -rn "memory_client\.\(add\|search\)"` across all `.py` (excluding tests) returns **zero** hits.
- The only references to `memory_client` are the two construction sites at `middleware/composition.py:222,282`. It is built and stored on `MiddlewareAdapters`, then **never called**.
- The actual `/agent/memory` route handlers in `middleware/app_prod.py` use `LongTermMemoryService` (the **sync** path) via `_require_memory()` (`app_prod.py:363`), NOT the async client.

**Impact:** Phase 3 as written replaces a component that does nothing. Either (a) the async `Mem0CloudClient` is dead code that should be **deleted, not ported**, or (b) there is an intended-but-unwired BFF memory surface. This must be resolved before Phase 3.

**Required action:** Add a Phase 0 investigation: confirm whether the async port is dead. If dead → Phase 3 becomes "delete `Mem0CloudClient` + the async `MemoryClient` port" (smaller, not larger). If a real consumer is intended → that wiring is a *separate* missing-feature task, not part of this swap. **Do not port a dead seam.**

### 🔴 BLOCKER B2 — Two different `MemoryRecord` types; the plan conflates them.

**Verified reality:** there are **two** `MemoryRecord` classes:
- `middleware/ports/memory_client.py:24` — async/BFF wire type: `{id, user_id, content, score, created_at}`. **No `key`, no `payload`, no `metadata`.**
- `services/long_term_memory.py:49` — sync/graph type: `{user_id, key, payload: dict, metadata: dict}`. **No `content`, no `score`, no `created_at` as top-level.**

**Impact:** Phase 2's SQL schema (`content`, `payload` JSONB, `metadata` JSONB, `key`) is a **union** of the two — it matches neither type cleanly. The sync backend (`PgVectorMemoryBackend`) maps to the *sync* record (key/payload/metadata) and must NOT carry a `content` column as a first-class field — the salient text rides inside `payload` (see `services/long_term_memory.py:30` `_SALIENCE_KEY`/payload convention). The `content` column in the plan's DDL is a leftover from the async type.

**Required action:** Rewrite the Phase 2 DDL to drop the standalone `content` column (or make it a generated/denormalized copy of `payload->>'text'` only for embedding/debug). The embedding is computed from `payload`'s salient text, not a separate `content` field. Reconcile which record type each phase targets, explicitly.

### 🟠 MAJOR B3 — "Same Cloud SQL as BFF threads" is unverified and probably crosses a language boundary.

**Claim in plan:** "reuse the existing `DATABASE_URL` that BFF threads already use."

**Verified reality:**
- The BFF thread store is **TypeScript/drizzle** (`frontend/lib/adapters/thread_store/pg_thread_repo.ts`, `db/migrations/0000_init_threads.sql`). It runs in the **Next.js BFF ring**, reached from Node — not from the Python backend.
- The Python backend *does* reach Postgres, but via a **different** consumer: the LangGraph checkpointer `agent_ui_adapter/adapters/runtime/postgres_saver.py:56`, which reads its own `DATABASE_URL`.

**Impact:** "BFF threads on Cloud SQL" and "Python backend can write `agent_memories`" are two different connections, possibly two different databases or schemas on the same instance. The plan's Pre-flight check ("the threads table queries return rows") proves the *Node* path works — it does NOT prove the *Python* backend has a working `DATABASE_URL` pointed at a database where it can `CREATE EXTENSION vector` and own a table.

**Required action:** Pre-flight must verify the **Python** side: that `postgres_saver`'s `DATABASE_URL` (the env the backend actually has) reaches an instance where we can create the extension + table, and that we have `CREATE` privileges there. Confirm whether `agent_memories` lives in the same DB as the checkpointer tables or a separate logical DB. The migration tooling is also split: drizzle (Node) for threads vs. raw SQL/`cloud-sql-proxy` for this — pick the Python-side path explicitly.

### 🟠 MAJOR B4 — `pgvector` extension availability on Cloud SQL is assumed, not confirmed.

Cloud SQL for PostgreSQL supports `pgvector`, but the extension must be **enabled per-instance** and the instance must run a Postgres version new enough for **HNSW** (pgvector ≥ 0.5, Postgres ≥ 12; HNSW landed in pgvector 0.5.0). The existing threads instance was provisioned for plain relational threads — nobody has confirmed it has pgvector available or that `CREATE EXTENSION vector` will succeed without a flag/allowlist change.

**Required action:** Pre-flight: `SELECT * FROM pg_available_extensions WHERE name='vector';` against the **Python-reachable** instance. If absent, enabling it may require a Terraform `database_flags` change + instance restart — a real infra task that belongs in Phase 5, not a one-line migration.

### 🟡 MODERATE B5 — Architecture test is an allowlist edit, not just a new assertion.

**Verified reality:** `tests/architecture/test_middleware_layer.py:59` has `mem0ai` in an explicit allowed-SDK list; lines 31/34/192/215 reference it in messages. Removing mem0 means **editing that allowlist** (removing `mem0ai`, adding nothing — embeddings reuse the existing OpenAI allowance if present). The plan's "Architecture-test additions" frames this as five *new* assertions but omits the *removal* edit. If `mem0ai` stays in the allowlist after deletion, the "0 mem0 imports" assertion and the allowlist will silently disagree.

**Required action:** Phase 5 deletion checklist must include removing `mem0ai` from the allowlist at `test_middleware_layer.py:59` and updating the four doc-comment references. *(Superseded detail: the original draft suggested allowing `openai` under `middleware/adapters/embedding/`. The C1 fix removes that path entirely — the embedding client lives in `services/embedding/` and uses `litellm`, which is already permitted. No new `middleware` SDK allowance is needed.)*

### 🟡 MODERATE B6 — `infer=False` semantics have no pgvector equivalent — make the non-translation explicit.

The whole reason the mem0 backend passes `infer=False` is to stop mem0's LLM from rewriting stored text. pgvector has no such behavior — text is stored verbatim by definition. This is *good* (the footgun disappears), but the plan should state explicitly that **`PgVectorMemoryBackend` stores `payload` byte-for-byte** and that the contract test which currently asserts "stored text reads back verbatim" (the test that exists *because* of `infer`) must be **kept and pass trivially** — not deleted alongside the mem0 fixture. Losing that assertion would remove a real invariant.

### 🟡 MODERATE B7 — Embedding-cost claim double-counts; recall is memoized but store is not.

Risk section says "~200 tokens per task." The embedding-tradeoff section says 500–1000 (recall query + store text). Both can't be the baseline. Recall is memoized per task (`recall_memoized`), so it's ~1 embed/task for reads; store adds a second. The honest figure is **2 embeds/task** (~500–1000 tokens), so the cost table (≈$6/mo at 300M tok) is the right one and the Risk-section "~200 tokens / 5M memories ≈ $20" line is inconsistent — reconcile to one number.

### 🟢 MINOR B8 — Dependency string mismatch.

Plan says `psycopg[binary,pool]`. Actual `pyproject.toml:46-47` is `psycopg[binary]>=3.1.0,<4` **plus** a separate `psycopg-pool>=3.2,<4`. Both are already present (good — Phase 2's "verify in pyproject" is satisfied), but the plan's extras string is wrong and would mislead the agent into editing deps unnecessarily. Pooling comes from the separate `psycopg-pool` package.

### 🟢 MINOR B9 — `agent_ui_adapter/` is a layer the plan never mentions.

The Python Postgres precedent (`postgres_saver.py`) lives under `agent_ui_adapter/adapters/runtime/` — a layer the four-layer-placement table doesn't list. If we want to reuse its connection/pool construction (sensible — don't write a second psycopg bootstrap), the plan should name it as the reference implementation and decide whether `PgVectorMemoryBackend` shares that pool or owns its own. Architecture-rule question: a `services/` backend importing connection plumbing from `agent_ui_adapter/` may cross a layer boundary — needs a ruling.

### 🟢 MINOR B10 — Phase 7 reads `agent_memories` directly; double-check the privacy invariant.

`services/long_term_memory.py:10` states a hard **privacy invariant: payload values NEVER appear in log lines**. Phase 7's `export_recall_traces.py` deliberately exports `payload.text` into a `.jsonl` for human coding. That's legitimate (it's an eval export, not a log line, and the human coder is authorized), but the script must (a) write outside any log sink, (b) land only in a gitignored / `docs/research/`-excluded path, and (c) be user-scoped consistently with `memory_subject()`. Add this as an explicit constraint so the agent doesn't accidentally route exported content through a logger.

### Net assessment

The **core thesis is sound** — we use a tiny slice of mem0; pgvector behind the sync `MemoryBackend` Protocol is the right swap; the graph genuinely doesn't change. But three findings are load-bearing and must be resolved **before** writing code:

1. **B1** — Phase 3 likely deletes-not-ports a dead async seam. This *shrinks* the work but changes its shape.
2. **B2** — the DDL targets a phantom record shape; the sync backend has no `content` field.
3. **B3 / B4** — "reuse the Cloud SQL we already have" is unproven from the **Python** side and may require a real infra change (pgvector enablement, connection ownership).

**Recommended gate before Phase 1:** insert a **Phase 0 — Verification spike** that (i) proves/disproves B1 by tracing every `MiddlewareAdapters.memory_client` consumer, (ii) confirms the Python backend's `DATABASE_URL` can `CREATE EXTENSION vector` and own a table, and (iii) reconciles the Phase 2 DDL to the sync `MemoryRecord`. Only after Phase 0 clears do Phases 1–7 proceed. The rest of the plan (embedding port, composition swap, probe, eval scaffold) is well-formed and survives this review unchanged.

### Follow-up observations — validated 2026-06-22 (all CONFIRMED, folded into the plan)

Seven additional observations were checked against live code. **All seven validated**; the plan above is corrected accordingly. None were rejected.

| # | Observation | Verdict | Where fixed |
|---|---|---|---|
| O1 | services/ → middleware/ports legality | ✅ **CONFIRMED — was a real layering bug.** M1 (`test_middleware_layer.py:86`) forbids it. | Four-layer table correction C1; port moved to `services/embedding/`; new scope guard |
| O2 | trace async client vs sync service consumers | ✅ CONFIRMED (= B1) | Phase 0 C2; Phase 3 rewritten to delete-or-build |
| O3 | sync psycopg + `CREATE EXTENSION vector` + exact `MemoryRecord` shape | ✅ CONFIRMED needed | Phase 0 C3 (disposable spike script) |
| O4 | resolve react_loop edit tension for Phase 6 | ✅ CONFIRMED — resolvable without editing react_loop (carriers already emitted at `:1150`/`:3336`) | Phase 0 C6 |
| O5 | embedding telemetry shape / does `eval_capture.record` change | ✅ **CONFIRMED — signature mismatch.** `record()` is `async`, takes `config` not `user_id`/`task_id` kwargs; `llm_config` is chat-only. | Phase 0 C5; H5 row corrected |
| O6 | shared-DB consumers matrix + pool budget | ✅ CONFIRMED — **and corrects "asyncpg": the checkpointer uses `psycopg_pool.AsyncConnectionPool`**, not asyncpg | Phase 0 C4 matrix + pool decision |
| O7 | async `PgVectorMemoryClient` necessity | ✅ CONFIRMED (= B1/C2) — likely unnecessary | Phase 0 C2; Phase 3 Branch A default |
| O8 | lock the `MEM0_*` rollback sequence | ✅ CONFIRMED worth hardening | Phase 5 S1–S6 locked table |

**Driver-landscape correction (O6):** the reviewer's matrix listed "checkpointer asyncpg" — verified WRONG. All Python PG consumers use **psycopg 3** (`agent_ui_adapter/adapters/runtime/postgres_saver.py:11,67,72` = `psycopg_pool.AsyncConnectionPool`). The new memory backend uses the **sync** psycopg pool. Driver is consistent; only the sync/async pool split matters.

### Third review round — validated 2026-06-22 (all CONFIRMED, folded into Phase 0.5 + Phase 2/5)

A third batch of comments, all checked against live code. **All seven validated**; one (R2) had a lighter fix than proposed.

| # | Comment | Verdict | Where fixed |
|---|---|---|---|
| R1 | Phase 5 deploy impossible: `build_adapters` hard-requires `MEM0_API_KEY` | ✅ **CONFIRMED — BLOCKER.** `_require("MEM0_API_KEY")` at `composition.py` v3 ~181 / v2 ~246; `app_prod.py:74` imports it. App crashes at startup with key unset. | **Phase 0.5 R1** — make memory adapter optional / delete with the dead seam; Phase 5 S0 precondition |
| R2 | DDL `gen_random_uuid()` needs `pgcrypto` | ✅ valid in general; **already satisfied** — instance is `POSTGRES_15` (`data.tf:41`) where it's core; threads migration proves it works keyless | DDL adds defensive `CREATE EXTENSION IF NOT EXISTS pgcrypto` (no-op on PG15) |
| R3 | Test blast radius under-scoped | ✅ **CONFIRMED** — 9 test files assume mem0, not 1 | Phase 0.5 R3 + Phase 4/5 checklists |
| R4 | Infra `MEM0_*` removal incomplete | ✅ **CONFIRMED** — 5 refs in `variables.tf`/`cloud-run-backend.tf` + secret resource + IAM | Phase 0.5 R4; Phase 5 S6 ordered with deploy |
| R5 | `task_id` telemetry infeasible on recall path | ✅ **CONFIRMED** — `search(user_id, query, limit)` carries no task context (`long_term_memory.py:80`) | C5: `task_id` **optional/null on recall**, no signature change |
| R6 | Sync backend thread-safety unspecified | ✅ **CONFIRMED** — hit by `to_thread` + web routes | Phase 0.5 R6 + required concurrency test; DDL note locks the sync pool |
| R7 | Test-strategy contradiction (delete mem0 tests vs reuse contract) | ✅ **CONFIRMED** | Phase 2: extract shared parametrized `contract.py` before deleting mem0-specific file |

**R2 nuance:** the reviewer feared an apply-time failure. On `POSTGRES_15` `gen_random_uuid()` is built-in, so there is **no** failure today (the existing threads migration is the proof). We add the defensive `pgcrypto` line anyway — it costs nothing and survives a hypothetical engine downgrade. R2 is the one comment whose severity was lower than stated; we still hardened it.
