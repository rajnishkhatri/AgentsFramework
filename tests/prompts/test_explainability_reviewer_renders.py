"""Golden-file tests: each explainability reviewer j2 renders without errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, UndefinedError

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

TEMPLATES = [
    "codeReviewer/explainability_frontend/system_prompt.j2",
    "codeReviewer/explainability_frontend/architecture_rules.j2",
    "codeReviewer/explainability_frontend/review_submission.j2",
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
                    "path": "frontend-explainability/lib/wire/responses.ts",
                    "content": "export const Foo = z.object({});",
                    "layer": "wire",
                    "language": "typescript",
                    "lines_changed": "1-5",
                }
            ],
            submission_context="Test submission",
            review_scope="full",
        )
    except UndefinedError as exc:
        pytest.fail(f"Template {template_path} raised UndefinedError: {exc}")

    assert len(rendered) > 0, f"Template {template_path} rendered empty output"


def test_no_frontend_lib_references_in_templates() -> None:
    """AC2: zero remaining frontend/lib/ references in the explainability reviewer."""
    templates_dir = PROMPTS_DIR / "codeReviewer" / "explainability_frontend"
    for j2_file in templates_dir.glob("*.j2"):
        content = j2_file.read_text()
        lines_with_violation = [
            (i + 1, line.strip())
            for i, line in enumerate(content.splitlines())
            if "frontend/lib/" in line and "frontend-explainability/lib/" not in line
        ]
        assert lines_with_violation == [], (
            f"{j2_file.name} contains 'frontend/lib/' references "
            f"(should be 'frontend-explainability/lib/'): {lines_with_violation}"
        )


def test_sdk_allowlist_present() -> None:
    """AC3: the seven UI libs are listed in architecture_rules.j2."""
    rules_file = (
        PROMPTS_DIR
        / "codeReviewer"
        / "explainability_frontend"
        / "architecture_rules.j2"
    )
    content = rules_file.read_text()
    expected_libs = [
        "recharts",
        "@visx/*",
        "reactflow",
        "@monaco-editor/react",
        "@tanstack/react-query",
        "@tanstack/react-table",
        "vis-network",
    ]
    for lib in expected_libs:
        assert lib in content, f"SDK allowlist missing {lib} in architecture_rules.j2"


def test_auto_reject_anti_patterns() -> None:
    """AC5: retained FE-AP-7, FE-AP-12, FE-AP-18, FE-AP-19; dropped FE-AP-4, FE-AP-6."""
    rules_file = (
        PROMPTS_DIR
        / "codeReviewer"
        / "explainability_frontend"
        / "architecture_rules.j2"
    )
    content = rules_file.read_text()

    for ap_id in ["FE-AP-7", "FE-AP-12", "FE-AP-18", "FE-AP-19"]:
        assert ap_id in content, f"Retained auto-reject {ap_id} missing"

    assert "FE-AP-4" in content, "FE-AP-4 should be mentioned (as dropped)"
    assert "FE-AP-6" in content, "FE-AP-6 should be mentioned (as dropped)"


def test_fd9_fd10_fd11_stubbed() -> None:
    """AC4: FD9, FD10, FD11 are stubbed as N/A."""
    rules_file = (
        PROMPTS_DIR
        / "codeReviewer"
        / "explainability_frontend"
        / "architecture_rules.j2"
    )
    content = rules_file.read_text()
    assert "FD9" in content and "N/A" in content
    assert "FD10" in content and "N/A" in content
    assert "FD11" in content and "N/A" in content


def test_sprint_story_acceptance_map_present() -> None:
    """AC6: Sprint Story Acceptance Map appendix lists explainability stories."""
    rules_file = (
        PROMPTS_DIR
        / "codeReviewer"
        / "explainability_frontend"
        / "architecture_rules.j2"
    )
    content = rules_file.read_text()
    assert "Sprint Story Acceptance Map" in content
    for story_id in ["S0.1.1", "S0.2.1", "S0.2.2", "S0.2.3", "S0.3.1", "S0.3.2", "S0.3.3"]:
        assert story_id in content, f"Story {story_id} missing from acceptance map"
