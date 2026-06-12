"""L2 Contract: the soft-gate understanding edit endpoint (Phase 4).

Mocked runtime adapter throughout. Failure paths first (TAP-4): the
auth-reject and malformed-payload cases precede the happy path, and the
governance assertion is rejection-shaped — an edit WITHOUT a corresponding
PARAMETER_CHANGED event in the hash-chained trace is a test failure (the
verdict basis must never change unrecorded, plan §4.7).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from middleware.understanding_edit import register_understanding_edit_route
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent


class _FakeRuntime:
    def __init__(
        self,
        *,
        raises: Exception | None = None,
        old: dict | None = None,
    ) -> None:
        self._raises = raises
        self._old = old or {
            "restated_intent": "old intent",
            "success_conditions": ["old a", "old b"],
            "source": "generated",
        }
        self.calls: list[dict[str, Any]] = []

    async def update_task_understanding(
        self,
        *,
        thread_id: str,
        trace_id: str,
        restated_intent: str,
        success_conditions: list[str],
    ) -> tuple[dict, dict]:
        self.calls.append(
            {
                "thread_id": thread_id,
                "trace_id": trace_id,
                "restated_intent": restated_intent,
                "success_conditions": success_conditions,
            }
        )
        if self._raises is not None:
            raise self._raises
        new = {
            **self._old,
            "restated_intent": restated_intent,
            "success_conditions": success_conditions,
            "source": "user_edited",
        }
        return self._old, new


def _client(tmp_path, runtime: _FakeRuntime) -> TestClient:
    app = FastAPI()

    def verify(authorization: str | None) -> str:
        if authorization != "Bearer good-token":
            raise HTTPException(status_code=401, detail="unauthorized")
        return "user-workos-1"

    register_understanding_edit_route(
        app,
        verify_bearer=verify,
        get_runtime=lambda: runtime,
        black_box_dir=tmp_path / "black_box_recordings",
    )
    return TestClient(app, raise_server_exceptions=False)


_VALID_BODY = {
    "trace_id": "tr-1",
    "restated_intent": "Create the file and verify it.",
    "success_conditions": ["file exists", "contents verified"],
}
_URL = "/run/understanding/thread-1"
_AUTH = {"Authorization": "Bearer good-token"}


def _seed_trace(tmp_path, workflow_id: str = "tr-1") -> None:
    """Start a chained trace the way the graph would."""
    recorder = BlackBoxRecorder(storage_dir=tmp_path / "black_box_recordings")
    recorder.record(TraceEvent(
        event_id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=EventType.TASK_STARTED,
        timestamp=datetime.now(UTC),
        details={"task_input": "create the file"},
    ))


# ── Failure paths first ──────────────────────────────────────────────


class TestRejections:
    def test_unauthenticated_request_is_401(self, tmp_path):
        client = _client(tmp_path, _FakeRuntime())
        resp = client.post(_URL, json=_VALID_BODY)
        assert resp.status_code == 401

    def test_bad_token_is_401(self, tmp_path):
        client = _client(tmp_path, _FakeRuntime())
        resp = client.post(
            _URL, json=_VALID_BODY, headers={"Authorization": "Bearer evil"}
        )
        assert resp.status_code == 401

    def test_single_condition_is_422(self, tmp_path):
        client = _client(tmp_path, _FakeRuntime())
        resp = client.post(
            _URL,
            json={**_VALID_BODY, "success_conditions": ["only one"]},
            headers=_AUTH,
        )
        assert resp.status_code == 422

    def test_oversized_condition_is_422(self, tmp_path):
        client = _client(tmp_path, _FakeRuntime())
        resp = client.post(
            _URL,
            json={**_VALID_BODY, "success_conditions": ["ok", "x" * 201]},
            headers=_AUTH,
        )
        assert resp.status_code == 422

    def test_trace_mismatch_is_400(self, tmp_path):
        """F-R7: wrong/missing trace_id echo is rejected."""
        client = _client(
            tmp_path, _FakeRuntime(raises=ValueError("trace_id mismatch"))
        )
        resp = client.post(_URL, json=_VALID_BODY, headers=_AUTH)
        assert resp.status_code == 400

    def test_unknown_thread_is_404(self, tmp_path):
        client = _client(tmp_path, _FakeRuntime(raises=KeyError("no checkpoint")))
        resp = client.post(_URL, json=_VALID_BODY, headers=_AUTH)
        assert resp.status_code == 404

    def test_completed_run_is_409(self, tmp_path):
        client = _client(
            tmp_path, _FakeRuntime(raises=RuntimeError("run already completed"))
        )
        resp = client.post(_URL, json=_VALID_BODY, headers=_AUTH)
        assert resp.status_code == 409

    def test_rejected_edit_records_no_parameter_changed(self, tmp_path):
        """No state change → no PARAMETER_CHANGED (the inverse invariant)."""
        _seed_trace(tmp_path)
        client = _client(tmp_path, _FakeRuntime(raises=KeyError("no checkpoint")))
        client.post(_URL, json=_VALID_BODY, headers=_AUTH)
        trace = (
            tmp_path / "black_box_recordings" / "tr-1" / "trace.jsonl"
        ).read_text()
        assert "parameter_changed" not in trace


# ── Acceptance ───────────────────────────────────────────────────────


class TestAcceptedEdit:
    def test_edit_updates_state_and_records_parameter_changed(self, tmp_path):
        """The governance-critical assertion (§4.7): the verdict basis must
        never change unrecorded. The accepted edit lands as PARAMETER_CHANGED
        in the SAME hash-chained trace.jsonl, with old/new hashes,
        reason=user_edit, and the authenticated user_id."""
        _seed_trace(tmp_path)
        runtime = _FakeRuntime()
        client = _client(tmp_path, runtime)

        resp = client.post(_URL, json=_VALID_BODY, headers=_AUTH)
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "user_edited"
        assert body["trace_id"] == "tr-1"

        # The runtime adapter received the edit for the right thread.
        assert runtime.calls == [
            {
                "thread_id": "thread-1",
                "trace_id": "tr-1",
                "restated_intent": "Create the file and verify it.",
                "success_conditions": ["file exists", "contents verified"],
            }
        ]

        trace_file = tmp_path / "black_box_recordings" / "tr-1" / "trace.jsonl"
        events = [json.loads(ln) for ln in trace_file.read_text().splitlines() if ln]
        changed = [e for e in events if e["event_type"] == "parameter_changed"]
        assert len(changed) == 1, (
            "an edit WITHOUT a corresponding PARAMETER_CHANGED event means "
            "the verdict basis changed unrecorded"
        )
        details = changed[0]["details"]
        assert details["parameter"] == "success_conditions"
        assert details["reason"] == "user_edit"
        assert details["user_id"] == "user-workos-1"
        # Compact + tamper-evident: hashes, not content.
        assert len(details["old_hash"]) == 64
        assert len(details["new_hash"]) == 64
        assert details["old_hash"] != details["new_hash"]

        # The chain (started by the "graph") stays valid across the append.
        recorder = BlackBoxRecorder(storage_dir=tmp_path / "black_box_recordings")
        assert recorder.export("tr-1")["hash_chain_valid"] is True
