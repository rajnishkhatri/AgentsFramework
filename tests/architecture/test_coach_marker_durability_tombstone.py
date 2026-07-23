"""Architecture gate: ADR-0034 coach-marker durability — built path (T F.5).

ADR-0034 deferred coach-session-marker durability behind a time-box closed by
**D4** = frontend `DATABASE_URL` bind + a *wired* migrate path. Coach-v3 Track F
landed that pair:

- ``infra/gcp/cloud-run-frontend.tf`` binds server-side ``DATABASE_URL``
  (FR-F1, never ``NEXT_PUBLIC_*``)
- ``frontend/scripts/migrate_engine.mjs`` + ``frontend`` ``db:migrate:engine``
  apply ``frontend/drizzle/0*.sql`` (incl. threads + coach_session_marker via
  ``0000_frontend_baseline.sql``) and re-run ``seed_*.sql`` every deploy
- ``scripts/deploy_gcp.sh`` ``phase_frontend`` runs the migrate **pre-traffic**

This module previously guarded the *unbuilt* path (antecedent-false when TF
had no bind). T F.5 flips it to assert the **built** path — bind present AND
runner present — so a future diff that strips either side goes red.

G8: the prior ``test_database_url_binding_requires_a_migrate_apply_path`` name
is retained (same tripwire intent; assertion strengthened). Docs-integrity on
ADR-0034 vocabulary remains.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FRONTEND_TF = _REPO_ROOT / "infra/gcp/cloud-run-frontend.tf"
_FRONTEND_PKG = _REPO_ROOT / "frontend/package.json"
_MIGRATE_RUNNER = _REPO_ROOT / "frontend/scripts/migrate_engine.mjs"
_BASELINE = _REPO_ROOT / "frontend/drizzle/0000_frontend_baseline.sql"
_DEPLOY = _REPO_ROOT / "scripts/deploy_gcp.sh"
_MARKER_MIGRATION = (
    _REPO_ROOT
    / "frontend/lib/adapters/thread_store/db/migrations/0001_coach_session_marker.sql"
)
_ADR = _REPO_ROOT / "docs/adr/0034-coach-marker-in-memory-until-threads-bind.md"

_DATABASE_URL_ENV_RE = re.compile(r'name\s*=\s*"DATABASE_URL"')
_NEXT_PUBLIC_DB_RE = re.compile(r"NEXT_PUBLIC_.*DATABASE", re.IGNORECASE)

_REQUIRED_ADR_MARKERS = (
    "InMemoryCoachMarkerRepo",
    "time-box",
    "D4",
    "0001_coach_session_marker.sql",
    "PgCoachMarkerRepo",
)


def _strip_tf_comments(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        hash_idx = line.find("#")
        out_lines.append(line if hash_idx == -1 else line[:hash_idx])
    return "\n".join(out_lines)


def _frontend_binds_database_url() -> bool:
    text = _strip_tf_comments(_FRONTEND_TF.read_text())
    return _DATABASE_URL_ENV_RE.search(text) is not None


def _migrate_apply_path_exists() -> bool:
    if _MIGRATE_RUNNER.exists() and "migrate_engine" in _MIGRATE_RUNNER.read_text():
        if _FRONTEND_PKG.exists():
            pkg = _FRONTEND_PKG.read_text()
            if re.search(r'"[^"]*migrate[^"]*"\s*:', pkg):
                return True
    if _DEPLOY.exists() and "migrate_engine.mjs" in _DEPLOY.read_text():
        return True
    return False


class TestCoachMarkerDurabilityTombstone:
    def test_database_url_binding_requires_a_migrate_apply_path(self) -> None:
        """FR-15 / T F.5: the built path — bind AND runner must both exist.

        Stripping the TF bind OR the migrate runner (package script /
        migrate_engine.mjs / deploy pre-traffic step) fails this gate — the
        ADR-0034 forgot-D4 hole must not reopen.
        """
        assert _FRONTEND_TF.exists(), (
            "infra/gcp/cloud-run-frontend.tf is missing — the frontend deploy "
            "surface has no record; the durability tombstone cannot anchor."
        )
        assert _MARKER_MIGRATION.exists(), (
            "The coach-marker migration 0001_coach_session_marker.sql is gone from "
            "frontend/lib/adapters/thread_store/db/migrations/ — ADR-0034's named D4 "
            "target no longer exists; restore it or re-open ADR-0034."
        )
        assert _frontend_binds_database_url(), (
            "cloud-run-frontend.tf must bind server-side DATABASE_URL (FR-F1) — "
            "the coach-v3 durable path is incomplete without it."
        )
        tf = _FRONTEND_TF.read_text()
        assert _NEXT_PUBLIC_DB_RE.search(tf) is None, (
            "DATABASE_URL must stay server-side only (F-R9) — no NEXT_PUBLIC_* "
            "database exposure."
        )
        assert _migrate_apply_path_exists(), (
            "DATABASE_URL is bound but NO migrate-apply path exists "
            "(frontend/scripts/migrate_engine.mjs + db:migrate:engine / "
            "deploy_gcp.sh pre-traffic). PgCoachMarkerRepo would run against an "
            "un-migrated table and strip answer fields forever (fail-closed). "
            "Restore the runner or re-open ADR-0034."
        )
        assert _BASELINE.exists(), (
            "frontend/drizzle/0000_frontend_baseline.sql is missing — FR-F2/F3 "
            "CREATE TABLE baseline (engine + threads + coach_session_marker) "
            "must exist for the runner inventory."
        )
        baseline = _BASELINE.read_text()
        for table in (
            "coach_session_marker",
            "threads",
            "thread_messages",
            "test_item",
            "quiz_session",
        ):
            assert f'CREATE TABLE IF NOT EXISTS "{table}"' in baseline, (
                f"0000 baseline must CREATE {table} (FR-F2/F3)"
            )
        assert "checkpoint" not in baseline.lower() or "ABSENT" in baseline, (
            "0000 baseline must not create LangGraph checkpoint tables"
        )

    def test_adr_0034_time_box_and_d4_closer_are_present(self) -> None:
        """Docs-integrity: ADR-0034 still names the in-memory time-box, D4 as the
        closer, PgCoachMarkerRepo, and the migration path."""
        if not _ADR.exists():
            pytest.fail(
                "ADR-0034 is missing — the coach-marker durability deferral has no "
                "record; restore docs/adr/0034-coach-marker-in-memory-until-threads-"
                "bind.md (or re-open per its own trigger)."
            )
        text = _ADR.read_text()
        missing = [m for m in _REQUIRED_ADR_MARKERS if m not in text]
        assert missing == [], (
            "ADR-0034 has been weakened — these required markers are gone, and the "
            "in-memory deferral is no longer mechanically tombstoned (restore them or "
            "re-open the ADR per its own trigger section):\n  " + "\n  ".join(missing)
        )
