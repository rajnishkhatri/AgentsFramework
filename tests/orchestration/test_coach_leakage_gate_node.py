"""L2 tests for the inline coach-leakage gate helper (Phase 5, T5/T6/T7).

Exercises the ``_run_coach_leakage_gate`` orchestration helper with a stub judge,
a stub regenerate callable, and an in-memory BlackBox recorder — NO live LLM
(FR-11), NO full graph build (TAP-2: real in-memory recorder, one stub per
external boundary). Failure paths first (FR-1 outage, FR-3 suppress).
"""

from __future__ import annotations

import pytest

from orchestration.react_loop import _run_coach_leakage_gate
from services.governance.black_box import BlackBoxRecorder


class _Judge:
    def __init__(self, verdicts):
        # verdicts: list of answer_leakage values (None => unavailable/raise-free)
        self._verdicts = list(verdicts)
        self.calls = 0

    async def evaluate(self, *, learner_utterance, coach_reply, mode, question=""):
        self.calls += 1
        val = self._verdicts.pop(0)

        class _V:
            answer_leakage = val

        return _V()


class _RaisingJudge:
    def __init__(self):
        self.calls = 0

    async def evaluate(self, **kw):
        self.calls += 1
        raise RuntimeError("judge down")


@pytest.fixture
def _bb(tmp_path):
    return BlackBoxRecorder(storage_dir=tmp_path / "bb")


def _gate_carriers(bb):
    return [
        e for e in bb.replay("wf") if e.details.get("guardrail") == "coach_leakage_gate"
    ]


async def _run(bb, **kw):
    defaults = dict(
        content="the answer is 42",
        mode="enforce",
        learner_utterance="lu",
        question="q",
        workflow_id="wf",
        step=1,
        trace_id="tid-1",
        fallback="Let's work through it — what have you tried?",
    )
    defaults.update(kw)
    out = await _run_coach_leakage_gate(black_box=bb, **defaults)
    return out, bb


# ── FR-1: judge outage in enforce → fail OPEN (reply passes) + loud carrier ──


@pytest.mark.asyncio
async def test_enforce_judge_outage_fails_open(_bb) -> None:
    out, bb = await _run(_bb, judge=_RaisingJudge(), regenerate=_fail_regen)
    assert out == "the answer is 42"  # original reply passes through
    carriers = _gate_carriers(bb)
    assert len(carriers) == 1
    assert carriers[0].details["action"] == "fail_open"
    assert carriers[0].details["verdict"] == "unavailable"


# ── FR-3: enforce + leak, regen STILL leaks → suppress to fallback ──


@pytest.mark.asyncio
async def test_enforce_leak_then_regen_still_leaks_suppresses(_bb) -> None:
    judge = _Judge([True, True])  # original leaks, regen leaks
    out, bb = await _run(_bb, judge=judge, regenerate=_leak_regen)
    assert out == "Let's work through it — what have you tried?"  # fallback
    assert "42" not in out  # the leaking text is never emitted
    assert judge.calls == 2  # judged original + regen
    c = _gate_carriers(bb)[0]
    assert c.details["action"] == "suppress"


# ── FR-7: enforce + leak, regen CLEARS → emit regenerated reply ──


@pytest.mark.asyncio
async def test_enforce_leak_then_regen_clears_emits_regenerated(_bb) -> None:
    judge = _Judge([True, False])  # original leaks, regen clean
    out, bb = await _run(_bb, judge=judge, regenerate=_clean_regen)
    assert out == "Consider what the units tell you."  # the regenerated reply
    assert judge.calls == 2
    c = _gate_carriers(bb)[0]
    assert c.details["action"] == "regenerate"


# ── FR-5-ish: enforce + clean → reply unchanged, one carrier, no regen ──


@pytest.mark.asyncio
async def test_enforce_clean_passes_unchanged(_bb) -> None:
    judge = _Judge([False])
    out, bb = await _run(_bb, judge=judge, regenerate=_fail_regen, content="nice hint")
    assert out == "nice hint"
    assert judge.calls == 1
    assert _gate_carriers(bb)[0].details["action"] == "allow"


# ── FR-6: shadow → judged + carrier, reply ALWAYS unchanged, never regens ──


@pytest.mark.asyncio
async def test_shadow_records_but_never_alters(_bb) -> None:
    judge = _Judge([True])  # would be a leak, but shadow must not act
    out, bb = await _run(
        _bb,
        judge=judge,
        regenerate=_fail_regen,
        mode="shadow",
        content="the answer is 42",
    )
    assert out == "the answer is 42"  # unchanged
    c = _gate_carriers(bb)[0]
    assert c.details["action"] == "shadow_record"
    assert c.details["verdict"] == "leak"


# ── FR-8: carrier carries mode/verdict/action/trace_id on every path ──


@pytest.mark.asyncio
async def test_carrier_shape_complete(_bb) -> None:
    _, bb = await _run(_bb, judge=_Judge([False]), regenerate=_fail_regen)
    d = _gate_carriers(bb)[0].details
    for key in ("mode", "verdict", "action", "trace_id"):
        assert key in d, f"carrier missing {key}"
    assert d["trace_id"] == "tid-1"


# ── regenerate callables (stubs) ──


async def _fail_regen(**kw):  # must not be called on non-regen paths
    raise AssertionError("regenerate should not be called here")


async def _leak_regen(**kw):
    return "still the answer is 42"


async def _clean_regen(**kw):
    return "Consider what the units tell you."
