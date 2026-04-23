# SPIKE_B — Self-hosted LangGraph Developer in FastAPI


| Field                     | Value                                                          |
| ------------------------- | -------------------------------------------------------------- |
| **Sprint**                | 0                                                              |
| **Story**                 | S0.3.1                                                         |
| **Hypotheses under test** | H10 (LGP-SHL ↔ existing graph), H11 (self-hosted in Cloud Run) |
| **Verdict**               | ➖ **SKIPPED** per Sprint 0 decision **D-S0-5**                 |


## Why skipped

The two hypotheses Spike B was meant to retire are **already retired** by the
existing codebase:


| Hypothesis                                                                                             | Existing evidence                                                                                                                                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H10 — the existing `react_loop` graph is embeddable in a FastAPI app and exposes Agent Protocol routes | `agent_ui_adapter/server.py:build_app()` plus `tests/agent_ui_adapter/test_smoke_langgraph.py` already wire `LangGraphRuntime(graph=build_graph(...))` into a FastAPI app and stream Agent-Protocol-shaped SSE events end-to-end against the real graph.                                                             |
| H11 — self-hosted LangGraph fits in Cloud Run                                                          | The graph + adapter together import `langgraph>=0.2` and `langchain-litellm>=0.2`; the resulting wheel weight is well under Cloud Run's 1 vCPU / 2 GB envelope. (Confirmable cheaply when Sprint 2 actually deploys it; running it on `min=0` adds at most cold-start latency, which is a separate tracked concern.) |


Re-running both as a Sprint-0 spike would not generate new evidence.

## What is *deferred* (not skipped)

The specific `langgraph.json`-config-based loading mechanism (vs the current
direct Python import of `build_graph`) is **owned by Sprint 1 story S1.1.1**
and validated as part of that story's acceptance tests. We picked
`langgraph-cli[inmem]` as the loader — adopting it is a Sprint 1 task, not
a Sprint 0 spike.

## Re-open trigger

If S1.1.1's `langgraph.json` loader cannot be made to work with
`langgraph-cli[inmem]`, we open Spike B as a salvage exercise and may
invoke the V2-Frontier fallback (LangGraph Platform Cloud SaaS Plus,
+$89-104/mo).

## Decision audit

- See `docs/plan/frontend/SPRINT_0_RUNBOOK.md` §0 row **D-S0-5** for the
full rationale and chain of evidence.