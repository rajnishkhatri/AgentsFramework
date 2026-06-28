# AGENTS.md — ReAct Agent Workspace

## Project Overview

LangGraph-based ReAct agent with four-layer architecture, trust kernel, governance
services, and dynamic model routing. Python 3.13+, LiteLLM for model calls, Jinja2
for prompts, Pydantic for validation.

> **Per-folder guides.** Folder-specific rules live in nested `AGENTS.md` files
> that load on demand when Claude reads that subtree: `trust/`, `services/`,
> `components/`, `orchestration/`, `meta/`, `prompts/`, and `frontend/` +
> `middleware/` (the Frontend Ring). This root file holds the **inter-layer**
> invariants — the rules a nested file would load too late to enforce.

## Key Commands

Run after making changes; fix all failures before proceeding.

- **Check (lint + format-check + typecheck + test):** `make check` — the canonical
  read-only pre-commit gate.
- **Test:** `pytest tests/ -q`. **Architecture tests:** `pytest tests/architecture/ -q`
  (these MUST pass).
- **Install / Run:** `pip install -e ".[dev]"` · `python -m agent.cli "..."`.

## Architecture Invariants — STRICTLY ENFORCED

Tests in `tests/architecture/` verify these. Never break them. (These stay in the
root because a nested file loads too late to stop an upward import in a *new* file.)

1. **Dependencies flow downward only.** Orchestration → Components → Services →
   Trust Kernel. Never upward.
2. **Trust kernel has ZERO outward dependencies.** `trust/` imports only stdlib +
   Pydantic. No I/O, no logging, no network.
3. **Components are framework-agnostic.** `components/` MUST NOT import `langgraph`
   or `langchain`.
4. **Services are framework-agnostic.** `services/` MUST NOT import `langgraph` or
   `langchain` (exception: `llm_config.py` wraps `ChatLiteLLM`).
5. **No peer imports between components.** `router.py` MUST NOT import from
   `evaluator.py` or vice versa.
6. **Orchestration nodes are thin wrappers.** All logic delegates to `components/`
   and `services/`. No domain logic in `orchestration/` (≤10–15 lines/node).
7. **Services MUST NOT import from components.** Horizontal services have no
   knowledge of domain logic.
8. **Meta-layer (`meta/`) MUST NOT import from orchestration.** It reads logs and
   config, never calls the graph directly.

## Boundaries

(The Architecture Invariants above already cover layering/import rules — these add
the non-layering boundaries.)

### ✅ Always
- `make check` after changes · `PromptService.render_prompt()` for all prompts (no
  hardcoded strings) · record every LLM call via `eval_capture.record()` with
  `user_id`+`task_id` · new prompts are `.j2` files in `prompts/`.
- **Red/green TDD for anything verifiable** — write the test, *watch it fail first*,
  then implement. A test that never failed proves nothing.
- **Demand evidence, not assertions** — paste the actual command/test output, not a
  summary of it. "Tests pass" without the output is not a result.

### ⚠️ Ask first  (also ADR triggers — see Decision records)
- New `pyproject.toml` dependency · trust-kernel type change in `trust/models.py`
  (triggers re-signing) · new graph node in `orchestration/react_loop.py` · new
  horizontal service · a new abstraction or any deviation from an invariant.

### 🚫 Never
- Commit secrets, API keys, or `.env` files · run live LLM calls in CI · hardcode
  model names (use tiers from `services/llm_config.py`) · place shared trust types
  in a service module (they belong in `trust/`).

## Decision records (intent debt) + comprehension gates

Capture the *why* behind structural changes — the human engagement automation can't.
The gate *mechanism* (the answer-before-reveal preamble + rotating wordings, incl.
**G3** security-boundary and **G7** architecture) lives in `docs/adr/GATES.md`; the
names below are the triggers.

- **ADR.1 — ADR ratchet.** When a change matches an `⚠️ Ask first` trigger above,
  append a numbered ADR to the `docs/adr/` OKF bundle and link it from the code
  seam it governs. Copy `docs/adr/0000-template.md` (Context / Decision /
  Options / Rationale / Consequences — the rejected alternatives are the
  intent-debt payload). OKF: every ADR needs frontmatter `type:`, an `index.md`
  entry, and a newest-first `log.md` line. (`tests/architecture/test_adr_ratchet.py`
  is the mechanical gate: a trigger path changed without a new `docs/adr/*` file —
  or an `ADR-OK:` waiver in a range commit message — fails it.)
- **G1 — new-abstraction gate.** Automation can't judge whether an abstraction
  earns its place. Before adding one, state in the PR/commit what it buys and what
  you considered instead (→ an ADR for anything load-bearing).
- **G4 — complex-algorithm gate (scoped to `trust/`).** On the crypto/signing
  path, write down what the algorithm does and why the change is correct *before*
  pasting the implementation back. A green test you can't explain is not done.
  (Detail in `trust/AGENTS.md`.)
- **G8 — test-mass-rewrite gate.** A large rewrite of existing tests can silently
  weaken the suite (TAP-1/3/4). When a diff rewrites many tests, justify *why each
  weakened assertion is still sound* before relying on the green result.
  (`tests/architecture/test_no_test_weakening.py` is the mechanical sensor: it
  fails a removed `def test_*` or a newly skipped/xfailed test that lacks a
  justification token.)
- **Spec the *what*, ADR the *why*.** For a non-trivial durable change, copy
  `docs/plan/_spec_template.md` → `docs/plan/<name>.spec.md` (EARS acceptance criteria
  → testable). The spec is the *what*; the ADR is the *why*. Small non-obvious choices
  too minor for an ADR go in `docs/adr/decisions.md` (2–4 lines).
- **Ratchet rule.** Every instruction line here traces to a real failure. Delete
  aspirational lines; don't add a rule without a failure that justifies it.

> Honest limit: Claude Code hooks can `ask`/`block` but **cannot** capture a typed
> human answer (no controlling terminal). The gates above are convention +
> PR-review, not tool-enforced. `tests/architecture/` is the hard enforcement.

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `trust/` | Shared kernel: pure types, protocols, crypto. ZERO framework dependencies. |
| `services/` | Horizontal infrastructure: prompts, guardrails, LLM config, eval capture, observability. |
| `services/governance/` | Governance services: black box, phase logger, agent facts registry. |
| `services/tools/` | Tool registry and implementations (shell, file I/O). |
| `components/` | Framework-agnostic domain logic: router, evaluator, schemas. |
| `orchestration/` | LangGraph graph topology (`react_loop.py`) and state (`state.py`). |
| `prompts/` | Jinja2 templates (`.j2`). Subdirs: `codeReviewer/`, `includes/`. |
| `meta/` | Offline meta-optimization: optimizer, analysis, judge, drift, judge validation. |
| `frontend/`, `middleware/` | The Frontend Ring (Next.js BFF + credentialed middleware). |
| `governanaceTriangle/` | Governance explainability narratives and deep-dive docs. *(Directory name is misspelled on disk; left as-is — 26 docs reference the path.)* |
| `utils/` | Shared utilities. Prefer `services/` for new infrastructure. |
| `docs/plan/` | Design & planning docs. New plans land here, not at the repo root. |
| `docs/vision/` | Intent docs: `MISSION.md`, `SOUL.md`. |
| `docs/adr/` | Architecture Decision Records (OKF bundle). |

> **Repo layout:** root holds only build/config files + the package dirs above.
> Design docs → `docs/plan/`, intent docs → `docs/vision/`. Keep the root scannable.

## Cross-cutting References

Layer patterns (H/V families), testing rules (L1–L4, TAP-1…4), and the security model
live in each folder's nested `AGENTS.md`. Canonical catalogs:

- @docs/style-guides/STYLE_GUIDE_LAYERING.md — four-layer rules and anti-patterns.
- @docs/style-guides/STYLE_GUIDE_PATTERNS.md — design patterns catalog (H1–H7, V1–V6).
- @docs/style-guides/STYLE_GUIDE_FRONTEND.md — Frontend Ring (F/W/P/A/T/X/C/B/U/S/O).
- @docs/Architectures/FOUR_LAYER_ARCHITECTURE.md — trust foundation, ports, policy engines.
- @docs/Architectures/TRUST_FRAMEWORK_ARCHITECTURE.md — seven-layer trust framework.
- @research/tdd_agentic_systems_prompt.md — the agentic testing pyramid (11 patterns).
