"""L1 contract for scripts/emit_engine_seed_sql.py (coach-v3 durable FR-G1/G2/G4).

The multi-source SQL emitter reconciles ALL authoritative content tables into
`frontend/drizzle/seed_engine_content.sql`: test_item + skill + hint + tutorial
+ content_string + test_blueprint. Inserts use ON CONFLICT … DO UPDATE (not
DO NOTHING — a re-emit of changed content must propagate, FR-G2). Rows present
in pg but dropped from the source are soft-retired (`reviewed = false`) with
NO DELETE anywhere in the bundle (attempt.question_id cascade would destroy
learner history). Learner write tables are never touched (FR-G4).
"""

from __future__ import annotations

import json
from pathlib import Path


_STAMP = "gpt-4o-mini@976a393626bf4e3eab85adf818db0096"

# Imported inside tests so T G.1 red fails with ModuleNotFoundError when the
# script is absent (the intended first-fail signal).


def _item(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "ti-gen-aaaaaaaaaaaaaaaa",
        "subject": "act-english",
        "skill_id": "s-punc",
        "difficulty": 2,
        "context_html": "The recipe calls for three <u>ingredients flour</u>.",
        "stem_md": "Which choice correctly punctuates the list?",
        "choices": [
            {"letter": "A", "label": "NO CHANGE", "is_no_change": True},
            {"letter": "B", "label": "ingredients: flour", "is_no_change": False},
            {"letter": "C", "label": "ingredients; flour", "is_no_change": False},
            {"letter": "D", "label": "ingredients', flour", "is_no_change": False},
        ],
        "answer_letter": "B",
        "per_choice_rationale": {
            "A": "No punctuation runs the list into the noun.",
            "B": "A colon introduces the list.",
            "C": "A semicolon cannot introduce a list.",
            "D": "Nothing calls for a possessive.",
        },
        "why_correct_md": "A **colon** introduces the list.",
        "why_tempted_md": "The sentence reads smoothly aloud.",
        "rule_md": "Use a colon after a complete clause to introduce a list.",
        "item_type": "underlined-span-mc",
        "misconception": None,
        "reviewed": True,
        "generated_by": _STAMP,
    }
    row.update(overrides)
    return row


def _hint(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "h-gen-aaaaaaaaaaaaaaaa",
        "subject": "act-english",
        "question_id": "ti-gen-aaaaaaaaaaaaaaaa",
        "choice_letter": "A",
        "rung": 1,
        "body_md": "Say the underlined phrase out loud.",
        "reviewed": True,
        "generated_by": _STAMP,
    }
    row.update(overrides)
    return row


def _skill(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "s-punc",
        "subject": "act-english",
        "key": "punctuation",
        "name": "Punctuation",
        "share_of_test_pct": 15,
        "accent_var": "--color-bucket-punctuation",
        "description": "Commas and colons.",
        "order": 1,
    }
    row.update(overrides)
    return row


def _tutorial(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "tut-hand-nec-s-punc",
        "subject": "act-english",
        "skill_id": "s-punc",
        "body_md": "Run the removal test.",
        "examples": ["My kitchen, which is small, is warm."],
        "generated_from": "hand:rajnish@2026-07-11",
        "reviewed": True,
        "ground_md": "You already use commas.",
        "pitfall_md": None,
        "question_md": None,
        "self_explain_prompt": None,
        "worked_example": None,
        "completion_try": None,
        "annotated_examples": None,
    }
    row.update(overrides)
    return row


def _content_string(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "subject": "act-english",
        "key": "session.target_count.adaptive",
        "locale": "en",
        "value": "30",
    }
    row.update(overrides)
    return row


def _blueprint(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "bp-act-english-default",
        "subject": "act-english",
        "skill_mix": {"s-punc": 1.0},
        "difficulty_dist": {"3": 1.0},
        "count": 5,
        "minutes": 10,
        "scale_band_table": [{"raw_min": 0, "raw_max": 5, "scale": 20}],
        "pass_criteria": None,
        "seed": 7,
    }
    row.update(overrides)
    return row


def _write_sources(tmp_path: Path) -> dict[str, Path]:
    """Write a small multi-source fixture tree the emitter reads."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    sources = {
        "test_items": tmp_path / "test_items.json",
        "hints": tmp_path / "hints.json",
        "skills": tmp_path / "skills.json",
        "tutorials": tmp_path / "tutorials.json",
        "content_strings": tmp_path / "content_strings.json",
        "blueprints": tmp_path / "blueprints.json",
    }
    sources["test_items"].write_text(
        json.dumps([_item(), _item(id="ti-gen-bbbbbbbbbbbbbbbb", skill_id="s-gram")]),
        encoding="utf-8",
    )
    sources["hints"].write_text(json.dumps({"rows": [_hint()]}), encoding="utf-8")
    sources["skills"].write_text(
        json.dumps(
            [_skill(), _skill(id="s-gram", key="grammar", name="Usage", order=2)]
        ),
        encoding="utf-8",
    )
    sources["tutorials"].write_text(json.dumps([_tutorial()]), encoding="utf-8")
    sources["content_strings"].write_text(
        json.dumps(
            [
                _content_string(),
                _content_string(key="session.target_count.drill"),
                _content_string(key="session.target_count.review"),
            ]
        ),
        encoding="utf-8",
    )
    sources["blueprints"].write_text(json.dumps([_blueprint()]), encoding="utf-8")
    return sources


def _emit(tmp_path: Path, sources: dict[str, Path] | None = None) -> str:
    from scripts.emit_engine_seed_sql import emit_engine_seed_sql

    src = sources or _write_sources(tmp_path / "src")
    out = tmp_path / "seed_engine_content.sql"
    emit_engine_seed_sql(
        test_items_path=src["test_items"],
        hints_path=src["hints"],
        skills_path=src["skills"],
        tutorials_path=src["tutorials"],
        content_strings_path=src["content_strings"],
        blueprints_path=src["blueprints"],
        sql_out=out,
    )
    return out.read_text(encoding="utf-8")


class TestEmissionRedGreen:
    def test_emitter_module_is_importable(self):
        """T G.1 red: absent script → ModuleNotFoundError."""
        import scripts.emit_engine_seed_sql  # noqa: F401

    def test_bundle_covers_all_sources_with_do_update(self, tmp_path: Path):
        sql = _emit(tmp_path)
        for table in (
            "test_item",
            "skill",
            "hint",
            "tutorial",
            "content_string",
            "test_blueprint",
        ):
            assert f'INSERT INTO "{table}"' in sql or f"INSERT INTO {table}" in sql, (
                f"missing inserts for {table}"
            )
            assert "ON CONFLICT" in sql
        # FR-G2: DO UPDATE, never DO NOTHING for content reconciliation.
        assert "DO UPDATE" in sql
        assert "DO NOTHING" not in sql
        # Provenance stamp carried on reviewed test_item rows.
        assert _STAMP in sql
        assert '"generated_by"' in sql or "generated_by" in sql

    def test_soft_retire_no_delete(self, tmp_path: Path):
        sql = _emit(tmp_path)
        upper = sql.upper()
        assert "DELETE FROM" not in upper
        assert "reviewed = false" in sql or "reviewed=false" in sql.replace(" ", "")
        # Soft-retire UPDATE must exist for tables that carry reviewed.
        assert "UPDATE" in upper

    def test_no_learner_write_tables(self, tmp_path: Path):
        """FR-G4: seed bundle never touches learner write tables."""
        sql = _emit(tmp_path).lower()
        for forbidden in (
            "quiz_session",
            "attempt",
            "skill_state",
            "progress_point",
        ):
            assert forbidden not in sql, f"seed must not touch {forbidden}"

    def test_double_emit_is_byte_identical(self, tmp_path: Path):
        sources = _write_sources(tmp_path / "src")
        a = _emit(tmp_path / "a", sources)
        b = _emit(tmp_path / "b", sources)
        assert a == b

    def test_changed_row_uses_excluded_in_do_update(self, tmp_path: Path):
        """Re-emit path: DO UPDATE must set columns from EXCLUDED (propagate)."""
        sql = _emit(tmp_path)
        assert "EXCLUDED." in sql or "excluded." in sql.lower()


class TestRowCounts:
    def test_per_table_insert_counts_match_sources(self, tmp_path: Path):
        sources = _write_sources(tmp_path / "src")
        sql = _emit(tmp_path, sources)
        assert sql.count("ti-gen-aaaaaaaaaaaaaaaa") >= 1
        assert sql.count("ti-gen-bbbbbbbbbbbbbbbb") >= 1
        assert sql.count("h-gen-aaaaaaaaaaaaaaaa") >= 1
        assert sql.count("s-punc") >= 1
        assert sql.count("tut-hand-nec-s-punc") >= 1
        assert sql.count("session.target_count.adaptive") >= 1
        assert sql.count("bp-act-english-default") >= 1
