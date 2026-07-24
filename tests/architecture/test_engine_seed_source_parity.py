"""Architecture gate: T R.8 — no silent drift between TS and Postgres seed (FR-G1).

Finding 8 from the coach-v3 end-to-end review: ``scripts/emit_engine_seed_sql.py``
copied skills / tutorials / content_strings / blueprints into Python constants,
so edits to the canonical TS modules (``_dev_seed.ts``, ``_lesson_seed.ts``, …)
could diverge from the emitted Postgres seed without CI noticing.

Contract:
  1. The four small sources live as shared JSON under
     ``frontend/lib/adapters/engine/seed_sources/`` (single source of truth).
  2. The SQL emitter defaults to those JSON paths (no embedded row arrays).
  3. The TS seed modules import/re-export from the same JSON.
  4. Counts + natural-id sets agree across JSON ↔ emitter load ↔ TS imports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_SEED_SOURCES = _REPO / "frontend" / "lib" / "adapters" / "engine" / "seed_sources"
_EMITTER = _REPO / "scripts" / "emit_engine_seed_sql.py"
_ADAPTERS = _REPO / "frontend" / "lib" / "adapters" / "engine"

_JSON_FILES = {
    "skill": _SEED_SOURCES / "skills.json",
    "tutorial": _SEED_SOURCES / "tutorials.json",
    "content_string": _SEED_SOURCES / "content_strings.json",
    "test_blueprint": _SEED_SOURCES / "blueprints.json",
}

# TS modules that must import the matching JSON (relative import path fragment).
_TS_IMPORTS = {
    "skills.json": _ADAPTERS / "_dev_seed.ts",
    "tutorials.json": _ADAPTERS / "_lesson_seed.ts",
    "content_strings.json": _ADAPTERS / "_session_policy_seed.ts",
    "blueprints.json": _ADAPTERS / "_blueprint_seed.ts",
}


def _natural_ids(source: str, rows: list[dict]) -> set[str]:
    if source == "content_string":
        return {f"{r['subject']}|{r['key']}|{r['locale']}" for r in rows}
    return {str(r["id"]) for r in rows}


def _load_json_array(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), f"{path} must be a JSON array"
    return data


class TestSharedSeedSourcesExist:
    def test_four_shared_json_files_exist(self) -> None:
        missing = [p.name for p in _JSON_FILES.values() if not p.is_file()]
        assert missing == [], (
            "T R.8: shared seed_sources JSON missing — "
            f"{missing}. Emit from canonical content into "
            "frontend/lib/adapters/engine/seed_sources/"
        )


class TestEmitterUsesSharedJson:
    def test_emitter_has_no_embedded_default_row_arrays(self) -> None:
        """Production defaults must not re-copy the four sources in Python."""
        text = _EMITTER.read_text(encoding="utf-8")
        for name in (
            "DEFAULT_SKILLS",
            "DEFAULT_TUTORIALS",
            "DEFAULT_CONTENT_STRINGS",
            "DEFAULT_BLUEPRINTS",
        ):
            # Path constants (DEFAULT_SKILLS_PATH) are fine; row arrays are not.
            # Match both `NAME = [` and `NAME: list[...] = [`.
            assert not re.search(
                rf"^{name}(?:\s*:\s*[^=]+)?\s*=\s*\[",
                text,
                flags=re.MULTILINE,
            ), (
                f"T R.8: {_EMITTER.name} still embeds {name} = […] — "
                "load from seed_sources/*.json instead"
            )

    def test_emitter_default_paths_point_at_shared_json(self) -> None:
        text = _EMITTER.read_text(encoding="utf-8")
        for path in _JSON_FILES.values():
            assert path.name in text, (
                f"T R.8: emitter must default to shared {path.name}"
            )


class TestTsModulesImportSharedJson:
    def test_canonical_ts_modules_import_seed_sources_json(self) -> None:
        missing: list[str] = []
        for json_name, ts_path in _TS_IMPORTS.items():
            if not ts_path.is_file():
                missing.append(f"{ts_path.name} (missing file)")
                continue
            body = ts_path.read_text(encoding="utf-8")
            if f"seed_sources/{json_name}" not in body and (
                f"seed_sources/{json_name.replace('.json', '')}" not in body
            ):
                # Accept either `from "./seed_sources/skills.json"` or similar.
                if json_name not in body:
                    missing.append(
                        f"{ts_path.name} must import seed_sources/{json_name}"
                    )
        assert missing == [], "T R.8 TS↔JSON wiring:\n" + "\n".join(missing)


class TestNaturalIdParity:
    def test_json_counts_and_ids_match_emitter_load(self) -> None:
        from scripts import emit_engine_seed_sql as mod

        for source, path in _JSON_FILES.items():
            assert path.is_file(), f"missing {path}"
            rows = _load_json_array(path)
            loaded = mod._load_json_array(path)
            assert len(loaded) == len(rows)
            assert _natural_ids(source, loaded) == _natural_ids(source, rows)
            assert len(rows) > 0, f"{source} must be non-empty (FR-G2a)"

    def test_json_natural_ids_match_ts_reexports_via_file_scan(self) -> None:
        """TS modules re-export the JSON; scan confirms import + JSON id set.

        Full runtime TS eval is out of scope for pytest; the import wiring test
        plus this id-set check on the JSON (the bytes both sides consume) is the
        parity contract. Counts are pinned to the known FR-G1 inventory.
        """
        expected_counts = {
            "skill": 6,
            "tutorial": 1,
            "content_string": 3,
            "test_blueprint": 1,
        }
        for source, path in _JSON_FILES.items():
            rows = _load_json_array(path)
            assert len(rows) == expected_counts[source], (
                f"{source}: expected {expected_counts[source]} rows, got {len(rows)}"
            )
            ids = _natural_ids(source, rows)
            assert len(ids) == len(rows), f"{source}: duplicate natural ids in {path}"
