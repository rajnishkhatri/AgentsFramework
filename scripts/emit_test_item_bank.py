"""Emit the practice-bank serving plane from the frozen promoted corpus.

Single-source seam of the Phase B bank tranche (spec FR-6/FR-12, the
ADR-0014 `emit_hint_bank.py` pattern): the checked-in
`docs/plan/coach-item-bank-live.promoted.json` — the cascade's `passed` list
verbatim, every row EARNED through the verifier cascade
(components/test_item_generation.py: schema -> independent-solver key gate ->
duplicate) — is the ONLY hand-off artifact; this converter deterministically
emits `frontend/lib/adapters/engine/_test_item_bank.ts`.

Serving-plane transforms, both deliberate:

- each choice gains ``is_no_change`` (label == "NO CHANGE") — the wire
  `Choice` field the corpus rows don't carry;
- ``standard_id`` is tolerated on input rows and HELD BACK from emission
  until D4 declares it on the wire (D4 spec §4 emitter seam) — the Zod
  kernel would default-strip it anyway; withholding keeps the plane honest.

Deterministic and offline: stdlib only, byte-stable for a given corpus (rows
sorted by ``(skill_id, difficulty, id)``). Never edit the emitted file by
hand — `tests/architecture/test_test_item_provenance_confinement.py` scans it
and the parity test pins it against the corpus. Regenerate:

    .venv/bin/python scripts/emit_test_item_bank.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = _REPO / "docs" / "plan" / "coach-item-bank-live.promoted.json"
DEFAULT_TS_OUT = (
    _REPO / "frontend" / "lib" / "adapters" / "engine" / "_test_item_bank.ts"
)

# The _reviewed_row shape (ADR-0015 clause 1 + ADR-0021 teaching payload) —
# also the emitted field ORDER. standard_id is deliberately absent (D4 adds it).
_ROW_FIELDS = (
    "id",
    "subject",
    "skill_id",
    "difficulty",
    "context_html",
    "stem_md",
    "choices",
    "answer_letter",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
    "rule_md",
    "item_type",
    "misconception",  # C2 / ADR-0027 — nullable authored one-liner
    "reviewed",
    "generated_by",
)
_TEACHING_FIELDS = ("why_correct_md", "why_tempted_md", "rule_md")

# ADR-0015 clause 6 — the provenance confinement gate's own pattern.
_CASCADE_PROVENANCE = re.compile(r"^[^@\s]+@[^@\s]+$")

_GENERATED_NOTE = (
    "GENERATED FILE — do not edit rows by hand; re-run the promotion +\n"
    " * this emitter instead. Every row was EARNED through the Python\n"
    " * verifier cascade (components/test_item_generation.py: schema ->\n"
    " * independent-solver key gate -> duplicate) driven by\n"
    " * scripts/generate_test_items.py; `generated_by` carries the promoting\n"
    ' * run\'s "<model>@<run_id>" stamp (ADR-0015 clause 6);\n'
    " * tests/architecture/test_test_item_provenance_confinement.py scans\n"
    " * THIS file. Regenerate (reads\n"
    " * docs/plan/coach-item-bank-live.promoted.json, emits this file):\n"
    " *\n"
    " *   .venv/bin/python scripts/emit_test_item_bank.py"
)


def _die(msg: str) -> None:
    raise SystemExit(f"emit_test_item_bank: {msg}")


def _validate(rows: list[dict[str, Any]]) -> None:
    if not rows:
        _die("promoted corpus is empty — refusing to emit a blank bank")
    seen_ids: set[str] = set()
    seen_stems: set[str] = set()
    for row in rows:
        rid = row.get("id", "?")
        missing = [f for f in _ROW_FIELDS if f not in row]
        if missing:
            _die(f"row {rid}: missing fields {missing}")
        if row["reviewed"] is not True:
            _die(f"row {rid}: bank rows are cascade-earned; reviewed must be true")
        if not _CASCADE_PROVENANCE.match(str(row["generated_by"])):
            _die(
                f"row {rid}: generated_by {row['generated_by']!r} is not the "
                "'<model>@<run_id>' cascade stamp"
            )
        letters = [c.get("letter") for c in row["choices"]]
        if len(letters) < 4:
            _die(f"row {rid}: fewer than 4 choices")
        if row["answer_letter"] not in letters:
            _die(
                f"row {rid}: answer_letter {row['answer_letter']!r} not among {letters}"
            )
        rationale = row["per_choice_rationale"]
        missing_rationale = [
            ltr for ltr in letters if not str(rationale.get(ltr, "")).strip()
        ]
        if missing_rationale:
            _die(f"row {rid}: per_choice_rationale missing letters {missing_rationale}")
        for field in _TEACHING_FIELDS:
            if not str(row[field]).strip():
                _die(f"row {rid}: empty {field}")
        if rid in seen_ids:
            _die(f"duplicate row id {rid}")
        seen_ids.add(rid)
        stem = " ".join(str(row["stem_md"]).lower().split())
        if stem in seen_stems:
            _die(f"row {rid}: duplicate stem after normalization")
        seen_stems.add(stem)


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (str(r["skill_id"]), int(r["difficulty"] or 0), str(r["id"])),
    )


def _serving_row(row: dict[str, Any]) -> dict[str, Any]:
    """Project onto the allowlist + derive the wire-only choice field."""
    projected = {f: row[f] for f in _ROW_FIELDS}
    projected["choices"] = [
        {
            "letter": c["letter"],
            "label": c["label"],
            "is_no_change": c["label"] == "NO CHANGE",
        }
        for c in row["choices"]
    ]
    return projected


def _ts_row(row: dict[str, Any]) -> str:
    body = json.dumps(_serving_row(row), indent=4, ensure_ascii=False)
    return "  " + body.replace("\n", "\n  ")


def _render_ts(rows: list[dict[str, Any]]) -> str:
    row_blocks = ",\n".join(_ts_row(r) for r in rows)
    return f"""/**
 * The governed practice item bank (ADR-0021) — cascade-promoted TestItem rows.
 *
 * {_GENERATED_NOTE}
 *
 * SERVING. Loaded by the browser composition root (dev guard, the _dev_seed
 * precedent) into the test_item table; the practice quiz reads it ONLY through
 * TestItemQuestionRepo over TestItemRepo.listReviewed (reviewed rows only).
 * JSON-quoted keys are deliberate: the provenance detector matches the quoted
 * form.
 */

import type {{ TestItem }} from "../../wire/engine_entities";
import type {{ InMemoryEngineDb }} from "./db/in_memory_engine_db";

export const TEST_ITEM_BANK: readonly TestItem[] = [
{row_blocks},
];

/** Load the promoted bank into the browser-safe engine DB (composition-only). */
export function seedTestItemBank(db: InMemoryEngineDb): void {{
  db.seedTestItems([...TEST_ITEM_BANK]);
}}
"""


def emit_test_item_bank(corpus_path: Path, ts_out: Path) -> None:
    """Read the frozen promoted corpus and write the serving plane."""
    try:
        rows = json.loads(corpus_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"cannot read corpus {corpus_path}: {exc}")
        return  # unreachable; keeps the type-checker happy
    if not isinstance(rows, list):
        _die("corpus must be a JSON array of promoted rows")
    # C2 / ADR-0027: every serving row carries misconception (string | null).
    for row in rows:
        if not isinstance(row, dict):
            _die("corpus rows must be objects")
        if "misconception" not in row:
            row["misconception"] = None
        elif row["misconception"] == "":
            row["misconception"] = None
    _validate(rows)
    ts_out.write_text(_render_ts(_sorted_rows(rows)), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--ts-out", type=Path, default=DEFAULT_TS_OUT)
    args = parser.parse_args()
    emit_test_item_bank(args.corpus, args.ts_out)
    print(f"emitted {args.ts_out} from {args.corpus}", file=sys.stderr)


if __name__ == "__main__":
    main()
