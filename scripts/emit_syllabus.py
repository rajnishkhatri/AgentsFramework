"""Emit the two generated syllabus planes from the canonical corpus.

Single-source seam of the D3 syllabus substrate (spec FR-9): the checked-in
`docs/plan/act-english-syllabus.seed.json` — the brainstorm's 32-topic ACT
English extraction table as data — is the ONLY hand-edited artifact; this
converter deterministically emits

- ``frontend/lib/adapters/engine/_act_english_syllabus.ts`` — the D4
  consumption plane (`ACT_ENGLISH_SYLLABUS` rows, data-plane only until the
  D4 taxonomy spec wires it);
- ``components/act_english_syllabus.py`` — pure stdlib data asset for
  coverage tooling and generation targeting.

Deterministic and offline: stdlib only, byte-stable for a given corpus (rows
sorted by ``standard_id``). Never edit the emitted files by hand — the drift
test re-emits and compares (FR-10). Regenerate:

    .venv/bin/python scripts/emit_syllabus.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_SEED = _REPO / "docs" / "plan" / "act-english-syllabus.seed.json"
DEFAULT_TS_OUT = (
    _REPO / "frontend" / "lib" / "adapters" / "engine" / "_act_english_syllabus.ts"
)
DEFAULT_PY_OUT = _REPO / "components" / "act_english_syllabus.py"

_ROW_FIELDS = ("standard_id", "name", "category", "bands", "app_skill")
_CATEGORIES = ("production", "knowledge", "conventions")
_APP_SKILLS = ("s-org", "s-rhet", "s-gram", "s-style", "s-punc", "s-sent")
_STANDARD_COUNT = 32

_GENERATED_NOTE = (
    "GENERATED FILE — do not edit by hand. Emitted from the canonical\n"
    " * docs/plan/act-english-syllabus.seed.json (the human-gated 32-topic\n"
    " * extraction of docs/ACT-syllabus/act-english.pdf, brainstorm\n"
    " * docs/plan/act-english-full-bank.brainstorm.md). Regenerate (emits this\n"
    " * file AND components/act_english_syllabus.py):\n"
    " *\n"
    " *   .venv/bin/python scripts/emit_syllabus.py"
)


def _die(msg: str) -> None:
    raise SystemExit(f"emit_syllabus: {msg}")


def _validate(rows: list[dict[str, Any]]) -> None:
    if len(rows) != _STANDARD_COUNT:
        _die(f"expected exactly {_STANDARD_COUNT} standards, got {len(rows)}")
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for row in rows:
        rid = row.get("standard_id", "?")
        extra = set(row) - set(_ROW_FIELDS)
        missing = [f for f in _ROW_FIELDS if f not in row]
        if extra or missing:
            _die(
                f"standard {rid}: missing fields {missing}, unknown fields {sorted(extra)}"
            )
        if not isinstance(rid, int) or not 1 <= rid <= _STANDARD_COUNT:
            _die(f"standard_id must be an int in 1..{_STANDARD_COUNT}, got {rid!r}")
        if rid in seen_ids:
            _die(f"duplicate standard_id {rid}")
        seen_ids.add(rid)
        name = str(row["name"]).strip()
        if not name:
            _die(f"standard {rid}: empty name")
        if name in seen_names:
            _die(f"standard {rid}: duplicate name {name!r}")
        seen_names.add(name)
        if row["category"] not in _CATEGORIES:
            _die(
                f"standard {rid}: category must be one of {_CATEGORIES}, got {row['category']!r}"
            )
        if row["app_skill"] not in _APP_SKILLS:
            _die(
                f"standard {rid}: app_skill must be one of {_APP_SKILLS}, got {row['app_skill']!r}"
            )
        bands = row["bands"]
        if (
            not isinstance(bands, list)
            or not bands
            or bands != sorted(set(bands))
            or not all(isinstance(b, int) and 1 <= b <= 5 for b in bands)
        ):
            _die(
                f"standard {rid}: bands must be a sorted, unique, non-empty subset of 1..5, got {bands!r}"
            )
    if seen_ids != set(range(1, _STANDARD_COUNT + 1)):
        _die(
            f"standard_ids must cover 1..{_STANDARD_COUNT} exactly; missing {sorted(set(range(1, 33)) - seen_ids)}"
        )


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: int(r["standard_id"]))


def _ts_row(row: dict[str, Any]) -> str:
    body = json.dumps({f: row[f] for f in _ROW_FIELDS}, indent=4, ensure_ascii=False)
    return "  " + body.replace("\n", "\n  ")


def _render_ts(rows: list[dict[str, Any]]) -> str:
    row_blocks = ",\n".join(_ts_row(r) for r in rows)
    return f"""/**
 * The ACT-English syllabus plane (D3 syllabus-substrate spec FR-9) —
 * {_GENERATED_NOTE}
 *
 * DATA PLANE ONLY until the D4 topic-taxonomy spec wires it into the wire
 * kernel and scheduler (docs/plan/act-english-topic-taxonomy.spec.md).
 * Nothing imports this module today; standard names/order for any future
 * surface come from HERE, never a duplicated list.
 */

export interface ActEnglishStandard {{
  readonly standard_id: number;
  readonly name: string;
  readonly category: "production" | "knowledge" | "conventions";
  readonly bands: readonly number[];
  readonly app_skill: string;
}}

export const ACT_ENGLISH_SYLLABUS: readonly ActEnglishStandard[] = [
{row_blocks},
];
"""


def _py_str(s: str) -> str:
    """A Python string literal in ruff-format style: double quotes, single
    only when that avoids escaping — the emitted module must pass the repo's
    ``format-check`` gate byte-identically (no post-format drift)."""
    if '"' in s and "'" not in s:
        return f"'{s}'"
    return json.dumps(s, ensure_ascii=False)


def _py_bands(bands: list[int]) -> str:
    inner = ", ".join(str(b) for b in bands)
    return f"({inner},)" if len(bands) == 1 else f"({inner})"


def _render_py(rows: list[dict[str, Any]]) -> str:
    entries = "\n".join(
        f"    ActEnglishStandard(\n"
        f"        standard_id={int(row['standard_id'])},\n"
        f"        name={_py_str(row['name'])},\n"
        f"        category={_py_str(row['category'])},\n"
        f"        bands={_py_bands(row['bands'])},\n"
        f"        app_skill={_py_str(row['app_skill'])},\n"
        f"    ),"
        for row in rows
    )
    generated_note = _GENERATED_NOTE.replace(" * ", "").replace(" *", "")
    return f'''"""Generated ACT-English syllabus data asset (D3 spec FR-9).

{generated_note}

Pure stdlib data: consumed by coverage tooling (the standard x band ratchet)
and generation targeting. The frontend twin is
``frontend/lib/adapters/engine/_act_english_syllabus.ts``; both planes are
pinned byte-for-byte to the canonical seed by the FR-10 drift test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ActEnglishStandard:
    """One syllabus standard: a teachable ACT-English topic with the score
    bands it appears in and the app practice skill that owns it."""

    standard_id: int
    name: str
    category: str
    bands: tuple[int, ...]
    app_skill: str


ACT_ENGLISH_SYLLABUS: Final[tuple[ActEnglishStandard, ...]] = (
{entries}
)
'''


def emit_syllabus(seed: Path, ts_out: Path, py_out: Path) -> None:
    """Read the canonical syllabus JSON and write both generated planes."""
    try:
        rows = json.loads(seed.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"cannot read corpus {seed}: {exc}")
        return  # unreachable; keeps the type-checker happy
    if not isinstance(rows, list):
        _die("corpus must be a JSON array of standards")
    _validate(rows)
    ordered = _sorted_rows(rows)
    ts_out.write_text(_render_ts(ordered), encoding="utf-8")
    py_out.write_text(_render_py(ordered), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--ts-out", type=Path, default=DEFAULT_TS_OUT)
    parser.add_argument("--py-out", type=Path, default=DEFAULT_PY_OUT)
    args = parser.parse_args()
    emit_syllabus(args.seed, args.ts_out, args.py_out)
    print(f"emitted {args.ts_out} and {args.py_out} from {args.seed}", file=sys.stderr)


if __name__ == "__main__":
    main()
