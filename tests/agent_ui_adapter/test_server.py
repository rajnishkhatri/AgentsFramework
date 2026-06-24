"""US-6.1, US-6.3: FastAPI app + routes + composition root tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent_ui_adapter.adapters.runtime.mock_runtime import MockRuntime
from agent_ui_adapter.server import (
    InMemoryJwtVerifier,
    JwtClaims,
    build_app,
)
from agent_ui_adapter.wire.domain_events import (
    LLMTokenEmitted,
    RunFinishedDomain,
    RunStartedDomain,
)
from services.authorization_service import AuthorizationService, EmbeddedPolicyBackend
from services.trace_service import InMemoryTraceSink, TraceService
from trust.models import AgentFacts, Capability


def _good_token(client: TestClient) -> dict:
    return {"Authorization": "Bearer good"}


def _make_app_with_runtime(runtime, agent_id: str = "a1", *, trace_sink=None):
    facts = AgentFacts(
        agent_id=agent_id,
        agent_name="Bot",
        owner="team",
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    sink = trace_sink or InMemoryTraceSink()
    trace_svc = TraceService(sinks=[sink])
    return build_app(
        runtime=runtime,
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "good": JwtClaims(
                    subject=agent_id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        authorization_service=AuthorizationService(
            embedded_backend=EmbeddedPolicyBackend(),
            trace_emit=trace_svc.emit,
        ),
        trace_service=trace_svc,
    )


# ── Routes ────────────────────────────────────────────────────────────


class TestRoutes:
    def test_healthz_returns_ok(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "adapter_version" in body

    def test_get_unknown_run_returns_404(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.get(
            "/agent/runs/does-not-exist", headers=_good_token(client)
        )
        assert r.status_code == 404

    def test_post_threads_creates_thread(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.post(
            "/agent/threads",
            json={"user_id": "u1", "metadata": {}},
            headers=_good_token(client),
        )
        assert r.status_code == 200
        assert r.json()["user_id"] == "u1"
        assert r.json()["thread_id"]

    def test_runs_stream_returns_sse_response(self) -> None:
        runtime = MockRuntime(
            events=[
                RunStartedDomain(trace_id="trace-1", run_id="r1", thread_id="t1"),
                LLMTokenEmitted(trace_id="trace-1", message_id="m1", delta="hi"),
                RunFinishedDomain(trace_id="trace-1", run_id="r1", thread_id="t1"),
            ]
        )
        client = TestClient(_make_app_with_runtime(runtime))
        with client.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(client),
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            assert r.headers.get("x-accel-buffering") == "no"
            body = b"".join(r.iter_bytes())
        assert b"event: RUN_STARTED" in body
        assert b"event: TEXT_MESSAGE_CONTENT" in body
        assert b"event: RUN_FINISHED" in body
        assert b"event: done" in body
        assert b"[DONE]" in body


# ── Chat-history sidebar endpoints (Phase 3) ──────────────────────────


class TestThreadSidebarEndpoints:
    # ── failure paths first (TAP-4) ──

    def test_list_requires_bearer(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        assert client.get("/agent/threads").status_code == 401

    def test_rename_requires_bearer(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.patch("/agent/threads/x", json={"title": "y"})
        assert r.status_code == 401

    def test_rename_rejects_empty_title(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        # Create one to target.
        created = client.post(
            "/agent/threads",
            json={"user_id": "team", "metadata": {}},
            headers=_good_token(client),
        ).json()
        r = client.patch(
            f"/agent/threads/{created['thread_id']}",
            json={"title": ""},
            headers=_good_token(client),
        )
        assert r.status_code == 422

    def test_rename_unknown_thread_404(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.patch(
            "/agent/threads/nope",
            json={"title": "x"},
            headers=_good_token(client),
        )
        assert r.status_code == 404

    # ── acceptance ──

    def test_create_sets_title_from_metadata_first_message(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        created = client.post(
            "/agent/threads",
            json={
                "user_id": "team",
                "metadata": {"first_message": "Plan my trip to Rome"},
            },
            headers=_good_token(client),
        ).json()
        assert created["title"] == "Plan my trip to Rome"

    def test_create_defaults_title_when_no_first_message(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        created = client.post(
            "/agent/threads",
            json={"user_id": "team", "metadata": {}},
            headers=_good_token(client),
        ).json()
        assert created["title"] == "New chat"

    def test_create_honors_client_supplied_thread_id(self) -> None:
        # The client mints the id (== the agent/checkpointer thread_id) so the
        # durable row keys by the same id the resume path reads.
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        created = client.post(
            "/agent/threads",
            json={"user_id": "team", "thread_id": "client-mint-1"},
            headers=_good_token(client),
        ).json()
        assert created["thread_id"] == "client-mint-1"

    def test_create_mints_thread_id_when_absent(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        created = client.post(
            "/agent/threads",
            json={"user_id": "team", "metadata": {}},
            headers=_good_token(client),
        ).json()
        assert created["thread_id"]  # non-empty server-minted id

    def test_list_returns_only_callers_own_newest_first(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        for i in range(3):
            client.post(
                "/agent/threads",
                json={"user_id": "team", "metadata": {"first_message": f"t{i}"}},
                headers=_good_token(client),
            )
        listed = client.get("/agent/threads", headers=_good_token(client)).json()
        assert len(listed["threads"]) == 3
        # newest first
        titles = [t["title"] for t in listed["threads"]]
        assert titles == ["t2", "t1", "t0"]

    def test_rename_updates_title(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        created = client.post(
            "/agent/threads",
            json={"user_id": "team", "metadata": {}},
            headers=_good_token(client),
        ).json()
        renamed = client.patch(
            f"/agent/threads/{created['thread_id']}",
            json={"title": "Renamed thread"},
            headers=_good_token(client),
        )
        assert renamed.status_code == 200
        assert renamed.json()["title"] == "Renamed thread"

    def test_archive_hides_from_list(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        created = client.post(
            "/agent/threads",
            json={"user_id": "team", "metadata": {"first_message": "doomed"}},
            headers=_good_token(client),
        ).json()
        r = client.delete(
            f"/agent/threads/{created['thread_id']}",
            headers=_good_token(client),
        )
        assert r.status_code == 200
        listed = client.get("/agent/threads", headers=_good_token(client)).json()
        assert created["thread_id"] not in [t["thread_id"] for t in listed["threads"]]


# ── Memory panel endpoints (Phase 3) ──────────────────────────────────


def _make_app_with_memory(*, agent_id: str = "a1", owner: str = "team"):
    """App wired with a real in-memory LongTermMemoryService for the panel."""
    from agent_ui_adapter.server import build_app
    from services.long_term_memory import (
        InMemoryMemoryBackend,
        LongTermMemoryService,
    )

    facts = AgentFacts(
        agent_id=agent_id,
        agent_name="Bot",
        owner=owner,
        version="1.0.0",
        capabilities=[Capability(name="agent.session.start")],
    )
    memory = LongTermMemoryService(InMemoryMemoryBackend())
    app = build_app(
        runtime=MockRuntime(events=[]),
        jwt_verifier=InMemoryJwtVerifier(
            token_to_claims={
                "good": JwtClaims(
                    subject=agent_id,
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            }
        ),
        agent_facts={facts.agent_id: facts},
        long_term_memory=memory,
    )
    return app, memory


class TestMemoryEndpoints:
    # ── failure paths first (TAP-4) ──

    def test_list_requires_bearer(self) -> None:
        app, _ = _make_app_with_memory()
        r = TestClient(app).get("/agent/memory")
        assert r.status_code == 401

    def test_create_requires_bearer(self) -> None:
        app, _ = _make_app_with_memory()
        r = TestClient(app).post("/agent/memory", json={"content": "x"})
        assert r.status_code == 401

    def test_list_returns_503_when_memory_not_wired(self) -> None:
        # No long_term_memory injected → the panel is unavailable, not a 500.
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        r = client.get("/agent/memory", headers=_good_token(client))
        assert r.status_code == 503

    def test_create_rejects_empty_content(self) -> None:
        app, _ = _make_app_with_memory()
        r = TestClient(app).post(
            "/agent/memory", json={"content": ""}, headers={"Authorization": "Bearer good"}
        )
        assert r.status_code == 422

    def test_create_rejects_client_supplied_user_id(self) -> None:
        # Cross-user-leak guard: user_id is never client-supplied (extra=forbid).
        app, _ = _make_app_with_memory()
        r = TestClient(app).post(
            "/agent/memory",
            json={"content": "x", "user_id": "victim"},
            headers={"Authorization": "Bearer good"},
        )
        assert r.status_code == 422

    # ── acceptance ──

    def test_create_then_list_round_trips_for_owner(self) -> None:
        app, _ = _make_app_with_memory(owner="team")
        client = TestClient(app)
        h = {"Authorization": "Bearer good"}
        created = client.post(
            "/agent/memory",
            json={"content": "prefers metric units", "type": "semantic"},
            headers=h,
        )
        assert created.status_code == 200
        listed = client.get("/agent/memory", headers=h)
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert any(i["content"] == "prefers metric units" for i in items)
        assert all(i["type"] in ("semantic", "episodic", "procedural", None) for i in items)

    def test_list_only_returns_callers_own_memory(self) -> None:
        # Seed another user's memory directly; the caller (owner="team") must
        # not see it.
        app, memory = _make_app_with_memory(owner="team")
        memory.store("someone-else", "k", {"text": "secret"}, metadata={"type": "semantic"})
        client = TestClient(app)
        listed = client.get("/agent/memory", headers={"Authorization": "Bearer good"})
        contents = [i["content"] for i in listed.json()["items"]]
        assert "secret" not in contents

    def test_delete_removes_own_item(self) -> None:
        app, _ = _make_app_with_memory(owner="team")
        client = TestClient(app)
        h = {"Authorization": "Bearer good"}
        client.post(
            "/agent/memory",
            json={"content": "temp fact", "type": "semantic", "key": "k-del"},
            headers=h,
        )
        r = client.delete("/agent/memory/k-del", headers=h)
        assert r.status_code == 200
        listed = client.get("/agent/memory", headers=h)
        assert "k-del" not in [i["key"] for i in listed.json()["items"]]

    def test_delete_requires_bearer(self) -> None:
        app, _ = _make_app_with_memory()
        r = TestClient(app).delete("/agent/memory/k")
        assert r.status_code == 401

    # ── Phase B: soft-suppress (PATCH) ──

    def test_suppress_requires_bearer(self) -> None:
        app, _ = _make_app_with_memory()
        r = TestClient(app).patch("/agent/memory/k", json={"suppressed": True})
        assert r.status_code == 401

    def test_suppress_missing_key_is_404(self) -> None:
        app, _ = _make_app_with_memory(owner="team")
        r = TestClient(app).patch(
            "/agent/memory/nope",
            json={"suppressed": True},
            headers={"Authorization": "Bearer good"},
        )
        assert r.status_code == 404

    def test_suppress_rejects_bad_body(self) -> None:
        app, _ = _make_app_with_memory(owner="team")
        r = TestClient(app).patch(
            "/agent/memory/k",
            json={"nope": True},  # missing required 'suppressed'
            headers={"Authorization": "Bearer good"},
        )
        assert r.status_code == 422

    def test_suppress_flags_record_and_excludes_from_recall(self) -> None:
        app, memory = _make_app_with_memory(owner="team")
        client = TestClient(app)
        h = {"Authorization": "Bearer good"}
        client.post(
            "/agent/memory",
            json={"content": "prefers metric", "type": "semantic", "key": "k-sup"},
            headers=h,
        )
        r = client.patch("/agent/memory/k-sup", json={"suppressed": True}, headers=h)
        assert r.status_code == 204
        # The row is retained (still listed for un-suppress) …
        listed = client.get("/agent/memory", headers=h).json()["items"]
        assert "k-sup" in [i["key"] for i in listed]
        # … but recall (search) no longer injects it: the survivor filter drops it.
        from components.memory_context import filter_recall_records

        recs = memory.search("team", "metric", 10)
        assert "k-sup" not in [r.key for r in filter_recall_records(recs)]

    def test_un_suppress_restores_recall(self) -> None:
        app, memory = _make_app_with_memory(owner="team")
        client = TestClient(app)
        h = {"Authorization": "Bearer good"}
        client.post(
            "/agent/memory",
            json={"content": "prefers metric", "type": "semantic", "key": "k-sup"},
            headers=h,
        )
        client.patch("/agent/memory/k-sup", json={"suppressed": True}, headers=h)
        r = client.patch("/agent/memory/k-sup", json={"suppressed": False}, headers=h)
        assert r.status_code == 204
        from components.memory_context import filter_recall_records

        recs = memory.search("team", "metric", 10)
        assert "k-sup" in [r.key for r in filter_recall_records(recs)]


# ── Composition root: DI swappability ─────────────────────────────────


class TestCompositionRoot:
    def test_build_app_uses_supplied_runtime(self) -> None:
        # Two different runtimes produce two different streams.
        rt1 = MockRuntime(
            events=[
                RunStartedDomain(trace_id="t", run_id="r1", thread_id="t1"),
                RunFinishedDomain(trace_id="t", run_id="r1", thread_id="t1"),
            ]
        )
        rt2 = MockRuntime(
            events=[
                RunStartedDomain(trace_id="t", run_id="r2", thread_id="t1"),
                LLMTokenEmitted(trace_id="t", message_id="m", delta="x"),
                RunFinishedDomain(trace_id="t", run_id="r2", thread_id="t1"),
            ]
        )
        c1 = TestClient(_make_app_with_runtime(rt1))
        c2 = TestClient(_make_app_with_runtime(rt2))
        with c1.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(c1),
        ) as r:
            b1 = b"".join(r.iter_bytes())
        with c2.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(c2),
        ) as r:
            b2 = b"".join(r.iter_bytes())
        # rt1 has 2 events; rt2 has 3. The token output proves they differ.
        assert b"TEXT_MESSAGE_CONTENT" not in b1
        assert b"TEXT_MESSAGE_CONTENT" in b2

    def test_build_app_returns_a_fastapi_app(self) -> None:
        from fastapi import FastAPI

        app = _make_app_with_runtime(MockRuntime(events=[]))
        assert isinstance(app, FastAPI)

    def test_cancel_run_routes_through_runtime(self) -> None:
        runtime = MockRuntime(
            events=[
                RunStartedDomain(trace_id="t", run_id="r1", thread_id="t1"),
                RunFinishedDomain(trace_id="t", run_id="r1", thread_id="t1"),
            ]
        )
        client = TestClient(_make_app_with_runtime(runtime))
        with client.stream(
            "POST",
            "/agent/runs/stream",
            json={"thread_id": "t1", "input": {}},
            headers=_good_token(client),
        ) as r:
            body = b"".join(r.iter_bytes())
        run_id = "r1"
        r2 = client.delete(
            f"/agent/runs/{run_id}", headers=_good_token(client)
        )
        assert r2.status_code == 200
        assert run_id in runtime.cancelled_runs


class TestModelsEndpoint:
    """GET /models — the model picker's catalog (auth-scoped, name+tier only)."""

    # ── Rejection first: must require a bearer (auth-scoped like /api/*) ──
    def test_requires_bearer(self) -> None:
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        assert client.get("/models").status_code == 401

    # ── Never leak pricing / litellm internals to the client ─────────────
    def test_omits_pricing_and_litellm_id(self, monkeypatch) -> None:
        monkeypatch.delenv("MODEL_PROFILE_SET", raising=False)
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        body = client.get("/models", headers=_good_token(client)).json()
        for m in body["models"]:
            assert set(m.keys()) == {"name", "tier"}
            assert "cost_per_1k_input" not in m
            assert "litellm_id" not in m

    # ── Default (openai) set shape ───────────────────────────────────────
    def test_default_set_lists_openai_catalog(self, monkeypatch) -> None:
        monkeypatch.delenv("MODEL_PROFILE_SET", raising=False)
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        body = client.get("/models", headers=_good_token(client)).json()
        assert body["default"] == "gpt-4o-mini"
        names = [m["name"] for m in body["models"]]
        assert names[0] == "gpt-4o-mini"  # first fast (registry order)
        assert "Auto" not in names  # Auto is a UI sentinel, never listed

    # ── Anthropic set tracks MODEL_PROFILE_SET ───────────────────────────
    def test_anthropic_set_lists_three_tier_stack(self, monkeypatch) -> None:
        monkeypatch.setenv("MODEL_PROFILE_SET", "anthropic")
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        body = client.get("/models", headers=_good_token(client)).json()
        assert body["default"] == "claude-haiku-4-5"
        names = [m["name"] for m in body["models"]]
        assert "claude-opus-4-8" in names
        # first-match per tier is the safety contract
        first_fast = next(m for m in body["models"] if m["tier"] == "fast")
        assert first_fast["name"] == "claude-haiku-4-5"

    # ── DeepSeek set tracks MODEL_PROFILE_SET (Flash fast+capable / Pro) ──
    def test_deepseek_set_lists_flash_and_pro(self, monkeypatch) -> None:
        monkeypatch.setenv("MODEL_PROFILE_SET", "deepseek")
        client = TestClient(_make_app_with_runtime(MockRuntime(events=[])))
        body = client.get("/models", headers=_good_token(client)).json()
        assert body["default"] == "deepseek-v4-flash"
        names = [m["name"] for m in body["models"]]
        # Both Flash names (fast + capable) AND Pro are listed; no pricing leak.
        assert "deepseek-v4-flash" in names
        assert "deepseek-v4-flash-capable" in names
        assert "deepseek-v4-pro" in names
        for m in body["models"]:
            assert set(m.keys()) == {"name", "tier"}
        first_fast = next(m for m in body["models"] if m["tier"] == "fast")
        assert first_fast["name"] == "deepseek-v4-flash"
        first_reasoning = next(
            m for m in body["models"] if m["tier"] == "reasoning"
        )
        assert first_reasoning["name"] == "deepseek-v4-pro"
