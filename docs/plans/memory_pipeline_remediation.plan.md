---
type: plan
name: Memory Pipeline Remediation
overview: Trace-driven remediation of the memory pipeline that fixes the root cause of the cricket hallucination loop (the live Phase-1 answer-store) and the empty-panel trust gap, while deferring recall-rendering, consolidation, and provenance work to the already-designed Hermes adoptions (H1/H2/H3). Replaces the prior memory_quality_improvements plan, whose B1 store-gate would have disabled memory for normal conversation.
todos:
  - id: t0-harness
    content: Extend the EXISTING multisession harness (corpus + analyzer + spec, 33 cases/7 abilities) - add a self-reinforcing-hallucination (cricket) ability, pin the stale-after-update substring as a hard-0 gate for knowledge-update cases, add a per-user store-key cardinality / unbounded-growth assertion (live - 87 keys/85 traces), and add a memory.consolidated carrier gate (live count = 0)
    status: pending
  - id: t1-store-model
    content: Change build_store_payload to store user-stated content (not agent answer), key by stable semantic key (not ephemeral task_id) so corrections upsert; add single-writer switch vs autocapture; remove goal_met gate; add tests. NOTE - this stops hallucination pollution but does NOT fix the multi-fact/update recall-quality misses (those are Track 5 typed extractor)
    status: pending
  - id: t3a-list-all
    content: Add list_all to MemoryBackend Protocol + all backends (InMemory/sqlite/Mem0 via _get_all); update tests/architecture; replace search("") in app_prod.py and agent_ui_adapter/server.py
    status: pending
  - id: t3b-panel-refresh
    content: Call reloadMemories() on terminal run state in chat-shell.tsx; add distinct error state in MemoryPanel.tsx; jsdom test for panel<->RecallIndicator sync
    status: pending
  - id: t4-recall-floor
    content: "Implement Hermes H1: relevance floor + exact-text dedup in render_recall_block (default min_relevance=0.0, settings-injected); add meta-query widening; calibrate floor via eval probe"
    status: pending
  - id: t2-supersession
    content: Stable-key upsert supersedes re-stated facts (deterministic half); validate via new self-reinforcing-hallucination case + stale-after-update hard-0 gate; general cross-key UPDATE owned by Track 5 typed extractor; auto-correction-detection is an A4/v2 seam (do not build)
    status: pending
  - id: t5-enablement
    content: "Typed extractor (owns MEM-MULTI/MEM-UPDATE recall-quality misses): check live shadow type-skew (73 semantic/1 episodic/0 procedural) in calibration -> flip MEMORY_AUTOCAPTURE_ENABLED (hands store path off the single-writer switch) -> add live UPDATE/DELETE -> H3 salience tiers; re-run corpus to confirm misses become hits. NOTE: H2 budget/consolidate pulled forward (see t5a)"
    status: pending
  - id: t5a-budget-guard
    content: "Pull Hermes H2 forward (live: 0 memory.consolidated ever, one user at 87 unbounded rows). Land budget + consolidate() + MEMORY_CONSOLIDATED carrier on the interim deterministic store before the full extractor flip, so the runaway user stops accumulating."
    status: pending
  - id: t6-infra
    content: "Split out: pg_thread_repo bind for sidebar persistence + Failed-to-fetch diagnosis (Cloud Run logs + SSE timeout); separate from memory quality"
    status: pending
isProject: false
---

# Memory Pipeline Remediation

Supersedes `memory_quality_improvements_2a574e92`. Reconciled with the live code, with [docs/research/memory/hermes_adoptions_design.md](docs/research/memory/hermes_adoptions_design.md), and with the validated multi-session walkthrough [docs/analysis/MEMORY_MULTISESSION_VALIDATED_SESSION.md](../analysis/MEMORY_MULTISESSION_VALIDATED_SESSION.md).

## Independent confirmation from the validated multi-session run (2026-06-18)

The 18/18 smoke run (`MEM_SMOKE=1`, GATE PASSED) corroborates the diagnosis and changes two assumptions:

- **The harness already exists and is mature** — 33-case / 7-ability corpus [`frontend/e2e/fixtures/memory_multisession_corpus.json`](frontend/e2e/fixtures/memory_multisession_corpus.json), driver [`memory-multisession.spec.ts`](frontend/e2e/full-stack/memory-multisession.spec.ts), analyzer [`scripts/analyze_memory_traces.py`](scripts/analyze_memory_traces.py) `--gate` with three hard-0 gates (cross-user leak, stale-after-update, fabricated memory). Track 0 is therefore *extend*, not *build*.
- **`MEM-UPDATE-units-01` is Track 2, proven**: seeded imperial then "scratch that, metric now"; both values stored (`count=2`), the probe answered with the stale **imperial**. Documented root cause: "the ADD-vs-UPDATE seam — both values stored, neither cleanly wins." It was recorded only as a recall-quality miss (not a `stale-after-update` hard-0) because the corpus probe did not pin the stale substring as a gate — a harness gap Track 0 closes.
- **`MEM-MULTI-trip-01` miss** (Japan + $3000, `count=0`): two facts from two sessions, top-3 returned neither. Root cause = the v1 `Task:/Answer:` prose store buries facts.
- **The doc's explicit conclusion**: both quality misses "trace to the v1 `Task:/Answer:` prose store. Promoting the typed extractor out of shadow mode is the lever on recall quality." This bounds Track 1: the deterministic interim stops hallucination pollution; the multi-fact and update misses are owned by **Track 5** (typed extractor).
- **"Failed to fetch"** is independently confirmed as a BFF/transport drop, tracked separately (Track 6).

## Live Langfuse trace evidence (2026-06-17 -> 2026-06-19, read-only enumeration)

Aggregated the `memory.*` carriers straight from Langfuse (`/api/public/observations`). The numbers move the diagnosis from "verified in code" to "verified in production":

- **Memory went live mid-day 2026-06-18; nothing before.** Zero carriers on 2026-06-17; the earliest carrier is `2026-06-18T16:28:07Z`, matching the `mem`-tag redeploy (rev `00087-qip`). So the unbounded accumulation is day-one-onward, not a legacy backlog. The runaway user grew from **73 keys (06-18) to 87 keys (by 06-19)** — ~14 new rows in one day, still climbing, with zero consolidations the whole time.
- **Store key is the ephemeral `task_id`, 100% of the time.** 124/124 committed `memory.stored` carriers have a 32-char UUID key (`3b8d5018...`, `type=None`). No store ever upserts; every turn is a brand-new row. This is the live mechanism Track 1 fixes.
- **One real human user is in a runaway loop.** `user_01KQ0FRZDH6HQ4A3ZXC1YEWVSX` has **87 distinct store keys across 85 traces** and **82/85 (96%) of its recalls return count=3** (the full top-3). Unbounded growth + always-full recall = the self-reinforcement loop, observed in prod, not just the cricket anecdote.
- **No consolidation has ever fired.** `memory.consolidated` = **0** observations in the window. There is no backstop on the growth above (H2 is not enabled). This raises the urgency of bringing a budget guard forward.
- **Recall has no relevance floor.** Across 124 recalls the count distribution is `count=3 -> 92 (74%)`, `2 -> 10`, `1 -> 8`, `0 -> 14`. Search almost always fills top-3 regardless of relevance -> context bloat (Track 4 / Hermes H1), now quantified.
- **Shadow autocapture is live but type-skewed.** 74 `proposed_only` stores: **73 semantic, 1 episodic, 0 procedural**. The extractor barely proposes episodic/procedural -> a concrete calibration gap for Track 5 before any write-back flip.
- **The eval misses reproduce live today.** `usermulti01` shows `count=0` on 3/6 recalls (the MEM-MULTI multi-fact miss); `userupd01` recalls run at count up to 3 with both stale+new stored (the MEM-UPDATE ADD-vs-UPDATE seam). Both confirmed on 2026-06-19 traffic.

Reproduce (read-only): query `/api/public/observations?name=memory.recalled|memory.stored|memory.consolidated&fromStartTime=2026-06-18T00:00:00Z` with the repo-root `LANGFUSE_*` creds.

## Test-suite review (smoke / eval / implementation / Playwright)

Inventory is mature; the gap is what is NOT asserted, not missing files:

- **Smoke (live):** `frontend/e2e/full-stack/memory-multisession.spec.ts` (T3, Cloud Run `mem`/`mem-hermes`) + `scripts/mem0_smoke.py` + `scripts/fetch_memory_trace.py`. NOTE: running T3 is a deliberate non-readonly action (real LLM calls + writes live Mem0), so it is post-approval, not part of this plan-mode pass.
- **Eval:** `scripts/analyze_memory_traces.py --gate` (3 hard-0 gates), `tests/scripts/test_analyze_memory_traces.py`, `tests/services/governance/test_memory_extractor_calibration.py`, `scripts/eval/memory_extractor_calibrate.py`.
- **Implementation:** ~22 backend pytest + 12 frontend vitest (MemoryPanel, RecallIndicator chain, BFF, translators, mem0 adapter, app_prod CRUD/owner-scoping, wiring sims).
- **Playwright:** T3 live driver + `integration/memory-multisession.mock.spec.ts` (T1 CI wiring guard).
- **Coverage gaps the live data exposes (fold into Track 0):**
  1. No test asserts **store-key cardinality stays bounded per user** — 87 unbounded rows would pass every current test. Add a regression assertion.
  2. The **`stale-after-update` hard-0 gate is not pinned** for `knowledge-update` cases, so `MEM-UPDATE-units-01` only scores as a quality miss (already noted; live `userupd01` confirms).
  3. No test exercises **`memory.consolidated`** end-to-end against the live carrier (H2 path is untested in prod posture).

## Root cause (verified in code, 2026-06-19)

- Live store path [`_maybe_store_memory`](orchestration/react_loop.py) calls [`build_store_payload(task_input, answer)`](components/memory_context.py) and stores the **agent's verbatim answer** every run.
- Key = `task_id`, which is minted **fresh per turn** (`task_id = run_id = uuid4()` in [langgraph_runtime.py:189-191](agent_ui_adapter/adapters/runtime/langgraph_runtime.py)). So each turn writes a **new Mem0 row** — never upserted across turns, unbounded.
- Recall [`route_node`](orchestration/react_loop.py) does `search(user_id, task_input, 3)` and injects all results via [`render_recall_block`](components/memory_context.py) with no relevance floor.
- Net effect (matches the Garvit/cricket session): a hallucinated answer is stored, then semantic-recalled into top-3 on later turns, reinforcing itself. The "duplicate baseball" rows are two turns → two UUIDs.

## What is wrong with the prior plan (do NOT carry forward)

- **B1 store-gate on `goal_met=false` is harmful.** Every conversational turn in the session has `goal_met=false`; gating on it disables storage for all chat (drops legitimate facts too). Also `goal_met` is not a state field (only `last_task_outcome` string + the in-`evaluate` verdict). Removed entirely.
- **B2/B3/B4 overlap the Hermes design.** Relevance floor + dedup = Hermes **H1**; consolidation/budget = **H2**; salience provenance = **H3**; trust feedback = **v2/A4**. This plan defers to those rather than reinventing them.

## Reconciliation with Hermes adoptions

- **Own here (gaps Hermes does not cover):** store-model fix, correction/supersession, panel list/refresh trust fixes, regression harness.
- **Defer to Hermes doc:** H1 recall relevance-floor+dedup (this plan only schedules/implements it), H2 budget+consolidate, H3 salience tiers, v2 trust feedback. Every Hermes item except H1 gates on autocapture write-back being ON.

## Tracks

### Track 0 — Extend the EXISTING regression harness FIRST (gate for everything)
The harness exists and passes (18/18 smoke). Do NOT rebuild it. Extend it:
- Add a `self-reinforcing-hallucination` ability/case to [`frontend/e2e/fixtures/memory_multisession_corpus.json`](frontend/e2e/fixtures/memory_multisession_corpus.json) modeling the cricket loop: seed a question whose answer the agent fabricates, then a user correction, then probe that the fabricated value does NOT resurface. Driver [`memory-multisession.spec.ts`](frontend/e2e/full-stack/memory-multisession.spec.ts) already iterates the corpus.
- Close the harness gap on updates: pin the **stale substring** as a `stale-after-update` hard-0 gate for `knowledge-update` cases in [`scripts/analyze_memory_traces.py`](scripts/analyze_memory_traces.py) (today `MEM-UPDATE-units-01` only scores as a quality miss; live `userupd01` confirms it on 2026-06-19).
- **New (from live traces): add a store-key cardinality / unbounded-growth assertion.** A per-user `memory.stored` distinct-key count that grows ~1 per turn (live: 87 keys / 85 traces for the real user) must be caught. Assert in `analyze_memory_traces.py` (or a `tests/scripts` fixture) that after Track 1, re-stated facts upsert (distinct-key count stays bounded) instead of accumulating.
- **New: exercise the `memory.consolidated` carrier.** Live count is 0 — nothing tests the H2 path against the real carrier shape. Add a gate/fixture so H2 (Track 5) cannot ship without emitting it.
- Re-run `MEM_SMOKE=1` + `analyze_memory_traces.py --gate` after each subsequent track; all three hard-0 gates must stay 0.
- Rationale: the prior plan ran fixes before measuring; this harness is the existing, trusted gate.

### Track 1 — Store-model fix (root cause, stops active harm)
Live proof this is active harm, not theoretical: 124/124 committed stores key by UUID `task_id`, and one real user already carries 87 unbounded rows with 96% full-top-3 recall.
- Decision (single-writer): stop storing the agent's free-text answer verbatim. Make the live store write **user-stated content only**, not `answer`.
  - Change [`build_store_payload`](components/memory_context.py) so v1 text is derived from `task_input` (user statement), not the agent answer; keep it deterministic, no LLM.
  - Key by a **stable** semantic key (not ephemeral `task_id`) so a re-stated fact upserts instead of accumulating a new row per turn. This is also what enables Track 2 supersession.
- Add an explicit single-writer switch so the live deterministic store and autocapture write-back never both write (prevents double-store when H-phases flip on).
- Remove the prior B1 `goal_met` gate concept.
- Tests: extend [`tests/orchestration`](tests/orchestration) store path + a `memory_context` unit asserting hallucinated answers are no longer persisted.

### Track 2 — Correction / supersession (the ADD-vs-UPDATE seam)
Confirmed by `MEM-UPDATE-units-01` (both imperial+metric stored, stale value won) and the cricket loop.
- Track 1's stable-key upsert means a corrected user fact (same semantic key) overwrites the stale one instead of coexisting — this is the deterministic half of the fix and resolves the `knowledge-update` ability for re-stated facts.
- Full UPDATE/supersession across differently-keyed facts is owned by **Track 5** typed extractor (the doc's named lever); it must move beyond Phase-2 ADD-only to live UPDATE/DELETE for this class.
- Existing polluted rows: the editable panel (Track 3) is the user escape hatch.
- Validate via Track 0: the new self-reinforcing-hallucination case + the stale-after-update hard-0 gate must pass.
- Out of scope (follow-up tied to A4/v2): automatic LLM correction-detection that proactively deletes on "no, that's wrong." Flag as a seam, do not build speculatively.

### Track 3 — Panel trust fixes (highest visible gap)
- Add `list_all(user_id, limit)` to the `MemoryBackend` Protocol in [`services/long_term_memory.py`](services/long_term_memory.py) and implement on **all** backends (InMemory, sqlite, [Mem0 via existing `_get_all`](services/memory_backends/mem0.py)); update [`tests/architecture`](tests/architecture) for the Protocol change.
- Replace `memory.search(owner, "", 500)` with the enumerate path in [`middleware/app_prod.py:375-390`](middleware/app_prod.py) and [`agent_ui_adapter/server.py`](agent_ui_adapter/server.py).
- Refresh panel after run completion: call `reloadMemories()` on terminal run state in [`frontend/app/chat-shell.tsx`](frontend/app/chat-shell.tsx); add jsdom test asserting panel populates and matches `RecallIndicator`.
- Surface a distinct error state (vs empty) in [`MemoryPanel.tsx`](frontend/components/memory/MemoryPanel.tsx).

### Track 4 — Recall quality = implement Hermes H1 (not a new design)
Live priority bump: recall returns the full top-3 in 74% of cases overall and 96% for the runaway user, with no floor — so H1 is not just noise reduction, it is actively throttling the self-reinforcement loop. Promote to run right after Track 1.
- Implement the H1 seam from the Hermes doc: relevance floor + exact-text dedup in [`render_recall_block`](components/memory_context.py), default `min_relevance=0.0` (byte-identical no-op), threshold on `AgentRuntimeSettings`, calibrated via the eval probe before prod flip.
- Meta-query widening ("what do you know about me", "is that all") as a small additive intent check; profile-first recall stays deferred until typed semantic records exist (post write-back).

### Track 5 — Typed extractor enablement (owns the recall-quality misses)
This is the documented lever for `MEM-MULTI` (multi-fact) and `MEM-UPDATE` (update) misses.
- **Calibration gap from live shadow data:** 74 shadow proposals over two days were 73 semantic / 1 episodic / 0 procedural. Before any write-back flip, calibration must confirm the extractor is not collapsing everything to `semantic` (the corpus has temporal/persona/relationship facts that should not all be semantic). Use this skew as an explicit calibration check.
- Autocapture write-back flip: collect shadow traces, run [`scripts/eval/memory_extractor_calibrate.py`](scripts/eval/memory_extractor_calibrate.py), flip `MEMORY_AUTOCAPTURE_ENABLED` only on ENABLE-ELIGIBLE; the single-writer switch (Track 1) hands the store path to the extractor at this point.
- Extend the extractor beyond Phase-2 ADD-only to live UPDATE/DELETE so re-stated/corrected facts supersede (closes Track 2's general case).
- **Pull H2 budget forward (live: 0 consolidations ever, one user at 87 rows).** Even on the deterministic interim store, the unbounded-growth backstop should not wait for the full extractor enablement. Land H2 (budget + `consolidate()` + `MEMORY_CONSOLIDATED` carrier) as the first sub-step here (or as a Track 1 follow-on) so the runaway user stops accumulating. H3 (salience tiers) follows per the Hermes doc. No duplication here.
- Re-run the multisession corpus (`MEM-MULTI`, `MEM-UPDATE`) to confirm the misses flip to hits.

### Track 6 — Infrastructure (split out, P3, not memory quality)
- Thread sidebar persistence (`pg_thread_repo` bind, [bff_cloudsql_thread_repo.plan.md](docs/plans/bff_cloudsql_thread_repo.plan.md)) and "Failed to fetch" diagnosis (Cloud Run + SSE timeout). Tracked separately so it does not dilute the memory work.

## Execution order
1. Track 0 (harness) — the gate. Add the store-key cardinality + `memory.consolidated` assertions first.
2. Track 1 (store-model) + Track 3 (panel) in parallel — stop harm + close visible trust gap; independent.
3. Track 4 (H1 recall floor) — promoted: live 96% full-top-3 recall on the runaway user means this directly throttles self-reinforcement.
4. **H2 budget guard (pulled forward from Track 5):** with 0 consolidations ever and a user at 87 rows, land the budget/`consolidate()` backstop on the interim store before the full extractor flip.
5. Track 2 cleanup verification.
6. Track 5 (shadow-skew calibration → write-back → live UPDATE/DELETE → H3).
7. Track 6 (infra) in parallel throughout.

## Invariants preserved
- No new graph nodes (recall/store stay thin OBP-3 wrappers per AGENTS.md).
- Privacy: carriers stay content-free (`user_id`/`key`/counts only).
- Layer rules: store-model + harness logic in `components/`+`services/`; no `langgraph`/`langchain` in `components/`/`services/`.
