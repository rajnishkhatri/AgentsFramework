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

    def test_checkpoint_thread_is_fresh_per_parse(self) -> None:
        """Replaying a case must NOT resume the prior batch's LangGraph
        checkpoint thread. A static ``session-gj-XXX`` checkpoint id
        saturates across batch reruns until the agent ends every run with
        an empty message (observed on Cloud Run 2026-06-11). The session_id
        stays stable as the telemetry join key; only the checkpoint thread
        gets a fresh suffix.
        """
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-010").hex
        first = parse_goaljudge_thread_id(f"gj:GJ-010:{trace_id}")
        second = parse_goaljudge_thread_id(f"gj:GJ-010:{trace_id}")
        assert first is not None and second is not None
        assert first.checkpoint_thread_id != second.checkpoint_thread_id
        assert first.checkpoint_thread_id.startswith("session-gj-010-")
        assert second.session_id == first.session_id == "session-gj-010"

    def test_parses_fresh_authored_case(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-F-001").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-F-001:{trace_id}")
        assert ctx is not None
        assert ctx.case_id == "GJ-F-001"
        assert ctx.trace_id == trace_id
        assert ctx.session_id == "session-gj-f-001"

    def test_parses_model_ab_family_ids(self) -> None:
        """The model-A/B corpus families (GJ-ABGENL/ABMULT/ABMEMO-NN) must adopt
        a deterministic trace_id like every other gj: family, or the analyzer
        can't join the run to its Langfuse trace."""
        for gj_id in ("GJ-ABGENL-01", "GJ-ABMULT-06", "GJ-ABMEMO-03"):
            trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, gj_id).hex
            ctx = parse_goaljudge_thread_id(f"gj:{gj_id}:{trace_id}")
            assert ctx is not None, f"{gj_id} did not parse"
            assert ctx.case_id == gj_id
            assert ctx.trace_id == trace_id


class TestParseMemThreadId:
    """The ``mem:`` bridge carries a PER-CASE user_id so the memory
    multi-session corpus can prove cross-session recall AND the cross-user-leak
    guard. The ``gj:`` bridge collapses every run to ``SATURATION_USER_ID`` (one
    user), which would make a leak structurally impossible to observe. Form:
    ``mem:{mem_id}:s{session_idx}:{user_id8}:{trace_id}``.
    """

    def test_rejects_gj_thread_as_mem(self) -> None:
        # A gj: thread still parses (as gj), but its user_id field is None.
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-010").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-010:{trace_id}")
        assert ctx is not None
        assert ctx.user_id is None  # gj: never carries a per-case user_id

    def test_rejects_mem_without_user_segment(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "MEM-0001").hex
        assert parse_goaljudge_thread_id(f"mem:MEM-0001:s0:{trace_id}") is None

    def test_rejects_mem_non_hex_trace(self) -> None:
        assert parse_goaljudge_thread_id("mem:MEM-0001:s0:abcd1234:nope") is None

    def test_parses_mem_thread_with_user_and_session(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "MEM-0001:s1").hex
        ctx = parse_goaljudge_thread_id(f"mem:MEM-0001:s1:user0001:{trace_id}")
        assert ctx is not None
        assert ctx.case_id == "MEM-0001"
        assert ctx.trace_id == trace_id
        assert ctx.user_id == "user0001"
        assert ctx.session_idx == 1
        # session_id keeps the per-session position so seed/probe traces are
        # distinct join keys within one case.
        assert ctx.session_id == "session-mem-0001-s1"

    def test_mem_checkpoint_thread_is_fresh_per_parse(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "MEM-0001:s0").hex
        first = parse_goaljudge_thread_id(f"mem:MEM-0001:s0:user0001:{trace_id}")
        second = parse_goaljudge_thread_id(f"mem:MEM-0001:s0:user0001:{trace_id}")
        assert first is not None and second is not None
        assert first.checkpoint_thread_id != second.checkpoint_thread_id


class TestMemUserIdResolution:
    """The headline precision precondition: two cases with distinct per-case
    user_ids MUST resolve to distinct eval_user_ids, or no cross-user leak can
    ever be detected (one user => no leak possible).
    """

    def test_mem_user_id_resolves_per_case(self) -> None:
        t_a = uuid.uuid5(uuid.NAMESPACE_DNS, "A").hex
        t_b = uuid.uuid5(uuid.NAMESPACE_DNS, "B").hex
        ctx_a = parse_goaljudge_thread_id(f"mem:MEM-A:s0:useraaaa:{t_a}")
        ctx_b = parse_goaljudge_thread_id(f"mem:MEM-B:s0:userbbbb:{t_b}")
        assert ctx_a is not None and ctx_b is not None
        ua = resolve_eval_user_id("workos-sub-1", ctx_a, "workos-sub-1")
        ub = resolve_eval_user_id("workos-sub-1", ctx_b, "workos-sub-1")
        assert ua == "useraaaa"
        assert ub == "userbbbb"
        assert ua != ub, "distinct per-case user_ids must NOT collapse to one user"

    def test_gj_thread_still_collapses_to_saturation_user(self) -> None:
        # Regression guard: the gj: path is unchanged.
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-010").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-010:{trace_id}")
        assert ctx is not None
        assert resolve_eval_user_id("workos-sub-1", ctx, "workos-sub-1") == (
            SATURATION_USER_ID
        )

    def test_mem_telemetry_subject_uses_per_case_user(self) -> None:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "MEM-A").hex
        ctx = parse_goaljudge_thread_id(f"mem:MEM-A:s0:useraaaa:{trace_id}")
        assert ctx is not None
        assert resolve_telemetry_subject("workos-sub-1", ctx) == "useraaaa"


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
        """``trace_id`` is the deterministic Langfuse join key for replay; it
        is the only correlation field we lock down here. ``task_id`` is left
        to the runtime to mint fresh per invocation — see
        ``test_overlay_does_not_pin_task_id`` for the regression guard.
        """
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-003B").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-003B:{trace_id}")
        assert ctx is not None
        overlay = saturation_input_overlay(ctx, SATURATION_USER_ID)
        assert overlay["trace_id"] == trace_id
        assert overlay["user_id"] == SATURATION_USER_ID
        assert overlay["case_id"] == "GJ-003B"

    def test_overlay_does_not_pin_task_id(self) -> None:
        """Per-invocation regression guard: ``task_id`` MUST NOT be carried in
        the saturation overlay. Pinning it to the deterministic ``trace_id``
        makes every Playwright replay of the same registry case look like a
        continuation of the prior run, which causes
        ``components.router.select_planning_depth`` to short-circuit to
        ``L0`` via the per-task synthesis check. The runtime defaults
        ``task_id`` to a fresh ``uuid.uuid4().hex`` when this key is absent —
        same as the non-saturation path — so every replay is a fresh task
        for the planner. See
        ``middleware/goaljudge_saturation_bridge.saturation_input_overlay``.
        """
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "GJ-012").hex
        ctx = parse_goaljudge_thread_id(f"gj:GJ-012:{trace_id}")
        assert ctx is not None
        overlay = saturation_input_overlay(ctx, SATURATION_USER_ID)
        assert "task_id" not in overlay, (
            "task_id leaks the saturation trace_id into the planner's per-task "
            "scoping filter and forces multi-subtask prompts to L0/1 plan step"
        )


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
        # Fresh checkpoint thread per run (suffix), stable session prefix.
        assert ctx.thread_id.startswith("session-gj-010-")
        assert ctx.thread_id != "session-gj-010"
        assert ctx.identity.owner == SATURATION_USER_ID
        assert ctx.telemetry_subject == SATURATION_USER_ID
        overlay = ctx.user_input["_goaljudge_saturation"]
        assert overlay["trace_id"] == trace_id
        # task_id is deliberately NOT pinned to trace_id (see
        # TestSaturationOverlay.test_overlay_does_not_pin_task_id).
        assert "task_id" not in overlay

    def test_mem_thread_sets_per_case_owner(self) -> None:
        """End-to-end: a ``mem:`` thread makes identity.owner the PER-CASE user
        (not SATURATION_USER_ID), so the recall/store seams key on it and the
        cross-user-leak guard is testable. The login subject is the harness;
        the per-case user_id is the synthetic memory subject.
        """
        from middleware.run_stream_context import build_run_stream_context

        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, "MEM-0001:s1").hex
        identity = _facts("workos-sub-1")
        ctx = build_run_stream_context(
            {
                "thread_id": f"mem:MEM-0001:s1:user0001:{trace_id}",
                "input": {"messages": [{"role": "user", "content": "prompt"}]},
            },
            identity=identity,
            subject="workos-sub-1",
        )
        assert ctx.saturation is not None
        assert ctx.saturation.case_id == "MEM-0001"
        assert ctx.saturation.user_id == "user0001"
        assert ctx.identity.owner == "user0001"
        assert ctx.telemetry_subject == "user0001"
        overlay = ctx.user_input["_goaljudge_saturation"]
        assert overlay["trace_id"] == trace_id
        assert overlay["user_id"] == "user0001"
