# Always use the repo virtualenv interpreter, never whatever `python` is on PATH.
# A Homebrew/anaconda `python` on PATH has a broken opentelemetry/logfire import
# and fails test collection; `.venv/bin/python` is the only interpreter that
# resolves this project's deps. Override with `make test PYTHON=...` if needed.
PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
# pyright is not a Python package dep; run via npx (node is required on PATH).
PYRIGHT := npx --yes pyright

.PHONY: test test-fast lint lint-fix format format-check typecheck check \
        explainability-backend explainability-frontend explainability model-ab

# Default test run (excludes the infra tree, which needs the `infra` extra and
# its own marker — see [tool.pytest.ini_options] norecursedirs in pyproject.toml).
test:
	$(PYTHON) -m pytest -q

# Quiet single-target run, e.g. `make test-fast T=tests/services/test_llm_config.py`
test-fast:
	$(PYTHON) -m pytest -q $(T)

# --- Sensor layer (Track A) ----------------------------------------------------
# Same checks run as Claude Code hooks (write-time) + pre-commit (commit-time) +
# CI (.github/workflows/pre-commit.yml). `make check` is the canonical local gate.

# Lint, read-only (used by `check` / CI — never mutates).
lint:
	$(RUFF) check .

# Lint with auto-fix (explicit, mutating — run by hand, not by `check`).
lint-fix:
	$(RUFF) check --fix .

# Format in place (mutating — run by hand).
format:
	$(RUFF) format .

# Format check only (no writes) — used by `check` / CI so it fails on drift.
format-check:
	$(RUFF) format --check .

# Type check the core four-layer Python tree (config in pyrightconfig.json).
typecheck:
	$(PYRIGHT)

# The full local gate: lint + format drift + types + tests. READ-ONLY —
# fails on issues, never rewrites files. Use `make lint-fix format` to fix.
check: lint format-check typecheck test

# Model-swap A/B gate (plan Part II). Runs the frozen corpus under two arms and
# diffs into PROMOTE/HOLD/CONTAMINATED. Real LLM calls — opt-in, NEVER in CI.
# Pass arms via ARGS, e.g.:
#   make model-ab ARGS="--baseline gpt-4o-mini --candidate claude-haiku-4-5 --limit 3"
#   make model-ab ARGS="--baseline-set openai --candidate-set anthropic --gate"
model-ab:
	$(PYTHON) scripts/model_ab_eval.py $(ARGS)

explainability-backend:
	$(PYTHON) -m explainability_app

explainability-frontend:
	cd frontend-explainability && npm run dev

explainability:
	@echo "Starting explainability backend on http://127.0.0.1:8001"
	@echo "Starting explainability frontend on http://localhost:3001"
	@trap 'kill 0' INT TERM EXIT; \
		$(PYTHON) -m explainability_app & \
		(cd frontend-explainability && npm run dev) & \
		wait
