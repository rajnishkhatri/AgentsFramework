"""Record AI input/output with target tags (H5 pattern).

Every LLM call, tool execution, and guardrail check records its
input/output. Builds a dict matching the EvalRecord schema defined
in components/schemas.py, but does NOT import from components/ to
satisfy the dependency rule (services must not import components).

Downstream consumers (meta/analysis.py) parse with EvalRecord.model_validate_json().
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("services.eval_capture")


async def record(
    target: str,
    ai_input: dict[str, Any],
    ai_response: Any,
    config: dict[str, Any],
    step: int = 0,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd: float | None = None,
    latency_ms: float | None = None,
) -> None:
    """Build an eval record dict and emit via the eval_capture logger."""
    configurable = config.get("configurable", {})
    eval_record = {
        "schema_version": 1,
        "timestamp": datetime.now(UTC).isoformat(),
        "task_id": configurable.get("task_id", ""),
        "user_id": configurable.get("user_id", "anonymous"),
        "step": step,
        "target": target,
        "model": model,
        "ai_input": ai_input,
        "ai_response": ai_response if isinstance(ai_response, (dict, str)) else str(ai_response),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
    }
    logger.info("AI Response", extra=eval_record)
