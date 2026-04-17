"""Input/output validation.

``InputGuardrail`` uses LLM-as-judge (H3 pattern) to classify user input.
``OutputGuardrail`` runs a two-stage scan on an assistant response:

1. Deterministic stage — :class:`~services.governance.guardrail_validator.GuardRailValidator`
   applies regex rules (PII, API keys). Any CRITICAL ``BLOCK`` hit short-
   circuits to a sanitized message; ``REDACT``-action matches are replaced
   inline with the guardrail's redaction token.
2. LLM-judge stage — optional, gated behind an explicit flag so CI stays
   L2-pure. Intended for nightly runs.

Both guardrails log to the shared ``guards.log`` logger and emit a
:class:`GuardrailScanResult` describing the decision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from services.governance.guardrail_validator import (
    FailAction,
    GuardRailValidator,
    Severity,
    ValidationResult,
)

if TYPE_CHECKING:
    from services.base_config import ModelProfile
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

logger = logging.getLogger("services.guardrails")


class InputGuardrail:
    def __init__(
        self,
        name: str,
        accept_condition: str,
        llm_service: LLMService,
        prompt_service: PromptService,
        judge_profile: ModelProfile,
    ) -> None:
        self.name = name
        self._accept_condition = accept_condition
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._judge_profile = judge_profile

    async def is_acceptable(
        self,
        prompt: str,
        raise_exception: bool = False,
    ) -> bool:
        verdict = await self._call_judge(prompt)
        accepted = verdict.strip().lower() == "accept"

        logger.info(
            "Guardrail %s: %s",
            self.name,
            "accepted" if accepted else "rejected",
            extra={
                "guardrail": self.name,
                "accepted": accepted,
                "input_preview": prompt[:100],
            },
        )

        if not accepted and raise_exception:
            raise ValueError(
                f"Input rejected by guardrail '{self.name}': {prompt[:100]}..."
            )

        return accepted

    async def _call_judge(self, prompt: str) -> str:
        """Call LLM-as-judge with injected services."""
        rendered = self._prompt_service.render_prompt(
            "input_guardrail",
            accept_condition=self._accept_condition,
            user_input=prompt,
        )

        response = await self._llm_service.invoke(
            self._judge_profile,
            [{"role": "user", "content": rendered}],
        )
        return response.content


@dataclass
class GuardrailScanResult:
    blocked: bool
    sanitized_content: str
    rule_results: list[ValidationResult] = field(default_factory=list)
    llm_judge_verdict: str | None = None


def _sanitized_block_message(rule_name: str) -> str:
    return (
        "[blocked] This response was withheld because it matched the "
        f"'{rule_name}' guardrail."
    )


def output_guardrail_scan(
    response_text: str,
    validator: GuardRailValidator,
) -> GuardrailScanResult:
    """Run the deterministic output-scan stage.

    Returns a :class:`GuardrailScanResult`. If any ``BLOCK`` rule at
    ``HIGH`` or ``CRITICAL`` severity fires, ``blocked=True`` and the
    sanitized content is a short refusal citing the offending rule. For
    ``REDACT`` actions, the matches are replaced inline with each rule's
    redaction token and the call is not blocked.
    """
    results = validator.validate(response_text)

    blocking = [
        r
        for r in results
        if not r.passed
        and r.fail_action == FailAction.BLOCK
        and r.severity in (Severity.HIGH, Severity.CRITICAL)
    ]

    if blocking:
        first = blocking[0]
        logger.info(
            "Output guardrail blocked response: rule=%s severity=%s",
            first.guardrail_name,
            first.severity.value,
            extra={
                "rule": first.guardrail_name,
                "severity": first.severity.value,
                "action": first.fail_action.value,
            },
        )
        return GuardrailScanResult(
            blocked=True,
            sanitized_content=_sanitized_block_message(first.guardrail_name),
            rule_results=results,
        )

    sanitized = validator.redact(response_text)
    return GuardrailScanResult(
        blocked=False,
        sanitized_content=sanitized,
        rule_results=results,
    )


class OutputGuardrail:
    """LLM-judge wrapper for the optional nightly output-safety stage.

    Mirrors :class:`InputGuardrail`. Intended to be invoked explicitly from
    pipelines or nightly tests; ``call_llm_node`` does NOT invoke this in
    normal CI because of per-commit flake budget.
    """

    def __init__(
        self,
        name: str,
        accept_condition: str,
        llm_service: LLMService,
        prompt_service: PromptService,
        judge_profile: ModelProfile,
    ) -> None:
        self.name = name
        self._accept_condition = accept_condition
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._judge_profile = judge_profile

    async def is_acceptable(self, response_text: str) -> bool:
        rendered = self._prompt_service.render_prompt(
            "output_guardrail",
            accept_condition=self._accept_condition,
            response_text=response_text,
        )
        response = await self._llm_service.invoke(
            self._judge_profile,
            [{"role": "user", "content": rendered}],
        )
        verdict = (response.content or "").strip().lower()
        accepted = verdict == "accept"

        logger.info(
            "Output guardrail (LLM judge) %s: %s",
            self.name,
            "accepted" if accepted else "rejected",
            extra={
                "guardrail": self.name,
                "accepted": accepted,
                "response_preview": response_text[:100],
            },
        )
        return accepted
