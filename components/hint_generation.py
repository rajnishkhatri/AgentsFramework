"""Hint verifier cascade (Phase 4 — ADR-0012/ADR-0014, spec FR-12).

The generator's output earns ``reviewed = True`` HERE, never asserts it:
schema-parse → deterministic per-rung leakage check → duplicate/similarity.
Deterministic-first (the judge-assist path stays out of the cascade until the
ADR-0008 cond#1 κ floor certifies). Anything that fails a stage becomes a
QUARANTINE row carrying the owning stage + violations for eval_capture —
never a served hint.

``components.hint_leakage`` is imported as a pure predicate helper (the
``components.schemas`` precedent), not a peer decision component — the
cascade and the checker are one domain decision split for testability.

Pure functions, deterministic (row ids are content hashes so re-runs are
idempotent), no I/O. The live-LLM driver lives in ``scripts/`` (a governed
``build_graph`` job), not here and not in ``meta/`` (invariant #8: meta never
drives the live graph).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from components.hint_leakage import check_rung_leakage

__all__ = ["CascadeVerdict", "run_hint_cascade"]

_VALID_RUNGS = (1, 2, 3)
# Near-duplicate threshold: token-set Jaccard against existing rung bodies.
_DUP_JACCARD = 0.85


@dataclass(frozen=True)
class CascadeVerdict:
    """One generator reply, adjudicated. ``passed`` rows carry reviewed=True."""

    passed: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)


def _extract_json(content: str) -> str:
    """Peel a ```json fence or find the outermost object (local helper —
    mirrors the judges' local copy; no peer import from goal_judge)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        return content[start : end + 1]
    return content


def _normalize(body: str) -> str:
    return re.sub(r"\s+", " ", body.lower()).strip().rstrip(".?!")


def _tokens(body: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", body.lower()))


def _is_near_duplicate(body: str, existing: Sequence[str]) -> bool:
    norm, toks = _normalize(body), _tokens(body)
    for other in existing:
        if _normalize(other) == norm:
            return True
        other_toks = _tokens(other)
        union = toks | other_toks
        if union and len(toks & other_toks) / len(union) >= _DUP_JACCARD:
            return True
    return False


def _quarantine(stage: str, raw: Any, violations: list[str]) -> dict[str, Any]:
    return {"stage": stage, "violations": violations, "raw": raw}


def _row_id(question_id: str, rung: int, body: str) -> str:
    digest = hashlib.sha256(
        f"{question_id}|{rung}|{_normalize(body)}".encode("utf-8")
    ).hexdigest()
    return f"h-gen-{digest[:16]}"


def run_hint_cascade(
    raw_reply: str,
    *,
    question: Mapping[str, Any],
    subject: str,
    existing_bodies: Sequence[str],
    generated_by: str,
) -> CascadeVerdict:
    """Adjudicate one generator reply for one question's ladder."""
    verdict = CascadeVerdict()

    # ── Stage 1: schema-parse ────────────────────────────────────────────
    try:
        data = json.loads(_extract_json(raw_reply))
        rungs = data["rungs"]
        if not isinstance(rungs, list):
            raise ValueError("'rungs' is not a list")
    except (ValueError, KeyError, TypeError):
        verdict.quarantined.append(
            _quarantine("schema", raw_reply[:500], ["reply is not a rungs JSON object"])
        )
        return verdict

    seen_levels: set[int] = set()
    accepted_bodies: list[str] = []
    for raw_rung in rungs:
        problems: list[str] = []
        rung_level = raw_rung.get("rung") if isinstance(raw_rung, Mapping) else None
        body = raw_rung.get("body_md") if isinstance(raw_rung, Mapping) else None
        if rung_level not in _VALID_RUNGS:
            problems.append(f"rung must be one of {_VALID_RUNGS}, got {rung_level!r}")
        if not isinstance(body, str) or not body.strip():
            problems.append("body_md must be a non-empty string")
        if rung_level in seen_levels:
            problems.append(f"duplicate rung level {rung_level} in one ladder")
        # The isinstance arms repeat the checks above so the type-checker
        # narrows rung_level/body for the stages below (a dynamic `problems`
        # list carries no narrowing).
        if problems or not isinstance(rung_level, int) or not isinstance(body, str):
            verdict.quarantined.append(_quarantine("schema", raw_rung, problems))
            continue

        # ── Stage 2: deterministic per-rung leakage check (critical gate) ─
        leaks = check_rung_leakage(body, question)
        if leaks:
            verdict.quarantined.append(_quarantine("leakage", raw_rung, leaks))
            continue

        # ── Stage 3: duplicate/similarity vs existing + this batch ───────
        if _is_near_duplicate(body, [*existing_bodies, *accepted_bodies]):
            verdict.quarantined.append(
                _quarantine("duplicate", raw_rung, ["near-duplicate rung body"])
            )
            continue

        seen_levels.add(rung_level)
        accepted_bodies.append(body)
        verdict.passed.append(
            {
                "id": _row_id(str(question.get("id", "")), rung_level, body),
                "subject": subject,
                "question_id": str(question.get("id", "")),
                "rung": rung_level,
                "body_md": body.strip(),
                # Earned by the cascade — the generator never asserts it.
                "reviewed": True,
                "generated_by": generated_by,
            }
        )

    verdict.passed.sort(key=lambda r: r["rung"])
    return verdict
