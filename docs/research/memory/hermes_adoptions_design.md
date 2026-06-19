# Hermes / memory-os Adoptions — Memory Pipeline Design

> **Status:** A1/A2/A3 **IMPLEMENTED + validated** (uncommitted, branch `feat/memory-layer-wiring`, 2026-06-19); live cloud run done + **analyzer gate PASSED (trustworthy)** after the join + answer-grounded-gate fixes (§10.6). All P0/P1 follow-ups + the P2 safety-floor/recency-tie-break **RESOLVED**. The autocapture write-back **enable-policy is now machine-ENFORCED** (§10.7) — a passing frozen-test-split certificate is required, not just the flag; flipping the flag alone no longer stores. A4 deferred (seam only). Remaining: a *real* calibration certificate (gated on the Stage 0→6 eval ladder) + commit. **Date:** 2026-06-19.
> **Companion to:** [memory_layer_wiring.plan.md](../../plans/memory_layer_wiring.plan.md) (the live pipeline this extends) and [memory_and_chat_history_best_practices_2026.md](../memory_and_chat_history_best_practices_2026.md) (the 2026 best-practice ground).
> **Source of the comparison:** external research on the **NousResearch Hermes Agent** (bounded `MEMORY.md`/`USER.md` + FTS5 session search) and the community **memory-os** 7-layer system built on Hermes (Qdrant hybrid, trust-scored facts, surgical injection). See §9 Sources.
>
> **Scope of this doc:** the four Hermes/memory-os ideas the trade-off analysis marked Adopt / Consider / Defer. It does **not** re-open anything marked Reject (Qdrant vector engine, auto-wiki, eager mid-turn writes, FTS5 — already covered by Mem0 + the checkpointer/thread sidebar). **§10 (appended 2026-06-19) is the implementation status, critical review, decisions taken, and remaining-TODO ledger.**

---

## 0. TL;DR — the four adoptions and where they bind

| # | Idea (origin) | Verdict | Binds onto | New infra? |
|---|---|---|---|---|
| **A1** | **Bounded memory budget + forced consolidation** (Hermes caps) | ✅ **Adopt** | `MemoryAutoCaptureService` write-back path + a new consolidation pass | **None** — pure logic over `LongTermMemoryService` |
| **A2** | **Relevance-gated + deduped recall injection** (memory-os L5/`pre_llm_call` hook) | ✅ **Adopt (lightweight)** | `components/memory_context.py::render_recall_block` + `should_recall` | **None** — scoring over existing `search()` results |
| **A3** | **Ground-truth hierarchy** — authoritative vs. speculative (memory-os L7 `SOUL.md`) | 🟡 **Consider** | `TypedMemory.salience` (exists) → surfaced in `render_recall_block` | **None** — render-only |
| **A4** | **Trust-scored facts with feedback loop** (memory-os L3) | 🟡 **Defer** | future procedural memory from reflexion critiques | deferred — needs feedback signal |

**One unifying observation.** Your architecture is *already ahead* of both Hermes variants on the things that are expensive to retrofit — substrate-swappability (the `MemoryBackend` Protocol), multi-tenant safety (`memory_subject` cross-user-leak guard), and auditability (content-free `MEMORY_RECALLED`/`MEMORY_STORED` carriers). The two real gaps Hermes exposes (A1, A2) are both **discipline on top of storage**, not storage itself — so neither needs new infrastructure. A3/A4 are about **provenance**, which you have the field for (`salience`) but don't yet surface or earn.

---

## 1. Where these bind in the current pipeline

The live pipeline (verified against code 2026-06-19):

```
                            ┌──────────────────────────────────────────────────┐
                            │            AGENT RUN (LangGraph hot path)          │
                            └──────────────────────────────────────────────────┘
  user turn ─▶ route_node ───────────────────────────────────────────▶ call_llm / supervisor / fanout
                  │                                                          (READERS of recalled_memories)
                  │  should_recall(enabled, user_id, memoized)  ◀── A2 gates HERE
                  │      └─ LongTermMemoryService.search(user_id, q, top_k)
                  │      └─ render_recall_block(records)  ◀── A2 dedup + A3 provenance render HERE
                  │      └─ memoize on recalled_memories_task_id (1 search / run)
                  ▼
            reasoning_recap_node  (PH_COMPLETION)
                  │  _maybe_store_memory → build_store_payload → store(user_id, task_id, payload)
                  │      └─ MEMORY_STORED carrier (content-free)
                  ▼
            ════════════════ run ends ════════════════
                  │
                  ▼  (OFF the hot path)
            MemoryAutoCaptureService.schedule(thread_id, ...)   debounced per thread
                  │  extractor.extract(messages) → [TypedMemory(type, content, key, salience)]
                  │  SHADOW: emit MEMORY_STORED(proposed_only=True), store nothing
                  │  WRITE-BACK (gated): store(user_id, key, {text}, {type, salience})  ◀── A1 budget+consolidate HERE
                  ▼
            LongTermMemoryService  ──▶  MemoryBackend Protocol  ──▶  { InMemory | Mem0 (durable) }
```

The four adoptions touch exactly three files, all framework-clean (I-3/I-4/I-5 hold):
- **A1** → `services/memory_autocapture.py` (write-back path) + a new `consolidate()` on `services/long_term_memory.py` (or a sibling helper).
- **A2 / A3** → `components/memory_context.py` (`render_recall_block`, `should_recall`) — pure functions, deterministic, zero-flake.
- **A4** → deferred; design seam only.

No `orchestration/` logic changes (the nodes stay thin OBP-3 wrappers); no new backend; no new dependency.

---

## 2. A1 — Bounded memory budget + forced consolidation  ✅ ADOPT

### 2.1 The Hermes idea, precisely

Hermes' `MEMORY.md` (~800 tokens) and `USER.md` (~500 tokens) have **hard character caps**. When the agent tries to write past the cap, the memory tool **returns an error and forces the agent to consolidate or delete in the same turn**. The cap is not a limitation — it is the consolidation *trigger*. This is what keeps Hermes' recall block self-limiting, readable in full, and free of the stale-fact accumulation that an unbounded vector store suffers.

### 2.2 The gap it fixes for us

Your store path is **unbounded**. v1 stores one record per `task_id`; autocapture write-back (when it flips on) stores one per proposed `TypedMemory`. Nothing ever caps or reconciles. Your own research (§3 of the best-practices doc) names this exact pitfall — "auto-memory lists drift stale; let users prune" — and your plan already commits to **ADD-only + a consolidation pass**. Hermes gives that commitment a concrete **trigger and budget** rather than a vague "periodic job."

### 2.3 Design — per-(user, type) budget with consolidation on overflow

Adopt a **per-(user_id, type) item budget**, not a token budget (your backend stores discrete records, not a single doc — an item count is the natural, deterministic unit and avoids a tokenizer dependency in `services/`).

```
                         WRITE-BACK PATH (MemoryAutoCaptureService, write_back ON)
                         ─────────────────────────────────────────────────────────
   extractor proposes
   TypedMemory item
   (type, content, key,
    salience)
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │ store(user_id, key, {text}, {type, salience})                        │
   └─────────────────────────────────────────────────────────────────────┘
        │
        ▼
   count_for(user_id, type)  ──  N items of this type for this user
        │
        ├── N ≤ BUDGET[type] ──────────────▶  done (no consolidation)
        │
        └── N >  BUDGET[type] ──────────────▶  CONSOLIDATE(user_id, type)
                                                    │
                                                    ▼
              ┌──────────────────────────────────────────────────────────┐
              │  consolidate(user_id, type)  — deterministic, no LLM (v1)  │
              │  1. load all items of (user_id, type)                      │
              │  2. drop exact-duplicate `text` (keep highest salience)    │
              │  3. if still > BUDGET: evict lowest (salience, then oldest) │
              │     until == BUDGET                                         │
              │  4. emit MEMORY_CONSOLIDATED carrier (counts only)         │
              └──────────────────────────────────────────────────────────┘
```

**Budgets (starting values, tunable):**

| Type | Budget (items / user) | Rationale |
|---|---|---|
| `semantic` | 50 | Stable user facts — bounded but generous; the recall top-k (3) is the real filter. |
| `episodic` | 30 | Past-task summaries decay in usefulness; cap tighter. |
| `procedural` | 10 | Rules should be few and high-signal (A4 territory). |

**Why deterministic (no LLM) in v1.** Hermes uses the *agent* to consolidate in-turn; that's an LLM call on the hot path — exactly what your background+shadow discipline avoids. The deterministic version (dedup-then-evict-by-salience) is cheaper, zero-flake, and testable as an L1 unit. An LLM-merge consolidation (true semantic dedup, "mornings" → "afternoons" reconciliation) is a **v1.5 upgrade** behind the same `consolidate()` seam — slot it where step 2 is, gated by its own flag, never on the hot path.

### 2.4 Mechanism / contract

Add to `services/long_term_memory.py` (framework-clean, I-4 holds):

```python
def __init__(self, backend, *, budgets: dict[str, int] | None = None): ...  # budgets injected
def store(self, user_id, key, payload, metadata=None) -> ConsolidationOutcome | None: ...  # consolidates on overflow
def count(self, user_id: str, *, mem_type: str | None = None) -> int: ...
def consolidate(self, user_id: str, mem_type: str, *, budget: int) -> ConsolidationOutcome: ...
#   ConsolidationOutcome(kept: int, evicted: int, deduped: int)  — counts only, frozen
```

**Enforcement point — the service `store()` path, not just autocapture (decided during implementation, 2026-06-19).** The budget map is injected into `LongTermMemoryService` at the composition root (`AgentRuntimeSettings` → `LongTermMemoryService(backend, budgets=...)`). `store()` itself consolidates the record's type on overflow (`_consolidate_on_overflow`) and **returns the `ConsolidationOutcome`** (or `None`). This is stronger than gating it inside `MemoryAutoCaptureService`: **every** writer is now bounded — autocapture write-back, the `/agent/memory` CRUD route, and the user-facing memory panel — so no path can grow the store unbounded. The service stays governance-free (it returns the outcome; it does not emit carriers); `MemoryAutoCaptureService` emits the `MEMORY_CONSOLIDATED` carrier from the returned outcome (the run-trace path). Shadow autocapture stores nothing → `store()` is never called → nothing consolidates. A record with no `type` (the v1 deterministic store) has no budget key → never consolidated (byte-identical to today). Four-layer compliance preserved: budget logic is in `services/` (I-4 framework-clean, I-5 no `components/` import), injected not hardcoded (Checklist 2).

### 2.5 Governance — a new content-free carrier

Consolidation is a runtime decision that *deletes* memory, so it must leave an honest carrier (Validation pillar — a silent eviction is exactly the swallowed-failure class the audit flags):

- New **non-required** `EventType.MEMORY_CONSOLIDATED`, details `{user_id, type, kept, evicted, deduped}` — **never content**. Maps to a BlackBox span like the existing memory carriers.
- Like `MEMORY_RECALLED`/`MEMORY_STORED`, it is **enrichment, not a `default_spec()` requirement** (memory is flag-gated; requiring it would false-positive every non-memory run — the GG-4 class §"Two compliance rules" in the wiring plan already establishes). The drift-guard stays green by construction (a new non-required member doesn't change any requirement tuple).

### 2.6 Trade-offs

| | Adopt (this design) | Don't (status quo: unbounded) |
|---|---|---|
| Stale-fact accumulation | bounded; evicted by salience | grows forever; recall noise rises |
| Cost | one extra backend `count` + occasional `consolidate` (off hot path) | none |
| Determinism | full (L1-testable) | n/a |
| User-visible deletion | carrier + (Phase-3 panel already lets users prune) | only manual panel pruning |
| Risk | evicting a fact the user still wanted | — |
| Mitigation | salience-ordered eviction + generous budgets + the editable panel is the escape hatch | — |

**Verdict: adopt deterministic v1 now (cheap, fixes the named gap), design the LLM-merge `consolidate()` seam for v1.5.**

---

## 3. A2 — Relevance-gated + deduped recall injection  ✅ ADOPT (lightweight)

### 3.1 The memory-os idea, precisely

memory-os's `pre_llm_call` hook retrieves candidate context, then **gates by a relevance threshold** and **dedups per-session** before injecting — "surgical context injection." It does this over a Qdrant hybrid score. The *idea* (relevance floor + dedup) is separable from the *substrate* (Qdrant): you can apply both to the records your existing `search()` already returns.

### 3.2 The gap it fixes for us

`render_recall_block` today injects **all** top-k records unconditionally — whatever `LongTermMemoryService.search()` returns, up to the limit, every one becomes a bullet in `additional_instructions`. With the `InMemoryBackend` that's naive substring matching; with Mem0 it's vector similarity but **with no floor** — a weakly-related memory still gets injected and crowds the prompt. Your best-practices doc §3: *"a lean retrieved context beats the full history."*

### 3.3 Design — a relevance floor + dedup in `render_recall_block`

```
   LongTermMemoryService.search(user_id, query, top_k)
        │  returns [MemoryRecord]  (Mem0 attaches a similarity score in metadata)
        ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │ render_recall_block(records, *, min_relevance=0.0, query=None)     │
   │                                                                    │
   │   for record in records:                                           │
   │     score = record.metadata.get("score")     # Mem0 hybrid score   │
   │     ── A2 RELEVANCE FLOOR ────────────────────────────────         │
   │     if score is not None and score < min_relevance: skip           │
   │     ── A2 DEDUP ──────────────────────────────────────────         │
   │     if normalize(text) in seen: skip        # exact-text dedup      │
   │     seen.add(normalize(text))                                       │
   │     ── A3 PROVENANCE (see §4) ────────────────────────────         │
   │     bullet = mark_authoritative(text, salience)                    │
   │     lines.append(bullet)                                           │
   │                                                                    │
   │   return "" if only the header survives  (byte-identical no-op)    │
   └──────────────────────────────────────────────────────────────────┘
```

**Key design constraints (preserve current invariants):**
- **Backward-compatible default.** `min_relevance=0.0` reproduces today's behavior exactly (no record has a score `< 0.0`, so nothing is skipped). A backend that attaches **no** score (InMemory) is unaffected — the floor only applies when a score is present. So dev/tests stay byte-identical; the floor only bites against Mem0 in prod.
- **Dedup is exact-text, not embedding.** Embedding-similarity dedup belongs in A1's consolidation (write side), not recall (read side) — doing it on every recall would re-embed on the hot path. Read-side dedup is the cheap exact-match guard against the same fact stored under two keys.
- **Still pure & deterministic.** No new I/O, no LLM. The score is read from metadata the backend already returns. L1-testable, zero-flake.

### 3.4 Where the threshold lives & how it's tuned

- `min_relevance` is a field on `AgentRuntimeSettings` (default `0.0` = off), injected through `route_node` into `render_recall_block`. Flipping it on is a config change on a `--tag` revision, mirroring `MEMORY_ENABLED`.
- **Tuning is an eval question, not a guess.** The `memory_recall` `eval_capture` target already records every recall. Add `recalled_count` + (when present) the min/max score to that record, then the `agentsframework-eval-probe` methodology calibrates the floor against a small gold set (recall-precision vs. recall-completeness) before prod flip. Start conservative (floor that drops only the clearly-weak tail, e.g. ~0.3 on Mem0's 0–1 cosine), shadow-measure, then raise.

### 3.5 Trade-offs

| | Adopt | Don't |
|---|---|---|
| Prompt noise from weak matches | filtered at a floor | every top-k injected |
| Hot-path cost | ~zero (read a score already returned) | zero |
| Substrate coupling | none — score is optional metadata | n/a |
| Risk | floor too high → drops a useful memory (recall miss) | floor absent → noise |
| Mitigation | default-off, eval-calibrated, shadow-first | — |

**Verdict: adopt the seam now (default-off, backward-compatible), calibrate the floor via the eval probe before flipping on in prod.**

---

## 4. A3 — Ground-truth hierarchy (authoritative vs. speculative)  🟡 CONSIDER

### 4.1 The memory-os idea, precisely

memory-os Layer 7 uses `SOUL.md`/`rulebook.md` to **mark injected memory as authoritative** — telling the agent "trust this, don't re-derive or re-query it." It's a provenance signal on the *injected* memory, distinguishing ground truth from speculation so the agent weights them differently.

### 4.2 What you already have (and don't surface)

`TypedMemory` already carries `salience: float ∈ [0,1]` (`components/schemas.py:267`), and autocapture write-back already stores it in `metadata={"type", "salience"}`. **You have the provenance field — you just throw it away at render time.** `render_recall_block` renders every record as an identical `- {text}` bullet; the agent can't tell a high-salience user-stated fact from a low-salience inferred guess.

### 4.3 Design — salience tiers in the rendered block

Surface salience as a **two-tier (or three-tier) prefix** in `render_recall_block`, so the LLM sees the provenance the same way Hermes' agent sees "authoritative":

```
   Relevant context you remember about this user:
   [confirmed] Prefers metric units                  ← salience ≥ 0.8  (authoritative)
   [confirmed] Works in fintech
   [inferred]  May prefer morning meetings            ← salience < 0.8  (speculative)
```

- Thresholds (`authoritative ≥ 0.8`) live in settings, injected — not hardcoded.
- A record with **no** salience metadata (the v1 deterministic store writes none) renders **unmarked** — backward-compatible, exactly today's bullet. Only typed-autocapture records (which carry salience) get a tier prefix.
- This is **render-only** — no store change, no new field, no backend change. Pure addition to the existing pure function.

### 4.4 Why "Consider," not "Adopt"

Two honest reasons to hold rather than ship immediately:
1. **Salience is only meaningful once autocapture write-back is on.** Today write-back is **shadow** (stores nothing) — so in prod there are *no* salience-bearing records yet. Shipping the render tier now decorates an empty set. It should land **with or just after** the autocapture enable-policy flips (the §Track-2 calibration gate).
2. **Salience calibration is unproven.** The extractor's salience scores haven't been validated against human judgment — a `[confirmed]` tier built on a miscalibrated score *mis-marks* provenance, which is worse than no mark. The autocapture calibration gate (κ ≥ 0.60, store-precision ≥ 0.90) should include a salience-agreement check before the tiers are trusted.

**Verdict: design the render seam now (it's three lines in a pure function), gate shipping it on (a) autocapture write-back being live and (b) the calibration gate covering salience agreement.** It rides A1/A2's file with zero marginal cost.

---

## 5. A4 — Trust-scored facts with feedback loop  🟡 DEFER

### 5.1 The memory-os idea, precisely

memory-os Layer 3 stores facts with a **trust score that improves from feedback** — an automatic loop trains confidence so the agent distinguishes high-confidence from speculative knowledge over time. This is salience that *learns*, versus A3's salience that's *assigned once at extraction*.

### 5.2 Why defer (and what it's waiting on)

This aligns precisely with your **procedural-memory-from-reflexion v2** plan (the wiring plan's "procedural → builds on reflexion critiques"). The blocker is structural, not effort: **you have no feedback signal wired into memory yet.** A trust loop needs an observation like "a recalled memory led to a good/bad outcome" — and the natural source is the **reflexion critique** (`reflections` in state) and/or the **GoalJudge outcome**, neither of which currently feeds back to the memory record that influenced the run.

### 5.3 Design seam (so v2 is wiring, not greenfield)

Leave exactly one seam so this is a later *activation*, mirroring how the whole memory layer was orphaned-then-wired:
- `MemoryRecord.metadata` already free-form — reserve a `trust: float` key (distinct from `salience`: salience = extraction confidence, trust = outcome-earned confidence).
- A future `LongTermMemoryService.reinforce(user_id, key, delta)` updates `trust` — called from a post-run hook that correlates which `recalled_memories` keys were in-context for a run the GoalJudge scored well/poorly.
- Recall ordering and the A2 floor can then blend `salience` and `trust`.

**Verdict: defer. Reserve the `trust` metadata key + `reinforce()` signature now (documentation only), wire it in v2 when procedural memory + a reflexion→memory feedback edge are in scope.** Do **not** build the loop speculatively — the wiring plan's discipline is "activate when the upstream signal exists."

---

## 6. Consolidated architecture (after A1 + A2 + A3; A4 reserved)

```
 ┌───────────────────────────────────────────────────────────────────────────────────┐
 │                                   READ SIDE (hot path)                              │
 │                                                                                     │
 │  route_node ─ should_recall ─▶ search(user_id, q, top_k) ─▶ render_recall_block(    │
 │                                                              records,                │
 │                                            A2 ──────────────  min_relevance,         │  ← relevance floor
 │                                            A3 ──────────────  authoritative_at )     │  ← salience tiers
 │                                  └─ exact-text dedup (A2)                            │
 │                                  └─ memoize / run                                   │
 └───────────────────────────────────────────────────────────────────────────────────┘
                                          │
 ┌───────────────────────────────────────────────────────────────────────────────────┐
 │                              WRITE SIDE (off hot path)                               │
 │                                                                                     │
 │  MemoryAutoCaptureService (write-back) ─▶ store(...) ─▶ count(user_id, type)         │
 │                                                          │                          │
 │                                       A1 ────────────────┴─▶ consolidate() on        │  ← budget + evict
 │                                                              overflow                │
 │                                                              └─ MEMORY_CONSOLIDATED  │  ← new content-free carrier
 │                                                                                     │
 │  A4 (DEFERRED): reinforce(user_id, key, Δtrust) ◀── reflexion/GoalJudge outcome      │  ← reserved seam
 └───────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
            LongTermMemoryService ──▶ MemoryBackend Protocol ──▶ { InMemory | Mem0 }
                 + count()  (A1)
                 + consolidate()  (A1)
                 + reinforce()  (A4, reserved)
```

**Layer cleanliness (test-enforced, all preserved):**
- A1/A4 live in `services/` — framework-clean (I-4), no `components/` import (I-5).
- A2/A3 live in `components/memory_context.py` — no `langgraph`/`langchain`/`AgentState` (I-3), pure & deterministic.
- `orchestration/` nodes stay thin OBP-3 wrappers (I-7) — they pass the new settings through, no logic.
- New `EventType.MEMORY_CONSOLIDATED` is non-required (no `default_spec()` change → drift-guard green).

---

## 7. Phasing & flags

All default-OFF, mirroring `MEMORY_ENABLED` / `T3_FANOUT_ENABLED` discipline (prod parity until a `--tag` revision flips them).

| Phase | Ships | Flag(s) | Gated on |
|---|---|---|---|
| **H1** | A2 relevance-floor + dedup seam (default `min_relevance=0.0` = off) | `MEMORY_RECALL_MIN_RELEVANCE` | nothing — backward-compatible; flip after eval-probe calibration |
| **H2** | A1 budget + deterministic `consolidate()` + `MEMORY_CONSOLIDATED` carrier | `MEMORY_BUDGET_*` (per type) | autocapture **write-back** being on (nothing to consolidate in shadow) |
| **H3** | A3 salience tiers in `render_recall_block` | `MEMORY_AUTHORITATIVE_AT` | (a) write-back live, (b) calibration gate covers salience agreement |
| **v1.5** | A1 LLM-merge consolidation (semantic dedup) | `MEMORY_LLM_CONSOLIDATE` | H2 live + a consolidation eval |
| **v2** | A4 trust feedback loop (`reinforce`) | `MEMORY_TRUST_FEEDBACK` | procedural memory + reflexion→memory edge in scope |

**Build order recommendation:** H1 first (independent, backward-compatible, immediately useful once Mem0 scores are flowing), then H2 (needs write-back), then H3 (rides H2's calibration). H1 is the cheapest highest-leverage change — it cuts recall noise with no dependency on the autocapture enable-policy.

---

## 8. What we are NOT doing (rejected, recorded so it stays rejected)

| Rejected | Why |
|---|---|
| Qdrant / self-hosted vector engine (memory-os L5) | Mem0 already provides vector search; violates the v1 no-new-backend non-goal; operational surface (Qdrant + Redis + ARQ + weekly scanners) unjustified at this scale. |
| Auto-curated LLM wiki (memory-os L6) | Pure cost with no demand; the typed three-type store is the structured-knowledge layer. |
| Eager mid-turn agent tool writes (Hermes) | Shadow-first + background + debounce is strictly safer; eager writes trade precision for an immediacy not needed. |
| FTS5 session search (Hermes / memory-os L2) | Equivalent already exists and is correctly kept separate: checkpointer + thread sidebar + (planned) `thread_messages`. Long-term memory must not be conflated with thread resume (best-practices §6). |
| Token-based budget (vs. item-count) for A1 | Would pull a tokenizer dependency into framework-clean `services/`; item-count per (user, type) is the deterministic natural unit. |

---

## 9. Sources

External research grounding this design:
- [NousResearch Hermes Agent](https://github.com/nousresearch/hermes-agent) — bounded `MEMORY.md`/`USER.md`, agent-curated proactive writes, hard caps forcing in-turn consolidation.
- [Hermes Agent Documentation](https://hermes-agent.nousresearch.com/docs/) — closed learning loop, FTS5 cross-session recall, Honcho user modeling.
- [ClaudioDrews/memory-os](https://github.com/ClaudioDrews/memory-os) — the 7-layer memory OS (Workspace / Sessions / Structured Facts / Fabric / Vector / Wiki / Ground-Truth), surgical `pre_llm_call` injection, trust-scored facts, 0.92-cosine dedup decay scanner.
- [Hermes Agent AI 2026 self-hosted guide — Petronella](https://petronellatech.com/blog/hermes-agent-ai-guide/)

Internal grounding:
- [memory_layer_wiring.plan.md](../../plans/memory_layer_wiring.plan.md) — the live pipeline, governance four-pillar binding, layer invariants (I-1..I-14), flag discipline.
- [memory_and_chat_history_best_practices_2026.md](../memory_and_chat_history_best_practices_2026.md) — three-type taxonomy, ADD-only+consolidation, lean-context-beats-full-history, visible/editable memory UX.
- Code: `components/memory_context.py` (A2/A3), `services/long_term_memory.py` (A1/A4), `services/memory_autocapture.py` (A1 trigger), `components/schemas.py::TypedMemory` (A3 salience field).
```

---

## 10. Implementation status, critical review & remaining TODOs (2026-06-19)

> Appended after the build session. Branch `feat/memory-layer-wiring`, **uncommitted** (33 files, +3027/−49). Gates run this session: backend fast suite **3340 passed** / 12 skipped / 0 failed; frontend vitest **710 passed**; architecture **99 passed** (I-3/I-4/I-5/I-7 hold); determinism 10× no-flake on the new pure fns; tsc clean; wire-drift regenerated (openapi.yaml + wire-types.ts + TS↔Python baseline). Live cloud validation IN PROGRESS (see §10.4).

### 10.1 What shipped (per adoption)

| Adoption | Status | Where |
|---|---|---|
| **A2 — relevance floor + dedup** | ✅ built + unit-tested | `components/memory_context.py` (`filter_recall_records` + `render_recall_block` keyword-only `min_relevance`); `MEMORY_RECALL_MIN_RELEVANCE` flag (`base_config` + `AgentRuntimeSettings`); threaded at `react_loop.py` recall seam; `recall_count` now counts SURVIVORS not raw top-k. Backward-compatible (default 0.0 + no-score-never-dropped). 12 new tests. |
| **A3 — salience tiers** | ✅ built + unit-tested | same `render_recall_block` pass (`[confirmed]`/`[inferred]` from `salience`, unmarked when absent); `MEMORY_AUTHORITATIVE_AT` flag; `MemoryCreateRequest.salience` added so panel/CRUD can set it (wire→Zod→port→adapter→BFF→both create routes). |
| **A1 — budget + consolidation** | ✅ built + unit-tested | `LongTermMemoryService` gained `count()`, `consolidate()` (dedup→evict-by-salience), `ConsolidationOutcome`, and budget-on-`store()` (`_consolidate_on_overflow`); `list_all` optional backend capability (InMemory/Mem0/sqlite); `MEMORY_CONSOLIDATED` carrier (`black_box` enum + publisher + dev_seed + drift-guard); per-type budget flags. ~20 new tests. |
| **A4 — trust feedback** | ⏸ deferred (seam only, as designed) | no code; v2. |
| **Corpus + analyzer (Part B)** | ✅ built + tested | `build_memory_multisession_corpus.py` +4 ability families (53 cases, was 33); `analyze_memory_traces.py` +4 score branches + new `evicted_high_salience` hard-0 gate; corpus-invariant tests updated for new abilities/`crud-seed` kind; deterministic. |
| **E2E spec (Part C wiring)** | ✅ built | `memory-multisession.spec.ts` handles `crud-seed` (BFF `/api/memory` seeding under `identity.owner`, no `mem:` bridge for those cases) + per-case cleanup; `mem-hermes` testing profile. |

### 10.2 Decisions taken during implementation (deviations from the approved plan)

1. **A1 enforcement moved into `LongTermMemoryService.store()`, not just the autocapture write-back path.** *(user-approved mid-session)* — the budget is a property of the store, so EVERY writer (autocapture, the `/agent/memory` CRUD route, the panel) now consolidates on overflow. Closes a real unbounded-CRUD-write gap. The service returns the `ConsolidationOutcome`; the autocapture path emits the `MEMORY_CONSOLIDATED` carrier from it (service stays governance-free). Four-layer compliance preserved (logic in `services/`, injected not hardcoded).
2. **A1/A3 live validation runs under the real `identity.owner`, not a per-case synthetic user_id.** *(user-approved)* — the `/agent/memory` CRUD route scopes to `identity.owner` and ignores client user_id (the cross-user-leak guard), so crud-seeded memories can only land under the real owner. Those cases therefore skip the `mem:` bridge and clean up after themselves (shared owner namespace). A2 cases keep the per-case bridge.
3. **`MemoryCreateRequest` gained an optional `salience` field.** Needed for A3 live seeding; also a legitimate panel feature (a user-added memory can carry importance). Wire-schema change → artifacts regenerated.
4. **A1 v1 is deterministic-only** (dedup + evict-by-salience). LLM-merge consolidation remains a v1.5 seam (unbuilt). *(as planned)*
5. **Live smoke runs against the existing `memui` frontend host, temporarily repointed** (new image + `mem-hermes` backend URL, `--no-traffic`), *not* a fresh `memhermesui` host — because the backend verifies bearers against the real WorkOS JWKS (no e2e bypass), so a fake/sealed session 401s at the backend and only a WorkOS-registered redirect-URI host gives real auth. *(user-approved; restore command in `cache/memory_multisession/MEMUI_RESTORE.txt`)*.

### 10.3 Critical review — weaknesses & risks (honest)

- **`recall_count` semantics changed.** It now counts post-filter survivors (so the `MEMORY_RECALLED` carrier + the UI indicator reflect what was injected). Correct, but it's a behavior change to an existing carrier — any downstream consumer asserting the old "raw top-k" count would shift. Searched: only the indicator + analyzer consume it; both want survivors. Low risk, noted.
- **Exact-text dedup only (A2/A1).** Two semantically-equal but differently-worded facts ("prefers mornings" / "likes AM meetings") are NOT deduped. This is by design (no embedding on the hot path; LLM-merge is v1.5), but it means the dedup is weaker than memory-os's 0.92-cosine dedup. Acceptable for v1; documented.
- **Eviction tie-break is salience-then-insertion-order, and InMemory has no real recency.** `consolidate()` evicts lowest-salience first; ties fall to dict/iteration order, which is insertion order for the InMemory backend but NOT guaranteed meaningful for Mem0 (its `get_all` order is backend-defined). So "evict oldest among equal-salience" is only loosely honored on Mem0. Low impact (salience is the load-bearing key) but not the crisp "oldest out" the design diagram implies.
- **A1/A3 unit tests use a behavioral fake over `InMemoryMemoryBackend`, not Mem0.** The Mem0 `list_all`/consolidate path is exercised only by the (slow, ask-first) live smoke, not CI — same TDD-review LOW as the original Mem0 backend (`_client()`'s real SDK shape is only proven live). The live smoke is the only validation the Mem0 metadata-scan consolidation works.
- **No test that consolidation NEVER evicts below a "pinned"/safety threshold.** A1 will happily evict a salience-1.0 safety fact if budget is exceeded by even-higher-salience facts. The corpus has a case asserting the highest-salience survives, but there's no notion of an un-evictable floor. Probably fine (budget ≫ realistic safety-fact count), but worth a follow-up if memory holds medical/safety facts.
- **Live smoke early signal (UNRESOLVED — see §10.4):** the first probe rows show `recalled_count_dom=1` on BOTH the `leak-control` and `abstention` control cases, which must recall 0. This is a DOM-indicator reading (the analyzer gates on the **trace carrier**, not the DOM count), so it is a flag-to-investigate, not yet a verdict — but it matches the prior `[[memory-multisession-e2e-corpus]]` note that the `mem:` user_id bridge / indicator may over-report. Must be reconciled against the Langfuse trace before declaring the live run clean.

### 10.4a Live smoke RESULT (2026-06-19) — implementation clean; harness join BROKEN

**Playwright: 27/27 passed (6.2m), all 11 abilities incl. the 4 new ones; `crud-seed` sessions fired for A1/A3.** The analyzer printed `GATE FAILED` (cross-user-leak 1, fabricated-memory 1, multi-session miss) — but root-cause analysis shows **these are probe→trace JOIN failures in the validation harness, NOT pipeline defects:**

- **The agent answers are all correct.** leak-control answered *"I don't have any previous interactions or memory of your preferences"*; abstention answered *"I don't have any information about your pet's name."* The analyzer's own detail strings confirm `foreign=[]` (no foreign user recalled) and `claims=False` (no memory claimed) — i.e. no actual leak, no actual fabrication. The hard-0 rule trips only on the bare carrier `count>=1`.
- **Root cause: the `mem:` thread bridge is NOT reaching Langfuse as the trace `sessionId`.** The real trace sessionIds are `session-mem-1001-s2-<hash>` (backend-generated), NOT the `mem:MEM-0901:s0:userleak01:<trace>` form the analyzer's `_mem_session_id()` reconstructs and queries. So the analyzer gets 0 on the exact-session query and its fallback joins the WRONG trace (a different case's carriers) → spurious hard-0 counts. The 3 crud-seed A1/A3 cases 404'd outright (same join gap). This is exactly the known `[[memory-multisession-e2e-corpus]]` defect: `probe_trace_id ≠ backend workflow_id`, analyzer can't join.
- **Therefore the live VERDICT is: A1/A2/A3 implementation behaved correctly on the smoke (answers + 27/27 Playwright pass); the trace-analysis GATE is INCONCLUSIVE because the harness join is broken for this revision.** The `GATE FAILED` is a false-negative caused by mis-joined traces, not a memory leak. The implementation's own unit/integration suite (3340 backend + 710 frontend) already proves the A1/A2/A3 logic; the live run proves the agent answers correctly end-to-end; only the automated trace-scoring couldn't bind to confirm carriers per-case.
- **New P0 added (§10.5 #2a): fix the `mem:` sessionId → Langfuse join** (make the backend stamp the `mem:` thread as the trace sessionId, OR teach the analyzer the real `session-mem-<id>-s<idx>` form) before the gate can give a trustworthy verdict. Until then the gate's leak/fabrication numbers on a bridged run are not trustworthy.

**Two genuine findings the live run DID surface (real, not harness artifacts):**

1. **Silent CRUD/panel consolidation (Validation-pillar gap, CONFIRMED live).** `memory.consolidated` carriers in Langfuse = **0** for the run, even though the budget-consolidation case crud-seeded 6 semantic facts against `MEMORY_BUDGET_SEMANTIC=5`. Root cause: the A1 decision put consolidation in `LongTermMemoryService.store()` (good — every writer is bounded) and has it RETURN the `ConsolidationOutcome`, but **only the autocapture path emits the `MEMORY_CONSOLIDATED` carrier from that return value** — the `/agent/memory` CRUD `create_memory` route (`app_prod.py:404`) discards it. So a CRUD/panel-triggered eviction prunes memory **silently, with no carrier** — exactly the swallowed-failure the Validation pillar forbids. **FIX (P1, §10.5 #6a): `create_memory` should emit a `MEMORY_CONSOLIDATED` carrier when `store()` returns a non-None outcome** (mint a workflow_id for the CRUD action, or attach to the request trace). The eviction itself is correct (storage is bounded); only the observability of a CRUD-path eviction is missing.
2. **Privacy/Recording pillar: PASS.** A direct scan of the run's `memory.recalled` carriers shows NO leaked content (none of the seeded fact-words appear) — the content-free-carrier invariant holds live.

### 10.4 Live cloud validation — state at session end

- **Deployed (both `--no-traffic`, prod root untouched):** backend `agent-backend-combined` tag **`mem-hermes`** rev `00088-gon` (`MEMORY_ENABLED=true`, `MEMORY_AUTOCAPTURE_ENABLED=true`, `MEMORY_RECALL_MIN_RELEVANCE=0.3`, `MEMORY_AUTHORITATIVE_AT=0.8`, `MEMORY_BUDGET_SEMANTIC=5`), health 200 `runtime:langgraph`. Frontend `agent-frontend` tag **`memui`** rev `00057-qah` (new image w/ salience BFF, `MIDDLEWARE_URL`→mem-hermes backend) — **temporarily repointed; MUST be restored.**
- **Smoke (`MEM_SMOKE=1`, real WorkOS auth) IN PROGRESS at session end:** 5/11 ability rows captured + `pass` at the spec level (leak-control, abstention, recall, multi-session, temporal); the 4 new Hermes abilities pending. `cache/memory_multisession/probe_batch.jsonl` accumulating.
- **NOT yet done:** `analyze_memory_traces.py --source langfuse --gate` (the authoritative per-ability + hard-0 verdict); the governance-trace-audit of a representative `mem-hermes` trace; reconciling the §10.3 `dom_recall=1` control-case signal against the trace carriers.

### 10.5 Remaining TODOs / actions (prioritized)

**P0 — finish the live run + restore shared state (do not leave half-done):**
1. Let the `MEM_SMOKE` run finish; confirm all 11 abilities captured.
2. ✅ DONE — analyzer run + root-caused (§10.4a): `GATE FAILED` is a **false-negative from a broken probe→trace join**, not a pipeline leak (answers are clean; `foreign=[]`/`claims=False`; real sessionIds are `session-mem-<id>-s<idx>`, not the `mem:` form the analyzer queries).
   - **2a. (NEW P0) Fix the `mem:` sessionId → Langfuse join** so the gate can give a trustworthy per-case verdict: either make the backend stamp the client `mem:` thread as the trace `sessionId`, or update the analyzer's `_mem_session_id()`/`_resolve_langfuse_trace_id()` to the real `session-mem-<id>-s<idx>-<hash>` shape. Re-run the gate after the fix; only then is the leak/fabrication scoring trustworthy on a bridged run. (Known issue: `[[memory-multisession-e2e-corpus]]`.)
3. Governance-trace-audit a representative trace carrying `memory.recalled` + `memory.consolidated` (via `scripts/fetch_memory_trace.py` then the `governance-trace-audit` skill): verify carriers present + **content-free**, same subject, consolidation visible (Validation pillar). Target verdict COMPLIANT(-WITH-FINDINGS).
4. **RESTORE `memui`** to rev `agent-frontend-00051-np2` + the `mem` backend URL (cmd in `cache/memory_multisession/MEMUI_RESTORE.txt`); **tear down** the `mem-hermes` backend tag (and the temporary `memui` repoint) so no stress tags linger (`[[deploy-gcp-stress-revision]]` lesson).

**P1 — close validation gaps:**
5. Optionally run the FULL 53-case batch (not just smoke) for complete per-ability rates once smoke is clean.
6. Add a Mem0-backed consolidation contract test OR mark the live smoke REQUIRED-before-promotion (the `list_all`/metadata-scan path is CI-untested — §10.3).
   - **6a. (NEW P1) Emit `MEMORY_CONSOLIDATED` from the CRUD path** (`app_prod.py` + `agent_ui_adapter/server.py` `create_memory`): when `memory.store()` returns a non-None `ConsolidationOutcome`, emit the carrier so a panel/CRUD-triggered eviction is not a silent Validation-pillar failure (CONFIRMED live: 0 consolidation carriers in Langfuse — §10.4a finding 1).
7. Phase-2 autocapture enable-policy still gates real write-back in prod: A1 consolidation only "bites" once write-back is on, which is still behind the grounded-theory calibration gate (store-precision ≥0.90, PII-flip ==0, κ ≥0.60). A1 is built + flag-ready but dormant in prod until that flips.

**P2 — design follow-ups (not blocking):**
8. Consider an un-evictable salience floor for safety-critical facts (§10.3).
9. A2/A1 dedup is exact-text only; the LLM-merge `consolidate()` (v1.5 seam) handles semantic dedup — schedule if recall noise from near-duplicate facts is observed.
10. Eviction recency tie-break is backend-order-dependent on Mem0 (§10.3) — add an explicit stored timestamp to `metadata` if "oldest out" must be crisp.
11. A4 trust-feedback loop (v2): reserve `metadata["trust"]` + `reinforce(user_id, key, Δ)`; wire when a reflexion/GoalJudge→memory feedback edge exists.

**P3 — housekeeping:**
12. **Commit** — nothing committed this session (user handles commits); 33 files on `feat/memory-layer-wiring` (now more — see §10.6).
13. The autocapture wire-schema change (`MemoryCreateRequest.salience`) + the swap-radius architecture guard may fire on commit (service+adapter co-change) — split commits or `-k 'not swap_radius'` per the Phase-2 commit note.

### 10.6 Follow-up session (2026-06-19, second pass) — P0/P1/P2 RESOLVED

> Built test-first; backend memory surface **299 passed / 0 failed**, architecture **99 passed** (swap_radius deselected per the commit note), consolidation **deterministic** 10×. Uncommitted, same branch.

- **P0 #2a — analyzer probe→trace join: FIXED + gate re-run TRUSTWORTHY.** Root cause was empirically pinned: the spec's `probe_trace_id` IS adopted by the backend as the real Langfuse trace id (via the `mem:` thread bridge — the earlier "FE-AP-7 says client trace_id is never echoed" assumption was **false**). New primary join = a **direct `/traces/{probe_trace_id}` fetch** (`_load_langfuse_events_for_row`), with a backend-sessionId **prefix** fallback (`session-{mem_id}-s{idx}-{uuid}` — the trailing uuid made exact-match impossible). The old `_mem_session_id` (reconstructed the raw `mem:` string) was a tautological-test–locked wrong shape; flipped. **Second defect found + fixed:** the leak/abstention hard-0 gate triggered on bare `recall_count >= 1`, which false-positives under the `mem:`→owner user-collapse (control probes recall the owner's own store, then abstain). Gate is now **answer-grounded** — a leak needs a *foreign user_id* in the carrier OR an answer that *asserts* a remembered fact (`_claims_memory`); abstention-fabrication needs the answer to *claim* memory. Re-run verdict: **GATE PASSED**, all 3 hard-0 = 0, leak/abstention 1.000, 0 missing-trace (matches the clean-abstention screenshots). Walkthrough: [hermes_live_walkthrough_report.md](hermes_live_walkthrough_report.md) §3.
- **P1 #6a — silent CRUD consolidation: FIXED.** New shared emitter `services/governance/memory_consolidation_carrier.py` (single source of the content-free carrier shape) is now called by autocapture AND both CRUD `create_memory` routes (`app_prod.py` + `agent_ui_adapter/server.py` via a new optional `black_box_recordings_dir`). An overflowing panel write mints a `mem-crud-*` workflow_id and records `MEMORY_CONSOLIDATED`; the in-process relay drains it to Langfuse. End-to-end test asserts the carrier lands on disk with counts only (no content leak) on overflow, and is absent under budget.
- **P1 #6 — Mem0 consolidation contract test: ADDED.** New `TestMem0ConsolidationContract` drives `count`/`consolidate`/store-overflow through the **real Mem0 backend** + the faithful v2 `_FakeMem0Sdk` (envelope, opaque ids, metadata-as-JSON-string flatten) — covering the `list_all`→`get_all` + delete-by-resolved-id path that only InMemory exercised before. Asserts eviction-order (high salience survives), dedup-keeps-highest, and metadata-survives-roundtrip-so-count-filters-by-type.
- **P2 #8 — un-evictable safety floor: ADDED.** `LongTermMemoryService(..., safety_floor=None)` (+ `MEMORY_SAFETY_FLOOR` setting, default 0.0/disabled, threaded at the composition root). A fact with `salience >= floor` is pinned and never evicted for budget; if pinned alone exceed budget, the store runs over rather than drop a safety fact.
- **P2 #10 — explicit recency tie-break: ADDED.** `store()` stamps `metadata["stored_at"]` (UTC iso, caller value preserved); `consolidate()` breaks equal-salience ties by evicting the **oldest** first (`(salience desc, stored_at desc)`), crisp instead of Mem0-insertion-order dependent. Two pre-existing exact-metadata-equality tests updated to the new contract (caller keys round-trip + a `stored_at` is added).

### 10.7 Third pass (2026-06-19) — #7 enable-policy ENFORCED (no longer honour-system)

> The gap #7 named was not "build a gate" (the scorer/CLI/policy-doc already existed) — it was that **nothing connected the gate to the runtime flag**. `MEMORY_AUTOCAPTURE_ENABLED=true` turned write-back on regardless of whether the calibration gate was ever run. That's the dangerous hole: A1/safety-floor were flag-ready *and ungoverned*. This pass closes it. Backend memory surface **173 passed / 0 failed**, architecture **99 passed** (swap_radius deselected), guard deterministic 10×. Uncommitted, same branch.

- **#7 — write-back enable-policy now MACHINE-ENFORCED.** New framework-clean guard `services/governance/memory_enable_policy.py`: `resolve_write_back(flag_requested, certificate) -> WriteBackDecision`. Write-back turns on only when the flag is set **AND** a passing, frozen-`test`-split **certificate** is present at `MEMORY_AUTOCAPTURE_CERT`. The guard re-validates the split + every gate individually (so a hand-edited `passed:true` over a failed hard-zero gate is rejected) and **fails SAFE to shadow** on any problem (missing/corrupt/wrong-schema/dev-split/blocked cert), logging a loud governance WARNING. The certificate is emitted by `scripts/eval/memory_extractor_calibrate.py --emit-certificate` (a pure projection of the same `CalibrationReport` — scorer stays the single source of the gate math; `--emit-certificate` refused on dev or a blocked run, AP-4). Wired at the composition root (`composition.py`: new `MEMORY_AUTOCAPTURE_CERT` setting → `resolve_write_back` → the *effective* `write_back_enabled` passed to `MemoryAutoCaptureService`). 16 new tests (13 guard unit, failure-paths-first + 3 composition-integration proving the constructed service reflects the guard, not the raw flag). Docs updated: `03_enable_policy.md` §1/§5, `04_calibration_runbook.md` Stage 6, `base_config.py`. **Result:** flipping `MEMORY_AUTOCAPTURE_ENABLED` alone in prod no longer starts storing — A1/safety-floor stay dormant until a real calibration certificate clears. Rollback unchanged (flag off → shadow instantly; removing the cert also drops to shadow).

**Still open (unchanged):** #5 (full 53-case batch, optional), #9/#11 (LLM-merge v1.5 seam, A4 trust loop — both deferred by design), #12/#13 (commit — now also the new files: `services/governance/memory_enable_policy.py`, `tests/services/governance/test_memory_enable_policy.py`, the §10.6 files, + edits to `composition.py`/`base_config.py`/the calibrate CLI/`test_agent_runtime_composition.py`/the two recipe docs). The remaining #7 piece — **actually producing a real calibration certificate** — is gated on collected shadow traces + the Stage 0→6 labeling ladder (`04_calibration_runbook.md`), which is the eval workstream, not this wiring.
