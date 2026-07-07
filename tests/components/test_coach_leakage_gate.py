"""L1 tests for the coach answer-leakage gate pure decision (Phase 5, T1/T2).

FR-9 truth table (off/shadow/enforce × clean/leak/unavailable × retry), FR-3
suppress, FR-7 regenerate, FR-10 arm cert-floor guard. Pure — no I/O, no LLM.
Failure rows first (TAP-4).
"""

from __future__ import annotations

import pytest

from components.coach_leakage_gate import (
    arm,
    decide_leakage_enforcement,
)


# ── FR-9 / FR-3 / FR-7: the enforce failure paths FIRST ──────────────────────


def test_enforce_leak_retry_still_leaks_suppresses() -> None:
    # FR-3: a regenerated reply that STILL leaks must be suppressed, never emitted.
    assert (
        decide_leakage_enforcement("enforce", "leak", retry_verdict="leak")
        == "suppress"
    )


def test_enforce_leak_no_retry_yet_regenerates() -> None:
    # FR-7: first flag in enforce → regenerate once (retry not yet attempted).
    assert (
        decide_leakage_enforcement("enforce", "leak", retry_verdict=None)
        == "regenerate"
    )


def test_enforce_leak_retry_clears_allows() -> None:
    # regeneration cleared the leak → emit the regenerated reply.
    assert (
        decide_leakage_enforcement("enforce", "leak", retry_verdict="clean") == "allow"
    )


def test_enforce_judge_unavailable_fails_open() -> None:
    # FR-1: judge outage while armed → fail OPEN (let the reply through), loud carrier.
    assert decide_leakage_enforcement("enforce", "unavailable") == "fail_open"


def test_enforce_clean_allows() -> None:
    assert decide_leakage_enforcement("enforce", "clean") == "allow"


# ── FR-6: shadow observes, never blocks ──────────────────────────────────────


@pytest.mark.parametrize("verdict", ["leak", "clean", "unavailable"])
def test_shadow_always_records_never_acts(verdict: str) -> None:
    assert decide_leakage_enforcement("shadow", verdict) == "shadow_record"


# ── FR-5: off is inert ───────────────────────────────────────────────────────


@pytest.mark.parametrize("verdict", ["leak", "clean", "unavailable"])
def test_off_always_allows(verdict: str) -> None:
    assert decide_leakage_enforcement("off", verdict) == "allow"


# ── FR-10: arm refuses to enforce below the cert floor (failure first) ────────


def test_arm_below_cert_forces_off() -> None:
    assert arm("enforce", goldset_certified=False) == "off"
    assert arm("shadow", goldset_certified=False) == "off"


def test_arm_certified_passes_mode_through() -> None:
    assert arm("enforce", goldset_certified=True) == "enforce"
    assert arm("shadow", goldset_certified=True) == "shadow"


def test_arm_off_stays_off_regardless() -> None:
    assert arm("off", goldset_certified=True) == "off"
    assert arm("off", goldset_certified=False) == "off"


# ── T4: runtime judge adapter — verdict mapping, None → unavailable (FR-1/FR-11) ──


class _StubJudge:
    """A stub PedagogyJudge for CI — no live LLM (FR-11). Returns a canned
    verdict object, None (parse/error), or raises."""

    def __init__(self, *, answer_leakage=None, raises=False, returns_none=False):
        self._answer_leakage = answer_leakage
        self._raises = raises
        self._returns_none = returns_none
        self.calls = 0

    async def evaluate(self, *, learner_utterance, coach_reply, mode, question=""):
        self.calls += 1
        if self._raises:
            raise RuntimeError("judge boom")
        if self._returns_none:
            return None

        class _V:
            answer_leakage = self._answer_leakage

        return _V()


async def _call(judge, **kw):
    from components.coach_leakage_gate import judge_leakage

    return await judge_leakage(
        judge,
        learner_utterance=kw.get("lu", "u"),
        coach_reply=kw.get("cr", "r"),
        mode=kw.get("mode", "pre_submit"),
        question=kw.get("q", ""),
    )


@pytest.mark.asyncio
async def test_judge_none_maps_to_unavailable() -> None:
    # FR-1: a judge that fails CLOSED to None → unavailable (→ fail_open downstream).
    assert await _call(_StubJudge(returns_none=True)) == "unavailable"


@pytest.mark.asyncio
async def test_judge_raises_maps_to_unavailable() -> None:
    # A judge outage/exception must NOT crash the turn — it degrades to unavailable.
    assert await _call(_StubJudge(raises=True)) == "unavailable"


@pytest.mark.asyncio
async def test_judge_leak_true_maps_to_leak() -> None:
    assert await _call(_StubJudge(answer_leakage=True)) == "leak"


@pytest.mark.asyncio
async def test_judge_leak_false_maps_to_clean() -> None:
    assert await _call(_StubJudge(answer_leakage=False)) == "clean"


@pytest.mark.asyncio
async def test_judge_none_answer_leakage_maps_to_unavailable() -> None:
    # A verdict object whose answer_leakage is itself None (un-decided) is not a
    # definite clean/leak — treat as unavailable, never fabricate a False.
    assert await _call(_StubJudge(answer_leakage=None)) == "unavailable"
