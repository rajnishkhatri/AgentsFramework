"""Coach-context prompt formatter (framework-agnostic, ADR-0012).

The OBP-1 counterpart of ``components/memory_context.render_recall_block``
for the Subject-Coach's two-layer context assembly: the BFF sanitizer
(frontend/lib/translators/coach_context_sanitizer.ts) derives the
authoritative mode and strips the four answer-bearing ``Question`` fields
pre-submit; this formatter turns the surviving ``coach_context`` state
channel into the ``additional_instructions`` block the persona's mode
contract reads (prompts/subject_coach_system_prompt.j2).

Defense in depth: the formatter RE-strips the answer-bearing fields whenever
the mode is not exactly ``post_feedback`` — a payload that evaded the BFF
strip still renders leak-free — and an unknown/missing mode fails closed to
``pre_submit`` (the ADR-0012 posture).

Layer rules (I-1/I-3/I-5): no langgraph/langchain/orchestration imports.
Pure function, deterministic, zero-flake. Never logs (question payloads are
learner-facing content).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Mirror of frontend/lib/wire/engine_entities.QUESTION_ANSWER_BEARING_FIELDS —
# the four fields ADR-0012 withholds pre-submit. Kept literal here (not
# imported) because this is the Python plane's independent second layer.
_ANSWER_BEARING_FIELDS: tuple[str, ...] = (
    "answer_letter",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
)

_HEADER = "### Coaching context"


def _derive_mode(context: Mapping[str, Any]) -> str:
    """Unknown, missing, or advisory-spoofed mode ⇒ pre_submit (fail closed)."""
    return "post_feedback" if context.get("mode") == "post_feedback" else "pre_submit"


def coach_context_contract(context: Any) -> dict[str, Any] | None:
    """The auditable facts of the two-layer assembly (§13 audit finding F1).

    ``None`` when there is no coach context (non-coach runs record nothing).
    Otherwise the payload the orchestrator records as ONE ``guardrail_checked``
    carrier per coach turn: the fail-closed ``mode`` the renderer will apply,
    which answer-bearing fields will render (post-feedback only), and which
    were withheld — so an evaded BFF strip is visible in the trace instead of
    silently absorbed by the re-strip.
    """
    if not isinstance(context, Mapping) or not context:
        return None
    mode = _derive_mode(context)
    question = context.get("question")
    present = (
        [f for f in _ANSWER_BEARING_FIELDS if question.get(f)]
        if isinstance(question, Mapping)
        else []
    )
    return {
        "mode": mode,
        "answer_fields_rendered": present if mode == "post_feedback" else [],
        "answer_fields_stripped": [] if mode == "post_feedback" else present,
    }


def render_coach_context_block(
    context: Mapping[str, Any] | None,
    hint_rungs: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Sanitized ``coach_context`` → an ``additional_instructions`` block.

    Returns the empty string for ``None``/empty/non-mapping input so the
    caller appends nothing and the system prompt stays byte-identical for
    every non-coach run (the ``render_recall_block`` no-op shape).

    ``hint_rungs`` (Phase 4, FR-20): the question's REVIEWED ladder, passed by
    the orchestrator (peer components never import each other — invariant #5).
    Rendered in pre-submit mode only, with the select-and-paraphrase rule the
    persona's mode contract names — a persona with no rungs free-generates,
    the Stage-0 rule-naming leak class. Post-feedback has the full rationale;
    the ladder is never rendered there. Empty/None ⇒ byte-identical output.
    """
    if not isinstance(context, Mapping) or not context:
        return ""

    mode = _derive_mode(context)

    lines = [f"{_HEADER} (mode: {mode})"]
    for key in ("question_id", "skill_id"):
        value = context.get(key)
        if isinstance(value, str) and value:
            lines.append(f"- {key}: {value}")

    question = context.get("question")
    if isinstance(question, Mapping):
        if mode != "post_feedback":
            question = {
                k: v for k, v in question.items() if k not in _ANSWER_BEARING_FIELDS
            }
        _render_question(lines, question, post_feedback=(mode == "post_feedback"))

    if mode != "post_feedback" and hint_rungs:
        lines.append(
            "- hint ladder (reviewed; select the ONE rung that matches the "
            "learner's impasse and paraphrase it — never invent a new hint):"
        )
        for rung in hint_rungs:
            if isinstance(rung, Mapping) and rung.get("body_md"):
                lines.append(f"  - rung {rung.get('rung', '?')}: {rung['body_md']}")

    return "\n".join(lines)


def _render_question(
    lines: list[str], question: Mapping[str, Any], *, post_feedback: bool
) -> None:
    if question.get("context_html"):
        lines.append(f"- passage: {question['context_html']}")
    if question.get("stem"):
        lines.append(f"- question: {question['stem']}")
    choices = question.get("choices")
    if isinstance(choices, list) and choices:
        lines.append("- choices:")
        for choice in choices:
            if isinstance(choice, Mapping):
                lines.append(
                    f"  - {choice.get('letter', '?')}) {choice.get('label', '')}"
                )
    if post_feedback:
        if question.get("answer_letter"):
            lines.append(f"- correct answer: {question['answer_letter']}")
        if question.get("why_correct_md"):
            lines.append(f"- why correct: {question['why_correct_md']}")
        if question.get("why_tempted_md"):
            lines.append(f"- why tempting: {question['why_tempted_md']}")
        rationale = question.get("per_choice_rationale")
        if isinstance(rationale, Mapping):
            lines.append("- per-choice rationale:")
            for letter, why in rationale.items():
                lines.append(f"  - {letter}: {why}")
    if question.get("rule_md"):
        lines.append(f"- rule: {question['rule_md']}")
