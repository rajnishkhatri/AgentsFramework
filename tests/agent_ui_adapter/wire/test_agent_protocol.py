"""L1 Deterministic: Tests for agent_ui_adapter.wire.agent_protocol.

Per AGENT_UI_ADAPTER_SPRINTS.md US-2.2 acceptance criteria.
TDD Protocol A. Failure paths first.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from agent_ui_adapter.wire.agent_protocol import (
    HealthResponse,
    RunCreateRequest,
    RunStateView,
    ThreadCreateRequest,
    ThreadState,
)


# ── ThreadCreateRequest ───────────────────────────────────────────────


class TestThreadCreateRequest:
    def test_valid_minimal(self):
        req = ThreadCreateRequest(user_id="u1")
        assert req.user_id == "u1"
        assert req.metadata == {}

    def test_valid_with_metadata(self):
        req = ThreadCreateRequest(user_id="u1", metadata={"k": "v"})
        assert req.metadata == {"k": "v"}

    def test_rejects_missing_user_id(self):
        with pytest.raises(ValidationError):
            ThreadCreateRequest()  # type: ignore[call-arg]

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ThreadCreateRequest(user_id="u1", bogus=1)  # type: ignore[call-arg]


# ── ThreadState ───────────────────────────────────────────────────────


class TestThreadState:
    def test_valid_minimal(self):
        now = datetime.now(UTC)
        state = ThreadState(
            thread_id="t1",
            user_id="u1",
            created_at=now,
            updated_at=now,
        )
        assert state.thread_id == "t1"
        assert state.messages == []

    def test_rejects_missing_thread_id(self):
        with pytest.raises(ValidationError):
            ThreadState(  # type: ignore[call-arg]
                user_id="u1",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ThreadState(
                thread_id="t1",
                user_id="u1",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                bogus=1,  # type: ignore[call-arg]
            )

    def test_round_trip_preserves_all_fields(self):
        now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
        original = ThreadState(
            thread_id="t1",
            user_id="u1",
            messages=[{"role": "user", "content": "hi"}],
            created_at=now,
            updated_at=now,
        )
        rehydrated = ThreadState.model_validate_json(original.model_dump_json())
        assert rehydrated == original


# ── RunCreateRequest ──────────────────────────────────────────────────


class TestRunCreateRequest:
    def test_valid_minimal(self):
        req = RunCreateRequest(thread_id="t1", input={"text": "hi"})
        assert req.thread_id == "t1"
        assert req.agent_id is None

    def test_valid_with_agent_id(self):
        req = RunCreateRequest(thread_id="t1", input={"text": "hi"}, agent_id="agent-x")
        assert req.agent_id == "agent-x"

    def test_rejects_missing_thread_id(self):
        with pytest.raises(ValidationError):
            RunCreateRequest(input={"text": "hi"})  # type: ignore[call-arg]

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            RunCreateRequest(
                thread_id="t1",
                input={},
                bogus=1,  # type: ignore[call-arg]
            )


# ── RunStateView ──────────────────────────────────────────────────────


class TestRunStateView:
    def test_valid_running(self):
        view = RunStateView(
            run_id="r1",
            thread_id="t1",
            status="running",
            started_at=datetime.now(UTC),
            completed_at=None,
        )
        assert view.status == "running"
        assert view.completed_at is None

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            RunStateView(
                run_id="r1",
                thread_id="t1",
                status="weird",  # type: ignore[arg-type]
                started_at=datetime.now(UTC),
                completed_at=None,
            )

    def test_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            RunStateView(  # type: ignore[call-arg]
                run_id="r1",
                thread_id="t1",
                status="running",
                completed_at=None,
            )

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            RunStateView(
                run_id="r1",
                thread_id="t1",
                status="running",
                started_at=datetime.now(UTC),
                completed_at=None,
                bogus=1,  # type: ignore[call-arg]
            )


# ── HealthResponse ────────────────────────────────────────────────────


class TestHealthResponse:
    def test_valid(self):
        resp = HealthResponse(status="ok", adapter_version="0.1.0")
        assert resp.status == "ok"

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="degraded", adapter_version="0.1.0")  # type: ignore[arg-type]

    def test_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="ok")  # type: ignore[call-arg]

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            HealthResponse(
                status="ok",
                adapter_version="0.1.0",
                bogus=1,  # type: ignore[call-arg]
            )


# ── Property-based round-trip ─────────────────────────────────────────


@pytest.mark.property
@given(
    thread_id=st.text(min_size=1, max_size=64),
    user_id=st.text(min_size=1, max_size=64),
)
def test_thread_state_round_trip(thread_id: str, user_id: str):
    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    original = ThreadState(
        thread_id=thread_id,
        user_id=user_id,
        messages=[],
        created_at=now,
        updated_at=now,
    )
    rehydrated = ThreadState.model_validate_json(original.model_dump_json())
    assert rehydrated == original
