"""L2 contract tests for docs/recipes/governance/ tutorial series.

Sprint F of the BlackBox→Langfuse plan.

Validates that the governance recipe documentation:
  - References files that actually exist in the repo.
  - Contains required structural elements (status banner, lessons,
    checkpoint questions, mermaid diagrams, next-recipe links).
  - Code snippets reference real symbols from the implementation.
  - Architecture layering claims are accurate.
  - Recipes link to each other in the correct sequence.

These tests are deterministic (L2, no I/O beyond filesystem reads).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
RECIPE_DIR = AGENT_ROOT / "docs" / "recipes" / "governance"

RECIPE_FILES = [
    "00_overview.md",
    "01_outbox_relay.md",
    "02_event_mapping.md",
    "03_compliance_dataset.md",
]


# ── Helpers ──────────────────────────────────────────────────────────


def _read_recipe(filename: str) -> str:
    path = RECIPE_DIR / filename
    assert path.exists(), f"Recipe file missing: {path}"
    return path.read_text(encoding="utf-8")


def _extract_relative_links(text: str) -> list[str]:
    """Extract markdown relative links (not http/https)."""
    pattern = r"\[.*?\]\((?!https?://)(.*?)\)"
    return re.findall(pattern, text)


def _extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """Return (language, body) pairs for fenced code blocks."""
    pattern = r"```(\w*)\n(.*?)```"
    return re.findall(pattern, text, re.DOTALL)


# ── Test: all recipe files exist ─────────────────────────────────────


class TestRecipeFilesExist:
    @pytest.mark.parametrize("filename", RECIPE_FILES)
    def test_recipe_file_exists(self, filename: str) -> None:
        path = RECIPE_DIR / filename
        assert path.exists(), f"Missing recipe: {filename}"


# ── Test: structural elements ────────────────────────────────────────


class TestRecipeStructure:
    @pytest.mark.parametrize("filename", RECIPE_FILES)
    def test_has_status_banner(self, filename: str) -> None:
        text = _read_recipe(filename)
        assert "**Status:**" in text, f"{filename} missing status banner"

    @pytest.mark.parametrize("filename", RECIPE_FILES[1:])  # skip overview
    def test_has_lessons(self, filename: str) -> None:
        text = _read_recipe(filename)
        assert "### Lesson" in text, f"{filename} missing lesson sections"

    @pytest.mark.parametrize("filename", RECIPE_FILES[1:])
    def test_has_checkpoint_questions(self, filename: str) -> None:
        text = _read_recipe(filename)
        assert "Checkpoint question" in text, f"{filename} missing checkpoint questions"

    @pytest.mark.parametrize("filename", RECIPE_FILES[1:])
    def test_has_mermaid_diagram(self, filename: str) -> None:
        text = _read_recipe(filename)
        assert "```mermaid" in text, f"{filename} missing mermaid diagram"

    @pytest.mark.parametrize("filename", RECIPE_FILES[:-1])  # all but last
    def test_links_to_next_recipe(self, filename: str) -> None:
        text = _read_recipe(filename)
        idx = RECIPE_FILES.index(filename)
        next_file = RECIPE_FILES[idx + 1]
        assert next_file in text, f"{filename} does not link to next recipe {next_file}"


# ── Test: file references resolve ────────────────────────────────────


class TestFileReferencesResolve:
    """Relative links in recipes must point to existing files."""

    @pytest.mark.parametrize("filename", RECIPE_FILES)
    def test_relative_links_resolve(self, filename: str) -> None:
        text = _read_recipe(filename)
        links = _extract_relative_links(text)
        recipe_path = RECIPE_DIR / filename

        unresolved = []
        for link in links:
            clean = link.split("#")[0].split("?")[0]
            if not clean:
                continue
            target = (recipe_path.parent / clean).resolve()
            if not target.exists():
                unresolved.append(link)

        assert not unresolved, f"{filename} has unresolvable links:\n" + "\n".join(
            f"  - {l}" for l in unresolved
        )


# ── Test: code snippets reference real modules ───────────────────────


class TestCodeSnippetAccuracy:
    """Python code blocks in recipes must reference real project symbols."""

    def test_publisher_mapping_in_02(self) -> None:
        """02_event_mapping.md must show the real EVENT_TYPE_TO_OBSERVATION dict."""
        text = _read_recipe("02_event_mapping.md")
        assert "EventType.TASK_STARTED" in text
        assert "EventType.TASK_COMPLETED" in text
        assert "EventType.ERROR_OCCURRED" in text

    def test_relay_class_in_01(self) -> None:
        """01_outbox_relay.md must reference BlackBoxToTelemetryRelay."""
        text = _read_recipe("01_outbox_relay.md")
        assert "BlackBoxToTelemetryRelay" in text
        assert "run_once" in text
        assert ".langfuse_offset" in text

    def test_compliance_publisher_in_03(self) -> None:
        """03_compliance_dataset.md must reference the CompliancePublisher port."""
        text = _read_recipe("03_compliance_dataset.md")
        assert "CompliancePublisher" in text
        assert "agent-compliance-audit" in text
        assert "agent-incident-replay" in text
        assert "hash_chain_valid" in text

    def test_redact_details_in_02(self) -> None:
        """02_event_mapping.md must reference the redaction function."""
        text = _read_recipe("02_event_mapping.md")
        assert "redact_details" in text

    def test_overview_references_black_box(self) -> None:
        """00_overview.md must reference the BlackBoxRecorder."""
        text = _read_recipe("00_overview.md")
        assert "BlackBoxRecorder" in text


# ── Test: architecture claims ────────────────────────────────────────


class TestArchitectureClaims:
    """Verify that layering claims in the recipes are accurate."""

    def test_publisher_has_no_sdk_imports(self) -> None:
        """The publisher is claimed to have zero SDK imports -- verify."""
        publisher_path = (
            AGENT_ROOT / "services" / "governance" / "black_box_publisher.py"
        )
        assert publisher_path.exists()
        tree = ast.parse(publisher_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("langfuse"), (
                    "black_box_publisher.py must not import langfuse"
                )

    def test_relay_has_no_sdk_imports(self) -> None:
        """The relay is claimed to use ports, never SDK directly -- verify."""
        relay_path = (
            AGENT_ROOT / "middleware" / "sidecars" / "black_box_to_telemetry.py"
        )
        assert relay_path.exists()
        tree = ast.parse(relay_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("langfuse"), (
                    "black_box_to_telemetry.py must not import langfuse"
                )

    def test_compliance_port_has_no_sdk_imports(self) -> None:
        """CompliancePublisher protocol must be SDK-free."""
        port_path = AGENT_ROOT / "middleware" / "ports" / "compliance_publisher.py"
        assert port_path.exists()
        tree = ast.parse(port_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("langfuse"), (
                    "compliance_publisher.py must not import langfuse"
                )


# ── Test: recipe sequence and cross-links ────────────────────────────


class TestRecipeSequence:
    def test_overview_is_first(self) -> None:
        text = _read_recipe("00_overview.md")
        assert "Series" in text or "series" in text or "overview" in text.lower()

    def test_recipes_form_linked_chain(self) -> None:
        for i, filename in enumerate(RECIPE_FILES[:-1]):
            text = _read_recipe(filename)
            next_file = RECIPE_FILES[i + 1]
            assert next_file in text, (
                f"Chain broken: {filename} does not link to {next_file}"
            )

    def test_last_recipe_does_not_link_to_nonexistent(self) -> None:
        text = _read_recipe(RECIPE_FILES[-1])
        assert "04_" not in text, "Last recipe should not link to 04_*"


# ── Test: recipes mention test counts ────────────────────────────────


class TestRecipeMentionsTests:
    """Each recipe ending should reference passing contract tests."""

    @pytest.mark.parametrize("filename", RECIPE_FILES[1:])
    def test_mentions_test_count(self, filename: str) -> None:
        text = _read_recipe(filename)
        assert re.search(r"\d+\s*(contract\s+)?tests?\s+pass", text, re.IGNORECASE), (
            f"{filename} should mention passing test count in status banner"
        )
