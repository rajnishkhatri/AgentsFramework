"""Shared ``/run/stream`` request normalization for dev + prod middleware."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from middleware.goaljudge_saturation_bridge import (
    GoalJudgeSaturationContext,
    parse_goaljudge_thread_id,
    resolve_eval_user_id,
    saturation_input_overlay,
)
from trust.models import AgentFacts


@dataclass(frozen=True)
class RunStreamContext:
    """Normalized inputs for one ``LangGraphRuntime.run`` invocation."""

    thread_id: str
    user_input: dict[str, Any]
    task_input: str
    identity: AgentFacts
    telemetry_subject: str
    saturation: GoalJudgeSaturationContext | None


def _extract_task_input(user_input: dict[str, Any]) -> str:
    messages = user_input.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return str(last.get("content", ""))
    if isinstance(last, str):
        return last
    return ""


def build_run_stream_context(
    body: dict[str, Any],
    *,
    identity: AgentFacts,
    subject: str,
) -> RunStreamContext:
    """Parse BFF body, apply GoalJudge saturation bridge when ``gj:`` thread id present."""
    raw_thread_id = body.get("thread_id", uuid.uuid4().hex)
    user_input = body.get("input", {}) or {}
    if not isinstance(user_input, dict):
        user_input = {}

    saturation = parse_goaljudge_thread_id(str(raw_thread_id))
    eval_user_id = resolve_eval_user_id(identity.owner, saturation, subject)
    thread_id = (
        saturation.checkpoint_thread_id if saturation is not None else str(raw_thread_id)
    )

    runtime_input: dict[str, Any] = {**user_input}
    if saturation is not None:
        runtime_input["_goaljudge_saturation"] = saturation_input_overlay(
            saturation,
            eval_user_id,
        )

    identity_for_run = identity
    if eval_user_id != identity.owner:
        identity_for_run = identity.model_copy(update={"owner": eval_user_id})

    from middleware.goaljudge_saturation_bridge import resolve_telemetry_subject

    return RunStreamContext(
        thread_id=thread_id,
        user_input=runtime_input,
        task_input=_extract_task_input(user_input),
        identity=identity_for_run,
        telemetry_subject=resolve_telemetry_subject(subject, saturation),
        saturation=saturation,
    )


__all__ = ["RunStreamContext", "build_run_stream_context"]
