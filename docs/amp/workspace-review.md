# ReAct Agent with Dynamic Model Selection — Workspace Review

**Date:** 2026-04-17  
**Status:** Healthy — 540 tests passing, 0 failures

## Overview

A LangGraph-based ReAct agent with a strict **4-layer architecture** (Trust Kernel → Services → Components → Orchestration), plus an offline Meta-Optimization package.

## Architecture

```
Layer 4: Orchestration (LangGraph StateGraph)
  └── react_loop.py, state.py, cli.py

Layer 3: Vertical Components (framework-agnostic domain logic)
  └── router.py, evaluator.py, schemas.py, routing_config.py

Layer 2: Horizontal Services (domain-agnostic infrastructure)
  ├── base_config.py, llm_config.py, prompt_service.py
  ├── guardrails.py, eval_capture.py, observability.py
  ├── governance/ (agent_facts_registry, black_box, guardrail_validator, phase_logger)
  └── tools/ (registry, shell, file_io, web_search)

Layer 1: Trust Kernel (pure types, protocols, crypto)
  └── enums.py, models.py, protocols.py, signature.py, exceptions.py, cloud_identity.py

Meta-Optimization (offline, separate package)
  └── judge.py, analysis.py, drift.py, run_eval.py
```

Dependencies flow strictly downward. `components/` and `services/` have **zero** LangGraph/LangChain imports (enforced by `tests/architecture/test_dependency_rules.py`), keeping the Phase 4 Pydantic AI fallback viable.

## Area Status

| Area | Status |
|---|---|
| **Orchestration** | Full ReAct loop: `guard_input → route → call_llm → execute_tool → evaluate → continue/done`. Checkpointing (SQLite) + `interrupt_before` for human-in-the-loop |
| **Routing** | 5-branch MECE decision tree (budget-downgrade, retry-after-backoff, escalate-after-N-failures, capable-for-planning, steady-state-fast) |
| **Security** | 3-layer defense-in-depth: LLM-as-judge input guardrail, deterministic tool validators (command allowlist, path sandbox), regex+LLM output guardrails (PII/API key scanning) |
| **Trust Kernel** | AgentFacts identity model, HMAC signatures, cloud IAM bindings, audit trails |
| **Governance** | BlackBoxRecorder, PhaseLogger, AgentFactsRegistry, GuardRailValidator |
| **Meta (offline)** | LLM judge, drift detector, analytics engine, eval pipeline scaffolding |
| **Tests** | 540 passing across all layers + architecture dependency enforcement tests |
| **Issue** | `logfire` plugin has an OpenTelemetry import conflict (harmless — tests pass with `-p no:logfire`) |

## Graph Flow

```
START → guard_input_node
  ├── [rejected] → END
  └── [accepted] → route_node → call_llm_node
                                   ├── [tool_call] → execute_tool_node → evaluate_node
                                   ├── [final_answer] → evaluate_node
                                   └── [budget_exceeded] → END
                                                            evaluate_node
                                                              ├── [continue] → route_node (loop)
                                                              └── [done] → END
```

## Key Files

| File | Purpose |
|---|---|
| `cli.py` | CLI entry point, wires config + graph + tools |
| `orchestration/state.py` | `AgentState` TypedDict with annotated reducers |
| `orchestration/react_loop.py` | `build_graph()` — topology + thin-wrapper nodes |
| `components/router.py` | `select_model()` — 5-branch MECE routing |
| `components/evaluator.py` | `classify_outcome()`, `check_continuation()` |
| `components/schemas.py` | `StepResult`, `ErrorRecord` |
| `components/routing_config.py` | `RoutingConfig` thresholds |
| `services/guardrails.py` | Input (LLM-as-judge) + Output (deterministic + LLM) |
| `services/llm_config.py` | `LLMService` wrapping `ChatLiteLLM` |
| `services/prompt_service.py` | Jinja2 template rendering |
| `services/governance/black_box.py` | `BlackBoxRecorder` for trace events |
| `services/governance/agent_facts_registry.py` | Agent identity registry with HMAC verification |
| `services/tools/registry.py` | `ToolRegistry` with cache-aware dispatch |
| `trust/models.py` | `AgentFacts`, `Capability`, `Policy`, `AuditEntry` |
| `trust/enums.py` | `IdentityStatus` (ACTIVE, SUSPENDED, REVOKED) |

## Test Coverage

- `tests/architecture/` — Dependency rule enforcement
- `tests/trust/` — Trust kernel models, enums, protocols, signatures, cloud identity
- `tests/services/` — Config, guardrails, LLM service, prompt service, tools, governance
- `tests/components/` — Router, evaluator, schemas, routing config
- `tests/orchestration/` — React loop, guard rejection, error propagation
- `tests/meta/` — Judge, analysis, drift, eval pipeline
- `tests/utils/` — Cloud providers, code analysis

## Tech Stack

- **Orchestration:** LangGraph `StateGraph`
- **LLM calls:** LiteLLM via `ChatLiteLLM`
- **Validation:** Pydantic v2
- **Prompts:** Jinja2 templates
- **Observability:** LangSmith + per-concern structured log files
- **CLI output:** Rich
- **Tests:** pytest + pytest-asyncio + Hypothesis
