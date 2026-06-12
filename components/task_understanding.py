"""TaskUnderstanding generator — plan-time intent restatement + checklist (D1).

Framework-agnostic: imports only ``components.schemas`` (same layer) and, under
``TYPE_CHECKING``, the injected ``services`` types. NO ``langgraph`` /
``langchain`` imports (AGENTS.md invariant #3). Mirrors
``components.goal_judge.GoalJudge``: injected ``LLMService`` + ``PromptService``
+ fast-tier ``ModelProfile``, renders a ``.j2`` prompt (H1), tolerant JSON
extraction.

Why this exists
---------------
The Stage 6 replay audit (§3) found 100/100 production runs judged against the
same two generic success conditions — the judge was never told task-specific
completion criteria (judge-vs-gold α = 0.50). This component generates a
per-task ``TaskUnderstanding`` (TICK-style checklist, arXiv:2410.03608) once at
plan time, BEFORE the agent acts — pre-registration, never hindsight.

Contract (plan §4.2)
--------------------
``generate`` RAISES on any failure: LLM error, unparseable JSON, or a
validation-gate rejection. It never falls back itself — falling back to the
plan_builder floor would require a peer component import (forbidden). The
orchestration thin-wrapper owns the try/except fallback, exactly like the
GoalJudge best-effort contract.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from components.schemas import TaskUnderstanding

if TYPE_CHECKING:
    from services.base_config import ModelProfile
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

logger = logging.getLogger("components.task_understanding")

__all__ = [
    "GENERIC_TAIL_CONDITION",
    "TaskUnderstandingGenerator",
    "TaskUnderstandingValidationError",
    "validate_conditions",
]

# Always appended after the generated/derived conditions. Matches the judge
# prompt's "supplemental constraints" framing and guarantees the artifact can
# never carry an empty checklist.
GENERIC_TAIL_CONDITION = (
    "The final answer is internally consistent and directly responds to the request."
)

_MIN_CONDITIONS = 2
_MAX_CONDITIONS = 7
_MAX_CONDITION_LEN = 200

# Minimal English stopword set for the lexical-grounding gate. Deterministic
# proxy for "this condition is about THIS task" — a hallucinated off-topic
# condition shares no content token with the task text.
_STOPWORDS = frozenset(
    """a an and are as at be been by for from has have in into is it its of on
    or that the their then there these this to was were will with without not
    no do does did done must should can could would you your the final answer
    agent task""".split()
)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9._/-]*")


class TaskUnderstandingValidationError(ValueError):
    """A generated checklist failed one or more anti-hallucination gates."""

    def __init__(self, issues: list[str]) -> None:
        super().__init__("; ".join(issues))
        self.issues = issues


def _content_tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}


def validate_conditions(
    conditions: list[str],
    *,
    task_input: str,
    source: str = "generated",
) -> list[str]:
    """Run the deterministic anti-hallucination gates; return issue strings.

    Gates (plan §4.2): count 2–7, length ≤200 chars each, lexical grounding
    vs the task text, normalized dedupe. ``user_edited`` conditions skip
    grounding (the human is the authority) but keep the count/length bounds.
    An empty result means all gates passed.
    """
    issues: list[str] = []
    if not (_MIN_CONDITIONS <= len(conditions) <= _MAX_CONDITIONS):
        issues.append(
            f"count gate: expected {_MIN_CONDITIONS}-{_MAX_CONDITIONS} "
            f"conditions, got {len(conditions)}"
        )
    for index, condition in enumerate(conditions):
        if len(condition) > _MAX_CONDITION_LEN:
            issues.append(
                f"length gate: condition {index} is {len(condition)} chars "
                f"(max {_MAX_CONDITION_LEN})"
            )
    if source != "user_edited":
        task_tokens = _content_tokens(task_input)
        for index, condition in enumerate(conditions):
            if task_tokens and not (_content_tokens(condition) & task_tokens):
                issues.append(
                    f"grounding gate: condition {index} shares no content "
                    "token with the task input"
                )
    normalized = [" ".join(c.lower().split()) for c in conditions]
    if len(normalized) != len(set(normalized)):
        issues.append("duplicate gate: normalized conditions are not unique")
    return issues


class TaskUnderstandingGenerator:
    """Fast-tier LLM generation of a per-task ``TaskUnderstanding`` artifact.

    Args:
        llm_service: injected ``LLMService`` (the only LLM boundary).
        prompt_service: injected ``PromptService`` for ``.j2`` rendering (H1).
        profile: fast-tier ``ModelProfile`` (H2).
        name: logging / eval-capture tag.
    """

    PROMPT_NAME = "task_understanding_prompt"

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        profile: ModelProfile,
        *,
        name: str = "task_understanding",
    ) -> None:
        self.name = name
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._profile = profile

    @property
    def model_name(self) -> str:
        return getattr(self._profile, "name", "")

    async def generate(self, *, task_input: str) -> TaskUnderstanding:
        """Generate, gate-validate, and return the artifact. Raises on failure."""
        rendered = self._prompt_service.render_prompt(
            self.PROMPT_NAME,
            task_input=task_input,
        )
        response = await self._llm_service.invoke(
            self._profile,
            [{"role": "user", "content": rendered}],
        )
        content = str(getattr(response, "content", response))
        data = json.loads(_extract_json(content))
        if not isinstance(data, dict):
            raise ValueError("task understanding response is not a JSON object")

        conditions = data.get("success_conditions")
        if not isinstance(conditions, list):
            raise ValueError("success_conditions is not a list")
        conditions = [str(c).strip() for c in conditions if str(c).strip()]

        issues = validate_conditions(conditions, task_input=task_input)
        if issues:
            raise TaskUnderstandingValidationError(issues)

        if GENERIC_TAIL_CONDITION not in conditions:
            conditions = [*conditions, GENERIC_TAIL_CONDITION]

        confidence = data.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        return TaskUnderstanding(
            restated_intent=str(data.get("restated_intent", "")).strip(),
            success_conditions=conditions,
            confidence=max(0.0, min(1.0, confidence)),
            source="generated",
            model=self.model_name,
        )


def _extract_json(content: str) -> str:
    """Return the JSON substring from a possibly fenced / chatty response."""
    text = content.strip()
    if "```" in text:
        fenced = text.split("```", 2)
        if len(fenced) >= 2:
            block = fenced[1]
            if block.lstrip().lower().startswith("json"):
                block = block.lstrip()[4:]
            text = block.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
