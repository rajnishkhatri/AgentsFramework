"""Typed background memory extractor (Phase 2 auto-capture).

Framework-agnostic (AGENTS.md I-3): imports only ``components.schemas`` (same
layer) and, under ``TYPE_CHECKING``, the injected ``services`` types. NO
``langgraph`` / ``langchain`` imports. Mirrors
``components.task_understanding.TaskUnderstandingGenerator``: injected
``LLMService`` + ``PromptService`` + fast-tier ``ModelProfile``, renders a
``.j2`` prompt (H1/I-12), tolerant JSON extraction.

Why this exists
---------------
Phase 1 stored a deterministic distillation of the final answer at run-end.
That is a blunt instrument: it cannot tell a stable *fact about the user*
(semantic) from *how a task went* (episodic) from *a strategy that worked*
(procedural), and it stores on every run regardless of whether anything is
worth remembering. This component is the typed, schema-guided extractor that
replaces it (research §1–§3): given a conversation window, it proposes
zero-or-more typed memory items. The *schema is the classifier* (research §3)
— the LLM is handed the three typed constraints and decides which type each
item is.

Contract (plan §Phase 2)
------------------------
``extract`` PROPOSES; it never stores. Storage is the autocapture service's
decision (shadow proposes-only vs. write-back, gated on the eval enable-policy
``MEMORY_AUTOCAPTURE_ENABLED``). ``extract`` RAISES ``MemoryExtractionError``
on a transport or whole-response parse failure (the caller owns the
graceful-degrade try/except, like the GoalJudge best-effort contract). A single
malformed *item* inside an otherwise-valid batch is DROPPED, not raised — the
``TypedMemory`` validator (``extra="forbid"``) is the schema-as-classifier
guard, and one hallucinated item must not lose the whole batch.

Phase 2 is ADD-only (research §3): no live UPDATE/DELETE. The ``existing_profile``
is shown to the model so it can avoid re-proposing a fact already stored; a
periodic consolidation pass (deferred) is the real conflict-resolution path.

Privacy: this component returns ``TypedMemory.content`` (the distilled fact) to
its caller, but the caller's carrier carries only ``{type, key, salience}`` —
never content (the privacy invariant lives at the carrier seam, not here).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, ValidationError

from components.schemas import TypedMemory

if TYPE_CHECKING:
    from services.base_config import ModelProfile
    from services.llm_config import LLMService
    from services.prompt_service import PromptService

logger = logging.getLogger("components.memory_extractor")

__all__ = [
    "MemoryExtractor",
    "MemoryExtractionError",
    "ExtractionResult",
]


class MemoryExtractionError(Exception):
    """Raised on a transport error or an unparseable whole response.

    A single malformed *item* does NOT raise this — it is dropped. This is
    reserved for failures that mean "no proposal could be produced at all".
    """


class ExtractionResult(BaseModel):
    """The extractor's proposal plus the LLM-call telemetry for ``eval_capture``.

    ``memories`` is the (possibly empty) list of valid proposed items. The
    token/cost/latency fields let the caller record the real extractor cost
    (I-11) — this is the only memory seam in Phase 1/2 with genuine tokens to
    report.
    """

    model_config = ConfigDict(extra="forbid")

    memories: list[TypedMemory]
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class MemoryExtractor:
    """Fast-tier LLM extraction of typed memory proposals from a window.

    Args:
        llm_service: injected ``LLMService`` (the only LLM boundary).
        prompt_service: injected ``PromptService`` for ``.j2`` rendering (H1).
        profile: fast/cheap-tier ``ModelProfile`` (H2) — same profile the
            judge / task-understanding generator use, injected at the
            composition root (never hardcoded here).
        name: logging / eval-capture tag.
    """

    PROMPT_NAME = "memory_extractor"

    def __init__(
        self,
        llm_service: LLMService,
        prompt_service: PromptService,
        profile: ModelProfile,
        *,
        name: str = "memory_extractor",
    ) -> None:
        self.name = name
        self._llm_service = llm_service
        self._prompt_service = prompt_service
        self._profile = profile

    @property
    def model_name(self) -> str:
        return getattr(self._profile, "name", "")

    async def extract(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        existing_profile: Iterable[str] | None = None,
    ) -> ExtractionResult:
        """Propose typed memory items for the given conversation window.

        Returns an ``ExtractionResult`` with zero-or-more valid items. Raises
        ``MemoryExtractionError`` on a transport or whole-response failure.
        An empty ``messages`` window short-circuits to an empty proposal with
        no LLM call (a confound, not a defect — nothing to extract from).
        """
        if not messages:
            return ExtractionResult(memories=[], model=self.model_name)

        transcript = _render_transcript(messages)
        profile_block = _render_existing_profile(existing_profile)
        rendered = self._prompt_service.render_prompt(
            self.PROMPT_NAME,
            transcript=transcript,
            existing_profile=profile_block,
        )

        import time

        start = time.perf_counter()
        try:
            response = await self._llm_service.invoke(
                self._profile,
                [{"role": "user", "content": rendered}],
            )
        except Exception as exc:
            raise MemoryExtractionError(
                f"memory extraction LLM call failed: {type(exc).__name__}"
            ) from exc
        latency_ms = (time.perf_counter() - start) * 1000.0

        content = str(getattr(response, "content", response))
        raw_items = self._parse(content)
        memories = _coerce_items(raw_items)

        usage = getattr(response, "usage_metadata", {}) or {}
        tokens_in = int(usage.get("input_tokens", 0) or 0)
        tokens_out = int(usage.get("output_tokens", 0) or 0)
        cost = (
            tokens_in * self._profile.cost_per_1k_input / 1000.0
            + tokens_out * self._profile.cost_per_1k_output / 1000.0
        )
        logger.info(
            "memory.extract proposed=%d model=%s",
            len(memories),
            self.model_name,
        )
        return ExtractionResult(
            memories=memories,
            model=self.model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    def _parse(self, content: str) -> list[Any]:
        """Extract the raw item list from a possibly chatty/fenced response.

        Raises ``MemoryExtractionError`` on malformed JSON or a non-object
        top level (whole-response failures). A missing/empty ``memories`` key
        is a valid "nothing to remember" proposal → empty list.
        """
        try:
            data = json.loads(_extract_json(content))
        except (json.JSONDecodeError, ValueError) as exc:
            raise MemoryExtractionError(
                "memory extraction response was not valid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise MemoryExtractionError(
                "memory extraction response is not a JSON object"
            )
        items = data.get("memories", [])
        if not isinstance(items, list):
            raise MemoryExtractionError("memories is not a list")
        return items


def _coerce_items(raw_items: list[Any]) -> list[TypedMemory]:
    """Validate each proposed item; DROP (never raise on) a malformed one.

    The ``extra="forbid"`` schema is the classifier guard: an item that
    invents a field, carries an unknown type, or omits a required field is
    silently dropped so one junk item cannot lose the whole batch. The count
    of dropped items is logged (no content) for the eval over-capture signal.
    """
    memories: list[TypedMemory] = []
    dropped = 0
    for item in raw_items:
        try:
            memories.append(TypedMemory.model_validate(item))
        except (ValidationError, TypeError):
            dropped += 1
    if dropped:
        logger.info("memory.extract dropped_invalid=%d", dropped)
    return memories


def _render_transcript(messages: Sequence[Mapping[str, Any]]) -> str:
    """Flatten the window into a plain ``role: content`` transcript.

    Returned as text and passed through ``render_prompt`` as a context var —
    the ``.j2`` owns all framing (H1; never string-concatenated into a prompt).
    """
    lines: list[str] = []
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _render_existing_profile(existing_profile: Iterable[str] | None) -> str:
    """Render the already-known facts so the model avoids re-proposing them."""
    if not existing_profile:
        return ""
    return "\n".join(f"- {fact}" for fact in existing_profile)


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
