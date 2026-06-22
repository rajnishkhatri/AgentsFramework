---
type: design
title: Replace mem0 with pgvector - Architecture Design
description: Detailed architectural design and visual diagrams for replacing mem0 with an in-repo pgvector memory backend.
tags: [design, architecture, memory, mem0, pgvector, embeddings]
timestamp: 2026-06-22
status: reconciled
related:
  - docs/plans/replace_mem0_pgvector.plan.md
plan_id: replace-mem0-pgvector
---

# Architecture Design: Replacing mem0 with pgvector

This document provides a detailed architectural design and visual diagrams for the planned replacement of the `mem0` memory backend with a first-party `pgvector` implementation, as defined in `docs/plans/replace_mem0_pgvector.plan.md`.

### Diagram index

| # | Diagram | Section |
| :--- | :--- | :--- |
| 1 | System context (who talks to what) | §1 |
| 2 | Before / after swap-point comparison | §2 |
| 3 | Four-layer placement + dependency arrows | §3 |
| 4 | Component class relationships | §3.1–3.2 |
| 5 | Shared DB consumers + pool ownership | §3.3 |
| 6 | Entity-relationship (data model) | §4 |
| 7 | Composition wiring sequence | §5 |
| 8 | Recall + store runtime sequences | §5.1–5.2 |
| 9 | Phase 3 async-seam decision tree | §5.3 |
| 10 | GCP deployment topology | §6 |
| 11 | Rollout timeline + state machine | §6 |
| 12 | Governance telemetry pipeline | §7 |
| 13 | Test pyramid placement | §8 |

---

## 1. Context & Motivation

Currently, the agent uses `mem0` as its durable long-term memory store. However, an audit revealed that we only use a tiny fraction of its capabilities (specifically, per-user kNN search over embeddings), while explicitly disabling its core feature (LLM-driven extraction via `infer=False`).

**Why replace mem0:**
- **Cost & Vendor Risk:** mem0 introduces rate limits, paid tiers, and API churn (e.g., breaking changes in v2).
- **Simplicity:** We already run Cloud SQL Postgres for BFF threads. Adding `pgvector` gives us the exact capabilities we need with zero marginal infrastructure cost.
- **Honesty:** The actual "agent memory" logic (deduplication, salience budgeting, safety floors) already lives in our `LongTermMemoryService`. mem0 is just acting as a vector store.

**Diagram — system context.** Solid boxes are in-repo; dashed boxes are external. The swap is confined to the backend adapter ring — orchestration and LTM policy are unchanged.

```mermaid
flowchart TB
    USER([User BFF UI])
    RL[react_loop.py]
    LTM[LongTermMemoryService]
    MB((MemoryBackend))
    MEM0[Mem0MemoryBackend]
    PGV[PgVectorMemoryBackend]
    MAPI[Mem0 Cloud API]
    EMB[EmbeddingClient]
    PG[(Cloud SQL pgvector)]
    OAI[OpenAI embeddings]

    USER -->|task| RL
    RL -->|recall and store| LTM
    LTM --> MB
    MB -. today .-> MEM0
    MB -->|swap| PGV
    MEM0 --> MAPI
    PGV --> PG
    PGV --> EMB
    EMB --> OAI
```

---

## 2. High-Level Architecture Comparison

The replacement happens entirely behind the existing `MemoryBackend` Protocol. The LangGraph orchestration layer (`react_loop.py`) and the `LongTermMemoryService` remain completely unchanged.

**Diagram — before / after at the swap point.** Green = unchanged; red = removed; blue = new.

```mermaid
flowchart LR
    RL[react_loop.py]
    LTM[LongTermMemoryService]
    PROTO((MemoryBackend))
    RL --> LTM --> PROTO

    subgraph BEFORE["Before - mem0"]
        M0[Mem0MemoryBackend]
        HTTP[HTTP round-trips]
        CLOUD[Mem0 Cloud]
        VDB[(Vendor vector DB)]
        M0 --> HTTP --> CLOUD --> VDB
    end

    subgraph AFTER["After - pgvector"]
        PGV[PgVectorMemoryBackend]
        SQL[Single SQL txn]
        POOL[sync ConnectionPool]
        PG[(Cloud SQL + pgvector)]
        EMB[LiteLLMEmbeddingClient]
        OAI[text-embedding-3-small]
        PGV --> POOL --> SQL --> PG
        PGV --> EMB --> OAI
    end

    PROTO --> M0
    PROTO --> PGV

    classDef keep fill:#ddf4ff,stroke:#0969da,stroke-width:2px,color:#1f2328
    classDef gone fill:#fde8e8,stroke:#cf222e,stroke-width:2px,color:#1f2328
    classDef add fill:#dafbe1,stroke:#1a7f37,stroke-width:2px,color:#1f2328
    classDef ext fill:#f5e8ff,stroke:#8250df,stroke-width:1px,color:#1f2328
    class RL,LTM,PROTO keep
    class M0,HTTP,CLOUD,VDB gone
    class PGV,SQL,POOL,PG,EMB add
    class OAI ext
```

### Non-goals (hard scope guards)

- No edits to `orchestration/react_loop.py` for this backend swap.
- No new symbols under `trust/`.
- No `services/` import from `middleware/` (M1 remains enforced).
- No markdown/RAG/doc-ingestion behavior in runtime long-term memory paths.

---

## 3. Component Design & Layering

The new components must strictly adhere to the Four-Layer Architecture (`docs/Architectures/FOUR_LAYER_ARCHITECTURE.md`).

### 3.0. Layering decision matrix (authoritative)

| New/Changed Module | Layer | Allowed Dependencies | Forbidden Dependencies |
| :--- | :--- | :--- | :--- |
| `services/embedding/port.py` | Services (L2) | stdlib, typing | `middleware/*`, `orchestration/*` |
| `services/embedding/litellm_embedding_client.py` | Services (L2) | `litellm`, services-local modules | `middleware/*`, `langgraph`, `langchain` |
| `services/memory_backends/pgvector.py` | Services (L2) | `psycopg`, `psycopg_pool`, `services.embedding.*`, `services.long_term_memory` | `middleware/*`, `components/*`, `orchestration/*`, `agent_ui_adapter/*` |
| `middleware/composition.py` | Middleware ring | imports downward into `services/*` | upward imports to orchestration internals |

This matrix enforces the C1 correction from the plan: the embedding port lives in `services/`, not `middleware/ports/`.

**Diagram — four-layer placement.** Solid arrows = allowed imports (downward). Red dashed = forbidden (M1).

```mermaid
flowchart TB
    RL[react_loop.py]
    COMP[composition.py]
    APP[app_prod.py]
    LTM[long_term_memory.py]
    PGV[pgvector.py]
    EMBP[embedding port]
    EMBL[litellm client]
    IMEM[in_memory re-export]
    CP[postgres_saver reference]

    RL --> LTM
    APP --> LTM
    COMP --> PGV
    COMP --> EMBL
    COMP --> IMEM
    PGV --> EMBP
    EMBL -.-> EMBP
    PGV --> LTM
    PGV -. FORBIDDEN .-> COMP
    PGV -. FORBIDDEN .-> CP
    EMBP -. FORBIDDEN .-> COMP
```

### 3.1. Embedding Client (services/embedding/)

We introduce a new horizontal service for embeddings. This avoids coupling the memory backend directly to an SDK.

```mermaid
classDiagram
    class EmbeddingClient {
        <<Protocol>>
        +embed(texts) list
        +dimension() int
    }

    class LiteLLMEmbeddingClient {
        -model str
        +embed(texts)
        +dimension() int
    }

    class FakeEmbeddingClient {
        -dim int
        +embed(texts)
        +dimension() int
    }

    EmbeddingClient <|-- LiteLLMEmbeddingClient
    EmbeddingClient <|-- FakeEmbeddingClient
```

- **Placement:** `services/embedding/port.py` (NOT `middleware/ports/` to avoid M1 layering violations).
- **Implementation:** Uses `litellm.aembedding` (sanctioned exception in AGENTS.md rule 4).
- **Telemetry:** Emits a lightweight synchronous telemetry event (`target="embedding"`) for Phase 6 drift detection.

### 3.2. PgVector Memory Backend (services/memory_backends/)

```mermaid
classDiagram
    class MemoryBackend {
        <<Protocol>>
        +put(record)
        +get(user_id, key)
        +search(user_id, query, limit)
        +delete(user_id, key)
    }

    class InMemoryMemoryBackend {
        +put(record)
        +search(user_id, query, limit)
        +list_all(user_id)
    }

    class PgVectorMemoryBackend {
        -pool ConnectionPool
        -embedder EmbeddingClient
        +put(record)
        +search(user_id, query, limit)
        +list_all(user_id)
    }

    class EmbeddingClient {
        <<Protocol>>
        +embed(texts)
        +dimension()
    }

    MemoryBackend <|-- InMemoryMemoryBackend
    MemoryBackend <|-- PgVectorMemoryBackend
    PgVectorMemoryBackend --> EmbeddingClient
```

- **Protocol contract (verified `services/long_term_memory.py:76-80`):** the `MemoryBackend` Protocol declares exactly `put → None`, `get → MemoryRecord | None`, `search(..., limit=10) → list[MemoryRecord]`, `delete → bool`. `list_all(user_id)` is **NOT a Protocol method** — it is an optional capability (commented out at `:81-88`) that `LongTermMemoryService._list_all` detects via `hasattr` and otherwise emulates with an over-fetched empty-query `search`. `PgVectorMemoryBackend` SHOULD still implement `list_all` (both `InMemoryMemoryBackend` and `Mem0MemoryBackend` do) so consolidation/budgeting stays cheap and reliable, but conformance does not require it.
- **Connection:** Owns a small, dedicated synchronous `psycopg_pool.ConnectionPool` (`min_size=1, max_size=4`).
- **Dependency Injection:** The `EmbeddingClient` and `DATABASE_URL` are injected at the composition root (`middleware/composition.py`).
- **Existing backend landscape (`services/memory_backends/`):** `in_memory.py` (re-export), `mem0.py` (to be deleted Phase 5 S6), and `sqlite.py` (a dev/test durable backend using stdlib `sqlite3`). `PgVectorMemoryBackend` is added alongside; `sqlite.py` stays and is **not** in scope for deletion. Only `pgvector.py` introduces a `psycopg` import in this package — the architecture-test allowlist (`test_middleware_layer.py`) must permit `psycopg` there plus the existing checkpointer path, and `sqlite.py`'s stdlib import needs no allowance.

### 3.3. Shared DB consumer map and pool ownership

```mermaid
flowchart TB
    CP[LangGraph Checkpointer async pool]
    MEM[PgVectorMemoryBackend sync pool]
    TH[Thread Store Node pool]
    TBL_CP[(checkpointer tables)]
    TBL_MEM[(agent_memories HNSW)]
    TBL_TH[(threads tables)]
    WARN[Separate pool warning]

    CP --> TBL_CP
    MEM --> TBL_MEM
    TH --> TBL_TH
    MEM -.-> WARN
```

| Consumer | Driver | Pool Type | DSN Source | Ownership Decision |
| :--- | :--- | :--- | :--- | :--- |
| LangGraph checkpointer | `psycopg` | async | Python `DATABASE_URL` | existing |
| `PgVectorMemoryBackend` | `psycopg` | sync (`ConnectionPool`) | Python `DATABASE_URL` (or explicit memory DSN) | new, dedicated small pool |
| BFF thread store | Node `pg`/Drizzle | Node pool | BFF `DATABASE_URL` | existing |

We intentionally do not share the async checkpointer pool with the sync memory backend.

---

## 4. Data Model

The database schema is designed to perfectly round-trip the sync `MemoryRecord` type defined in `services/long_term_memory.py`.

### SQL Schema (`agent_memories`)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE agent_memories (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       TEXT NOT NULL,
  key           TEXT NOT NULL,
  embedding     VECTOR(1536),
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, key)
);

CREATE INDEX agent_memories_user_idx ON agent_memories (user_id);
CREATE INDEX agent_memories_embedding_idx 
  ON agent_memories USING hnsw (embedding vector_cosine_ops);
```

> **Forward-compatible superset (recommended for the S1 migration).** This schema
> is the faithful-swap minimum. The companion improvement design
> [`typed_memory_searchability.design.md`](typed_memory_searchability.design.md)
> §5 defines a **type-aware superset** of this table — adds a first-class
> `mem_type` column, `created_at`, a generated `tsvector`, and a
> `(user_id, mem_type)` index — that costs ~5 extra lines of DDL, keeps day-one
> runtime behavior byte-identical, and avoids a second live Cloud SQL migration
> when per-type retrieval lands. **Decision: fold §5's superset into the Phase 5
> S1 migration (one migration, not two).** The runtime in §5/§6 of this document
> is unchanged either way.

### Mapping to `MemoryRecord`

| SQL Column | `MemoryRecord` Field | Notes |
| :--- | :--- | :--- |
| `user_id` | `user_id` | Partition key |
| `key` | `key` | Unique identifier per user |
| `payload` | `payload` | Opaque dict. Contains `text` used for embedding. |
| `metadata` | `metadata` | Opaque dict. Contains `score`, `salience`, `suppressed`, etc. |
| `embedding` | *(computed)* | Generated via `EmbeddingClient` from `payload['text']` |

*Note: There is no standalone `content` column. The salient text rides inside the `payload` JSONB, matching the exact shape of the sync `MemoryRecord`.*

**Diagram — entity relationship and embedding source.**

```mermaid
erDiagram
    AGENT_MEMORIES {
        uuid id PK
        text user_id
        text key
        vector embedding
        jsonb payload
        jsonb metadata
        timestamptz created_at
    }

    MEMORY_RECORD {
        string user_id
        string key
        dict payload
        dict metadata
    }

    EMBEDDING_CLIENT {
        string model
        int dimension
    }

    MEMORY_RECORD ||--|| AGENT_MEMORIES : round_trip
    AGENT_MEMORIES }o--|| EMBEDDING_CLIENT : embed_payload_text
```

> **Mapping caveat.** `MemoryRecord` (`long_term_memory.py:49-53`) carries only `user_id`, `key`, `payload`, `metadata`. The `id`, `embedding`, and `created_at` columns are **DB-side only** — generated by Postgres / the backend, never present on the Pydantic record. `get`/`search` reconstruct a `MemoryRecord` from the row and drop those columns (search additionally writes the cosine score into `metadata`). So the relationship is a faithful round-trip of the four record fields, not a column-for-column identity.

**Diagram — row lifecycle (put → search round-trip).**

```mermaid
flowchart LR
    R[MemoryRecord in] --> T[extract payload text]
    T --> E[EmbeddingClient embed]
    E --> V[vector 1536]
    V --> DB[agent_memories row]
    DB --> R2[MemoryRecord out]
```

### Data invariants

- `payload` and `metadata` are stored and returned verbatim (no flattening, no coercion).
- User isolation is hard-enforced in every query predicate (`WHERE user_id = $...`).
- `search()` returns at most `limit`, ordered by nearest-neighbor cosine distance.
- The same `MemoryBackend` contract tests used for mem0 must pass unchanged against pgvector.

**Diagram — kNN search (per-user scoped).**

```mermaid
flowchart TB
    Q[Query task_input] --> EMB[embed query to vector]
    EMB --> SQL["kNN query scoped by user_id LIMIT 3"]
    SQL --> HNSW[(HNSW index)]
    HNSW --> RANK[cosine score ranking]
    RANK --> MR[MemoryRecord list]

    subgraph ISOLATION["Hard isolation"]
        U1[user A rows]
        U2[user B rows]
    end

    U2 -. never scanned .-> SQL
    MR --> LTM[LongTermMemoryService filters]

    classDef q fill:#fff8c5,stroke:#bf8700,stroke-width:2px,color:#1f2328
    classDef idx fill:#dafbe1,stroke:#1a7f37,stroke-width:2px,color:#1f2328
    classDef out fill:#ddf4ff,stroke:#0969da,stroke-width:2px,color:#1f2328
    class Q,EMB q
    class SQL,HNSW,RANK idx
    class MR,LTM out
```

---

## 5. Composition & Wiring

The `middleware/composition.py` root is responsible for wiring the correct backend based on environment variables.

```mermaid
sequenceDiagram
    participant App as app_prod
    participant Comp as composition
    participant Settings as settings
    participant Emb as embedding_client
    participant PG as pgvector_backend
    participant IM as inmemory_backend
    participant LTM as memory_service

    App->>Comp: build_adapters
    Comp->>Settings: read MEMORY_BACKEND

    alt pgvector with DATABASE_URL
        Comp->>Emb: construct
        Comp->>PG: construct
        Comp->>LTM: construct with PG
    else inmemory default
        Comp->>IM: construct
        Comp->>LTM: construct with IM
    end

    Comp-->>App: MiddlewareAdapters
```

> **Ground-truth reconciliation (target vs current — verified `composition.py:829-839`).** The diagram above is the **target** wiring. Today `build_components` selects the backend by **presence of `settings.mem0_api_key`** (`Mem0MemoryBackend` if set, else `InMemoryMemoryBackend`) — there is no `MEMORY_BACKEND` setting yet. Phase 4 introduces `MEMORY_BACKEND` and must **replace** the `mem0_api_key` branch, not sit beside it. During the Phase 4→5 transition the selector is effectively three-way — `inmemory` (dev/test) · `mem0` (transitional rollback target, still present until Phase 5 S6) · `pgvector` (new default) — collapsing back to two once mem0 is deleted. The composition root remains the only place a concrete backend is named (rule C1), and `LongTermMemoryService` is always constructed so the graph shape is stable regardless of the flag.

### 5.1. Runtime read path (recall)

```mermaid
sequenceDiagram
    participant RL as route_node
    participant LTM as memory_service
    participant PGV as pgvector_backend
    participant EMB as embedding_client
    participant DB as postgres
    participant GOV as blackbox

    RL->>LTM: search by task_input
    LTM->>PGV: search scoped by user_id
    PGV->>EMB: embed query
    EMB-->>PGV: query vector
    PGV->>DB: kNN query LIMIT k
    DB-->>PGV: ranked rows
    PGV-->>LTM: MemoryRecord list
    LTM-->>RL: MemoryRecord list
    RL->>GOV: MEMORY_RECALLED carrier
```

> **Note on method names (verified `react_loop.py:1093-1096`).** The graph performs top-K recall via `memory_service.search(user_id, task_input, limit)` wrapped in `asyncio.to_thread` inside `route_node` — the universal seam every tier passes through. The service's `recall(user_id, key)` is a **different** method (a single-record get by key) and is NOT the top-K path. Relevance flooring and rendering (`filter_recall_records`, `render_recall_block`) happen in the orchestration helper, not in the backend.

### 5.2. Runtime write path (store)

```mermaid
sequenceDiagram
    participant RL as react_loop
    participant LTM as memory_service
    participant PGV as pgvector_backend
    participant EMB as embedding_client
    participant DB as postgres
    participant GOV as blackbox

    RL->>LTM: store task and answer
    LTM->>PGV: put MemoryRecord
    PGV->>EMB: embed payload text
    EMB-->>PGV: memory vector
    PGV->>DB: upsert row
    DB-->>PGV: ok
    PGV-->>LTM: success
    LTM-->>RL: stored key
    RL->>GOV: MEMORY_STORED carrier
```

**Diagram — recall vs store on the hot path (one task).**

```mermaid
flowchart TB
    TASK([One agent task])
    R1[embed task_input]
    R2[kNN top-3 per user]
    R3[inject into system prompt]
    W1[LTM dedup salience suppress]
    W2[embed task plus answer]
    W3[upsert agent_memories row]

    TASK --> R1 --> R2 --> R3
    TASK --> W1 --> W2 --> W3
```

### 5.3. Async seam resolution (Phase 3 branching)

```mermaid
flowchart TD
    START([Phase 0 C2]) --> TRACE[Trace async MemoryClient consumers]
    TRACE --> D{Non-test consumer found?}

    D -->|No expected| A[Branch A DELETE seam]
    D -->|Yes rare| B[Branch B thin async wrapper]

    A --> A1[Remove mem0_cloud_client]
    A --> A2[Remove memory_client port]
    A --> A3[Drop memory_client field]
    A1 --> AOK([Smaller default path])

    B --> B1[pgvector_memory_client]
    B1 --> B2[asyncio to_thread wrapper]
    B2 --> BOK([Only if consumer proven])
```

---

## 6. Phased Rollout Strategy

The implementation follows a strict, reversible sequence to ensure zero downtime and safe rollback capabilities.

**Diagram — GCP deployment topology at cutover.**

```mermaid
flowchart TB
    UI[Next.js BFF Chat UI]
    REV_OLD[Revision N mem0 rollback]
    REV_NEW[Revision N+1 pgvector live]
    EXT[pgvector extension]
    T_MEM[(agent_memories)]
    T_CP[(checkpointer)]
    PROXY[cloud-sql-proxy migration]
    OAI[OpenAI embeddings]
    MEM0_API[Mem0 API rollback until S6]

    UI --> REV_NEW
    REV_NEW --> T_MEM
    REV_NEW --> T_CP
    REV_NEW --> OAI
    REV_OLD -. rollback .-> MEM0_API
    PROXY --> T_MEM
```

**Diagram — implementation phase timeline.**

```mermaid
gantt
    title replace-mem0-pgvector phases
    dateFormat YYYY-MM-DD

    section Preflight
    Phase 0 spike           :p0w, 2026-06-22, 1d

    section Build
    Phase 1 embedding       :p1, after p0w, 1d
    Phase 2 pgvector backend  :p2, after p1, 2d
    Phase 3 async seam      :p3, after p2, 1d
    Phase 4 composition     :p4, after p3, 1d

    section Deploy
    Phase 5 cutover         :p5, after p4, 2d

    section Governance
    Phase 6 probe           :p6, after p5, 1d
    Phase 7 eval scaffold   :p7, after p6, 2d
```

### Phase 5 Locked Rollback Sequence

1. **S1:** Apply SQL migration to Cloud SQL via `cloud-sql-proxy`. Apply the §4 *forward-compatible superset* (the `mem_type` / `created_at` / `tsvector` columns + `(user_id, mem_type)` index from [`typed_memory_searchability.design.md`](typed_memory_searchability.design.md) §5), not the bare table — one migration covers both the swap and future per-type retrieval.
2. **S2:** Deploy no-traffic Cloud Run revision (`MEMORY_BACKEND=pgvector`, `MEM0_API_KEY` still set).
3. **S3:** Smoke-test the no-traffic tag.
4. **S4:** Shift traffic to the pgvector revision. *(Instant rollback possible)*
5. **S5:** 24h soak period.
6. **S6:** Point of no return. Delete mem0 code -> Remove env vars -> Revoke API key.

### Rollout state model

```mermaid
stateDiagram-v2
    [*] --> Prepared
    Prepared --> DarkLaunched : S2 deploy
    DarkLaunched --> Verified : S3 smoke
    Verified --> LiveCutover : S4 traffic
    LiveCutover --> Soaking : S5 soak
    Soaking --> Finalized : S6 cleanup
    LiveCutover --> Verified : rollback
    Soaking --> Verified : rollback
```

**Diagram — Phase 5 step sequence (S1–S6).**

```mermaid
flowchart LR
    S1[S1 Apply DDL] --> S2[S2 Dark deploy]
    S2 --> S3[S3 Smoke E2E]
    S3 --> S4[S4 Shift traffic]
    S4 --> S5[S5 24h soak]
    S5 --> S6[S6 Cleanup irreversible]
    S4 -. rollback .-> S3
    S5 -. rollback .-> S3
```

---

## 7. Telemetry & Governance (Phase 6 & 7)

The new architecture integrates deeply with our governance framework:

1. **Embedding Telemetry:** `LiteLLMEmbeddingClient` emits a lightweight sync event (`target="embedding"`) containing model, dimension, tokens, latency, and user_id.
2. **Recall/Store Carriers:** `react_loop.py` continues to emit `EventType.MEMORY_RECALLED` and `MEMORY_STORED` unchanged.
3. **L3 Drift Probe:** Consumes the embedding telemetry and recall carriers to detect degradation in index quality or embedding drift.
4. **Tier-A Eval Scaffold:** Generates `recall_traces.jsonl` by joining recall carriers, `eval_capture` task inputs, and read-only DB queries for human-led open coding and rubric generation.

### Governance telemetry dataflow

```mermaid
flowchart TB
    REC[recall path]
    STO[store path]
    EMB_CALL[embedding calls]
    C_REC[MEMORY_RECALLED carrier]
    C_STO[MEMORY_STORED carrier]
    T_EMB[embedding telemetry]
    BB[BlackBox trace]
    EVT_LOG[embedding event stream]
    L1[L1 probe invariants]
    L3[L3 drift lane]
    EXP[export recall traces]
    POST[environment posture check]
    JSONL[recall_traces jsonl]
    OPEN[open coding]
    AXIAL[axial coding]
    JUDGE[shadow judge flag OFF]

    REC --> C_REC
    STO --> C_STO
    EMB_CALL --> T_EMB
    C_REC --> BB
    C_STO --> BB
    T_EMB --> EVT_LOG
    BB --> L1
    BB --> L3
    EVT_LOG --> L3
    BB --> EXP
    EXP --> POST
    POST --> JSONL
    JSONL --> OPEN
    OPEN --> AXIAL
    AXIAL --> JUDGE
```

### Privacy and handling constraints

- Export artifacts containing recalled text are not log lines and must never flow through runtime logging sinks.
- Export scripts enforce user scoping (`memory_subject()` semantics) during joins.
- Sensitive eval exports should live in research paths with explicit handling discipline before any commit.

---

## 8. Failure Modes & Mitigations

**Diagram — test pyramid placement for this change.**

```mermaid
flowchart TB
    P6[meta recall probe]
    P7[meta relevance judge]
    TE[embedding client tests]
    TP[pgvector backend tests]
    TC[composition tests]
    TA[architecture tests]
    ARCH[dependency rules]

    P6 --> TE
    P7 --> TE
    TE --> ARCH
    TP --> ARCH
    TC --> ARCH
    TA --> ARCH
```

| Failure Mode | Detection Signal | Immediate Behavior | Mitigation |
| :--- | :--- | :--- | :--- |
| Missing `pgvector` extension | Phase 0 C3 SQL probe fails | Block Phase 1+ | Infra task (enable extension), then re-run gate |
| `MEMORY_BACKEND=pgvector` but no DSN | Composition-time check | Raise startup error (no silent fallback) | Fix env and redeploy |
| Embedding dimension mismatch | Backend contract tests + runtime assertion | Reject write/search with typed error | Keep `EMBEDDING_DIMENSION` aligned with model |
| Cross-user leakage regression | L2 failure-mode tests + probe invariants | Block release | Fix SQL predicates and re-run contract suite |
| Recall quality drift | L3 drift probe anomaly | Alert + investigate | Compare telemetry trends, rollback traffic if needed |
| Post-cutover instability | Soak window checks | Traffic rollback to previous revision | Use S4/S5 reversible window before S6 |

**Diagram — failure detection and response paths.**

```mermaid
flowchart LR
    D1[extension probe] --> A1[block phase 1]
    D2[DSN guard] --> A2[fail fast at boot]
    D3[contract tests] --> A3[reject release]
    D4[drift probe] --> A4[alert team]
    D5[soak monitors] --> A5[traffic rollback]
```

## 9. Implementation Readiness Checklist

- [ ] Phase 0 C1-C6 evidence recorded in `docs/plans/log.md`.
- [ ] Layering checks green with new services modules.
- [ ] Contract tests green for `PgVectorMemoryBackend`.
- [ ] Composition rejection path implemented (`pgvector` without DSN fails fast).
- [ ] No-traffic and soak rollout playbook validated.
- [ ] mem0 deletion and key revocation deferred until post-soak S6.
