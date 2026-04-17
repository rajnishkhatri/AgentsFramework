"""LangGraph feasibility gate: keep-or-replace decision (STORY-413).

Evaluates FrameworkTelemetry data against thresholds to produce a
structured FeasibilityReport. Zero imports from orchestration/.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from services.observability import FrameworkTelemetry

logger = logging.getLogger("meta.feasibility")

# Threshold constants
CHECKPOINT_USAGE_RATE_THRESHOLD = 0.10  # >10%
ROLLBACK_TIME_SAVED_THRESHOLD_MINUTES = 5.0  # >5 min per 100 tasks
AUTO_TRACE_INSIGHTS_THRESHOLD = 3  # >3


class FeasibilityReport(BaseModel):
    """Structured output from the feasibility gate."""

    keep_langgraph: bool
    checkpoint_usage_rate: float = 0.0
    rollback_time_saved_minutes: float = 0.0
    auto_trace_insights: int = 0
    criteria_met: dict[str, bool] = Field(default_factory=dict)
    recommendation: str = ""


class FeasibilityGate:
    """Evaluates LangGraph telemetry against keep-or-replace criteria."""

    def evaluate(
        self,
        telemetry: FrameworkTelemetry,
        total_tasks: int,
    ) -> FeasibilityReport:
        if total_tasks <= 0:
            raise ValueError(
                f"total_tasks must be positive, got {total_tasks}"
            )

        checkpoint_rate = telemetry.checkpoint_invocations / total_tasks
        rollback_minutes = telemetry.rollback_time_saved_ms / 60_000.0
        # Normalize to per-100-tasks
        rollback_per_100 = (
            (rollback_minutes / total_tasks) * 100 if total_tasks > 0 else 0.0
        )

        criteria = {
            "checkpoint_usage_rate": checkpoint_rate > CHECKPOINT_USAGE_RATE_THRESHOLD,
            "rollback_time_saved": rollback_per_100 > ROLLBACK_TIME_SAVED_THRESHOLD_MINUTES,
            "auto_trace_insights": telemetry.auto_trace_insights > AUTO_TRACE_INSIGHTS_THRESHOLD,
        }

        keep = all(criteria.values())

        if keep:
            recommendation = (
                "KEEP LangGraph. All three criteria are met: "
                f"checkpoint usage rate ({checkpoint_rate:.1%}) exceeds {CHECKPOINT_USAGE_RATE_THRESHOLD:.0%}, "
                f"rollback time saved ({rollback_per_100:.1f} min/100 tasks) exceeds "
                f"{ROLLBACK_TIME_SAVED_THRESHOLD_MINUTES} min, and "
                f"{telemetry.auto_trace_insights} auto-trace insights exceed "
                f"{AUTO_TRACE_INSIGHTS_THRESHOLD}."
            )
        else:
            failed = [k for k, v in criteria.items() if not v]
            recommendation = (
                f"REPLACE LangGraph. {len(failed)} of 3 criteria not met: "
                f"{', '.join(failed)}. Consider the Pydantic AI fallback prototype."
            )

        return FeasibilityReport(
            keep_langgraph=keep,
            checkpoint_usage_rate=checkpoint_rate,
            rollback_time_saved_minutes=rollback_per_100,
            auto_trace_insights=telemetry.auto_trace_insights,
            criteria_met=criteria,
            recommendation=recommendation,
        )
