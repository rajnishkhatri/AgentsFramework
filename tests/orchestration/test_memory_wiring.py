"""L4 simulation tests for Phase 1 memory wiring (Protocol D).

docs/plans/memory_layer_wiring.plan.md, Verification step 2. Drives the
compiled graph with a mocked LLM and a *spy* MemoryBackend (a real backend
that records calls — no MagicMock on the port, per AP-2). Asserts the
failure-mode matrix (Pattern 11) and the tier coverage (T1/T2/T3) the plan
requires. Failure/rejection rows first (TAP-4). No live LLM.

The load-bearing properties under test:
  - Flag OFF → no search/store, system prompt byte-identical (regression).
  - Flag ON, no user_id → no-op, no carrier, no crash.
  - Backend raises → run completes, warning logged, NO content in logs.
  - Recall memoized once per run (incl. a reflexion reflect→route lap).
  - T3 fan-out is NOT memory-blind; the Send payload carries recalled_memories
    BY VALUE (OBP-M1), never AgentState.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.base_config import AgentConfig, ModelProfile
from services.long_term_memory import (
    InMemoryMemoryBackend,
    LongTermMemoryService,
    MemoryRecord,
)


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _capable_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )


class _SpyBackend:
    """A real MemoryBackend that records calls (no mock on the port — AP-2).

    Wraps InMemoryMemoryBackend; counts search/put so the once-per-run
    memoization and store-once properties are assertable. ``raise_on`` makes
    the named op raise, to drive the graceful-degrade row of the matrix.
    """

    def __init__(self, *, raise_on: set[str] | None = None) -> None:
        self._inner = InMemoryMemoryBackend()
        self.search_calls: list[tuple[str, str, int]] = []
        self.put_calls: list[MemoryRecord] = []
        self._raise_on = raise_on or set()

    def put(self, record: MemoryRecord) -> None:
        self.put_calls.append(record)
        if "put" in self._raise_on:
            raise RuntimeError("boom-put")
        self._inner.put(record)

    def get(self, user_id: str, key: str) -> MemoryRecord | None:
        return self._inner.get(user_id, key)

    def search(self, user_id: str, query: str, limit: int = 10) -> list[MemoryRecord]:
        self.search_calls.append((user_id, query, limit))
        if "search" in self._raise_on:
            raise RuntimeError("boom-search")
        return self._inner.search(user_id, query, limit)

    def delete(self, user_id: str, key: str) -> bool:
        return self._inner.delete(user_id, key)


def _mock_llm_response(content: str = "FINAL ANSWER: metric units.") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = []
    resp.usage_metadata = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}
    resp.response_metadata = {"model_name": "gpt-4o-mini"}
    return resp


def _read_bb_events(cache_dir, workflow_id: str) -> list[dict]:
    trace_file = cache_dir / "black_box_recordings" / workflow_id / "trace.jsonl"
    if not trace_file.exists():
        return []
    return [json.loads(ln) for ln in trace_file.read_text().splitlines() if ln]


async def _run_graph(
    *,
    cache_dir,
    agent_config: AgentConfig,
    memory_service,
    user_id: str = "u-demo",
    task_input: str = "what units do I prefer?",
    workflow_id: str = "wf-mem-001",
    task_id: str = "task-mem-001",
    capture_response: list | None = None,
):
    response = _mock_llm_response()
    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChatLiteLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        mock_llm_instance = MockChatLiteLLM.return_value
        sent_messages: list = []

        async def _ainvoke(messages, *a, **k):
            sent_messages.append(messages)
            return response

        mock_llm_instance.ainvoke = AsyncMock(side_effect=_ainvoke)

        from orchestration.react_loop import build_graph

        graph = build_graph(
            agent_config=agent_config,
            cache_dir=cache_dir / "cache",
            memory_service=memory_service,
        )
        state_in: dict = {
            "task_id": task_id,
            "task_input": task_input,
            "messages": [],
            "workflow_id": workflow_id,
            "registered_agent_id": "agent-test",
        }
        if user_id:
            state_in["user_id"] = user_id
        result = await graph.ainvoke(
            state_in,
            config={
                "configurable": {
                    "task_id": task_id,
                    "user_id": user_id or "anonymous",
                    "workflow_id": workflow_id,
                }
            },
        )
        if capture_response is not None:
            capture_response.extend(sent_messages)
        return result, cache_dir / "cache"


def _cfg(**overrides) -> AgentConfig:
    base = dict(default_model="gpt-4o-mini", models=[_fast_profile(), _capable_profile()])
    base.update(overrides)
    return AgentConfig(**base)


# ── Matrix row: flag OFF → no search/store, prompt unchanged ──────────────


@pytest.mark.asyncio
async def test_flag_off_does_not_touch_memory(tmp_path):
    """Regression guard: memory_enabled=False → no search, no store, no carriers."""
    spy = _SpyBackend()
    service = LongTermMemoryService(spy)
    _result, cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=False),
        memory_service=service,
    )
    assert spy.search_calls == []
    assert spy.put_calls == []
    events = _read_bb_events(cache, "wf-mem-001")
    assert not [e for e in events if e["event_type"].startswith("memory_")]


# ── Matrix row: flag ON, no user_id → no-op, no carrier, no crash ─────────


@pytest.mark.asyncio
async def test_flag_on_without_user_id_is_noop(tmp_path):
    spy = _SpyBackend()
    service = LongTermMemoryService(spy)
    _result, cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=True),
        memory_service=service,
        user_id="",  # no subject → recall/store predicate is False
    )
    assert spy.search_calls == []
    assert spy.put_calls == []
    events = _read_bb_events(cache, "wf-mem-001")
    assert not [e for e in events if e["event_type"].startswith("memory_")]


# ── Matrix row: backend raises → run completes, no content in logs ────────


@pytest.mark.asyncio
async def test_recall_backend_raise_degrades_without_content(tmp_path, caplog):
    spy = _SpyBackend(raise_on={"search"})
    service = LongTermMemoryService(spy)
    with caplog.at_level(logging.WARNING):
        result, cache = await _run_graph(
            cache_dir=tmp_path,
            agent_config=_cfg(memory_enabled=True),
            memory_service=service,
        )
    # Run still completes.
    assert "messages" in result
    # A degraded carrier is still emitted (count 0 / error_kind) — not silent.
    events = _read_bb_events(cache, "wf-mem-001")
    recalled = [e for e in events if e["event_type"] == "memory_recalled"]
    assert recalled, "degraded recall must still leave a carrier (Validation pillar)"
    assert recalled[0]["details"]["count"] == 0
    assert "error_kind" in recalled[0]["details"]
    # Privacy invariant: payload content never reaches a log line.
    joined_logs = " ".join(r.getMessage() for r in caplog.records)
    assert "metric units" not in joined_logs


@pytest.mark.asyncio
async def test_store_backend_raise_degrades_without_content(tmp_path, caplog):
    spy = _SpyBackend(raise_on={"put"})
    service = LongTermMemoryService(spy)
    with caplog.at_level(logging.WARNING):
        result, cache = await _run_graph(
            cache_dir=tmp_path,
            agent_config=_cfg(memory_enabled=True),
            memory_service=service,
        )
    assert "messages" in result
    events = _read_bb_events(cache, "wf-mem-001")
    stored = [e for e in events if e["event_type"] == "memory_stored"]
    assert stored, "degraded store must still leave a carrier"
    assert "error_kind" in stored[0]["details"]
    joined_logs = " ".join(r.getMessage() for r in caplog.records)
    assert "metric units" not in joined_logs


# ── T1 happy path: recall injected, store fires once, carriers present ────


@pytest.mark.asyncio
async def test_t1_recall_injected_and_store_fires(tmp_path):
    spy = _SpyBackend()
    service = LongTermMemoryService(spy)
    # Seed a memory the recall query will match (InMemoryMemoryBackend does a
    # substring search over payload repr).
    service.store("u-demo", "seed", {"text": "prefers metric units"})
    spy.put_calls.clear()  # ignore the seed write in assertions below

    sent: list = []
    result, cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=True),
        memory_service=service,
        task_input="metric",  # substring of the seeded payload
        capture_response=sent,
    )
    # Recall ran and the recalled block reached the system prompt.
    assert len(spy.search_calls) >= 1
    system_texts = [
        m.content
        for batch in sent
        for m in batch
        if getattr(m, "type", "") == "system"
    ]
    assert any("metric units" in t for t in system_texts), (
        "recalled memory must be injected into the system prompt"
    )
    # Store fired exactly once at run-end, keyed on task_id, namespaced to the subject.
    assert len(spy.put_calls) == 1
    assert spy.put_calls[0].user_id == "u-demo"
    assert spy.put_calls[0].key == "task-mem-001"
    # Carriers present, content absent.
    events = _read_bb_events(cache, "wf-mem-001")
    recalled = [e for e in events if e["event_type"] == "memory_recalled"]
    stored = [e for e in events if e["event_type"] == "memory_stored"]
    assert recalled and stored
    assert set(recalled[0]["details"]).issubset(
        {"user_id", "count", "query_len", "error_kind", "keys"}
    )
    assert set(stored[0]["details"]).issubset({"user_id", "key", "error_kind"})


# ── recalled_memories_count surfaced on state (for the UI indicator) ──────


@pytest.mark.asyncio
async def test_recall_count_surfaced_on_state(tmp_path):
    """The route node writes recalled_memories_count (metadata only) so the
    runtime adapter can emit a MemoryRecalled domain event. It equals the
    number of records the search returned."""
    spy = _SpyBackend()
    service = LongTermMemoryService(spy)
    service.store("u-demo", "seed-a", {"text": "prefers metric units"})
    service.store("u-demo", "seed-b", {"text": "uses metric for cooking too"})
    spy.put_calls.clear()

    result, _cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=True),
        memory_service=service,
        task_input="metric",  # substring matches both seeds
    )
    assert result.get("recalled_memories_count") == 2
    # Phase B: the keys of the injected survivors ride alongside the count so
    # the per-chat eval view can list which memories were recalled. Keys are
    # identifiers (the stored keys), never content.
    assert set(result.get("recalled_memories_keys") or []) == {"seed-a", "seed-b"}


@pytest.mark.asyncio
async def test_recall_count_is_zero_when_flag_off(tmp_path):
    """Flag OFF → recall never runs → count stays 0 (indicator renders nothing)."""
    spy = _SpyBackend()
    service = LongTermMemoryService(spy)
    service.store("u-demo", "seed", {"text": "prefers metric units"})
    spy.put_calls.clear()
    result, _cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=False),
        memory_service=service,
        task_input="metric",
    )
    assert int(result.get("recalled_memories_count", 0) or 0) == 0
    # Phase B: flag off → no keys either (eval view shows nothing).
    assert list(result.get("recalled_memories_keys") or []) == []


@pytest.mark.asyncio
async def test_recall_count_zero_on_degraded_backend(tmp_path):
    """Backend raises → degraded recall → count 0 (matches the carrier)."""
    spy = _SpyBackend(raise_on={"search"})
    service = LongTermMemoryService(spy)
    result, _cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=True),
        memory_service=service,
        task_input="metric",
    )
    assert int(result.get("recalled_memories_count", 0) or 0) == 0
    # Phase B: degraded recall must NOT surface stale keys — [] matches count 0.
    assert list(result.get("recalled_memories_keys") or []) == []


# ── T2 correctness: recall memoized once per run across a reflexion lap ────


@pytest.mark.asyncio
async def test_t2_recall_memoized_once_across_reflexion_lap(tmp_path):
    """Reflexion reflect→route re-entry keeps task_id → exactly one search."""
    spy = _SpyBackend()
    service = LongTermMemoryService(spy)
    service.store("u-demo", "seed", {"text": "prefers metric units"})
    spy.put_calls.clear()

    # reflexion_enabled forces evaluate→reflect→route laps possible; the LLM mock
    # returns a final answer so the loop still terminates, but route_node may be
    # re-entered. The memoize guard must keep search at exactly one call.
    _result, _cache = await _run_graph(
        cache_dir=tmp_path,
        agent_config=_cfg(memory_enabled=True, reflexion_enabled=True),
        memory_service=service,
        task_input="metric",
    )
    assert len(spy.search_calls) == 1, (
        f"recall must query once per run, got {len(spy.search_calls)} "
        "(reflexion re-entry must reuse the memoized block)"
    )


# ── T3 fan-out (OBP-M1) ───────────────────────────────────────────────────
#
# The end-to-end T3 propagation — recall reaches the supervisor decompose
# prompt on a fan-out run (not memory-blind), recall queries once per run, and
# recalled_memories rides the Send payload BY VALUE — is covered by the
# @pytest.mark.simulation test test_fanout_is_not_memory_blind in
# tests/orchestration/test_tier_topology_sim.py, which reuses that file's
# fan-out harness (supervisor decompose + branch dispatch patch). Kept there to
# share the harness rather than duplicate it here.
