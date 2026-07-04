"""Phase-3 environment posture checker — garbage-in guard before coding.

Failure paths first (TAP-4): a confound is excluded BEFORE the eligible path is
asserted, and a missing mode carrier is a confound BEFORE any happy
classification. The report carries counts only — never a fabricated quality
score (AP-6).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from components.schemas import EvalRecord
from meta.coach_corpus_posture import (
    EVAL_CAPTURE_TASK_INPUT_CAP,
    PostureReport,
    check_posture,
    load_manifest_mode_map,
)
from meta.subject_coach_judge_sampler import mode_of  # cross-check only


def _rec(
    *,
    task_id: str = "task-1",
    step: int = 0,
    coach_mode: str | None = "pre_submit",
    task_input: str = "why is the semicolon right here?",
    response: str = "Let's think about the two clauses...",
) -> EvalRecord:
    ai_input: dict = {"task_input": task_input}
    if coach_mode is not None:
        ai_input["coach_mode"] = coach_mode
    return EvalRecord(
        schema_version=1,
        timestamp=datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC),
        task_id=task_id,
        user_id="learner-1",
        step=step,
        target="subject_coach",
        model="gpt-4o",
        ai_input=ai_input,
        ai_response=response,
    )


# ---------------------------------------------------------------------------
# FR-G1.1 — manifest mode mismatch is a confound (BEFORE eligible path)
# ---------------------------------------------------------------------------


class TestManifestModeMismatch:
    def test_mode_manifest_mismatch_is_confound(self) -> None:
        """Carrier says pre_submit but manifest authored the turn post_feedback."""
        manifest = load_manifest_mode_map(
            [{"mode": "post_feedback", "utterance": "why is the semicolon right here?"}]
        )
        classified, report = check_posture(
            [_rec(coach_mode="pre_submit")], manifest=manifest
        )
        assert classified[0].classification == "confound"
        assert classified[0].reason == "manifest_mode_mismatch"
        assert report.confound_rows == 1
        assert report.coding_eligible == 0

    def test_match_is_not_confound(self) -> None:
        manifest = load_manifest_mode_map(
            [{"mode": "pre_submit", "utterance": "why is the semicolon right here?"}]
        )
        classified, _ = check_posture(
            [_rec(coach_mode="pre_submit")], manifest=manifest
        )
        assert classified[0].classification != "confound"

    def test_no_manifest_skips_mismatch_check(self) -> None:
        """Production harvest has no manifest; FR-G1.1 is N/A there."""
        classified, _ = check_posture([_rec(coach_mode="pre_submit")], manifest=None)
        assert classified[0].classification != "confound"


# ---------------------------------------------------------------------------
# FR-G1.2 — missing mode carrier is a confound (pre-F1 / malformed capture)
# ---------------------------------------------------------------------------


class TestMissingModeCarrier:
    def test_missing_coach_mode_carrier_is_confound(self) -> None:
        """No coach_mode key AND no legacy marker in task_input → confound."""
        rec = _rec(coach_mode=None, task_input="no marker anywhere here")
        # Sanity: mode_of still returns a fail-closed default — but posture must
        # NOT trust it.
        assert mode_of(rec) == "pre_submit"
        classified, report = check_posture([rec], manifest=None)
        assert classified[0].classification == "confound"
        assert classified[0].reason == "missing_mode_carrier"
        assert report.confound_rows == 1
        assert report.coding_eligible == 0

    def test_legacy_marker_alone_is_not_confound(self) -> None:
        """Pre-F1 records carry the legacy '"mode": "post_feedback"' marker."""
        rec = _rec(
            coach_mode=None,
            task_input='help me with this {"mode": "post_feedback"} question',
        )
        classified, _ = check_posture([rec], manifest=None)
        assert classified[0].classification != "confound"

    def test_carrier_present_is_not_confound(self) -> None:
        classified, _ = check_posture([_rec(coach_mode="pre_submit")], manifest=None)
        assert classified[0].classification != "confound"


# ---------------------------------------------------------------------------
# FR-G1.3 — partial_context: pre_submit + eval-capture truncated task_input
# ---------------------------------------------------------------------------


class TestPartialContext:
    def test_partial_context_excluded_from_holdout(self) -> None:
        """pre_submit turn whose task_input hit the 200-char eval cap is flagged
        partial_context — eligible for open coding, NOT for holdout candidacy."""
        truncated = "x" * EVAL_CAPTURE_TASK_INPUT_CAP
        rec = _rec(coach_mode="pre_submit", task_input=truncated)
        classified, report = check_posture([rec], manifest=None)
        assert classified[0].classification == "partial_context"
        assert report.partial_context_rows == 1
        # partial_context is NOT counted as coding_eligible (it is a separate
        # bucket — the holdout candidacy exclusion is the whole point).
        assert report.coding_eligible == 0
        assert report.confound_rows == 0

    def test_post_feedback_truncated_is_not_partial_context(self) -> None:
        """Truncation only matters pre-submit (leak is only defined pre-submit)."""
        truncated = "x" * EVAL_CAPTURE_TASK_INPUT_CAP
        rec = _rec(coach_mode="post_feedback", task_input=truncated)
        classified, report = check_posture([rec], manifest=None)
        assert classified[0].classification == "coding_eligible"
        assert report.partial_context_rows == 0

    def test_short_pre_submit_is_eligible(self) -> None:
        classified, report = check_posture(
            [_rec(coach_mode="pre_submit", task_input="short")], manifest=None
        )
        assert classified[0].classification == "coding_eligible"
        assert report.partial_context_rows == 0


# ---------------------------------------------------------------------------
# FR-G1.4 — report is counts only (AP-6: no fabricated quality score)
# ---------------------------------------------------------------------------


class TestReportCountsOnly:
    def test_report_counts_only_no_quality_score(self) -> None:
        fields = set(PostureReport.model_fields)
        assert "quality_score" not in fields
        assert "coverage_ratio" not in fields
        assert "confidence" not in fields
        # The named count buckets exist.
        assert {"coding_eligible", "confound_rows", "partial_context_rows"} <= fields

    def test_report_counts_match_classifications(self) -> None:
        recs = [
            _rec(task_id="ok1", coach_mode="pre_submit", task_input="fine"),
            _rec(task_id="bad1", coach_mode=None, task_input="no marker"),
            _rec(
                task_id="pc1",
                coach_mode="pre_submit",
                task_input="y" * EVAL_CAPTURE_TASK_INPUT_CAP,
            ),
            _rec(task_id="ok2", coach_mode="post_feedback", task_input="fine post"),
        ]
        _, report = check_posture(recs, manifest=None)
        assert report.coding_eligible == 2
        assert report.confound_rows == 1
        assert report.partial_context_rows == 1


# ---------------------------------------------------------------------------
# Per-mode eligible counts + shortfall (feeds FR-G2.5 in the export step)
# ---------------------------------------------------------------------------


class TestPerModeCounts:
    def test_per_mode_counts_eligible_only(self) -> None:
        recs = [
            _rec(task_id=f"pre{i}", coach_mode="pre_submit", task_input="ok")
            for i in range(2)
        ] + [
            _rec(task_id=f"post{i}", coach_mode="post_feedback", task_input="ok")
            for i in range(3)
        ]
        _, report = check_posture(recs, manifest=None)
        assert report.per_mode == {"pre_submit": 2, "post_feedback": 3}

    def test_shortfall_when_under_gate(self) -> None:
        from meta.subject_coach_corpus_harvest import GATE_TURNS_PER_MODE

        recs = [_rec(task_id="pre0", coach_mode="pre_submit", task_input="ok")]
        _, report = check_posture(recs, manifest=None)
        assert report.shortfall == {
            "pre_submit": GATE_TURNS_PER_MODE - 1,
            "post_feedback": GATE_TURNS_PER_MODE,
        }


# ---------------------------------------------------------------------------
# Latest-turn collapse + non-coach targets excluded (reuse from sampler)
# ---------------------------------------------------------------------------


def test_non_coach_targets_excluded() -> None:
    rec = _rec()
    rec = rec.model_copy(update={"target": "hint_generator"})
    classified, report = check_posture([rec], manifest=None)
    assert classified == []
    assert report.coding_eligible == 0


def test_multi_step_collapses_to_latest_turn() -> None:
    recs = [
        _rec(task_id="t1", step=0, task_input="draft"),
        _rec(task_id="t1", step=2, task_input="final answer here"),
    ]
    classified, _ = check_posture(recs, manifest=None)
    assert len(classified) == 1


# ---------------------------------------------------------------------------
# Manifest loader — utterance→mode map; conflicting modes raise
# ---------------------------------------------------------------------------


class TestManifestModeMap:
    def test_lookup_by_utterance(self) -> None:
        mmap = load_manifest_mode_map([{"mode": "pre_submit", "utterance": "hello"}])
        assert mmap.expected_mode("hello") == "pre_submit"
        assert mmap.expected_mode("absent") is None

    def test_conflicting_modes_for_same_utterance_raise(self) -> None:
        with pytest.raises(ValueError):
            load_manifest_mode_map(
                [
                    {"mode": "pre_submit", "utterance": "dup"},
                    {"mode": "post_feedback", "utterance": "dup"},
                ]
            )
