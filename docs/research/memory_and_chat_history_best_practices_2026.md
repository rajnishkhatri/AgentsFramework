# Memory & Chat-History Best Practices for Agentic Chatbots (2026) — External Research

> **Date:** 2026-06-17. **Purpose:** ground the memory-layer expansion (chat-history sidebar + auto-detected typed memory) in current best practices before extending [memory_layer_wiring.plan.md](../plans/memory_layer_wiring.plan.md). Companion to that plan.

## 0. TL;DR (what the research tells us to build)

1. **The three memory types we picked are the industry-standard model.** Semantic (facts), episodic (past events/experiences), procedural (learned rules/behaviors) is the canonical taxonomy across Mem0, Zep, Letta, and **LangMem** (LangChain's own SDK). Our repo vocabulary already matches it.
2. **Background ("subconscious") extraction is the recommended default for auto-capture** — exactly the choice locked. Run a cheap LLM reflection pass *after* the response, with **debouncing** (batch a burst of messages, process on a pause). Keeps latency off the hot path; gives higher recall.
3. **Use a hybrid storage shape per type, not one bucket:** semantic → *profile* (single evolving doc) for stable user facts/preferences + *collection* for unbounded facts; episodic → *collection* of structured items; procedural → prompt rules. This is LangMem's profile-vs-collection distinction and it directly answers "how do we classify."
4. **Conflict resolution is the make-or-break detail.** When the user contradicts themselves ("mornings" → later "afternoons"), naive vector store keeps both. Production systems dedup/merge on embedding similarity (~0.85 merge / ~0.9 dedup thresholds) with an LLM resolving the winner, or use **ADD-only single-pass extraction + periodic consolidation** (cheaper, ~22% precision gain, 60% storage cut per recent results).
5. **Trust/UX: auto-capture must be visible and editable** (the choice locked). The 2026 norm (Claude/ChatGPT memory) is transparent recall ("searched past conversations") + a memory panel where users view/edit/delete/disable. This is a *feature*, not a backend detail.
6. **Chat history and long-term memory are two different mechanisms that look similar** — keep them distinct. Chat history = resume a specific thread (our checkpointer + thread list). Memory = facts that travel *across* threads. Past conversations can *feed* memory extraction, but the sidebar is not the memory store.

---

## 1. Memory types — the canonical model (confirmed)

| Type | Holds | Example | Storage shape | Write trigger |
|------|-------|---------|---------------|---------------|
| **Semantic** | Facts/knowledge about user & world | "Prefers metric units", "Works in fintech" | *Profile* (latest-state doc) for core prefs; *collection* for open-ended facts | Stable fact stated/implied |
| **Episodic** | Past events / how a task was solved | "Last session debugged the auth flow, approach Y worked" | *Collection* of `{observation, thoughts, action, result}` items | Run/task completes |
| **Procedural** | Rules/strategies that work | "Always show code before explanation for this user" | Prompt rules / optimized system-prompt fragment | Repeated feedback signal |

LangMem (LangChain) implements exactly these three and ships APIs per type: `create_memory_manager`/`create_memory_store_manager` (semantic+episodic collections), `create_prompt_optimizer` (procedural). Mem0/Zep/Letta converge on the same taxonomy with different substrates (vector / temporal graph / OS-style memory blocks).

**Classification answer (this is the key design question the user asked):** Don't build a free-standing "what type is this?" classifier. Instead drive a **schema-guided extraction** pass: give the LLM the three schemas and ask it to emit zero-or-more typed memory items per conversation window. The schema *is* the classifier. Profiles replace; collections reconcile (insert/update/invalidate).

## 2. Write strategy — hot path vs background (background wins for us)

- **Hot path:** agent calls a memory tool mid-turn. Immediate, but adds perceptible latency and lets memory churn pollute the turn. Best reserved for *recall* (read), not auto-*capture* (write).
- **Background / "subconscious":** an after-the-response reflection pass extracts + reconciles memories. **No user-facing latency, higher recall.** LangMem's `create_memory_store_manager` does this and **debounces** ("if the user sends 5 messages in 10 seconds, wait for a pause and process them together").

→ **Our pattern:** recall on the hot path (already planned: top-3 into the system prompt, memoized at step 0); **capture in the background** after a run completes, debounced per thread.

## 3. Production pitfalls (what teams get wrong)

- **Whole-history-in-prompt scales badly** on cost, latency, *and* accuracy (irrelevant turns crowd the window). Extraction/compression precision matters more than context volume — "a lean retrieved context beats the full history."
- **Conflict/staleness:** contradictions must resolve to a current value. Options: (a) similarity-threshold merge (~0.85) + LLM conflict resolution + dedup (~0.9); (b) **ADD-only extraction with periodic consolidation** — simpler, cheaper, and recent work reports +22% precision / −60% storage vs raw chunking. For v1 we lean (b): append + a consolidation job, no live UPDATE/DELETE in the hot path.
- **Cost:** every extraction is an LLM call. Background + debounce + cheap model keeps it bounded. Benchmarks (LongMemEval, LoCoMo, BEAM) exist if we want to measure recall quality later; Zep currently leads accuracy (~63.8% LongMemEval) and Mem0 leads adoption.
- **Over- vs under-extraction:** over-extract → low precision (noise injected into prompts); under-extract → low recall. Tunable via extraction prompt strength + top-k recall limit. Start conservative (top-3 recall, high-bar extraction).

## 4. Trust & UX — memory must be visible/editable

2026 norm across Claude and ChatGPT memory:
- **Transparent recall** — show when the agent used memory ("searched past conversations"). Builds trust; the screenshotted Claude UX does exactly this.
- **User-owned & editable** — a memory panel to view, add, edit, delete entries, and **toggle memory off** entirely. Power users prefer this granular control; auto-generated entries are noisier than explicit instructions, so editing matters.
- **Caveat from the field:** auto-memory lists drift stale; let users prune. Don't silently accumulate.

→ Matches the locked choice: auto-capture + user-visible/editable panel. Our governance layer (BlackBox carriers) gives the "transparent recall" audit trail for free.

## 5. Chat history (sidebar) — pattern + our actual gap

**Pattern (industry):** conversations auto-saved to a DB, listed in a collapsible sidebar grouped by time ("Today / Yesterday / Previous 7 days"), **auto-generated titles** with manual rename, click to resume, search, scoped to the user. Resume replays the thread; long threads get summarized.

**Our repo's real state (verified by code inspection, not the generic screenshot):**
- Frontend: `frontend/components/chat/ThreadSidebar.tsx` **exists but is inert** — it renders `thread_id` (no human title), and `grep` shows it is **not mounted** in any page/shell.
- BFF: `frontend/app/api/threads/route.ts` has GET+POST; `lib/bff/handlers.test.ts` already asserts "returns the caller's threads only (B6)".
- DB: Drizzle declares `threads` + `thread_messages` tables, but `thread_messages` is **never written/read** in app code.
- Python backend: `agent_ui_adapter/server.py` `_ThreadStore` is an **in-memory placeholder** with only `create`/`get` — **no list endpoint**, no persistence.

→ "Add chat history to the UI" is **completing a scaffold**, not greenfield: add a thread **list** (backend list endpoint + persistence), give threads **titles**, **mount** `ThreadSidebar`, and wire resume. Mirror exactly the memory finding — the skeleton exists, it's just not connected.

**Relationship to memory:** the sidebar resumes a *specific* thread (short-term, checkpointer-backed). It is **not** the long-term memory store. Past conversations are *input* to background memory extraction, but recall pulls from the typed memory stores, not by re-reading old threads. Keep the two seams separate (avoids the common conflation flagged in the research).

---

## 6. Recommendations for our build (feeds the plan update)

1. **Recall (hot path):** keep v1 plan — top-3 semantic recall into `additional_instructions`, memoized at step 0, governed by `MEMORY_RECALLED` carrier.
2. **Capture (background):** add a post-run background extraction pass (cheap model), **debounced per thread**, schema-guided to emit typed items (semantic/episodic/procedural). This replaces the v1 plan's "deterministic distillation of final answer" with the proper typed extractor — **promoting the previously-deferred fact-extraction component into scope** because the user explicitly wants auto-typed detection. Governed by `MEMORY_STORED` carrier(s), one per item with `type` in details (never content).
3. **Storage:** semantic-profile + semantic/episodic collections keyed on `user_id`; procedural deferred to v2 (needs a feedback signal — reuse reflexion critiques). Backend stays the injected `LongTermMemoryService`; add a `type` field to the memory payload/metadata so the panel and recall can filter.
4. **Conflict handling v1:** ADD-only + a consolidation pass (cheap, high-precision); no live UPDATE/DELETE in the hot path.
5. **Trust UI:** a memory panel (view/edit/delete/toggle) + transparent recall indicator, leveraging existing governance carriers for the audit trail. New BFF endpoints for memory CRUD scoped by user (mirror the `/api/threads` "caller's own only" pattern).
6. **Chat-history UI:** complete the scaffold — backend thread **list** + persistence (`thread_messages`), auto-titling, mount `ThreadSidebar`, resume flow, time-grouping.
7. **Build-vs-buy note:** LangMem is the lowest-friction fit (native LangGraph, three-type model, background manager with debounce, `BaseStore` namespacing). Decision for the plan update: **adopt LangMem's *patterns*** on top of our existing `LongTermMemoryService`/`MemoryBackend` seam, or **adopt the LangMem SDK** directly (new dep, but less custom code). Flagged as the one open question for the user.

---

## Sources

- [AI Agent Memory: Types, Implementation & Best Practices 2026 — 47Billion](https://47billion.com/blog/ai-agent-memory-types-implementation-best-practices/)
- [Best AI Agent Memory Frameworks in 2026 — Atlan](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/)
- [Types of AI Agent Memory: Episodic, Semantic, Procedural — Atlan](https://atlan.com/know/types-of-ai-agent-memory/)
- [Beyond Short-term Memory: The 3 Types of Long-term Memory — MachineLearningMastery](https://machinelearningmastery.com/beyond-short-term-memory-the-3-types-of-long-term-memory-ai-agents-need/)
- [AI Agent Memory in 2026: Mem0 vs Zep vs Letta vs Cognee — DEV](https://dev.to/agdex_ai/ai-agent-memory-in-2026-mem0-vs-zep-vs-letta-vs-cognee-a-practical-guide-cfa)
- [Agent Memory at Scale 2026: Letta, Zep, Mem0, LangMem — AgentMarketCap](https://agentmarketcap.ai/blog/2026/04/10/agent-memory-vendor-landscape-2026-letta-zep-mem0-langmem)
- [LangMem — Conceptual Guide (Long-term Memory in LLM Applications)](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [LangMem — Background Quickstart (`create_memory_store_manager`)](https://langchain-ai.github.io/langmem/background_quickstart/)
- [LangMem — Hot Path Quickstart](https://langchain-ai.github.io/langmem/hot_path_quickstart/)
- [Latency vs. Accuracy for LLM Apps / Memory Layer — DEV](https://dev.to/gervaisamoah/latency-vs-accuracy-for-llm-apps-how-to-choose-and-how-a-memory-layer-lets-you-win-both-d6g)
- [Less Context, More Accuracy: Bi-Temporal Memory Engine — arXiv 2606.09900](https://arxiv.org/html/2606.09900)
- [AI Memory Benchmarks 2026: LoCoMo, LongMemEval & BEAM — Mem0](https://mem0.ai/blog/ai-memory-benchmarks-in-2026)
- [Claude Memory vs ChatGPT Memory — MindStudio](https://www.mindstudio.ai/blog/claude-memory-vs-chatgpt-memory-comparison)
- [Conversational UI Design — Patterns (2026) — AI Design Patterns](https://www.aiuxdesign.guide/patterns/conversational-ui)
- [Memory & Personalization — Open WebUI docs](https://docs.openwebui.com/features/chat-conversations/memory/)
- [LangChain Memory Concepts (short vs long-term; semantic/episodic/procedural)](https://docs.langchain.com/oss/python/concepts/memory)
