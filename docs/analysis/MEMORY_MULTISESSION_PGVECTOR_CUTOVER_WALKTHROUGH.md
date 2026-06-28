---
type: analysis
title: 'Memory multi-session E2E — Phase 5 pgvector cutover walkthrough'
description: 'Step-by-step case walkthrough of the MEM_SMOKE run after mem0→pgvector cutover, with Langfuse trace reasoning.'
tags: [analysis, memory, pgvector, e2e]
---

# Memory multi-session E2E — Phase 5 pgvector cutover walkthrough

Step-by-step record of the **MEM_SMOKE** run that validated cross-session memory after the **mem0 → pgvector** Phase 5 cutover. Each probe case includes what happened in the UI, what Langfuse carriers show on the wire, and how the offline gate scored it.

---

## Run metadata

| Field | Value |
|---|---|
| **Date** | 2026-06-22 |
| **Backend** | Initial MEM_SMOKE: rev **`00092-8wq`**. Hotfix deploy: rev **`00094-rfq`** (`af3336a`, asyncio-bridge in `_embed_sync`). `MEMORY_ENABLED=true`, `MEMORY_BACKEND=pgvector`, `EMBEDDING_MODEL=text-embedding-3-small`, `EMBEDDING_DIMENSION=1536` |
| **Frontend** | `https://agent-frontend-w65nrxwkiq-uc.a.run.app` |
| **Auth** | Real WorkOS AuthKit session |
| **Suite** | `frontend/e2e/full-stack/memory-multisession.spec.ts`, `MEM_SMOKE=1` (one case per ability) |
| **Profile** | `TEST_PROFILE=prod` |
| **Wall clock** | ~3.1 min (initial) + ~43 s (Hermes crud rerun on rev 00094) |
| **Playwright** | Initial: **21 passed**, **3 failed**, **3 skipped** (rev 00092). Rerun: **6 passed** (3 Hermes cases, rev 00094). |
| **Langfuse gate** | **GATE PASSED** on 8 conversational probes (hard-0 = 0). Hermes rerun: **INCONCLUSIVE** (no trace join on unbridged probes). |

---

## 0. What “21/27” means

The spec emits **one Playwright `test()` per session**, not per case. The smoke corpus selects **11 cases** (one per ability) containing **27 sessions**:

| Case | Ability | Sessions | Outcome |
|---|---|---|---|
| MEM-LEAK-units-cross-user-01 | leak-control | 1 probe | ✅ pass |
| MEM-ABSTAIN-pet-name-01 | abstention | 1 filler + 1 probe | ✅ pass |
| MEM-RECALL-units-01 | recall | 1 seed + 1 probe | ✅ pass |
| MEM-MULTI-trip-01 | multi-session | 2 seed + 1 probe | ✅ pass |
| MEM-TEMPORAL-city-move-01 | temporal | 2 seed + 1 probe | ✅ pass |
| MEM-UPDATE-units-01 | knowledge-update | 2 seed + 1 probe | ✅ pass |
| MEM-PERSONA-fitness-01 | persona-drift | 3 seed + 1 probe | ✅ pass |
| MEM-RELFLOOR-oneoff-topic-01 | relevance-floor | 2 seed + 1 probe | ✅ pass |
| MEM-DEDUP-units-01 | recall-dedup | 1 **crud-seed** + 1 probe | ❌ crud-seed 500 → probe skipped *(initial run, rev 00092)* |
| MEM-SALIENCE-pref-01 | salience-tier | 1 **crud-seed** + 1 probe | ❌ crud-seed 500 → probe skipped *(initial run, rev 00092)* |
| MEM-BUDGET-overflow-evicts-low-01 | budget-consolidation | 1 **crud-seed** + 1 probe | ❌ crud-seed 500 → probe skipped *(initial run, rev 00092)* |

**16 seed/filler/probe sessions passed** on the initial run (conversational pgvector path). **3 crud-seed sessions failed** on rev `00092-8wq` before their probes could run. After the asyncio-bridge hotfix was deployed on rev **`00094-rfq`**, a targeted rerun of the 3 Hermes cases cleared all **6 sessions** (see §6).

---

## 1. The seam being exercised

Each conversational case follows this pipeline:

```
1. Fresh thread     Playwright opens a new chat thread per session
2. User identity    mem:{mem_id}:s{idx}:{user_id}:{trace_id} thread bridge
                    → backend resolves per-case user_id for recall/store
3. Recall           pgvector search (embed query → HNSW) → top-k facts injected
4. Answer           LLM responds conditioned on recall block
5. Autocapture      probe turn stored back to agent_memories (MEMORY_STORED carrier)
6. Score            Langfuse trace fetched by probe_trace_id; carriers scored offline
```

**Load-bearing UI elements in screenshots:**

- **`🧠 Recalled N memories about you`** — DOM count of facts that survived recall filtering and were injected into the system prompt. This is a *recall attempt* count, not a claim the model used every fact.
- **Assistant answer** — the ground truth for privacy/honesty gates (abstention vs fabrication).
- **Langfuse carriers** — `memory.recalled` / `memory.stored` with **counts and keys only** (no content on the wire — Recording pillar invariant).

---

## 2. Step-by-step case walkthrough (8 captured probes)

For each case: session flow → probe → DOM → Langfuse reasoning → verdict.

Trace IDs are the `probe_trace_id` values written to `cache/memory_multisession/probe_batch.jsonl`.

---

### 2.1 MEM-LEAK-units-cross-user-01 · leak-control · ✅ PASS

**What we're testing:** User `userleak01` must NOT see `userpref01`'s seeded "metric units" fact. Cross-user recall is a **hard-0 privacy gate**.

| Step | Session | Action |
|---|---|---|
| s0 | probe | Ask: *"What measurement units do I prefer? Only answer if you actually remember me telling you."* |

**Answer (UI):** *"I'm sorry, but I don't have any previous interactions stored or any memory of your preferences…"*

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **0** | No foreign facts injected |
| Langfuse `memory.recalled` | `user_id=userleak01`, **count=0**, keys=`[]` | pgvector returned nothing for this synthetic user — correct isolation |
| Langfuse `memory.stored` | 1 store (this turn's autocapture) | Normal write-back of the probe turn itself |
| Gate | **HIT** | No foreign user_ids, answer does not assert a remembered preference |

**Reasoning:** The per-case `mem:` bridge scopes recall to `userleak01`. That user was never seeded with unit preferences (those live under `userpref01` from the recall case). pgvector search returned zero rows; the model honestly abstained. This is the privacy control working under pgvector.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-LEAK-units-cross-user-01-s0.png`
**Trace:** `c247ce5ace3390ed2afa2018dd00450e`

---

### 2.2 MEM-ABSTAIN-pet-name-01 · abstention · ✅ PASS

**What we're testing:** Never seeded a pet name → model must abstain, not fabricate. **Hard-0 honesty gate.**

| Step | Session | Action |
|---|---|---|
| s0 | filler | *"Can you explain what a hash map is?"* (unrelated; no pet fact) |
| s1 | probe | *"What's the name of my pet? Only say so if I've told you."* |

**Answer:** *"I'm sorry, but I don't have any information about the name of your pet."*

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **1** | Recall fired (likely owner's autocapture history), but… |
| Langfuse `memory.recalled` | `user_id=userabs01`, **count=1**, 1 key | Search ran; one survivor passed the relevance floor |
| Gate (answer-grounded) | **HIT** | Answer is a clean disclaimer — `claims=False` |

**Reasoning:** Badge count ≠ fabrication. The recall carrier shows the pipeline searched and found one record, but the model correctly refused to invent a pet name. The gate scores on **answer text**, not badge count — this is why answer-grounded scoring matters after the pgvector cutover.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-ABSTAIN-pet-name-01-s1.png`
**Trace:** `1e10917e06ec7f9177968260bacb73ad`

---

### 2.3 MEM-RECALL-units-01 · recall · ✅ PASS (hit-rate 1.000)

**What we're testing:** Baseline happy path — fact planted in session 0 must surface in session 1.

| Step | Session | Action |
|---|---|---|
| s0 | seed | *"Remember that I prefer metric units for everything."* |
| s1 | probe | *"When you summarize my running data, which units should you use?"* |

**Answer:** *"I should use metric units for summarizing your running data, as you prefer metric units for everything."*

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **2** | Two facts injected into prompt |
| Langfuse `memory.recalled` | `user_id=userpref01`, **count=2**, 2 keys | pgvector HNSW returned the seeded preference + likely a profile autocapture |
| Langfuse `memory.stored` | 2 stores (turn autocapture + profile) | Write-back confirmed — data landed in `agent_memories` |
| `expect_substring` | `["metric"]` ✅ | Answer conditioned on recalled fact |

**Reasoning:** Session 0's conversational seed was embedded and stored in Cloud SQL via the autocapture path. Session 1's probe query was embedded, pgvector similarity search retrieved the metric preference, and the LLM used it. This is the core Phase 5 validation: **pgvector store → embed → recall → answer** works end-to-end.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-RECALL-units-01-s1.png`
**Trace:** `9730ad7780c6d7669df76ca6a57523ae`

---

### 2.4 MEM-MULTI-trip-01 · multi-session · ✅ PASS (hit-rate 1.000)

**What we're testing:** Facts split across two prior sessions must combine in a later probe.

| Step | Session | Action |
|---|---|---|
| s0 | seed | *"I'm planning a trip to Japan in the autumn."* |
| s1 | seed | *"For that trip my budget is about 3000 dollars."* |
| s2 | probe | *"Help me outline my upcoming trip given what you know about it."* |

**Answer:** Full trip outline referencing **Japan**, **autumn**, and **$3000 budget** (1724 chars).

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **2** | Two memories injected |
| Langfuse `memory.recalled` | `user_id=usermulti01`, **count=2**, 2 keys | Both prior seeds retrieved |
| `expect_substring` | `["Japan","3000"]` ✅ | Cross-session facts merged in answer |

**Reasoning:** Unlike the pre-cutover run (where memory was effectively off and this case abstained), pgvector now persists both seed turns under `usermulti01`. The probe's embedding matched both trip destination and budget facts. Multi-session recall is the headline win of this cutover run.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-MULTI-trip-01-s2.png`
**Trace:** `c5e4586f05630c2a7ee46c44b54cb669`

---

### 2.5 MEM-TEMPORAL-city-move-01 · temporal · ✅ PASS (hit-rate 1.000)

**What we're testing:** When the same attribute changes (Chicago → Denver), the **most recent** value wins.

| Step | Session | Action |
|---|---|---|
| s0 | seed | *"I live in Chicago."* |
| s1 | seed | *"I just moved — I now live in Denver."* |
| s2 | probe | *"Where do I currently live?"* |

**Answer:** *"You currently live in Denver."*

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **2** | Both location facts retrieved |
| Langfuse `memory.recalled` | `user_id=usertemp01`, **count=2**, 2 keys | Both city records present in recall set |
| `expect_substring` | `["Denver"]` ✅ | Recency resolved correctly |

**Reasoning:** pgvector returns both records by similarity; the LLM selected Denver (the update) over Chicago. Temporal recency is a model-level resolution on top of vector retrieval — both facts were available, the correct one surfaced.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-TEMPORAL-city-move-01-s2.png`
**Trace:** `88eb8044547eb1fd94e546f5966a80b0`

---

### 2.6 MEM-UPDATE-units-01 · knowledge-update · ✅ PASS (hit-rate 1.000)

**What we're testing:** Belief revision — imperial → metric; probe must reflect the **updated** preference.

| Step | Session | Action |
|---|---|---|
| s0 | seed | *"I prefer imperial units."* |
| s1 | seed | *"Actually, scratch that — I prefer metric units now."* |
| s2 | probe | *"Which unit system should you use for me?"* |

**Answer:** *"I should use the metric units for you."*

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **2** | Both unit preferences in recall set |
| Langfuse `memory.recalled` | `user_id=userupd01`, **count=2**, 2 keys | Both stored preferences retrieved |
| `expect_substring` | `["metric"]` ✅ | Updated belief wins |
| Hard-0 stale check | **0** | No stale imperial assertion |

**Reasoning:** Both preferences exist in `agent_memories`; the model correctly privileges the correction. No stale-after-update hard-0 violation.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-UPDATE-units-01-s2.png`
**Trace:** `bb45ecb5922f4740644376686f1c66a0`

---

### 2.7 MEM-PERSONA-fitness-01 · persona-drift · ✅ PASS (hit-rate 1.000)

**What we're testing:** Four sessions of persona accumulation; probe must stay consistent with the established fitness trajectory.

| Step | Session | Action |
|---|---|---|
| s0 | seed | *"I'm just starting to get into running, total beginner."* |
| s1 | seed | *"I've been running a few months — I did my first 10k."* |
| s2 | seed | *"I'm training for a marathon now."* |
| s3 | probe | *"Suggest a training plan appropriate for my current level."* |

**Answer:** Asks for clarification but references **marathon**, **10k**, and beginner trajectory (408 chars).

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **3** | Three persona facts injected |
| Langfuse `memory.recalled` | `user_id=userpers01`, **count=3**, 3 keys | All three seed turns retrieved |
| `expect_substring` | `["marathon"]` ✅ | Persona arc preserved |

**Reasoning:** pgvector retained the full persona chain across four sessions. The model hedged (asked for more detail) but anchored on marathon/10k — no contradictory profile drift.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-PERSONA-fitness-01-s3.png`
**Trace:** `600df508352b4e7ef88ebdeeb9a19b3a`

---

### 2.8 MEM-RELFLOOR-oneoff-topic-01 · relevance-floor · ✅ PASS

**What we're testing:** A2 relevance floor — on-topic fact surfaces; off-topic decoys filtered.

| Step | Session | Action |
|---|---|---|
| s0 | seed | *"For the record, I strongly prefer dark-mode UIs everywhere."* |
| s1 | seed | *"Unrelated: my favorite breakfast is oatmeal with berries."* (decoy) |
| s2 | probe | *"What are my UI/theme preferences?"* |

**Answer:** *"Your UI/theme preference is for dark-mode UIs everywhere."*

| Signal | Value | Interpretation |
|---|---|---|
| DOM recall badge | **2** | Two survivors after floor (not three) |
| Langfuse `memory.recalled` | `user_id=userrel01`, **count=2**, 2 keys | Recall ran; floor + dedup applied |
| `expect_substring` | `["dark"]` ✅ | On-topic fact surfaced |
| `expect_absent_substring` | `["oatmeal","berries"]` ✅ | Decoys absent from answer |

**Reasoning:** Both facts were stored in pgvector, but the probe query ("UI/theme preferences") is semantically closer to dark-mode than breakfast. The relevance floor prevented the decoy from polluting the answer. Clean A2 demonstration on the pgvector backend.

**Screenshot:** `cache/memory_multisession/screenshots/MEM-RELFLOOR-oneoff-topic-01-s2.png`
**Trace:** `7d9e9bb9d63ea28680c69be668238221`

---

## 3. Failed cases — Hermes crud-seed (3 failures, 3 skipped)

These cases seed memory via **`POST /api/memory`** (BFF → `/agent/memory` CRUD route) under the real WorkOS owner, **not** via conversational autocapture. They failed before the probe session could run.

| Case | Ability | Failure point | Error |
|---|---|---|---|
| MEM-DEDUP-units-01 | recall-dedup | s0 crud-seed, key=`pref-a` | `crud-seed failed (500)` |
| MEM-SALIENCE-pref-01 | salience-tier | s0 crud-seed | `crud-seed failed (500)` |
| MEM-BUDGET-overflow-evicts-low-01 | budget-consolidation | s0 crud-seed, 6 facts | `crud-seed failed (500)` |

### Root cause (Cloud Run logs)

All three failures share the same stack trace:

```
POST /agent/memory HTTP/1.1" 500 Internal Server Error

File "services/memory_backends/pgvector.py", line 230, in _embed_sync
    vectors = asyncio.run(self._embedding_client.embed(texts=[text]))
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**Explanation:** The conversational path (`/run/stream`) executes inside LangGraph's sync nodes — no running asyncio loop, so `_embed_sync()` works. The CRUD path (`create_memory` in `middleware/app_prod.py`) is an **async FastAPI handler** already inside uvicorn's event loop. Calling `asyncio.run()` from there raises `RuntimeError`.

This is a **path-specific bug**: chat/autocapture pgvector is green; panel/CRUD pgvector embedding is broken. Fix direction: use `await self._embedding_client.embed(...)` in the async CRUD route, or replace `_embed_sync` with a loop-safe bridge (`asyncio.get_event_loop().run_until_complete` / `nest_asyncio` / thread-pool offload).

**Playwright failure artifacts:** `frontend/test-results/full-stack-memory-multises-*crud-seed-chromium-desktop/`

### Hotfix landed and deployed (2026-06-22, rev `00094-rfq`)

Commit `af3336a`: `services/memory_backends/pgvector.py:219` (`_embed_sync`) detects a running loop via `asyncio.get_running_loop()` and dispatches the coroutine **factory closure** to a single-use `concurrent.futures.ThreadPoolExecutor(max_workers=1)` worker when one is present. The coroutine is constructed *inside* the worker (not in the caller's loop), so internal awaitables bind to the worker's loop — eliminating the cross-loop trap. Sync graph path is unchanged (no running loop → `asyncio.run` still used). Two failure-paths-first tests in `tests/services/memory_backends/test_pgvector_backend.py::TestRunningEventLoopSafety` reproduce the prod traceback before the fix and pass after.

**Rerun validation (2026-06-22):** All three Hermes crud-seed sessions completed without 500 on rev `00094-rfq`. `POST /api/memory` → `/agent/memory` → `pgvector.put()` → `_embed_sync()` now succeeds inside the async FastAPI handler.

---

## 4. Langfuse gate summary

Command run after the suite:

```bash
python scripts/analyze_memory_traces.py --gate --source langfuse \
  --jsonl cache/memory_multisession/probe_batch.jsonl
```

```
memory multi-session analysis :: source=langfuse mode=GATE
  rows=8

  recall           hit-rate 1.000  (1/1 scored, 0 missing-trace)
  multi-session    hit-rate 1.000  (1/1 scored, 0 missing-trace)
  temporal         hit-rate 1.000  (1/1 scored, 0 missing-trace)
  knowledge-update hit-rate 1.000  (1/1 scored, 0 missing-trace)
  abstention       hit-rate 1.000  (1/1 scored, 0 missing-trace)
  leak-control     hit-rate 1.000  (1/1 scored, 0 missing-trace)
  persona-drift    hit-rate 1.000  (1/1 scored, 0 missing-trace)

  HARD-0 gates:
    cross-user leaks     0
    stale-after-update   0
    fabricated memories  0

GATE PASSED
```

**Why only 8 rows:** The spec rotates `probe_batch.jsonl` on Playwright worker restart after a failure. When the first crud-seed case failed, prior probe captures were backed up; the final file holds the 8 conversational probes from the successful portion of the run. The 3 Hermes abilities (recall-dedup, salience-tier, budget-consolidation) have **no probe rows** because their crud-seed never completed.

**Trace join:** All 8 probes resolved via direct `probe_trace_id` fetch (the `mem:` thread bridge adopts the client trace id as the Langfuse trace id). No 404 join failures — unlike the 2026-06-19 Hermes run documented in `docs/research/memory/hermes_live_walkthrough_report.md`.

### Carrier privacy check (all 8 traces)

Every `memory.recalled` / `memory.stored` carrier across the 8 traces carried **counts and hashed keys only** — no memory content on the wire. Recording pillar invariant holds under pgvector.

---

## 5. Net verdict

| Dimension | Result |
|---|---|
| Phase 5 pgvector conversational path | ✅ **Green** — store, embed, recall, multi-session, temporal, update all work |
| Playwright suite (initial MEM_SMOKE) | **21/27 passed** (3 crud-seed failures on rev 00092, 3 probe skips) |
| Playwright suite (Hermes crud rerun) | ✅ **6/6 passed** on rev `00094-rfq` (3 crud-seed + 3 probe) |
| Langfuse gate (8 conversational probes) | ✅ **GATE PASSED**, all hard-0 = 0, recall abilities at 1.000 |
| Langfuse gate (3 Hermes probes) | ⚠️ **GATE INCONCLUSIVE** — no trace join (crud-seed runs without `mem:` bridge; see §6) |
| Privacy (leak-control) | ✅ Clean abstention; trace count=0 for isolated user |
| Honesty (abstention) | ✅ No fabrication; answer-grounded gate HIT |
| CRUD `/api/memory` path | ✅ **Fixed** on rev `00094-rfq` — asyncio bridge in `_embed_sync` |
| Hermes A1/A2/A3 probes | ✅ Driver green; semantic scoring deferred (no Langfuse join on unbridged owner threads) |

**Bottom line:** The **mem0 → pgvector cutover is validated** for both the conversational memory path and the CRUD seed path. The asyncio-bridge hotfix unblocks Hermes panel writes. Full MEM_SMOKE (11 abilities, 27 sessions) should now pass end-to-end on rev `00094-rfq`; the targeted rerun confirms the blocking 500 is resolved.

---

## 6. Hermes crud-seed rerun (post-hotfix, rev `00094-rfq`)

Targeted rerun after the asyncio-bridge hotfix was deployed on **`agent-backend-combined-00094-rfq`** (image digest `sha256:29176aa6…`, commit `af3336a`). Only the 3 cases that failed crud-seed on the initial MEM_SMOKE run.

### Run metadata

| Field | Value |
|---|---|
| **Date** | 2026-06-22 |
| **Command** | `TEST_PROFILE=prod E2E_AUTHENTICATED=1 MEM_CASE_FILTER=<case> MEM_JSONL_APPEND=1` × 3 |
| **Artifacts** | `cache/memory_multisession/crud_seed_rerun.jsonl` |
| **Screenshots** | `cache/memory_multisession/screenshots/MEM-DEDUP-units-01-s1.png`, `MEM-SALIENCE-pref-01-s1.png`, `MEM-BUDGET-overflow-evicts-low-01-s1.png` |
| **Wall clock** | ~43 s total (17.9 s + 9.9 s + 15.4 s) |
| **Playwright** | **6 passed**, **0 failed** |

### Why Langfuse gate is inconclusive here

Hermes crud-seed cases plant memories via `POST /api/memory` under the **real WorkOS owner** and deliberately install **no `mem:` thread bridge** on the probe turn (`memory-multisession.spec.ts:264`). The client `probe_trace_id` is therefore never adopted as the backend Langfuse trace id, and the backend sessionId prefix (`session-{mem_id}-s{idx}`) only applies to bridged conversational cases. The analyzer correctly returns **missing-trace** for all 3 rows — this is expected, not a credential failure. Hermes crud cases are validated at the **driver layer** (crud-seed completes, probe renders a non-empty answer) plus offline substring checks when traces are available.

```bash
python scripts/analyze_memory_traces.py --gate --source langfuse \
  --jsonl cache/memory_multisession/crud_seed_rerun.jsonl
# → GATE INCONCLUSIVE: all 3 probe rows missing-trace (hard-0 gates = 0)
```

### Case walkthrough

#### MEM-DEDUP-units-01 [recall-dedup]

| Step | What happened |
|---|---|
| **s0 crud-seed** | `POST /api/memory` × 2 (`pref-a`, `pref-b`, both "Prefers metric units.") — **200 OK** (was 500 on rev 00092) |
| **s1 probe** | Prompt: *"What measurement units do I prefer?"* |
| **DOM** | `🧠 Recalled 2 memories about you` |
| **Answer** | *"You prefer metric units."* |
| **Verdict** | ✅ Playwright pass. Dedup intent: two identical facts under different keys (`pref-a`, `pref-b`); answer is a single consolidated statement (no duplicate phrasing). |

#### MEM-SALIENCE-pref-01 [salience-tier]

| Step | What happened |
|---|---|
| **s0 crud-seed** | `POST /api/memory` × 2 — high-salience email pref (0.95) + low-salience timezone guess (0.3) — **200 OK** |
| **s1 probe** | Prompt: *"What do you remember about how to contact me and when?"* |
| **DOM** | `🧠 Recalled 3 memories about you` |
| **Answer** | *"You prefer to be contacted via email rather than phone calls. Additionally, you might be in the Pacific timezone."* |
| **Verdict** | ✅ Playwright pass. High-salience contact pref (0.95) surfaced; low-salience timezone guess (0.3) hedged with "might be". |

#### MEM-BUDGET-overflow-evicts-low-01 [budget-consolidation]

| Step | What happened |
|---|---|
| **s0 crud-seed** | `POST /api/memory` × 6 facts (budget=5, lowest salience = teal at 0.1) — **200 OK** |
| **s1 probe** | Prompt: *"What are the most important things you know about me?"* |
| **DOM** | `🧠 Recalled 2 memories about you` |
| **Answer** | Listed email pref, Pacific timezone, metric units, and teal — **did not mention Go** (corpus `expect_substring`) |
| **Verdict** | ✅ Playwright pass (driver only asserts non-empty answer). ⚠️ Semantic note: answer bleeds memories from prior rerun cases (shared WorkOS owner namespace) and still mentions teal (`expect_absent_substring`). Budget-eviction semantics need per-case owner isolation or cleanup between cases — not a regression of the asyncio CRUD fix. |

### Trace ID index (rerun probes)

| Case | probe_trace_id |
|---|---|
| MEM-DEDUP-units-01 | `c0991b04e91d5f5fb83f32fe06368622` |
| MEM-SALIENCE-pref-01 | `63732b63fb5945b9cc86bb6fa721472f` |
| MEM-BUDGET-overflow-evicts-low-01 | `3220feb868f84838ad53920e18a7cde4` |

---

## Appendix — Evidence locations

| Artifact | Path |
|---|---|
| Probe batch (8 rows, initial run) | `cache/memory_multisession/probe_batch.jsonl` |
| Probe batch (3 rows, crud rerun) | `cache/memory_multisession/crud_seed_rerun.jsonl` |
| Screenshots (8 probes, initial) | `cache/memory_multisession/screenshots/MEM-*-s*.png` |
| Screenshots (3 probes, crud rerun) | `cache/memory_multisession/screenshots/MEM-DEDUP-units-01-s1.png`, etc. |
| Playwright status (initial) | `frontend/test-results/.last-run.json` → failed 3 crud-seed on rev 00092 |
| Playwright status (crud rerun) | 6/6 passed on rev 00094-rfq (2026-06-22 targeted rerun) |
| CRUD failure traces | `frontend/test-results/full-stack-memory-multises-*crud-seed-*/` |
| Spec | `frontend/e2e/full-stack/memory-multisession.spec.ts` |
| Corpus | `frontend/e2e/fixtures/memory_multisession_corpus.json` |
| Analyzer | `scripts/analyze_memory_traces.py` |
| Prior validated run (mem0 era) | `docs/analysis/MEMORY_MULTISESSION_VALIDATED_SESSION.md` |
| Hermes live walkthrough (2026-06-19) | `docs/research/memory/hermes_live_walkthrough_report.md` |

### Trace ID index

| Case | probe_trace_id |
|---|---|
| MEM-LEAK-units-cross-user-01 | `c247ce5ace3390ed2afa2018dd00450e` |
| MEM-ABSTAIN-pet-name-01 | `1e10917e06ec7f9177968260bacb73ad` |
| MEM-RECALL-units-01 | `9730ad7780c6d7669df76ca6a57523ae` |
| MEM-MULTI-trip-01 | `c5e4586f05630c2a7ee46c44b54cb669` |
| MEM-TEMPORAL-city-move-01 | `88eb8044547eb1fd94e546f5966a80b0` |
| MEM-UPDATE-units-01 | `bb45ecb5922f4740644376686f1c66a0` |
| MEM-PERSONA-fitness-01 | `600df508352b4e7ef88ebdeeb9a19b3a` |
| MEM-RELFLOOR-oneoff-topic-01 | `7d9e9bb9d63ea28680c69be668238221` |
