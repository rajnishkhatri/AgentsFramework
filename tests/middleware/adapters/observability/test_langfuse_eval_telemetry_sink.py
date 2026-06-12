"""L2 Contract: LangfuseEvalTelemetrySink maps eval rows to observations."""

from __future__ import annotations

from typing import Any

from middleware.adapters.observability.langfuse_eval_telemetry_sink import (
    LangfuseEvalTelemetrySink,
)


class _StubExporter:
    def __init__(self) -> None:
        self.last: dict[str, Any] | None = None

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        self.last = {"name": name, "trace_id": trace_id, "attributes": attributes}
        return True

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def flush(self) -> None:
        pass


class TestLangfuseEvalTelemetrySink:
    def test_exports_eval_goal_judge_observation(self):
        exporter = _StubExporter()
        sink = LangfuseEvalTelemetrySink(exporter)

        sink.publish_goal_judge(
            trace_id="wf-abc",
            user_id="user-1",
            task_id="wf-abc",
            ai_input={"task_input": "task", "success_conditions": []},
            ai_response={
                "goal_met": False,
                "criteria_met": 0.67,
                "partial_fraction": 0.67,
                "would_downgrade": True,
            },
            step=2,
            model="judge-model",
        )

        assert exporter.last is not None
        assert exporter.last["name"] == "eval.goal_judge"
        assert exporter.last["trace_id"] == "wf-abc"
        attrs = exporter.last["attributes"]
        assert attrs["target"] == "goal_judge"
        assert attrs["__bb_observation_type"] == "evaluator"
        assert attrs["__output"]["partial_fraction"] == 0.67

    def test_long_success_conditions_round_trip_unmodified(self):
        """Phase 0 cap lift: the sink itself must not shorten values — caps
        live upstream (eval_telemetry) and are exempted there."""
        exporter = _StubExporter()
        sink = LangfuseEvalTelemetrySink(exporter)

        conditions = ["c-" + "y" * 600, "second condition"]
        sink.publish_goal_judge(
            trace_id="wf-long",
            user_id="u",
            task_id="wf-long",
            ai_input={
                "task_input": "t" * 1500,
                "success_conditions": conditions,
                "final_answer": "a" * 900,
            },
            ai_response={"goal_met": True},
            step=1,
            model="m",
        )

        attrs = exporter.last["attributes"]
        assert attrs["success_conditions"] == conditions
        assert attrs["task_input"] == "t" * 1500
        assert attrs["final_answer"] == "a" * 900

    def test_exporter_exception_is_swallowed(self):
        class _RaisingExporter:
            def export_event(self, **kwargs: Any) -> bool:
                raise RuntimeError("boom")

            def release_trace(self, trace_id: str) -> None:
                pass

            def shutdown(self) -> None:
                pass

            def flush(self) -> None:
                pass

        sink = LangfuseEvalTelemetrySink(_RaisingExporter())
        sink.publish_goal_judge(
            trace_id="t",
            user_id="u",
            task_id="t",
            ai_input={},
            ai_response={"goal_met": True},
            step=0,
            model=None,
        )
