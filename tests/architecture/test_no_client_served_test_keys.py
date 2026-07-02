"""Architecture gate: the ADR-0013 Option-A → Option-B tripwire must stay mechanically
observable, not prose-only.

ADR-0013 (Subject-Coach Test Mode) accepts bundle-readable answer keys for the
unproctored, zero-stakes MVP (Option A) and names Option B (server-side delivery as a
third ADR-0012 context-contract mode) as the committed evolution behind **three
independent, any-one-sufficient decision triggers**: delivery (DB/sync-served rows),
stake (placement / mastery-FSRS feedback / reporting), and proctoring. The ADR's own
rationale (mirroring the ADR-0011/0012 lesson) is that a prose assertion rots; a
mechanical check or a named seam does not. This module is that mechanical check.

Two assertions, both green under Option A today:

  1. **Tripwire docs-integrity** — the ADR-0013 file still names the three triggers, the
     `COACH_TEST_KEYS_CLIENT_SERVED` posture flag, this detector test, and the "third
     mode of ADR-0012" evolution landing spot. Fails if the tripwire section is silently
     weakened/stripped (the "tripwire-on-the-tripwire": the deferral is only safe while
     the tripwire text is load-bearing and present).

  2. **Option-A posture live** — the four answer-bearing `Question` fields
     (`answer_letter`, `per_choice_rationale`, `why_correct_md`, `why_tempted_md`) ARE
     present in the Test-01 corpus fixture today, proving keys are client-served = Option
     A in effect. When Option B lands (keys removed from the bundle / fixture retired in
     favor of a DB/sync-served bank), this assertion's premise breaks — the test forces a
     conscious update paired with a `COACH_TEST_KEYS_CLIENT_SERVED=false` flip and a new
     gate row asserting keys are NOT shipped client-side. That conscious failure is the
     designed tripwire signal: the migration cannot start silently.

Since the ADR-0013 acceptance condition landed, the gate keys off the **actual flag
state** (`services.governance.coach_test_mode_posture.COACH_TEST_KEYS_CLIENT_SERVED`, a
literal code constant — deliberately not env-overridable, so flipping it is a reviewed
code diff, never a deploy-time toggle): flag `True` ⇒ the Option-A posture assertions
run (keys ARE client-served); flag `False` ⇒ the gate inverts and asserts keys are NOT
shipped client-side. The docs-integrity assertion runs under both postures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.governance.coach_test_mode_posture import (
    COACH_TEST_KEYS_CLIENT_SERVED,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ADR = (
    _REPO_ROOT
    / "docs/adr/0013-subject-coach-test-mode-blueprint-generation-integrity.md"
)
_CORPUS_FIXTURE = _REPO_ROOT / "frontend/lib/adapters/engine/_test01_english_corpus.ts"

# The four answer-bearing Question fields ADR-0012 excludes server-side for the coach
# pre-submit and ADR-0013 acknowledges are client-shipped today under Option A.
_ANSWER_BEARING_FIELDS = (
    "answer_letter",
    "per_choice_rationale",
    "why_correct_md",
    "why_tempted_md",
)

# The tripwire vocabulary that must remain present in the ADR (any silent removal is the
# weakening this gate exists to catch).
_REQUIRED_TRIPWIRE_MARKERS = (
    "Decision triggers — migration to Option B",
    "Delivery trigger",
    "Stake trigger",
    "Proctoring trigger",
    "COACH_TEST_KEYS_CLIENT_SERVED",
    "test_no_client_served_test_keys.py",
    "third `mode` of the ADR-0012 context contract",
)


class TestNoClientServedTestKeys:
    def test_adr_0013_tripwire_section_is_present_and_complete(self) -> None:
        """The three named triggers, the posture flag, this detector, and the Option-B
        evolution landing spot must all remain in ADR-0013. A silent strip of any marker
        weakens the tripwire and fails this gate (G8-OK / ADR-0013 scope)."""
        if not _ADR.exists():
            pytest.fail(
                "ADR-0013 file is missing — the Test Mode integrity stance has no "
                "record; restore docs/adr/0013-subject-coach-test-mode-blueprint-"
                "generation-integrity.md (ADR-0013 scope)."
            )
        text = _ADR.read_text()
        missing = [m for m in _REQUIRED_TRIPWIRE_MARKERS if m not in text]
        assert missing == [], (
            "ADR-0013 tripwire section has been weakened — these required markers are "
            "gone, and the Option-A deferral is no longer mechanically tripwired "
            "(restore them or re-open the ADR per its own trigger section):\n  "
            + "\n  ".join(missing)
        )

    def test_posture_flag_is_a_real_code_switch(self) -> None:
        """The ADR-0013 acceptance condition: `COACH_TEST_KEYS_CLIENT_SERVED` exists as
        a real, typed code constant (agent spec FR-28) — not env-derived, not inferred
        from docs. This import-level assertion IS the condition's mechanical proof."""
        assert isinstance(COACH_TEST_KEYS_CLIENT_SERVED, bool), (
            "COACH_TEST_KEYS_CLIENT_SERVED must be a literal bool constant (FR-28); "
            f"got {type(COACH_TEST_KEYS_CLIENT_SERVED).__name__}."
        )

    def test_posture_matches_flag_state(self) -> None:
        """The gate keys off the actual flag state (the ADR-0013 acceptance condition).

        Flag `True` (Option A): the four answer-bearing fields ARE shipped in the client
        bundle — the accepted-risk posture, not a violation. The assertion fails the
        moment the fields disappear from the fixture, the designed tripwire signal that
        the **delivery** trigger fired; the fix is a paired code change flipping
        `COACH_TEST_KEYS_CLIENT_SERVED = False` (which mechanically inverts this gate),
        never a silent fixture edit.

        Flag `False` (Option B): the gate inverts — no client-served corpus may carry
        the answer-bearing fields; test delivery must be server-mediated (the third
        ADR-0012 context-contract mode)."""
        if COACH_TEST_KEYS_CLIENT_SERVED:
            if not _CORPUS_FIXTURE.exists():
                pytest.fail(
                    "COACH_TEST_KEYS_CLIENT_SERVED is True (Option A) but the Test-01 "
                    "corpus fixture is gone (_test01_english_corpus.ts). If delivery "
                    "moved to a DB/sync-served bank, the delivery trigger has fired: "
                    "re-open ADR-0013 and flip COACH_TEST_KEYS_CLIENT_SERVED = False "
                    "in services/governance/coach_test_mode_posture.py (ADR-0013)."
                )
            text = _CORPUS_FIXTURE.read_text()
            missing = [f for f in _ANSWER_BEARING_FIELDS if f not in text]
            assert missing == [], (
                "COACH_TEST_KEYS_CLIENT_SERVED is True (Option A) but these "
                "answer-bearing fields are absent from the Test-01 corpus fixture — the "
                "posture no longer matches the flag. If the delivery trigger fired, "
                "re-open ADR-0013 and flip the flag; do not leave the posture "
                "half-changed:\n  " + "\n  ".join(missing)
            )
        else:
            if _CORPUS_FIXTURE.exists():
                text = _CORPUS_FIXTURE.read_text()
                present = [f for f in _ANSWER_BEARING_FIELDS if f in text]
                assert present == [], (
                    "COACH_TEST_KEYS_CLIENT_SERVED is False (Option B) but the client "
                    "corpus fixture still ships answer-bearing fields — keys must NOT "
                    "be client-served under Option B (ADR-0013; delivery = the third "
                    "ADR-0012 context-contract mode):\n  " + "\n  ".join(present)
                )
