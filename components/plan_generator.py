"""PlanGenerator — plan-time LLM decomposition into an ordered plan (Phase 1, T1).

Framework-agnostic: imports only same-layer ``components`` helpers and, under
``TYPE_CHECKING``, the injected ``services`` types. NO ``langgraph`` /
``langchain`` imports (AGENTS.md invariant #3). Mirrors
``components.task_understanding.TaskUnderstandingGenerator``: injected
``LLMService`` + ``PromptService`` + fast-tier ``ModelProfile``, renders a
``.j2`` prompt (H1), tolerant JSON extraction.

Contract
--------
``generate`` returns the raw decoded plan ``dict`` (or RAISES on an LLM /
parse error). It does NOT build, validate, or floor the artifact — that is
:func:`components.plan_builder.build_plan_artifact_llm`'s job, which owns the
deterministic floor fallback. Splitting the LLM boundary (this class) from the
parse/validate/floor (the pure ``plan_builder`` function) keeps ``plan_builder``
free of any LLM dependency and lets the floor be exercised in unit tests with a
plain callable, no mock LLM.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from components.plan_builder import PlanningDepth, build_planning_instructions

if TYPE_CHECKING:
    from services.base_config import ModelProfile
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

logger = logging.getLogger("components.plan_generator")

__all__ = ["PlanGenerator"]


def _extract_json(content: str) -> str:
    """Best-effort JSON-object extraction from a raw LLM response.

    Models wrap the object in prose or ```json fences; slice from the first ``{``
    to the last ``}``. Same tolerant strategy as the TaskUnderstanding generator.
    """
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


class PlanGenerator:
    """Fast-tier LLM generation of a raw ordered-plan ``dict``.

    Args:
        llm_service: injected ``LLMService`` (the only LLM boundary).
        prompt_service: injected ``PromptService`` for ``.j2`` rendering (H1).
        profile: fast-tier ``ModelProfile`` (H2).
        name: logging / eval-capture tag.
    """

    PROMPT_NAME = "plan_builder_prompt"

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        profile: ModelProfile,
        *,
        name: str = "plan_builder",
    ) -> None:
        self.name = name
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._profile = profile

    @property
    def model_name(self) -> str:
        return getattr(self._profile, "name", "")

    async def generate(
        self,
        *,
        task_input: str,
        planning_depth: PlanningDepth,
    ) -> dict:
        """Render the prompt, invoke the LLM, return the decoded plan dict.

        Raises on LLM-transport or malformed-JSON errors — the caller
        (``build_plan_artifact_llm`` via the orchestration node) catches and
        falls back to the deterministic floor.
        """
        rendered = self._prompt_service.render_prompt(
            self.PROMPT_NAME,
            task_input=task_input,
            planning_depth=planning_depth,
            depth_guidance=build_planning_instructions(
                planning_depth, task_input=task_input
            ),
        )
        response = await self._llm_service.invoke(
            self._profile,
            [{"role": "user", "content": rendered}],
        )
        content = str(getattr(response, "content", response))
        data = json.loads(_extract_json(content))
        if not isinstance(data, dict):
            raise ValueError("plan response is not a JSON object")
        return data
