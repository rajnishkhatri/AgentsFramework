"""Synthetic dataset for BlackBox → Langfuse end-to-end validation.

Single source of truth for scenarios S1–S6 and S8. Each scenario
defines the BFF input payload, expected BlackBox event types, expected
Langfuse observations, and compliance dataset / score expectations.

Used by:
  - scripts/validate_blackbox_langfuse.py (CLI driver)
  - tests/integration/test_blackbox_langfuse_gcp.py (pytest harness)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScenarioID(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    S8 = "S8"


@dataclass(frozen=True)
class ExpectedObservation:
    """A single expected Langfuse observation."""

    name: str
    observation_type: str
    level: str = "DEFAULT"


@dataclass(frozen=True)
class ComplianceExpectation:
    """Expected compliance dataset + score behavior for a scenario."""

    dataset_name: str
    hash_chain_valid_score: float
    incident_replay: bool = False


@dataclass(frozen=True)
class Scenario:
    """A synthetic validation scenario."""

    id: ScenarioID
    description: str
    bff_payload: dict[str, Any]
    expected_observations: list[ExpectedObservation]
    compliance: ComplianceExpectation
    redaction_assertions: list[str] = field(default_factory=list)
    notes: str = ""


def _bff_payload(message: str, thread_id: str | None = None) -> dict[str, Any]:
    """Build a BFF-compatible POST body for /api/run/stream."""
    payload: dict[str, Any] = {
        "input": {
            "messages": [{"role": "user", "content": message}],
        },
    }
    if thread_id is not None:
        payload["thread_id"] = thread_id
    return payload


# ─────────────────────────────────────────────────────────────────────
# S1: Simple Q&A — exercises the standard happy path (6 event types)
# ─────────────────────────────────────────────────────────────────────

S1 = Scenario(
    id=ScenarioID.S1,
    description="Simple Q&A: forces TASK_STARTED, STEP_PLANNED, MODEL_SELECTED, "
    "GUARDRAIL_CHECKED, STEP_EXECUTED, TASK_COMPLETED",
    bff_payload=_bff_payload(
        "What is the capital of France? Answer in one sentence."
    ),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
)

# ─────────────────────────────────────────────────────────────────────
# S2: Tool-using task — adds TOOL_CALLED
# ─────────────────────────────────────────────────────────────────────

S2 = Scenario(
    id=ScenarioID.S2,
    description="Tool-using task: forces TOOL_CALLED via web_search tool invocation",
    bff_payload=_bff_payload(
        "Search the web for the current weather in Austin, Texas "
        "and summarize the result in one paragraph."
    ),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="tool.called", observation_type="tool"),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
)

# ─────────────────────────────────────────────────────────────────────
# S3: Tool that errors but recovers — adds ERROR_OCCURRED
# ─────────────────────────────────────────────────────────────────────

S3 = Scenario(
    id=ScenarioID.S3,
    description="Tool error + recovery: forces ERROR_OCCURRED via shell tool "
    "on a command that fails, then agent recovers",
    bff_payload=_bff_payload(
        "Run the shell command `cat /nonexistent_file_abc123.txt` and tell me "
        "what happened. Then answer: what is 2 + 2?"
    ),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="tool.called", observation_type="tool"),
        ExpectedObservation(
            name="error.occurred", observation_type="span", level="ERROR"
        ),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
)

# ─────────────────────────────────────────────────────────────────────
# S4: Routing tier change — adds PARAMETER_CHANGED
# ─────────────────────────────────────────────────────────────────────

S4 = Scenario(
    id=ScenarioID.S4,
    description="Routing tier change: complex multi-step task that triggers "
    "model escalation from fast to capable tier (PARAMETER_CHANGED)",
    bff_payload=_bff_payload(
        "Write a detailed 500-word essay analyzing the economic impact of "
        "artificial intelligence on the global labor market, with citations "
        "from recent research papers. Use web search to find relevant data."
    ),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="parameter.changed", observation_type="span"),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
    notes="PARAMETER_CHANGED may not always fire — depends on router heuristics. "
    "If absent, the scenario validates all other events and notes the gap.",
)

# ─────────────────────────────────────────────────────────────────────
# S5: Forced failing workflow — outcome=failure → incident-replay
# ─────────────────────────────────────────────────────────────────────

S5 = Scenario(
    id=ScenarioID.S5,
    description="Forced failing workflow: task designed to exhaust retries "
    "and produce TASK_COMPLETED(outcome=failure) → agent-incident-replay",
    bff_payload=_bff_payload(
        "Execute the shell command `exit 1` repeatedly until you succeed. "
        "Do not give up — keep retrying the exact same command. "
        "You must run it at least 25 times."
    ),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(
            name="error.occurred", observation_type="span", level="ERROR"
        ),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-incident-replay",
        hash_chain_valid_score=1.0,
        incident_replay=True,
    ),
    notes="The agent should exhaust max_steps and produce outcome=failure. "
    "hash_chain_valid is still 1.0 (chain is intact, the task just failed).",
)

# ─────────────────────────────────────────────────────────────────────
# S6: PII/API-key in input — exercises redaction path
# ─────────────────────────────────────────────────────────────────────

S6 = Scenario(
    id=ScenarioID.S6,
    description="PII/API-key redaction: input contains email and API key pattern "
    "that must be redacted in Langfuse observation metadata",
    bff_payload=_bff_payload(
        "My email is alice.smith@example.com and my API key is "
        "sk-proj-abc123def456ghi789jkl012mno345pqrstu678vwx. "
        "Please confirm you received this information and repeat it back."
    ),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
    redaction_assertions=[
        "alice.smith@example.com",
        "sk-proj-abc123def456ghi789jkl012mno345pqrstu678vwx",
    ],
    notes="Assert that raw PII/key strings do NOT appear in Langfuse "
    "observation metadata. Redaction markers (e.g. [REDACTED]) should appear instead.",
)

# ─────────────────────────────────────────────────────────────────────
# S8: Two concurrent workflows — multi-workflow isolation
# ─────────────────────────────────────────────────────────────────────

S8 = Scenario(
    id=ScenarioID.S8,
    description="Two concurrent workflows: parallel requests produce independent "
    "traces with isolated offsets and compliance bundles",
    bff_payload=_bff_payload("What is 7 * 8? Answer with just the number."),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="step.planned", observation_type="chain"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
    notes="S8 is run twice concurrently. Assertions verify two distinct trace_ids "
    "in Langfuse, each with independent observations and compliance items.",
)

# ─────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────

ALL_SCENARIOS: dict[ScenarioID, Scenario] = {
    ScenarioID.S1: S1,
    ScenarioID.S2: S2,
    ScenarioID.S3: S3,
    ScenarioID.S4: S4,
    ScenarioID.S5: S5,
    ScenarioID.S6: S6,
    ScenarioID.S8: S8,
}

SCENARIO_ORDER: list[ScenarioID] = [
    ScenarioID.S1,
    ScenarioID.S2,
    ScenarioID.S3,
    ScenarioID.S4,
    ScenarioID.S5,
    ScenarioID.S6,
    ScenarioID.S8,
]
