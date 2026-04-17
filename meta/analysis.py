"""Analytics engine: metrics from JSONL logs and governance artifacts.

Reads EvalRecord JSONL files and governance logs to compute operational
metrics for the ReAct agent.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from components.schemas import EvalRecord

logger = logging.getLogger("meta.analysis")


class AgentMetrics(BaseModel):
    """Computed metrics from agent execution logs."""

    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    success_rate: float = 0.0

    success_rate_by_tier: dict[str, float] = Field(default_factory=dict)
    cost_per_successful_step: float = 0.0
    total_cost_usd: float = 0.0

    unnecessary_escalation_rate: float = 0.0
    failure_rate_before_escalation: float = 0.0
    rollback_frequency_by_tier: dict[str, float] = Field(default_factory=dict)

    avg_steps_per_task: float = 0.0
    avg_latency_ms: float = 0.0

    model_usage_counts: dict[str, int] = Field(default_factory=dict)
    error_type_counts: dict[str, int] = Field(default_factory=dict)


class OptimizerInput(BaseModel):
    """Wraps AgentMetrics + config snapshot + golden-set scores for the optimizer."""

    metrics: AgentMetrics = Field(default_factory=AgentMetrics)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    golden_set_scores: list[float] = Field(default_factory=list)
    sensitivity: dict[str, float] = Field(default_factory=dict)


def load_eval_records(path: Path) -> list[EvalRecord]:
    """Load EvalRecord entries from a JSONL file, handling version differences."""
    records: list[EvalRecord] = []
    if not path.exists():
        return records
    for line in path.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            schema_version = data.get("schema_version", 1)
            if schema_version in (1, 2):
                records.append(EvalRecord.model_validate(data))
            else:
                logger.warning("Unsupported schema_version=%d, attempting parse", schema_version)
                records.append(EvalRecord.model_validate(data))
        except Exception as exc:
            logger.warning("Skipping invalid record: %s", exc)
    return records


def compute_metrics(
    records: list[EvalRecord],
    rollback_data: list[dict[str, Any]] | None = None,
) -> AgentMetrics:
    """Compute aggregate metrics from a list of EvalRecords."""
    if not records:
        return AgentMetrics()

    tier_success: dict[str, list[bool]] = {}
    tier_counts: dict[str, int] = {}
    model_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    total_cost = 0.0
    successful_costs: list[float] = []
    latencies: list[float] = []
    steps_per_task: dict[str, int] = {}
    task_outcomes: dict[str, bool] = {}

    escalation_count = 0
    total_routing_decisions = 0
    # Track per-task tier usage and failures for failure_rate_before_escalation
    task_fast_failed: set[str] = set()
    task_has_capable: set[str] = set()
    tasks_routed_to_fast: set[str] = set()

    for rec in records:
        model = rec.model or "unknown"
        model_counts[model] = model_counts.get(model, 0) + 1

        tier = _infer_tier(model)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        cost = rec.cost_usd or 0.0
        total_cost += cost

        if rec.latency_ms:
            latencies.append(rec.latency_ms)

        if rec.error_type:
            error_counts[rec.error_type] = error_counts.get(rec.error_type, 0) + 1
            if rec.task_id not in task_outcomes:
                task_outcomes[rec.task_id] = False
            tier_success.setdefault(tier, []).append(False)
            if tier == "fast":
                task_fast_failed.add(rec.task_id)
        else:
            task_outcomes[rec.task_id] = True
            tier_success.setdefault(tier, []).append(True)
            successful_costs.append(cost)

        if tier == "fast":
            tasks_routed_to_fast.add(rec.task_id)
        if tier == "capable":
            task_has_capable.add(rec.task_id)

        steps_per_task[rec.task_id] = steps_per_task.get(rec.task_id, 0) + 1

        if rec.target == "call_llm" and tier == "capable":
            total_routing_decisions += 1
            if rec.step == 0:
                pass
            else:
                escalation_count += 1

    total_tasks = len(task_outcomes)
    successful = sum(1 for v in task_outcomes.values() if v)
    failed = total_tasks - successful

    success_rate_by_tier: dict[str, float] = {}
    for tier, outcomes in tier_success.items():
        if outcomes:
            success_rate_by_tier[tier] = sum(1 for o in outcomes if o) / len(outcomes)

    cost_per_success = (
        sum(successful_costs) / len(successful_costs) if successful_costs else 0.0
    )

    esc_rate = (
        escalation_count / total_routing_decisions
        if total_routing_decisions > 0
        else 0.0
    )

    rollback_by_tier: dict[str, float] = {}
    if rollback_data:
        tier_rollbacks: dict[str, int] = {}
        for rb in rollback_data:
            t = rb.get("model_tier", "unknown")
            tier_rollbacks[t] = tier_rollbacks.get(t, 0) + 1
        for t, count in tier_rollbacks.items():
            total_for_tier = tier_counts.get(t, 1)
            rollback_by_tier[t] = count / total_for_tier

    # failure_rate_before_escalation: tasks that failed at fast tier before
    # escalation to capable tier, divided by total tasks routed to fast tier
    fast_failed_then_escalated = task_fast_failed & task_has_capable
    fail_before_esc = (
        len(fast_failed_then_escalated) / len(tasks_routed_to_fast)
        if tasks_routed_to_fast
        else 0.0
    )

    avg_steps = (
        sum(steps_per_task.values()) / len(steps_per_task) if steps_per_task else 0.0
    )
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return AgentMetrics(
        total_tasks=total_tasks,
        successful_tasks=successful,
        failed_tasks=failed,
        success_rate=successful / total_tasks if total_tasks else 0.0,
        success_rate_by_tier=success_rate_by_tier,
        cost_per_successful_step=cost_per_success,
        total_cost_usd=total_cost,
        unnecessary_escalation_rate=esc_rate,
        failure_rate_before_escalation=fail_before_esc,
        rollback_frequency_by_tier=rollback_by_tier,
        avg_steps_per_task=avg_steps,
        avg_latency_ms=avg_latency,
        model_usage_counts=model_counts,
        error_type_counts=error_counts,
    )


def compute_sensitivity(
    records: list[EvalRecord],
    config: dict[str, Any],
) -> dict[str, float]:
    """Estimate marginal impact on success_rate for each RoutingConfig field.

    Uses heuristic analysis: counts how many tasks are near each threshold
    boundary to estimate sensitivity.
    """
    if not records:
        return {k: 0.0 for k in config}

    sensitivity: dict[str, float] = {}
    metrics = compute_metrics(records)

    for field_name, value in config.items():
        if not isinstance(value, (int, float)):
            sensitivity[field_name] = 0.0
            continue

        if field_name == "escalate_after_failures":
            near_boundary = sum(
                1
                for tid, cnt in _task_error_counts(records).items()
                if abs(cnt - value) <= 1
            )
            total = metrics.total_tasks or 1
            sensitivity[field_name] = near_boundary / total

        elif field_name == "budget_downgrade_threshold":
            near_boundary = sum(
                1
                for rec in records
                if rec.cost_usd is not None and abs(rec.cost_usd - value) < 0.1
            )
            total = len(records) or 1
            sensitivity[field_name] = near_boundary / total

        else:
            sensitivity[field_name] = 0.0

    return sensitivity


def build_optimizer_input(
    records: list[EvalRecord],
    config_snapshot: dict[str, Any] | None = None,
    golden_set_scores: list[float] | None = None,
    rollback_data: list[dict[str, Any]] | None = None,
) -> OptimizerInput:
    """Build the full optimizer input from eval records and config."""
    config_snapshot = config_snapshot or {}
    golden_set_scores = golden_set_scores or []

    metrics = compute_metrics(records, rollback_data=rollback_data)
    sensitivity = compute_sensitivity(records, config_snapshot)

    return OptimizerInput(
        metrics=metrics,
        config_snapshot=config_snapshot,
        golden_set_scores=golden_set_scores,
        sensitivity=sensitivity,
    )


def _task_error_counts(records: list[EvalRecord]) -> dict[str, int]:
    """Count errors per task_id."""
    counts: dict[str, int] = {}
    for rec in records:
        if rec.error_type:
            counts[rec.task_id] = counts.get(rec.task_id, 0) + 1
    return counts


def _infer_tier(model_name: str) -> str:
    """Infer model tier from name. Heuristic fallback when tier is not tagged."""
    name = model_name.lower()
    if "mini" in name or "fast" in name or "small" in name:
        return "fast"
    if "capable" in name or "gpt-4o" in name and "mini" not in name:
        return "capable"
    return "fast"
