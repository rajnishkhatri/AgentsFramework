"""C1 Phase 8 — H1 contract for the compaction-fidelity judge prompt.

Design §8.3 binds two AGENTS.md rules to the L2 judge:

1. **H1 / AP-3 — no hardcoded prompts.** The rubric is authored as a Jinja2
   template ``prompts/compaction_fidelity_judge.j2`` and rendered via
   ``PromptService.render_prompt()``. NEVER an inline Python f-string.
2. The judge prompt is **analytic** (per-criterion: decision-loss vs
   constraint-loss) + **evidence-grounded** (cite the dropped span) +
   **binary** (per R5 / R15). It is *not* calibrated in v1 (PROVISIONAL).

These tests pin the H1 contract (template lives at the right path, renders
via PromptService, includes the load-bearing rubric anchors) without
calling an LLM.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.prompt_service import PromptService


_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@pytest.fixture
def svc() -> PromptService:
    return PromptService(template_dir=str(_PROMPTS_DIR))


class TestCompactionFidelityPromptH1:
    def test_template_file_exists_at_canonical_path(self) -> None:
        """The rubric MUST be a .j2 template file — not a Python string.
        Per H1: every LLM prompt is rendered, never f-string'd."""
        assert (_PROMPTS_DIR / "compaction_fidelity_judge.j2").exists(), (
            "prompts/compaction_fidelity_judge.j2 must exist — design §8.3 H1"
        )

    def test_renders_via_prompt_service(self, svc: PromptService) -> None:
        """The template renders with all required context variables."""
        rendered = svc.render_prompt(
            "compaction_fidelity_judge",
            task_input="redact API keys from foo.txt",
            dropped_prefix_digest="sha256:abc123",
            pinned_constraints=["never delete files"],
            summary="SUMMARY:\n  redacted API keys on lines 4,7\n",
        )
        assert isinstance(rendered, str)
        assert rendered.strip(), "rendered prompt must not be empty"

    def test_includes_load_bearing_rubric_anchors(self, svc: PromptService) -> None:
        """The judge rubric ships per-criterion + evidence-grounded +
        binary (design §8.3 / R5 R15). Pin the verdict-key anchors so a
        future refactor can't silently flatten the rubric."""
        rendered = svc.render_prompt(
            "compaction_fidelity_judge",
            task_input="x",
            dropped_prefix_digest="sha256:0",
            pinned_constraints=[],
            summary="s",
        )
        # The three verdict keys named in design §8.3.
        for token in ("decision_loss", "constraint_loss", "unsafe_fold"):
            assert token in rendered, (
                f"rubric anchor {token!r} missing — design §8.3 names this "
                "as a required verdict key"
            )

    def test_renders_pinned_constraints_verbatim(self, svc: PromptService) -> None:
        """Constraints are verbatim (design §4 fn 3 / §B2-R): the rendered
        rubric must reflect what the judge will actually see, no munging."""
        rendered = svc.render_prompt(
            "compaction_fidelity_judge",
            task_input="x",
            dropped_prefix_digest="sha256:0",
            pinned_constraints=["DO NOT DELETE /etc/hosts", "never run rm -rf /"],
            summary="s",
        )
        assert "DO NOT DELETE /etc/hosts" in rendered
        assert "never run rm -rf /" in rendered

    def test_handles_empty_constraints(self, svc: PromptService) -> None:
        """A fold with zero pinned constraints (no task_understanding
        success_conditions) is a real path — the template must render."""
        rendered = svc.render_prompt(
            "compaction_fidelity_judge",
            task_input="x",
            dropped_prefix_digest="sha256:0",
            pinned_constraints=[],
            summary="s",
        )
        assert rendered.strip()

    def test_no_python_file_inlines_the_judge_prompt(self) -> None:
        """H1 anti-pattern guard: no Python source builds the *judge prompt*
        by string concatenation. The judge prompt is unmistakable — it
        contains the phrase ``"rigorous, impartial evaluation judge"``
        verbatim (mirroring the goal_judge prompt's opening). Any Python
        file containing this phrase outside a ``.j2`` template is a
        hardcoded prompt."""
        repo_root = _PROMPTS_DIR.parent
        # This phrase is the judge prompt's distinctive opening — it
        # cannot appear in a dict-key payload or a comment by accident.
        judge_marker = "rigorous, impartial evaluation judge"
        for sub in ("orchestration", "services", "middleware"):
            for py in (repo_root / sub).rglob("*.py"):
                text = py.read_text()
                assert judge_marker not in text, (
                    f"{py} inlines the judge prompt as Python — design "
                    "§8.3 forbids this (H1). Move it to a .j2 template."
                )
