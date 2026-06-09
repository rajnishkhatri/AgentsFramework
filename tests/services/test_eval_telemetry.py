"""L2 Contract: eval telemetry E1 sink wiring."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from middleware.adapters.observability.langfuse_eval_telemetry_sink import (
    LangfuseEvalTelemetrySink,
)
from services.eval_telemetry import (
    observation_name_for_target,
    publish_goal_judge,
    set_sink,
)


class _RecordingExporter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        self.calls.append(
            {"name": name, "trace_id": trace_id, "attributes": dict(attributes or {})}
        )
        return True

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def flush(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _clear_sink():
    set_sink(None)
    yield
    set_sink(None)


class TestEvalTelemetryPublish:
    @pytest.mark.asyncio
    async def test_no_sink_is_noop(self):
        await publish_goal_judge(
            trace_id="trace-1",
            user_id="user-a",
            task_id="trace-1",
            ai_input={"task_input": "hello"},
            ai_response={"goal_met": False, "partial_fraction": 0.0},
            step=3,
            model="gpt-4o-mini",
        )

    @pytest.mark.asyncio
    async def test_sink_receives_redacted_goal_judge_export(self):
        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        await publish_goal_judge(
            trace_id="cbfe84539b675824a1eb08b331204b8d",
            user_id="synthetic-saturation-user",
            task_id="cbfe84539b675824a1eb08b331204b8d",
            ai_input={
                "task_input": "sk-1234567890abcdef",
                "success_conditions": ["do the thing"],
            },
            ai_response={
                "goal_met": False,
                "partial_fraction": 0.0,
                "graceful_failure": True,
                "rationale": "partial progress only",
                "per_criterion": {"a2": False},
            },
            step=5,
            model="gpt-4o-mini",
        )

        assert len(exporter.calls) == 1
        call = exporter.calls[0]
        assert call["name"] == observation_name_for_target("goal_judge")
        assert call["trace_id"] == "cbfe84539b675824a1eb08b331204b8d"
        attrs = call["attributes"]
        assert attrs["target"] == "goal_judge"
        assert "sk-" not in attrs["task_input"]
        output = attrs["__output"]
        assert output["goal_met"] is False
        assert output["partial_fraction"] == 0.0
        assert output["graceful_failure"] is True

    @pytest.mark.asyncio
    async def test_sink_receives_enriched_goal_judge_audit_fields(self):
        """E.1 (Stage 4 Confirmation telemetry enrichment).

        ``react_loop`` now forwards the ``final_answer``, ``evidence_digest``,
        ``tool_calls_summary``, and ``plan_steps`` fields it actually fed the
        judge — so a surprising verdict can be re-read end-to-end from the
        Langfuse trace. Assert the sink passes them through redaction without
        losing the audit trail.
        """
        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        await publish_goal_judge(
            trace_id="trace-enriched",
            user_id="synthetic-saturation-user",
            task_id="trace-enriched",
            ai_input={
                "task_input": "list its contents",
                "success_conditions": ["c1", "c2"],
                "final_answer": "The contents of /workspace are: f1.txt, f2.txt",
                "evidence_digest": "- shell(input={'command': 'ls /workspace'}) -> f1.txt\\nf2.txt",
                "tool_calls_summary": [
                    {"tool_name": "shell", "args_keys": ["command"]},
                ],
                "plan_steps": 1,
            },
            ai_response={"goal_met": False, "partial_fraction": 0.33},
            step=4,
            model="gpt-4o-mini",
        )

        assert len(exporter.calls) == 1
        attrs = exporter.calls[0]["attributes"]
        assert attrs["final_answer"].startswith("The contents")
        assert "ls /workspace" in attrs["evidence_digest"]
        assert attrs["tool_calls_summary"] == [
            {"tool_name": "shell", "args_keys": ["command"]}
        ]
        assert attrs["plan_steps"] == 1

    @pytest.mark.asyncio
    async def test_sink_failure_does_not_raise(self):
        broken = MagicMock()
        broken.publish_goal_judge.side_effect = RuntimeError("langfuse down")
        set_sink(broken)

        await publish_goal_judge(
            trace_id="t",
            user_id="u",
            task_id="t",
            ai_input={},
            ai_response={"goal_met": True},
            step=0,
            model=None,
        )
