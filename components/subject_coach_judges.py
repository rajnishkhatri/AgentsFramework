"""Subject-Coach judges — GraderJudge (FR-14) + PedagogyJudge (FR-15/16).

Framework-agnostic mirrors of ``components.goal_judge.GoalJudge``: injected
``LLMService`` + ``PromptService`` + fast-tier ``ModelProfile``, ``.j2`` rubric
(H1), structured-JSON verdict parse with repair. NO langgraph/langchain
imports (invariant #3); imports only ``components.schemas`` in-layer.

Failure contract (deliberately NOT GoalJudge's)
-----------------------------------------------
GoalJudge raises on a bad verdict so its caller falls back to the keyword
heuristic. The coach judges have no fallback consumer — they feed the post-hoc
``target="coach_judges"`` telemetry stream (design §7.3, ADR-0009). An
undecidable turn therefore yields ``None`` (AP-6): never a fabricated 0.0,
never a defaulted ``answer_leakage=False`` (a leak detector that fails open is
worse than none), never a binary ``*_pass`` derived post-hoc from its float
(gap G8 — the judge asserts the binary directly in the rubric).

The only repair performed is the GoalJudge percentage clamp: a 0-100 float
axis is rescaled into the 0..1 contract. Missing fields are not repaired.

FR-18: every content line (question, utterances, evidence) passes the injected
``GuardRailValidator`` redactor before it reaches the rubric prompt.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from components.schemas import GraderVerdict, PedagogyVerdict

if TYPE_CHECKING:
    from services.base_config import ModelProfile
    from services.governance.guardrail_validator import GuardRailValidator
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

logger = logging.getLogger("components.subject_coach_judges")

__all__ = ["GraderJudge", "PedagogyJudge"]

_VerdictT = TypeVar("_VerdictT", bound=BaseModel)


class _CoachJudgeBase:
    """Shared plumbing: injection, redaction, invoke, parse-with-repair."""

    PROMPT_NAME = ""  # subclasses pin their rubric template

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        judge_profile: ModelProfile,
        *,
        redactor: GuardRailValidator | None = None,
        name: str = "",
    ) -> None:
        self.name = name or type(self).__name__
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._judge_profile = judge_profile
        self._redactor = redactor

    @property
    def model_name(self) -> str:
        return getattr(self._judge_profile, "name", "")

    def _clean(self, line: str) -> str:
        """FR-18: one content line through the redactor before the prompt."""
        if self._redactor is None:
            return line
        return self._redactor.redact(line)

    async def _verdict(
        self,
        rendered_prompt: str,
        verdict_type: type[_VerdictT],
        float_axes: tuple[str, ...],
    ) -> _VerdictT | None:
        """Invoke the judge model and parse; undecidable → ``None`` (AP-6)."""
        try:
            response = await self._llm_service.invoke(
                self._judge_profile,
                [{"role": "user", "content": rendered_prompt}],
            )
        except Exception:
            logger.warning("%s: provider error; verdict undecidable", self.name)
            return None
        # Normalize provider-shape at the H2 boundary: reasoning models
        # (DeepSeek V4) return ``.content`` as a block list whose answer lives in
        # ``text`` blocks; ``str(content)`` would repr the whole list (thinking
        # and all) and break the parser. ``response_text`` joins text blocks and
        # drops thinking — the same normalization every call site uses.
        from services.llm_config import response_text

        content = response_text(response)
        try:
            data = json.loads(_extract_json(content))
            if not isinstance(data, dict):
                raise ValueError("verdict is not a JSON object")
            _rescale_percentages(data, float_axes)
            return verdict_type.model_validate(data)
        except (ValueError, ValidationError) as exc:
            logger.warning(
                "%s: unparseable/incomplete verdict (%s); undecidable",
                self.name,
                exc,
            )
            return None


class GraderJudge(_CoachJudgeBase):
    """Grades the coach's GENERATED CONTENT (a hint/explanation/mini-question)
    on faithfulness, correctness, justification, actionability (FR-14).
    Reference-free; verdicts are telemetry-only (ADR-0008)."""

    PROMPT_NAME = "subject_coach_grader_judge"
    _FLOAT_AXES = ("faithfulness", "correctness", "justification", "actionability")

    async def evaluate(
        self,
        *,
        question: str,
        coach_content: str,
        evidence: list[str] | None = None,
    ) -> GraderVerdict | None:
        rendered = self._prompt_service.render_prompt(
            self.PROMPT_NAME,
            question=self._clean(question),
            coach_content=self._clean(coach_content),
            evidence=[self._clean(line) for line in (evidence or [])],
        )
        return await self._verdict(rendered, GraderVerdict, self._FLOAT_AXES)


class PedagogyJudge(_CoachJudgeBase):
    """Grades a coaching TURN as teaching (FR-15) with the first-class
    ``answer_leakage`` flag (FR-16). ``mode`` makes the leakage rubric
    mode-aware: pre-submit any answer reveal is a leak; post-feedback the key
    is already disclosed by construction (ADR-0012)."""

    PROMPT_NAME = "subject_coach_pedagogy_judge"
    _FLOAT_AXES = (
        "mistake_identification",
        "mistake_location",
        "actionability",
        "coherence",
        "productive_struggle",
        "illusion_of_competence",
    )

    async def evaluate(
        self,
        *,
        learner_utterance: str,
        coach_reply: str,
        mode: str,
        question: str = "",
    ) -> PedagogyVerdict | None:
        rendered = self._prompt_service.render_prompt(
            self.PROMPT_NAME,
            learner_utterance=self._clean(learner_utterance),
            coach_reply=self._clean(coach_reply),
            mode=mode,
            question=self._clean(question),
        )
        return await self._verdict(rendered, PedagogyVerdict, self._FLOAT_AXES)


def _extract_json(content: str) -> str:
    """Return the JSON substring from a possibly fenced / chatty response."""
    text = content.strip()
    if "```" in text:
        fenced = text.split("```", 2)
        if len(fenced) >= 2:
            block = fenced[1]
            if block.lstrip().lower().startswith("json"):
                block = block.lstrip()[4:]
            text = block.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


_CLAMP_BAND_MAX = 1.5


def _rescale_percentages(data: dict[str, Any], float_axes: tuple[str, ...]) -> None:
    """Repair 0-100 float axes into the 0..1 contract, in place.

    The ONLY repair the coach judges perform (the GoalJudge ``criteria_met``
    clamp precedent). Non-numeric or missing values are left untouched — shape
    problems are ``model_validate``'s to reject, not this repair's to paper
    over. Values already in 0..1 pass through unchanged.

    Values in (1.0, 1.5] are a slight 0..1 overshoot, not a percentage reply
    — rescaling one would silently invert a near-perfect score into a
    near-zero one (1.5 → 0.015), so that band clamps to 1.0 instead. A real
    percentage-scale reply lands well above the band (a 1.5% axis score is
    not a plausible verdict).
    """
    for axis in float_axes:
        value = data.get(axis)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        rescaled = value / 100.0 if value > _CLAMP_BAND_MAX else float(value)
        data[axis] = max(0.0, min(1.0, rescaled))
