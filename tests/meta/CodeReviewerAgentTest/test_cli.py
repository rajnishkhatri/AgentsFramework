"""L2 tests for ``meta.CodeReviewerAgentTest.cli.run_cli``.

Verdict mapping is the contract: 0=approve, 1=request_changes,
2=reject, 3=error. Failure paths first.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta.CodeReviewerAgentTest.cli import run_cli
from meta.CodeReviewerAgentTest.env_settings import EnvSettings

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _bypass_dotenv(monkeypatch):
    monkeypatch.setattr(
        EnvSettings,
        "model_config",
        {**EnvSettings.model_config, "env_file": "/nonexistent.env"},
    )


def _write_config(tmp_path: Path, **overrides) -> Path:
    base = {
        "name": "tmp-config",
        "files": [str(AGENT_ROOT / "trust" / "enums.py")],
        "deterministic_only": True,
        "output_json": str(tmp_path / "report.json"),
    }
    base.update(overrides)
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(base))
    return p


def test_missing_config_file_returns_3(tmp_path, monkeypatch):
    _bypass_dotenv(monkeypatch)
    rc = run_cli([str(tmp_path / "missing.json")])
    assert rc == 3


def test_invalid_config_returns_3(tmp_path, monkeypatch):
    _bypass_dotenv(monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text('{"oops": true}')
    rc = run_cli([str(bad)])
    assert rc == 3


def test_llm_path_without_api_key_returns_3(tmp_path, monkeypatch):
    _bypass_dotenv(monkeypatch)
    monkeypatch.setenv("MODEL_NAME", "anthropic/claude-3-haiku-20240307")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cfg = _write_config(tmp_path, deterministic_only=False)
    rc = run_cli([str(cfg)])
    assert rc == 3


def test_deterministic_only_clean_files_returns_0(tmp_path, monkeypatch):
    _bypass_dotenv(monkeypatch)
    cfg = _write_config(tmp_path)
    rc = run_cli([str(cfg)])
    assert rc == 0
    assert (tmp_path / "report.json").is_file()
    parsed = json.loads((tmp_path / "report.json").read_text())
    assert parsed["verdict"] == "approve"


def test_cli_writes_markdown_when_output_md_set(tmp_path, monkeypatch):
    _bypass_dotenv(monkeypatch)
    md_path = tmp_path / "report.md"
    cfg = _write_config(tmp_path, output_md=str(md_path))
    rc = run_cli([str(cfg)])
    assert rc == 0
    assert md_path.is_file()
    body = md_path.read_text()
    assert "## 1. Governing Thought" in body
    assert "## 10. Metadata" in body


def test_cli_overrides_with_deterministic_only_flag(tmp_path, monkeypatch):
    """--deterministic-only forces the deterministic path even if config disagrees."""
    _bypass_dotenv(monkeypatch)
    monkeypatch.setenv("MODEL_NAME", "anthropic/claude-3-haiku-20240307")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cfg = _write_config(tmp_path, deterministic_only=False)
    rc = run_cli([str(cfg), "--deterministic-only"])
    assert rc == 0


def test_llm_path_with_mocked_llm_writes_report(tmp_path, monkeypatch):
    _bypass_dotenv(monkeypatch)
    monkeypatch.setenv("MODEL_NAME", "openai/gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    minimal = {
        "verdict": "approve",
        "statement": "fixture-ok",
        "confidence": 0.9,
        "dimensions": [],
        "gaps": [],
        "validation_log": [],
        "files_reviewed": [],
    }
    fake_llm = MagicMock()
    fake_llm.invoke = AsyncMock(return_value=MagicMock(content=json.dumps(minimal)))

    cfg = _write_config(tmp_path, deterministic_only=False)
    with patch(
        "meta.CodeReviewerAgentTest.runner.LLMService", return_value=fake_llm
    ):
        rc = run_cli([str(cfg)])

    assert rc == 0
    parsed = json.loads(Path(json.loads(cfg.read_text())["output_json"]).read_text())
    assert parsed["verdict"] == "approve"
