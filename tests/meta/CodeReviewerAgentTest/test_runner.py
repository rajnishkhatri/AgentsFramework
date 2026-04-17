"""L2 tests for ``meta.CodeReviewerAgentTest.runner``.

Uses a mocked LLMService so no live API call happens. Verifies the
profile selected from ``MODEL_NAME`` flows through to the agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta.CodeReviewerAgentTest.env_settings import EnvSettings
from meta.CodeReviewerAgentTest.review_config import ReviewAgentConfig
from meta.CodeReviewerAgentTest.runner import run_review
from trust.review_schema import Verdict

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _bypass_dotenv(monkeypatch):
    monkeypatch.setattr(
        EnvSettings,
        "model_config",
        {**EnvSettings.model_config, "env_file": "/nonexistent.env"},
    )


@pytest.mark.asyncio
async def test_deterministic_only_path_returns_review_report(monkeypatch):
    """When deterministic_only=True, no LLM service is constructed."""
    _bypass_dotenv(monkeypatch)
    monkeypatch.delenv("MODEL_NAME", raising=False)

    config = ReviewAgentConfig(
        name="det-only",
        files=["trust/enums.py"],
        deterministic_only=True,
        output_json="docs/_unused.json",
    )

    with patch("meta.CodeReviewerAgentTest.runner.LLMService") as llm_cls:
        report = await run_review(config)

    assert report.verdict in (Verdict.APPROVE, Verdict.REQUEST_CHANGES, Verdict.REJECT)
    llm_cls.assert_not_called()  # deterministic path skips LLM construction


@pytest.mark.asyncio
async def test_runner_passes_env_profile_to_llm_service(monkeypatch):
    _bypass_dotenv(monkeypatch)
    monkeypatch.setenv("MODEL_NAME", "anthropic/claude-3-haiku-20240307")

    minimal = {
        "verdict": "approve",
        "statement": "ok",
        "confidence": 0.9,
        "dimensions": [],
        "gaps": [],
        "validation_log": [],
        "files_reviewed": [],
    }
    fake_llm = MagicMock()
    fake_llm.invoke = AsyncMock(return_value=MagicMock(content=json.dumps(minimal)))

    config = ReviewAgentConfig(
        name="env-profile",
        files=["trust/enums.py"],
        deterministic_only=False,
        output_json="docs/_unused.json",
    )

    with patch(
        "meta.CodeReviewerAgentTest.runner.LLMService", return_value=fake_llm
    ) as llm_cls:
        report = await run_review(config)

    assert report.verdict == Verdict.APPROVE
    llm_cls.assert_called_once()
    agent_config = llm_cls.call_args.args[0]
    profile = agent_config.models[0]
    assert profile.litellm_id == "anthropic/claude-3-haiku-20240307"
    assert profile.name == "claude-3-haiku"
    assert agent_config.default_model == "claude-3-haiku"
