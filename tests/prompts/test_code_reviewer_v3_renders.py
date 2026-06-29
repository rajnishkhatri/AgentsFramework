"""Render tests for the unified context-routed reviewer v3 bundle (WI-3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined, UndefinedError

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

V3_DIR = PROMPTS_DIR / "codeReviewer" / "v3"


@pytest.fixture
def jinja_env() -> Environment:
    # StrictUndefined mirrors the real PromptService — an unguarded missing var
    # must raise here so a lenient bare env cannot false-green a template that
    # PromptService would reject at runtime.
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        undefined=StrictUndefined,
    )


def test_system_prompt_renders_with_include(jinja_env: Environment) -> None:
    template = jinja_env.get_template("codeReviewer/v3/CodeReviewer_system_prompt.j2")
    try:
        rendered = template.render()
    except UndefinedError as exc:
        pytest.fail(f"v3 system prompt raised UndefinedError: {exc}")
    assert rendered.strip()
    # The architecture-rules include must be pulled in.
    assert "Dependency Table" in rendered
    assert "Routed enforcement map" in rendered


def test_submission_renders_with_routed_groups(jinja_env: Environment) -> None:
    template = jinja_env.get_template(
        "codeReviewer/v3/CodeReviewer_review_submission.j2"
    )
    try:
        rendered = template.render(
            submission_context="diff review",
            review_scope="routed",
            deterministic_findings='[{"rule_id": "DEP.trust_no_upward"}]',
            routed_groups=[
                {
                    "rules_file": "trust/REVIEW.md",
                    "language": "backend",
                    "rules_file_content": "| rule_id | source | detection |",
                    "files": [
                        {
                            "path": "trust/signature.py",
                            "folder": "trust",
                            "language": "backend",
                            "language_hint": "python",
                            "content": "def compute_signature(): ...",
                        }
                    ],
                },
                {
                    "rules_file": "frontend/REVIEW.md",
                    "language": "frontend",
                    "rules_file_content": "| FD3 Security | ... |",
                    "files": [
                        {
                            "path": "frontend/app/page.tsx",
                            "folder": "frontend",
                            "language": "frontend",
                            "language_hint": "tsx",
                            "content": "export default function Page() {}",
                        }
                    ],
                },
            ],
        )
    except UndefinedError as exc:
        pytest.fail(f"v3 submission raised UndefinedError: {exc}")
    assert "trust/REVIEW.md" in rendered
    assert "frontend/REVIEW.md" in rendered
    assert "DEP.trust_no_upward" in rendered


def test_submission_renders_without_optional_blocks(jinja_env: Environment) -> None:
    """No deterministic findings and no groups must still render cleanly."""
    template = jinja_env.get_template(
        "codeReviewer/v3/CodeReviewer_review_submission.j2"
    )
    rendered = template.render(routed_groups=[])
    assert rendered.strip()
    # The optional pre-computed-findings *section heading* must be absent when no
    # deterministic findings are passed (the word may still appear in Instructions).
    assert "## Pre-computed deterministic findings" not in rendered


def test_v3_system_prompt_folds_tap_and_fd(jinja_env: Environment) -> None:
    content = (V3_DIR / "CodeReviewer_system_prompt.j2").read_text()
    for marker in ["TAP-1", "TAP-2", "TAP-3", "TAP-4", "FD1", "FD7", "ADR.1"]:
        assert marker in content, f"Expected v3 marker missing: {marker}"
    # FD7 auto-reject anti-patterns are named.
    for ap in ["FE-AP-4", "FE-AP-18"]:
        assert ap in content, f"Expected FD7 auto-reject marker missing: {ap}"
