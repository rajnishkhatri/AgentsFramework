# Developer Guide -- Extend the framework without breaking the layer rules

You have read `[AGENTS.md](../AGENTS.md)` and you are about to add something -- a new tool, a new prompt, a new orchestration node, a new trust type, a new meta tool. This guide tells you what one bad import will cost you, the one question every PR must answer, the five-layer cheat sheet that makes the answer obvious, and the five recipes that keep your change inside the rules. Each recipe ends with the exact `pytest` command that proves you got it right.

```
What you must answer in every PR:
   "In which layer does this artifact belong, and which test enforces that?"

The five layers, top-down:
   meta/         (offline tools; may import trust, services, components)
   orchestration/   (graph topology only; the only place langgraph lives)
   components/   (framework-agnostic domain logic)
   services/     (horizontal infrastructure; framework-agnostic except llm_config.py)
   trust/        (pure types and pure functions; zero outward imports)

The eight tests that catch a layering mistake:
   pytest tests/architecture/test_dependency_rules.py -q
```

## Skim these headings to read this guide in two minutes

1. [One vertical-to-vertical import breaks three things at once](#1-one-vertical-to-vertical-import-breaks-three-things-at-once)
2. [The question every PR must answer in 30 seconds](#2-the-question-every-pr-must-answer-in-30-seconds)
3. [Five layers, one cheat sheet, twelve tests that enforce it](#3-five-layers-one-cheat-sheet-twelve-tests-that-enforce-it)
4. [Add anything in one of five recipes](#4-add-anything-in-one-of-five-recipes)
  - [4.1 Add a trust type in three rules and one re-export](#41-add-a-trust-type-in-three-rules-and-one-re-export)
  - [4.2 Add a horizontal service in five steps and one logger entry](#42-add-a-horizontal-service-in-five-steps-and-one-logger-entry)
  - [4.3 Add a vertical component without importing another vertical](#43-add-a-vertical-component-without-importing-another-vertical)
  - [4.4 Add an orchestration node by editing only `react_loop.py` and `state.py](#44-add-an-orchestration-node-by-editing-only-react_looppy-and-statepy)`
  - [4.5 Add a meta tool that reads logs and config but never the graph](#45-add-a-meta-tool-that-reads-logs-and-config-but-never-the-graph)
5. [Every recipe ends with the gate that catches its failure](#5-every-recipe-ends-with-the-gate-that-catches-its-failure)
6. [The daily loop is five commands](#6-the-daily-loop-is-five-commands)
7. [Avoid these nine anti-patterns -- they are the failure modes the gates catch](#7-avoid-these-nine-anti-patterns----they-are-the-failure-modes-the-gates-catch)
8. [Where to look -- a glossary from common topics to the section that owns them](#8-where-to-look----a-glossary-from-common-topics-to-the-section-that-owns-them)

---

## 1. One vertical-to-vertical import breaks three things at once

You have a clone, the tests are green, and you reach for the obvious thing: a `from components.router import select_model` inside `services/eval_capture.py`, or a `from langgraph.graph import StateGraph` inside `components/router.py`, or a `from orchestration.react_loop import build_graph` inside `meta/optimizer.py`. Each of these *seems* harmless. Each of them collapses three independent guarantees at once.

What breaks, concretely:

- **The architecture tests fail.** `tests/architecture/test_dependency_rules.py` scans every `.py` file in each layer and refuses any import that crosses the wrong boundary. A `services/` file that imports from `components/` fails `test_services_does_not_import_components`. A `components/` file that imports `langgraph` fails `test_components_no_framework_imports`. A `meta/` file that imports from `orchestration/` fails `test_meta_does_not_import_orchestration`. The build is red on the next CI run; the diff cannot merge.
- **The framework-swap fallback collapses.** `meta/fallback_prototype.py` is a LangGraph-free implementation of the same loop, built by composing `components/router` and `components/evaluator` and calling `litellm.completion` directly. It exists so that if LangGraph becomes the wrong substrate, the agent can be rebuilt without a rewrite of the components. The moment a component imports `langgraph`, that fallback stops being viable -- the component goes with the framework.
- **The trust kernel guarantee collapses.** `trust/` imports nothing from `services`, `components`, `orchestration`, or `meta`; that is the invariant that makes signature recomputation, identity verification, and review-schema validation safe to call from anywhere. A `trust/` file that imports anything else loses pure-function semantics; a `services/` file that mutates trust types in-place crosses a layer boundary; either failure puts the kernel in a state where every consumer must defensively re-validate.

These are not three different problems. They are one structural mistake -- a downward arrow inverted -- with three visible symptoms. The rest of this guide is organised around preventing that one mistake.

---

## 2. The question every PR must answer in 30 seconds

Every change to this workspace is one answer to one question:

> *In which layer does this artifact belong, and which test enforces that?*

You can apply that question to any line of code:


| You are about to add...                                                                        | The layer is...               | The enforcing test is...                                                                                                                         |
| ---------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| A new Pydantic model that two services or a service and a component will both consume          | `trust/`                      | `tests/architecture/test_dependency_rules.py::TestDependencyRules::test_trust_does_not_import_utils` (kernel purity)                             |
| A new shared protocol (e.g. a new provider interface)                                          | `trust/protocols.py`          | Same as above.                                                                                                                                   |
| A new horizontal capability (logging, signing, caching, prompt rendering, eval capture)        | `services/`                   | `test_services_does_not_import_components`, `test_services_no_framework_imports_except_llm_config`                                               |
| A new domain-logic function called from the orchestrator (routing, evaluation, schema parsing) | `components/`                 | `test_components_no_framework_imports`, `test_components_does_not_import_orchestration`                                                          |
| A new graph node, edge, or conditional route                                                   | `orchestration/react_loop.py` | (Architectural rule rather than test: orchestration nodes must remain thin -- 10-15 lines -- delegating logic to `components/` and `services/`.) |
| A new offline tool that reads logs / eval data / config and acts                               | `meta/`                       | `test_meta_does_not_import_orchestration`                                                                                                        |
| A new tool implementation (shell variant, file IO variant, web search)                         | `services/tools/`             | `test_services_does_not_import_components`, `test_services_no_framework_imports_except_llm_config`                                               |
| A new prompt template                                                                          | `prompts/<subdir>/`           | (No layer test; rendered via `PromptService.render_prompt`.)                                                                                     |
| A new architecture rule                                                                        | `tests/architecture/`         | This file *is* the rule.                                                                                                                         |


If the answer to "which layer?" is unclear, the artifact probably belongs in a different shape (split into two pieces; promote a type into `trust/`; demote a behaviour into `services/`). The next chapter gives you the cheat sheet that makes the answer obvious in most cases.

---

## 3. Five layers, one cheat sheet, twelve tests that enforce it

You have the breakage and the question. Here is the shared model that makes the question quick to answer.

The five layers, from foundation upward, with what each one is and what it must not import:


| Layer            | What lives here (what actually exists in code today)                                                                                                                                                                                                                                                                                                                                                                                                                               | Imports allowed                                                                                                                                                    | Imports forbidden                                                                                                     |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| `trust/`         | `Capability`, `Policy`, `AgentFacts`, `AuditEntry`, `VerificationReport`, `CloudBinding` (`trust/models.py`), the IAM DTOs in `trust/cloud_identity.py`, the `IdentityStatus` enum, the `IdentityProvider`/`PolicyProvider`/`CredentialProvider` protocols, `compute_signature`/`verify_signature`, the review-schema types (`Severity`, `Verdict`, `DimensionStatus`, `Certificate`, `ReviewFinding`, `DimensionResult`, `ReviewReport`), and the `TrustProviderError` hierarchy. | stdlib, `pydantic`, other modules inside `trust/`                                                                                                                  | Anything in `services/`, `utils/`, `components/`, `agents/`, `orchestration/`, `meta/`.                               |
| `services/`      | `prompt_service.PromptService`, `llm_config.LLMService`, `guardrails.{InputGuardrail,OutputGuardrail,output_guardrail_scan}`, `eval_capture.record`, `observability.{setup_logging,FrameworkTelemetry,InstrumentedCheckpointer}`, `governance/{black_box,phase_logger,agent_facts_registry,guardrail_validator}`, `tools/{registry,shell,file_io,web_search,sandbox}`, `base_config.{ModelProfile,AgentConfig,default_fast_profile}`.                                              | `trust/`, stdlib, `pydantic`, sibling `services/` modules (cautiously). `services/llm_config.py` is the only file allowed to import `langchain_litellm`/`litellm`. | `components/`, `orchestration/`, `meta/`, `langgraph`/`langchain` (except `llm_config.py`).                           |
| `components/`    | `router.select_model`, `evaluator.{classify_outcome,build_step_result,check_continuation,parse_response_structured}`, `schemas.{ErrorRecord,StepResult,EvalRecord,TaskResult}`, `routing_config.RoutingConfig`, `sprint_schemas.`*.                                                                                                                                                                                                                                                | `trust/`, `services/`, stdlib, `pydantic`.                                                                                                                         | `orchestration/`, `meta/`, `langgraph`/`langchain`/`langchain_core` (anything that ties domain logic to a framework). |
| `orchestration/` | `state.AgentState` (TypedDict over `MessagesState`), `react_loop.build_graph` plus the five node callables (`guard_input_node`, `route_node`, `call_llm_node`, `execute_tool_node`, `evaluate_node`) and the three conditional-route helpers (`_guard_routing`, `_parse_response`, `_should_continue`).                                                                                                                                                                            | `trust/`, `services/`, `components/`, `langgraph`, `langchain_core`.                                                                                               | `meta/`.                                                                                                              |
| `meta/`          | `judge`, `run_eval`, `analysis`, `drift`, `feasibility`, `optimizer`, `code_reviewer`, `fallback_prototype`, `CodeReviewerAgentTest/`.                                                                                                                                                                                                                                                                                                                                             | `trust/`, `services/`, `components/`, stdlib, third-party.                                                                                                         | `orchestration/` (this is the only forbidden direction; meta tools may freely import everything below).               |


The eight dependency-rule tests in `tests/architecture/test_dependency_rules.py` enforce the cells of this table:


| Test                                                                                     | Rule it enforces                                                                  |
| ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `test_trust_does_not_import_utils` (`tests/architecture/test_dependency_rules.py:47-54`) | `trust/` does not import `utils`, `agents`, or `governance`.                      |
| `test_trust_does_not_import_agents` (`:56-63`)                                           | `trust/` does not import `agents`.                                                |
| `test_utils_does_not_import_agents` (`:65-72`)                                           | `utils/` does not import `agents`, `governance`, or `orchestration`.              |
| `test_components_no_framework_imports` (`:74-86`)                                        | `components/` does not import `langgraph`/`langchain`/`langchain_core`.           |
| `test_components_does_not_import_orchestration` (`:88-99`)                               | `components/` does not import `orchestration/`.                                   |
| `test_services_no_framework_imports_except_llm_config` (`:101-114`)                      | `services/` does not import `langgraph`/`langchain` -- except in `llm_config.py`. |
| `test_services_does_not_import_components` (`:116-127`)                                  | `services/` does not import `components/`.                                        |
| `test_meta_does_not_import_orchestration` (`:129-140`)                                   | `meta/` does not import `orchestration/`.                                         |


Plus the four placement tests in `tests/architecture/test_code_reviewer_placement.py`:


| Test                                                                                                              | Rule it enforces                                                                                                     |
| ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `test_imports_only_trust_and_stdlib` (review schema) (`tests/architecture/test_code_reviewer_placement.py:19-54`) | `trust/review_schema.py` imports only stdlib + `trust/`.                                                             |
| `test_no_io_imports` (`:56-82`)                                                                                   | `trust/review_schema.py` imports no I/O modules (`os`, `pathlib`, `subprocess`, `socket`, `requests`, `httpx`, ...). |
| `test_imports_only_trust_and_stdlib` (code analysis) (`:89-117`)                                                  | `utils/code_analysis.py` does not import `agents`/`governance`.                                                      |
| `test_uses_only_stdlib_externals` (`:119-153`)                                                                    | `utils/code_analysis.py` uses only `ast`, `pathlib`, `typing`, `trust`.                                              |


Run them all in a second:

```bash
pytest tests/architecture/ -q
```

A green run means every layer rule is intact across every file. A red run names the file and the forbidden import. Treat that test suite as the authoritative grammar of the architecture; everything else in this guide is a recipe that respects it.

> **Doc-vs-code naming.** The architectural reference docs (`[docs/STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md)`, `[docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](FOUR_LAYER_ARCHITECTURE.md)`) describe the horizontal layer as `utils/` and the vertical layer as `agents/`. The actual workspace ships them as `services/` and `components/`. The dependency tests target the **real** directories. When you read the older docs, mentally substitute `services/` for `utils/` and `components/` for `agents/`. The `LAYER_DIRS` map at `tests/architecture/test_dependency_rules.py:30-44` is the source of truth.

---

## 4. Add anything in one of five recipes

The five canonical extensions cover every kind of artifact you can add to this workspace. Each recipe is short on purpose: pick the layer, follow the steps, run the gate.

### 4.1 Add a trust type in three rules and one re-export

A new shared Pydantic model belongs in `trust/` only when **two or more layers above the kernel will consume it**. A type used by exactly one service stays in that service. Pre-emptively promoting types makes `trust/` a dumping ground.

**Rules:**

1. The type imports nothing from `services/`, `components/`, `orchestration/`, or `meta/`. Only stdlib + `pydantic` + other `trust/` modules.
2. The type does no I/O (no `open(...)`, no `subprocess`, no network). It is data and pure functions only.
3. If the type carries a signature or feeds one, the signed-vs-unsigned boundary is explicit: a field that determines what an agent is *authorized* to do is signed; everything else is operational metadata. (See `services/governance/agent_facts_registry.py:41-45` for how the registry partitions on the existing `signature_hash` field.)

**File template (`trust/credential_record.py`):**

```python
"""CredentialRecord -- ephemeral credential value object.

Lives in trust/ because credential_cache.py (services) and
authorization_service.py (services) both consume it.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CredentialRecord(BaseModel):
    agent_id: str
    provider: Literal["aws_sts", "gcp_iam", "azure_ad", "local"]
    issued_at: datetime
    expires_at: datetime
    scope: list[str]
    credential_hash: str
```

**Re-export from the package:**

```python
# trust/__init__.py
from trust.credential_record import CredentialRecord

__all__ = [..., "CredentialRecord"]
```

**Test to write (failure path first per the AGENTS.md TAP-4 rule):**

```python
# tests/trust/test_credential_record.py
import pytest
from datetime import datetime, timedelta

from trust import CredentialRecord


def test_invalid_provider_rejected():
    with pytest.raises(ValueError):
        CredentialRecord(
            agent_id="agent-1",
            provider="not_a_provider",  # type: ignore[arg-type]
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            scope=[],
            credential_hash="x" * 64,
        )


def test_valid_credential_round_trip():
    record = CredentialRecord(
        agent_id="agent-1",
        provider="local",
        issued_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=15),
        scope=["read:logs"],
        credential_hash="x" * 64,
    )
    assert CredentialRecord(**record.model_dump()) == record
```

**Gate to run:**

```bash
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_trust_does_not_import_utils -q
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_trust_does_not_import_agents -q
pytest tests/trust/test_credential_record.py -q
```

The first two prove you did not accidentally import a service. The third proves the model behaves.

> **Reality check on existing trust types.** `AGENTS.md` lists `TrustTraceRecord`, `PolicyDecision`, and `CredentialRecord` as key types. As of this writing, none of those three exist as code symbols in the repository -- they are documented intent, not shipped API. If you depend on them, add them yourself using this recipe; do not assume `from trust import TrustTraceRecord` will succeed.

### 4.2 Add a horizontal service in five steps and one logger entry

A horizontal service belongs in `services/` when the capability is **domain-agnostic** (works the same whether called from a routing component, a sprint planner, or an orchestration node) and is or will be consumed by **two or more callers**.

**Steps:**

1. **Write the module under `services/`.** Single responsibility (rate limiter, cost tracker, signing helper, ...). Imports from `trust/`, stdlib, `pydantic`, and -- only if absolutely needed -- a sibling service.
2. **Use `trust/` types where you need shared data.** Do not invent a new shape inside the service if one already exists.
3. **Render any prompts via `PromptService.render_prompt(template_name, **context)`.** Templates live under `prompts/<your_subdir>/`. Never inline a prompt string. (See [Anti-pattern 3](#73-hardcoded-prompts-bypass-promptservice).)
4. **Record any LLM call via `services.eval_capture.record(...)`** with a unique `target` tag. The signature is `async def record(target, ai_input, ai_response, config, step=0, model=None, tokens_in=None, tokens_out=None, cost_usd=None, latency_ms=None)` (`services/eval_capture.py:20-30`).
5. **Add your logger to `logging.json`.** Pattern: a dedicated handler writing to `logs/<service>.log`, plus a logger named after the module path with `level: "INFO"` and `propagate: false`.

**File template (`services/rate_limiter.py`):**

```python
"""Rate limiter -- horizontal service.

Domain-agnostic: works for any caller that needs to throttle
per-agent or per-endpoint requests. Imports only from trust/
and stdlib.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

logger = logging.getLogger("services.rate_limiter")


class RateLimiter:
    """Sliding-window per-key request limiter."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > self._window:
            events.popleft()
        if len(events) >= self._max:
            logger.info("rate_limited", extra={"key": key, "count": len(events)})
            return False
        events.append(now)
        return True
```

**Logger registration (`logging.json` excerpt):**

```json
{
    "handlers": {
        "rate_limiter": {
            "class": "logging.FileHandler",
            "filename": "logs/rate_limiter.log",
            "mode": "a",
            "level": "INFO",
            "formatter": "json"
        }
    },
    "loggers": {
        "services.rate_limiter": {
            "handlers": ["rate_limiter", "console"],
            "level": "INFO",
            "propagate": false
        }
    }
}
```

**Tests to write (failure-path first):**

```python
# tests/services/test_rate_limiter.py
import time
from services.rate_limiter import RateLimiter


def test_blocks_after_threshold():
    limiter = RateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False  # rejection path tested first


def test_allows_after_window_expires(monkeypatch):
    limiter = RateLimiter(max_requests=1, window_seconds=0.05)
    assert limiter.allow("k") is True
    time.sleep(0.06)
    assert limiter.allow("k") is True
```

**Gate to run:**

```bash
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_services_does_not_import_components -q
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_services_no_framework_imports_except_llm_config -q
pytest tests/services/test_rate_limiter.py -q
```

> `**prompts/includes/` is documented but does not yet exist.** `AGENTS.md:63` mentions `prompts/includes/` for reusable Jinja partials. The directory has not been created. If your service needs a partial, create the directory, add the `.j2`, and reference it with `{% include "includes/<name>.j2" %}` from your template.

### 4.3 Add a vertical component without importing another vertical

A new component belongs in `components/` when it is a **piece of domain-specific logic** called by an orchestration node -- routing, evaluation, scoring, classification, schema parsing, plan-building.

**Rules:**

1. Imports come only from `services/`, `trust/`, stdlib, and `pydantic`. **No `langgraph`. No `langchain`. No `langchain_core`.** That is what `test_components_no_framework_imports` enforces.
2. **No peer imports.** `components/router.py` does not import from `components/evaluator.py` and vice versa. Shared types (`ErrorRecord`, `StepResult`, `RoutingConfig`) live in `components/schemas.py` or `components/routing_config.py`. Both are imported, neither imports the other.
3. **The orchestrator composes you.** Your component is a function or a small class with a single entry point. The orchestrator passes inputs and routes outputs.

**File template (`components/cost_estimator.py`):**

```python
"""Cost estimator -- vertical component.

Pure function. Imports only services.base_config (for ModelProfile)
and stdlib. No framework, no peer component.
"""
from __future__ import annotations

from services.base_config import ModelProfile


def estimate_step_cost_usd(profile: ModelProfile, tokens_in: int, tokens_out: int) -> float:
    """Estimate the dollar cost of one step given a profile and token counts."""
    in_cost = (tokens_in / 1_000_000) * (profile.cost_per_million_input or 0.0)
    out_cost = (tokens_out / 1_000_000) * (profile.cost_per_million_output or 0.0)
    return in_cost + out_cost
```

**Tests to write:**

```python
# tests/components/test_cost_estimator.py
from services.base_config import default_fast_profile
from components.cost_estimator import estimate_step_cost_usd


def test_zero_tokens_zero_cost():
    profile = default_fast_profile()
    assert estimate_step_cost_usd(profile, 0, 0) == 0.0


def test_known_token_counts_compute_expected_cost():
    profile = default_fast_profile()
    cost = estimate_step_cost_usd(profile, tokens_in=1_000_000, tokens_out=1_000_000)
    expected = (profile.cost_per_million_input or 0.0) + (profile.cost_per_million_output or 0.0)
    assert cost == expected
```

**Gate to run:**

```bash
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_components_no_framework_imports -q
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_components_does_not_import_orchestration -q
pytest tests/components/test_cost_estimator.py -q
```

### 4.4 Add an orchestration node by editing only `react_loop.py` and `state.py`

A new orchestration node belongs in `orchestration/react_loop.py` when the agent needs a **new step in the ReAct loop**. Adding a node is the only change in this guide that is gated by `AGENTS.md` "Ask first" -- it is a deliberate decision, not a routine one. (See `AGENTS.md:25-29`.)

**Rules:**

1. The node is a thin wrapper -- 10-15 lines. All logic lives in `components/` or `services/`. (`AGENTS.md:49`.)
2. The node accepts and returns the `AgentState` TypedDict. New fields you need go in `orchestration/state.py`.
3. The node is added to the graph in `build_graph(...)` together with its edges (an outbound edge to the next node, or a conditional-route helper that maps state to a node name).
4. If the node can fail in a user-visible way, add a chapter to `[docs/USER_MANUAL.md](USER_MANUAL.md#11-six-named-failures-cover-every-way-one-query-can-break)` explaining the new failure mode.

**File template (the new node + edge wiring inside `orchestration/react_loop.py`):**

```python
async def post_eval_summary_node(state: AgentState) -> dict:
    """Compose a one-line summary of the run after evaluation completes.

    Thin wrapper: delegates to components.summary.compose_summary.
    """
    summary_text = compose_summary(
        steps=state["step_count"],
        cost=state["total_cost_usd"],
        last_outcome=state["last_outcome"],
    )
    return {"reasoning_trace": state["reasoning_trace"] + [summary_text]}


# Inside build_graph():
builder.add_node("post_eval_summary", post_eval_summary_node)
# Re-route the existing "done" path through this node:
builder.add_conditional_edges("evaluate", _should_continue, {
    "continue": "route",
    "done": "post_eval_summary",
})
builder.add_edge("post_eval_summary", END)
```

**Tests to write:**

```python
# tests/orchestration/test_post_eval_summary.py
import pytest
from orchestration.react_loop import post_eval_summary_node


@pytest.mark.asyncio
async def test_summary_appends_to_reasoning_trace():
    state = {"step_count": 3, "total_cost_usd": 0.01, "last_outcome": "done", "reasoning_trace": []}
    result = await post_eval_summary_node(state)
    assert len(result["reasoning_trace"]) == 1
```

**Gate to run:**

```bash
pytest tests/architecture/ -q             # the layer rules still hold
pytest tests/orchestration/ -q             # your new node test
python -m agent.cli "What is 2+2?"          # smoke: the graph still executes end to end
```

If your node introduces a new user-visible failure mode (a budget cap, a guard verdict, a tool error category), update `[docs/USER_MANUAL.md` chapter 11](USER_MANUAL.md#11-six-named-failures-cover-every-way-one-query-can-break) and the cross-reference to it from `[docs/PYRAMID_ANALYSIS.md](PYRAMID_ANALYSIS.md#cross-pyramid-interactions)`. The recipes in this guide and the named failures in the user manual must stay in sync.

### 4.5 Add a meta tool that reads logs and config but never the graph

A new meta tool belongs in `meta/` when it **operates offline on artifacts produced by the running agent** -- log files, eval JSONL, the trace and decisions JSONL, the routing config. Meta tools may freely import `trust/`, `services/`, and `components/`. They may not import from `orchestration/`. They run as standalone modules.

**Rules:**

1. No import from `orchestration/`. Read the trace JSONL, do not re-invoke the graph. (`test_meta_does_not_import_orchestration`.)
2. Add an `if __name__ == "__main__":` block so the module is runnable as `python -m meta.<your_tool>`. The four existing meta tools that follow this pattern: `meta.drift`, `meta.code_reviewer`, `meta.optimizer`, `meta.CodeReviewerAgentTest`.
3. Use `argparse` for the CLI; print one JSON object on stdout (or to `--output`); exit non-zero on failure.
4. If the tool is a long-running judge or evaluator, capture its LLM calls via `services.eval_capture.record(...)` with a `target` that names the meta tool.

**File template (`meta/cost_summarizer.py`):**

```python
"""Cost summarizer -- offline meta tool.

Reads logs/evals.log and prints the sum of cost_usd by model.
Runnable as: python -m meta.cost_summarizer [--evals-log logs/evals.log]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def summarize(evals_log_path: Path) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for line in evals_log_path.read_text().splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        model = record.get("model", "unknown")
        cost = record.get("cost_usd") or 0.0
        totals[model] += float(cost)
    return dict(totals)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evals-log", default="logs/evals.log", type=Path)
    args = parser.parse_args()
    if not args.evals_log.exists():
        print(json.dumps({"error": f"missing log {args.evals_log}"}))
        return 1
    print(json.dumps(summarize(args.evals_log), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Tests to write:**

```python
# tests/meta/test_cost_summarizer.py
import json
from pathlib import Path

from meta.cost_summarizer import summarize


def test_sum_costs_per_model(tmp_path: Path):
    log = tmp_path / "evals.log"
    log.write_text(
        "\n".join(
            json.dumps(rec)
            for rec in [
                {"model": "gpt-4o-mini", "cost_usd": 0.001},
                {"model": "gpt-4o-mini", "cost_usd": 0.002},
                {"model": "gpt-4o", "cost_usd": 0.05},
            ]
        )
    )
    assert summarize(log) == {"gpt-4o-mini": 0.003, "gpt-4o": 0.05}


def test_missing_log_returns_empty_when_file_missing(tmp_path: Path):
    log = tmp_path / "does-not-exist.log"
    assert not log.exists()
```

**Gate to run:**

```bash
pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_meta_does_not_import_orchestration -q
pytest tests/meta/test_cost_summarizer.py -q
python -m meta.cost_summarizer --evals-log logs/evals.log
```

---

## 5. Every recipe ends with the gate that catches its failure

The recipes in chapter 4 each named the exact `pytest` invocation that proves the change is well-formed. Together they form the layered enforcement table:


| Layer touched    | Layer-rule gate                                                                                                                                                                        | Functional gate                  | Optional smoke                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ----------------------------------------------------------------------- |
| `trust/`         | `pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_trust_does_not_import_utils -q` and `::test_trust_does_not_import_agents -q`                            | `pytest tests/trust/ -q`         | `python -c "from trust import <YourType>; print('ok')"`                 |
| `services/`      | `pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_services_does_not_import_components -q` and `::test_services_no_framework_imports_except_llm_config -q` | `pytest tests/services/ -q`      | `python -c "from services.<your_service> import <Symbol>; print('ok')"` |
| `components/`    | `pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_components_no_framework_imports -q` and `::test_components_does_not_import_orchestration -q`            | `pytest tests/components/ -q`    | --                                                                      |
| `orchestration/` | `pytest tests/architecture/ -q` (the full layer suite)                                                                                                                                 | `pytest tests/orchestration/ -q` | `python -m agent.cli "What is 2+2?"`                                    |
| `meta/`          | `pytest tests/architecture/test_dependency_rules.py::TestDependencyRules::test_meta_does_not_import_orchestration -q`                                                                  | `pytest tests/meta/ -q`          | `python -m meta.<your_tool> --help`                                     |


Plus the four runtime gates that exist regardless of which layer you touched:


| Runtime gate                                          | What it enforces                                                                                                        | What you do                                                                                                                                                                  |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `services.PromptService.render_prompt`                | All prompts are loaded from `prompts/` and rendered via Jinja2 -- no hardcoded prompt strings anywhere in the codebase. | Create your `.j2` file. Call `PromptService.render_prompt("<name>", **context)`.                                                                                             |
| `services.eval_capture.record(...)`                   | Every LLM call is recorded with `target`, `task_id`, `user_id`, model, tokens, cost, latency.                           | Call `await record(target="<your_target>", ai_input=..., ai_response=..., config=...)` after your LLM call.                                                                  |
| `logging.json`                                        | Each service logs to its own file under `logs/`.                                                                        | Add a handler + logger entry; do not call `logging.basicConfig` from your module.                                                                                            |
| `BlackBoxRecorder` and `PhaseLogger` (under `cache/`) | Every orchestration step and every routing/continuation decision is captured in append-only JSONL.                      | Nothing required for components/services -- inherited automatically. For new orchestration nodes, the node's `events` are recorded by the surrounding `react_loop.py` calls. |


A red layer-rule gate names the file and the import. A red functional gate names the test that broke. A red smoke command means the graph cannot build -- usually a missing dependency or a broken `state.py` field.

---

## 6. The daily loop is five commands

You have the recipes and the gates. The loop is short:

```bash
# 1. Install (once, or after pyproject changes):
pip install -e ".[dev]"

# 2. Run the full test suite (after every change):
pytest tests/ -q

# 3. Run the architecture suite explicitly (the gate that must always pass):
pytest tests/architecture/ -q

# 4. Smoke-test the agent end to end:
python -m agent.cli "What is 2+2?"

# 5. Build and run the Docker image (before merging):
docker build -t react-agent . && \
    docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -e AGENT_FACTS_SECRET=change-me \
        react-agent "What is 2+2?"
```

Five lines, all from `AGENTS.md` Key Commands. Step 3 is technically a subset of step 2, but you should be able to recite it from memory because it is the gate that fails most often after a layering mistake.

> **Packaging note (do not let it block you).** `pyproject.toml` Hatch wheel packages list `trust`, `utils`, `components`, `services`, `orchestration`, `meta` -- there is no top-level `agent` package. The documented `python -m agent.cli` works only when the parent of `agent/` is on `sys.path`. Inside `agent/`, `python cli.py "<task>"` works directly. Both invocations are documented in `README.md` and the user manual; choose the one that fits your context.

---

## 7. Avoid these nine anti-patterns -- they are the failure modes the gates catch

The patterns below are exactly what `tests/architecture/`, `services.PromptService`, `services.eval_capture`, and `logging.json` exist to catch. Each one is a real-world version of "import inverted" or "logic in the wrong layer." The gallery is consistent with the catalog in `[docs/STYLE_GUIDE_LAYERING.md` Anti-Patterns](STYLE_GUIDE_LAYERING.md#anti-patterns).

### 7.1 A God Utility hides four responsibilities behind one method and turns every change into shotgun surgery

A single `services/<everything>.py` that renders prompts, validates input, logs eval data, retrieves memory, and signs identity cards. Every change becomes shotgun surgery; the single-responsibility violation makes mocking impossible. **Fix:** one module per responsibility.

### 7.2 A vertical-to-vertical import couples two components the orchestrator deliberately keeps independent

`components/router.py` importing `components/evaluator.py` (or vice versa) ties together two components that the orchestrator composes in sequence; the swap-one-out promise breaks. **Fix:** shared types live in `components/schemas.py` or `components/routing_config.py`; both consume those, neither imports the other.

### 7.3 Hardcoded prompts bypass `PromptService` and become invisible to logs and A/B tests

`prompt = f"You are a math tutor..."` inside a module is invisible to `logs/prompts.log`, cannot be A/B tested, and changing it requires a code-review cycle. **Fix:** create a `.j2` template under `prompts/<your_subdir>/`, render via `PromptService.render_prompt`.

### 7.4 Business logic inside a horizontal service makes the service domain-specific and stops it from being shared

`PromptService.render_prompt` deciding which template to use based on the topic stops being domain-agnostic; adding a new domain requires editing the service. **Fix:** the caller passes the template name; the service renders whatever it is given.

### 7.5 Per-component logging produces inconsistent files no one reads

Each component opening its own log file produces inconsistent formats, scattered files, and missing logger setup. **Fix:** use `services.eval_capture.record(...)` or call a service-specific logger registered in `logging.json`.

### 7.6 Trust types defined inside a service force every other consumer into hidden peer coupling

`AgentFacts` defined in `services/governance/agent_facts_registry.py` would force every other consumer of `AgentFacts` to import from a peer service; tests would need a registry to use the type. **Fix:** the type lives in `trust/models.py`; the registry imports it.

### 7.7 Horizontal-to-horizontal direct calls for shared data make every service depend on every other

`authorization_service.evaluate(agent_id)` calling `identity_service.get(agent_id)` to fetch facts ties authorization to identity; testing one requires mocking the other; identity API changes break authorization. **Fix:** the orchestrator fetches facts and passes them as a parameter -- `authorization_service.evaluate(facts=facts, action=..., context=...)`.

### 7.8 An upward call from `meta/` into `orchestration/` creates a circular dependency and breaks the framework-swap fallback

`meta/optimizer.py` invoking `build_graph(...)` creates a circular dependency (orchestration -> services -> meta -> orchestration); breaks `test_meta_does_not_import_orchestration`; collapses the framework-swap fallback. **Fix:** read the artifacts (`logs/evals.log`, `cache/black_box_recordings/`) the running agent already produced. If you genuinely need to re-execute the loop, use `meta.fallback_prototype.FallbackReactLoop`.

### 7.9 Domain logic in an orchestration node ties the agent to LangGraph forever

A `route_node` that contains the routing heuristic instead of calling `components.router.select_model` ties domain logic to LangGraph; the framework-swap fallback in `meta/fallback_prototype.py` cannot reuse the heuristic; the node grows to hundreds of lines. **Fix:** the node is a 10-15 line wrapper; the heuristic is a function in `components/`.

---

## 8. Where to look -- a glossary from common topics to the section that owns them


| If you came here looking for...                  | Read this section                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Layer rules / dependency table                   | [Chapter 3](#3-five-layers-one-cheat-sheet-twelve-tests-that-enforce-it)                                                                                                                                                                                                                                                          |
| Architecture tests                               | [Chapter 3](#3-five-layers-one-cheat-sheet-twelve-tests-that-enforce-it), [Chapter 5](#5-every-recipe-ends-with-the-gate-that-catches-its-failure)                                                                                                                                                                                |
| Adding a new prompt                              | [Chapter 4.2](#42-add-a-horizontal-service-in-five-steps-and-one-logger-entry) (Step 3)                                                                                                                                                                                                                                           |
| Adding a new tool                                | [Chapter 4.2](#42-add-a-horizontal-service-in-five-steps-and-one-logger-entry) (under `services/tools/`)                                                                                                                                                                                                                          |
| Adding a new model profile                       | [Chapter 5](#5-every-recipe-ends-with-the-gate-that-catches-its-failure) (`services/base_config.py`); register in `cli.py:48-68`                                                                                                                                                                                                  |
| Adding a graph node                              | [Chapter 4.4](#44-add-an-orchestration-node-by-editing-only-react_looppy-and-statepy)                                                                                                                                                                                                                                             |
| Adding a state field                             | [Chapter 4.4](#44-add-an-orchestration-node-by-editing-only-react_looppy-and-statepy) (edit `orchestration/state.py`)                                                                                                                                                                                                             |
| Adding a meta-optimizer / drift / judge tool     | [Chapter 4.5](#45-add-a-meta-tool-that-reads-logs-and-config-but-never-the-graph)                                                                                                                                                                                                                                                 |
| Adding a trust type                              | [Chapter 4.1](#41-add-a-trust-type-in-three-rules-and-one-re-export)                                                                                                                                                                                                                                                              |
| Logging                                          | [Chapter 4.2](#42-add-a-horizontal-service-in-five-steps-and-one-logger-entry) (Step 5); user-facing map in `[docs/USER_MANUAL.md` Chapter 7](USER_MANUAL.md#7-eight-per-service-log-files-under-logs-are-routed-by-loggingjson)                                                                                                  |
| Eval capture                                     | [Chapter 5](#5-every-recipe-ends-with-the-gate-that-catches-its-failure) (Runtime gates row 2)                                                                                                                                                                                                                                    |
| `BlackBoxRecorder` / `PhaseLogger`               | User-facing description in `[docs/USER_MANUAL.md` Chapters 8-9](USER_MANUAL.md#8-hash-chained-jsonl-under-cacheblack_box_recordings_workflow_id_tracejsonl-is-the-full-replay-tape); for emitting events from a new orchestration node, see [Chapter 4.4](#44-add-an-orchestration-node-by-editing-only-react_looppy-and-statepy) |
| Trust kernel rules                               | [Chapter 3](#3-five-layers-one-cheat-sheet-twelve-tests-that-enforce-it) (table row 1); deep dive in `[docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](FOUR_LAYER_ARCHITECTURE.md)` and `[docs/TRUST_FRAMEWORK_ARCHITECTURE.md](TRUST_FRAMEWORK_ARCHITECTURE.md)`                                                                                |
| `AGENTS.md` cross-reference                      | [Chapter 6](#6-the-daily-loop-is-five-commands) (Key Commands), `[AGENTS.md](../AGENTS.md)` (the full conventions file)                                                                                                                                                                                                           |
| Style guide details                              | `[docs/STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md)` and `[docs/STYLE_GUIDE_PATTERNS.md](STYLE_GUIDE_PATTERNS.md)`                                                                                                                                                                                                           |
| Governance narratives                            | `[governanaceTriangle/](../governanaceTriangle/)` -- six tutorial markdown files; do not duplicate their content here                                                                                                                                                                                                             |
| Running the agent end to end                     | `[docs/USER_MANUAL.md](USER_MANUAL.md)`                                                                                                                                                                                                                                                                                           |
| Why this is a developer guide and not a tutorial | `[docs/PYRAMID_ANALYSIS.md](PYRAMID_ANALYSIS.md)` (the planning artifact behind this guide)                                                                                                                                                                                                                                       |


---

*See also:* `[docs/USER_MANUAL.md](USER_MANUAL.md)` (running one query), `[docs/PYRAMID_ANALYSIS.md](PYRAMID_ANALYSIS.md)` (the planning artifact behind both manuals), `[AGENTS.md](../AGENTS.md)` (the workspace conventions), `[docs/Architectures/FOUR_LAYER_ARCHITECTURE.md](FOUR_LAYER_ARCHITECTURE.md)` and `[docs/STYLE_GUIDE_LAYERING.md](STYLE_GUIDE_LAYERING.md)` (the architectural references this guide projects from).