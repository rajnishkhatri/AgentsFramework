# AGENTS.md — ReAct Agent Workspace

## Project Overview

LangGraph-based ReAct agent with four-layer architecture, trust kernel, governance services, and dynamic model routing. Python 3.10+, LiteLLM for model calls, Jinja2 for prompts, Pydantic for validation.

## Key Commands

Run these after making changes. Fix all failures before proceeding.

- **Install:** `pip install -e ".[dev]"`
- **Test:** `pytest tests/ -q` — run immediately after changes
- **Architecture tests:** `pytest tests/architecture/ -q` — verify layer boundaries. These MUST pass.
- **Run:** `python -m agent.cli "What is the capital of France?"`
- **Docker:** `docker build -t react-agent . && docker run -e OPENAI_API_KEY=$OPENAI_API_KEY react-agent "What is 2+2?"`

## Boundaries

### ✅ Always
- Run `pytest tests/ -q` after making changes
- Use `PromptService.render_prompt()` for all prompts — no hardcoded strings
- Record every LLM call via `eval_capture.record()` with `user_id` and `task_id`
- Create `.j2` files in `prompts/` for new prompts

### ⚠️ Ask first
- Adding new dependencies to `pyproject.toml`
- Modifying trust kernel types in `trust/models.py` (triggers re-signing)
- Adding new graph nodes to `orchestration/react_loop.py`
- Creating new horizontal services

### 🚫 Never
- Import from `orchestration/` in `components/` or `services/`
- Import from `langgraph` or `langchain` in `components/` or `trust/`
- Place shared trust types inside a service module — they belong in `trust/`
- Hardcode model names — reference tiers from `services/llm_config.py`
- Commit secrets, API keys, or `.env` files
- Run live LLM calls in CI test suites
- Create peer imports between components (e.g., `router` importing `evaluator`)

## Architecture Invariants — STRICTLY ENFORCED

Tests in `tests/architecture/` verify these. Never break them.

1. **Dependencies flow downward only.** Orchestration → Components → Services → Trust Kernel. Never upward.
2. **Trust kernel has ZERO outward dependencies.** `trust/` imports only stdlib + Pydantic. No I/O, no logging, no network.
3. **Components are framework-agnostic.** `components/` MUST NOT import `langgraph` or `langchain`.
4. **Services are framework-agnostic.** `services/` MUST NOT import `langgraph` or `langchain` (exception: `llm_config.py` wraps `ChatLiteLLM`).
5. **No peer imports between components.** `router.py` MUST NOT import from `evaluator.py` or vice versa.
6. **Orchestration nodes are thin wrappers.** All logic delegates to `components/` and `services/`. No domain logic in `orchestration/`.
7. **Services MUST NOT import from components.** Horizontal services have no knowledge of domain logic.
8. **Meta-layer (`meta/`) MUST NOT import from orchestration.** It reads logs and config, never calls the graph directly.

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `trust/` | Shared kernel: pure types, protocols, crypto. ZERO framework dependencies. |
| `services/` | Horizontal infrastructure: prompts, guardrails, LLM config, eval capture, observability |
| `services/governance/` | Governance services: black box, phase logger, agent facts registry |
| `services/tools/` | Tool registry and implementations (shell, file I/O) |
| `components/` | Framework-agnostic domain logic: router, evaluator, schemas |
| `orchestration/` | LangGraph graph topology (`react_loop.py`) and state (`state.py`) |
| `prompts/` | Jinja2 templates (`.j2`). Subdirs: `codeReviewer/` (review prompts), `includes/` (reusable partials) |
| `meta/` | Offline meta-optimization: optimizer, analysis, judge, drift |
| `governanaceTriangle/` | Governance explainability narratives and deep-dive docs |
| `utils/` | Shared utilities (`code_analysis.py`, `cloud_providers/`). Prefer `services/` for new infrastructure. |

## Design Patterns

Reference: @docs/STYLE_GUIDE_PATTERNS.md for full catalog (H1–H7, V1–V6).

| ID | Rule |
|----|------|
| H1 | Create all prompts as `.j2` files in `prompts/`. Render via `PromptService.render_prompt()`. Never hardcode prompt strings. |
| H2 | Reference model tiers from `services/llm_config.py`. Never hardcode model names. |
| H3 | Guardrails use `InputGuardrail` parameterized by `accept_condition`. Small/fast model, boolean output. |
| H4 | Per-concern log files via `logging.json`. Each service has its own logger. |
| H5 | Record every LLM call via `eval_capture.record()` with a `target` tag. |
| V1 | Abstract interfaces with template methods; specialize via subclass. |
| V2 | `components/router.py` — deterministic heuristics + advisory `.j2` templates. |
| V6 | Pydantic models for all non-trivial outputs. Schema enforcement with retries. |

## Trust Kernel Rules

A type belongs in `trust/` only if ALL criteria are met:

1. **Pure**: No I/O, no storage, no network, no logging.
2. **Shared**: Consumed by 2+ layers above.
3. **Stable**: Changes less frequently than consumers.
4. **Dependency-free**: Zero imports from services, components, orchestration, or meta.

Key types: `AgentFacts`, `Capability`, `Policy`, `AuditEntry`, `TrustTraceRecord`, `PolicyDecision`, `CredentialRecord`.

Signed fields determine authorization (triggers re-signing on change). Unsigned fields are operational metadata. See @docs/FOUR_LAYER_ARCHITECTURE.md §Signed vs Unsigned for field classification.

## Testing Rules

- **Failure paths first** — write rejection tests before acceptance tests for all gates/guards.
- **Never run live LLM calls in CI** — use mocks/fixtures for L1 and L2.
- **L1 zero flake tolerance** — any non-deterministic test in `trust/` is a bug in the test.
- **L1 (trust/)**: Pure TDD, property-based, exact assertions. Every commit, <10s.
- **L2 (services/)**: Contract-driven TDD, mock I/O, record/replay. Every commit, <30s.
- **Test imports follow layer rules** — `tests/trust/` may only import from `trust/`. `tests/services/` may import from `trust/` and `services/`. Never import from a layer above the code under test.

### Test Categories by Layer

- **L1 (trust/)**: Schema validation (valid + invalid), pure function correctness, enum completeness, state machine invariants, backward compatibility
- **L2 (services/)**: Registry CRUD + lifecycle, authorization decision matrix, credential TTL (use `freezegun`), policy backend contracts, record/replay fixtures
- **L3 (components/)**: Deterministic behavior (mocked LLM), trajectory evals, rubric-based quality evals
- **L4 (orchestration/, meta/)**: Trust gate failure mode matrix, governance feedback loop simulations, binary outcome scenarios

### pytest Markers

Tag tests by execution context. CI runs only L1+L2 by default.

- `@pytest.mark.slow` — L3 tests (nightly/weekly)
- `@pytest.mark.simulation` — L4 tests (on-demand)
- `@pytest.mark.live_llm` — tests requiring real LLM API calls (never in CI)
- `@pytest.mark.property` — Hypothesis property-based tests

See @research/tdd_agentic_systems_prompt.md for the full agentic testing pyramid (§Test Pattern Catalog has 11 reusable patterns: property-based schema, state machine invariant, signature roundtrip, consumer-driven contract, record/replay, mock provider, dependency enforcement, trajectory eval, rubric eval, governance loop simulation, failure mode matrix).

## Security Model — Defense in Depth

Three runtime layers, all required:

1. **Input guardrail**: LLM-as-judge (small/fast model) rejecting prompt injection and system prompt overrides.
2. **Tool validators**: Deterministic Pydantic validators — command allowlist for shell, path sandboxing for file I/O.
3. **Output guardrail**: PII/API-key/system-prompt leakage scanning (regex + LLM-based).

## Development Conventions

- **Prompts**: Create `.j2` files in `prompts/`. Naming: `{component_name}_system_prompt.j2` or `{ClassName}_{method}.j2`. Use `prompts/includes/` for reusable partials.
- **Adding a horizontal service**: Domain-agnostic API, own log handler in `logging.json`, single responsibility, no vertical imports.
- **Adding a component**: Import only from `services/` and `trust/`. No peer component imports. Register in orchestrator.
- **Error classification**: Typed as `retryable`, `model_error`, `tool_error`, or `terminal`. Route node uses type to decide retry-with-backoff vs. escalate.
- **Config**: `.j2` templates hold human intent (prose policy). `routing_config.py` holds numeric thresholds. Meta-optimizer tunes numbers, humans write policy.
- **Eval capture**: Every LLM call MUST include `user_id` and `task_id` for per-user analysis and data isolation.

## Critical Anti-Patterns

### 🚫 AP-1: Trust Types Inside a Service
Placing `AgentFacts` or `Policy` inside `services/identity_service.py` instead of `trust/models.py`.
**Why it fails:** Other services must import from a peer, creating hidden coupling. Every new consumer adds another cross-service dependency.
**Fix:** Shared trust types always live in `trust/`. Services import from the foundation.

### 🚫 AP-2: Horizontal-to-Horizontal Coupling
`authorization_service` calling `identity_service.get()` directly.
**Why it fails:** Two services become coupled; testing one requires mocking the other; changes to identity API break authorization.
**Fix:** The orchestrator fetches data and passes it as a parameter. Services receive data, not service dependencies.

### 🚫 AP-3: Hardcoded Prompts
Writing `prompt = f"You are a math educator..."` in Python code.
**Why it fails:** Bypasses logging, prevents non-engineers from editing prompts, makes A/B testing impossible.
**Fix:** Create a `.j2` file in `prompts/` and call `PromptService.render_prompt()`.

### 🚫 AP-4: Upward Governance Calls
`meta/lifecycle_manager.py` importing from `orchestration/`.
**Why it fails:** Creates circular dependency. Governance depends on orchestration which depends on services which governance also uses.
**Fix:** Governance emits `TrustTraceRecord` events. A separate consumer handles orchestration actions.

### 🚫 AP-5: Domain Logic in Orchestration Nodes
Putting routing heuristics directly in `orchestration/react_loop.py`.
**Why it fails:** Logic becomes coupled to LangGraph. Breaks the framework-swap fallback (PLAN_v2.md Phase 4).
**Fix:** All logic lives in `components/` or `services/`. Orchestration nodes are thin wrappers — max 10-15 lines each.

## Testing Anti-Patterns

### 🚫 TAP-1: Tautological Tests
Reimplementing the production algorithm in the test (e.g., computing SHA256 in the test to compare against `compute_signature()`).
**Detect:** Test contains the same logic as the implementation.
**Fix:** Test behavioral properties ("sign then verify is True") or use known test vectors, never the algorithm itself.

### 🚫 TAP-2: Mock Addiction
Using 4+ mocks in a single test. The test verifies mock configuration, not real behavior.
**Detect:** Count mocks per test. >3 is a warning.
**Fix:** Use real in-memory implementations (e.g., `InMemoryIdentityService`). Reserve mocks for truly external systems.

### 🚫 TAP-3: Determinism Theater
Asserting exact LLM output strings with `temperature=0`. Breaks on model updates.
**Detect:** `assertEqual(output, "exact string")` in tests involving LLM calls.
**Fix:** Assert structural properties at L2 (with mock providers). Use rubric-based evals at L3.

### 🚫 TAP-4: Gap Blindness in Tests
Writing only success-path tests for trust gates. A gate that accepts everything is more dangerous than one that rejects everything.
**Detect:** Success tests outnumber failure tests 2:1 for any decision point.
**Fix:** Write the rejection test before the acceptance test. Use failure mode matrices for gates.

## References

For deep context on architecture and patterns, see:

- @docs/STYLE_GUIDE_LAYERING.md — four-layer architecture rules and anti-patterns
- @docs/STYLE_GUIDE_PATTERNS.md — design patterns catalog (H1-H7, V1-V6)
- @docs/FOUR_LAYER_ARCHITECTURE.md — trust foundation, hexagonal ports, policy engines
- @docs/TRUST_FRAMEWORK_ARCHITECTURE.md — seven-layer trust framework
- @research/tdd_agentic_systems_prompt.md — testing pyramid for agentic systems
