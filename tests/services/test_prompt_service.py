"""L2 Reproducible: Tests for services/prompt_service.py.

Contract-driven TDD. Tests template rendering, missing template
handling, and variable injection. No I/O except Jinja2 filesystem
loader (deterministic).
"""

from __future__ import annotations

import pytest

from services.prompt_service import PromptService


@pytest.fixture
def svc(tmp_path):
    tmpl = tmp_path / "test_template.j2"
    tmpl.write_text("Hello {{ name }}, you are {{ role }}.")
    return PromptService(template_dir=str(tmp_path))


class TestPromptService:
    def test_render_basic(self, svc):
        result = svc.render_prompt("test_template", name="Alice", role="admin")
        assert result == "Hello Alice, you are admin."

    def test_render_missing_template_raises(self, svc):
        with pytest.raises(Exception):
            svc.render_prompt("nonexistent_template")

    def test_render_with_defaults(self, tmp_path):
        tmpl = tmp_path / "defaults.j2"
        tmpl.write_text("Value: {{ x | default('fallback') }}")
        svc = PromptService(template_dir=str(tmp_path))
        result = svc.render_prompt("defaults")
        assert result == "Value: fallback"

    def test_uses_real_prompts_dir(self):
        """Verify the default prompts/ directory contains system_prompt.j2."""
        from pathlib import Path

        prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        svc = PromptService(template_dir=str(prompts_dir))
        result = svc.render_prompt("system_prompt", additional_instructions="")
        assert "ReAct agent" in result
