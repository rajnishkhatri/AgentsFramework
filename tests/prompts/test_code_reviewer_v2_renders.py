"""Golden-file tests for codeReviewer v2 template rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, UndefinedError

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

TEMPLATES = [
    "codeReviewer/v2/CodeReviewer_system_prompt.j2",
    "codeReviewer/v2/CodeReviewer_architecture_rules.j2",
    "codeReviewer/v2/CodeReviewer_review_submission.j2",
]


@pytest.fixture
def jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(PROMPTS_DIR)))


@pytest.mark.parametrize("template_path", TEMPLATES)
def test_template_renders_without_undefined_error(
    jinja_env: Environment, template_path: str
) -> None:
    template = jinja_env.get_template(template_path)
    try:
        rendered = template.render(
            files_to_review=[
                {
                    "path": "meta/code_reviewer.py",
                    "content": "class CodeReviewerAgent: ...",
                    "layer": "meta",
                    "language": "python",
                    "lines_changed": "1-20",
                }
            ],
            submission_context="Sprint 4 rollout",
            review_scope="full",
        )
    except UndefinedError as exc:
        pytest.fail(f"Template {template_path} raised UndefinedError: {exc}")

    assert rendered.strip(), f"Template {template_path} rendered empty output"


def test_v2_rules_include_sprint4_hardening_requirements() -> None:
    rules_file = (
        PROMPTS_DIR / "codeReviewer" / "v2" / "CodeReviewer_architecture_rules.j2"
    )
    content = rules_file.read_text()
    for marker in [
        "PR.VER.1",
        "PR.VER.2",
        "PR.VER.3",
        "DEEP.DOCS.1",
        "DEEP.DOCS.2",
        "DEEP.CLEAN.1",
        "DEEP.CLEAN.2",
        "AP10",
    ]:
        assert marker in content, f"Expected v2 hardening marker missing: {marker}"
