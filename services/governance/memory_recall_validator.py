"""Phase 6 (replace-mem0-pgvector) — Tier-A memory-recall invariant validator.

Pure function over (user_id, requested_limit, kept_records) returning one
binary result per invariant. Modeled on services.governance.guardrail_validator
(ValidationResult shape) but with a fixed set of structural invariants the
recall seam must always satisfy.

Invariants (decidable at the moment the seam produces `kept`):

  1. LIMIT_RESPECTED   — len(kept) <= requested_limit
  2. USER_ISOLATED     — every kept record has user_id == requested user_id
                         (the load-bearing PRIVACY invariant for the recall
                         seam — a cross-user leak is the worst-case bug)
  3. SCORE_BOUNDED     — metadata['score'], when present, is a float in [0, 1]
                         (pgvector returns 1 - cosine_distance clamped to
                         [0,1]; the in-memory backend may omit score)
  4. KEY_INTEGRITY     — record.key is a non-empty string (carriers and the
                         eval-view join on these)

Privacy contract: result.details strings contain only identifiers (user_id,
key, integer counts, numeric scores) — NEVER payload values. See
TestContentFreeContract in tests/services/governance/test_memory_recall_validator.py.

This module lives in services/governance/ and may import from
services.long_term_memory (the MemoryRecord type it scores against — same
precedent as guardrail_validator owning GuardRail). No framework imports.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from services.long_term_memory import MemoryRecord


class RecallInvariant(str, Enum):
    """The four Tier-A recall invariants, named in evaluation order."""

    LIMIT_RESPECTED = "memory_recall.limit_respected"
    USER_ISOLATED = "memory_recall.user_isolated"
    SCORE_BOUNDED = "memory_recall.score_bounded"
    KEY_INTEGRITY = "memory_recall.key_integrity"


class RecallInvariantResult(BaseModel):
    """One invariant outcome — binary, with a content-free details string."""

    name: str
    passed: bool
    details: str


_INVARIANT_ORDER: tuple[RecallInvariant, ...] = (
    RecallInvariant.LIMIT_RESPECTED,
    RecallInvariant.USER_ISOLATED,
    RecallInvariant.SCORE_BOUNDED,
    RecallInvariant.KEY_INTEGRITY,
)


def validate_recall(
    *,
    user_id: str,
    requested_limit: int,
    kept: list[MemoryRecord],
) -> list[RecallInvariantResult]:
    """Run all Tier-A invariants over a recall result; return per-invariant
    binary results in a fixed order so the carrier payload schema is stable.
    """
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("user_id must be a non-empty string")
    if not isinstance(requested_limit, int) or requested_limit < 0:
        raise ValueError("requested_limit must be a non-negative int")

    return [
        _check_limit(requested_limit, kept),
        _check_user_isolation(user_id, kept),
        _check_score_bounds(kept),
        _check_key_integrity(kept),
    ]


def _check_limit(
    requested_limit: int, kept: list[MemoryRecord]
) -> RecallInvariantResult:
    n = len(kept)
    passed = n <= requested_limit
    details = (
        f"kept={n} <= limit={requested_limit}"
        if passed
        else f"kept={n} EXCEEDS limit={requested_limit}"
    )
    return RecallInvariantResult(
        name=RecallInvariant.LIMIT_RESPECTED.value,
        passed=passed,
        details=details,
    )


def _check_user_isolation(
    user_id: str, kept: list[MemoryRecord]
) -> RecallInvariantResult:
    foreign = [
        (r.user_id, r.key) for r in kept if r.user_id != user_id
    ]
    passed = not foreign
    if passed:
        details = f"all {len(kept)} records owned by user_id={user_id!r}"
    else:
        # Identifiers only — user_id + key are content-free per the
        # privacy invariant. Payload values are NOT referenced.
        sample = ", ".join(
            f"{uid!r}:{key!r}" for uid, key in foreign[:3]
        )
        details = (
            f"{len(foreign)} foreign-owner record(s) leaked into recall "
            f"for user_id={user_id!r} (sample: {sample})"
        )
    return RecallInvariantResult(
        name=RecallInvariant.USER_ISOLATED.value,
        passed=passed,
        details=details,
    )


def _check_score_bounds(kept: list[MemoryRecord]) -> RecallInvariantResult:
    out_of_bounds: list[tuple[str, object]] = []
    for r in kept:
        if "score" not in r.metadata:
            continue
        score = r.metadata["score"]
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            out_of_bounds.append((r.key, score))
            continue
        if score < 0.0 or score > 1.0:
            out_of_bounds.append((r.key, score))
    passed = not out_of_bounds
    if passed:
        details = f"all scores in [0, 1] across {len(kept)} record(s)"
    else:
        sample = ", ".join(
            f"key={key!r}:score={score!r}" for key, score in out_of_bounds[:3]
        )
        details = (
            f"{len(out_of_bounds)} record(s) with out-of-bounds score "
            f"(sample: {sample})"
        )
    return RecallInvariantResult(
        name=RecallInvariant.SCORE_BOUNDED.value,
        passed=passed,
        details=details,
    )


def _check_key_integrity(kept: list[MemoryRecord]) -> RecallInvariantResult:
    missing = [i for i, r in enumerate(kept) if not isinstance(r.key, str) or not r.key]
    passed = not missing
    details = (
        f"all {len(kept)} record key(s) non-empty"
        if passed
        else f"{len(missing)} record(s) with empty/non-string key at positions {missing[:3]}"
    )
    return RecallInvariantResult(
        name=RecallInvariant.KEY_INTEGRITY.value,
        passed=passed,
        details=details,
    )


__all__ = [
    "RecallInvariant",
    "RecallInvariantResult",
    "validate_recall",
]
