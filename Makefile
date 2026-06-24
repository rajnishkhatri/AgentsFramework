# Always use the repo virtualenv interpreter, never whatever `python` is on PATH.
# A Homebrew/anaconda `python` on PATH has a broken opentelemetry/logfire import
# and fails test collection; `.venv/bin/python` is the only interpreter that
# resolves this project's deps. Override with `make test PYTHON=...` if needed.
PYTHON := .venv/bin/python

.PHONY: test test-fast explainability-backend explainability-frontend explainability model-ab

# Default test run (excludes the infra tree, which needs the `infra` extra and
# its own marker — see [tool.pytest.ini_options] norecursedirs in pyproject.toml).
test:
	$(PYTHON) -m pytest -q

# Quiet single-target run, e.g. `make test-fast T=tests/services/test_llm_config.py`
test-fast:
	$(PYTHON) -m pytest -q $(T)

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
