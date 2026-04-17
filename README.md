# ReAct Agent -- Phase 1

A LangGraph-based ReAct agent with four-layer architecture, trust kernel, and governance services.

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key (or equivalent LiteLLM-compatible provider)
- Optional: LangSmith API key for tracing

### Install

```bash
cd agent
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
# From the workspace root:
python -m agent.cli "What is the capital of France?"

# Or from within agent/:
cd agent
python cli.py "What is the capital of France?"
```

### Run Tests

```bash
cd agent
pytest tests/ -q
```

### Docker

```bash
cd agent
docker build -t react-agent .
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -e AGENT_FACTS_SECRET=change-me react-agent "What is 2+2?"
```

## Architecture

Four-layer grid (bottom-up):

1. **Trust Kernel** (`trust/`) -- Pure types, protocols, crypto. Zero framework dependencies.
2. **Horizontal Services** (`services/`) -- Domain-agnostic infrastructure (prompt rendering, LLM calls, guardrails, tools, governance).
3. **Vertical Components** (`components/`) -- Framework-agnostic domain logic (router, evaluator, schemas).
4. **Orchestration** (`orchestration/`) -- LangGraph StateGraph with thin-wrapper nodes.

Dependencies flow downward only. Architecture rules enforced by tests in `tests/architecture/`.

## Observability

- **LangSmith tracing**: Automatic via LangGraph (set `LANGCHAIN_TRACING_V2=true`)
- **Per-concern logs**: `logs/prompts.log`, `logs/guards.log`, `logs/evals.log`, `logs/routing.log`, etc.
- **Governance artifacts**: `cache/black_box_recordings/`, `cache/phase_logs/`, `cache/agent_facts/`
