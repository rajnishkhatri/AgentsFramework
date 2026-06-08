"""L2 contract tests for GoalJudge UI saturation bridge (G1)."""

from __future__ import annotations

import uuid

import pytest

from middleware.goaljudge_saturation_bridge import (
    SATURATION_USER_ID,
    is_saturation_subject,
    parse_goaljudge_thread_id,
    resolve_eval_user_id,
    resolve_telemetry_subject,
    saturation_input_overlay,
)
from trust.models import AgentFacts


def _facts(owner: str = "workos-sub-1") -> AgentFacts:
    return AgentFacts(
        agent_id="agent-1",
        agent_name="Agent",
        owner=owner,
        version="1.0.0",
    )


class TestParseGoaljudgeThreadId:
    def test_rejects_random_uuid_thread(self) -> None:
        assert parse_goaljudge_thread_id(uuid.uuid4().hex) is None

    def test_rejects_missing_trace_segment(self) -> None:
        assert parse_goaljudge_thread_id("gj:GJ-010") is None

    def test_rejects_non_hex_trace(self) -> None:
        assert parse_goaljudge_thread_id("gj:GJ-010:not-a-trace") is None

    def test_parses_walkthrough_case(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-010").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-010:{trace_id}")
        assert ctx is not None
        assert ctx.case_id == "GJ-010"
        assert ctx.trace_id == trace_id
        assert ctx.session_id == "session-gj-010"
        assert ctx.checkpoint_thread_id == "session-gj-010"


class TestSaturationSubjectMapping:
    def test_unknown_subject_not_saturation(self) -> None:
        allow = frozenset({"user_saturation"})
        assert is_saturation_subject("other", allowlist=allow) is False

    def test_allowlisted_subject_maps_to_saturation_user(self) -> None:
        allow = frozenset({"user_saturation"})
        assert resolve_telemetry_subject("user_saturation", None, allowlist=allow) == (
            SATURATION_USER_ID
        )
        assert resolve_eval_user_id("user_saturation", None, "user_saturation", allowlist=allow) == (
            SATURATION_USER_ID
        )


class TestSaturationOverlay:
    def test_overlay_matches_cli_batch_keys(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-003B").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-003B:{trace_id}")
        assert ctx is not None
        overlay = saturation_input_overlay(ctx, SATURATION_USER_ID)
        assert overlay["trace_id"] == trace_id
        assert overlay["task_id"] == trace_id
        assert overlay["user_id"] == SATURATION_USER_ID
        assert overlay["case_id"] == "GJ-003B"


class TestRunStreamContext:
    @pytest.mark.parametrize(
        "thread_id",
        [
            "not-gj-thread",
            "gj:GJ-010:short",
        ],
    )
    def test_non_gj_thread_preserves_identity_owner(self, thread_id: str) -> None:
        from middleware.run_stream_context import build_run_stream_context

        identity = _facts("workos-sub-1")
        ctx = build_run_stream_context(
            {"thread_id": thread_id, "input": {"messages": [{"role": "user", "content": "hi"}]}},
            identity=identity,
            subject="workos-sub-1",
        )
        assert ctx.saturation is None
        assert ctx.identity.owner == "workos-sub-1"
        assert ctx.telemetry_subject == "workos-sub-1"
        assert "_goaljudge_saturation" not in ctx.user_input

    def test_gj_thread_applies_saturation_overlay(self) -> None:
        from middleware.run_stream_context import build_run_stream_context

        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-010").hex
        identity = _facts("workos-sub-1")
        ctx = build_run_stream_context(
            {
                "thread_id": f"gj:GJ-010:{trace_id}",
                "input": {"messages": [{"role": "user", "content": "prompt"}]},
            },
            identity=identity,
            subject="workos-sub-1",
        )
        assert ctx.saturation is not None
        assert ctx.saturation.case_id == "GJ-010"
        assert ctx.thread_id == "session-gj-010"
        assert ctx.identity.owner == SATURATION_USER_ID
        assert ctx.telemetry_subject == SATURATION_USER_ID
        overlay = ctx.user_input["_goaljudge_saturation"]
        assert overlay["trace_id"] == trace_id
        assert overlay["task_id"] == trace_id
