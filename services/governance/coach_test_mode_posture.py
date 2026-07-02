"""ADR-0013 Test-Mode integrity posture — the Option-A / Option-B tripwire switch.

``COACH_TEST_KEYS_CLIENT_SERVED`` (agent spec FR-28) records the codebase's *posture* on
whether test answer keys ship in the client bundle:

- ``True``  — **Option A** (ADR-0013): keys are client-served. Accepted for the
  unproctored, zero-stakes MVP only; the four answer-bearing ``Question`` fields ride
  the checked-in Test-01 corpus fixture and grading is client-side.
- ``False`` — **Option B**: keys are withheld from the client; test delivery is
  server-mediated as a third mode of the ADR-0012 context contract.

Flip to ``False`` when **any** of ADR-0013's three named, any-one-sufficient decision
triggers fires: **delivery** (corpus moves to DB/sync-served rows), **stake** (placement,
mastery/FSRS feedback, or reporting attaches significance to the score), or
**proctoring** (the surface gains a proctoring signal). The flip re-opens ADR-0013 by
its own terms.

This is deliberately a **literal constant, not an env read**: the posture is a property
of the codebase, and changing it must be a reviewed code diff paired with the ADR
re-opening — an env override would let a deploy invert the tripwire silently, which is
exactly the failure mode the flag exists to prevent.
``tests/architecture/test_no_client_served_test_keys.py`` keys off this value and
mechanically inverts its gate when the flag flips.
"""

from __future__ import annotations

from typing import Final

COACH_TEST_KEYS_CLIENT_SERVED: Final[bool] = True
