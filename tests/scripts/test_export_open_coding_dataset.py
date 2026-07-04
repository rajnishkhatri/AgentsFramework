"""Task 3.3d — coach open-coding dataset export wrapper (FR-G3.1.11–.12).

Failure/guard path first: the exporter DEFAULTS TO A DRY RUN — it must not touch
Langfuse unless --write is passed (FR-G3.1.12). Then the item shape + idempotent
uuid5 id (FR-G3.1.11). No network in these tests: we exercise the pure
row→item mapping + the dry-run main, never build_real_langfuse_dataset_client.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from scripts.export_coach_open_coding_to_dataset import (
    COACH_DATASET,
    build_dataset_item,
    main,
)


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "coded.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return p


_ROW = {
    "trace_id": "7c71871f",
    "prompt": "why is B wrong",
    "final_answer": "let's explore why B feels off",
    "mode": "pre_submit",
    "question_id": "q-1",
    "stratum": "breadth",
    "open_codes": ["clarification-instead-of-action"],
    "memo": "did not act",
}


class TestItemShape:
    def test_item_shape_and_idempotent_id(self) -> None:
        item = build_dataset_item(_ROW)
        # idempotent id = uuid5 of the trace_id (same scheme as the skill exporter)
        expected = uuid.uuid5(uuid.NAMESPACE_DNS, "opencode-ds:7c71871f").hex
        assert item["id"] == expected
        assert item["input"] == {
            "task": "why is B wrong",
            "mode": "pre_submit",
            "question_id": "q-1",
        }
        assert item["expected_output"] == "let's explore why B feels off"
        assert item["metadata"]["open_codes"] == ["clarification-instead-of-action"]
        assert item["metadata"]["memo"] == "did not act"
        assert item["metadata"]["stratum"] == "breadth"
        assert item["source_trace_id"] == "7c71871f"

    def test_id_is_stable_across_calls(self) -> None:
        assert build_dataset_item(_ROW)["id"] == build_dataset_item(dict(_ROW))["id"]


class TestDryRunDefault:
    def test_defaults_to_dry_run_no_write(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, [_ROW])
        # No --write: must return 0 and never construct a Langfuse client.
        # (If it tried, the missing creds / network would raise — a clean 0 proves
        #  the dry-run path took no client action.)
        rc = main(["--coded", str(path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert COACH_DATASET in out

    def test_dry_run_uses_coach_dataset_name(self, tmp_path: Path, capsys) -> None:
        path = _write(tmp_path, [_ROW])
        main(["--coded", str(path)])
        assert COACH_DATASET == "coach-phase3-open-coding"
