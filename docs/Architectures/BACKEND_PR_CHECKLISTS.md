---
type: checklist
title: 'Backend PR Review Checklists'
description: 'Scope: Reviewer aid for PRs touching the Python backend (trust/, services/, components/, orchestration/, meta/, StructuredReasoning/, agent_ui_adapter/).'
tags: [architecture]
---

# Backend PR Review Checklists

**Scope:** Reviewer aid for PRs touching the Python backend (`trust/`, `services/`, `components/`, `orchestration/`, `meta/`, `StructuredReasoning/`, `agent_ui_adapter/`).

**Audience:** Architects and reviewers gating PRs against layer rules.

**How to use this document.** Pick the checklist matching the kind of change in the PR. Paste it into the PR review comment, tick boxes as you verify, and link to the violating line if a box stays unchecked. Each checklist row references the invariant (I-x), pattern (Hx/Vx), or anti-pattern (AP-x/TAP-x) it guards — full definitions live in `docs/Architectures/BACKEND_SOLUTION_ARCHITECTURE.md` and `docs/style-guides/STYLE_GUIDE_PATTERNS.md`.

---

## Index

1. [Placing a new module](#1-placing-a-new-module)
2. [Adding a new horizontal service](#2-adding-a-new-horizontal-service)
3. [Adding a new vertical component](#3-adding-a-new-vertical-component)
4. [Adding a new orchestration node](#4-adding-a-new-orchestration-node)
5. [Adding a new tool](#5-adding-a-new-tool)
6. [Changing a trust kernel type](#6-changing-a-trust-kernel-type)
7. [Adding a new adapter family](#7-adding-a-new-adapter-family)
8. [Always-on quick gate](#8-always-on-quick-gate)

---

## 1. Placing a new module

Use this checklist when the PR adds a new `.py` file anywhere in the backend.

```markdown
**Placement review (Checklist 1)**

- [ ] **Layer choice is justified in the PR description.** The author explicitly states whether the new module is trust / service / component / orchestration / meta / adapter, and why. (I-1)
- [ ] **The new module's imports go only downward or sideways within its allowed set.** Verify by running `pytest tests/architecture/ -q`. (I-1..I-10)
- [ ] **If the module lives in `trust/`,** it imports only stdlib + Pydantic. No `services/`, no `components/`, no `orchestration/`, no `meta/`, no `langgraph`, no `langchain`. (I-2)
- [ ] **If the module lives in `components/`,** it does not import `langgraph`, `langchain`, `langchain_core`, or `langchain_community`. (I-3)
- [ ] **If the module lives in `services/` (not `services/llm_config.py`),** it does not import framework packages. (I-4)
- [ ] **If the module lives in `services/`,** it does not import from `components/`. (I-5)
- [ ] **If the module lives in `meta/`,** it does not import from `orchestration/`. (I-6)
- [ ] **If the module lives in `agent_ui_adapter/` outside `adapters/runtime/`,** it has no third-party SDK imports. (I-9)
- [ ] **If the module lives in `StructuredReasoning/`,** it respects the inner mirror rules — verify by running `pytest tests/architecture/test_structured_reasoning_layers.py -q`. (I-8)
- [ ] **Module-level docstring states the layer, purpose, and any framework carve-out.** Match the style of existing files in the same layer.
- [ ] **A test file lives at the parallel path** under `tests/<layer>/test_<module>.py`, and that test file imports only from the test-allowed layers (trust tests import only `trust/`; service tests import `trust/` + `services/`; etc.).
- [ ] **The architecture test suite passes locally:** `pytest tests/architecture/ -q`.
```

**Reviewer red flags.**

- A new file under `trust/` that adds `import logging` or any `services.*` import — reject (AP-1).
- A new file under `services/foo.py` that imports `from services.bar import ...` — challenge (AP-2); the consumer should receive `bar`'s output as a parameter, not import the peer.
- A new file under `orchestration/` that contains more than topology — reject (AP-5).

---

## 2. Adding a new horizontal service

Use this checklist when the PR adds a new file (or restructures one) inside `services/` or `services/<sub>/`.

```markdown
**Horizontal service review (Checklist 2)**

- [ ] **The service has a single responsibility.** One sentence describes what it does; no `and`. (H6)
- [ ] **The service API is domain-agnostic.** The same API could be used by the ReAct agent, the Pyramid agent, or a future code-reviewer agent — verify by reading the public method signatures and confirming they take generic types (dicts, Pydantic models from `trust/`, primitive arguments). (H6, AP-2)
- [ ] **No imports from `components/` or `orchestration/`.** (I-5)
- [ ] **No framework imports** (`langgraph`, `langchain`, `langchain_core`, `langchain_community`) — unless the file is `services/llm_config.py`, in which case the carve-out is documented in the module docstring. (I-4, G-10)
- [ ] **Constructor injection only.** Collaborators are passed via `__init__`. No module-level singletons. (H7)
- [ ] **Per-concern logger.** `logger = logging.getLogger("services.<name>")` and a corresponding entry in `logging.json` routing the logger to its own file under `logs/`. (H4)
- [ ] **If the service calls an LLM,** every call invokes `eval_capture.record()` with `target`, `user_id`, `task_id`, plus token counts, cost, and latency. (H5, I-11)
- [ ] **If the service renders text for the LLM,** every prompt is a `.j2` file in `prompts/` rendered via `PromptService.render_prompt()`. No f-strings, no inline `"You are a..."`. (H1, AP-3)
- [ ] **If the service has any external I/O** (file, network, DB), the I/O is hidden behind a port (`Protocol` or `Registry`) so it can be replaced in tests.
- [ ] **Unit tests under `tests/services/test_<name>.py`** cover failure paths first (TAP-4): bad input rejected, dependency errors surfaced, success cases last.
- [ ] **Test count of mocks per test ≤ 3.** If a test needs more, replace mocks with in-memory implementations. (TAP-2)
- [ ] **Pydantic outputs** for any non-trivial result. Use `ConfigDict(extra="forbid")`. (V6)
```

---

## 3. Adding a new vertical component

Use this checklist when the PR adds a new file inside `components/` or `StructuredReasoning/components/`.

```markdown
**Vertical component review (Checklist 3)**

- [ ] **The component is framework-agnostic.** No `langgraph`, no `langchain*`. (I-3)
- [ ] **The component imports only from `services/` and `trust/`.** No peer-component imports (no `router.py` importing `evaluator.py`).
- [ ] **The component is testable without LangGraph.** Tests in `tests/components/test_<name>.py` instantiate the component directly and feed it dicts / Pydantic models.
- [ ] **All non-trivial outputs are Pydantic models** with `extra="forbid"`. (V6)
- [ ] **Deterministic heuristics for routing/gating decisions;** LLM advisories are advisory `.j2` prompts, not control-flow inputs. (V2)
- [ ] **If the component participates in a gate, write the rejection test before the acceptance test.** Add a failure-mode matrix when ≥ 3 distinct rejection causes exist. (TAP-4)
- [ ] **Public functions are pure where possible.** No global state, no module-level config. Side effects (logging) are explicit.
- [ ] **A test file lives at `tests/components/test_<name>.py`** with at least one rejection test and one acceptance test.
- [ ] **`pytest tests/architecture/ -q` passes.**
```

---

## 4. Adding a new orchestration node

Use this checklist when the PR adds a new node (or significantly modifies an existing one) inside `orchestration/react_loop.py` or `StructuredReasoning/orchestration/pyramid_loop.py`.

```markdown
**Orchestration node review (Checklist 4)**

- [ ] **Node body is a thin wrapper.** Target ≤ 30 lines (aspiration ≤ 15). All decision logic delegates to `components/` or `services/`. (I-7, AP-5)
- [ ] **No domain logic inside the node.** No conditionals over content, no parsing, no heuristics — only state assembly, service invocation, and state return. (AP-5)
- [ ] **State reads are typed via the `AgentState` / `PyramidState` TypedDict.** No `.get(...)` with magic string keys not declared on the state class.
- [ ] **State writes are returned as a dict.** No in-place mutation of `state` arguments.
- [ ] **Black box + phase logger emissions** at the node's significant decision points. (`BlackBoxRecorder.record(TraceEvent(...))`, `PhaseLogger.log_decision(...)`)
- [ ] **`TrustTraceRecord` emission** for any gate decision (authorization, identity verification, guardrail rejection).
- [ ] **If the node invokes an LLM,** `eval_capture.record()` is called with full metadata. (H5, I-11)
- [ ] **If the node alters control flow (conditional edges),** the routing function is a separate top-level function (`_should_continue`, `_guard_routing`, `_parse_response`, `_verify_authz_routing`) — not embedded inline.
- [ ] **The graph wiring change (`builder.add_node`, `builder.add_edge`, `builder.add_conditional_edges`) is in the same PR.**
- [ ] **A topology test** (`tests/orchestration/test_<feature>.py`) covers the new node's happy path and at least one failure path.
- [ ] **If the change adds a new state field,** the appropriate reducer is set (`Annotated[list, _append_list]`, `Annotated[int, operator.add]`, etc.) and a checkpoint round-trip test exists.
- [ ] **Imports respect I-1.** The node imports only from `components/` and `services/`; never from peer `orchestration/` files.
```

**Reviewer red flags.**

- A node body over 50 lines — challenge: what should move to `services/` or `components/`?
- An `if` branch over `state.get("last_outcome")` inside a node that does more than route to another node — challenge: that's an `evaluate`-style decision; move it to `components/evaluator.py`.
- Direct LiteLLM/LangChain calls inside a node — reject; route via `LLMService.invoke_with_tools()`.

---

## 5. Adding a new tool

Use this checklist when the PR adds a new tool inside `services/tools/`.

```markdown
**New tool review (Checklist 5)**

- [ ] **Tool input is a Pydantic model with `extra="forbid"`.** Named `<ToolName>Input`. Lives in the same file as the executor. (V6)
- [ ] **Tool executor signature** matches the registry's expectation: `execute_<name>(input: <ToolName>Input, *, _state: dict) -> ToolExecutionResult`. (Or whatever the canonical signature in `services/tools/registry.py` is at PR time.)
- [ ] **Tool returns `ToolExecutionResult`** with `output`, `ok`, optional `error`, optional `metadata`, optional `state_delta`.
- [ ] **If the tool has security-sensitive parameters** (paths, commands, URLs, code), validation goes through `services/tools/sandbox.py` (command allowlist, path sandboxing).
- [ ] **Tool registration** is in the composition root (`cli.py`, `cli_pyramid.py`, `agent_ui_adapter/server.py`), not at module load. (H7)
- [ ] **Tool cache policy** (`cacheable=True/False` in `ToolDefinition`) is justified in the PR description. Stateful or side-effecting tools must be `cacheable=False`.
- [ ] **If the tool emits `TrustTraceRecord` events,** the metadata follows the `EventCategory` taxonomy — `tool_executed` for normal execution, `delegation_*` for `task_tool`, etc.
- [ ] **If the tool may need authorization,** confirm `verify_authorize_log_node` runs for the relevant `AgentFacts.capabilities` entry (e.g., capability `tools.shell.execute`).
- [ ] **Unit tests under `tests/services/test_<tool>.py` or `tests/services/governance/`** cover:
  - [ ] Happy path (success, expected output).
  - [ ] Bad input (validation rejection — write this test FIRST). (TAP-4)
  - [ ] Sandbox bypass attempt (if relevant).
  - [ ] State-delta effect (if the tool mutates `files` / `todos` / `plan_ref`).
- [ ] **If the tool can return large outputs,** the offload threshold in `react_loop.py::_apply_tool_output_thresholds` is respected (no special-casing required if the registry is used correctly).
```

---

## 6. Changing a trust kernel type

Use this checklist when the PR modifies a Pydantic class in `trust/models.py`, `trust/enums.py`, or `trust/review_schema.py`.

```markdown
**Trust kernel change review (Checklist 6)**

- [ ] **The change is approved as "ask first."** Trust kernel changes are flagged in `AGENTS.md` as requiring explicit approval — the PR has that approval recorded.
- [ ] **The change keeps the type pure.** No new I/O, no logging, no network. (Trust Kernel Rule 1)
- [ ] **`ConfigDict(frozen=True)`** is preserved for identity / audit-attribution types. (G-11)
- [ ] **Signed vs unsigned classification:** if a new field is added, the PR description states whether it is signed (participates in signature) or unsigned (operational metadata). See `docs/Architectures/FOUR_LAYER_ARCHITECTURE.md §Signed vs Unsigned`.
- [ ] **If a signed field is added, removed, or its semantics change,** existing signed records must be re-signed:
  - [ ] Migration script or runtime re-signer documented.
  - [ ] Backward-compat mode for one minor version (read old signature, re-sign on next write).
  - [ ] `AGENT_FACTS_SECRET` rotation is **not** required (this is a schema change, not a key rotation).
- [ ] **Every consumer is updated.** Search for usages of the changed type/field across `services/`, `components/`, `orchestration/`, `meta/`, `agent_ui_adapter/`, `StructuredReasoning/`. (Use `rg "AgentFacts" --type py`.)
- [ ] **`trust/__init__.py` `__all__`** is updated if a new public symbol is added.
- [ ] **`tests/trust/test_models.py`** covers:
  - [ ] Valid construction.
  - [ ] Invalid construction (each rejected field has a test).
  - [ ] Roundtrip through `model_dump()` / `model_validate()`.
  - [ ] If signed: signature roundtrip via `compute_signature` / `verify_signature`.
- [ ] **`pytest tests/trust/ -q`** passes with zero flakes. (Trust kernel has zero-flake tolerance.)
- [ ] **`pytest tests/architecture/test_dependency_rules.py -q`** passes (confirms `trust/` did not gain forbidden imports).
- [ ] **CHANGELOG / release note entry** for the schema change.
```

**Reviewer red flags.**

- Adding a `Field(default_factory=lambda: ...)` that calls a service or reads env — reject; trust kernel must be pure.
- Removing `ConfigDict(frozen=True)` from `AgentFacts` or `Capability` — reject without strong justification; immutability is a load-bearing property.
- Adding a field with a sentinel like `"REPLACE_ME"` — reject; defaults must be valid.

---

## 7. Adding a new adapter family

Use this checklist when the PR adds a new sub-package under `agent_ui_adapter/adapters/` (e.g., a non-LangGraph runtime, an OTLP telemetry adapter, a Redis memory adapter) or under `middleware/adapters/`.

```markdown
**Adapter family review (Checklist 7)**

- [ ] **A driven port exists for this concern.** If the adapter implements a new abstraction, the corresponding `Protocol` is defined in `agent_ui_adapter/ports/` (Python) or `frontend/lib/ports/` / `middleware/ports/` (per ring). Adapter ring R9: only one port per concern.
- [ ] **The adapter is the only place SDK types appear for this family.** Outside the adapter file, every type is from `wire/`, `trust/`, or stdlib. (I-9, I-10)
- [ ] **The adapter implements all methods of its `Protocol`.** Verified by `isinstance(impl, ProtocolName)` (works because the Protocol is `@runtime_checkable`).
- [ ] **No upward imports.** The adapter imports from `ports/`, `wire/`, `trust/`, and SDK packages only — never from the core (`services/`, `components/`, `orchestration/`).
- [ ] **Trust trace propagation.** Any `trace_id` from the request flows verbatim through the adapter — the adapter must NOT mint a new one.
- [ ] **Error translation table** documented in the adapter's module docstring. SDK exceptions map to the port's documented exception types; nothing leaks unchanged.
- [ ] **Idempotency contract** documented for any retry-relevant method (cancel, run-create, message-send).
- [ ] **A conformance test bundle** runs against this adapter:
  - [ ] Reuses the shared port-conformance fixtures.
  - [ ] Exercises the documented event mapping (e.g., AG-UI event order).
  - [ ] Verifies the error translation table row-by-row.
- [ ] **Composition root wiring** added to `agent_ui_adapter/server.py` (or the appropriate composition root) with a config flag selecting this adapter.
- [ ] **Architecture test** for the layer passes: `pytest tests/architecture/test_agent_ui_adapter_layer.py -q` (or `test_middleware_layer.py` for middleware adapters).
- [ ] **Documentation update:** the deep-dive doc (`AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md` or the middleware equivalent) gains a section for the new adapter family.
```

---

## 8. Always-on quick gate

Use this checklist on every backend PR regardless of category — it catches the issues that any change can introduce.

```markdown
**Always-on review (Checklist 8)**

- [ ] **`pytest tests/architecture/ -q`** passes. These tests are non-negotiable.
- [ ] **`pytest tests/ -q`** passes (or, on platforms without API keys, `pytest tests/ -q -m "not live_llm"`).
- [ ] **No secrets committed.** Search the diff for `OPENAI_API_KEY`, `WORKOS_API_KEY`, `AGENT_FACTS_SECRET`, `LANGCHAIN_API_KEY`, and other credential patterns. No `.env` file added.
- [ ] **No hardcoded model names.** Search the diff for `"gpt-4"`, `"claude-"`, `"gemini-"`, `"llama-"` — every match must be inside `services/base_config.py` or a test fixture. (H2)
- [ ] **No hardcoded prompts.** Search the diff for `"You are"`, `"Your task"`, `"You must"` — every match must be inside a `.j2` file. (H1, AP-3, G-3)
- [ ] **No `live_llm` calls in CI tests.** New tests calling a real LLM are tagged `@pytest.mark.live_llm` and CI excludes that marker.
- [ ] **All new public functions / classes have a docstring** stating purpose, parameters, and (if applicable) the layer they belong to.
- [ ] **No `print(...)` left in code.** Logging via the layer's own logger.
- [ ] **No `# TODO` without a tracked issue link.**
- [ ] **PR description includes** (a) the layer(s) touched, (b) any architecture invariant the PR strengthens or weakens, (c) the rollback plan if applicable.
```

---

## Reviewer escalation matrix

If during review you observe one of these, do not approve — escalate to an architecture-owning reviewer:

| Pattern observed | Why it's a stop-the-line | Reference |
|---|---|---|
| New file under `trust/` with any I/O or logging | Breaks the trust-kernel purity rule that the entire architecture depends on. | I-2 |
| New file under `components/` importing `langgraph` or `langchain*` | Breaks framework-swap promise (Phase 4 of `PLAN_v2.md`). | I-3 |
| New file under `services/` importing from `components/` | Reverse-coupling — services should never know about domain logic. | I-5 |
| Orchestration node growing past 50 lines with no extraction | Domain logic is leaking into the topology layer (AP-5). | I-7, G-1 |
| LLM call in any layer without `eval_capture.record()` | Breaks per-user analysis and meta-judge eval coverage. | H5, I-11, G-2 |
| Hardcoded prompt string (any layer) | Bypasses prompt management; blocks A/B testing and non-engineer edits. | H1, AP-3, G-3 |
| `from middleware.adapters.* import <SDK type>` outside `middleware/adapters/` | SDK type leak from the frontend ring boundary. | I-10 |
| `from langgraph...` or `from langchain...` inside `agent_ui_adapter/` outside `adapters/runtime/` | SDK type leak from the adapter ring boundary. | I-9 |
| Trust kernel signed-field change without a re-signing migration | Existing signed records become unverifiable on next load. | Checklist 6 |
| New tool with no rejection test | Gap blindness (TAP-4). | TAP-4 |

---

## References

- `docs/Architectures/BACKEND_SOLUTION_ARCHITECTURE.md` — the canonical backend architecture with full invariant definitions (I-1..I-14), pattern catalog, and gap analysis (G-1..G-12).
- `docs/Architectures/FOUR_LAYER_ARCHITECTURE.md` — four-layer rules, signed-vs-unsigned classification, governance feedback phases.
- `docs/Architectures/AGENT_UI_ADAPTER_ARCHITECTURE.md` and `AGENT_UI_ADAPTER_ADAPTERS_DEEP_DIVE.md` — adapter-ring rules (referenced by Checklist 7).
- `docs/style-guides/STYLE_GUIDE_LAYERING.md` — composable-layering base.
- `docs/style-guides/STYLE_GUIDE_PATTERNS.md` — H1–H7, V1–V6 patterns referenced by all checklists.
- `AGENTS.md` — workspace boundaries ("always / ask first / never") and the anti-pattern catalog AP-1..AP-5 / TAP-1..TAP-4.
- `tests/architecture/` — the live-fire enforcement layer; if a test fails, fix the placement, do not silence the test.
