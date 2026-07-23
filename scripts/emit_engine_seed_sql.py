"""Emit the multi-source engine content seed SQL (coach-v3 durable FR-G1/G2/G4).

Reconciles ALL authoritative content tables into
``frontend/drizzle/seed_engine_content.sql``:

- ``test_item`` ← ``docs/plan/coach-item-bank-live.promoted.json`` (987 items)
- ``hint`` ← ``docs/plan/coach-bank-hints.seed.json``
- ``skill`` ← embedded DEV taxonomy (``seedDevTaxonomy`` / ``_dev_seed.ts``)
- ``tutorial`` ← embedded lesson seed (``seedLessonContent`` / ``_lesson_seed.ts``)
- ``content_string`` ← per-mode session target defaults (``session.target_count.*``)
- ``test_blueprint`` ← default ACT-English blueprint

Inserts use ``ON CONFLICT … DO UPDATE`` (never ``DO NOTHING`` — FR-G2). Rows
present in pg but dropped from the source are soft-retired
(``reviewed = false``) with **no DELETE** anywhere in the bundle. Learner write
tables (``quiz_session`` / ``attempt`` / ``skill_state`` / ``progress_point``)
are never touched (FR-G4).

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

# Canonical small sources that live as TS constants today (seedDevTaxonomy /
# seedLessonContent / session-target policy). Embedded so the SQL emitter does
# not need a TS parser; keep byte-stable and mirrored with those modules.
DEFAULT_SKILLS: list[dict[str, Any]] = [
    {
        "id": "s-punc",
        "subject": "act-english",
        "key": "punctuation",
        "name": "Punctuation",
        "share_of_test_pct": 15,
        "accent_var": "--color-bucket-punctuation",
        "description": "Commas, semicolons, colons, dashes, and apostrophes.",
        "order": 1,
    },
    {
        "id": "s-gram",
        "subject": "act-english",
        "key": "grammar",
        "name": "Usage",
        "share_of_test_pct": 20,
        "accent_var": "--color-bucket-usage",
        "description": "Subject–verb agreement, pronouns, verb tense, idioms.",
        "order": 2,
    },
    {
        "id": "s-sent",
        "subject": "act-english",
        "key": "sentence",
        "name": "Sentence Structure",
        "share_of_test_pct": 20,
        "accent_var": "--color-bucket-sentence-structure",
        "description": "Fragments, run-ons, modifiers, and parallelism.",
        "order": 3,
    },
    {
        "id": "s-rhet",
        "subject": "act-english",
        "key": "rhetoric",
        "name": "Rhetoric",
        "share_of_test_pct": 20,
        "accent_var": "--color-bucket-rhetoric",
        "description": "Word choice, tone, and conciseness in context.",
        "order": 4,
    },
    {
        "id": "s-org",
        "subject": "act-english",
        "key": "organization",
        "name": "Organization",
        "share_of_test_pct": 15,
        "accent_var": "--color-bucket-organization",
        "description": "Transitions, sentence order, and opening/closing sentences.",
        "order": 5,
    },
    {
        "id": "s-style",
        "subject": "act-english",
        "key": "style",
        "name": "Conciseness",
        "share_of_test_pct": 10,
        "accent_var": "--color-bucket-conciseness",
        "description": "Redundancy, wordiness, and consistent register.",
        "order": 6,
    },
]

DEFAULT_TUTORIALS: list[dict[str, Any]] = [
    {
        "id": "tut-hand-nec-s-punc",
        "subject": "act-english",
        "skill_id": "s-punc",
        "body_md": (
            "Run the removal test: lift the clause out of the sentence. If it "
            "still stands, the clause is non-essential — fence it with a pair "
            "of commas. If the clause pins down which thing you mean, it's "
            "essential — no commas."
        ),
        "examples": [
            "My kitchen, which provides an alternative to eating out, is small.",
            "The car that I bought is electric.",
        ],
        "generated_from": "hand:rajnish@2026-07-11",
        "reviewed": True,
        "ground_md": (
            "You already use commas every day — to list things, to mark a "
            "pause, to keep parts of a sentence from colliding. Nothing here "
            "is new machinery; it builds on habits you already have."
        ),
        "pitfall_md": (
            "But one clause can need a pair of commas while another needs "
            "none — and the wrong choice quietly flips what the sentence "
            "means. The clauses that catch people cluster right after words "
            'like "which" and "who."'
        ),
        "question_md": "So how do you tell when a clause actually needs its commas?",
        "self_explain_prompt": (
            "Before you read the rule — take a guess. When do you think a "
            "clause needs commas around it?"
        ),
        "worked_example": {
            "sentence": (
                "My kitchen, which provides an alternative to eating out, is small."
            ),
            "steps": [
                'Remove the clause → "My kitchen is small." Still a complete sentence.',
                "So the clause is extra detail — non-essential.",
                "Non-essential → fence it with a pair of commas.",
            ],
            "answer": "Keep both commas.",
        },
        "completion_try": {
            "sentence": "The teacher, who grades fairly, is popular.",
            "choices": [
                {"text": "Keep both commas", "correct": True},
                {"text": "Delete the commas", "correct": False},
            ],
            "why": (
                'Remove "who grades fairly" → "The teacher is popular" still '
                "stands, so the clause is non-essential — keep both commas."
            ),
        },
        "annotated_examples": [
            {
                "pre": "My kitchen",
                "clause": "which provides an alternative to eating out",
                "post": " is small.",
                "essential": False,
                "callouts": [
                    'remove it → "My kitchen is small." still works',
                    "so → fence with a pair of commas",
                ],
            },
            {
                "pre": "The car ",
                "clause": "that I bought",
                "post": " is electric.",
                "essential": True,
                "callouts": ["identifies which car → essential → no commas"],
            },
        ],
    }
]

DEFAULT_CONTENT_STRINGS: list[dict[str, Any]] = [
    {
        "subject": "act-english",
        "key": "session.target_count.adaptive",
        "locale": "en",
        "value": "30",
    },
    {
        "subject": "act-english",
        "key": "session.target_count.drill",
        "locale": "en",
        "value": "30",
    },
    {
        "subject": "act-english",
        "key": "session.target_count.review",
        "locale": "en",
        "value": "30",
    },
]

DEFAULT_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "id": "bp-act-english-default",
        "subject": "act-english",
        "skill_mix": {
            "s-punc": 0.15,
            "s-gram": 0.20,
            "s-sent": 0.20,
            "s-rhet": 0.20,
            "s-org": 0.15,
            "s-style": 0.10,
        },
        "difficulty_dist": {"2": 0.2, "3": 0.5, "4": 0.3},
        "count": 30,
        "minutes": 35,
        "scale_band_table": [
            {"raw_min": 0, "raw_max": 10, "scale": 10},
            {"raw_min": 11, "raw_max": 20, "scale": 20},
            {"raw_min": 21, "raw_max": 30, "scale": 30},
        ],
        "pass_criteria": None,
        "seed": 1,
    }
]

_HEADER = """\
-- seed_engine_content.sql — multi-source engine content reconciliation
-- GENERATED FILE — do not edit by hand.
--
-- Emitted by scripts/emit_engine_seed_sql.py (coach-v3 durable FR-G1/G2/G4).
-- Applied by frontend/scripts/migrate_engine.mjs AFTER 0000–0004 every run
-- (the seed is idempotent DO UPDATE reconciliation — ledgering it would skip
-- a re-emit and reintroduce FR-G2 drift).
--
-- Soft-retire (reviewed=false), never hard-DELETE. No learner write tables.
-- Transaction ownership: migrate_engine.mjs wraps each file in one txn —
-- this file must NOT contain BEGIN/COMMIT (nested BEGIN warns in PG).
-- Regenerate:
--   .venv/bin/python scripts/emit_engine_seed_sql.py

"""


def _die(msg: str) -> None:
    raise SystemExit(f"emit_engine_seed_sql: {msg}")


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


def _load_optional_array(
    path: Path | None, default: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if path is None:
        return list(default)
    return _load_json_array(path)


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
) -> None:
    """Read all content sources and write the transactional reconciliation SQL."""
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

    skills = _load_optional_array(skills_path, DEFAULT_SKILLS)
    skills.sort(key=lambda r: (int(r.get("order", 0)), str(r["id"])))
    tutorials = _load_optional_array(tutorials_path, DEFAULT_TUTORIALS)
    tutorials.sort(key=lambda r: str(r["id"]))
    content_strings = _load_optional_array(
        content_strings_path, DEFAULT_CONTENT_STRINGS
    )
    content_strings.sort(
        key=lambda r: (
            str(r.get("subject", "")),
            str(r.get("key", "")),
            str(r.get("locale", "")),
        )
    )
    blueprints = _load_optional_array(blueprints_path, DEFAULT_BLUEPRINTS)
    blueprints.sort(key=lambda r: str(r["id"]))

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument("--hints", type=Path, default=DEFAULT_HINTS)
    parser.add_argument("--skills", type=Path, default=None)
    parser.add_argument("--tutorials", type=Path, default=None)
    parser.add_argument("--content-strings", type=Path, default=None)
    parser.add_argument("--blueprints", type=Path, default=None)
    parser.add_argument("--sql-out", type=Path, default=DEFAULT_SQL_OUT)
    args = parser.parse_args()
    emit_engine_seed_sql(
        test_items_path=args.test_items,
        hints_path=args.hints,
        skills_path=args.skills,
        tutorials_path=args.tutorials,
        content_strings_path=args.content_strings,
        blueprints_path=args.blueprints,
        sql_out=args.sql_out,
    )
    print(f"emitted {args.sql_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
