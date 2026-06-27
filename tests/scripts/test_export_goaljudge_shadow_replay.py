"""Tests for Stage 4 §8.3 shadow-replay export."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_goaljudge_shadow_replay import export_shadow_replay
from tests.fixtures.goaljudge.langfuse_replay import (
    TRACE_ID_TO_REGISTRY_ID,
    load_replayed_verdicts,
)


def _write_evals(path: Path, trace_id: str, verdict: dict) -> None:
    row = {
        "target": "goal_judge",
        "task_id": trace_id,
        "ai_response": verdict,
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


class TestExportShadowReplay:
    def test_writes_anchor_rows_from_evals_log(self, tmp_path: Path) -> None:
        trace_id = next(iter(TRACE_ID_TO_REGISTRY_ID))
        evals = tmp_path / "evals.log"
        out = tmp_path / "replay.json"
        _write_evals(
            evals,
            trace_id,
            {"goal_met": False, "partial_fraction": 0.0, "rationale": "test"},
        )

        count, missing = export_shadow_replay(
            evals_path=str(evals),
            out_path=str(out),
            use_langfuse_fallback=False,
        )

        assert count == 1
        assert missing  # other anchors absent
        loaded = load_replayed_verdicts(out)
        assert trace_id in {
            tid for tid, rid in TRACE_ID_TO_REGISTRY_ID.items() if rid in loaded
        }
        assert loaded[TRACE_ID_TO_REGISTRY_ID[trace_id]]["goal_met"] is False

    def test_missing_all_anchors_returns_full_missing_list(
        self, tmp_path: Path
    ) -> None:
        evals = tmp_path / "empty.log"
        evals.write_text("", encoding="utf-8")
        out = tmp_path / "replay.json"

        count, missing = export_shadow_replay(
            evals_path=str(evals),
            out_path=str(out),
            use_langfuse_fallback=False,
        )

        assert count == 0
        assert set(missing) == set(TRACE_ID_TO_REGISTRY_ID.values())
        assert not out.exists() or json.loads(out.read_text()) == []
