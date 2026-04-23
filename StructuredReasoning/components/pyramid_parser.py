"""Parse raw LLM text into a validated ``AnalysisOutput``.

Walking-skeleton (PR 1) responsibility: extract a JSON object from an
LLM response (which may include leading/trailing whitespace, code fences,
or stray prose) and validate it against the pyramid schema. The parser
is a pure function; it does not call the LLM. The orchestration layer
owns retry-with-LLM-reprompt logic, but this module exposes the
``ParseError`` shape and a ``build_retry_prompt`` helper so the loop's
retry policy is consistent.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from StructuredReasoning.trust.pyramid_schema import AnalysisOutput

# Match a top-level JSON object greedily across newlines. The pyramid
# schema is large but always serializes as a single ``{...}`` block.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)\n?```", re.DOTALL)


class ParseError(Exception):
    """Raised when the parser cannot turn LLM text into an ``AnalysisOutput``.

    ``stage`` indicates how far the parse got (``extract`` for JSON
    extraction failure; ``json`` for malformed JSON; ``schema`` for a
    Pydantic validation failure on otherwise-well-formed JSON).
    ``detail`` is the underlying exception message, suitable for
    inclusion in a retry prompt.
    """

    def __init__(self, *, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(f"PyramidParseError[{stage}]: {detail}")


def extract_json_object(text: str) -> str:
    """Return the first JSON object substring in ``text``.

    Strips Markdown code fences if present, then falls back to a regex
    scan for the outermost ``{...}`` block. Raises ``ParseError`` if no
    candidate is found.
    """
    if not text or not text.strip():
        raise ParseError(stage="extract", detail="empty LLM response")

    fence_match = _FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text

    obj_match = _JSON_OBJECT_RE.search(candidate)
    if obj_match is None:
        raise ParseError(
            stage="extract",
            detail="no JSON object found in LLM response",
        )
    return obj_match.group(0)


def parse_analysis_output(text: str) -> AnalysisOutput:
    """Parse raw LLM text into a validated ``AnalysisOutput``.

    Raises ``ParseError`` with a ``stage`` of ``extract``, ``json``, or
    ``schema`` so callers (notably the orchestration retry policy) can
    decide whether the failure is recoverable via a reprompt.
    """
    raw = extract_json_object(text)
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParseError(stage="json", detail=str(exc)) from exc

    if not isinstance(payload, dict):
        raise ParseError(
            stage="json",
            detail=f"expected JSON object, got {type(payload).__name__}",
        )

    try:
        return AnalysisOutput.model_validate(payload)
    except ValidationError as exc:
        raise ParseError(stage="schema", detail=exc.json()) from exc


def build_retry_prompt(error: ParseError) -> str:
    """Compose a follow-up user message that asks the LLM to fix its output.

    Used by the walking-skeleton orchestration loop after a single
    parse failure. The message is intentionally short and directive --
    the agent already has the system prompt with the full schema.
    """
    return (
        "Your previous response could not be parsed.\n"
        f"Failure stage: {error.stage}\n"
        f"Detail: {error.detail}\n\n"
        "Reply with a single JSON object that conforms to the "
        "analysis_output schema. Do not include any text outside the "
        "JSON object."
    )
