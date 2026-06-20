"""Phase B: PATCH suppress must emit a MEMORY_SUPPRESSED carrier (C3 trace evidence).

Failure-paths-first: no recordings dir → no carrier (no-op); a successful suppress
emits exactly one carrier with metadata only (never content).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from agent_ui_adapter.server import InMemoryJwtVerifier, JwtClaims, build_app
from services.long_term_memory import InMemoryMemoryBackend, LongTermMemoryService
from trust.models import AgentFacts, Capability

_AGENT_ID = "a1"


def _suppress_events(recordings_dir: Path) -> list[dict]:
    out: list[dict] = []
    for trace_file in recordings_dir.rglob("trace.jsonl"):
        for line in trace_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if ev.get("event_type") == "memory_suppressed":
                out.append(ev)
    return out


def _make_client(tmp_path: Path, *, recordings: bool) -> TestClient:
    memory = LongTermMemoryService(InMemoryMemoryBackend())
    facts = AgentFacts(
        agent_id=_AGENT_ID,
        agent_name="Bot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    app = build_app(
        runtime=object(),
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "good": JwtClaims(
                    subject=_AGENT_ID,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        long_term_memory=memory,
        black_box_recordings_dir=(
            tmp_path / "black_box_recordings" if recordings else None
        ),
    )
    client = TestClient(app)
    return client


class TestSuppressCarrier:
    def test_no_recordings_dir_emits_no_carrier(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path, recordings=False)
        h = {"Authorization": "Bearer good"}
        client.post(
            "/agent/memory",
            json={"type": "semantic", "content": "prefers metric", "key": "k1"},
            headers=h,
        )
        r = client.patch("/agent/memory/k1", json={"suppressed": True}, headers=h)
        assert r.status_code == 204
        assert _suppress_events(tmp_path / "black_box_recordings") == []

    def test_suppress_emits_one_carrier_with_flag(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path, recordings=True)
        h = {"Authorization": "Bearer good"}
        client.post(
            "/agent/memory",
            json={"type": "semantic", "content": "prefers metric units", "key": "k1"},
            headers=h,
        )
        r = client.patch("/agent/memory/k1", json={"suppressed": True}, headers=h)
        assert r.status_code == 204

        events = _suppress_events(tmp_path / "black_box_recordings")
        assert len(events) == 1
        details = events[0]["details"]
        assert details["key"] == "k1"
        assert details["suppressed"] is True
        assert details["user_id"] == "team"
        assert set(details) == {"user_id", "key", "suppressed"}
        blob = json.dumps(events[0])
        assert "prefers metric" not in blob
        assert "units" not in blob

    def test_missing_key_is_404_and_no_carrier(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path, recordings=True)
        r = client.patch(
            "/agent/memory/nope",
            json={"suppressed": True},
            headers={"Authorization": "Bearer good"},
        )
        assert r.status_code == 404
        assert _suppress_events(tmp_path / "black_box_recordings") == []
