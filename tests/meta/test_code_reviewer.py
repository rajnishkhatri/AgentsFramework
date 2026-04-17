"""L1/L2 tests for CodeReviewer (STORY-408/409/410).

Tests deterministic validators and CLI entrypoint.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta.code_reviewer import (
    CodeReviewerAgent,
    check_import_rules,
    run_code_reviewer_cli,
    run_deterministic_review,
)
from trust.review_schema import Severity, Verdict


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestCheckImportRules:
    def test_clean_trust_file(self):
        """trust/enums.py should have zero findings."""
        findings = check_import_rules(str(AGENT_ROOT / "trust" / "enums.py"))
        assert findings == []

    def test_trust_file_with_io_import(self, tmp_path):
        """A trust/ file importing logging should produce a D4 critical finding."""
        bad_file = tmp_path / "trust" / "bad.py"
        bad_file.parent.mkdir(parents=True)
        bad_file.write_text("import logging\n")
        findings = check_import_rules(str(bad_file))
        assert len(findings) >= 1
        assert any(f.dimension == "D4" for f in findings)
        assert any(f.severity == Severity.CRITICAL for f in findings)

    def test_clean_services_file(self):
        """services/base_config.py should have zero D1 findings."""
        findings = check_import_rules(str(AGENT_ROOT / "services" / "base_config.py"))
        d1_findings = [f for f in findings if f.dimension == "D1"]
        assert d1_findings == []

    def test_nonexistent_file(self, tmp_path):
        """Nonexistent file produces findings about parse failure."""
        findings = check_import_rules(str(tmp_path / "nonexistent.py"))
        # parse_imports returns pass=False → check_dependency_rules passes that through
        assert isinstance(findings, list)


class TestDeterministicReview:
    def test_clean_files_approve(self):
        """Review of well-formed files should produce approve verdict."""
        files = [
            str(AGENT_ROOT / "trust" / "enums.py"),
            str(AGENT_ROOT / "trust" / "models.py"),
        ]
        report = run_deterministic_review(files)
        assert report.verdict == Verdict.APPROVE
        assert len(report.files_reviewed) == 2

    def test_violation_produces_reject(self, tmp_path):
        """File with forbidden import should produce reject verdict."""
        bad_file = tmp_path / "trust" / "bad_imports.py"
        bad_file.parent.mkdir(parents=True)
        bad_file.write_text("from services.llm_config import LLMService\n")
        report = run_deterministic_review([str(bad_file)])
        assert report.verdict == Verdict.REJECT
        assert any(
            f.severity == Severity.CRITICAL
            for d in report.dimensions
            for f in d.findings
        )

    def test_nonexistent_file_skipped(self, tmp_path):
        report = run_deterministic_review([str(tmp_path / "nope.py")])
        assert report.verdict == Verdict.APPROVE
        assert report.files_reviewed == []
        assert any("not found" in line for line in report.validation_log)

    def test_non_python_skipped(self, tmp_path):
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        report = run_deterministic_review([str(txt)])
        assert report.files_reviewed == []


class TestCodeReviewerCLI:
    def test_deterministic_only_clean_approve(self):
        exit_code = run_code_reviewer_cli([
            "--files", str(AGENT_ROOT / "trust" / "enums.py"),
            "--deterministic-only",
        ])
        assert exit_code == 0

    def test_deterministic_only_violation_reject(self, tmp_path):
        bad_file = tmp_path / "trust" / "bad.py"
        bad_file.parent.mkdir(parents=True)
        bad_file.write_text("from orchestration.react_loop import build_graph\n")
        exit_code = run_code_reviewer_cli([
            "--files", str(bad_file),
            "--deterministic-only",
        ])
        assert exit_code == 2  # reject

    def test_output_file(self, tmp_path):
        output = tmp_path / "report.json"
        exit_code = run_code_reviewer_cli([
            "--files", str(AGENT_ROOT / "trust" / "enums.py"),
            "--deterministic-only",
            "--output", str(output),
        ])
        assert exit_code == 0
        assert output.exists()
        report = json.loads(output.read_text())
        assert report["verdict"] == "approve"

    def test_nonexistent_file_error(self, tmp_path):
        exit_code = run_code_reviewer_cli([
            "--files", str(tmp_path / "nonexistent.py"),
            "--deterministic-only",
        ])
        assert exit_code == 0  # no files reviewed, so approve (no violations)

    def test_llm_without_api_key_returns_3(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        exit_code = run_code_reviewer_cli([
            "--files", str(AGENT_ROOT / "trust" / "enums.py"),
            "--llm",
        ])
        assert exit_code == 3

    def test_llm_and_deterministic_mutually_exclusive(self):
        exit_code = run_code_reviewer_cli([
            "--files", str(AGENT_ROOT / "trust" / "enums.py"),
            "--llm",
            "--deterministic-only",
        ])
        assert exit_code == 3

    def test_cli_does_not_mutate_cwd(self, tmp_path):
        """D5-W2 regression: run_code_reviewer_cli must NOT change os.getcwd().

        The pre-fix CLI called ``os.chdir(AGENT_ROOT)`` inside
        ``_async_llm_review``, leaking global state into pytest workers.
        Even the deterministic-only path goes through arg parsing + I/O
        and must leave the cwd untouched.
        """
        original = os.getcwd()
        try:
            os.chdir(tmp_path)
            exit_code = run_code_reviewer_cli([
                "--files", str(AGENT_ROOT / "trust" / "enums.py"),
                "--deterministic-only",
            ])
            assert exit_code == 0
            assert os.getcwd() == str(tmp_path)
        finally:
            os.chdir(original)

    @pytest.mark.asyncio
    async def test_async_llm_review_does_not_mutate_cwd(self, tmp_path):
        """D5-W2 regression: _async_llm_review must leave cwd intact.

        Targets the exact code path (``_async_llm_review``) where the old
        ``os.chdir(AGENT_ROOT)`` lived. Patches LLMService so no real
        network call happens.
        """
        from meta.code_reviewer import _async_llm_review

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
        fake_llm.invoke = AsyncMock(
            return_value=MagicMock(content=json.dumps(minimal))
        )

        original = os.getcwd()
        try:
            os.chdir(tmp_path)
            with patch(
                "services.llm_config.LLMService", return_value=fake_llm
            ):
                report = await _async_llm_review(
                    files=[str(AGENT_ROOT / "trust" / "enums.py")],
                    diff=None,
                    task_id="t-cwd",
                    user_id="u-cwd",
                )
            assert report.verdict == Verdict.APPROVE
            assert os.getcwd() == str(tmp_path), (
                "_async_llm_review leaked an os.chdir() call into the "
                "global cwd (D5-W2 regression)."
            )
        finally:
            os.chdir(original)


class TestCodeReviewerEvalCapture:
    """H5: LLM path records eval_capture with target code_review."""

    @pytest.mark.asyncio
    async def test_successful_llm_review_calls_eval_capture(self):
        minimal = {
            "verdict": "approve",
            "statement": "ok",
            "confidence": 0.9,
            "dimensions": [],
            "gaps": [],
            "validation_log": [],
            "files_reviewed": [],
        }
        llm = AsyncMock()
        llm.invoke.return_value = MagicMock(content=json.dumps(minimal))

        ps = MagicMock()
        ps.render_prompt.return_value = "rendered"

        recorded: list[dict] = []

        async def capture(**kwargs: object) -> None:
            recorded.append(kwargs)

        profile = MagicMock()
        profile.name = "gpt-4o-mini"

        with patch("meta.code_reviewer.eval_capture.record", side_effect=capture):
            agent = CodeReviewerAgent(
                llm_service=llm,
                prompt_service=ps,
                judge_profile=profile,
                task_id="task-cr-1",
                user_id="user-cr",
            )
            report = await agent.review([str(AGENT_ROOT / "trust" / "enums.py")])

        assert report.verdict == Verdict.APPROVE
        assert len(recorded) == 1
        assert recorded[0]["target"] == "code_review"
        cfg = recorded[0]["config"]
        assert cfg["configurable"]["task_id"] == "task-cr-1"
        assert cfg["configurable"]["user_id"] == "user-cr"
        assert recorded[0]["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_failed_llm_review_still_records_eval_capture(self):
        llm = AsyncMock()
        llm.invoke.side_effect = RuntimeError("invoke failed")

        ps = MagicMock()
        ps.render_prompt.return_value = "rendered"

        recorded: list[dict] = []

        async def capture(**kwargs: object) -> None:
            recorded.append(kwargs)

        profile = MagicMock()
        profile.name = "gpt-4o-mini"

        with patch("meta.code_reviewer.eval_capture.record", side_effect=capture):
            agent = CodeReviewerAgent(
                llm_service=llm,
                prompt_service=ps,
                judge_profile=profile,
                task_id="t2",
                user_id="u2",
            )
            report = await agent.review([str(AGENT_ROOT / "trust" / "enums.py")])

        assert report.verdict == Verdict.REJECT
        assert len(recorded) == 1
        assert recorded[0]["target"] == "code_review"
        assert "error" in recorded[0]["ai_response"]


# ── L3: end-to-end with recorded LLM fixture (STORY-408) ───────────


@pytest.mark.slow
class TestCodeReviewerL3:
    """Replay a recorded LLM response so the L3 path exists in CI without
    making a live API call. The recording is generated with
    ``scripts/record_code_reviewer_fixture.py`` -- see
    ``tests/fixtures/code_reviewer/README.md`` for the procedure.
    """

    FIXTURE_PATH = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "code_reviewer"
        / "review_response.json"
    )

    @pytest.mark.asyncio
    async def test_review_with_recorded_fixture(self):
        if not self.FIXTURE_PATH.exists():
            pytest.skip(
                "Recording absent. Run scripts/record_code_reviewer_fixture.py "
                "with OPENAI_API_KEY to populate "
                f"{self.FIXTURE_PATH}.",
            )

        recorded = json.loads(self.FIXTURE_PATH.read_text())

        llm = AsyncMock()
        llm.invoke.return_value = MagicMock(content=json.dumps(recorded))
        ps = MagicMock()
        ps.render_prompt.return_value = "rendered"
        profile = MagicMock()
        profile.name = "gpt-4o-mini"

        agent = CodeReviewerAgent(
            llm_service=llm,
            prompt_service=ps,
            judge_profile=profile,
            task_id="l3-replay",
            user_id="l3-user",
        )
        report = await agent.review(
            [str(AGENT_ROOT / "trust" / "enums.py")]
        )
        assert report.verdict in (
            Verdict.APPROVE,
            Verdict.REQUEST_CHANGES,
            Verdict.REJECT,
        )
        assert isinstance(report.confidence, float)
        assert 0.0 <= report.confidence <= 1.0
