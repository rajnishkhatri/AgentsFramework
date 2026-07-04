"""axial_cite_check — exemplar-ID fidelity, the prose-emit gate (A5).

Failure paths first: the check exists to catch a citation whose trace doesn't
exist, or exists but lacks the claimed code — the exact D1 defect from the
iteration-2 review.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.skills.axial_coding.conftest import load

cc = load("axial_cite_check")


def _coded(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


_ROWS = [
    {
        "trace_id": "0d3f493f0001",
        "open_codes": ["leak-strong-implication", "hands-over-conclusion"],
    },
    {
        "trace_id": "00eda7de0002",
        "open_codes": ["no-teach-back", "leak-strong-implication"],
    },
]


class TestFailurePaths:
    def test_dangling_id_flagged(self, tmp_path: Path) -> None:
        coded = _coded(tmp_path / "c.jsonl", _ROWS)
        # '08...' matches nothing — the real dangling id from the review.
        problems = cc.check_citations(
            coded, [{"trace_id": "08abcd00", "code": "no-teach-back"}]
        )
        assert any("dangling" in p or "NO trace" in p for p in problems)

    def test_claimed_code_not_on_trace_flagged(self, tmp_path: Path) -> None:
        coded = _coded(tmp_path / "c.jsonl", _ROWS)
        # 0d3f493f does NOT carry no-teach-back — the exact D1 wrong-code cite.
        problems = cc.check_citations(
            coded, [{"trace_id": "0d3f493f", "code": "no-teach-back"}]
        )
        assert any("does NOT carry" in p and "no-teach-back" in p for p in problems)


class TestPasses:
    def test_faithful_citation_ok(self, tmp_path: Path) -> None:
        coded = _coded(tmp_path / "c.jsonl", _ROWS)
        # 00eda7de is the CORRECT no-teach-back exemplar (prefix cite).
        assert (
            cc.check_citations(
                coded, [{"trace_id": "00eda7de", "code": "no-teach-back"}]
            )
            == []
        )

    def test_prefix_resolution(self, tmp_path: Path) -> None:
        coded = _coded(tmp_path / "c.jsonl", _ROWS)
        # 8-char prefix resolves to the full id.
        assert (
            cc.check_citations(
                coded, [{"trace_id": "0d3f493f", "code": "leak-strong-implication"}]
            )
            == []
        )

    def test_main_exit_codes(self, tmp_path: Path) -> None:
        coded = _coded(tmp_path / "c.jsonl", _ROWS)
        cites_ok = tmp_path / "ok.json"
        cites_ok.write_text(
            json.dumps([{"trace_id": "00eda7de", "code": "no-teach-back"}])
        )
        assert cc.main(["--coded", str(coded), "--citations", str(cites_ok)]) == 0
        cites_bad = tmp_path / "bad.json"
        cites_bad.write_text(json.dumps([{"trace_id": "08zzzz", "code": "x"}]))
        assert cc.main(["--coded", str(coded), "--citations", str(cites_bad)]) == 1
