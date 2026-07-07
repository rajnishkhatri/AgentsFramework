"""FR-E3 — re-verify the checked-in hint corpus against the leakage gate.

The corpus rows earned ``reviewed=true`` through the live cascade, but the
checked-in artifact can drift (a hand edit, a bad merge). This suite re-runs
the SAME deterministic ``check_rung_leakage`` predicate over every canonical
corpus row against its bank item — pure functions, no LLM, so the leak-free
property is re-proven on every ``make check``, not just at generation time.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from components.hint_leakage import check_rung_leakage

_REPO = Path(__file__).resolve().parent.parent.parent
_SEED_JSON = _REPO / "docs" / "plan" / "coach-bank-hints.seed.json"
_BANK_TS = _REPO / "frontend" / "lib" / "adapters" / "engine" / "_test_item_bank.ts"


def _bank_items() -> dict[str, dict]:
    """Extract the TEST_ITEM_BANK rows from the TS literal (JSON-quoted keys —
    the seed-file convention the provenance gates also rely on)."""
    source = _BANK_TS.read_text(encoding="utf-8")
    lb = source.index("= [", source.index("export const TEST_ITEM_BANK")) + 2
    depth = 0
    rb = lb
    for i in range(lb, len(source)):
        if source[i] == "[":
            depth += 1
        elif source[i] == "]":
            depth -= 1
            if depth == 0:
                rb = i
                break
    literal = re.sub(r",(\s*[}\]])", r"\1", source[lb : rb + 1])
    return {row["id"]: row for row in json.loads(literal)}


def _corpus_rows() -> list[dict]:
    return json.loads(_SEED_JSON.read_text(encoding="utf-8"))["rows"]


def test_every_corpus_row_passes_the_deterministic_leakage_gate() -> None:
    items = _bank_items()
    rows = _corpus_rows()
    assert rows, "canonical corpus is empty"
    offenders: list[str] = []
    for row in rows:
        question = items.get(row["question_id"])
        if question is None:
            offenders.append(f"{row['id']}: no bank item {row['question_id']!r}")
            continue
        violations = check_rung_leakage(row["body_md"], question)
        if violations:
            offenders.append(
                f"{row['question_id']}#{row['rung']}: {violations} — {row['body_md'][:80]!r}"
            )
    assert offenders == [], "checked-in hint rows leak: " + "; ".join(offenders)


def test_extractor_sees_the_committed_bank() -> None:
    """Guard the helper: a bank-format drift that blinds the extractor would
    otherwise let the leakage re-verification pass vacuously."""
    items = _bank_items()
    assert len(items) >= 8, f"expected >=8 bank items, extractor saw {len(items)}"
    assert all(i.startswith("ti-gen-") for i in items)


def test_gate_still_fails_a_leaky_body() -> None:
    """Red anchor: the predicate wired here can actually fire."""
    items = _bank_items()
    some_item = next(iter(items.values()))
    leaky = f"The answer is {some_item['answer_letter']} — pick it."
    assert check_rung_leakage(leaky, some_item), "leakage gate went blind"


if not _SEED_JSON.exists():  # pragma: no cover
    pytest.skip("canonical corpus not generated yet", allow_module_level=True)
