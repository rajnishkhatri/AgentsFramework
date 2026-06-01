"""Synthetic dataset for BlackBox → Langfuse end-to-end validation.

Single source of truth for two families of scenarios:

  * **Live (``kind="bff"``)** — S1–S6 and S8. Each defines a BFF input
    payload, expected BlackBox event types, expected Langfuse observations,
    and compliance dataset / score expectations. Driven through the real
    agent by the live integration harness.
  * **Negative / synthetic (``kind="synthetic"``)** — S7, S9, S10, S11. These
    exercise the *gate-failure* modes (G7/G8/G9) that a user prompt cannot
    produce: a failed ``AgentFacts`` verification, a tampered hash chain, and
    ``retryable``/``tool_error`` runtime failures. They are constructed
    deterministically from ``synthetic_events`` (no live LLM) so the
    "gate that only ever says yes" (TAP-4 gap blindness, AGENTS.md) is
    actually proven. Exercised by the L2 relay contract test, never the
    live BFF harness.

Used by:
  - scripts/validate_blackbox_langfuse.py (CLI driver — live scenarios only)
  - tests/integration/test_blackbox_langfuse_gcp.py (live pytest harness)
  - tests/middleware/sidecars/test_compliance_dataset.py (L2 negative-path)
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
    S7 = "S7"
    S8 = "S8"
    S9 = "S9"
    S10 = "S10"
    S11 = "S11"


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
class SyntheticEvent:
    """One BlackBox event to record when materializing a synthetic scenario.

    ``event_type`` is the ``EventType`` *value* string (e.g. ``"task_completed"``)
    so this module stays dependency-free of ``services.governance.black_box``
    (the L2 test maps it back to the enum when recording). ``details`` mirrors
    the real ``react_loop`` payload for that event so the synthetic trace is a
    faithful stand-in for the runtime one.
    """

    event_type: str
    details: dict[str, Any]
    step: int | None = None


@dataclass(frozen=True)
class Scenario:
    """A validation scenario — live (``kind="bff"``) or synthetic.

    Synthetic-only fields (default to inert values so live scenarios are
    unaffected):
      - ``synthetic_events``: the trace to record directly via the recorder.
      - ``corrupt_event_index``: index into ``synthetic_events`` whose stored
        integrity hash the harness tampers, to force a broken chain (G8).
      - ``expected_outcome`` / ``expected_reason``: the terminal
        ``task_completed`` outcome the bundle summary must surface (G7).
      - ``expected_error_types``: error_type values that must appear on a
        terminal event when ``error.occurred`` fired (G9 trace coverage).
      - ``expected_broken_chain``: the bundle's ``hash_chain_valid`` must be
        ``False`` and ``broken_at_event_id`` populated (G8).
    """

    id: ScenarioID
    description: str
    bff_payload: dict[str, Any]
    expected_observations: list[ExpectedObservation]
    compliance: ComplianceExpectation
    redaction_assertions: list[str] = field(default_factory=list)
    notes: str = ""
    kind: str = "bff"
    synthetic_events: tuple[SyntheticEvent, ...] = ()
    corrupt_event_index: int | None = None
    expected_outcome: str | None = None
    expected_reason: str | None = None
    expected_error_types: tuple[str, ...] = ()
    expected_broken_chain: bool = False


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

# ═════════════════════════════════════════════════════════════════════
# Negative / synthetic scenarios (G7/G8/G9) — gate-failure coverage
#
# These cannot be produced by a user prompt: you cannot ask the agent to
# fail its own AgentFacts verification or to corrupt its own hash chain.
# They are recorded directly so the dangerous "gate that only ever accepts"
# (TAP-4 gap blindness) is exercised. The L2 relay contract test materializes
# them and asserts the failure routing; the live BFF harness skips them.
# ═════════════════════════════════════════════════════════════════════

# Frozen timestamps keep the recorded chain deterministic across runs.
_T0 = "2026-05-28T12:00:00+00:00"


def _synthetic_payload(note: str) -> dict[str, Any]:
    """Marker payload — synthetic scenarios are never POSTed to the BFF."""
    return {"synthetic": True, "note": note}


# ─────────────────────────────────────────────────────────────────────
# S7: Failed AgentFacts verification — outcome=rejected (G7)
# ─────────────────────────────────────────────────────────────────────

S7 = Scenario(
    id=ScenarioID.S7,
    description="Failed AgentFacts verification: unverifiable agent identity → "
    "task_completed(outcome=rejected, reason=agent_facts_verification_failed) "
    "before any model call (exercises react_loop guard_input_node:484-502)",
    bff_payload=_synthetic_payload("agent_facts verification failure"),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="guardrail.checked", observation_type="guardrail"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
    kind="synthetic",
    synthetic_events=(
        SyntheticEvent("task_started", {"task": "unverifiable-agent task"}, step=0),
        SyntheticEvent(
            "guardrail_checked",
            {
                "guardrail": "agent_facts",
                "agent_id": "agent-unregistered",
                "verified": False,
            },
            step=0,
        ),
        SyntheticEvent(
            "task_completed",
            {
                "bundle_schema_version": "2",
                "outcome": "rejected",
                "reason": "agent_facts_verification_failed",
                "step_count": 0,
                "total_cost_usd": 0.0,
            },
            step=0,
        ),
    ),
    expected_outcome="rejected",
    expected_reason="agent_facts_verification_failed",
    notes="Chain is intact (hash_chain_valid=1.0) — the *task* was rejected, not "
    "the recording. Routes to the audit dataset; the summary block surfaces "
    "outcome=rejected so a reviewer sees the gate fired.",
)

# ─────────────────────────────────────────────────────────────────────
# S9: Broken hash chain — incident-replay, score 0, broken_at_event_id (G8)
# ─────────────────────────────────────────────────────────────────────

S9 = Scenario(
    id=ScenarioID.S9,
    description="Tampered hash chain: a recorded event's integrity hash is "
    "altered post-hoc → hash_chain_valid=0, routes to agent-incident-replay, "
    "broken_at_event_id populated (G8)",
    bff_payload=_synthetic_payload("broken hash chain"),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(name="step.executed", observation_type="span"),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-incident-replay",
        hash_chain_valid_score=0.0,
        incident_replay=True,
    ),
    kind="synthetic",
    synthetic_events=(
        SyntheticEvent("task_started", {"task": "tampered-evidence task"}, step=0),
        SyntheticEvent("model_selected", {"model": "fast-tier"}, step=0),
        SyntheticEvent("step_executed", {"action": "answer", "tampered_target": True}, step=1),
        SyntheticEvent(
            "task_completed",
            {
                "bundle_schema_version": "2",
                "outcome": "success",
                "goal_met": True,
                "step_count": 1,
                "total_cost_usd": 0.0,
            },
            step=2,
        ),
    ),
    corrupt_event_index=2,
    expected_broken_chain=True,
    notes="The corrupted event (index 2, step.executed) becomes broken_at_event_id. "
    "Even though outcome=success, integrity failure overrides routing → incident "
    "dataset with hash_chain_valid score 0.0. A 'clean success' on a broken chain "
    "is exactly the corrupt-success the gate must catch.",
)

# ─────────────────────────────────────────────────────────────────────
# S10: LLM retryable (429) — ERROR_OCCURRED, error_type=retryable (G9 trace)
# ─────────────────────────────────────────────────────────────────────

S10 = Scenario(
    id=ScenarioID.S10,
    description="LLM 429 rate-limit: a retryable model error fires ERROR_OCCURRED "
    "then the terminal event carries error_type=retryable and the backoff path "
    "(G9 dataset trace coverage; runtime already lands ERROR_OCCURRED)",
    bff_payload=_synthetic_payload("retryable 429"),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="model.selected", observation_type="generation"),
        ExpectedObservation(
            name="error.occurred", observation_type="span", level="ERROR"
        ),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
    kind="synthetic",
    synthetic_events=(
        SyntheticEvent("task_started", {"task": "rate-limited task"}, step=0),
        SyntheticEvent("model_selected", {"model": "fast-tier"}, step=0),
        SyntheticEvent(
            "error_occurred",
            {
                "source": "llm_call",
                "model": "fast-tier",
                "error": "RateLimitError: 429 Too Many Requests",
                "latency_ms": 12.0,
            },
            step=0,
        ),
        SyntheticEvent(
            "task_completed",
            {
                "bundle_schema_version": "2",
                "outcome": "failure",
                "error_type": "retryable",
                "step_count": 1,
                "total_cost_usd": 0.0,
            },
            step=1,
        ),
    ),
    expected_outcome="failure",
    expected_error_types=("retryable",),
    notes="ERROR_OCCURRED present + terminal error_type non-null proves the 429 "
    "path is observable in the dataset, not just in the running process.",
)

# ─────────────────────────────────────────────────────────────────────
# S11: Tool error — ERROR_OCCURRED, error_type=tool_error (G9 trace)
# ─────────────────────────────────────────────────────────────────────

S11 = Scenario(
    id=ScenarioID.S11,
    description="Tool failure: a tool returns ok=False → ERROR_OCCURRED, terminal "
    "event carries error_type=tool_error (G9 dataset trace coverage)",
    bff_payload=_synthetic_payload("tool_error"),
    expected_observations=[
        ExpectedObservation(name="task.started", observation_type="agent"),
        ExpectedObservation(name="tool.called", observation_type="tool"),
        ExpectedObservation(
            name="error.occurred", observation_type="span", level="ERROR"
        ),
        ExpectedObservation(name="task.completed", observation_type="agent"),
    ],
    compliance=ComplianceExpectation(
        dataset_name="agent-compliance-audit",
        hash_chain_valid_score=1.0,
    ),
    kind="synthetic",
    synthetic_events=(
        SyntheticEvent("task_started", {"task": "failing-tool task"}, step=0),
        SyntheticEvent(
            "tool_called",
            {"tool": "shell", "args": {"cmd": "exit 1"}, "cached": False},
            step=0,
        ),
        SyntheticEvent(
            "error_occurred",
            {
                "source": "tool_execution",
                "tool": "shell",
                "error": "command exited non-zero (1)",
            },
            step=0,
        ),
        SyntheticEvent(
            "task_completed",
            {
                "bundle_schema_version": "2",
                "outcome": "failure",
                "error_type": "tool_error",
                "step_count": 1,
                "total_cost_usd": 0.0,
            },
            step=1,
        ),
    ),
    expected_outcome="failure",
    expected_error_types=("tool_error",),
    notes="Distinct from S3 (tool error + recovery): here the failure is terminal, "
    "so error_type survives onto the task_completed event.",
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

# Negative / synthetic scenarios — kept OUT of ALL_SCENARIOS / SCENARIO_ORDER so
# the live BFF harness never tries to drive a trace it cannot produce. Consumed
# only by the deterministic L2 relay contract test.
NEGATIVE_SCENARIOS: dict[ScenarioID, Scenario] = {
    ScenarioID.S7: S7,
    ScenarioID.S9: S9,
    ScenarioID.S10: S10,
    ScenarioID.S11: S11,
}

NEGATIVE_SCENARIO_ORDER: list[ScenarioID] = [
    ScenarioID.S7,
    ScenarioID.S9,
    ScenarioID.S10,
    ScenarioID.S11,
]
