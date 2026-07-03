"""Test-item verifier cascade (Phase 6 — ADR-0013/ADR-0015, spec FR-23).

The generator's second content family (the ``hint_generation.py`` sibling). A
candidate item earns ``reviewed = True`` HERE, never asserts it:
schema-parse → answer-key consistency (an INDEPENDENT solver pass, the
critical gate) → duplicate/similarity. Anything that fails a stage — or is
undecidable — becomes a QUARANTINE row carrying the owning stage + violations
for eval_capture; never a served item (AP-6: undecidable → quarantine, never a
fabricated pass).

The solver is an injected async callable (``(item) -> str``), the same
provider seam ``hint_generation`` uses for its leak predicate: the live-LLM
driver lives in ``scripts/`` (a governed ``build_graph`` job), not here. The
declared answer key is NEVER shown to the solver — it sees stem + choices only
(FR-23.3), so a plausible-but-wrong key is caught by disagreement.

Pure/deterministic apart from the injected solver (row ids are content hashes
so re-runs are idempotent), no I/O. Framework-agnostic (invariant #3): no
langgraph/langchain import; no peer component import (invariant #5).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Solver",
    "TestItemCascadeVerdict",
    "extract_solver_letter",
    "run_test_item_cascade",
]

Solver = Callable[[Mapping[str, Any]], Awaitable[str]]

_MIN_CHOICES = 4
# Near-duplicate threshold: token-set Jaccard over stems (hint cascade parity).
_DUP_JACCARD = 0.85
# A standalone choice letter: not glued to another letter (so "A." matches but
# "Answer" does not). Case-insensitive; the caller intersects with the valid set.
_LETTER_TOKEN = re.compile(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])")


def extract_solver_letter(reply: str, valid: set[str]) -> str | None:
    """Return the single choice letter the solver's reply names, or ``None``
    when undecidable — parity-pinned to ``ExactLetterGrader`` semantics (the
    verdict is a letter, compared exactly). Undecidable = names zero valid
    letters, or names more than one distinct valid letter (an ambiguous reply
    is never guessed at — AP-6). Letters outside the choice set are ignored, so
    a reply that names only an out-of-range letter is undecidable.
    """
    found = {
        m.group(1).upper()
        for m in _LETTER_TOKEN.finditer(reply)
        if m.group(1).upper() in valid
    }
    if len(found) == 1:
        return next(iter(found))
    return None


@dataclass(frozen=True)
class TestItemCascadeVerdict:
    """A batch of generated items, adjudicated. ``passed`` rows carry reviewed=True."""

    passed: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)


def _extract_json(content: str) -> str:
    """Peel a ```json fence or find the outermost object (local helper —
    the hint cascade / judges pattern; no peer import)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        return content[start : end + 1]
    return content


def _quarantine(stage: str, raw: Any, violations: list[str]) -> dict[str, Any]:
    return {"stage": stage, "violations": violations, "raw": raw}


def _schema_violations(item: Any) -> list[str]:
    """Structural checks only (FR-23.1). A plausible-but-WRONG declared key is
    NOT caught here — that is the solver stage's job (FR-23.3)."""
    problems: list[str] = []
    if not isinstance(item, Mapping):
        return ["item is not a JSON object"]

    stem = item.get("stem_md")
    if not isinstance(stem, str) or not stem.strip():
        problems.append("stem_md must be a non-empty string")

    choices = item.get("choices")
    letters: list[str] = []
    if not isinstance(choices, list) or len(choices) < _MIN_CHOICES:
        problems.append(f"choices must be a list of at least {_MIN_CHOICES}")
    else:
        for choice in choices:
            letter = choice.get("letter") if isinstance(choice, Mapping) else None
            label = choice.get("label") if isinstance(choice, Mapping) else None
            if not isinstance(letter, str) or not letter.strip():
                problems.append("each choice needs a non-empty letter")
            elif not isinstance(label, str) or not label.strip():
                problems.append(f"choice {letter} needs a non-empty label")
            else:
                letters.append(letter)
        if len(set(letters)) != len(letters):
            problems.append("choice letters must be unique")

    answer = item.get("answer_letter")
    if not isinstance(answer, str) or answer not in letters:
        problems.append("answer_letter must name one of the choice letters")

    skill = item.get("skill_id")
    if not isinstance(skill, str) or not skill.strip():
        problems.append("skill_id must be a non-empty string")

    return problems


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip().rstrip(".?!")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _is_near_duplicate(stem: str, existing: Sequence[str]) -> bool:
    norm, toks = _normalize(stem), _tokens(stem)
    for other in existing:
        if _normalize(other) == norm:
            return True
        other_toks = _tokens(other)
        union = toks | other_toks
        if union and len(toks & other_toks) / len(union) >= _DUP_JACCARD:
            return True
    return False


def _solver_view(item: Mapping[str, Any]) -> dict[str, Any]:
    """The item as the independent solver sees it: stem + choices only. The
    declared ``answer_letter`` (and any rationale) is WITHHELD so the solver's
    letter is an independent verdict, not an echo (FR-23.3)."""
    return {
        "stem_md": item["stem_md"],
        "choices": [
            {"letter": c["letter"], "label": c["label"]} for c in item["choices"]
        ],
    }


def _row_id(subject: str, stem: str, answer_letter: str) -> str:
    """Deterministic content-hash id (idempotent re-runs — the
    ``hint_generation`` precedent). Keyed on the graded content so a re-emit of
    the same item collides to the same row."""
    norm = re.sub(r"\s+", " ", stem.lower()).strip()
    digest = hashlib.sha256(f"{subject}|{norm}|{answer_letter}".encode()).hexdigest()
    return f"ti-gen-{digest[:16]}"


def _reviewed_row(
    item: Mapping[str, Any], subject: str, generated_by: str
) -> dict[str, Any]:
    """A passed candidate, stamped ``reviewed=True`` by the cascade (never
    self-asserted). Carries the Question-shaped fields the ``test_item`` table
    stores (ADR-0015 clause 1)."""
    return {
        "id": _row_id(subject, item["stem_md"], item["answer_letter"]),
        "subject": subject,
        "skill_id": item["skill_id"],
        "difficulty": item.get("difficulty"),
        "stem_md": item["stem_md"].strip(),
        "choices": [
            {"letter": c["letter"], "label": c["label"]} for c in item["choices"]
        ],
        "answer_letter": item["answer_letter"],
        # Earned by the cascade — the generator never asserts it.
        "reviewed": True,
        "generated_by": generated_by,
    }


async def run_test_item_cascade(
    raw_reply: str,
    *,
    subject: str,
    solver: Solver,
    existing_stems: Sequence[str],
    generated_by: str,
) -> TestItemCascadeVerdict:
    """Adjudicate a generator reply (a ``{"items": [...]}`` batch) for one subject.

    ``solver`` confirms each candidate's declared key by an independent pass;
    it is never reached for a candidate that fails the structural schema stage.
    """
    verdict = TestItemCascadeVerdict()

    # ── Stage 1: schema-parse ────────────────────────────────────────────
    try:
        data = json.loads(_extract_json(raw_reply))
        items = data["items"]
        if not isinstance(items, list):
            raise ValueError("'items' is not a list")
    except (ValueError, KeyError, TypeError):
        verdict.quarantined.append(
            _quarantine(
                "schema", raw_reply[:500], ["reply is not an items JSON object"]
            )
        )
        return verdict

    accepted_stems: list[str] = []
    for raw_item in items:
        problems = _schema_violations(raw_item)
        if problems:
            verdict.quarantined.append(_quarantine("schema", raw_item, problems))
            continue

        # ── Stage 2: answer-key consistency (critical gate) ──────────────
        # The declared key is withheld — the solver sees stem + choices only
        # (FR-23.3) and must independently arrive at the same letter.
        letters = {c["letter"] for c in raw_item["choices"]}
        solver_reply = await solver(_solver_view(raw_item))
        solved = extract_solver_letter(solver_reply, letters)
        if solved is None:
            verdict.quarantined.append(
                _quarantine(
                    "answer_key",
                    raw_item,
                    ["solver reply undecidable (no clear letter)"],
                )
            )
            continue
        if solved != raw_item["answer_letter"]:
            verdict.quarantined.append(
                _quarantine(
                    "answer_key",
                    raw_item,
                    [
                        f"declared key {raw_item['answer_letter']!r} != solver {solved!r}"
                    ],
                )
            )
            continue

        # ── Stage 3: duplicate/similarity vs existing bank + this batch ──
        if _is_near_duplicate(raw_item["stem_md"], [*existing_stems, *accepted_stems]):
            verdict.quarantined.append(
                _quarantine("duplicate", raw_item, ["near-duplicate item stem"])
            )
            continue

        accepted_stems.append(raw_item["stem_md"])
        verdict.passed.append(_reviewed_row(raw_item, subject, generated_by))

    return verdict
