"""Q5 deploy-proof gate: `scripts/smoke_gcp.sh` must assert `/learn`, not just `/`.

Spec FR-11/FR-12 (eng-coach-gcp-deploy): a bare frontend `/` 200 is NOT proof the
coach works — the root serves the sign-in CTA on any live frontend, seeded or not.
The smoke script must additionally request `/learn` unauthenticated and assert a
307/308 redirect to the WorkOS host (proving the route exists, the (coach)/layout
guard fires, and the new revision is live — without a session or any test
credential, keeping F-R9 intact).

The `/learn` assertion itself runs in the DEPLOY PIPELINE against a live revision
(FR-11/12 are pipeline-layer, not CI — no frontend URL in unit CI). This test is
the CI-runnable gate that the proof was ADDED and is STRUCTURALLY correct: it fails
if the `/learn` block is removed or weakened (e.g. reverted to accepting a `/` 200
alone), so the Q5 guard cannot silently regress. FR-13 (the authenticated render)
stays a manual DoD step — a skill/render assertion needs a session.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SMOKE = _REPO_ROOT / "scripts/smoke_gcp.sh"


def _smoke_text() -> str:
    assert _SMOKE.exists(), (
        "scripts/smoke_gcp.sh is missing — the deploy proof gate has no anchor."
    )
    return _SMOKE.read_text()


class TestSmokeLearnProof:
    def test_smoke_requests_the_learn_route(self) -> None:
        """FR-11: the smoke must probe `/learn`, not only `/` — a `/` 200 alone no
        longer passes the frontend gate."""
        text = _smoke_text()
        assert "/learn" in text, (
            "scripts/smoke_gcp.sh does not probe /learn — a bare `/` 200 is not proof "
            "the coach works (FR-11). Re-add the /learn deploy-proof block."
        )

    def test_smoke_asserts_learn_redirect_to_workos(self) -> None:
        """FR-12: unauthenticated `/learn` must be asserted to 307/308-redirect to a
        WorkOS/AuthKit host (route + guard + live revision)."""
        text = _smoke_text()
        # Status assertion: the /learn check must require a 307/308 redirect.
        assert "307" in text and "308" in text, (
            "smoke_gcp.sh must assert /learn returns 307/308 (unauth → WorkOS "
            "redirect) — FR-12."
        )
        # Location assertion: the redirect target must be the WorkOS/AuthKit host.
        assert ("workos" in text.lower()) and ("location" in text.lower()), (
            "smoke_gcp.sh must assert the /learn redirect Location points at the "
            "WorkOS/AuthKit host (FR-12) — proving the sign-in flow, not just any "
            "redirect."
        )

    def test_learn_proof_is_a_hard_fail_not_a_warn(self) -> None:
        """The /learn assertions must `fail` (exit 1), not `warn`/`SKIP` — a soft
        warning would let a broken coach revision pass the gate (FR-11 intent)."""
        text = _smoke_text()
        # Isolate the coach-route proof block (from its banner to the next banner).
        marker = "Coach route proof"
        assert marker in text, (
            f"expected a '{marker}' block in smoke_gcp.sh (FR-11/12)."
        )
        start = text.index(marker)
        rest = text[start:]
        end = rest.index("── 3.") if "── 3." in rest else len(rest)
        block = rest[:end]
        assert "fail " in block, (
            "the /learn proof block must use `fail` (hard exit 1) on a bad status / "
            "wrong redirect target — a warn/SKIP would let a broken coach revision "
            "pass Q5 (FR-11)."
        )
