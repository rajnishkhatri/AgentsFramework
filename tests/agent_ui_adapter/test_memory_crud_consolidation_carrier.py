"""P1 #6a: the CRUD ``create_memory`` route must leave a MEMORY_CONSOLIDATED
carrier when a panel write overflows the budget — a silent prune is the
swallowed-failure the Validation pillar forbids (live smoke found 0 carriers
despite a forced overflow). See docs/research/memory/hermes_adoptions_design.md
§10.5.

Failure-paths-first: the silent-eviction regression (no carrier on overflow) is
asserted before the under-budget no-op. End-to-end through the real adapter
route + a real LongTermMemoryService (InMemory backend); the carrier is read back
off disk so we assert the actual recorded event, not a mock.
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


def _carrier_events(recordings_dir: Path) -> list[dict]:
    """Every MEMORY_CONSOLIDATED event recorded under any workflow dir."""
    out: list[dict] = []
    for trace_file in recordings_dir.rglob("trace.jsonl"):
        for line in trace_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if ev.get("event_type") == "memory_consolidated":
                out.append(ev)
    return out


def _make_client(tmp_path: Path, *, budget: int) -> TestClient:
    backend = InMemoryMemoryBackend()
    memory = LongTermMemoryService(backend, budgets={"semantic": budget})
    facts = AgentFacts(
        agent_id=_AGENT_ID,
        agent_name="Bot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    app = build_app(
        runtime=object(),  # unused by the memory CRUD routes
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
        black_box_recordings_dir=tmp_path / "black_box_recordings",
    )
    return TestClient(app)


def _add(client: TestClient, content: str) -> None:
    r = client.post(
        "/agent/memory",
        json={"type": "semantic", "content": content},
        headers={"Authorization": "Bearer good"},
    )
    assert r.status_code == 200, r.text


class TestCrudConsolidationCarrier:
    def test_overflow_write_emits_consolidated_carrier(self, tmp_path: Path) -> None:
        """Budget=2; the 3rd distinct semantic write overflows -> the route must
        record a MEMORY_CONSOLIDATED carrier (counts only, never content)."""
        client = _make_client(tmp_path, budget=2)
        recordings = tmp_path / "black_box_recordings"

        _add(client, "I prefer metric units")
        _add(client, "I live in Denver")
        assert _carrier_events(recordings) == []  # still at/under budget

        _add(client, "My favorite color is teal")  # 3rd -> overflow

        events = _carrier_events(recordings)
        assert len(events) == 1, "an overflowing CRUD write must leave a carrier"
        details = events[0]["details"]
        assert details["type"] == "semantic"
        assert details["evicted"] >= 1
        # Privacy: counts only — no memory content smuggled into the carrier.
        assert set(details) == {"user_id", "type", "kept", "evicted", "deduped"}
        blob = json.dumps(events[0])
        for secret in ("metric", "Denver", "teal"):
            assert secret not in blob

    def test_under_budget_writes_emit_no_carrier(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path, budget=10)
        recordings = tmp_path / "black_box_recordings"
        _add(client, "fact one")
        _add(client, "fact two")
        assert _carrier_events(recordings) == []
