"""Structured reflection tool for bounded internal reasoning notes."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.tools.registry import ToolExecutionResult


class ThinkToolInput(BaseModel):
    thought: str = Field(min_length=1, max_length=500)
    category: Literal["hypothesis", "risk", "decision", "observation"] = "observation"
    next_action: str | None = Field(default=None, max_length=160)
    state: dict[str, Any] = Field(default_factory=dict, alias="_state")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("thought")
    @classmethod
    def _normalize_whitespace(cls, value: str) -> str:
        return " ".join(value.strip().split())


def execute_think_tool(args: dict[str, Any]) -> ToolExecutionResult:
    """Append a bounded reflection entry to ``reasoning_trace``."""
    try:
        validated = ThinkToolInput(**args)
    except Exception as exc:
        return ToolExecutionResult(output=f"Error: {exc}", ok=False, error=str(exc))

    trace_entry = {
        "category": validated.category,
        "thought": validated.thought,
        "next_action": validated.next_action or "",
    }
    return ToolExecutionResult(
        output=json.dumps(trace_entry),
        ok=True,
        state_delta={"reasoning_trace": [json.dumps(trace_entry)]},
    )
