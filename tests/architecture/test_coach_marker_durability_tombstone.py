"""Architecture gate: the ADR-0034 coach-marker durability time-box tombstone.

ADR-0034 defers coach-session-marker durability: the deploy slice ships the
in-memory `InMemoryCoachMarkerRepo` (fails closed), time-boxed to the threads BFF
Cloud SQL bind, with **D4** (frontend `PgCoachMarkerRepo` on the same
`DATABASE_URL` + a *wired* migrate path) named as the closer. The ADR's own
rationale (mirroring the ADR-0011/0012/0013 lesson, and shaped exactly like
`test_no_client_served_test_keys.py`) is that a prose "we'll do D4 later" rots; a
mechanical tombscheck does not. This module is that check.

The real forgot-D4 failure is NOT "URL present but repo still in-memory"
(unreachable — `selectCoachMarkerRepo` switches to `PgCoachMarkerRepo` the instant
`DATABASE_URL` is set). It is **`PgCoachMarkerRepo` running against an un-migrated
table**: the frontend has no migration runner today (the coach-marker migration
`frontend/lib/adapters/thread_store/db/migrations/0001_coach_session_marker.sql`
is a loose SQL file no script/Dockerfile/deploy phase runs; the drizzle-kit
`frontend/drizzle/` dir holds only unrelated test-item migrations), so binding
`DATABASE_URL` **without** wiring an apply path makes the repo's fail-closed
`catch` strip answer fields *forever* — the same silent UX hole, harder to spot.

Two assertions, both green under today's world:

  1. **Tombstone tripwire (FR-15)** — parse `infra/gcp/cloud-run-frontend.tf`. IF it
     binds a real `DATABASE_URL` env var THEN a migrate-apply path for `0001` must
     exist (a `db:migrate` script in `frontend/package.json`, a Dockerfile step, or
     a deploy phase). ELSE pass. **Green today** — the frontend binds NO
     `DATABASE_URL` (only a `#` comment names it, as the no-cloud-creds invariant
     F-R9 requires), so the antecedent is false. Goes **red** when a future TF diff
     binds `DATABASE_URL` without wiring the apply path; **green again** once D4
     (bind + wired migrate) lands. The conscious bind+migrate pairing cannot be
     skipped silently. This is NOT a red-in-CI-today reminder (rejected as a G8
     smell) — antecedent-false → passing.

  2. **Docs-integrity** — ADR-0034 still names the in-memory time-box, D4 as the
     closer, and the migration path. A silent strip of the deferral's rationale is
     the weakening this gate catches (the tripwire-on-the-tripwire).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FRONTEND_TF = _REPO_ROOT / "infra/gcp/cloud-run-frontend.tf"
_FRONTEND_PKG = _REPO_ROOT / "frontend/package.json"
_FRONTEND_DOCKERFILE = _REPO_ROOT / "frontend/Dockerfile"
_MARKER_MIGRATION = (
    _REPO_ROOT
    / "frontend/lib/adapters/thread_store/db/migrations/0001_coach_session_marker.sql"
)
_ADR = _REPO_ROOT / "docs/adr/0034-coach-marker-in-memory-until-threads-bind.md"

# A real Cloud Run env binding in the TF: `env { name = "DATABASE_URL" ... }`.
# NOT the `#`-comment on the no-cloud-creds line — comments are stripped first.
_DATABASE_URL_ENV_RE = re.compile(r'name\s*=\s*"DATABASE_URL"')

# The ADR vocabulary that must remain present (any silent removal is the
# weakening this gate exists to catch).
_REQUIRED_ADR_MARKERS = (
    "InMemoryCoachMarkerRepo",
    "time-box",
    "D4",
    "0001_coach_session_marker.sql",
    "PgCoachMarkerRepo",
)


def _strip_tf_comments(text: str) -> str:
    """Drop full-line and trailing `#` comments so the `#`-comment naming
    DATABASE_URL on the no-cloud-creds line is never a false positive."""
    out_lines = []
    for line in text.splitlines():
        hash_idx = line.find("#")
        out_lines.append(line if hash_idx == -1 else line[:hash_idx])
    return "\n".join(out_lines)


def _frontend_binds_database_url() -> bool:
    text = _strip_tf_comments(_FRONTEND_TF.read_text())
    return _DATABASE_URL_ENV_RE.search(text) is not None


def _migrate_apply_path_exists() -> bool:
    """A wired apply path for the coach-marker migration: a `db:migrate`-style
    script in package.json, a migrate step in the Dockerfile, or (documented) a
    deploy phase. Today none exist — the migration is runner-less."""
    if _FRONTEND_PKG.exists():
        pkg = _FRONTEND_PKG.read_text()
        # A scripts entry that runs migrations (db:migrate / migrate:deploy / drizzle-kit migrate).
        if re.search(r'"[^"]*migrate[^"]*"\s*:', pkg) or "drizzle-kit migrate" in pkg:
            return True
    if _FRONTEND_DOCKERFILE.exists():
        docker = _FRONTEND_DOCKERFILE.read_text()
        if "migrate" in docker or "0001_coach_session_marker" in docker:
            return True
    return False


class TestCoachMarkerDurabilityTombstone:
    def test_database_url_binding_requires_a_migrate_apply_path(self) -> None:
        """FR-15 tombstone. Antecedent-false today (frontend binds no DATABASE_URL)
        ⇒ pass. When a TF diff binds DATABASE_URL, a migrate-apply path for the
        coach-marker migration 0001 must exist in the SAME change (D4 = bind +
        wired migrate), else PgCoachMarkerRepo runs against an un-migrated table and
        fails closed forever. That paired failure is the designed tripwire signal."""
        assert _FRONTEND_TF.exists(), (
            "infra/gcp/cloud-run-frontend.tf is missing — the frontend deploy "
            "surface has no record; the durability tombstone cannot anchor."
        )
        assert _MARKER_MIGRATION.exists(), (
            "The coach-marker migration 0001_coach_session_marker.sql is gone from "
            "frontend/lib/adapters/thread_store/db/migrations/ — ADR-0034's named D4 "
            "target no longer exists; restore it or re-open ADR-0034."
        )
        if _frontend_binds_database_url():
            assert _migrate_apply_path_exists(), (
                "cloud-run-frontend.tf now binds DATABASE_URL, but NO migrate-apply "
                "path exists for the coach-marker migration 0001_coach_session_marker"
                ".sql (no db:migrate script in frontend/package.json, no Dockerfile "
                "migrate step, no deploy phase). PgCoachMarkerRepo would run against "
                "an un-migrated table and strip answer fields forever (fail-closed). "
                "This is the forgot-D4 failure ADR-0034 names: wire the apply path in "
                "the SAME change that binds DATABASE_URL (D4 = bind + migrate), or "
                "re-open ADR-0034."
            )

    def test_adr_0034_time_box_and_d4_closer_are_present(self) -> None:
        """Docs-integrity: ADR-0034 still names the in-memory time-box, D4 as the
        closer, PgCoachMarkerRepo, and the migration path. A silent strip weakens
        the deferral's tripwire (the deferral is only safe while this text is
        load-bearing and present)."""
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
