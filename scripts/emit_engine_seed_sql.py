"""Emit the multi-source engine content seed SQL (coach-v3 durable FR-G1/G2/G2a/G4).

Reconciles ALL authoritative content tables into
``frontend/drizzle/seed_engine_content.sql``:

- ``test_item`` ← ``docs/plan/coach-item-bank-live.promoted.json`` (987 items)
- ``hint`` ← ``docs/plan/coach-bank-hints.seed.json``
- ``skill`` ← ``frontend/lib/adapters/engine/seed_sources/skills.json``
  (canonical; also imported by ``_dev_seed.ts`` / ``seedDevTaxonomy``)
- ``tutorial`` ← ``…/seed_sources/tutorials.json``
  (canonical; also imported by ``_lesson_seed.ts`` / ``seedLessonContent``)
- ``content_string`` ← ``…/seed_sources/content_strings.json``
  (``session.target_count.*``; also ``_session_policy_seed.ts``)
- ``test_blueprint`` ← ``…/seed_sources/blueprints.json``
  (also ``_blueprint_seed.ts``)

Inserts use ``ON CONFLICT … DO UPDATE`` (never ``DO NOTHING`` — FR-G2). Rows
present in pg but dropped from the source are soft-retired
(``reviewed = false``) with **no DELETE** anywhere in the bundle. Learner write
tables (``quiz_session`` / ``attempt`` / ``skill_state`` / ``progress_point``)
are never touched (FR-G4).

FR-G2a fail-closed: an empty or count-regressed source aborts before any
blanket ``reviewed = false`` update is emitted. Override only with an explicit
``--force-empty-<source>`` flag (documented destructive intent). Successful
emits ledger per-source counts next to the SQL
(``seed_engine_content.counts.json``).

Deterministic, stdlib-only. Regenerate:

    .venv/bin/python scripts/emit_engine_seed_sql.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_ITEMS = _REPO / "docs" / "plan" / "coach-item-bank-live.promoted.json"
DEFAULT_HINTS = _REPO / "docs" / "plan" / "coach-bank-hints.seed.json"
DEFAULT_SQL_OUT = _REPO / "frontend" / "drizzle" / "seed_engine_content.sql"
# T R.8 / FR-G1: the four small sources are shared JSON (single source of
# truth) — also imported by the canonical TS seed modules. No Python row
# copies; silent TS↔Postgres drift is gated by
# tests/architecture/test_engine_seed_source_parity.py.
_SEED_SOURCES = _REPO / "frontend" / "lib" / "adapters" / "engine" / "seed_sources"
DEFAULT_SKILLS_PATH = _SEED_SOURCES / "skills.json"
DEFAULT_TUTORIALS_PATH = _SEED_SOURCES / "tutorials.json"
DEFAULT_CONTENT_STRINGS_PATH = _SEED_SOURCES / "content_strings.json"
DEFAULT_BLUEPRINTS_PATH = _SEED_SOURCES / "blueprints.json"

# Authoritative sources gated by FR-G2a (table name == CLI ``--force-empty-*`` key).
SEED_SOURCES: tuple[str, ...] = (
    "test_item",
    "hint",
    "skill",
    "tutorial",
    "content_string",
    "test_blueprint",
)


class SeedSourceFailClosedError(Exception):
    """FR-G2a: empty or regressed source without ``--force-empty-<source>``."""

    def __init__(
        self,
        source: str,
        *,
        count: int,
        ledgered: int | None,
        reason: str,
    ) -> None:
        self.source = source
        self.count = count
        self.ledgered = ledgered
        self.reason = reason
        super().__init__(
            f"seed source {source!r} fail-closed ({reason}): count={count}"
            + (f", ledgered={ledgered}" if ledgered is not None else "")
            + f"; pass --force-empty-{source.replace('_', '-')} to override"
        )


# Small sources (skill / tutorial / content_string / test_blueprint) load
# from DEFAULT_*_PATH JSON above — see T R.8 / FR-G1 seed_sources parity.

_HEADER = """\
-- seed_engine_content.sql — multi-source engine content reconciliation
-- GENERATED FILE — do not edit by hand.
--
-- Emitted by scripts/emit_engine_seed_sql.py (coach-v3 durable FR-G1/G2/G2a/G4).
-- Applied by frontend/scripts/migrate_engine.mjs AFTER 0000–0004 every run
-- (the seed is idempotent DO UPDATE reconciliation — ledgering the SQL itself
-- would skip a re-emit and reintroduce FR-G2 drift; per-source *counts* are
-- ledgered separately in seed_engine_content.counts.json for FR-G2a).
--
-- Soft-retire (reviewed=false), never hard-DELETE. No learner write tables.
-- FR-G2a: empty/regressed sources fail closed unless --force-empty-<source>.
-- Transaction ownership: migrate_engine.mjs wraps each file in one txn —
-- this file must NOT contain BEGIN/COMMIT (nested BEGIN warns in PG).
-- Regenerate:
--   .venv/bin/python scripts/emit_engine_seed_sql.py

"""


def _die(msg: str) -> None:
    raise SystemExit(f"emit_engine_seed_sql: {msg}")


def _default_ledger_path(sql_out: Path) -> Path:
    """``seed_engine_content.sql`` → ``seed_engine_content.counts.json``."""
    return sql_out.with_name(f"{sql_out.stem}.counts.json")


def _load_count_ledger(path: Path) -> dict[str, int] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"cannot read count ledger {path}: {exc}")
    if not isinstance(data, dict):
        _die(f"count ledger {path} must be a JSON object")
    out: dict[str, int] = {}
    for key, value in data.items():
        if (
            not isinstance(key, str)
            or not isinstance(value, int)
            or isinstance(value, bool)
        ):
            _die(f"count ledger {path}: invalid entry {key!r}={value!r}")
        out[key] = value
    return out


def _write_count_ledger(path: Path, counts: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Stable key order matching SEED_SOURCES, then any extras.
    ordered = {src: counts[src] for src in SEED_SOURCES if src in counts}
    for key, value in counts.items():
        if key not in ordered:
            ordered[key] = value
    path.write_text(
        json.dumps(ordered, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def _assert_sources_fail_closed(
    counts: dict[str, int],
    *,
    ledger: dict[str, int] | None,
    force_empty: frozenset[str],
) -> None:
    """FR-G2a: abort on empty or regressed source unless explicitly forced."""
    unknown = force_empty - set(SEED_SOURCES)
    if unknown:
        _die(f"unknown --force-empty source(s): {sorted(unknown)}")
    for source in SEED_SOURCES:
        count = counts.get(source, 0)
        forced = source in force_empty
        if count == 0 and not forced:
            raise SeedSourceFailClosedError(
                source, count=0, ledgered=None, reason="empty"
            )
        if ledger is not None and source in ledger:
            prior = ledger[source]
            if count < prior and not forced:
                raise SeedSourceFailClosedError(
                    source,
                    count=count,
                    ledgered=prior,
                    reason="regressed",
                )


def _sql_str(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (dict, list)):
        raw = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    else:
        raw = str(value)
    escaped = raw.replace("'", "''")
    return f"'{escaped}'"


def _load_json_array(
    path: Path, *, wrap_key: str | None = None
) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _die(f"cannot read {path}: {exc}")
    if wrap_key is not None:
        if not isinstance(data, dict) or wrap_key not in data:
            _die(f"{path} must be an object with '{wrap_key}'")
        data = data[wrap_key]
    if not isinstance(data, list):
        _die(f"{path} must be a JSON array")
    rows: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            _die(f"{path}: rows must be objects")
        rows.append(row)
    return rows


def _load_optional_array(path: Path | None, default_path: Path) -> list[dict[str, Any]]:
    """Load a JSON array from ``path``, or from the shared default JSON path."""
    return _load_json_array(path if path is not None else default_path)


def _upsert(
    table: str,
    columns: tuple[str, ...],
    rows: list[dict[str, Any]],
    *,
    conflict: str,
    update_cols: tuple[str, ...],
) -> list[str]:
    lines: list[str] = [f"-- {table}: {len(rows)} row(s)"]
    if not rows:
        return lines
    col_list = ", ".join(f'"{c}"' for c in columns)
    set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
    for row in rows:
        values = ", ".join(_sql_str(row.get(c)) for c in columns)
        lines.append(
            f'INSERT INTO "{table}" ({col_list}) VALUES ({values})\n'
            f"ON CONFLICT ({conflict}) DO UPDATE SET {set_clause};"
        )
    return lines


def _soft_retire(table: str, id_col: str, keep_ids: list[str]) -> list[str]:
    """Mark source-absent rows reviewed=false. Never DELETE."""
    lines = [f"-- soft-retire {table} rows absent from source (FR-G2)"]
    if not keep_ids:
        lines.append(
            f'UPDATE "{table}" SET "reviewed" = false WHERE "reviewed" = true;'
        )
        return lines
    id_list = ", ".join(_sql_str(x) for x in keep_ids)
    lines.append(
        f'UPDATE "{table}" SET "reviewed" = false\n'
        f'WHERE "{id_col}" NOT IN ({id_list}) AND "reviewed" = true;'
    )
    return lines


def _normalize_item(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if "misconception" not in out or out["misconception"] == "":
        out["misconception"] = None
    # Derive is_no_change on choices when absent (matches emit_test_item_bank).
    choices = out.get("choices")
    if isinstance(choices, list):
        normalized: list[dict[str, Any]] = []
        for ch in choices:
            if not isinstance(ch, dict):
                continue
            c = dict(ch)
            if "is_no_change" not in c:
                label = str(c.get("label", ""))
                c["is_no_change"] = label.strip().upper() == "NO CHANGE"
            normalized.append(c)
        out["choices"] = normalized
    return out


def _normalize_hint(row: dict[str, Any]) -> dict[str, Any] | None:
    rung = row.get("rung")
    if rung == 4:
        return None  # assertion rung stays off the wire (ADR-0012)
    out = dict(row)
    letter = out.get("choice_letter")
    if letter == "":
        out["choice_letter"] = None
    return out


def emit_engine_seed_sql(
    *,
    test_items_path: Path,
    hints_path: Path,
    sql_out: Path,
    skills_path: Path | None = None,
    tutorials_path: Path | None = None,
    content_strings_path: Path | None = None,
    blueprints_path: Path | None = None,
    force_empty: frozenset[str] | None = None,
    ledger_path: Path | None = None,
) -> None:
    """Read all content sources and write the transactional reconciliation SQL.

    FR-G2a: aborts with ``SeedSourceFailClosedError`` (and writes nothing) when
    a source is empty or its count regresses below the previous ledger, unless
    that source is listed in ``force_empty``.
    """
    forced = force_empty or frozenset()
    counts_ledger_path = ledger_path or _default_ledger_path(sql_out)

    items = [_normalize_item(r) for r in _load_json_array(test_items_path)]
    items.sort(
        key=lambda r: (
            str(r.get("skill_id", "")),
            int(r.get("difficulty", 0)),
            str(r["id"]),
        )
    )

    raw_hints = _load_json_array(hints_path, wrap_key="rows")
    hints: list[dict[str, Any]] = []
    for r in raw_hints:
        h = _normalize_hint(r)
        if h is not None:
            hints.append(h)
    hints.sort(
        key=lambda r: (
            str(r.get("question_id", "")),
            str(r.get("choice_letter") or ""),
            int(r.get("rung", 0)),
            str(r["id"]),
        )
    )

    skills = _load_optional_array(skills_path, DEFAULT_SKILLS_PATH)
    skills.sort(key=lambda r: (int(r.get("order", 0)), str(r["id"])))
    tutorials = _load_optional_array(tutorials_path, DEFAULT_TUTORIALS_PATH)
    tutorials.sort(key=lambda r: str(r["id"]))
    content_strings = _load_optional_array(
        content_strings_path, DEFAULT_CONTENT_STRINGS_PATH
    )
    content_strings.sort(
        key=lambda r: (
            str(r.get("subject", "")),
            str(r.get("key", "")),
            str(r.get("locale", "")),
        )
    )
    blueprints = _load_optional_array(blueprints_path, DEFAULT_BLUEPRINTS_PATH)
    blueprints.sort(key=lambda r: str(r["id"]))

    counts = {
        "test_item": len(items),
        "hint": len(hints),
        "skill": len(skills),
        "tutorial": len(tutorials),
        "content_string": len(content_strings),
        "test_blueprint": len(blueprints),
    }
    # Fail closed BEFORE any SQL is written (no blanket retire on corrupt sources).
    _assert_sources_fail_closed(
        counts,
        ledger=_load_count_ledger(counts_ledger_path),
        force_empty=forced,
    )

    parts: list[str] = [_HEADER]

    # skill first (FK parent for test_item / tutorial).
    parts.extend(
        _upsert(
            "skill",
            (
                "id",
                "subject",
                "key",
                "name",
                "share_of_test_pct",
                "accent_var",
                "description",
                "order",
            ),
            skills,
            conflict='"id"',
            update_cols=(
                "subject",
                "key",
                "name",
                "share_of_test_pct",
                "accent_var",
                "description",
                "order",
            ),
        )
    )

    parts.extend(
        _upsert(
            "test_item",
            (
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
                "misconception",
                "reviewed",
                "generated_by",
            ),
            items,
            conflict='"id"',
            update_cols=(
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
                "misconception",
                "reviewed",
                "generated_by",
            ),
        )
    )
    parts.extend(_soft_retire("test_item", "id", [str(r["id"]) for r in items]))

    parts.extend(
        _upsert(
            "hint",
            (
                "id",
                "subject",
                "question_id",
                "choice_letter",
                "rung",
                "body_md",
                "reviewed",
                "generated_by",
            ),
            hints,
            conflict='"id"',
            update_cols=(
                "subject",
                "question_id",
                "choice_letter",
                "rung",
                "body_md",
                "reviewed",
                "generated_by",
            ),
        )
    )
    parts.extend(_soft_retire("hint", "id", [str(r["id"]) for r in hints]))

    parts.extend(
        _upsert(
            "tutorial",
            (
                "id",
                "subject",
                "skill_id",
                "body_md",
                "examples",
                "generated_from",
                "reviewed",
                "ground_md",
                "pitfall_md",
                "question_md",
                "self_explain_prompt",
                "worked_example",
                "completion_try",
                "annotated_examples",
            ),
            tutorials,
            conflict='"id"',
            update_cols=(
                "subject",
                "skill_id",
                "body_md",
                "examples",
                "generated_from",
                "reviewed",
                "ground_md",
                "pitfall_md",
                "question_md",
                "self_explain_prompt",
                "worked_example",
                "completion_try",
                "annotated_examples",
            ),
        )
    )
    parts.extend(_soft_retire("tutorial", "id", [str(r["id"]) for r in tutorials]))

    parts.extend(
        _upsert(
            "content_string",
            ("subject", "key", "locale", "value"),
            content_strings,
            conflict='"subject", "key", "locale"',
            update_cols=("value",),
        )
    )

    parts.extend(
        _upsert(
            "test_blueprint",
            (
                "id",
                "subject",
                "skill_mix",
                "difficulty_dist",
                "count",
                "minutes",
                "scale_band_table",
                "pass_criteria",
                "seed",
            ),
            blueprints,
            conflict='"id"',
            update_cols=(
                "subject",
                "skill_mix",
                "difficulty_dist",
                "count",
                "minutes",
                "scale_band_table",
                "pass_criteria",
                "seed",
            ),
        )
    )

    parts.append("")  # trailing newline via join
    sql_out.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(parts)
    if not text.endswith("\n"):
        text += "\n"
    sql_out.write_text(text, encoding="utf-8")
    # Ledger only after a successful write (FR-G2a ratchet for the next run).
    _write_count_ledger(counts_ledger_path, counts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test-items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--hints", type=Path, default=DEFAULT_HINTS)
    parser.add_argument("--skills", type=Path, default=DEFAULT_SKILLS_PATH)
    parser.add_argument("--tutorials", type=Path, default=DEFAULT_TUTORIALS_PATH)
    parser.add_argument(
        "--content-strings", type=Path, default=DEFAULT_CONTENT_STRINGS_PATH
    )
    parser.add_argument("--blueprints", type=Path, default=DEFAULT_BLUEPRINTS_PATH)
    parser.add_argument("--sql-out", type=Path, default=DEFAULT_SQL_OUT)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="Per-source count ledger path (default: <sql-out-stem>.counts.json)",
    )
    for source in SEED_SOURCES:
        flag = f"--force-empty-{source.replace('_', '-')}"
        parser.add_argument(
            flag,
            action="store_true",
            help=(
                f"FR-G2a override: allow empty/regressed {source} source "
                "(documented destructive intent — may blanket soft-retire)"
            ),
        )
    args = parser.parse_args()
    forced = frozenset(
        src for src in SEED_SOURCES if getattr(args, f"force_empty_{src}")
    )
    try:
        emit_engine_seed_sql(
            test_items_path=args.test_items,
            hints_path=args.hints,
            skills_path=args.skills,
            tutorials_path=args.tutorials,
            content_strings_path=args.content_strings,
            blueprints_path=args.blueprints,
            sql_out=args.sql_out,
            force_empty=forced,
            ledger_path=args.ledger,
        )
    except SeedSourceFailClosedError as exc:
        print(f"emit_engine_seed_sql: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"emitted {args.sql_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
