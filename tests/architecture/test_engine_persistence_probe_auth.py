"""Architecture gate: T R.6 — authenticated full-stack persistence probe (DoD §9).

Finding 4 from the coach-v3 end-to-end review: Phase Z's ``probe_engine_persistence.mjs``
steps d/e used raw SQL INSERT/SELECT (bypassing ``HttpEngineDb``, BFF auth, ownership,
and adapter idempotency), and the Playwright companion could false-pass when only the
session id changed.

This module tombstones the contract:
  (a) Playwright owns FR-A5/FR-B4 authenticated proof and must list attempts via BFF
  (b) Playwright must not treat session-id change alone as persistence evidence
  (c) The Node probe must not claim authenticated submit/resume via raw SQL step names
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PROBE_MJS = _REPO_ROOT / "frontend/scripts/probe_engine_persistence.mjs"
_PLAYWRIGHT = _REPO_ROOT / "frontend/e2e/full-stack/engine-persistence-probe.spec.ts"


class TestEnginePersistenceProbeAuth:
    def test_playwright_lists_attempts_via_bff(self) -> None:
        """T R.6 (c): attempt must be listable by the server (not only /session/active)."""
        text = _PLAYWRIGHT.read_text()
        assert "listSessionAttempts" in text, (
            "engine-persistence-probe.spec.ts must call listSessionAttempts "
            "(POST /api/engine/db/listSessionAttempts) so the attempt is proven "
            "listable through BFF auth + ownership"
        )
        assert "/api/engine/db/listSessionAttempts" in text or (
            "listSessionAttempts" in text and "/api/engine/db/" in text
        ), "listSessionAttempts must be invoked via the fine-grained BFF dispatcher"

    def test_playwright_rejects_session_id_change_alone(self) -> None:
        """T R.6: remove the false-pass when only session.id differs."""
        text = _PLAYWRIGHT.read_text()
        # The old probe accepted `body.session.id !== beforeBody.session?.id`
        # as sufficient evidence of durability — that is not an attempt proof.
        false_pass = re.search(
            r"session\.id\s*!==\s*beforeBody\.session\?\.\s*id"
            r"|beforeBody\.session\?\.\s*id\s*!==\s*.*session\.id",
            text,
        )
        assert false_pass is None, (
            "engine-persistence-probe must not treat session-id change alone as "
            "persistence evidence (T R.6 false-pass)"
        )
        assert "pointer_attempted" in text or "score_total" in text, (
            "probe must require pointer_attempted and/or running_score evidence"
        )

    def test_playwright_second_context_resumes_same_session(self) -> None:
        """T R.6 (c): shared-auth second context must resume the same open session."""
        text = _PLAYWRIGHT.read_text()
        assert "newContext" in text and "storageState" in text, (
            "probe must open a second browser context with shared auth storage"
        )
        assert "toBe(sessionId)" in text and "FR-B4" in text, (
            "second context must assert the same session id (FR-B4)"
        )

    def test_node_probe_does_not_claim_authenticated_submit_via_raw_sql(self) -> None:
        """T R.6 (a): DB-layer probe must not own FR-A5/FR-B4 end-to-end claims."""
        text = _PROBE_MJS.read_text()
        # Old step names claimed authenticated submit/resume while using raw SQL.
        assert 'step: "d_attempt_persisted"' not in text, (
            "probe_engine_persistence.mjs must not emit d_attempt_persisted "
            "(raw-SQL FR-A5 claim); authenticated proof lives in Playwright"
        )
        assert 'step: "e_resume_by_learner"' not in text, (
            "probe_engine_persistence.mjs must not emit e_resume_by_learner "
            "(raw-SQL FR-B4 claim); authenticated proof lives in Playwright"
        )
        # Must point operators at the Playwright companion for the auth path.
        assert "engine-persistence-probe.spec.ts" in text, (
            "Node probe must document that authenticated full-stack proof is "
            "engine-persistence-probe.spec.ts (T R.6)"
        )
