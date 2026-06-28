# components/ — Framework-Agnostic Domain Logic

> Nested guide. Loads when Claude reads a file under `components/`. Root
> `AGENTS.md` owns the inter-layer invariants; `tests/architecture/` enforces
> them. This file is local guidance.

## What a component is

Framework-agnostic domain logic: router, evaluator, schemas, answer verifiers,
synthesis validator. Components hold the *decisions*; orchestration just wires
them into the graph.

**Framework-agnostic (Invariant #3):** `components/` MUST NOT import `langgraph`
or `langchain`. **No peer imports (Invariant #5):** `router.py` MUST NOT import
from `evaluator.py` or vice versa — peer components communicate through state
passed by the orchestrator, never by importing each other.

## Adding a component

- Import **only** from `services/` and `trust/`. No peer component imports.
- Register it in the orchestrator (orchestration wires; it does not decide).
- Non-trivial outputs are Pydantic models with schema enforcement + retries (V6).

## Design patterns that live here

| ID | Rule |
|----|------|
| V1 | Abstract interfaces with template methods; specialize via subclass. |
| V2 | `router.py` — deterministic heuristics + advisory `.j2` templates. |
| V6 | Pydantic models for all non-trivial outputs. Schema enforcement with retries. |

## Error classification

Errors are typed `retryable`, `model_error`, `tool_error`, or `terminal`. The
route node uses the type to decide retry-with-backoff vs. escalate. Keep the
classification logic here (a decision), not in the orchestration node.

## L3 testing rules (components/)

- Deterministic behavior with **mocked** LLM; trajectory evals; rubric-based
  quality evals. Tagged `@pytest.mark.slow` (L3 runs nightly/weekly, not per-commit).
- **TAP-3 (determinism theater):** never assert exact LLM output strings at
  `temperature=0` — it breaks on model updates. Assert structural properties at
  L2 (mock providers); use rubric-based evals at L3.
- **Test import rule:** `tests/components/` may import from `trust/`, `services/`,
  and `components/` — never from `orchestration/`.
