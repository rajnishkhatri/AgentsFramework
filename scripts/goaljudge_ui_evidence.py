"""Shared UI evidence helpers for GoalJudge batch grading and verification."""
from __future__ import annotations

import re

DEFAULT_STATUS_PREFIX = "Using tools:"


def strip_status_prefix(text: str, prefix: str = DEFAULT_STATUS_PREFIX) -> str:
    """Remove leading status-feed segments from streamed capture text.

    Fully-answered runs often begin with a progressively-replaced status feed
    (e.g. ``Using tools: file_io, web_search…``). Strip one-or-more leading
    ``<prefix> … <ellipsis>`` segments before measuring substantive content.
    """
    if not text:
        return ""
    esc = re.escape(prefix)
    pattern = re.compile(rf"^(?:\s*{esc}[^…]*…)+", re.IGNORECASE)
    return pattern.sub("", text).strip()


def is_ui_admissible(
    response_text: str,
    outcome: str,
    *,
    status_prefix: str = DEFAULT_STATUS_PREFIX,
) -> bool:
    """UI capture is admissible when Playwright passed and stripped text remains."""
    if outcome != "pass":
        return False
    return bool(strip_status_prefix(response_text, status_prefix))


def extract_answer_text(
    *,
    corpus_final_answer: object,
    ui_response: str = "",
    ui_admissible: bool = False,
) -> str:
    """Resolve prose answer text for grading (Langfuse bundle dict is not prose)."""
    if ui_admissible and ui_response.strip():
        stripped = strip_status_prefix(ui_response)
        if stripped:
            return stripped
    if isinstance(corpus_final_answer, str) and corpus_final_answer.strip():
        return corpus_final_answer.strip()
    return ""
