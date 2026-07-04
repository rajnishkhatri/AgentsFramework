"""axial_minimal_pairs — contract + pairing + normalization (FR-7/8/9a)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.skills.axial_coding.conftest import load

mp = load("axial_minimal_pairs")


def _coded(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


class TestContract:
    def test_rejects_row_missing_trace_id_or_codes(self, tmp_path: Path) -> None:
        coded = _coded(tmp_path / "c.jsonl", [{"prompt": "hi"}])
        with pytest.raises(ValueError, match="input contract"):
            mp.find_minimal_pairs(coded)


class TestNormalization:
    def test_prompt_normalization(self) -> None:
        # FR-9a: lowercase, collapse whitespace, strip surrounding punctuation.
        assert mp.normalize_prompt("  Cool, next!  ") == mp.normalize_prompt(
            "cool, next"
        )
        assert mp.normalize_prompt("Why  is   B  wrong?") == "why is b wrong"


class TestPairing:
    def test_same_prompt_divergent_codes_surfaced(self, tmp_path: Path) -> None:
        coded = _coded(
            tmp_path / "c.jsonl",
            [
                {
                    "trace_id": "clean",
                    "prompt": "cool, next",
                    "open_codes": ["redirects-off-topic"],
                },
                {
                    "trace_id": "leaky",
                    "prompt": "Cool, next!",  # normalizes to the same key
                    "open_codes": ["redirects-off-topic", "hands-over-conclusion"],
                },
            ],
        )
        pairs = mp.find_minimal_pairs(coded)
        assert len(pairs) == 1
        ids = {m["trace_id"] for m in pairs[0]["members"]}
        assert ids == {"clean", "leaky"}

    def test_identical_coding_is_not_a_pair(self, tmp_path: Path) -> None:
        coded = _coded(
            tmp_path / "c.jsonl",
            [
                {"trace_id": "a", "prompt": "same", "open_codes": ["x"]},
                {"trace_id": "b", "prompt": "same", "open_codes": ["x"]},
            ],
        )
        assert mp.find_minimal_pairs(coded) == []

    def test_row_without_prompt_skipped_not_crashed(self, tmp_path: Path) -> None:
        coded = _coded(
            tmp_path / "c.jsonl",
            [{"trace_id": "a", "open_codes": ["x"]}],  # no prompt -> graceful skip
        )
        assert mp.find_minimal_pairs(coded) == []
