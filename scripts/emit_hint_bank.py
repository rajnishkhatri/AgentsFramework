"""Emit the two generated hint-bank serving modules from the canonical corpus.

Single-source seam of the coach-bank-hints increment (spec FR-B1..B3): the
checked-in `docs/plan/coach-bank-hints.seed.json` (cascade PASS rows + FR-A3
waivers) is the ONLY hand-off artifact; this converter deterministically emits

- ``frontend/lib/adapters/engine/_hint_bank.ts`` — `Hint` wire rows
  (JSON-quoted keys, the provenance-detector convention), the FR-A3 waiver
  table, and ``seedHintBank(db)`` (the ``_test_item_bank.ts`` pattern);
- ``components/subject_coach_bank_hints.py`` — ``BANK_RUNGS`` as `HintRung`
  literals, with the wire ``generated_by`` stamp carried verbatim on
  ``authored_by`` (FR-B3).

ADR-0035: optional ``choice_letter`` (null = Gen1 item-level; A–D = Gen2
choice-conditional); uniqueness on ``(question_id, choice_letter, rung)``;
rung 4 is stripped before emit (assertion stays off the wire per ADR-0012).

Deterministic and offline: stdlib only, byte-stable for a given corpus (rows
sorted by ``(question_id, choice_letter, rung)``). Never edit the emitted
files by hand — parity tests pin both against the JSON (FR-B2). Regenerate:

    .venv/bin/python scripts/emit_hint_bank.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_SEED = _REPO / "docs" / "plan" / "coach-bank-hints.seed.json"
DEFAULT_TS_OUT = _REPO / "frontend" / "lib" / "adapters" / "engine" / "_hint_bank.ts"
DEFAULT_PY_OUT = _REPO / "components" / "subject_coach_bank_hints.py"

_VALID_RUNGS = (1, 2, 3)
_VALID_LETTERS = ("A", "B", "C", "D")
_ROW_FIELDS = (
    "id",
    "subject",
    "question_id",
    "choice_letter",
    "rung",
    "body_md",
    "reviewed",
    "generated_by",
)

_GENERATED_NOTE = (
    "GENERATED FILE — do not edit by hand. Every row was EARNED through the\n"
    " * hint verifier cascade (components/hint_generation.py: schema ->\n"
    " * deterministic per-rung leakage -> duplicate) driven by\n"
    " * scripts/generate_hints.py; `generated_by` carries the promoting run's\n"
    ' * "<model>@<workflow_id>" stamp. Regenerate (reads\n'
    " * docs/plan/coach-bank-hints.seed.json, emits this file AND\n"
    " * components/subject_coach_bank_hints.py):\n"
    " *\n"
    " *   .venv/bin/python scripts/emit_hint_bank.py"
)


def _die(msg: str) -> None:
    raise SystemExit(f"emit_hint_bank: {msg}")


def _normalize_letter(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    letter = str(raw)
    if letter not in _VALID_LETTERS:
        _die(f"choice_letter must be one of {_VALID_LETTERS} or null, got {raw!r}")
    return letter


def _strip_rung4(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ADR-0035 / ADR-0012: assertion rung stays off the wire — drop, don't die."""
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in rows:
        if int(row.get("rung", 0)) == 4:
            dropped += 1
            continue
        kept.append(row)
    if dropped:
        print(
            f"emit_hint_bank: stripped {dropped} rung-4 row(s) (off-wire)",
            file=sys.stderr,
        )
    return kept


def _validate(rows: list[dict[str, Any]], waivers: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str | None, int]] = set()
    for row in rows:
        # choice_letter is optional in source JSON; normalize before field check.
        row["choice_letter"] = _normalize_letter(row.get("choice_letter"))
        missing = [f for f in _ROW_FIELDS if f not in row]
        if missing:
            _die(f"row {row.get('id', '?')} missing fields {missing}")
        if row["rung"] not in _VALID_RUNGS:
            _die(
                f"row {row['id']}: rung must be one of {_VALID_RUNGS}, got {row['rung']!r}"
            )
        if row["reviewed"] is not True:
            _die(
                f"row {row['id']}: corpus rows are cascade-earned; reviewed must be true"
            )
        if not str(row["body_md"]).strip():
            _die(f"row {row['id']}: empty body_md")
        if not str(row["generated_by"]).strip():
            _die(f"row {row['id']}: empty generated_by")
        key = (str(row["question_id"]), row["choice_letter"], int(row["rung"]))
        if key in seen:
            _die(
                f"duplicate (question_id, choice_letter, rung) {key} — "
                "ADR-0035 uniqueness"
            )
        seen.add(key)
    for waiver in waivers:
        if waiver.get("rung") not in _VALID_RUNGS or not str(
            waiver.get("question_id", "")
        ):
            _die(f"malformed waiver {waiver!r}")
        if not str(waiver.get("reason", "")).strip():
            _die(f"waiver {waiver['question_id']}#{waiver['rung']} needs a reason")


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            str(r["question_id"]),
            r["choice_letter"] or "",
            int(r["rung"]),
        ),
    )


def _ts_row(row: dict[str, Any]) -> str:
    body = json.dumps({f: row[f] for f in _ROW_FIELDS}, indent=4, ensure_ascii=False)
    return "  " + body.replace("\n", "\n  ")


def _render_ts(rows: list[dict[str, Any]], waivers: list[dict[str, Any]]) -> str:
    row_blocks = ",\n".join(_ts_row(r) for r in rows)
    waiver_blocks = ",\n".join(
        "  "
        + json.dumps(
            {
                "question_id": w["question_id"],
                "rung": w["rung"],
                "reason": w["reason"],
            },
            indent=4,
            ensure_ascii=False,
        ).replace("\n", "\n  ")
        for w in waivers
    )
    waiver_literal = f"[\n{waiver_blocks},\n]" if waivers else "[]"
    return f"""/**
 * The governed hint-ladder bank (coach-bank-hints spec FR-B1) —
 * {_GENERATED_NOTE}
 *
 * SERVING. Loaded by the browser composition root's dev-default branch via
 * `seedHintBank(db)` (next to `seedTestItemBank`); served ONLY through the
 * read-only `HintRepo` reviewed gate (ADR-0014/ADR-0035, FR-12). JSON-quoted
 * keys are deliberate: the provenance detector matches the quoted form.
 */

import type {{ Hint }} from "../../wire/engine_entities";
import type {{ InMemoryEngineDb }} from "./db/in_memory_engine_db";

export const HINT_BANK: readonly Hint[] = [
{row_blocks},
];

/**
 * Explicit FR-A3 waivers — (question_id, rung) ladder gaps the coverage
 * ratchet (`_hint_bank.test.ts`) accepts. An empty table means every
 * reviewed bank item carries a full 3-rung item-level ladder.
 */
export const HINT_BANK_WAIVERS: ReadonlyArray<{{
  readonly question_id: string;
  readonly rung: 1 | 2 | 3;
  readonly reason: string;
}}> = {waiver_literal};

/** Load the reviewed hint ladders into the dev in-memory engine DB. */
export function seedHintBank(db: InMemoryEngineDb): void {{
  db.seedHints([...HINT_BANK]);
}}
"""


def _py_str(s: str) -> str:
    """A Python string literal in ruff-format style: double quotes, single
    only when that avoids escaping — the emitted module must pass the repo's
    ``format-check`` gate byte-identically (no post-format drift)."""
    if '"' in s and "'" not in s:
        return f"'{s}'"
    return json.dumps(s, ensure_ascii=False)


def _render_py(rows: list[dict[str, Any]]) -> str:
    entries = "\n".join(
        f"    HintRung(\n"
        f"        question_id={_py_str(row['question_id'])},\n"
        f"        rung={int(row['rung'])},\n"
        f"        body_md={_py_str(row['body_md'])},\n"
        f"        reviewed=True,\n"
        f"        authored_by={_py_str(row['generated_by'])},\n"
        f"        choice_letter="
        f"{'None' if row['choice_letter'] is None else _py_str(row['choice_letter'])},\n"
        f"    ),"
        for row in rows
    )
    generated_note = _GENERATED_NOTE.replace(" * ", "").replace(" *", "")
    return f'''"""Generated bank hint-ladder rungs (coach-bank-hints spec FR-B1).

{generated_note}

``authored_by`` carries the wire ``generated_by`` stamp VERBATIM (FR-B3) — the
provenance value is identical on both serving planes. Served by
``components.subject_coach_hints.rungs_for_question`` (AUTHORED + BANK), which
imports this module lazily so this data asset stays one-way-importable.
"""

from __future__ import annotations

from typing import Final

from components.subject_coach_hints import HintRung

BANK_RUNGS: Final[list[HintRung]] = [
{entries}
]
'''


def emit_hint_bank(seed: Path, ts_out: Path, py_out: Path) -> None:
    """Read the canonical corpus JSON and write both generated modules."""
    try:
        corpus = json.loads(seed.read_text(encoding="utf-8"))
        rows = corpus["rows"]
        waivers = corpus.get("waivers", [])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _die(f"cannot read corpus {seed}: {exc}")
        return  # unreachable; keeps the type-checker happy
    if not isinstance(rows, list) or not isinstance(waivers, list):
        _die("corpus must be {'rows': [...], 'waivers': [...]}")
    rows = _strip_rung4(rows)
    _validate(rows, waivers)
    ordered = _sorted_rows(rows)
    ordered_waivers = sorted(
        waivers, key=lambda w: (str(w["question_id"]), int(w["rung"]))
    )
    ts_out.write_text(_render_ts(ordered, ordered_waivers), encoding="utf-8")
    py_out.write_text(_render_py(ordered), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--ts-out", type=Path, default=DEFAULT_TS_OUT)
    parser.add_argument("--py-out", type=Path, default=DEFAULT_PY_OUT)
    args = parser.parse_args()
    emit_hint_bank(args.seed, args.ts_out, args.py_out)
    print(f"emitted {args.ts_out} and {args.py_out} from {args.seed}", file=sys.stderr)


if __name__ == "__main__":
    main()
