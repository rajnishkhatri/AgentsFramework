# SPIKE_C — Alternatives research

| Field | Value |
|---|---|
| **Companion to** | [SPIKE_C.md](SPIKE_C.md) |
| **Sprint** | 0 |
| **Run date** | 2026-04-23 |
| **Trigger** | Spike C measured Mem0 Cloud Hobby search p95 = 447.6 ms (2.2× over the 200 ms budget). Before defaulting to the V1 fallback ("defer F15 to v1.5"), evaluate other substrates that might both (a) clear the 200 ms bar and (b) stay inside the V3-Dev-Tier free / low-cost envelope. |
| **Outcome** | **No swap performed in v1.** Mem0 Cloud Hobby retained per Decision **D-S0-8** (see [SPRINT_0_RUNBOOK.md](../SPRINT_0_RUNBOOK.md) §0). This document is the on-disk record of the swap candidates, kept so any future re-evaluation does not have to redo the legwork. |

---

## 1. Re-anchored acceptance criteria

| Constraint | Threshold |
|---|---|
| `search()` p95 latency | ≤ 200 ms (hard, per H5) |
| Monthly cost in dev (Stage A) | $0 ideal, ≤ $25 acceptable |
| Free-tier limit ≥ | 10 K writes + 1 K – 10 K reads / mo |
| Native semantic search scoped by `user_id` | required |
| SDK confined to `agent_ui_adapter/adapters/memory/` (no vendor types past boundary) | required (F-R8 / A4) |
| Composition-root-only swap path to a paid tier | required (F3) |
| Optional: auto-extract structured facts from chat (the Mem0 value-add) | nice-to-have |

## 2. Six candidates that survived the first cut

| # | Candidate | Why on the list |
|---|---|---|
| 1 | **pgvector on Neon Free** (DIY) | Already in our V3 stack. Lowest possible network hop. |
| 2 | **Cloudflare Vectorize** | Already partially in our stack (CF Pages). Edge-distributed. |
| 3 | **Upstash Vector** | Most generous free tier (10 K queries / **day**). Same `serverless + scale-to-zero` pattern as the rest of V3. |
| 4 | **Zep Cloud** | The "managed memory layer with graph + temporal facts" replacement most often discussed. |
| 5 | **Self-hosted Mem0 OSS** in the Cloud Run pod | Same Mem0 DX, but no network hop. |
| 6 | **LangMem SDK + DIY backend** (e.g., pgvector) | Get the auto-fact-extraction abstractions; keep storage in our control. |

## 3. Side-by-side comparison

| | (1) pgvector / Neon | (2) CF Vectorize | (3) Upstash Vector | (4) Zep Cloud | (5) Mem0 OSS in pod | (6) LangMem + pgvector |
|---|---|---|---|---|---|---|
| **Free-tier cost** | $0 (3 Neon Free projects already in V3) | $0 (Workers Free) | $0 (1 free DB) | $0 (1 K credits/mo, **no rollover**, lower priority) | $0 infra (within Cloud Run free tier; +~150 MB image) | $0 (LangMem SDK) + $0 (Neon Free) |
| **First paid tier** | Neon Launch PAYG: $0.106/CU-hr, no monthly minimum (~$5 – 10/mo at our load) | Workers Paid $5/mo + ~$0.06 – $0.59 metered | $0.40 / 100 K requests **OR** $60/mo flat for 1 M/day | **$125/mo Flex** (50 K credits) — **NOT** $25 as the V3 plan assumed; the $25 figure is a top-up increment, not the entry tier | Same as Cloud Run + Neon | Same as (1) |
| **Free-tier write/read limits** | 0.5 GB + 100 CU-hr per Neon project (covers ~10 K – 100 K vectors easily in dev) | 5 M stored dimensions + 30 M queried dimensions / mo (≈ 6.5 K vectors @ 768 d for storage; queries effectively unlimited at our scale) | **10 K queries / day**, 200 M vec×dim cap, 100 namespaces | **1 K credits / mo**; each Episode (chat message, JSON, text block ≤ 350 B) = 1 credit. Heavy rate-limiting | bounded only by Cloud Run / Neon | as (1) |
| **Measured p95 latency from Cloud Run us-central1** | **~28 ms** (pgvector + pgvectorscale benchmark, 50 M vectors, 99 % recall) | **~31 ms median**, p95 not published; edge-optimised | sub-10 ms to ~50 ms depending on region (US-Iowa GCP region available — same as us-central1) | Vendor claims "200 ms retrieval"; sub-200 ms p95 reported in third-party benchmark | <10 ms (same pod) | same as (1) |
| **Verdict against ≤ 200 ms p95 budget** | ✅ comfortable (7× headroom) | ✅ comfortable (6× headroom) | ✅ comfortable | ⚠️ at the edge | ✅ best-in-class | ✅ comfortable |
| **Auto fact extraction from chat (the Mem0 value-add)** | ❌ DIY (write your own LLM-as-extractor pass) | ❌ DIY | ❌ DIY | ✅ native (with temporal knowledge graph) | ✅ Mem0 OSS includes it | ✅ LangMem includes it |
| **`user_id` scoping** | SQL `WHERE user_id = $1` | metadata filter `{user_id: …}` | metadata filter | native multi-tenant | native (Mem0 API) | namespace per user |
| **Substrate-swap fit (F3)** | swap Neon → Cloud SQL is config-only | swap Vectorize → another vector DB rewrites adapter | swap Upstash → Pinecone rewrites adapter | swap Zep → anything rewrites adapter | container swap | LangMem swap to alternative backend = config |
| **SDK leakage risk** | Drizzle types only (already in our stack); easy to wrap | needs `@cloudflare/workers-types` in adapter; clean wrapper | needs `@upstash/vector` SDK; clean wrapper | needs `@getzep/zep-cloud` SDK; clean wrapper | needs `mem0ai` Python SDK; clean wrapper | LangMem types in adapter only |
| **Dev-loop friction** | uses an existing Neon connection, no extra account | new Cloudflare account / project step | new Upstash account step | new Zep account step + episode-budget anxiety | new Docker / process supervision | LangMem learning curve |
| **In-spec for V3 architecture invariants?** | ✅ — `agent_app` already on Neon; same connection | ✅ — Cloudflare side already in scope | ⚠️ — adds a 4th vendor | ⚠️ — adds a 4th vendor | ✅ — same `middleware/` Cloud Run pod | ✅ — pure DIY using existing infra |

## 4. Findings worth flagging

- **The V3 plan's "Zep Flex $25" assumption is stale.** Current Zep Cloud Flex is **$125/mo with 50 K credits**; $25 is the top-up cost per 10 K credits. So the documented "Mem0 Hobby fail → swap to Zep Flex $25" path in the V3 plan and SPRINT_BOARD is no longer accurate — it's actually a $125/mo cliff.
- **Zep Free Plan is much smaller than it sounds**: 1 K credits = ~1 K chat messages /mo, with rate-limiting and lower priority. Insufficient even for solo dev once you start round-tripping.
- **Cloudflare Vectorize and Neon pgvector are both "free" in the strict sense for our workload**, but they shine for different reasons (Vectorize = edge proximity to Cloudflare Pages; Neon pgvector = same DB connection as our checkpoint store).
- **The Mem0 spike's failure was network, not API** — see [SPIKE_C.md §4](SPIKE_C.md#4-hypotheses-for-the-latency). Anything we run inside our region (Neon, Cloudflare's edge, Upstash's GCP region, or in-pod) automatically clears the latency bar with multiple-x headroom. The Mem0 OSS option (#5) is the strictly-faster version of what we already failed.

## 5. Tiered shortlist (if/when we re-evaluate)

### Top pick — **pgvector on Neon Free** (option 1)

Why:
- **Zero new vendors.** Neon Free is already provisioned for `agent_app` checkpoints in Sprint 2 (`infra/dev-tier/neon.tf`).
- **Zero new cost.** Free until the underlying Neon project hits 0.5 GB or 100 CU-hr.
- **Concrete latency measurement**: 28 ms p95 at 50 M vectors with HNSW index — 7× under our 200 ms budget and good enough that scale-to-zero cold-start (~500 ms) becomes the real concern, not steady-state search.
- **Cleanest adapter shape.** The same Drizzle / `@neondatabase/serverless` SDK already needed for `ThreadStore` (S3.3.3 in SPRINT_BOARD) covers this — one import, one connection pool.
- **Substrate swap stays trivial**: Neon → Cloud SQL is a connection-string change at Stage D.

The cost — and it's real — is that you give up Mem0's auto-fact-extraction. You'd need either a small LLM-call pass that turns each (user_msg, assistant_msg) pair into 0..N "memory facts" (~100 lines of code), or you adopt LangMem (option 6) on top of pgvector to get that pass for free.

### Strong runner-up — **LangMem SDK + pgvector on Neon** (option 6)

Why pick this over (1):
- You get the "extract structured facts from chat" pass that made Mem0 attractive in the first place.
- Storage is still your own Postgres — same latency profile as (1).
- LangMem is a LangChain-ecosystem SDK and we already depend on `langchain-litellm` and `langgraph`, so no new vendor relationship.

Why you might *not* pick this:
- Adds a non-trivial dep that doesn't perfectly fit our F-R8 boundary; need to wrap carefully.
- Real F15 product spec hasn't been written; you may be paying for abstractions you don't end up using.

### Backup / future option — **Cloudflare Vectorize** (option 2)

Worth keeping in your back pocket because:
- Cloudflare is already on the V3 frontend critical path (Pages + edge).
- Edge co-location lets the BFF (Route Handlers) call it directly without going through Cloud Run middleware — useful if at some point the BFF wants its own lightweight memory cache for personalization.

But not the right pick for a from-scratch v1 because:
- It would mean a memory adapter that doesn't share the same network path as the agent loop, which inverts the data-locality story.
- Our current architecture has all credentials in `middleware/` (F-R9 / S2); a Vectorize-from-BFF call would muddy that boundary.

### Drop from consideration

- **Zep Cloud** — entry tier is $125/mo, not $25. Defer to v1.5 product re-evaluation.
- **Upstash Vector** — adds a 4th vendor for no measurable benefit over pgvector.
- **Self-hosted Mem0 OSS** — fastest possible, but the operational cost (extra container, model dependency for embeddings, supervision) is too high relative to (1) for v1.

## 6. Recommended Spike C-prime (if/when we re-evaluate)

Same harness as Spike C, but pointed at pgvector on Neon Free:

- 100 seeds + 50 searches design.
- HNSW index on `(user_id, embedding)`.
- Use `text-embedding-3-small` (OpenAI, 1536 d) — already on the account.
- Pass criterion: same ≤ 200 ms p95.

Estimated wall-clock: 30 minutes once a Neon project + connection string is available.

## 7. Sources used

| URL | Used for |
|---|---|
| <https://www.getzep.com/pricing> | Zep Cloud pricing (Flex $125/mo, Free 1 K credits) |
| <https://developers.cloudflare.com/vectorize/platform/pricing/> | CF Vectorize free-tier limits + $0.06 – $5.86/mo example workloads |
| <https://upstash.com/pricing/vector> | Upstash Vector free-tier (10 K queries/day, 200 M vec×dim) |
| <https://encore.dev/articles/pgvector-vs-pinecone> | pgvector p50/p95 latency baseline |
| <https://blog.cloudflare.com/workers-ai-bigger-better-faster/> | CF Vectorize 31 ms median latency claim |
| <https://dev.to/anajuliabit/mem0-vs-zep-vs-langmem-vs-memoclaw-ai-agent-memory-comparison-2026-1l1k> | Mem0 vs Zep vs LangMem vs MemoClaw 2026 comparison |
| <https://vectorize.io/articles/hindsight-vs-zep> | Zep Cloud sub-200 ms retrieval claim |
| <https://neon.com/docs/ai/ai-vector-search-optimization> | Neon pgvector tuning (HNSW `m` / `ef_search`) |
| <https://dev.to/polliog/postgresql-as-a-vector-database-when-to-use-pgvector-vs-pinecone-vs-weaviate-4kfi> | pgvectorscale 28 ms p95 @ 50 M vectors benchmark |
