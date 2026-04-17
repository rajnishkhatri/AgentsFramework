"""L2 Contract: LLM judge tests (Story 3.3).

Tests judge prompt building, response parsing, and scoring with mocked LLM.
No live LLM calls (Pattern 5).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from components.schemas import EvalRecord
from meta.judge import (
    JudgeResult,
    JudgeScore,
    build_judge_prompt,
    load_taxonomy,
    parse_judge_response,
    score_eval_record,
)


def _sample_eval_record(**overrides) -> EvalRecord:
    defaults = {
        "task_id": "task-001",
        "user_id": "user-001",
        "step": 0,
        "target": "call_llm",
        "ai_input": {"task_input": "What is 2+2?"},
        "ai_response": "The answer is 4.",
        "timestamp": datetime.now(UTC),
    }
    defaults.update(overrides)
    return EvalRecord(**defaults)


class TestJudgePromptBuilding:
    def test_build_prompt_includes_input_and_output(self):
        rec = _sample_eval_record()
        prompt = build_judge_prompt(rec)
        assert "What is 2+2?" in prompt
        assert "The answer is 4." in prompt

    def test_build_prompt_includes_taxonomy_categories(self):
        taxonomy = load_taxonomy()
        rec = _sample_eval_record()
        prompt = build_judge_prompt(rec, taxonomy)
        assert "tool_selection_error" in prompt or "Tool Selection" in prompt


class TestJudgeResponseParsing:
    def test_parse_valid_json_response(self):
        raw = json.dumps({
            "score": 5,
            "failure_categories": [],
            "reasoning": "Perfect output",
            "confidence": 0.95,
        })
        score = parse_judge_response(raw)
        assert score.score == 5
        assert score.failure_categories == []
        assert score.confidence == 0.95

    def test_parse_json_in_code_block(self):
        raw = '```json\n{"score": 3, "failure_categories": ["reasoning_loop"], "reasoning": "Issues", "confidence": 0.7}\n```'
        score = parse_judge_response(raw)
        assert score.score == 3
        assert "reasoning_loop" in score.failure_categories

    def test_parse_invalid_json_returns_fallback(self):
        raw = "This is not JSON at all"
        score = parse_judge_response(raw)
        assert score.score == 1
        assert score.confidence == 0.0
        assert "parse_error" in score.failure_categories

    def test_parse_out_of_range_score_fails_validation(self):
        raw = json.dumps({"score": 10, "failure_categories": [], "reasoning": "x", "confidence": 0.5})
        score = parse_judge_response(raw)
        assert score.score == 1  # Fallback on validation error


class TestJudgeScoring:
    @pytest.mark.asyncio
    async def test_score_eval_record_with_mock_llm(self):
        from unittest.mock import AsyncMock, MagicMock

        from services.base_config import ModelProfile

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 4,
            "failure_categories": [],
            "reasoning": "Good output",
            "confidence": 0.9,
        })

        mock_service = MagicMock()
        mock_service.invoke = AsyncMock(return_value=mock_response)

        profile = ModelProfile(
            name="gpt-4o-mini",
            litellm_id="openai/gpt-4o-mini",
            tier="fast",
            context_window=128000,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
        )

        rec = _sample_eval_record()
        result = await score_eval_record(rec, mock_service, profile)

        assert isinstance(result, JudgeResult)
        assert result.judge_score.score == 4
        assert result.task_id == "task-001"

    @pytest.mark.asyncio
    async def test_score_eval_record_handles_llm_failure(self):
        from unittest.mock import AsyncMock, MagicMock

        from services.base_config import ModelProfile

        mock_service = MagicMock()
        mock_service.invoke = AsyncMock(side_effect=Exception("LLM down"))

        profile = ModelProfile(
            name="gpt-4o-mini",
            litellm_id="openai/gpt-4o-mini",
            tier="fast",
            context_window=128000,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
        )

        rec = _sample_eval_record()
        result = await score_eval_record(rec, mock_service, profile)

        assert result.judge_score.score == 1
        assert result.judge_score.confidence == 0.0
