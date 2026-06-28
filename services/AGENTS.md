# services/ — Horizontal Infrastructure

> Nested guide. Loads when Claude reads a file under `services/`. Root
> `AGENTS.md` owns the inter-layer invariants; `tests/architecture/` enforces
> them. This file is local guidance for horizontal services.

## What a service is

Domain-agnostic infrastructure: prompts, guardrails, LLM config, eval capture,
observability, governance, tools. A service knows **nothing** about domain logic.

**Framework-agnostic (Invariant #4):** `services/` MUST NOT import `langgraph` or
`langchain`. The single exception is `llm_config.py`, which wraps `ChatLiteLLM`.
For config typing, use `collections.abc.Mapping` structurally rather than
importing `RunnableConfig`.

## Adding a horizontal service

- Domain-agnostic public API; single responsibility.
- Own log handler in `logging.json` (H4 — per-concern log files).
- **No vertical imports** — never import from `components/` (Invariant #7) or
  `orchestration/`.
- Shared types go in `trust/`, never inside a service module (AP-1).

## Design patterns that live here

| ID | Rule |
|----|------|
| H1 | All prompts are `.j2` files in `prompts/`, rendered via `PromptService.render_prompt()`. Never hardcode prompt strings (AP-3). |
| H2 | Reference model tiers from `services/llm_config.py`. Never hardcode model names. |
| H3 | Guardrails use `InputGuardrail` parameterized by `accept_condition` — small/fast model, boolean output. |
| H4 | Per-concern log files via `logging.json`. Each service has its own logger. |
| H5 | Record every LLM call via `eval_capture.record()` with a `target` tag, plus `user_id` and `task_id` (per-user analysis + data isolation). |

## Anti-patterns most relevant here

- **AP-1 Trust types inside a service** → shared types live in `trust/`.
- **AP-2 Horizontal-to-horizontal coupling** → a service must not call another
  service directly (e.g. `authorization_service` calling `identity_service.get()`).
  The orchestrator fetches data and passes it as a parameter. Services receive
  data, not service dependencies.
- **AP-3 Hardcoded prompts** → `.j2` + `PromptService.render_prompt()`.

## Security model — defense in depth (all three required)

1. **Input guardrail** — LLM-as-judge (small/fast model) rejecting prompt
   injection and system-prompt overrides.
2. **Tool validators** — deterministic Pydantic validators: command allowlist for
   shell, path sandboxing for file I/O.
3. **Output guardrail** — PII / API-key / system-prompt-leakage scanning (regex +
   LLM-based).

## L2 testing rules (services/)

- Contract-driven TDD, mock I/O, record/replay. Every commit, <30s.
- Registry CRUD + lifecycle, authorization decision matrix, credential TTL (use
  `freezegun`), policy backend contracts.
- **Failure paths first** (TAP-4); **never run live LLM in CI** (use mocks/fixtures).
- **TAP-2 (mock addiction):** >3 mocks in one test is a warning — prefer real
  in-memory implementations; reserve mocks for truly external systems.
- **Test import rule:** `tests/services/` may import from `trust/` and `services/`.
