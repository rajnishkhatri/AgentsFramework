"""Phase 6 (replace-mem0-pgvector) — Tier-A recall invariant validator.

L1 deterministic check over `(recall_user_id, requested_limit, kept_records)`.
Pure function in `services/governance/memory_recall_validator.py`; per-invariant
binary results modeled on `ValidationResult`. Failure-paths-first per AGENTS.md
§Testing Rules — every invariant has at least one rejection test before its
acceptance test.
"""

from __future__ import annotations

import pytest

from services.governance.memory_recall_validator import (
    RecallInvariant,
    RecallInvariantResult,
    validate_recall,
)
from services.long_term_memory import MemoryRecord


def _record(
    *,
    user_id: str = "alice",
    key: str = "k1",
    score: float | None = 0.5,
) -> MemoryRecord:
    metadata: dict = {}
    if score is not None:
        metadata["score"] = score
    return MemoryRecord(
        user_id=user_id,
        key=key,
        payload={"text": "anything"},
        metadata=metadata,
    )


class TestLimitInvariantRejections:
    """Invariant 1: len(kept) <= requested_limit."""

    def test_more_records_than_limit_fails_limit_invariant(self) -> None:
        records = [_record(key=f"k{i}") for i in range(5)]
        results = validate_recall(
            user_id="alice", requested_limit=3, kept=records
        )
        limit_result = _result_for(results, RecallInvariant.LIMIT_RESPECTED)
        assert limit_result.passed is False
        assert "5" in limit_result.details and "3" in limit_result.details

    def test_zero_limit_with_returned_records_fails(self) -> None:
        results = validate_recall(
            user_id="alice", requested_limit=0, kept=[_record()]
        )
        assert _result_for(results, RecallInvariant.LIMIT_RESPECTED).passed is False

    def test_negative_limit_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="requested_limit"):
            validate_recall(user_id="alice", requested_limit=-1, kept=[])


class TestUserIdInvariantRejections:
    """Invariant 2: every kept record has user_id == recall_user_id (PRIVACY)."""

    def test_foreign_user_id_in_kept_records_fails(self) -> None:
        records = [
            _record(user_id="alice", key="ka"),
            _record(user_id="mallory", key="km"),
        ]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=records
        )
        user_result = _result_for(results, RecallInvariant.USER_ISOLATED)
        assert user_result.passed is False
        # Content-free details: the foreign user_id and the leaked key are
        # identifiers, not payload — the carrier already records both.
        assert "mallory" in user_result.details

    def test_all_records_foreign_user_fails(self) -> None:
        records = [_record(user_id="bob", key="kb")]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=records
        )
        assert _result_for(results, RecallInvariant.USER_ISOLATED).passed is False

    def test_empty_recall_user_id_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="user_id"):
            validate_recall(user_id="", requested_limit=10, kept=[])


class TestScoreBoundsInvariantRejections:
    """Invariant 3: metadata['score'] in [0, 1] when present."""

    def test_score_above_one_fails(self) -> None:
        records = [_record(key="k1", score=1.5)]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=records
        )
        score_result = _result_for(results, RecallInvariant.SCORE_BOUNDED)
        assert score_result.passed is False
        assert "1.5" in score_result.details

    def test_score_below_zero_fails(self) -> None:
        records = [_record(key="k1", score=-0.1)]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=records
        )
        assert _result_for(results, RecallInvariant.SCORE_BOUNDED).passed is False

    def test_non_numeric_score_fails(self) -> None:
        rec = _record(score=None)
        rec.metadata["score"] = "high"  # type: ignore[assignment]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=[rec]
        )
        assert _result_for(results, RecallInvariant.SCORE_BOUNDED).passed is False


class TestKeyIntegrityInvariantRejections:
    """Invariant 4: record.key is a non-empty string (carrier-join integrity)."""

    def test_empty_key_fails(self) -> None:
        records = [_record(key="")]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=records
        )
        key_result = _result_for(results, RecallInvariant.KEY_INTEGRITY)
        assert key_result.passed is False


class TestAcceptancePaths:
    """All invariants PASS on a clean recall."""

    def test_clean_recall_passes_all_invariants(self) -> None:
        records = [_record(key=f"k{i}", score=0.8 - i * 0.1) for i in range(3)]
        results = validate_recall(
            user_id="alice", requested_limit=3, kept=records
        )
        assert _result_for(results, RecallInvariant.LIMIT_RESPECTED).passed
        assert _result_for(results, RecallInvariant.USER_ISOLATED).passed
        assert _result_for(results, RecallInvariant.SCORE_BOUNDED).passed
        assert _result_for(results, RecallInvariant.KEY_INTEGRITY).passed

    def test_empty_recall_passes_all_invariants(self) -> None:
        """An empty kept list (cold cache, no matches, degraded path) is
        valid by construction — zero records can't violate any invariant."""
        results = validate_recall(
            user_id="alice", requested_limit=5, kept=[]
        )
        assert all(r.passed for r in results)

    def test_score_at_zero_and_one_boundary_passes(self) -> None:
        records = [_record(key="ka", score=0.0), _record(key="kb", score=1.0)]
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=records
        )
        assert _result_for(results, RecallInvariant.SCORE_BOUNDED).passed

    def test_missing_score_metadata_passes(self) -> None:
        """The score field is optional in the round-trip; absence is not a
        violation. The pgvector backend writes it; in-memory may not."""
        rec = _record(score=None)
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=[rec]
        )
        assert _result_for(results, RecallInvariant.SCORE_BOUNDED).passed


class TestContentFreeContract:
    """Privacy invariant — details strings name only identifiers + counts,
    never payload content (payload['text'], payload values)."""

    def test_details_never_contain_payload_text(self) -> None:
        # Use distinctive payload text the validator must NOT echo.
        secret = "TOTALLY_UNIQUE_PAYLOAD_TOKEN_42"
        rec = MemoryRecord(
            user_id="bob",  # foreign user — triggers USER_ISOLATED failure
            key="k1",
            payload={"text": secret},
            metadata={"score": 2.0},  # also triggers SCORE_BOUNDED failure
        )
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=[rec]
        )
        for result in results:
            assert secret not in result.details, (
                f"Validator leaked payload text into '{result.name}'.details"
            )

    def test_results_count_is_stable(self) -> None:
        """Exactly one result per invariant, in a deterministic order so
        downstream carrier / eval_capture payloads have a fixed schema."""
        results = validate_recall(
            user_id="alice", requested_limit=10, kept=[_record()]
        )
        assert len(results) == 4
        names = [r.name for r in results]
        assert names == [
            RecallInvariant.LIMIT_RESPECTED.value,
            RecallInvariant.USER_ISOLATED.value,
            RecallInvariant.SCORE_BOUNDED.value,
            RecallInvariant.KEY_INTEGRITY.value,
        ]


def _result_for(
    results: list[RecallInvariantResult], invariant: RecallInvariant
) -> RecallInvariantResult:
    matches = [r for r in results if r.name == invariant.value]
    assert len(matches) == 1, f"expected one result for {invariant}, got {len(matches)}"
    return matches[0]
