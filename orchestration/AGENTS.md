# orchestration/ — Graph Topology (LangGraph)

> Nested guide. Loads when Claude reads a file under `orchestration/`. Root
> `AGENTS.md` owns the inter-layer invariants; `tests/architecture/` enforces
> them. This file is local guidance.

## What orchestration is

LangGraph graph topology (`react_loop.py`) and state (`state.py`). This is the
**only** layer that may import `langgraph`/`langchain`. It wires components and
services into a graph — it does not make domain decisions.

## AP-5 — Nodes are thin wrappers

All logic delegates to `components/` and `services/`. **No domain logic in
orchestration nodes** — max ~10–15 lines each. Putting routing heuristics
directly in `react_loop.py` couples logic to LangGraph and breaks the
framework-swap fallback (PLAN_v2.md Phase 4). If a node grows past a wrapper,
the logic belongs in a component or service.

## Adding a graph node

Adding a node to `react_loop.py` is an **`⚠️ Ask first`** event (it changes the
graph contract). When you do: the node stays thin; the behavior lives in a
component/service; and if it introduces a new abstraction or deviates from an
architecture invariant, append an ADR (see root `AGENTS.md` → Decision records).

## Config rule

- `.j2` templates hold **human intent** (prose policy).
- `routing_config.py` holds **numeric thresholds**.
- The meta-optimizer tunes numbers; humans write policy. Don't put thresholds in
  templates or policy prose in `routing_config.py`.

## L4 testing rules (orchestration/)

- Trust-gate failure-mode matrix, governance feedback-loop simulations, binary
  outcome scenarios. Tagged `@pytest.mark.simulation` (L4, on-demand).
- **Never run live LLM in CI** (`@pytest.mark.live_llm` is excluded by default).
