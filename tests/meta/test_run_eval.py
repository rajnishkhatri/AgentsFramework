"""L2 Contract: Automated scoring pipeline tests (Story 3.4).

Tests pipeline with mocked agent + mocked judge.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from components.schemas import EvalRecord
from meta.run_eval import EvalReport, load_golden_set, run_eval_pipeline, save_report
from services.base_config import ModelProfile


def _sample_record(**overrides) -> EvalRecord:
    defaults = {
        "task_id": "task-001",
        "user_id": "user-001",
        "step": 0,
        "target": "call_llm",
        "ai_input": {"task_input": "test"},
        "ai_response": "test output",
        "timestamp": datetime.now(UTC),
    }
    defaults.update(overrides)
    return EvalRecord(**defaults)


def _judge_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


class TestEvalPipeline:
    @pytest.mark.asyncio
    async def test_pipeline_produces_valid_report(self):
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "score": 4,
            "failure_categories": [],
            "reasoning": "Good",
            "confidence": 0.9,
        })
        mock_service = MagicMock()
        mock_service.invoke = AsyncMock(return_value=mock_response)

        golden = [_sample_record(task_id=f"t-{i}") for i in range(3)]

        report = await run_eval_pipeline(
            golden_set=golden,
            llm_service=mock_service,
            judge_profile=_judge_profile(),
        )

        assert isinstance(report, EvalReport)
        assert report.total_records == 3
        assert report.scored_records == 3
        assert report.failed_records == 0
        assert report.mean_score == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_pipeline_handles_failures_gracefully(self):
        """When the judge LLM fails, the pipeline still completes with fallback scores."""
        mock_service = MagicMock()
        mock_service.invoke = AsyncMock(side_effect=Exception("LLM down"))

        golden = [_sample_record(task_id=f"t-{i}") for i in range(2)]

        report = await run_eval_pipeline(
            golden_set=golden,
            llm_service=mock_service,
            judge_profile=_judge_profile(),
        )

        assert report.total_records == 2
        assert len(report.entries) == 2
        for entry in report.entries:
            assert entry.judge_score.score == 1
            assert entry.judge_score.confidence == 0.0

    @pytest.mark.asyncio
    async def test_pipeline_empty_golden_set(self):
        mock_service = MagicMock()

        report = await run_eval_pipeline(
            golden_set=[],
            llm_service=mock_service,
            judge_profile=_judge_profile(),
        )

        assert report.total_records == 0
        assert report.mean_score == 0.0


class TestGoldenSetLoading:
    def test_load_from_jsonl(self, tmp_path):
        records = [_sample_record(task_id=f"t-{i}") for i in range(3)]
        path = tmp_path / "golden.jsonl"
        path.write_text("\n".join(r.model_dump_json() for r in records) + "\n")

        loaded = load_golden_set(path)
        assert len(loaded) == 3

    def test_load_nonexistent_returns_empty(self, tmp_path):
        loaded = load_golden_set(tmp_path / "nope.jsonl")
        assert loaded == []


class TestReportSaving:
    def test_save_report_creates_json(self, tmp_path):
        report = EvalReport(
            report_id="test-report",
            total_records=5,
            scored_records=5,
            mean_score=4.0,
        )
        output = tmp_path / "reports" / "report.json"
        save_report(report, output)

        assert output.exists()
        loaded = json.loads(output.read_text())
        assert loaded["report_id"] == "test-report"
        assert loaded["mean_score"] == 4.0
