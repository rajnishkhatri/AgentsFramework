"""L2 Contract: subject-coach persona template (FR-10/FR-11, ADR-0012).

Structural assertions only — section markers and directives, never exact
LLM-output strings (TAP-3 determinism theater). The persona is the coach's
anti-leakage stance in prompt form; the Pedagogy judge (Phase 2) measures
whether the model honors it.

H1: the persona is a ``.j2`` in ``prompts/`` rendered via
``PromptService.render_prompt()`` — no prompt strings in ``.py``.
"""

from __future__ import annotations

from services.prompt_service import PromptService


def _render(subject: str = "English") -> str:
    return PromptService().render_prompt("subject_coach_system_prompt", subject=subject)


class TestAntiLeakageStance:
    """FR-11 failure-path stance FIRST: the persona must forbid answer-reveal."""

    def test_persona_forbids_revealing_the_answer(self):
        rendered = _render().lower()
        assert "never" in rendered and "answer" in rendered, (
            "persona must carry an explicit never-reveal-the-answer directive"
        )

    def test_persona_names_the_adversarial_refusal_case(self):
        # The guardrail ADMITS "just tell me the answer" (on-topic); the
        # persona is what refuses to leak (agent spec §6 edge case).
        rendered = _render().lower()
        assert "just tell me" in rendered

    def test_persona_preserves_productive_struggle(self):
        rendered = _render().lower()
        assert "productive struggle" in rendered


class TestPedagogyMoves:
    """FR-10: the four ratified pedagogy moves are all present."""

    def test_teach_back_feynman(self):
        rendered = _render().lower()
        assert "teach-back" in rendered or "explain your reasoning" in rendered

    def test_analogy_first(self):
        assert "analog" in _render().lower()

    def test_name_the_why(self):
        # Oakley/FSRS: say WHY a skill is being revisited.
        rendered = _render().lower()
        assert "why" in rendered and "revisit" in rendered

    def test_mode_block_covers_both_contract_modes(self):
        # ADR-0012: the persona instructs differently pre-submit vs
        # post-feedback; both mode names must appear.
        rendered = _render().lower()
        assert "pre-submit" in rendered
        assert "post-feedback" in rendered


class TestSubjectParameterization:
    def test_subject_is_rendered(self):
        assert "English" in _render(subject="English")
        assert "Math" in _render(subject="Math")


class TestConfigSeam:
    """FR-10: the persona rides AgentConfig.additional_instructions."""

    def test_agent_config_carries_additional_instructions(self):
        from services.base_config import AgentConfig

        cfg = AgentConfig(additional_instructions="PERSONA-MARKER")
        assert cfg.additional_instructions == "PERSONA-MARKER"

    def test_default_is_empty_byte_identical(self):
        from services.base_config import AgentConfig

        assert AgentConfig().additional_instructions == ""

    def test_coach_factory_accepts_persona_override(self):
        from services.governance.subject_coach_identity import (
            subject_coach_agent_config,
        )

        persona = _render()
        cfg = subject_coach_agent_config(additional_instructions=persona)
        assert cfg.additional_instructions == persona
