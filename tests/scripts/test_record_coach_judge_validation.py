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


# ── grader_judge routing: the spec-mandated content-axis wiring (3.5d) ──────


class _RecordingJudge:
    """Records that it was invoked, returns None (abstain) so no schema needed."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.seen: list[str] = []

    async def evaluate(self, *, learner_utterance, coach_reply, mode, question):  # noqa: ANN001
        self.seen.append(coach_reply)
        return None


def test_grader_case_routes_to_grader_judge():
    """A case marked ``judge: grader`` MUST go to ``grader_judge``, not pedagogy —
    the forward-wiring the spec (3.5d '+ GraderJudge for content-axis cases')
    reserves the param for. Pedagogy must not silently swallow it."""
    ped = _RecordingJudge("pedagogy")
    grd = _RecordingJudge("grader")
    cases = {
        "P1": {
            "learner_prompt": "p",
            "coach_reply": "ped-reply",
            "mode": "post_submit",
        },
        "C1": {
            "learner_prompt": "c",
            "coach_reply": "grader-reply",
            "mode": "post_submit",
            "judge": "grader",
        },
    }
    payload = asyncio.run(record_verdicts(cases, pedagogy_judge=ped, grader_judge=grd))
    assert ped.seen == ["ped-reply"]
    assert grd.seen == ["grader-reply"]
    judges = {r["case_id"]: r["judge"] for r in payload["verdicts"]}
    assert judges == {"P1": "pedagogy", "C1": "grader"}


def test_grader_case_without_grader_judge_fails_loud():
    """A grader-axis case with no ``grader_judge`` supplied must raise, never be
    silently rescored as pedagogy (fail-closed, mirrors the scorer's ScorerError)."""
    import pytest

    cases = {
        "C1": {
            "learner_prompt": "c",
            "coach_reply": "r",
            "mode": "post_submit",
            "judge": "grader",
        }
    }
    with pytest.raises(ValueError, match="grader"):
        asyncio.run(record_verdicts(cases, pedagogy_judge=_RecordingJudge("ped")))


# ── C-pre: model-pin seam (fresh-recert spec FR-8) ─────────────────────────────
# The 3.9 re-cert must run on glm-5.2, but glm-5.2 is provider="direct" and lives
# only in the `glm` profile set whose *tier* default is glm-5.1 — so a tier-only
# override picks the wrong GLM. `select_judge_profile` adds an explicit by-NAME pin
# (COACH_JUDGE_MODEL) that overrides the tier default, staying inside the registry
# (H2 — no hardcoded model string in the harness). Pure selection over a profile
# list: no LLMService, no network.


def _prof(name: str, tier: str, provider: str = "litellm") -> ModelProfile:
    return ModelProfile(
        name=name,
        litellm_id=name,
        tier=tier,
        context_window=128000,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        provider=provider,  # type: ignore[arg-type]
    )


_FAKE_GLM_SET = [
    _prof("glm-5.1", "reasoning"),
    _prof("glm-5.2", "reasoning", provider="direct"),
]
_FAKE_OPENAI_SET = [
    _prof("gpt-4o-mini", "fast"),
    _prof("gpt-4o", "capable"),
    _prof("o3", "reasoning"),
]


def test_select_judge_profile_honors_model_pin():
    """FR-8: an explicit model pin overrides the tier and returns THAT profile,
    even when the tier default would pick a sibling (glm-5.1 vs glm-5.2)."""
    from scripts.record_coach_judge_validation import select_judge_profile

    chosen = select_judge_profile(_FAKE_GLM_SET, model_pin="glm-5.2", tier="reasoning")
    assert chosen.name == "glm-5.2"
    assert chosen.provider == "direct"


def test_select_judge_profile_falls_back_to_tier_when_unset():
    """Unset pin → today's behavior: pick the requested tier (capable default)."""
    from scripts.record_coach_judge_validation import select_judge_profile

    chosen = select_judge_profile(_FAKE_OPENAI_SET, model_pin=None, tier="capable")
    assert chosen.name == "gpt-4o"  # the capable-tier row, unchanged from 3.9


def test_select_judge_profile_unknown_pin_raises_with_available():
    """A pin absent from the active set fails LOUD (KeyError-style), naming the
    set — so `MODEL_PROFILE_SET=glm` guidance is actionable, never a silent wrong
    model. (glm-5.2 is only in the `glm` set; pinning it under `openai` must error.)"""
    import pytest

    from scripts.record_coach_judge_validation import select_judge_profile

    with pytest.raises(KeyError, match="glm-5.2"):
        select_judge_profile(_FAKE_OPENAI_SET, model_pin="glm-5.2", tier="capable")
