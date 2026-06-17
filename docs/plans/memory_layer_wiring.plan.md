# Add a Memory Layer to the Agent (wire the orphaned long-term memory into the react loop)

> **Status**: approved 2026-06-17. Implementation plan for wiring the existing (orphaned) long-term memory stack into the agent runtime, behind a default-OFF flag. Branch: `feat/t3-supervisor-fanout` (or a dedicated `feat/memory-layer-wiring`).

## Context

**Why this work exists.** The team set out to "add a memory layer," but investigation shows the long-term memory *primitives already exist and are tested* — they are simply **orphaned**: nothing in the agent runtime ever reads from or writes to them.

What exists today (built, tested, unused by the loop):
- `services/long_term_memory.py` — `LongTermMemoryService` (`store` / `recall` / `search` / `forget`), the `MemoryBackend` Protocol, and `InMemoryMemoryBackend`. Spec: [docs/plan/services/LONG_TERM_MEMORY_PLAN.md](../plan/services/LONG_TERM_MEMORY_PLAN.md).
- `services/memory_backends/sqlite.py` + `in_memory.py` — concrete backends.
- `middleware/ports/memory_client.py` (`MemoryClient` async port) + `middleware/adapters/memory/mem0_cloud_client.py` (`Mem0CloudClient`), wired **only** in [middleware/composition.py](../../middleware/composition.py) for the BFF ring (v3/v2 profiles, `MEM0_API_KEY`).

**The gap.** `grep` confirms **zero** memory references in [orchestration/react_loop.py](../../orchestration/react_loop.py), [orchestration/state.py](../../orchestration/state.py), `cli.py`, or `services/base_config.py`. The agent never recalls relevant context before reasoning and never persists what it learned after finishing. Two memory worlds exist side by side and never meet:
- **Short-term (thread-scoped):** `AgentState` + the LangGraph checkpointer + `services/summarizer.py` trajectory compaction. *Already works.*
- **Long-term (cross-session, per-user):** the orphaned service above. *Never invoked.*

**Intended outcome.** Connect the existing `LongTermMemoryService` into the react loop so that, behind a default-OFF flag, the agent (a) **recalls** relevant user memories before it reasons and injects them into the system prompt, and (b) **stores** salient facts at run-end — fully governed and observable. This is a *wiring/activation* task, not a green-field build.

**Vocabulary** (anchored to [LangChain memory concepts](https://docs.langchain.com/oss/python/concepts/memory)) maps cleanly onto repo primitives:
- **Short-term / thread-scoped** → `AgentState` + checkpointer + summarizer (exists).
- **Long-term / cross-session, namespaced by user** → `LongTermMemoryService` keyed on `user_id` (this plan activates it).
- **Semantic** (facts about the user) → primary target of recall/store v1.
- **Episodic** (past events/how prior tasks were solved) → v1.5, store run outcome summaries.
- **Procedural** (rules/strategies that worked) → v2, builds on reflexion critiques (`reflections` in state).
- Writing strategy: **hot-path recall** (read before reasoning, low latency, top-3) + **end-of-run write** (a small synchronous write at completion; background/async write deferred to v1.5).

---

## Scope (locked with user)

- **Wire up what exists** — no new memory engine, no new backend in v1. Reuse `LongTermMemoryService` + `InMemoryMemoryBackend` (local/tests) and the already-wired `Mem0CloudClient` path for prod.
- **All three memory dimensions acknowledged**, phased: v1 = semantic long-term (recall + store). Short-term is already handled (documented, not re-built). Episodic/procedural are designed-for but deferred (clear extension seams left in place).
- **Default-OFF, shadow-first flag** — add `MEMORY_ENABLED` mirroring `REFLEXION_ENABLED` / `T3_FANOUT_ENABLED`. Prod parity preserved; a dev/stress revision flips it on. Matches the repo's tiered-loops discipline.

**Non-goals (v1):** fact-extraction LLM component (store salient text deterministically from the final answer + task, not via a new judge); background/async writes; procedural/episodic stores; backend swap to pgvector (tracked separately via SPIKE_C).

---

## Architecture constraints (test-enforced — must hold)

From [AGENTS.md](../../AGENTS.md), verified by `tests/architecture/`:
1. **Components & orchestration nodes stay framework- and SDK-clean.** The node must NOT import a backend or the service module directly with wiring logic — it receives an injected callable/service.
2. **The service is injected at the composition root**, never imported by a node. `build_components` / `build_graph` already follow this pattern (goal_judge_config_reader, tool_registry, agent_facts_registry are all injected this way).
3. **Privacy invariant:** payload/memory content NEVER appears in log lines — only `user_id` + `key`. Already enforced in `long_term_memory.py`; the new call sites must not log content.
4. **Governance:** memory access is a runtime decision → emit BlackBox carriers so the trace stays truthful (the four-pillar audit will check this). Use the existing `BlackBoxRecorder` / `TraceEvent` path. Open question Q-M1 (TrustTraceRecord wrapper) stays deferred.

---

## Design: where memory plugs in

### Recall (hot path) — `call_llm_node`, [orchestration/react_loop.py:1324](../../orchestration/react_loop.py)
The system prompt is already rendered with `additional_instructions=planning_instructions`, and reflexion critiques are *already* folded into that same string just above (lines 1303–1322). This is the proven injection seam (Pattern H6). Plan:
- At **step 0 only** (avoid re-querying every loop iteration — same memoize-once discipline as `task_understanding`), if memory is enabled and a `user_id` is present, call `memory.search(user_id, query=task_input, limit=3)`.
- Format the top-3 records into a short "Relevant context you remember about this user:" block and **append to `planning_instructions`** before `render_prompt`. `prompts/system_prompt.j2:17` already consumes `{{ additional_instructions }}` — no template change needed.
- **Graceful degradation:** wrap in try/except; on any `MemoryBackendError`/timeout, log a warning (no content) and continue with zero memories. Memory must never fail a run.
- Emit a BlackBox `MEMORY_RECALLED` carrier (`{user_id, count, query_len}` — never content).
- Persist the recalled block into state once (new `recalled_memories: str` field, memoized by `recalled_memories_task_id`) so re-entry laps reuse it without re-querying.

### Store (end of run) — after `evaluate` → done, alongside `reasoning_recap`
- When the run completes successfully (terminal `done` branch / `reasoning_recap_node`, [orchestration/react_loop.py:~457](../../orchestration/react_loop.py) region), if enabled and `user_id` present, write one salient memory: `memory.store(user_id, key=task_id, payload={...})` **or** the async port `memory_client.add(user_id, content=...)` depending on profile (see wiring note).
- v1 content = a deterministic distillation: `task_input` + `last_final_answer` (already in state). No new LLM call.
- Wrap in try/except (never fail the run); emit `MEMORY_STORED` carrier (`{user_id, key}` — never content).

### user_id is already available
`LangGraphRuntime.run(..., identity: AgentFacts)` already derives `eval_user_id = identity.owner` and injects `user_id` into the graph config ([agent_ui_adapter/adapters/runtime/langgraph_runtime.py:163,202](../../agent_ui_adapter/adapters/runtime/langgraph_runtime.py)). The nodes read `config["configurable"]` / state; thread that `user_id` into `AgentState` at run start so the recall/store nodes can read it. No new identity plumbing.

---

## Wiring note: which memory abstraction does the loop use?

There are two parallel abstractions today. To keep the loop framework-clean and avoid async-in-sync-node hazards, **v1 injects the sync `LongTermMemoryService`** (not the async `MemoryClient`):
- **Local/dev/tests:** `LongTermMemoryService(InMemoryMemoryBackend())` — zero new deps, fast tests.
- **Prod:** add a thin `Mem0MemoryBackend` adapter under `services/memory_backends/mem0.py` that implements the sync `MemoryBackend` Protocol by delegating to the existing `Mem0CloudClient` (the SDK is sync under the hood; the async wrapper is a middleware concern). This keeps the existing Mem0 wiring as the source of truth and honors the "swap backend = one file" promise. *If the team prefers to reuse the async `MemoryClient` directly, the alternative is making the recall/store nodes async and awaiting it — they are already `async def`, so this is viable; the sync-service route is recommended for v1 to match `long_term_memory.py`'s tested surface.*

This decision is the one genuinely open implementation choice — resolved by the early spike (Verification step 1).

---

## Files to change

**New:**
- `services/memory_backends/mem0.py` — `Mem0MemoryBackend(MemoryBackend)` delegating to `Mem0CloudClient` (prod backend; only if sync-service route chosen).
- `tests/services/memory_backends/test_mem0_backend.py` — conformance against the `MemoryBackend` Protocol (mock SDK client).
- `tests/orchestration/test_memory_wiring.py` — recall injects into system prompt; store fires at run-end; flag-OFF is a no-op; backend failure degrades gracefully; content never logged.

**Modified (representative pattern — inject a service, read a flag, call at the two seams):**
- `services/base_config.py` — add `memory_enabled: bool = False` to `AgentConfig` (mirrors `reflexion_enabled`).
- `middleware/composition.py` — add `MEMORY_ENABLED` to `AgentRuntimeSettings` (mirror `reflexion_enabled` parse at lines 399/438); construct the `LongTermMemoryService` in `build_components` and pass it through `build_runtime_graph` → `build_graph` (new injected param, like `goal_judge_config_reader`).
- `orchestration/react_loop.py` — accept injected `memory_service` in `build_graph`; add recall block in `call_llm_node` (~1307–1326) and store block in the run-end/`reasoning_recap` path; add the two BlackBox carriers.
- `orchestration/state.py` — add `user_id: str`, `recalled_memories: str`, `recalled_memories_task_id: str` (plain last-write-wins keys; follow the existing memoize-by-task_id comment style).
- `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` — thread `user_id` (`identity.owner`) into the initial graph input/state.
- `services/governance/black_box.py` — add `MEMORY_RECALLED` / `MEMORY_STORED` to the `EventType` enum (governance carrier vocabulary; the carrier spec drift-guard in `trust/governance_carrier_spec.py` may need the new wire strings — check `tests/trust/test_governance_carrier_spec.py`).
- `logging.json` — add the `services.long_term_memory` logger block per the existing plan §4 (if not already present).
- `cli.py` — optional: accept `--user-id` / read env so the CLI path can exercise memory locally.

**Reused as-is (do not reinvent):** `LongTermMemoryService`, `MemoryBackend`, `InMemoryMemoryBackend`, `Mem0CloudClient`, `MemoryRecord`, `prompts/system_prompt.j2` (`additional_instructions`), the `BlackBoxRecorder`/`TraceEvent` carrier path, and the flag-parsing pattern in `AgentRuntimeSettings`.

---

## Verification

1. **Spike first (½ day):** confirm the wiring-note decision (sync `LongTermMemoryService` + `Mem0MemoryBackend` vs await the async `MemoryClient` in the already-async nodes). Pick one; the rest of the plan is identical downstream.
2. **Unit/contract tests** (`pytest`, <10s budget per the memory plan):
   - Flag OFF → no `search`/`store` calls, system prompt unchanged (regression guard).
   - Flag ON → `call_llm_node` injects recalled text into `additional_instructions`; run-end calls `store` once with the right `user_id`/`key`.
   - Backend raises → run completes, warning logged, no content in logs (privacy invariant test reusing the magic-string assertion from `tests/services/test_long_term_memory.py`).
   - Recall is memoized (one `search` per task, not per loop lap).
3. **Architecture tests:** run `tests/architecture/` — confirm no new disallowed imports in components/orchestration; service only injected at composition root.
4. **Governance trace check:** run a local task with memory ON, then use the `governance-trace-audit` skill on the resulting trace to confirm `MEMORY_RECALLED`/`MEMORY_STORED` carriers appear and the four-pillar verdict stays healthy.
5. **Local end-to-end:** `python -m agent.cli --user-id demo "remember I prefer metric units"` then a second run `"what units do I prefer?"` — second run's system prompt should carry the recalled fact (inspect via logs/trace).
6. **Full suite:** `pytest` — assert no regressions against the current 3032-pass baseline before considering it done.
7. **Rollout:** ship default-OFF; flip `MEMORY_ENABLED=true` on a dev/stress Cloud Run revision (out-of-band `--tag` revision, prod untouched — per the deploy-gcp stress-revision pattern) to validate live before any prod promotion.

---

## Deferred (designed-for, not built in v1)
- **Episodic memory:** store per-run outcome summaries (reuse `reasoning_summary`) for few-shot recall on similar future tasks.
- **Procedural memory:** persist reflexion critiques (`reflections`) that led to success as reusable strategies.
- **Background/async writes** (LangChain "in the background" strategy) to remove the end-of-run write from the latency path.
- **Fact-extraction component** to decide *what* is worth remembering (vs the v1 deterministic distillation).
- **Backend graduation** Mem0 → pgvector-on-Neon per SPIKE_C latency debt (~447ms p95 search).
