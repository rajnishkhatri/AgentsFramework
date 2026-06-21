"""C1 Phase 8 — L2 shadow contract: publish_compaction_fidelity sink (design §8.3).

This sink mirrors ``publish_goal_judge`` / ``publish_task_understanding`` on
``LangfuseEvalTelemetrySink``: it maps an ``eval_capture.record(target=
"compaction_fidelity", ...)`` row to a Langfuse ``eval.compaction_fidelity``
observation. **Shadow-only** in v1 — never gates a fold (AP-7).

Two AGENTS.md rules pin the privacy posture (design §8.3):
- the ``ai_input`` here MAY carry the dropped-prefix digest + constraint
  strings — this is a dev/telemetry path, not a governance carrier
  (asymmetry with §7);
- the sink itself NEVER shortens values (Phase 0 cap lift); caps live
  upstream in ``eval_telemetry`` and are exempted there.

L2 (record/replay) tests, no Langfuse SDK, no real I/O.
"""

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


class TestPublishCompactionFidelity:
    def test_exports_eval_compaction_fidelity_observation(self) -> None:
        """Auto-maps via ``observation_name_for_target("compaction_fidelity")``
        ⇒ ``eval.compaction_fidelity`` (no registry edit needed)."""
        exporter = _StubExporter()
        sink = LangfuseEvalTelemetrySink(exporter)

        sink.publish_compaction_fidelity(
            trace_id="wf-cf-1",
            user_id="u-1",
            task_id="wf-cf-1",
            ai_input={
                "task_input": "redact secrets from foo.txt",
                "dropped_prefix_digest": "sha256:abc123",
                "pinned_constraints": ["never delete files"],
                "summary": "SUMMARY:\n  redacted secrets\n",
            },
            ai_response={
                "decision_loss": False,
                "constraint_loss": False,
                "unsafe_fold": False,
                "evidence_span": "tool result line 3",
                "token_reduction_ratio": 0.67,
            },
            step=3,
            model="judge-model",
        )

        assert exporter.last is not None
        assert exporter.last["name"] == "eval.compaction_fidelity"
        assert exporter.last["trace_id"] == "wf-cf-1"
        attrs = exporter.last["attributes"]
        assert attrs["target"] == "compaction_fidelity"
        assert attrs["__bb_observation_type"] == "evaluator"

    def test_carries_identity_and_step(self) -> None:
        """Mandatory eval-capture identity fields (design §8.3): ``user_id``
        and ``task_id`` reach the observation attrs. AGENTS.md §Always
        requires every LLM-call record to carry both."""
        exporter = _StubExporter()
        sink = LangfuseEvalTelemetrySink(exporter)

        sink.publish_compaction_fidelity(
            trace_id="wf-id",
            user_id="user-42",
            task_id="task-77",
            ai_input={"task_input": "x", "summary": "s"},
            ai_response={"unsafe_fold": False},
            step=11,
            model="m",
        )
        attrs = exporter.last["attributes"]
        assert attrs["user_id"] == "user-42"
        assert attrs["task_id"] == "task-77"
        assert attrs["step"] == 11
        assert attrs["subject"] == "user-42"

    def test_carries_verdict_in_output(self) -> None:
        """The judge verdict (``unsafe_fold``, the action-triggering class)
        rides on ``__output`` so Stage 6 metrics can slice by verdict."""
        exporter = _StubExporter()
        sink = LangfuseEvalTelemetrySink(exporter)

        sink.publish_compaction_fidelity(
            trace_id="wf-v",
            user_id="u",
            task_id="wf-v",
            ai_input={"task_input": "x", "summary": "s"},
            ai_response={
                "decision_loss": True,
                "constraint_loss": False,
                "unsafe_fold": True,
                "evidence_span": "decision dropped on line 4",
            },
            step=1,
            model="m",
        )
        attrs = exporter.last["attributes"]
        assert attrs["__output"]["unsafe_fold"] is True
        assert attrs["__output"]["decision_loss"] is True

    def test_long_inputs_round_trip_unmodified(self) -> None:
        """Phase 0 cap lift mirror: the sink itself does not shorten values.
        Caps live upstream — the dev/telemetry wire takes long inputs."""
        exporter = _StubExporter()
        sink = LangfuseEvalTelemetrySink(exporter)

        long_summary = "S" * 2000
        long_constraint = "never " + "y" * 600
        sink.publish_compaction_fidelity(
            trace_id="wf-long",
            user_id="u",
            task_id="wf-long",
            ai_input={
                "task_input": "t" * 1200,
                "summary": long_summary,
                "pinned_constraints": [long_constraint],
                "dropped_prefix_digest": "sha256:0123",
            },
            ai_response={"unsafe_fold": False},
            step=0,
            model="m",
        )
        attrs = exporter.last["attributes"]
        assert attrs["summary"] == long_summary
        assert attrs["pinned_constraints"] == [long_constraint]

    def test_exporter_exception_is_swallowed(self) -> None:
        """The L2 sink must NEVER raise — a Langfuse hiccup must not bubble
        into the agent loop. Mirrors the pattern on the other publishers."""

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
        # No raise — this is the assertion.
        sink.publish_compaction_fidelity(
            trace_id="t",
            user_id="u",
            task_id="t",
            ai_input={},
            ai_response={"unsafe_fold": False},
            step=0,
            model=None,
        )
