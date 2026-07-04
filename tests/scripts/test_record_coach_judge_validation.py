"""Task 3.5d-1 — offline stub smoke test for the recorder (FR-9 stub).

Drives ``record_verdicts`` with a STUB provider so no network/LLM is touched.
The live entrypoint (``main`` / ``build_live_judges``) is manual-only and is not
exercised here (it is ``# pragma: no cover - live only``).
"""

from __future__ import annotations

import asyncio
import json

from components.subject_coach_judges import PedagogyJudge
from meta.coach_judge_validation import load_cases, load_verdicts, score
from scripts.record_coach_judge_validation import record_verdicts, write_verdicts
from services.base_config import ModelProfile

_PED_JSON = json.dumps(
    {
        "mistake_identification": 0.6,
        "mistake_location": 0.6,
        "actionability": 0.6,
        "coherence": 0.6,
        "productive_struggle": 0.6,
        "illusion_of_competence": 0.6,
        "mistake_identification_pass": True,
        "mistake_location_pass": True,
        "actionability_pass": True,
        "coherence_pass": True,
        "productive_struggle_pass": True,
        "illusion_of_competence_pass": True,
        "answer_leakage": False,
        "rationale": "stub",
    }
)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """Stub provider: every invoke returns the same canned verdict JSON."""

    async def invoke(self, profile, messages, **kwargs):  # noqa: ANN001
        return _FakeResponse(_PED_JSON)


class _ErrorLLM:
    async def invoke(self, profile, messages, **kwargs):  # noqa: ANN001
        raise RuntimeError("provider down")


def _profile() -> ModelProfile:
    return ModelProfile(
        name="stub-judge",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _cases_slice():
    from pathlib import Path

    fx = Path(__file__).resolve().parents[1] / "fixtures" / "coach_judge_validation"
    cases = load_cases(fx / "cases.jsonl")
    return {cid: cases[cid] for cid in ("A1", "G4")}


def _judge(llm) -> PedagogyJudge:  # noqa: ANN001
    from services.prompt_service import PromptService

    return PedagogyJudge(llm, PromptService(), _profile(), name="PedagogyJudge")


def test_recorder_produces_one_row_per_case_offline():
    """FR-9 stub: recorder yields a verdict row per case with no live call."""
    cases = _cases_slice()
    payload = asyncio.run(record_verdicts(cases, pedagogy_judge=_judge(_FakeLLM())))
    got = {r["case_id"] for r in payload["verdicts"]}
    assert got == set(cases)
    assert all(r["abstained"] is False for r in payload["verdicts"])


def test_recorder_records_abstain_on_provider_error():
    """FR-9 / fail-open ban: a None verdict is recorded as abstained, not faked."""
    cases = _cases_slice()
    payload = asyncio.run(record_verdicts(cases, pedagogy_judge=_judge(_ErrorLLM())))
    assert all(r["abstained"] is True for r in payload["verdicts"])
    assert all(r["verdict"] is None for r in payload["verdicts"])


def test_recorded_output_replays_through_scorer(tmp_path):
    """The recorder's output is consumable by the offline scorer (round-trip)."""
    cases = _cases_slice()
    payload = asyncio.run(record_verdicts(cases, pedagogy_judge=_judge(_FakeLLM())))
    out = tmp_path / "verdicts.json"
    write_verdicts(out, payload)
    verdicts = load_verdicts(out)
    rep = score(cases, verdicts)
    # A1 is leak-true; stub says leakage=false → a false negative (surfaced, not hidden)
    assert rep.counts.fn == 1
    assert rep.control_regressions == []
