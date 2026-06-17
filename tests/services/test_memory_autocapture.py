"""L2 Reproducible: services/memory_autocapture.py (Phase 2 background seam).

Contract-driven TDD per Protocol B. Failure paths first (TAP-4).

The autocapture service is the post-run background seam: it runs the typed
extractor over a thread's window, emits one carrier per PROPOSED item (never
content), and — only when write-back is enabled — stores them. In shadow mode
(``MEMORY_AUTOCAPTURE_ENABLED`` OFF, the default) it proposes-only: the trace
carries the proposal but NOTHING is written. Write-back flips ONLY after the
grounded-theory enable-policy clears.

Debounce is per thread: a burst of completions for one thread coalesces into a
single extraction (bounds LLM cost). The scheduling is exercised separately
from the capture policy so the policy stays deterministic.
"""

from __future__ import annotations

import asyncio

import pytest

from components.schemas import TypedMemory
from services.governance.black_box import BlackBoxRecorder, EventType
from services.memory_autocapture import CaptureOutcome, MemoryAutoCaptureService

# ─────────────────────────────────────────────────────────────────────
# Fakes (Pattern 6 / 4 — ≤3 mocks)
# ─────────────────────────────────────────────────────────────────────


class _Result:
    def __init__(self, memories, *, tokens_in=0, tokens_out=0, cost=0.0):
        self.memories = memories
        self.model = "gpt-4o-mini"
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost
        self.latency_ms = 1.0


class FakeExtractor:
    def __init__(self, *, memories=None, raises=None):
        self._memories = memories or []
        self._raises = raises
        self.calls = []

    async def extract(self, *, messages, existing_profile=None):
        self.calls.append((messages, existing_profile))
        if self._raises is not None:
            raise self._raises
        return _Result(list(self._memories))


class SpyMemoryService:
    def __init__(self, *, store_raises=None):
        self.stored = []
        self._store_raises = store_raises

    def search(self, user_id, query, limit=10, *, mem_type=None):
        return []

    def store(self, user_id, key, payload, metadata=None):
        if self._store_raises is not None:
            raise self._store_raises
        self.stored.append((user_id, key, payload, metadata))


def _item(type_="semantic", content="prefers metric units", key="profile", sal=0.9):
    return TypedMemory(type=type_, content=content, key=key, salience=sal)


def _service(extractor, mem, *, write_back=False):
    return MemoryAutoCaptureService(
        extractor=extractor,  # type: ignore[arg-type]
        memory_service=mem,  # type: ignore[arg-type]
        write_back_enabled=write_back,
    )


def _recorder(tmp_path):
    return BlackBoxRecorder(tmp_path / "bb")


_MESSAGES = [{"role": "user", "content": "I want metric units."}]


def _carrier_count(recorder, wf, event_type):
    trace = recorder.export(wf)
    return sum(1 for e in trace["events"] if e["event_type"] == event_type.value)


# ─────────────────────────────────────────────────────────────────────
# Failure / shadow paths (FIRST — TAP-4)
# ─────────────────────────────────────────────────────────────────────


class TestCaptureShadowAndFailures:
    async def test_no_user_id_is_noop(self, tmp_path):
        ex = FakeExtractor(memories=[_item()])
        mem = SpyMemoryService()
        svc = _service(ex, mem, write_back=True)
        outcome = await svc.capture(
            thread_id="t",
            user_id="",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=_recorder(tmp_path),
        )
        assert outcome.proposed == 0
        assert ex.calls == []  # no extraction without a subject
        assert mem.stored == []

    async def test_anonymous_user_is_noop(self, tmp_path):
        # Cross-user-leak guard: "anonymous"/blank must not be a subject.
        ex = FakeExtractor(memories=[_item()])
        mem = SpyMemoryService()
        svc = _service(ex, mem, write_back=True)
        outcome = await svc.capture(
            thread_id="t",
            user_id="anonymous",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=_recorder(tmp_path),
        )
        assert outcome.proposed == 0
        assert mem.stored == []

    async def test_shadow_proposes_but_does_not_store(self, tmp_path):
        # The load-bearing Phase-2 guarantee: write_back OFF → proposal carrier
        # present, NOTHING written.
        ex = FakeExtractor(memories=[_item(), _item(type_="episodic", key="e1")])
        mem = SpyMemoryService()
        rec = _recorder(tmp_path)
        svc = _service(ex, mem, write_back=False)
        outcome = await svc.capture(
            thread_id="t",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=rec,
        )
        assert outcome.proposed == 2
        assert outcome.stored == 0
        assert mem.stored == []  # SHADOW: nothing written
        # One carrier per proposed item.
        assert _carrier_count(rec, "wf1", EventType.MEMORY_STORED) == 2

    async def test_extractor_error_degrades_no_carrier_no_crash(self, tmp_path):
        ex = FakeExtractor(raises=RuntimeError("llm down"))
        mem = SpyMemoryService()
        rec = _recorder(tmp_path)
        svc = _service(ex, mem, write_back=True)
        outcome = await svc.capture(
            thread_id="t",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=rec,
        )
        assert outcome.proposed == 0
        assert outcome.stored == 0
        assert mem.stored == []

    async def test_store_error_degrades_run_continues(self, tmp_path):
        ex = FakeExtractor(memories=[_item()])
        mem = SpyMemoryService(store_raises=RuntimeError("backend down"))
        rec = _recorder(tmp_path)
        svc = _service(ex, mem, write_back=True)
        outcome = await svc.capture(
            thread_id="t",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=rec,
        )
        assert outcome.proposed == 1
        assert outcome.stored == 0  # store failed, but no crash
        # Carrier still emitted (degraded), so the failure is not silent.
        assert _carrier_count(rec, "wf1", EventType.MEMORY_STORED) == 1

    async def test_carrier_never_contains_content(self, tmp_path):
        ex = FakeExtractor(memories=[_item(content="SECRET-FACT-XYZ")])
        mem = SpyMemoryService()
        rec = _recorder(tmp_path)
        svc = _service(ex, mem, write_back=True)
        await svc.capture(
            thread_id="t",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=rec,
        )
        trace_json = str(rec.export("wf1"))
        assert "SECRET-FACT-XYZ" not in trace_json


# ─────────────────────────────────────────────────────────────────────
# Write-back acceptance (gated; tested so the path is correct when enabled)
# ─────────────────────────────────────────────────────────────────────


class TestCaptureWriteBack:
    async def test_write_back_stores_each_item_with_type_metadata(self, tmp_path):
        ex = FakeExtractor(
            memories=[_item(key="profile"), _item(type_="episodic", key="e1")]
        )
        mem = SpyMemoryService()
        rec = _recorder(tmp_path)
        svc = _service(ex, mem, write_back=True)
        outcome = await svc.capture(
            thread_id="t",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=rec,
        )
        assert outcome.stored == 2
        assert len(mem.stored) == 2
        # type rides in metadata so recall's type filter can find it.
        types = {md.get("type") for (_u, _k, _p, md) in mem.stored}
        assert types == {"semantic", "episodic"}
        # every write uses the run's subject — cross-user-leak guard.
        assert {u for (u, *_rest) in mem.stored} == {"alice"}

    async def test_empty_proposal_stores_nothing(self, tmp_path):
        ex = FakeExtractor(memories=[])
        mem = SpyMemoryService()
        svc = _service(ex, mem, write_back=True)
        outcome = await svc.capture(
            thread_id="t",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wf1",
            task_id="task1",
            black_box=_recorder(tmp_path),
        )
        assert outcome.proposed == 0
        assert mem.stored == []


# ─────────────────────────────────────────────────────────────────────
# Per-thread debounce (coalesce a burst into one extraction)
# ─────────────────────────────────────────────────────────────────────


class TestDebounce:
    async def test_burst_for_one_thread_coalesces_to_one_extraction(self, tmp_path):
        ex = FakeExtractor(memories=[_item()])
        mem = SpyMemoryService()
        rec = _recorder(tmp_path)
        svc = MemoryAutoCaptureService(
            extractor=ex,  # type: ignore[arg-type]
            memory_service=mem,  # type: ignore[arg-type]
            write_back_enabled=False,
            debounce_seconds=0.05,
        )
        # Fire three completions for the same thread in quick succession.
        for i in range(3):
            svc.schedule(
                thread_id="t",
                user_id="alice",
                messages=_MESSAGES,
                workflow_id=f"wf{i}",
                task_id=f"task{i}",
                black_box=rec,
            )
        await svc.drain()
        # Debounced: only the last burst entry actually extracts.
        assert len(ex.calls) == 1

    async def test_distinct_threads_each_extract(self, tmp_path):
        ex = FakeExtractor(memories=[_item()])
        mem = SpyMemoryService()
        rec = _recorder(tmp_path)
        svc = MemoryAutoCaptureService(
            extractor=ex,  # type: ignore[arg-type]
            memory_service=mem,  # type: ignore[arg-type]
            write_back_enabled=False,
            debounce_seconds=0.05,
        )
        svc.schedule(
            thread_id="t1",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wfa",
            task_id="ta",
            black_box=rec,
        )
        svc.schedule(
            thread_id="t2",
            user_id="alice",
            messages=_MESSAGES,
            workflow_id="wfb",
            task_id="tb",
            black_box=rec,
        )
        await svc.drain()
        assert len(ex.calls) == 2
