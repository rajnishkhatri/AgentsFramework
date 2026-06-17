# Add a Memory Layer to the Agent (wire the orphaned long-term memory into the react loop)

> **Status**: All three phases **re-approved as scoped 2026-06-17** (P1 runtime wiring → P2 typed auto-capture, shadow-first behind the eval enable-policy → P3 chat-history + memory UI). Build-vs-buy **resolved**: adopt LangMem *patterns* on the existing seam, not the SDK (no new dependency, one memory abstraction). Compliance binding (per-phase invariant-cited checklists, frontend F-R + STYLE_GUIDE_FRONTEND, eval_capture on all memory seams), governance-triangle four-pillar binding, tier-compatibility (T1/T2/T3), and OBP/ports-and-adapters/layer-separation audit all added 2026-06-17. Branch: `feat/memory-layer-wiring`.
>
> **PHASE 1 IMPLEMENTED 2026-06-17 (uncommitted, on branch).** Test-first build complete and green. Spike resolved → sync `LongTermMemoryService` route (see Wiring note). Built: `components/memory_context.py` (OBP-1 `render_recall_block`/`build_store_payload` + OBP-2 `should_recall` + `memory_subject` cross-user-leak guard); recall in `route_node` (universal seam, memoized, `MEMORY_RECALLED` carrier + `eval_capture` + graceful-degrade via `await asyncio.to_thread`); `call_llm`/`supervisor` read `recalled_memories`; `_route_fanout` Send payload (OBP-M1); store in `reasoning_recap_node` (`_maybe_store_memory`, reads `last_final_answer` = tier-agnostic, `MEMORY_STORED` carrier); two non-required `EventType` members; `AgentState` fields; `AgentConfig.memory_enabled=False`; composition `MEMORY_ENABLED` flag + constructs `LongTermMemoryService(InMemoryMemoryBackend())`; `langgraph_runtime` threads `user_id=identity.owner`. **Two enum-completeness consumers updated** (required, surfaced by the full suite): `black_box_publisher` mapping (`memory.recalled`/`memory.stored` → `span`) + `dev_seed` corpus. **Real bug a failure-path test caught:** `"anonymous"` must not be a memory subject (cross-user pooling) → `memory_subject()` guard. Tests green: L1 20/20, L4 wiring 7/7, T3 sim `test_fanout_is_not_memory_blind`, all enum-consumer + drift-guard 170/170, full fast suite no-regression. **`Mem0MemoryBackend` deferred** (ask-first new horizontal service; default-OFF flag keeps prod parity meanwhile). **Still pending:** governance-trace-audit gate (Verification 4), local e2e (Verification 5), commit.
>
> **Research backing**: [docs/research/memory_and_chat_history_best_practices_2026.md](../research/memory_and_chat_history_best_practices_2026.md). The three-type model (semantic/episodic/procedural), background-debounced auto-capture, ADD-only+consolidation conflict handling, and the visible/editable memory-panel UX are all confirmed 2026 best practice (LangMem, Mem0, Zep, Claude/ChatGPT memory).
>
> **Compliance backing**: [docs/Architectures/](../Architectures/). Each phase below carries the paste-into-PR checklist from [BACKEND_PR_CHECKLISTS.md](../Architectures/BACKEND_PR_CHECKLISTS.md) (Checklists 2/4/7) and the frontend invariants from [FRONTEND_ARCHITECTURE.md](../Architectures/FRONTEND_ARCHITECTURE.md) (F-R1..F-R9) + the rule families in [STYLE_GUIDE_FRONTEND.md](../STYLE_GUIDE_FRONTEND.md). Invariant IDs (I-1..I-14) are defined in [BACKEND_SOLUTION_ARCHITECTURE.md](../Architectures/BACKEND_SOLUTION_ARCHITECTURE.md).
>
> **Phases:**
> - **Phase 1 — Runtime wiring (semantic recall + store).** Original scope below. *Approved.*
> - **Phase 2 — Typed background auto-capture.** Promote the deferred fact-extraction component into scope: a post-run, debounced, schema-guided LLM pass that emits typed (semantic/episodic/procedural) memory items. *Per user request "auto-detect human memory types."*
> - **Phase 3 — UI: chat-history sidebar + memory panel.** Complete the inert frontend scaffold (`ThreadSidebar`, `/api/threads`, `thread_messages`) and add a user-visible/editable memory panel with transparent-recall indicator.

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

## Architecture compliance (test-enforced — must hold)

These are the invariants from [docs/Architectures/](../Architectures/) that this work touches, with their enforcing test. They are non-negotiable: if a `tests/architecture/` test fails, fix the placement — do not silence the test. Each phase below restates the *applicable* subset as a paste-into-PR checklist.

### Backend invariants in play (I-x)

| ID | Rule (verbatim intent) | Where it binds this work | Enforced by |
|----|------------------------|--------------------------|-------------|
| **I-1** | Dependencies flow downward only: orchestration → components → services → trust. | Recall/store nodes import only `components/` + `services/`; never a peer `orchestration/` file. | `test_dependency_rules.py` ✅ |
| **I-3** | `components/` must not import `langgraph` / `langchain*`. | Phase 2 `components/memory_extractor.py` must be framework-clean. | `test_components_no_framework_imports` ✅ |
| **I-4** | `services/` must not import framework packages (except `services/llm_config.py`). | `Mem0MemoryBackend` and any new service code stay framework-clean. | `test_services_no_framework_imports_except_llm_config` ✅ |
| **I-5** | `services/` must not import from `components/`. | `LongTermMemoryService` / backends must not reach up into `components/`. | `test_services_does_not_import_components` ✅ |
| **I-7** | Orchestration nodes are thin wrappers — all logic delegates to `components/`/`services/`. | Recall/store seams stay ≤ ~30 lines; the injected `memory_service` does the work. | _(proposed test G-1)_ ⚠ — hold by review |
| **I-9** | SDKs (LangGraph) appear **only** in `agent_ui_adapter/adapters/runtime/`. | Phase 3 thread-list endpoint + ThreadStore persistence must keep SDK types inside `adapters/`. | `test_agent_ui_adapter_layer.py` ✅ |
| **I-10** | `middleware/` SDK imports (WorkOS, Mem0, Langfuse) confined to `middleware/adapters/`. | The existing `Mem0CloudClient` wiring is the only place the Mem0 SDK appears; the sync-backend adapter must not leak it upward. | `test_middleware_layer.py` ✅ |
| **I-11** | **Every LLM invocation routes through `services.eval_capture.record()` with `user_id` + `task_id`** (Pattern H5). | **Per user decision: wrap every memory recall/store seam with `eval_capture.record()` for uniform observability — even the v1 deterministic seams that make no LLM call — and the Phase-2 extractor LLM call records full token/cost/latency.** See note below. | _(proposed test G-2)_ ⚠ — hold by review |
| **I-12** | Every prompt is a `.j2` in `prompts/` via `PromptService.render_prompt()` — no hardcoded prompt strings. | Phase 2 extraction prompt lives in `prompts/memory_extractor.j2`; no inline prompt text anywhere. | _(proposed test G-3)_ ⚠ — hold by review |
| **I-14** | Trust kernel types are `frozen` when they participate in signing/audit attribution. | Only relevant if `MemoryRecord`/carrier types move into `trust/` — they should not; keep memory types in `services/`. | convention (G-11) |

### Cross-cutting rules this work must satisfy

1. **Constructor injection at the composition root (H7).** The `LongTermMemoryService` is built in `build_components` and threaded through `build_runtime_graph` → `build_graph` as an injected param (mirror `goal_judge_config_reader` / `tool_registry`). No node imports a backend or constructs the service. (Checklist 2: "Constructor injection only. No module-level singletons.")
2. **Privacy invariant.** Payload/memory content NEVER appears in a log line — only `user_id` + `key` (+ `type`/`count`/`salience` in Phase 2). Already enforced in `long_term_memory.py`; the new call sites must not log content. Verified by the magic-string assertion in `tests/services/test_long_term_memory.py`.
3. **Governance carriers.** Memory access is a runtime decision → emit BlackBox `MEMORY_RECALLED` / `MEMORY_STORED` `TraceEvent`s via the existing `BlackBoxRecorder` path so the four-pillar audit stays truthful. Open question Q-M1 (TrustTraceRecord wrapper) stays deferred. (Checklist 4: "Black box + phase logger emissions at significant decision points.")
4. **eval_capture on memory seams (I-11, user decision).** Per the 2026-06-17 decision, *every* memory recall/store seam calls `eval_capture.record()` with `target` (e.g. `"memory_recall"` / `"memory_store"` / `"memory_extract"`), `user_id`, `task_id`. For the v1 deterministic seams there is no token/cost/latency to report (record zeros / latency of the backend call); the Phase-2 extractor LLM call reports real token counts, cost, and latency. This is heavier than I-11 strictly requires (it binds only LLM calls) but gives the per-user memory-activity analysis the meta-judge can consume — a deliberate, documented over-application, not a misread of the invariant.
5. **Style-guide patterns.** New service/component code follows the H1–H7 / V1–V6 catalog: Pydantic outputs with `ConfigDict(extra="forbid")` for non-trivial results (V6); per-concern logger `logging.getLogger("services.<name>")` with a `logging.json` route (H4); failure-path tests written first (TAP-4); ≤ 3 mocks per test (TAP-2).

---

## Governance-triangle compliance (the four pillars must stay truthful) — must hold

Source of intent: [governanaceTriangle/01_explainability_fundamentals.md](../../governanaceTriangle/01_explainability_fundamentals.md) (the four pillars) and the audit contract in [docs/skills/governance-trace-audit/SKILL.md](../skills/governance-trace-audit/SKILL.md). The contract is: **a reader must be able to answer "what happened / who / what was checked / why" from the memory-touched trace alone.** Adding memory adds two new runtime decisions (recall, store) — both must leave honest carriers so the post-hoc audit and the inline carrier gate stay healthy.

### How memory maps onto the four pillars

| Pillar | Question | What memory must carry | Carrier |
|--------|----------|------------------------|---------|
| **Recording** (BlackBox) | *What happened?* | recall ran (count, query_len), store ran (key) — **never content** | new `MEMORY_RECALLED` / `MEMORY_STORED` `TraceEvent`s; the Phase-2 extractor LLM call also leaves a `step_executed` with tokens/cost (the only reliable token carrier — audit Step 2 Recording). |
| **Identity** (AgentFacts) | *Who did it?* | the `user_id` the memory is namespaced to = `identity.owner` | already on `task_started`; the memory carriers echo `user_id` so recall/store attribute to the same subject. **No memory write may use a `user_id` that isn't the run's subject** (cross-user-leak guard). |
| **Validation** (GuardRails) | *What was checked?* | recall/store failures surface, never silently swallowed | the graceful-degrade `try/except` logs a warning **and** the backend-failure path must remain visible (a swallowed `MemoryBackendError` with no carrier = a silent failure the audit Step 2 Validation check flags). Emit the carrier even on the degraded path (count 0 / `error_kind`, never content). |
| **Reasoning** (PhaseLogger) | *Why was it done?* | why these memories were injected / why this fact was stored | recall carrier names the query; Phase-2 store carrier names `type`/`salience` (the extractor's *why*). v1 deterministic store needs no rationale beyond "run completed". |

### Two compliance rules the design must encode (learned from the carrier gate)

1. **Memory carriers ENRICH Recording; they are NOT a new per-phase pillar requirement.** The inline carrier gate ([trust/governance_carrier_spec.py](../../trust/governance_carrier_spec.py)) keys required carriers by `WorkflowPhase`. Recall runs in `route_node` → `PH_ROUTING`, store in the completion path → `PH_COMPLETION`. **Do NOT add `MEMORY_RECALLED`/`MEMORY_STORED` to `default_spec()` as required carriers** — memory is flag-gated and absent on most runs, so requiring them would make the gate **false-positive on every non-memory run** (the exact GG-4 class the spec's resumed-Identity exemption was built to avoid). They are optional enrichment carriers: present when memory ran, absent (correctly) when it didn't. `PH_ROUTING` keeps its single requirement (`model_selected`); `PH_COMPLETION` keeps `eval.goal_judge`.
2. **The new `EventType` members feed the drift-guard, not the rubric.** `EventType.MEMORY_RECALLED` / `MEMORY_STORED` are added in `services/governance/black_box.py`. The carrier-spec drift-guard test (`tests/trust/test_governance_carrier_spec.py`) asserts the spec's wire strings still match real enum members — adding two **non-required** members does not change `ALL_PHASE_VALUES` or any requirement tuple, so that test stays green by construction. (If a future phase *does* want to require a memory carrier, that is a deliberate `SPEC_VERSION` bump + rubric edit in the skill first — never a silent spec change.)

### Verification via the audit skill (the post-implementation gate)

Per the skill's "use it as the verification step after any telemetry-touching change," the governance trace check (Verification step 4) is **mandatory, not optional**, for this work. The acceptance bar:
- A memory-ON run's trace shows `MEMORY_RECALLED` (count, query_len) and `MEMORY_STORED` (key) carriers, **content absent** (the skill's privacy + zero-carrier checks).
- The four-pillar verdict stays **COMPLIANT** (or COMPLIANT-WITH-FINDINGS only for pre-existing run-level findings, never a new memory-induced FAIL).
- A memory-OFF run's trace is **byte-identical** to today (no carriers, gate unchanged) — the shadow-first guarantee, confirmed by the audit reading "nothing actionable."
- The inline carrier gate emits **no** `source: "carrier_gate"` / `would_enforce: true` alert attributable to memory (it would mean we accidentally made a memory carrier a requirement).

---

## Tier compatibility (T1 ReAct / T2 Reflexion / T3 Supervisor fan-out) — must hold

The graph is **one** `StateGraph` with three tiers gated by flags; memory must behave correctly on all three, not just the T1 hot path. Verified topology ([orchestration/react_loop.py:2758–2820](../../orchestration/react_loop.py)):

```
START → guard_input → route ─┬─(direct)──────→ call_llm ⇄ execute_tool → evaluate ─┬─(done)→ reasoning_recap → END
                             │                                                     └─(reflect)→ reflect → route   ← T2 loop
                             └─(supervisor)→ supervisor ─┬─(fan_out)→ worker* → join → evaluate
                                                         └─(decline)──────────────→ call_llm
```

| Tier | Path through the graph | Recall behaviour required | Store behaviour required |
|------|------------------------|---------------------------|--------------------------|
| **T1 ReAct** (`t3_fanout` OFF or `direct`) | `route → call_llm ⇄ execute_tool → evaluate → done` | recall once, injected into the `call_llm` system prompt | run-end store of `last_final_answer` |
| **T2 Reflexion** (`reflexion_enabled`, escalate) | `evaluate → reflect → route → call_llm …` (loops) | **recall must fire ONCE per run, not once per reflexion lap** — `call_llm` re-executes every lap | store fires once at terminal `done` (unchanged) |
| **T3 Supervisor fan-out** (`t3_fanout_enabled`, `fan_out`) | `route → supervisor → worker* → join → evaluate → done` — **bypasses `call_llm` entirely** | **`call_llm`-only recall would silently skip every fan-out run** — supervisor + workers each call the LLM with no recalled context | run-end store of the **join's** `last_final_answer` (already in state — works) |

**Decision (resolves the T3 gap): move the recall seam UP to `route_node`, not `call_llm_node`.** `route` is the one node *every* tier passes through (`START → guard_input → route` is universal; both the `direct` and `supervisor` forks descend from it, and the T2 `reflect → route` loop re-enters it). Recall executed once in `route` and persisted to `recalled_memories` state is then readable by `call_llm` (T1/T2), `supervisor`, and every `worker` (T3) — one seam, tier-agnostic, no duplication.

- **T1/T2 consumer:** `call_llm_node` appends `state["recalled_memories"]` to `planning_instructions` before `render_prompt` (the seam the plan already identified — now a *reader* of state, not the place recall *runs*).
- **T3 consumer:** the `supervisor` decompose prompt and each `worker` objective prompt include the recalled block (workers already carry `user_id` in their Send payload — [react_loop.py:2495,2547](../../orchestration/react_loop.py); a Phase-1.5 follow-up may add it to the worker prompt, but **recall must at minimum reach the supervisor** so fan-out runs are not memory-blind).
- **Memoization (T2 guard):** recall is memoized by `recalled_memories_task_id`; reflexion re-entry preserves `task_id`, so the `task_id`-unchanged → reuse check means recall queries the backend **once per run** even across many `reflect → route` laps. This is the load-bearing T2 correctness property — assert it (Verification step 2: "one `search` per run, not per lap, incl. reflexion re-entry").

> **AGENTS.md ⚠️ ask-first note:** putting recall in `route_node` is an *inline block in an existing node*, not a new graph node — so it does **not** fire the "new graph node" gate (same as the original `call_llm` plan). Confirmed against the topology above.

---

## Design: where memory plugs in

### Recall (universal seam) — `route_node` ([orchestration/react_loop.py:2730](../../orchestration/react_loop.py)), consumed downstream
Recall **runs** in `route_node` (the universal seam — see Tier compatibility above) and is **consumed** wherever a prompt is built. The proven injection mechanism is unchanged (Pattern H6): `call_llm_node` already renders `additional_instructions=planning_instructions` with reflexion critiques folded in just above (lines 1303–1322). Plan:
- In `route_node`, at **step 0 / first entry only** (memoized by `recalled_memories_task_id` so reflexion re-entry and fan-out re-runs reuse it — never re-query per lap), if memory is enabled and a `user_id` is present, call `memory.search(user_id, query=task_input, limit=3)` and write the formatted block to `state["recalled_memories"]`.
- **T1/T2:** `call_llm_node` appends `state["recalled_memories"]` to `planning_instructions` before `render_prompt`. `prompts/system_prompt.j2:17` already consumes `{{ additional_instructions }}` — no template change needed.
- **T3:** `supervisor_node` (and, as a Phase-1.5 extension, `worker_node`) include `state["recalled_memories"]` in their prompts so fan-out runs are not memory-blind.
- **Graceful degradation:** wrap in try/except; on any `MemoryBackendError`/timeout, log a warning (no content) and continue with zero memories. Memory must never fail a run on any tier.
- Emit a BlackBox `MEMORY_RECALLED` carrier (`{user_id, count, query_len}` — never content) once, at the `route` seam.
- **eval_capture (I-11, per user decision):** call `eval_capture.record(target="memory_recall", user_id=..., task_id=..., latency=<search ms>)` even though recall makes no LLM call — uniform observability for per-user memory-activity analysis.
- Persist the recalled block into state once (new `recalled_memories: str` field, memoized by `recalled_memories_task_id`) so all three tiers' downstream nodes reuse it without re-querying.

### Store (end of run) — terminal `done` branch, `reasoning_recap_node`
- The terminal `done` branch is **shared by all three tiers** (`evaluate → done → reasoning_recap → END`, [react_loop.py:2808–2820](../../orchestration/react_loop.py)). T1/T2 produce `last_final_answer` from `call_llm`; **T3 produces it from `join_node`** ([react_loop.py:2722–2725](../../orchestration/react_loop.py) sets `last_final_answer = joined`). Because the store reads `last_final_answer` from state, **the same store seam works for all three tiers unchanged** — it captures the joined fan-out answer just as it captures a T1 answer.
- When the run completes successfully (terminal `done` branch / `reasoning_recap_node`), if enabled and `user_id` present, write one salient memory: `memory.store(user_id, key=task_id, payload={...})` **or** the async port `memory_client.add(user_id, content=...)` depending on profile (see wiring note).
- v1 content = a deterministic distillation: `task_input` + `last_final_answer` (already in state, tier-agnostic). No new LLM call.
- Wrap in try/except (never fail the run); emit `MEMORY_STORED` carrier (`{user_id, key}` — never content).
- **eval_capture (I-11, per user decision):** call `eval_capture.record(target="memory_store", user_id=..., task_id=..., latency=<store ms>)` at the seam (deterministic in v1; the Phase-2 extractor adds real token/cost).

### user_id is already available
`LangGraphRuntime.run(..., identity: AgentFacts)` already derives `eval_user_id = identity.owner` and injects `user_id` into the graph config ([agent_ui_adapter/adapters/runtime/langgraph_runtime.py:163,202](../../agent_ui_adapter/adapters/runtime/langgraph_runtime.py)). The nodes read `config["configurable"]` / state; thread that `user_id` into `AgentState` at run start so the recall/store nodes can read it. No new identity plumbing.

---

## Wiring note: which memory abstraction does the loop use?

There are two parallel abstractions today. To keep the loop framework-clean and avoid async-in-sync-node hazards, **v1 injects the sync `LongTermMemoryService`** (not the async `MemoryClient`):
- **Local/dev/tests:** `LongTermMemoryService(InMemoryMemoryBackend())` — zero new deps, fast tests.
- **Prod:** add a thin `Mem0MemoryBackend` adapter under `services/memory_backends/mem0.py` that implements the sync `MemoryBackend` Protocol by delegating to the existing `Mem0CloudClient` (the SDK is sync under the hood; the async wrapper is a middleware concern). This keeps the existing Mem0 wiring as the source of truth and honors the "swap backend = one file" promise. *If the team prefers to reuse the async `MemoryClient` directly, the alternative is making the recall/store nodes async and awaiting it — they are already `async def`, so this is viable; the sync-service route is recommended for v1 to match `long_term_memory.py`'s tested surface.*

This decision is the one genuinely open implementation choice — resolved by the early spike (Verification step 1).

> **Spike RESOLVED (2026-06-17 — sync `LongTermMemoryService` route confirmed).** Read of [middleware/adapters/memory/mem0_cloud_client.py](../../middleware/adapters/memory/mem0_cloud_client.py) confirms the `mem0ai` SDK client is **synchronous** — `Mem0CloudClient` only wraps it in `asyncio.to_thread()` because it lives in the async FastAPI BFF ring. So the loop depends on **one** port (the sync `MemoryBackend` Protocol), and the prod `Mem0MemoryBackend` is a thin adapter over the already-sync `_sync_add`/`_sync_search` (the Mem0 SDK stays confined to `middleware/adapters/` per I-10 — the backend delegates to the existing client, never imports `mem0`). Awaiting the async `MemoryClient` was rejected: it would drag a *second* memory abstraction into the loop (the exact coupling the OBP/ports audit closed). **One async refinement to the sketch:** because the node is `async def` and the prod backend's `search`/`store` do blocking network I/O, the OBP-3 block calls them via `await asyncio.to_thread(memory_service.search, ...)` so the event loop stays free; the `InMemoryMemoryBackend` path is fast enough that `to_thread` is harmless. This keeps the sync port *and* event-loop safety.

---

## OBP / ports-and-adapters / layer separation (no coupling) — must hold

The recall/store wiring must obey the same four-rule OBP split every loop tier obeys ([design.md §OBP](planning_pipeline_tiered_loops.design.md)), or it couples orchestration to memory logic. The split for memory:

| OBP rule | Memory responsibility | Lands in | Must NOT |
|----------|----------------------|----------|----------|
| **OBP-1** (generation/logic) | format top-k records → the "Relevant context…" block; distill `task_input`+`last_final_answer` → store payload; the graceful-degrade fallback | a **pure helper** — `components/memory_context.py` (`render_recall_block(records) -> str`, `build_store_payload(task_input, answer) -> dict`), framework-clean | import `langgraph`/`orchestration`/`AgentState`; call the backend itself |
| **OBP-2** (the decision) | "recall now?" = `enabled ∧ user_id present ∧ not-memoized-this-task` | a **pure predicate** taking scalars — `should_recall(enabled: bool, user_id: str, memoized: bool) -> bool` (same file) | read `AgentState` |
| **OBP-3** (node wrapper) | unpack state → call predicate → call `memory_service.search` → call the OBP-1 formatter → return a state delta | the inline block in `route_node` / the store block in the run-end path | contain any formatting/selection *logic* — it only adapts state ↔ service ↔ helper, exactly like `route_node`'s existing `select_model` / `select_planning_depth` calls |
| **OBP-4** (edge) | none — recall/store add **no new edge** (recall rides the existing `route` node, store rides the existing `done → reasoning_recap` edge) | n/a | — |

**This is the fix for the only real coupling risk:** the node must not inline the search-result formatting or the degrade policy. `route_node` already demonstrates the correct shape — it calls pure `select_model(...)`/`select_planning_depth(...)` and only assembles state. Recall follows suit: `route_node` calls `should_recall(...)` then `memory_service.search(...)` then `render_recall_block(...)`, and writes the result to `recalled_memories`. No memory logic lives in orchestration.

**Ports & adapters — name the one port the loop depends on.** The loop depends on **exactly one** memory abstraction: the sync **`MemoryBackend` Protocol** (the port), consumed via `LongTermMemoryService` (the injected collaborator). Everything else is an adapter behind that port:
- `InMemoryMemoryBackend` / `SqliteMemoryBackend` — adapters (local/test).
- `Mem0MemoryBackend` — adapter that **wraps** the existing async `Mem0CloudClient`; the async `MemoryClient` port stays a *middleware* concern (BFF ring) and is **not** a second port the loop sees. The loop never imports `MemoryClient`, never imports a backend directly, never imports the Mem0 SDK (I-10 keeps the SDK in `middleware/adapters/`). One port into the loop; the two-abstraction split stays a layer boundary, not a coupling.

**OBP-M1 (T3 worker isolation) — recall rides the Send payload, not `AgentState`.** A worker receives a plain dict `Send` payload, never `AgentState` ([react_loop.py:2485–2497](../../orchestration/react_loop.py)). So "workers see recalled memory" means **adding `recalled_memories` to the `Send` payload dict** in `_route_fanout` (alongside the existing `objective`/`user_id`/`constraints`), exactly as those fields already ride. The worker reads `payload["recalled_memories"]`, never reaches into shared state. The supervisor (which *does* get `AgentState`) reads `state["recalled_memories"]` directly — OBP-3-clean.

**Layer-separation summary (what imports what):**
- `components/memory_context.py` → imports `services`/`trust` types only; **no** `langgraph`/`orchestration`/`AgentState` (I-1, I-3; enforced by `test_components_no_framework_imports` + `test_components_does_not_import_orchestration`).
- `services/memory_backends/mem0.py` → imports the `MemoryBackend` Protocol + the Mem0 client port; **no** framework, **no** `components` (I-4, I-5).
- `orchestration/react_loop.py` → imports the OBP-1 helper + receives the injected `LongTermMemoryService`; **no** backend import, **no** memory engine construction (H7, I-1).
- `trust/` → untouched (memory types are not trust-kernel types; carrier `EventType` lives in `services/governance/`, not `trust/`).

---

## Files to change

**New:**
- `components/memory_context.py` — the **OBP-1 pure helpers**: `render_recall_block(records) -> str`, `build_store_payload(task_input, answer) -> dict`, and the **OBP-2 predicate** `should_recall(enabled, user_id, memoized) -> bool`. Framework-clean (no `langgraph`/`orchestration`/`AgentState`). This is where all recall/store *logic* lives — keeping `route_node` an OBP-3 wrapper.
- `tests/components/test_memory_context.py` — pure unit tests for the helpers + predicate (L1/Protocol A; no LangGraph runtime).
- `services/memory_backends/mem0.py` — `Mem0MemoryBackend(MemoryBackend)` delegating to `Mem0CloudClient` (prod backend; only if sync-service route chosen).
- `tests/services/memory_backends/test_mem0_backend.py` — conformance against the `MemoryBackend` Protocol (mock SDK client).
- `tests/orchestration/test_memory_wiring.py` — recall injects into system prompt; store fires at run-end; flag-OFF is a no-op; backend failure degrades gracefully; content never logged; **T3 worker payload carries `recalled_memories` (not `AgentState`) — OBP-M1**.

**Modified (representative pattern — inject a service, read a flag, call at the two seams):**
- `services/base_config.py` — add `memory_enabled: bool = False` to `AgentConfig` (mirrors `reflexion_enabled`).
- `middleware/composition.py` — add `MEMORY_ENABLED` to `AgentRuntimeSettings` (mirror `reflexion_enabled` parse at lines 399/438); construct the `LongTermMemoryService` in `build_components` and pass it through `build_runtime_graph` → `build_graph` (new injected param, like `goal_judge_config_reader`).
- `orchestration/react_loop.py` — accept injected `memory_service` in `build_graph`; in **`route_node`** (the universal seam — reaches T1/T2/T3, see Tier compatibility) add an **OBP-3 block that calls `should_recall(...)` → `memory_service.search(...)` → `render_recall_block(...)`** (no inline logic — mirror the existing `select_model`/`select_planning_depth` calls) and writes `recalled_memories` to state; make `call_llm_node` (~1307–1326) **and** `supervisor_node` *read* `state["recalled_memories"]` into their prompts; in `_route_fanout` add `recalled_memories` to each **`Send` payload dict** so workers receive it by value (OBP-M1 — never `AgentState`); add the store block in the shared run-end/`reasoning_recap` path (calls `build_store_payload(...)` then `memory_service.store(...)`, reads `last_final_answer`, tier-agnostic); add the two BlackBox carriers.
- `orchestration/state.py` — add `user_id: str`, `recalled_memories: str`, `recalled_memories_task_id: str` (plain last-write-wins keys; follow the existing memoize-by-task_id comment style).
- `agent_ui_adapter/adapters/runtime/langgraph_runtime.py` — thread `user_id` (`identity.owner`) into the initial graph input/state.
- `services/governance/black_box.py` — add `MEMORY_RECALLED` / `MEMORY_STORED` to the `EventType` enum (governance carrier vocabulary; these are **non-required** enrichment carriers — they are NOT added to `default_spec()` in `trust/governance_carrier_spec.py`, so `ALL_PHASE_VALUES` and the requirement tuples are unchanged and the drift-guard `tests/trust/test_governance_carrier_spec.py` stays green with no `SPEC_VERSION` bump — see Governance-triangle compliance).
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
   - Recall is memoized (one `search` per **run**, not per loop lap **and not per reflexion re-entry** — assert across a `reflect → route` loop; T2 correctness).
   - **Tier coverage (T1/T2/T3 — Protocol D simulation):**
     - *T1* (`t3_fanout` OFF): recall injected into `call_llm`; store fires at `done`.
     - *T2* (`reflexion_enabled`, force an escalate→`reflect`→`route` lap): exactly **one** `search` for the whole run; store still fires once at terminal `done`.
     - *T3* (`t3_fanout_enabled`, `fan_out` decision): `route` recall fires and reaches `supervisor` (assert the supervisor prompt carries the recalled block); `call_llm` is bypassed yet recall is **not** skipped; run-end store captures the **join's** `last_final_answer`. A fan-out run is never memory-blind.
     - *T3 decline* (`route → supervisor → call_llm`): recall still present via `route`; behaves like T1.
3. **Architecture tests:** run `tests/architecture/` — confirm no new disallowed imports in components/orchestration; service only injected at composition root.
4. **Governance trace check:** run a local task with memory ON, then use the `governance-trace-audit` skill on the resulting trace to confirm `MEMORY_RECALLED`/`MEMORY_STORED` carriers appear and the four-pillar verdict stays healthy.
5. **Local end-to-end:** `python -m agent.cli --user-id demo "remember I prefer metric units"` then a second run `"what units do I prefer?"` — second run's system prompt should carry the recalled fact (inspect via logs/trace).
6. **Full suite:** `pytest` — assert no regressions against the current 3032-pass baseline before considering it done.
7. **Rollout:** ship default-OFF; flip `MEMORY_ENABLED=true` on a dev/stress Cloud Run revision (out-of-band `--tag` revision, prod untouched — per the deploy-gcp stress-revision pattern) to validate live before any prod promotion.

### Phase 1 PR compliance checklist (paste into the PR)

The recall/store seams are orchestration nodes → **[BACKEND_PR_CHECKLISTS.md Checklist 4](../Architectures/BACKEND_PR_CHECKLISTS.md#4-adding-a-new-orchestration-node)**; the `Mem0MemoryBackend` is a service/adapter → **Checklist 2 / 7**. Applicable rows:

```markdown
**Phase 1 — Memory wiring (Checklist 4 + 2/7)**

- [ ] Recall & store seams are thin wrappers (≤ ~30 lines); all work delegates to the injected `memory_service`. (I-7, AP-5)
- [ ] **OBP-1: all recall/store logic** (format block, build payload, degrade fallback) lives in `components/memory_context.py`, NOT inlined in the node. (OBP-1)
- [ ] **OBP-2: the "recall now?" decision** is a pure predicate `should_recall(enabled, user_id, memoized)` taking scalars — not `if` soup reading `AgentState` in the node. (OBP-2)
- [ ] **OBP-4: no new graph node and no new edge** — recall rides the existing `route` node, store rides the existing `done → reasoning_recap` edge. (OBP-4; also clears the AGENTS.md new-node ask-first gate)
- [ ] **OBP-M1: T3 workers receive `recalled_memories` via the `Send` payload dict**, never `AgentState`; assert the worker reads `payload["recalled_memories"]`. (OBP-M1)
- [ ] **One port into the loop:** the loop depends only on the sync `MemoryBackend` Protocol (via injected `LongTermMemoryService`); it imports no backend, no `MemoryClient`, no Mem0 SDK. (ports & adapters, I-10)
- [ ] **Recall runs in `route_node`** (the universal seam) — verified to reach all three tiers: T1 `call_llm`, T2 `reflect→route` re-entry, T3 `supervisor`/fan-out. NOT `call_llm`-only (that would skip every fan-out run). (Tier compatibility)
- [ ] **Recall is memoized once per run** (`recalled_memories_task_id`); a `reflect → route` reflexion lap does NOT re-query the backend. (T2 correctness)
- [ ] **Store reads `last_final_answer`** so it is tier-agnostic — captures the T3 `join_node` answer identically to a T1 answer. (Tier compatibility)
- [ ] No domain logic in the node — no parsing/heuristics over content; only state assembly + service call + state return. (AP-5)
- [ ] State reads/writes go through the `AgentState` TypedDict — `user_id`, `recalled_memories`, `recalled_memories_task_id` are declared on the class with last-write-wins (no magic-string `.get`). (Checklist 4)
- [ ] BlackBox `MEMORY_RECALLED` / `MEMORY_STORED` emitted at the seams via `BlackBoxRecorder.record(TraceEvent(...))`; details carry `user_id`/`key`/`count` — never content. (Checklist 4, privacy invariant)
- [ ] **Memory carriers ENRICH Recording — they are NOT added to `default_spec()` as per-phase requirements.** `PH_ROUTING` keeps `model_selected`, `PH_COMPLETION` keeps `eval.goal_judge`; requiring a memory carrier would false-positive the carrier gate on every non-memory run (GG-4 class). (Governance-triangle compliance, rule 1)
- [ ] **Degraded recall/store still leaves a carrier** (count 0 / `error_kind`, never content) — a swallowed `MemoryBackendError` with zero carriers is a silent failure the audit's Validation pillar flags. (Governance-triangle compliance, Validation row)
- [ ] **No memory write uses a `user_id` other than the run's subject** (`identity.owner`) — cross-user-leak guard. (Identity pillar)
- [ ] `eval_capture.record()` called at both seams with `target`/`user_id`/`task_id`. (I-11, per user decision)
- [ ] `LongTermMemoryService` is injected via `build_components` → `build_graph` (new param like `goal_judge_config_reader`); no node imports a backend. (H7, I-1)
- [ ] `Mem0MemoryBackend` (if built) imports no framework package and no `components/`. (I-4, I-5) — Checklist 2.
- [ ] Privacy test: backend raises → run completes, warning logged, no content in logs (reuse the magic-string assertion). (TAP-4 first)
- [ ] `EventType.MEMORY_RECALLED` / `MEMORY_STORED` added in `services/governance/black_box.py`; the carrier-spec drift-guard `tests/trust/test_governance_carrier_spec.py` stays green (new members are non-required, so `ALL_PHASE_VALUES` and the requirement tuples are unchanged — no `SPEC_VERSION` bump).
- [ ] **Governance audit gate (REQUIRED, post-deploy):** a memory-ON run audited via the `governance-trace-audit` skill returns **COMPLIANT** with `MEMORY_RECALLED`/`MEMORY_STORED` present, content absent, no `source: "carrier_gate"` memory alert; a memory-OFF run audits byte-identical to today. (Verification step 4)
- [ ] `pytest tests/architecture/ -q` passes — no new disallowed imports; service only injected at composition root.
- [ ] No hardcoded model names / prompts in the diff (H1/H2); no secrets; no `print(...)`. (Checklist 8)
```

---

# Phase 2 — Typed background auto-capture (semantic / episodic / procedural)

**Why (user request):** auto-detect the three human memory types as the user interacts. Research confirms the right shape: a **background, debounced, schema-guided extraction pass** — not a hot-path classifier and not a deterministic distillation. The schema *is* the classifier (give the LLM the three typed schemas; it emits zero-or-more typed items per window). See research §1–§3.

**Design:**
- **Trigger:** after a run completes (BFF/runtime layer, *not* inside the graph hot path), enqueue a background extraction task for the thread. **Debounce per thread** (batch a burst; process on a pause) to bound LLM cost — mirrors LangMem `create_memory_store_manager`.
- **Extractor (new component, framework-clean):** `components/memory_extractor.py` — pure function `extract_memories(messages, existing_profile) -> list[TypedMemory]` where `TypedMemory = {type: semantic|episodic|procedural, content, key, salience}`. Cheap-tier model. Schema-guided: one prompt, three schemas, emits typed items. **ADD-only** in v1 (no live UPDATE/DELETE) + a periodic **consolidation** pass — cheaper and higher-precision per research §3.
- **Storage shape (research §1):** semantic → a *profile* record (latest-state, `key="profile"`) plus a *collection* for open-ended facts; episodic → *collection* of `{observation, action, result}` items keyed by `task_id`; procedural → deferred to v2 (needs a feedback signal — reuse `reflections`). All via the existing `LongTermMemoryService.store`, with `metadata={"type": <type>}` so recall and the UI can filter.
- **Recall update:** Phase-1 recall stays top-3 semantic; extend the `search` to optionally filter by `type` and prefer the profile record first.
- **Governance:** one `MEMORY_STORED` carrier per extracted item, `details={user_id, key, type, salience}` — **never content** (privacy invariant).
- **Flag:** reuse `MEMORY_ENABLED`; add `MEMORY_AUTOCAPTURE_ENABLED` (default OFF) so recall can ship before write-back.

**New/changed files (Phase 2):**
- `components/memory_extractor.py` (new, framework-agnostic) + `tests/components/test_memory_extractor.py`.
- `prompts/memory_extractor.j2` (new) — the schema-guided extraction prompt (three typed schemas).
- A background task seam in the BFF/runtime (e.g. `agent_ui_adapter/` or middleware) that calls the extractor post-run with debounce; wired at the composition root.
- `services/long_term_memory.py` recall: optional `type` filter on `search` (additive, backward-compatible).

**Replaces** the Phase-1 "deterministic distillation of final answer" store with this typed extractor once Phase 2 lands.

### Phase 2 eval workstream — calibrate the extractor as an LLM judge ([llm-eval-grounded-theory](../skills/llm-eval-grounded-theory/SKILL.md))

The Phase-2 extractor is a **probabilistic classifier**: it decides *what is worth remembering* and *which of the three types it is*. That is exactly the kind of LLM-as-judge the grounded-theory pipeline exists to make trustworthy — so it ships **shadow/telemetry-first, action-gated**, not enabled-on-merge. Cardinal rule 6 ("default-off until calibrated") *is* `MEMORY_AUTOCAPTURE_ENABLED=false`; the flag does not flip to write-back until the enable-policy clears.

**Why this and not just unit tests:** Protocol-C unit tests (mocked-LLM, trajectory shape) prove the extractor *parses and degrades*; they do **not** prove it extracts the *right* memories with acceptable precision. Two failure modes only an eval loop catches: **over-capture** (storing trivia → memory pollution that degrades every future recall) and **mis-typing** (an episodic event filed as a semantic fact). Both are silent in CI and corrosive in production. Precision on the capture-trigger class is the gate metric (cardinal rule 5), not accuracy.

**Staged plan (maps to the pipeline's Stage 0–7):**

| Stage | Applied to the memory extractor | Gate before next stage |
|-------|----------------------------------|------------------------|
| **0 — Traces** | Collect real (memory-ON, shadow) run trajectories: `messages` in, the extractor's proposed `TypedMemory[]` out, with stable `trace_id`/`user_id`/`task_id`. Shadow mode means it proposes but does **not** store. | full trajectories + stable IDs; privacy posture verified (no content in the trace carriers). |
| **1 — Open coding** | Human reads ≥100 proposed-extraction traces; first-failure-discipline notes: *over-capture? mis-type? missed-salient? content-leak?* No LLM first pass (AP-10). | saturation (~20 traces, no new code). |
| **2 — Axial coding** | Cluster into 5–6 **testable** extractor failure categories (e.g. `OVER_CAPTURE`, `MISTYPE_EPISODIC_AS_SEMANTIC`, `MISSED_SALIENT`, `STALE_PROFILE_OVERWRITE`). Split confounds (empty input, backend down) from judge defects. IAA ≥ 0.80 on category. | top mode selected. |
| **3 — Synthetic strata** | Generate **inputs** (conversation snippets) for rare strata production won't supply — e.g. a user *correcting* a prior fact (UPDATE pressure), PII the extractor must **not** store, three-types-in-one-turn. Synthetic → dev split ONLY (contamination firewall, AP-5). | coverage map complete. |
| **4 — Rubric** | The extraction rubric is **analytic + binary** per item: *is this worth storing? (pass/fail)* and *is the type correct? (pass/fail)* — encoded in `prompts/memory_extractor.j2` as the schema's constraints + the eval rubric. PROVISIONAL → shadow. | provisional rubric in shadow. |
| **5 — Gold set** | ~200–300 double-labeled `(conversation → should-store? which-type?)` items, stratified by the taxonomy, oversampling the store-trigger class; α ≥ 0.80 on the store-decision gate field; frozen test split. | α ≥ 0.80, test frozen. |
| **6 — Calibration** | Report **precision/recall on the store-trigger class** + per-`type` breakdown + a CoT-gaming red-team (can a crafted message force a junk store?). Enable-policy (precision-first profile): precision on store ≥ 0.90, false-store on trivia ≤ 2%, mis-type ≤ some bar, κ ≥ 0.6. | all enable-policy gates pass on test split. |
| **7 — Monitoring** | After gates clear: L1 sync schema check 100%, L2 async judge sample 5–10% of stores, L3 drift alert on per-type store rates; every production mis-store → candidate gold entry. | continuous loop live. |

**Enable-policy is the flag gate.** `MEMORY_AUTOCAPTURE_ENABLED` flips from "propose-only shadow" to "store" **only** when the Stage-6 enable-policy clears on the frozen test split — mirroring the GoalJudge rollout (shadow → dev-enable → prod-enable, never iterate prompt on test). Until then Phase 2 runs in shadow: the extractor proposes, the trace carries the proposal, **nothing is written**.

**Eval anti-patterns to avoid (skill's AP table):** AP-1 (don't write the extraction prompt before coding real traces); AP-3 (gate on store-class precision, not global accuracy); AP-4/AP-5 (never tune the rubric on, or leak synthetic into, the test split); AP-7 (no always-store extractor in prod before gates clear); AP-8 (binary per-item criteria, not a holistic salience-Likert).

**New eval artifacts (Phase 2, under `docs/recipes/` / `docs/plans/` per the skill's `paths`):** a memory-extractor failure taxonomy, a stratified gold set (`memory-extract-gold-v1`), an enable-policy doc, and a CI golden-regression once gates clear. These reuse the existing eval-capture / open-coding tooling (the skill notes the `llm-eval-grounded-theory` + `agentsframework-open-coding` companion tools already exist in-repo).

### Phase 2 PR compliance checklist (paste into the PR)

`components/memory_extractor.py` is a vertical component → **[Checklist 3](../Architectures/BACKEND_PR_CHECKLISTS.md#3-adding-a-new-vertical-component)**; the background-task seam in the BFF/runtime is an adapter-family/composition concern → **Checklist 7 / 2**. Applicable rows:

```markdown
**Phase 2 — Typed extractor (Checklist 3 + 2/7)**

- [ ] `components/memory_extractor.py` is framework-agnostic — no `langgraph`/`langchain*`. (I-3) — Checklist 3.
- [ ] The component imports only from `services/` and `trust/`; no peer-component imports. (Checklist 3)
- [ ] `extract_memories(...)` is testable without LangGraph — instantiated directly, fed dicts/Pydantic. (Checklist 3)
- [ ] `TypedMemory` output is a Pydantic model with `extra="forbid"`; `type` is a literal `semantic|episodic|procedural`. (V6)
- [ ] The extraction prompt is `prompts/memory_extractor.j2` rendered via `PromptService.render_prompt()` — NO inline prompt strings. (H1, I-12, AP-3)
- [ ] The extractor LLM call invokes `eval_capture.record()` with `target="memory_extract"`, `user_id`, `task_id`, token counts, cost, latency. (H5, I-11)
- [ ] Cheap-tier model selected via config (`services/base_config.py`), not hardcoded. (H2)
- [ ] One `MEMORY_STORED` carrier per extracted item: `details={user_id, key, type, salience}` — never content. (privacy invariant)
- [ ] Background task seam wired at the composition root (debounce per thread); does NOT run inside the graph hot path. (H7)
- [ ] `services/long_term_memory.py` `search` `type` filter is additive/backward-compatible; existing tests stay green.
- [ ] `MEMORY_AUTOCAPTURE_ENABLED` defaults OFF; flag-OFF path is a no-op (regression guard).
- [ ] Rejection test written first (TAP-4): malformed extractor output rejected; ≤ 3 mocks/test (TAP-2).
- [ ] **Eval gate (llm-eval-grounded-theory):** error analysis on ≥100 shadow extraction traces precedes the prompt (AP-1); failure taxonomy + stratified gold set (`memory-extract-gold-v1`, α ≥ 0.80) exist; store-trigger-class **precision ≥ 0.90** + mis-type + CoT-gaming flip-rate measured on the **frozen test split**; enable-policy doc written.
- [ ] **`MEMORY_AUTOCAPTURE_ENABLED` flips to write-back ONLY after the enable-policy clears** (shadow → dev-enable → prod-enable; never iterate the prompt on the test split). Until then the extractor proposes-only; nothing is stored.
- [ ] `pytest tests/architecture/ -q` and `pytest tests/components/ -q` pass.
```

---

# Phase 3 — UI: chat-history sidebar + editable memory panel

**Why (user request + research §4–§5):** a Recents-style chat list to resume past threads, and a visible/editable memory panel (auto-capture + user control is the 2026 trust norm). **Key finding: the chat-history frontend is scaffolded but inert** — completing it, not greenfield.

**Current state (verified by code inspection):**
- `frontend/components/chat/ThreadSidebar.tsx` exists but renders `thread_id` (no title) and is **not mounted** anywhere.
- `frontend/app/api/threads/route.ts` has GET+POST; `lib/bff/handlers.test.ts` already enforces "caller's own threads only (B6)".
- Drizzle declares `threads` + `thread_messages`, but `thread_messages` is never written/read.
- `agent_ui_adapter/server.py` `_ThreadStore` is in-memory, **create/get only — no list, no persistence**.

**Chat-history work:**
- **Backend:** add a thread **list** endpoint to `agent_ui_adapter/server.py` (scoped by `user_id`); replace the in-memory `_ThreadStore` with a persistent store (Postgres/Drizzle `threads` + `thread_messages`). Auto-generate a thread **title** (cheap-model first-turn summary).
- **BFF:** GET `/api/threads` returns the caller's list (already test-specified).
- **Frontend:** give `ThreadSidebar` real titles + time-grouping (Today / Yesterday / Previous 7 days), **mount** it in the chat shell, wire click→resume (replay thread), rename/delete. Keep it RSC-fetched per the existing component's contract.

**Memory-panel work (research §4):**
- **BFF + backend:** memory CRUD endpoints scoped by user (mirror the "caller's own only" pattern) over `LongTermMemoryService` (`search`/`store`/`forget`); group results by `type`.
- **Frontend:** a memory panel — list entries by type (semantic/episodic/procedural), edit, delete, add manual, **toggle memory off**. Plus a **transparent-recall indicator** in the chat ("recalled N memories"), sourced from the `MEMORY_RECALLED` carrier — gives the Claude/ChatGPT-style "searched past conversations" affordance for free via the governance trail.

**Separation invariant (research §5):** the sidebar resumes a *specific thread* (short-term, checkpointer). The memory panel shows *cross-thread* facts (long-term store). Past conversations *feed* extraction but recall reads the typed stores, not old threads. Do not conflate the two seams.

**New/changed files (Phase 3, representative):**
- `agent_ui_adapter/server.py` — thread list endpoint + persistent ThreadStore.
- `frontend/components/chat/ThreadSidebar.tsx` — titles + grouping; mount in `frontend/app/chat-shell.tsx`.
- `frontend/app/api/threads/route.ts` + new `frontend/app/api/memory/route.ts` (memory CRUD).
- new `frontend/components/memory/MemoryPanel.tsx` + recall indicator in the chat view.
- Drizzle: actually write/read `thread_messages`; a `memories` table (or rely on the backend memory store).

### Phase 3 PR compliance checklist (paste into the PR)

Phase 3 spans two rings. **Backend half** (thread-list endpoint, persistent `ThreadStore`, memory CRUD over `LongTermMemoryService`) → **[Checklist 7](../Architectures/BACKEND_PR_CHECKLISTS.md#7-adding-a-new-adapter-family) / 4**. **Frontend half** (`ThreadSidebar`, `MemoryPanel`, BFF routes) → **[FRONTEND_ARCHITECTURE.md](../Architectures/FRONTEND_ARCHITECTURE.md) F-R1..F-R9** + the rule families in **[STYLE_GUIDE_FRONTEND.md](../STYLE_GUIDE_FRONTEND.md)**.

```markdown
**Phase 3 — Backend (Checklist 7 / 4)**

- [ ] Persistence goes behind the `ThreadStore` port; the new persistent impl is the only place its storage SDK appears (I-9 if in `adapters/runtime/`; otherwise port-confined).
- [ ] Thread-list & memory-CRUD endpoints are scoped by `user_id` (caller's own only) — mirror the `/api/threads` "B6" ownership rule.
- [ ] Memory CRUD delegates to `LongTermMemoryService` (`search`/`store`/`forget`); no new memory engine. (H6)
- [ ] Auto-title generation routes its LLM call through `eval_capture.record()` and its prompt is a `.j2`. (H5/I-11, H1/I-12)
- [ ] `trace_id` from the request flows verbatim through any adapter — never re-minted. (Checklist 7)
- [ ] `pytest tests/architecture/test_agent_ui_adapter_layer.py -q` (or `test_middleware_layer.py`) passes.
```

```markdown
**Phase 3 — Frontend (F-R1..F-R9 + STYLE_GUIDE_FRONTEND)**

- [ ] No domain logic in `ThreadSidebar`/`MemoryPanel` — they take typed props and render; lifecycle/fetch lives in adapters/translators. (F-R1, Rule families A/T)
- [ ] SDK imports (CopilotKit, Mem0, WorkOS, LangGraph client) appear only under `frontend/lib/adapters/`. (F-R2, Rule A1)
- [ ] No SDK type escapes an adapter boundary — `ports/`, `translators/`, `transport/`, `wire/` use `wire/` shapes or primitives. (F-R8, Rule A4, W-family)
- [ ] The memory/thread BFF Route Handlers (`/api/threads`, `/api/memory`) are composition adapters — delegate to a port, no business `if`-branches. (F-R4, Rule P/A)
- [ ] One interface per `ports/` module if a memory/thread port is added or refined. (F-R3, Rule P1)
- [ ] Wire shapes are snake_case on the wire, camelCase only after a translator; discriminated unions for typed memory items. (Rule W3, W6; `wire/` mirrors the Python source — W2)
- [ ] `trace_id` is forwarded untouched through the recall-indicator path (sourced from the `MEMORY_RECALLED` carrier). (F-R7, Rule W5/T2)
- [ ] No prompt/instruction text in any TypeScript file. (F-R5, Rule W-family)
- [ ] `trust-view/` stays read-only — the panel reads identity/recall views, never mutates them. (F-R6)
- [ ] BFF holds no cloud credentials — Mem0/WorkOS keys stay in `middleware/`; BFF talks JWT-over-HTTPS only. (F-R9)
- [ ] Architecture tests `tests/architecture/test_frontend_layering.ts` (F-R1/2/3/8) pass once authored.
```

---

## Resolved decisions (2026-06-17)

1. **Build-vs-buy (Phase 2 auto-capture) — RESOLVED: adopt the patterns on the existing seam.** Phase 2 borrows LangMem's schema-guided-extraction + per-thread debounce *design* but implements them on the existing `LongTermMemoryService` / `MemoryBackend` port. Rationale (and why it matters for the coupling audit above): keeps **one** memory abstraction into the loop, honors the tested surface + "swap backend = one file", and — decisively — does **not** introduce a second memory abstraction (the exact ports-and-adapters coupling we just closed) nor a new `pyproject.toml` dependency (so the AGENTS.md ⚠️ ask-first dependency gate does **not** fire). The LangMem SDK is **not** adopted.
2. **Scope — RESOLVED: all three phases re-approved as scoped.** P1 (runtime recall+store, now OBP/governance/tier-hardened) ships first; P2 (typed auto-capture) ships shadow-first behind `MEMORY_AUTOCAPTURE_ENABLED`, write-back gated on the grounded-theory enable-policy; P3 (chat-history sidebar + memory panel) follows. **Implementation begins only on explicit go.**

---

## AGENTS.md compliance confirmation

Checked against [AGENTS.md](../../AGENTS.md). The plan honors the ✅-Always / 🚫-Never rules, and three ⚠️-Ask-first triggers are called out so they are not done silently.

### ⚠️ Ask-first gates this plan triggers (require explicit approval before the relevant phase)

| Gate (AGENTS.md ⚠️) | Where it fires | Status |
|---------------------|----------------|--------|
| **Adding new graph nodes to `orchestration/react_loop.py`** | Phase 1 recall/store seams. *If* they land as discrete nodes (vs. inline blocks in `call_llm_node` / the run-end path), node addition is ask-first. The plan's current design folds recall into the existing `call_llm_node` and store into the existing run-end path — **no new node**, so this gate may not fire; confirm the seam shape at implementation. | ⏳ confirm at build |
| **Creating new horizontal services** | Phase 1 `Mem0MemoryBackend` (a new `services/memory_backends/` module) and any Phase 2 service-side helper. New service surface is ask-first. | ⏳ approve with phase |
| **Adding new dependencies to `pyproject.toml`** | Only if the LangMem-SDK build-vs-buy answer is "adopt the SDK." The recommended "patterns on existing seam" route adds **no** dependency. | ⏳ gated on open question |
| **Modifying trust kernel types in `trust/models.py`** | **Not triggered** — memory types (`MemoryRecord`, carrier details) stay in `services/`; `EventType` additions live in `services/governance/black_box.py`, not `trust/models.py`. (Confirms I-14 stays untouched.) | ✅ avoided by design |

### ✅ Always-rules — how the plan satisfies each

- **`pytest tests/ -q` after changes** → Verification steps 2 & 6 (full suite, 3032-pass baseline regression gate).
- **`PromptService.render_prompt()` for all prompts, no hardcoded strings** → Phase 2 extraction prompt is `prompts/memory_extractor.j2`; Phase 3 auto-title prompt is a `.j2`. No inline prompt strings anywhere. (H1 / AP-3)
- **`eval_capture.record()` with `user_id` + `task_id` on every LLM call** → per the 2026-06-17 decision, *every* memory seam records (recall/store latency-only in v1; extractor + auto-title record real token/cost). (H5 / I-11)
- **New prompts as `.j2` in `prompts/`** → covered above.

### 🚫 Never-rules — explicit guards in the design

- **No `orchestration/` import in `components/`/`services/`** → `memory_extractor.py` (component) and `Mem0MemoryBackend` (service) import only downward. (I-1)
- **No `langgraph`/`langchain` in `components/`/`trust/`** → `memory_extractor.py` is framework-clean; no memory type enters `trust/`. (I-3)
- **No shared trust types inside a service** → memory types stay in `services/`; they are not "shared by 2+ layers / stable / dependency-free" per the Trust Kernel Rules, so they do **not** belong in `trust/`. (AP-1)
- **No hardcoded model names** → the extractor/auto-title cheap-tier model is referenced from `services/llm_config.py` / `base_config.py`. (H2)
- **No secrets / `.env` committed; no live LLM in CI** → Mem0/WorkOS keys stay in `middleware/` secret injection (F-R9); all new LLM tests are `@pytest.mark.live_llm` and excluded from CI.
- **No peer component imports** → `memory_extractor.py` imports no sibling component. (I-5 peer rule)

---

## TDD implementation protocol (per @research/tdd_agentic_systems_prompt.md)

Each phase is bound to its **layer protocol**, the **named test patterns** it must use, and the **failure-first** discipline. The plan's existing Verification list is the L1/L2 gate; this section adds the layer-correct strategy and the patterns to reach for, so the implementation is test-led, not test-after.

### Uncertainty-boundary placement (which protocol applies where)

| Module (this plan) | Layer | Pyramid / Protocol | Primary strategy |
|--------------------|-------|--------------------|------------------|
| `Mem0MemoryBackend`, `LongTermMemoryService` recall `type`-filter | `services/` | **L2 / Protocol B** (contract-driven) | Mock I/O, record/replay, ≤3 mocks, <30s |
| `components/memory_context.py` (`render_recall_block`, `build_store_payload`, `should_recall`) | `components/` | **L1 / Protocol A** (pure TDD) | Deterministic helpers + predicate; no LLM, no runtime; zero-flake (OBP-1/OBP-2) |
| `components/memory_extractor.py` (`extract_memories`) | `components/` | **L3 / Protocol C** (eval-driven) | Mocked-LLM determinism tests + trajectory/rubric for quality; aggregate pass rates |
| Recall/store **node wrappers** + Send-payload propagation in `react_loop.py` | `orchestration/` | **L4 / Protocol D** (simulation-driven) | Binary-outcome scenarios + failure-mode matrix; OBP-M1 worker-payload assertion |
| `EventType.MEMORY_RECALLED/STORED` + carrier-spec wire strings | `trust/`-adjacent (governance enum) | **L1 / Protocol A** (pure TDD) | Enum-completeness + carrier-spec drift assertion, zero-flake |

### Patterns to apply (from the §Test Pattern Catalog)

- **Pattern 6 — Mock Provider** (L2/L3): drive the extractor's LLM with a `TextOnly`/`ToolCall`/`Error` mock provider to test parsing + the graceful-degradation path **without** a live model. *Prevents Determinism Theater (AP-3).*
- **Pattern 5 — Record/Replay Fixture** (L2): record one real Mem0 interaction; replay in CI for the `Mem0MemoryBackend` conformance test. *Prevents Live-LLM-in-CI (AP-5).*
- **Pattern 4 — Consumer-Driven Contract** (L2): the `MEMORY_RECALLED/STORED` carrier is a cross-layer type — assert the governance/relay consumer gets `{user_id, key, type, count, salience}` and **never** content. *Prevents Mock Addiction (AP-2).*
- **Pattern 11 — Failure-Mode Matrix** (L4, the load-bearing one): parametrize the recall/store seams over `{flag OFF, flag ON+no user_id, flag ON+empty store, flag ON+hit, backend raises, backend times out}` → expected `{no-op, no-op, no-op+carrier count 0, injected+carrier, run completes+warning, run completes+warning}`. Write the **rejection rows first**. *Prevents Gap Blindness (AP-6 / TAP-4).*
- **Pattern 8 — Trajectory Eval** (L3): for Phase 2, assert the extractor emits *zero-or-more typed items of the right shape*, **not** an exact item list (a better model may extract differently). *Prevents Eval-Dataset Overfitting (AP-4).*
- **Pattern 7 — Dependency-Rule Enforcement** (all layers): `tests/architecture/` already runs this; the plan adds no new allowed import. *Prevents Cross-Layer Leak (AP-7).*

### Failure-paths-first checklist (write these tests before the happy path)

Per the "failure paths first" operating principle and TAP-4, each seam's rejection test is authored first:
1. Flag-OFF → no `search`/`store`/`extract` call; system prompt byte-identical (regression guard).
2. Flag-ON, no `user_id` → no-op, no carrier, no crash.
3. Backend raises `MemoryBackendError` / times out → run completes, warning logged, **no content in logs** (reuse the magic-string assertion from `tests/services/test_long_term_memory.py`).
4. Malformed extractor output (Phase 2) → rejected by the `TypedMemory` validator; nothing stored.
5. *Then* the acceptance tests: hit injects top-3 into `additional_instructions`; run-end stores once; extractor emits typed items.

### Self-validation gate (the §Self-Validation Suite, run before each phase is "done")

The 8 checks become an explicit exit gate per phase: **(1) coverage** — every new module has a test; **(2) layer alignment** — extractor uses mocked-LLM/rubric not L2 exact-match; **(3) dependency compliance** — `pytest tests/architecture/`; **(4) failure-path coverage** — the matrix above is complete; **(5) anti-pattern scan** — no TAP-1..TAP-4 / AP-1..AP-7; **(6) contract coverage** — the carrier producer+consumer contract exists; **(7) determinism audit** — L1/L2 memory tests pass 10× with no flake; **(8) CI/CD tagging** — extractor/auto-title live tests are `@pytest.mark.live_llm`, L3 trajectory tests `@pytest.mark.slow`, L4 matrices `@pytest.mark.simulation`. A phase is not "done" until all 8 read pass.

---

## Deferred (beyond these three phases)
- **Live conflict resolution (UPDATE/DELETE on the hot path)** — v1 is ADD-only + consolidation; similarity-threshold merge (~0.85) + LLM resolution is a later upgrade (research §3).
- **Procedural memory auto-capture** — needs a reliable feedback signal; v2 reuses successful `reflections` as reusable strategies.
- **Memory-quality benchmarking** — LongMemEval/LoCoMo/BEAM harness if we need to measure recall precision.
- **Backend graduation** Mem0 → pgvector-on-Neon per SPIKE_C latency debt (~447ms p95 search).
