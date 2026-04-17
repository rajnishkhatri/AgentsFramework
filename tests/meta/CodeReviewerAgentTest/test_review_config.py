"""L1 tests for ``meta.CodeReviewerAgentTest.review_config.ReviewAgentConfig``.

Failure paths first: missing required fields and empty lists must be
rejected by the schema before we accept the canonical phase1 config.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meta.CodeReviewerAgentTest.review_config import ReviewAgentConfig

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PHASE1_CONFIG = (
    AGENT_ROOT / "meta" / "CodeReviewerAgentTest" / "configs" / "phase1.json"
)


def test_missing_name_is_rejected():
    with pytest.raises(ValidationError):
        ReviewAgentConfig.model_validate({
            "files": ["trust/__init__.py"],
            "output_json": "out.json",
        })


def test_missing_files_is_rejected():
    with pytest.raises(ValidationError):
        ReviewAgentConfig.model_validate({
            "name": "x",
            "output_json": "out.json",
        })


def test_empty_files_is_rejected():
    with pytest.raises(ValidationError):
        ReviewAgentConfig.model_validate({
            "name": "x",
            "files": [],
            "output_json": "out.json",
        })


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        ReviewAgentConfig.model_validate({
            "name": "x",
            "files": ["a.py"],
            "output_json": "out.json",
            "totally_unknown_field": True,
        })


def test_phase1_config_loads_clean():
    config = ReviewAgentConfig.from_path(PHASE1_CONFIG)
    assert config.name == "phase1-verification"
    assert config.model_env_var == "MODEL_NAME"
    assert "trust/__init__.py" in config.files
    assert config.output_json == "docs/PHASE1_CODE_REVIEW.json"
    assert config.output_md == "docs/PHASE1_CODE_REVIEW.md"
    assert config.md_template_section_overrides["phase_label"] == "Phase 1"


def test_minimal_config_round_trips(tmp_path):
    cfg = {
        "name": "tiny",
        "files": ["trust/enums.py"],
        "output_json": "docs/tiny.json",
    }
    p = tmp_path / "tiny.json"
    p.write_text(json.dumps(cfg))
    parsed = ReviewAgentConfig.from_path(p)
    assert parsed.deterministic_only is False
    assert parsed.user_id == "code-reviewer"
    assert parsed.output_md is None
