"""GoalJudge — task-adaptive LLM-as-judge for goal satisfaction (I2).

Framework-agnostic: imports only from ``components.schemas`` (same layer) and,
under ``TYPE_CHECKING``, the injected ``services`` types. NO ``langgraph`` /
``langchain`` imports (AGENTS.md invariant #3). Mirrors
``services.guardrails.InputGuardrail``: it takes an injected ``LLMService`` +
``PromptService`` + ``ModelProfile``, renders a ``.j2`` prompt (H1), calls
``llm_service.invoke`` (H2 fast tier), and parses a structured JSON verdict.

Why this exists
---------------
``evaluate_task_outcome`` scores ``goal_met``/``criteria_met`` via keyword
overlap against two fixed generic strings from ``plan_builder``. Those never
share vocabulary with a real answer, so ``criteria_met`` is ~always ``0.0`` and
``unmet_conditions`` is identical on good and bad runs. Keyword/overlap metrics
are blind to goal-directed reasoning; goal satisfaction needs a task-adaptive
judge (reference-free rubric over the final answer + trajectory evidence).

Layering contract
-----------------
The judge overlays ``goal_met``/``criteria_met``/``unmet_conditions`` onto the
``TaskOutcome``. It NEVER changes ``outcome``: the deterministic process floor
("ran cleanly") stays the gating signal. The keyword heuristic remains the
offline/CI fallback (AGENTS.md: no live LLM in CI), so the judge is injectable,
flag-gated, and mockable.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from components.answer_verifiers import verify_answer
from components.schemas import GENERIC_TAIL_CONDITION, GoalVerdict

if TYPE_CHECKING:
    from services.base_config import ModelProfile
    from services.governance.guardrail_validator import GuardRailValidator
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

logger = logging.getLogger("components.goal_judge")

__all__ = ["GoalJudge"]


class GoalJudge:
    """Reference-free LLM-as-judge that scores goal satisfaction.

    Args:
        llm_service: injected ``LLMService`` (the only LLM boundary).
        prompt_service: injected ``PromptService`` for ``.j2`` rendering (H1).
        judge_profile: fast-tier ``ModelProfile`` (H2).
        redactor: optional ``GuardRailValidator`` (L2). When present, every
            evidence-digest line is passed through ``redactor.redact(line)``
            so PII / secrets in the tool trajectory never reach the judge
            prompt. Constructed at the graph-build boundary; ``None`` keeps
            the judge a pure L3 unit in CI.
        name: logging / eval-capture tag.
    """

    PROMPT_NAME = "goal_judge_system_prompt"

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        judge_profile: ModelProfile,
        *,
        redactor: GuardRailValidator | None = None,
        name: str = "goal_judge",
    ) -> None:
        self.name = name
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._judge_profile = judge_profile
        self._redactor = redactor

    @property
    def model_name(self) -> str:
        return getattr(self._judge_profile, "name", "")

    async def evaluate(
        self,
        *,
        task_input: str,
        final_answer: str,
        success_conditions: list[str],
        evidence: list[dict[str, Any]] | None = None,
    ) -> GoalVerdict:
        """Judge whether ``final_answer`` satisfies the task goal.

        Builds a compact evidence digest from the tool trajectory, renders the
        rubric prompt, invokes the judge model, and parses the JSON verdict.
        Raises on an unparseable response so the caller can fall back to the
        deterministic heuristic (the judge is best-effort, never load-bearing).
        """
        # Correctness cascade (priority-cascade pattern): for tasks with a
        # checkable answer, a deterministic verifier owns the goal_met verdict —
        # the LLM rubric grades process-presence and was observed to score a
        # REVERSED topological sort 1.0 while failing a correct one for not
        # echoing it. ``verify_answer`` returns a bool only when it can validate
        # the result against the task's own constraints; otherwise ``None`` and
        # we fall through to the LLM judge (never averaging the two — the
        # deterministic verdict is authoritative when it fires).
        verified = verify_answer(task_input, final_answer, evidence)
        if verified is not None:
            return GoalVerdict(
                goal_met=verified,
                criteria_met=1.0 if verified else 0.0,
                rationale=(
                    "Deterministic verifier: the produced result "
                    + ("satisfies" if verified else "violates")
                    + " the task's stated constraints."
                ),
                verifier_source="deterministic",
            )

        # Append the generic consistency criterion at JUDGE-TIME (it grades the
        # final answer, so it belongs here — not in the plan-time checklist).
        # Idempotent: callers that already include it are not double-scored.
        scored_conditions = list(success_conditions)
        if GENERIC_TAIL_CONDITION not in scored_conditions:
            scored_conditions.append(GENERIC_TAIL_CONDITION)
        evidence_digest = _summarize_evidence(evidence, redactor=self._redactor)
        rendered = self._prompt_service.render_prompt(
            self.PROMPT_NAME,
            task_input=task_input,
            final_answer=final_answer,
            success_conditions=scored_conditions,
            evidence=evidence_digest,
        )
        response = await self._llm_service.invoke(
            self._judge_profile,
            [{"role": "user", "content": rendered}],
        )
        content = getattr(response, "content", response)
        return self._parse_verdict(str(content))

    @staticmethod
    def _parse_verdict(content: str) -> GoalVerdict:
        """Parse a JSON verdict, tolerating ```json fenced blocks."""
        payload = _extract_json(content)
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("goal judge verdict is not a JSON object")
        # ``criteria_met`` may arrive as a 0-100 percentage from some models;
        # clamp into the 0..1 contract.
        supplied: float | None
        try:
            supplied = float(data["criteria_met"])
        except (KeyError, TypeError, ValueError):
            supplied = None
        if supplied is not None:
            if supplied > 1.0:
                supplied = supplied / 100.0
            supplied = max(0.0, min(1.0, supplied))
        # Models sometimes omit or zero ``criteria_met`` while still filling
        # ``per_criterion`` (production trace: 0.0 alongside 4/4 met=true),
        # shipping an internally contradictory verdict into the Stage 5/6
        # calibration slices. The breakdown is authoritative: its met-flag
        # mean replaces a missing/unparseable value, or one that implies a
        # different met-count (off by more than half a criterion's weight,
        # 0.5/N). ``criteria_met_derived`` marks the repair so calibration
        # can stratify repaired verdicts from model-supplied ones.
        met_flags = _met_flags(data.get("per_criterion"))
        criteria = supplied if supplied is not None else 0.0
        derived = False
        if met_flags:
            mean_met = sum(met_flags) / len(met_flags)
            if supplied is None or abs(supplied - mean_met) > 0.5 / len(met_flags):
                criteria = mean_met
                derived = True
        data["criteria_met"] = criteria
        data["criteria_met_derived"] = derived
        # ``partial_fraction`` is telemetry-only completion metadata; clamp it
        # into the 0..1 contract mirroring ``criteria_met`` (a 0-100 percentage
        # from some models is rescaled before clamping).
        if "partial_fraction" in data:
            fraction = data.get("partial_fraction", 0.0)
            try:
                fraction = float(fraction)
            except (TypeError, ValueError):
                fraction = 0.0
            if fraction > 1.0:
                fraction = fraction / 100.0
            data["partial_fraction"] = max(0.0, min(1.0, fraction))
        return GoalVerdict.model_validate(data)


def _extract_json(content: str) -> str:
    """Return the JSON substring from a possibly fenced / chatty response."""
    text = content.strip()
    if "```" in text:
        # Pull the first fenced block, dropping an optional ``json`` tag.
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


def _met_flags(per_criterion: Any) -> list[bool]:
    """Extract ``met`` flags from a raw ``per_criterion`` payload.

    Returns ``[]`` when the payload is absent or malformed — shape problems
    are ``GoalVerdict.model_validate``'s to report, not the repair path's.
    String flags get explicit falsy-spelling handling (mirroring pydantic's
    bool coercion) so a ``"false"`` from the model does not count as met.
    """
    if not isinstance(per_criterion, list):
        return []
    flags: list[bool] = []
    for entry in per_criterion:
        if not isinstance(entry, dict):
            return []
        met = entry.get("met")
        if isinstance(met, str):
            flags.append(
                met.strip().lower() not in {"false", "f", "no", "n", "off", "0"}
            )
        else:
            flags.append(bool(met))
    return flags


def _summarize_evidence(
    evidence: list[dict[str, Any]] | None,
    *,
    max_items: int = 8,
    max_chars: int = 400,
    redactor: GuardRailValidator | None = None,
) -> str:
    """Render the tool trajectory into a compact, prompt-safe digest.

    Each line carries the tool **input** (what the agent asked for) and the
    tool **output** (what it observed), so the judge can ground a ``met=true``
    in observable action — not self-narrated progress. When a ``redactor`` is
    supplied, every line is scrubbed before it reaches the prompt so PII /
    secrets in the trajectory never leak into the judge call.
    """
    if not evidence:
        return "(no tool calls were made)"
    lines: list[str] = []
    for entry in evidence[-max_items:]:
        tool = entry.get("tool_name", "?")
        inp = _compact(entry.get("tool_input"), max_chars=max_chars)
        out = _compact(entry.get("tool_output"), max_chars=max_chars)
        line = f"- {tool}(input={inp}) -> {out}"
        if redactor is not None:
            line = redactor.redact(line)
        lines.append(line)
    return "\n".join(lines)


def _compact(value: Any, *, max_chars: int) -> str:
    """Stringify and truncate a tool input/output fragment for the digest."""
    text = "" if value is None else str(value)
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


def summarize_tool_calls(
    evidence: list[dict[str, Any]] | None,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Compact, queryable per-call audit for the eval.goal_judge telemetry.

    Returns the last ``limit`` tool calls with only the tool name and the
    sorted set of arg keys — enough to write Langfuse queries like "show me
    all GoalJudge verdicts where web_search wasn't called" without
    inlining full tool args/outputs (those live in the evidence digest).
    """
    if not evidence:
        return []
    return [
        {
            "tool_name": entry.get("tool_name", "?"),
            "args_keys": sorted((entry.get("tool_input") or {}).keys()),
        }
        for entry in evidence[-limit:]
    ]
