"""Phase-3 corpus harvest — turning captured coach shadow traffic into
coding-ready corpus rows and an honest gate report (plan Phase 3 entry gate:
>= 100 coded turns per mode from PRODUCTION traffic).

Failure paths first (TAP-4): malformed input is skipped and counted, never
raised past; the gate report says NOT-met before any happy path asserts met.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from meta.subject_coach_corpus_harvest import (
    GATE_TURNS_PER_MODE,
    CoachCorpusRow,
    HarvestReport,
    harvest_corpus,
    parse_harvest_object,
    parse_harvest_stream,
)


def _record_obj(
    *,
    task_id: str = "task-1",
    step: int = 0,
    target: str = "subject_coach",
    coach_mode: str | None = None,
    task_input: str = "why is the semicolon right here?",
    response: str = "Let's think about the two clauses...",
) -> dict:
    ai_input: dict = {"task_input": task_input}
    if coach_mode is not None:
        ai_input["coach_mode"] = coach_mode
    return {
        "schema_version": 1,
        "timestamp": datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC).isoformat(),
        "task_id": task_id,
        "user_id": "learner-1",
        "step": step,
        "target": target,
        "model": "gpt-4o",
        "ai_input": ai_input,
        "ai_response": response,
    }


# ---------------------------------------------------------------------------
# parse_harvest_object — fail-closed on garbage (rejection before acceptance)
# ---------------------------------------------------------------------------


class TestParseHarvestObject:
    def test_missing_required_fields_returns_none(self) -> None:
        assert parse_harvest_object({"target": "subject_coach"}) is None

    def test_non_dict_payload_returns_none(self) -> None:
        assert parse_harvest_object({"jsonPayload": "not-a-dict"}) is None

    def test_top_level_record_parses(self) -> None:
        rec = parse_harvest_object(_record_obj())
        assert rec is not None
        assert rec.task_id == "task-1"
        assert rec.target == "subject_coach"

    def test_cloud_logging_envelope_parses_identically(self) -> None:
        """A `gcloud logging read --format=json` entry nests the record under
        jsonPayload; the parse must be equivalent to the top-level form."""
        plain = parse_harvest_object(_record_obj())
        wrapped = parse_harvest_object({"jsonPayload": _record_obj()})
        assert wrapped is not None and plain is not None
        assert wrapped.model_dump() == plain.model_dump()


# ---------------------------------------------------------------------------
# parse_harvest_stream — malformed lines skipped + counted, never raised
# ---------------------------------------------------------------------------


class TestParseHarvestStream:
    def test_malformed_json_line_is_skipped_and_counted(self) -> None:
        text = "not json at all\n" + json.dumps(_record_obj()) + "\n"
        records, skipped = parse_harvest_stream(text)
        assert len(records) == 1
        assert skipped == 1

    def test_valid_json_wrong_shape_is_skipped_and_counted(self) -> None:
        text = json.dumps({"hello": "world"}) + "\n" + json.dumps(_record_obj()) + "\n"
        records, skipped = parse_harvest_stream(text)
        assert len(records) == 1
        assert skipped == 1

    def test_json_array_input_is_accepted(self) -> None:
        """gcloud --format=json emits one array, not JSONL."""
        text = json.dumps([{"jsonPayload": _record_obj()}, {"noise": True}])
        records, skipped = parse_harvest_stream(text)
        assert len(records) == 1
        assert skipped == 1

    def test_empty_input_yields_nothing(self) -> None:
        records, skipped = parse_harvest_stream("")
        assert records == [] and skipped == 0


# ---------------------------------------------------------------------------
# harvest_corpus — filtering, collapse, mode split, dedupe, honest gate
# ---------------------------------------------------------------------------


class TestHarvestCorpus:
    def test_non_coach_targets_are_excluded(self) -> None:
        recs = [
            parse_harvest_object(_record_obj(task_id="t1")),
            parse_harvest_object(_record_obj(task_id="t2", target="hint_generator")),
        ]
        rows, report = harvest_corpus([r for r in recs if r is not None])
        assert [row.task_id for row in rows] == ["t1"]
        assert report.coach_records == 1

    def test_multi_step_task_collapses_to_latest_turn(self) -> None:
        recs = [
            parse_harvest_object(_record_obj(task_id="t1", step=0, response="draft")),
            parse_harvest_object(_record_obj(task_id="t1", step=2, response="final")),
        ]
        rows, _ = harvest_corpus([r for r in recs if r is not None])
        assert len(rows) == 1
        assert rows[0].coach_reply == "final"

    def test_mode_split_prefers_coach_mode_carrier(self) -> None:
        recs = [
            parse_harvest_object(_record_obj(task_id="t1", coach_mode="post_feedback")),
            parse_harvest_object(_record_obj(task_id="t2")),  # no carrier -> pre_submit
        ]
        rows, report = harvest_corpus([r for r in recs if r is not None])
        modes = {row.task_id: row.mode for row in rows}
        assert modes == {"t1": "post_feedback", "t2": "pre_submit"}
        assert report.per_mode == {"pre_submit": 1, "post_feedback": 1}

    def test_dedupe_against_existing_task_ids(self) -> None:
        recs = [
            parse_harvest_object(_record_obj(task_id="t1")),
            parse_harvest_object(_record_obj(task_id="t2")),
        ]
        rows, report = harvest_corpus(
            [r for r in recs if r is not None], existing_task_ids={"t1"}
        )
        assert [row.task_id for row in rows] == ["t2"]
        assert report.deduped == 1

    def test_rows_are_labeled_production_by_default(self) -> None:
        recs = [parse_harvest_object(_record_obj())]
        rows, _ = harvest_corpus([r for r in recs if r is not None])
        assert rows[0].provenance == "production"


class TestGateReport:
    def test_below_gate_is_not_met(self) -> None:
        recs = [parse_harvest_object(_record_obj(task_id=f"t{i}")) for i in range(3)]
        _, report = harvest_corpus([r for r in recs if r is not None])
        assert report.gate_met is False
        assert report.shortfall == {
            "pre_submit": GATE_TURNS_PER_MODE - 3,
            "post_feedback": GATE_TURNS_PER_MODE,
        }

    def test_gate_met_only_when_both_modes_reach_floor(self) -> None:
        recs = [
            parse_harvest_object(_record_obj(task_id=f"pre{i}"))
            for i in range(GATE_TURNS_PER_MODE)
        ] + [
            parse_harvest_object(
                _record_obj(task_id=f"post{i}", coach_mode="post_feedback")
            )
            for i in range(GATE_TURNS_PER_MODE)
        ]
        _, report = harvest_corpus([r for r in recs if r is not None])
        assert report.gate_met is True
        assert report.shortfall == {"pre_submit": 0, "post_feedback": 0}

    def test_one_mode_at_floor_alone_does_not_meet_gate(self) -> None:
        recs = [
            parse_harvest_object(_record_obj(task_id=f"pre{i}"))
            for i in range(GATE_TURNS_PER_MODE)
        ]
        _, report = harvest_corpus([r for r in recs if r is not None])
        assert report.gate_met is False


# ---------------------------------------------------------------------------
# CLI roundtrip — deterministic file-in/file-out smoke
# ---------------------------------------------------------------------------


class TestCliRoundtrip:
    def test_jsonl_in_corpus_out(self, tmp_path) -> None:
        from meta.subject_coach_corpus_harvest import main

        src = tmp_path / "export.jsonl"
        lines = [json.dumps(_record_obj(task_id=f"t{i}")) for i in range(2)]
        lines.insert(1, "garbage")
        src.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = tmp_path / "corpus.jsonl"

        code = main(["--input", str(src), "--output", str(out)])

        assert code == 0
        rows = [
            CoachCorpusRow.model_validate_json(line)
            for line in out.read_text(encoding="utf-8").splitlines()
        ]
        assert sorted(row.task_id for row in rows) == ["t0", "t1"]

    def test_appending_run_dedupes_against_output_file(self, tmp_path) -> None:
        from meta.subject_coach_corpus_harvest import main

        src = tmp_path / "export.jsonl"
        src.write_text(json.dumps(_record_obj(task_id="t0")) + "\n", encoding="utf-8")
        out = tmp_path / "corpus.jsonl"

        assert main(["--input", str(src), "--output", str(out)]) == 0
        assert main(["--input", str(src), "--output", str(out)]) == 0

        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1  # second run added nothing

    def test_missing_input_file_fails_with_nonzero_exit(self, tmp_path) -> None:
        from meta.subject_coach_corpus_harvest import main

        code = main(
            ["--input", str(tmp_path / "absent.jsonl"), "--output", str(tmp_path / "o")]
        )
        assert code != 0


# ---------------------------------------------------------------------------
# HarvestReport is honest telemetry (AP-6: counts, no fabricated ratios)
# ---------------------------------------------------------------------------


def test_report_has_no_fabricated_fields() -> None:
    fields = set(HarvestReport.model_fields)
    assert "coverage_ratio" not in fields
    assert "quality_score" not in fields


def test_gate_constant_matches_plan() -> None:
    assert GATE_TURNS_PER_MODE == 100


@pytest.mark.parametrize("mode", ["pre_submit", "post_feedback"])
def test_corpus_row_mode_is_closed_vocabulary(mode: str) -> None:
    row = CoachCorpusRow(
        task_id="t",
        user_id="u",
        timestamp=datetime(2026, 7, 3, tzinfo=UTC),
        mode=mode,
        learner_utterance="x",
        coach_reply="y",
        step=0,
    )
    assert row.mode == mode


def test_corpus_row_rejects_unknown_mode() -> None:
    with pytest.raises(Exception):
        CoachCorpusRow(
            task_id="t",
            user_id="u",
            timestamp=datetime(2026, 7, 3, tzinfo=UTC),
            mode="mid_submit",
            learner_utterance="x",
            coach_reply="y",
            step=0,
        )
