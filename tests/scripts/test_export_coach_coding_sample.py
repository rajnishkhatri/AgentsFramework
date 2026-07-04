"""Phase-3 coding-sample export + holdout ledger (FR-G2.1–G2.5).

Failure paths first (TAP-4): the holdout is disjoint from the coding sample
BEFORE a happy export; a confound is excluded BEFORE an eligible row ships; a
shortfall is emitted when a mode is under the gate BEFORE the gate is implied
met.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from components.schemas import EvalRecord
from meta.coach_corpus_posture import check_posture, load_manifest_mode_map

from scripts.export_coach_coding_sample import (
    HoldoutLedger,
    build_coder_rows,
    compute_holdout,
    write_coder_jsonl,
    write_holdout_ledger,
)


def _rec(
    *,
    task_id: str,
    coach_mode: str = "pre_submit",
    task_input: str = "a short learner utterance",
    response: str = "a coach reply that guides without leaking",
) -> EvalRecord:
    ai_input: dict = {"task_input": task_input}
    if coach_mode is not None:
        ai_input["coach_mode"] = coach_mode
    return EvalRecord(
        schema_version=1,
        timestamp=datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC),
        task_id=task_id,
        user_id="learner-1",
        step=0,
        target="subject_coach",
        model="gpt-4o",
        ai_input=ai_input,
        ai_response=response,
    )


def _manifest_rows(
    *, utterance: str, mode: str, question_id: str = "q-1", cls: str = "breadth"
):
    return [
        {
            "mode": mode,
            "utterance": utterance,
            "question_id": question_id,
            "cls": cls,
            "index": 0,
        }
    ]


# ---------------------------------------------------------------------------
# FR-G2.1 — holdout disjoint from coding sample (BEFORE happy export)
# ---------------------------------------------------------------------------


class TestHoldoutDisjoint:
    def test_holdout_disjoint_from_coding_sample(self) -> None:
        task_ids = [f"t{i}" for i in range(200)]
        holdout = compute_holdout(task_ids, seed=42, fraction=0.30)
        coding = [tid for tid in task_ids if tid not in holdout]
        assert holdout.isdisjoint(set(coding))
        # Roughly the requested fraction (deterministic hash bucketing).
        assert 0.25 < len(holdout) / len(task_ids) < 0.35

    def test_empty_input_yields_empty_holdout(self) -> None:
        assert compute_holdout([], seed=42, fraction=0.30) == set()

    def test_fraction_zero_yields_empty_holdout(self) -> None:
        assert compute_holdout(["a", "b", "c"], seed=42, fraction=0.0) == set()


# ---------------------------------------------------------------------------
# FR-G2.2 — holdout ledger deterministic by seed + written to versioned path
# ---------------------------------------------------------------------------


class TestHoldoutLedger:
    def test_holdout_ledger_deterministic_by_seed(self) -> None:
        ids = [f"t{i}" for i in range(50)]
        a = compute_holdout(ids, seed=7, fraction=0.30)
        b = compute_holdout(ids, seed=7, fraction=0.30)
        c = compute_holdout(ids, seed=8, fraction=0.30)
        assert a == b
        # A different seed is not required to differ, but determinism per seed
        # is the binding property — assert it explicitly.
        assert a == compute_holdout(ids, seed=7, fraction=0.30)

    def test_write_holdout_ledger_roundtrips(self, tmp_path: Path) -> None:
        ids = ["t1", "t2", "t3"]
        path = tmp_path / "cache" / "coach_shadow" / "holdout_ledger.json"
        write_holdout_ledger(path, task_ids=ids, seed=42)
        ledger = HoldoutLedger.model_validate_json(path.read_text(encoding="utf-8"))
        assert ledger.seed == 42
        assert set(ledger.task_ids) == {"t1", "t2", "t3"}
        assert ledger.created_at is not None

    def test_ledger_path_under_cache_coach_shadow(self, tmp_path: Path) -> None:
        """FR-G2.2 versioned default path (caller passes the canonical path)."""
        path = tmp_path / "cache" / "coach_shadow" / "holdout_ledger.json"
        write_holdout_ledger(path, task_ids=[], seed=42)
        assert path.exists()


# ---------------------------------------------------------------------------
# FR-G2.3 — coder JSONL field map (trace_id / prompt / final_answer + meta)
# ---------------------------------------------------------------------------


class TestCoderJsonlFieldMap:
    def test_coder_jsonl_trace_id_field_map(self) -> None:
        manifest = load_manifest_mode_map(
            _manifest_rows(
                utterance="a short learner utterance",
                mode="pre_submit",
                question_id="q-punc-1",
                cls="breadth",
            )
        )
        recs = [
            _rec(
                task_id="task-1",
                coach_mode="pre_submit",
                task_input="a short learner utterance",
            )
        ]
        classified, _ = check_posture(recs, manifest=manifest)
        rows, holdout, _ = build_coder_rows(
            recs,
            classified,
            manifest=manifest,
            provenance="synthetic",
            seed=42,
            holdout_fraction=0.0,  # isolate the field map — no holdout draw
        )
        assert len(rows) == 1
        row = rows[0]
        # C11 field map — the open-coder requires trace_id; prompt/final_answer
        # are the coder's working columns.
        assert row["trace_id"] == "task-1"
        assert row["prompt"] == "a short learner utterance"
        assert row["final_answer"] == "a coach reply that guides without leaking"
        # metadata per C11.
        assert row["mode"] == "pre_submit"
        assert row["question_id"] == "q-punc-1"
        assert row["provenance"] == "synthetic"
        assert row["stratum"] == "breadth"
        assert "meta" in row and isinstance(row["meta"], dict)

    def test_write_coder_jsonl_is_valid_for_open_coder(self, tmp_path: Path) -> None:
        """serve_open_coder._validate_jsonl requires a trace_id per JSON row."""
        rows = [
            {"trace_id": "t1", "prompt": "p", "final_answer": "a", "mode": "pre_submit"}
        ]
        path = tmp_path / "sample.jsonl"
        write_coder_jsonl(path, rows)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            assert "trace_id" in obj

    def test_production_row_without_manifest_omits_question_id(self) -> None:
        recs = [
            _rec(
                task_id="prod-1",
                coach_mode="pre_submit",
                task_input="a real learner utterance",
            )
        ]
        classified, _ = check_posture(recs, manifest=None)
        rows, _, _ = build_coder_rows(
            recs,
            classified,
            manifest=None,
            provenance="production",
            seed=42,
            holdout_fraction=0.0,  # isolate the field map — no holdout draw
        )
        row = rows[0]
        assert row["provenance"] == "production"
        # question_id/stratum unknown without a manifest — present-but-None, not
        # fabricated.
        assert row.get("question_id") is None
        assert row.get("stratum") is None


# ---------------------------------------------------------------------------
# FR-G2.4 — confounds excluded from export (BEFORE happy path)
# ---------------------------------------------------------------------------


class TestConfoundExcluded:
    def test_confound_excluded_from_export(self) -> None:
        # missing carrier -> confound (FR-G1.2)
        bad = _rec(task_id="bad", coach_mode=None, task_input="no marker here")
        good = _rec(
            task_id="good", coach_mode="pre_submit", task_input="a fine utterance"
        )
        manifest = load_manifest_mode_map(
            _manifest_rows(utterance="a fine utterance", mode="pre_submit")
        )
        classified, _ = check_posture([bad, good], manifest=manifest)
        rows, holdout, report = build_coder_rows(
            [bad, good],
            classified,
            manifest=manifest,
            provenance="synthetic",
            seed=42,
            holdout_fraction=0.0,  # no holdout — isolation for the confound test
        )
        shipped = {r["trace_id"] for r in rows}
        assert "bad" not in shipped
        assert "good" in shipped
        assert report.confound_excluded == 1


# ---------------------------------------------------------------------------
# FR-G2.5 — per-mode shortfall when under the gate (BEFORE implying met)
# ---------------------------------------------------------------------------


class TestShortfallReport:
    def test_posture_shortfall_when_under_gate(self) -> None:
        from meta.subject_coach_corpus_harvest import GATE_TURNS_PER_MODE

        recs = [_rec(task_id="only-one", coach_mode="pre_submit", task_input="ok")]
        classified, posture = check_posture(recs, manifest=None)
        _, _, report = build_coder_rows(
            recs,
            classified,
            manifest=None,
            provenance="synthetic",
            seed=42,
            holdout_fraction=0.0,
        )
        assert report.per_mode == {"pre_submit": 1, "post_feedback": 0}
        assert report.shortfall == {
            "pre_submit": GATE_TURNS_PER_MODE - 1,
            "post_feedback": GATE_TURNS_PER_MODE,
        }
        assert report.gate_met is False


# ---------------------------------------------------------------------------
# Holdout candidacy: partial_context rows are never held out (FR-G1.3)
# ---------------------------------------------------------------------------


class TestPartialContextNeverHeldOut:
    def test_partial_context_ships_in_coding_sample(self) -> None:
        from meta.coach_corpus_posture import EVAL_CAPTURE_TASK_INPUT_CAP

        truncated = "x" * EVAL_CAPTURE_TASK_INPUT_CAP
        rec = _rec(task_id="pc1", coach_mode="pre_submit", task_input=truncated)
        classified, _ = check_posture([rec], manifest=None)
        rows, holdout, report = build_coder_rows(
            [rec],
            classified,
            manifest=None,
            provenance="synthetic",
            seed=42,
            holdout_fraction=1.0,  # hold out EVERYTHING eligible — pc must still ship
        )
        shipped = {r["trace_id"] for r in rows}
        assert "pc1" in shipped
        assert "pc1" not in holdout
        assert report.partial_context_rows == 1
