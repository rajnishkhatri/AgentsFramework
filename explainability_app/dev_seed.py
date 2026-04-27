"""Dev seed: generate synthetic workflows for the explainability dashboard.

Usage: python -m explainability_app.dev_seed --seed 42 --count 5

Uses real BlackBoxRecorder and PhaseLogger to produce valid hash chains.
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import Decision, PhaseLogger, WorkflowPhase

AGENT_ROOT = Path(__file__).resolve().parents[1]

MODELS = ["gpt-4o", "gpt-4o-mini", "claude-3-opus", "claude-3-sonnet"]
TASK_INPUTS = [
    "What is the capital of France?",
    "Summarize the quarterly report",
    "Debug the authentication flow",
    "Write a Python function to sort a list",
    "Explain the theory of relativity",
    "Review this pull request for security issues",
    "Generate a test plan for the checkout module",
    "Translate this document to Spanish",
    "Calculate the total cost of the order",
    "Analyze the sentiment of customer reviews",
]
GUARDRAIL_TYPES = ["prompt_injection", "agent_facts", "output_pii_scan"]


def _existing_workflow_count(cache_dir: Path) -> int:
    recordings_dir = cache_dir / "black_box_recordings"
    if not recordings_dir.exists():
        return 0
    return sum(1 for path in recordings_dir.iterdir() if path.is_dir())


def generate_workflows(
    cache_dir: Path,
    count: int = 5,
    seed: int = 42,
) -> list[str]:
    rng = random.Random(seed)
    recorder = BlackBoxRecorder(cache_dir / "black_box_recordings")
    phase_logger = PhaseLogger(cache_dir / "phase_logs")

    workflow_ids: list[str] = []
    base_time = datetime(2026, 4, 26, 8, 0, 0, tzinfo=UTC)
    workflow_offset = _existing_workflow_count(cache_dir)

    for i in range(count):
        wf_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{workflow_offset + i}")
        wf_id = f"wf-seed-{wf_uuid.hex[:8]}"
        workflow_ids.append(wf_id)
        t = base_time + timedelta(hours=i * 2, minutes=rng.randint(0, 59))
        num_steps = rng.randint(2, 4)
        has_error = i == count - 1 or rng.random() < 0.2
        task_input = rng.choice(TASK_INPUTS)
        model = rng.choice(MODELS)
        agent_id = rng.choice(["cli-agent", "dev-agent"])

        recorder.record(TraceEvent(
            event_id=str(uuid.UUID(int=rng.getrandbits(128))),
            workflow_id=wf_id,
            event_type=EventType.TASK_STARTED,
            timestamp=t,
            details={"task_input": task_input, "agent_id": agent_id},
        ))
        t += timedelta(milliseconds=rng.randint(50, 200))

        for guardrail in rng.sample(GUARDRAIL_TYPES, k=rng.randint(1, len(GUARDRAIL_TYPES))):
            recorder.record(TraceEvent(
                event_id=str(uuid.UUID(int=rng.getrandbits(128))),
                workflow_id=wf_id,
                event_type=EventType.GUARDRAIL_CHECKED,
                timestamp=t,
                details={"guardrail": guardrail, "accepted": True},
            ))
            t += timedelta(milliseconds=rng.randint(100, 5000))

        recorder.record(TraceEvent(
            event_id=str(uuid.UUID(int=rng.getrandbits(128))),
            workflow_id=wf_id,
            event_type=EventType.MODEL_SELECTED,
            timestamp=t,
            details={"model": model, "reason": "capable-for-planning"},
        ))
        phase_logger.log_decision(wf_id, Decision(
            phase=WorkflowPhase.ROUTING,
            description=f"Selected {model}",
            alternatives=[m for m in MODELS if m != model][:2],
            rationale=f"capable-for-planning (step=0, errors=0)",
            confidence=rng.uniform(0.6, 0.95),
        ))
        t += timedelta(milliseconds=rng.randint(10, 50))

        temperature = round(rng.uniform(0.0, 0.4), 2)
        recorder.record(TraceEvent(
            event_id=str(uuid.UUID(int=rng.getrandbits(128))),
            workflow_id=wf_id,
            event_type=EventType.PARAMETER_CHANGED,
            timestamp=t,
            details={
                "parameter": "temperature",
                "old_value": 0.0,
                "new_value": temperature,
                "reason": "dev seed variation",
            },
        ))
        t += timedelta(milliseconds=rng.randint(10, 50))

        for step in range(num_steps):
            recorder.record(TraceEvent(
                event_id=str(uuid.UUID(int=rng.getrandbits(128))),
                workflow_id=wf_id,
                event_type=EventType.STEP_PLANNED,
                timestamp=t,
                step=step,
                details={
                    "agent_id": agent_id,
                    "model": model,
                    "planned_action": "tool_then_model" if step % 2 == 0 else "model_only",
                },
            ))
            t += timedelta(milliseconds=rng.randint(10, 50))

            if has_error and step == num_steps - 1:
                recorder.record(TraceEvent(
                    event_id=str(uuid.UUID(int=rng.getrandbits(128))),
                    workflow_id=wf_id,
                    event_type=EventType.ERROR_OCCURRED,
                    timestamp=t,
                    step=step,
                    details={"error": "Simulated error", "model": model},
                ))
                phase_logger.log_decision(wf_id, Decision(
                    phase=WorkflowPhase.EVALUATION,
                    description="Error occurred",
                    alternatives=["retry", "escalate", "terminal"],
                    rationale="Simulated error for seed data",
                    confidence=1.0,
                ))
            else:
                tokens_in = rng.randint(200, 1500)
                tokens_out = rng.randint(5, 500)
                latency = rng.uniform(500, 5000)
                cost = (tokens_in * 0.000003 + tokens_out * 0.000015)
                recorder.record(TraceEvent(
                    event_id=str(uuid.UUID(int=rng.getrandbits(128))),
                    workflow_id=wf_id,
                    event_type=EventType.TOOL_CALLED,
                    timestamp=t,
                    step=step,
                    details={
                        "tool_name": "dev_seed_tool",
                        "input": {"step": step, "task": task_input},
                        "output": {"ok": True},
                    },
                ))
                t += timedelta(milliseconds=rng.randint(25, 100))

                recorder.record(TraceEvent(
                    event_id=str(uuid.UUID(int=rng.getrandbits(128))),
                    workflow_id=wf_id,
                    event_type=EventType.STEP_EXECUTED,
                    timestamp=t,
                    step=step,
                    details={
                        "model": model,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost_usd": round(cost, 6),
                        "latency_ms": round(latency, 2),
                        "error": None,
                    },
                ))
                phase_logger.log_decision(wf_id, Decision(
                    phase=WorkflowPhase.EVALUATION,
                    description=f"Step {step} completed successfully",
                    alternatives=["retry", "escalate", "terminal"],
                    rationale="Step completed successfully",
                    confidence=1.0,
                ))
            t += timedelta(milliseconds=int(rng.uniform(500, 5000)))

        if not has_error:
            recorder.record(TraceEvent(
                event_id=str(uuid.UUID(int=rng.getrandbits(128))),
                workflow_id=wf_id,
                event_type=EventType.TASK_COMPLETED,
                timestamp=t,
                details={"status": "success"},
            ))

    return workflow_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed explainability dashboard data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=AGENT_ROOT / "cache",
    )
    args = parser.parse_args()

    wf_ids = generate_workflows(args.cache_dir, count=args.count, seed=args.seed)
    print(f"Generated {len(wf_ids)} workflows:")
    for wf_id in wf_ids:
        print(f"  {wf_id}")


if __name__ == "__main__":
    main()
