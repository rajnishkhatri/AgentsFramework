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
    async def test_sink_receives_pipeline_dimension_labels(self):
        """Tier 3 Phase 2.5 (close the D6 telemetry gap).

        ``react_loop`` also forwards the **pipeline-dimension labels** the
        gold-set will stratify across: ``planning_depth`` (D1),
        ``routing_reason`` (D3), ``model_tier`` (D4), ``cost_fraction`` (D6).
        Without these on the input side, Stage 6 cannot slice judge metrics
        by dimension from Langfuse alone — it would need to re-join other
        traces by trace_id, which the Tier 2 unblock session showed is brittle
        when traces are de-duplicated by deterministic id. Assert the sink
        carries them through to the exported attributes.
        """
        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        await publish_goal_judge(
            trace_id="trace-dims",
            user_id="synthetic-saturation-user",
            task_id="trace-dims",
            ai_input={
                "task_input": "Create f.txt, list its contents, and fetch weather.",
                "success_conditions": ["c1", "c2", "c3"],
                "final_answer": "Done.",
                "evidence_digest": "- file_io(write) -> ok",
                "tool_calls_summary": [
                    {"tool_name": "file_io", "args_keys": ["operation", "path"]},
                ],
                "plan_steps": 3,
                # The four new dimension labels.
                "planning_depth": "L2",
                "routing_reason": "capable-for-planning",
                "model_tier": "capable",
                "cost_fraction": 0.42,
            },
            ai_response={"goal_met": False, "partial_fraction": 0.33},
            step=4,
            model="gpt-4o",
        )

        assert len(exporter.calls) == 1
        attrs = exporter.calls[0]["attributes"]
        assert attrs["planning_depth"] == "L2"
        assert attrs["routing_reason"] == "capable-for-planning"
        assert attrs["model_tier"] == "capable"
        assert attrs["cost_fraction"] == 0.42

    @pytest.mark.asyncio
    async def test_long_values_survive_publish_intact(self):
        """Phase 0 cap lift (task_understanding plan §5, audit §2).

        The wave-1 corpus lost every judge input past 200 chars because the
        eval publish path reused ``redact_text``'s default cap. Generated
        success-condition lists and full final answers must reach the sink
        intact — the exemption is the whole point of Phase 0.
        """
        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        long_condition = "The agent enumerates every file in /workspace " + "x" * 600
        long_answer = "answer " * 300  # ~2100 chars

        await publish_goal_judge(
            trace_id="trace-long",
            user_id="u",
            task_id="trace-long",
            ai_input={
                "task_input": "t" * 1500,
                "success_conditions": [long_condition, "short one"],
                "final_answer": long_answer,
            },
            ai_response={"goal_met": True, "partial_fraction": 1.0},
            step=1,
            model="gpt-4o-mini",
        )

        attrs = exporter.calls[0]["attributes"]
        assert attrs["success_conditions"][0] == long_condition
        assert attrs["final_answer"] == long_answer
        assert attrs["task_input"] == "t" * 1500

    @pytest.mark.asyncio
    async def test_pii_redacted_on_long_values_without_truncation(self):
        """Redact ≠ truncate: the redactor still runs on exempted long values."""
        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        tail = "contact me at jane.doe@example.com for the key sk-1234567890abcdef"
        long_with_pii = "p" * 400 + " " + tail

        await publish_goal_judge(
            trace_id="trace-pii",
            user_id="u",
            task_id="trace-pii",
            ai_input={"task_input": long_with_pii, "success_conditions": ["c"]},
            ai_response={"goal_met": True},
            step=1,
            model=None,
        )

        published = exporter.calls[0]["attributes"]["task_input"]
        assert len(published) > 200  # not capped at the publisher default
        assert "jane.doe@example.com" not in published
        assert "sk-1234567890abcdef" not in published

    @pytest.mark.asyncio
    async def test_eval_value_cap_is_config_driven(self, monkeypatch):
        """The exemption is a larger bound, not unbounded — and env-tunable
        (numeric knob, AGENTS.md config convention)."""
        from services import eval_telemetry

        monkeypatch.setenv("EVAL_TELEMETRY_MAX_VALUE_LEN", "50")

        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        await publish_goal_judge(
            trace_id="trace-knob",
            user_id="u",
            task_id="trace-knob",
            ai_input={"task_input": "k" * 500, "success_conditions": ["c"]},
            ai_response={"goal_met": True},
            step=1,
            model=None,
        )

        assert exporter.calls[0]["attributes"]["task_input"] == "k" * 50
        # Default bound (env unset) is generous but finite.
        monkeypatch.delenv("EVAL_TELEMETRY_MAX_VALUE_LEN")
        assert eval_telemetry.eval_value_max_len() >= 4000

    def test_clip_eval_text_uses_configured_bound(self, monkeypatch):
        """``clip_eval_text`` replaces the ad-hoc ``[:500]`` snippets in
        ``react_loop`` gj_ai_input construction (audit §2 lift)."""
        from services.eval_telemetry import clip_eval_text, eval_value_max_len

        text = "z" * (eval_value_max_len() + 100)
        assert clip_eval_text(text) == "z" * eval_value_max_len()
        assert clip_eval_text("short") == "short"

        monkeypatch.setenv("EVAL_TELEMETRY_MAX_VALUE_LEN", "10")
        assert clip_eval_text("0123456789abcdef") == "0123456789"

    @pytest.mark.asyncio
    async def test_task_understanding_sink_failure_does_not_raise(self):
        """O1 (exception-swallowing FIRST): a broken sink must never abort
        the run — telemetry is best-effort, never load-bearing."""
        from services.eval_telemetry import publish_task_understanding

        broken = MagicMock()
        broken.publish_task_understanding.side_effect = RuntimeError("langfuse down")
        set_sink(broken)

        await publish_task_understanding(
            trace_id="t",
            user_id="u",
            task_id="t",
            ai_input={"task_input": "x"},
            ai_response={"restated_intent": "x", "success_conditions": ["a"]},
            step=0,
            model=None,
        )

    @pytest.mark.asyncio
    async def test_task_understanding_no_sink_is_noop(self):
        from services.eval_telemetry import publish_task_understanding

        await publish_task_understanding(
            trace_id="t",
            user_id="u",
            task_id="t",
            ai_input={},
            ai_response={},
            step=0,
            model=None,
        )

    @pytest.mark.asyncio
    async def test_task_understanding_published_redacted_and_uncapped(self):
        from services.eval_telemetry import publish_task_understanding

        exporter = _RecordingExporter()
        set_sink(LangfuseEvalTelemetrySink(exporter))

        long_condition = "The report must list every file in /workspace " + "y" * 400
        await publish_task_understanding(
            trace_id="trace-tu",
            user_id="u",
            task_id="trace-tu",
            ai_input={"task_input": "list files, email jane.doe@example.com"},
            ai_response={
                "restated_intent": "List the files and email the result.",
                "success_conditions": [long_condition, "second"],
                "confidence": 0.8,
                "source": "generated",
                "fallback_reason": "",
            },
            step=0,
            model="gpt-4o-mini",
        )

        assert len(exporter.calls) == 1
        call = exporter.calls[0]
        assert call["name"] == "eval.task_understanding"
        attrs = call["attributes"]
        assert "jane.doe@example.com" not in str(attrs)
        assert attrs["__output"]["success_conditions"][0] == long_condition

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
