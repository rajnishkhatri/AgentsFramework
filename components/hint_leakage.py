"""Deterministic per-rung leakage check (ADR-0012/ADR-0014, spec FR-12).

The critical gate of the Phase-4 hint verifier cascade: a hint rung must
never assert, quote, recite, or uniquely narrow to the correct answer. This
module is the DETERMINISTIC-FIRST half of that gate — the judge-assist path
(PedagogyJudge.answer_leakage) stays out of the cascade until the ADR-0008
cond#1 κ floor certifies it.

Scope: this check covers exactly four LITERAL leak classes — assertive
letter reveal, correct-label quote, why-correct rationale recital, and
eliminate-every-distractor. The rule-naming-as-leak class the Stage-0 live
batch surfaced (a rung whose named rule uniquely identifies one choice) is
SEMANTIC and NOT covered here: rung 2 legitimately names the rule in general
terms, so a deterministic rule-overlap check would quarantine valid rungs.
That class stays an accepted ADR-0012 residual until the judge-assist path
above certifies.

Posture: fail-closed. An unverifiable input (no answer key) returns a
violation — the cascade quarantines it; it never passes silently (AP-6).

Layer rules: pure function, stdlib ``re`` only, deterministic, no I/O, no
peer component imports.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

__all__ = ["check_rung_leakage"]

# Assertive-context keywords: a choice letter appearing NEAR one of these is
# an answer assertion ("the answer is B", "pick B", "B is correct"). A bare
# letter mention ("compare A and B") is legitimate ladder language.
_ASSERTIVE_KEYWORDS = re.compile(
    r"\b(answer|correct|right|pick|choose|select|go\s+with)\b", re.IGNORECASE
)
# Negation vocabulary for the eliminate-down-to-one class.
_NEGATION_KEYWORDS = re.compile(
    r"\b(not|isn'?t|wrong|rule\s+out|eliminate|cross\s+off|can'?t\s+be|cannot\s+be)\b",
    re.IGNORECASE,
)
_WINDOW_BACK = 25
_WINDOW_FWD = 45

# Minimal stopword set for the rationale-recital overlap (content words only).
_STOPWORDS = frozenset(
    "the a an is are it its of to and or in on at that this with for be".split()
)
_RECITAL_THRESHOLD = 0.8
_MIN_RATIONALE_CONTENT_WORDS = 4
_MIN_LABEL_LEN = 6


def _letter_pattern(letter: str) -> re.Pattern[str]:
    """Case-sensitive standalone choice letter (an IGNORECASE 'A' would match
    the article 'a')."""
    return re.compile(rf"(?<![A-Za-z]){re.escape(letter)}(?![a-z])")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS}


def _letter_near_keywords(body: str, keywords: re.Pattern[str], letter: str) -> bool:
    pat = _letter_pattern(letter)
    for match in keywords.finditer(body):
        window = body[max(0, match.start() - _WINDOW_BACK) : match.end() + _WINDOW_FWD]
        if pat.search(window):
            return True
    return False


def check_rung_leakage(body_md: str, question: Mapping[str, Any]) -> list[str]:
    """Return the rung's leakage violations; ``[]`` means clean.

    A non-empty result — including the unverifiable case — means FAIL:
    the cascade must quarantine the row, never flip ``reviewed``.
    """
    violations: list[str] = []

    if not body_md or not body_md.strip():
        return ["empty rung body"]

    answer_letter = question.get("answer_letter")
    if not isinstance(answer_letter, str) or not answer_letter.strip():
        return ["unverifiable: question has no answer_letter"]
    answer_letter = answer_letter.strip()

    # 1. Assertive answer reveal ("the answer is B", "pick B", "B is right").
    if _letter_near_keywords(body_md, _ASSERTIVE_KEYWORDS, answer_letter):
        violations.append(
            f"assertive reference to the correct letter {answer_letter!r}"
        )

    choices = question.get("choices")
    choices = choices if isinstance(choices, list) else []

    # 2. Quoting the correct choice's surface form IS the answer.
    for choice in choices:
        if not isinstance(choice, Mapping) or choice.get("letter") != answer_letter:
            continue
        label = _normalize(str(choice.get("label", "")))
        if len(label) >= _MIN_LABEL_LEN and label in _normalize(body_md):
            violations.append("quotes the correct choice's label")

    # 3. Reciting the why-correct rationale (high content-word overlap).
    rationale_words = _content_words(str(question.get("why_correct_md", "")))
    if len(rationale_words) >= _MIN_RATIONALE_CONTENT_WORDS:
        overlap = len(rationale_words & _content_words(body_md)) / len(rationale_words)
        if overlap >= _RECITAL_THRESHOLD:
            violations.append(
                f"recites the why-correct rationale (overlap {overlap:.2f})"
            )

    # 4. Eliminating EVERY distractor uniquely narrows to the key.
    distractors = [
        str(c.get("letter"))
        for c in choices
        if isinstance(c, Mapping) and c.get("letter") not in (None, answer_letter)
    ]
    if len(distractors) >= 2 and all(
        _letter_near_keywords(body_md, _NEGATION_KEYWORDS, d) for d in distractors
    ):
        violations.append("eliminates every distractor (unique narrowing)")

    return violations
