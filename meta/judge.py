"""LLM-as-judge for agent output evaluation.

Scores agent outputs against the failure taxonomy. Receives an EvalRecord
(input + output + trace) and produces a structured score with category labels.

Uses LLMService for inference -- no direct LLM imports.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from components.schemas import EvalRecord
from services.base_config import ModelProfile

logger = logging.getLogger("meta.judge")

_TAXONOMY_PATH = Path(__file__).parent / "discovery" / "failure_taxonomy.json"
_PROMPT_PATH = Path(__file__).parent / "judge_prompt.j2"


class JudgeScore(BaseModel):
    """Structured output from the LLM judge."""

    score: int = Field(ge=1, le=5)
    failure_categories: list[str] = Field(default_factory=list)
    reasoning: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class JudgeResult(BaseModel):
    """Full result including the eval record reference and judge score."""

    task_id: str
    step: int
    judge_score: JudgeScore
    raw_response: str = ""


def load_taxonomy() -> dict[str, Any]:
    """Load the failure taxonomy from the discovery directory."""
    if not _TAXONOMY_PATH.exists():
        return {"categories": []}
    return json.loads(_TAXONOMY_PATH.read_text())


def build_judge_prompt(
    eval_record: EvalRecord,
    taxonomy: dict[str, Any] | None = None,
) -> str:
    """Render the judge prompt with taxonomy and eval record data."""
    if taxonomy is None:
        taxonomy = load_taxonomy()

    from services.prompt_service import PromptService

    ps = PromptService(template_dir=str(_PROMPT_PATH.parent))
    return ps.render_prompt(
        "judge_prompt",
        categories=taxonomy.get("categories", []),
        input=json.dumps(eval_record.ai_input),
        output=(
            eval_record.ai_response
            if isinstance(eval_record.ai_response, str)
            else json.dumps(eval_record.ai_response)
        ),
        trace="",
    )


def parse_judge_response(raw: str) -> JudgeScore:
    """Parse the LLM judge's JSON response into a JudgeScore."""
    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1]
        cleaned = cleaned.split("```", 1)[0]
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1]
        cleaned = cleaned.split("```", 1)[0]

    try:
        data = json.loads(cleaned.strip())
        return JudgeScore.model_validate(data)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Failed to parse judge response: %s", exc)
        return JudgeScore(
            score=1,
            failure_categories=["parse_error"],
            reasoning=f"Failed to parse judge response: {raw[:200]}",
            confidence=0.0,
        )


async def score_eval_record(
    eval_record: EvalRecord,
    llm_service: Any,
    judge_profile: ModelProfile,
    taxonomy: dict[str, Any] | None = None,
) -> JudgeResult:
    """Score a single EvalRecord using the LLM judge."""
    prompt = build_judge_prompt(eval_record, taxonomy)

    try:
        response = await llm_service.invoke(
            judge_profile,
            [{"role": "user", "content": prompt}],
        )
        raw = getattr(response, "content", str(response))
    except Exception as exc:
        logger.error("Judge LLM call failed: %s", exc)
        raw = ""

    judge_score = parse_judge_response(raw)

    return JudgeResult(
        task_id=eval_record.task_id,
        step=eval_record.step,
        judge_score=judge_score,
        raw_response=raw[:1000],
    )
