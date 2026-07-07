"""G8 tombstone — the hint seed-parity suite was retired by ADR-0021.

This module deliberately contains NO tests. Its two parity tests pinned the
frontend ``DEV_HINTS`` copy against ``components/subject_coach_hints.py``'s
``AUTHORED_RUNGS`` (the ADR-0014 two-plane drift risk). ADR-0021 removed the
frontend hint plane entirely (``DEV_HINTS`` deleted with the dev questions),
so there is no second plane left to keep in parity: the backend asset is the
sole source, shape-covered by ``tests/components/test_subject_coach_hints.py``.

The waiver comments below are the mechanical G8 record the
``test_no_test_weakening`` ratchet requires for a removed ``def test_*`` —
an in-file ``# G8-OK: <test name>`` naming each retired test (a commit-message
token is NOT read by the gate). Delete this file only when the merge base no
longer contains the original module.
"""

# G8-OK: test_every_authored_rung_body_is_in_the_dev_seed — retired with the
# frontend DEV_HINTS plane (ADR-0021); no second hint plane exists to compare.
# G8-OK: test_ladder_shape_matches — retired for the same reason; ladder shape
# is covered at the sole source by tests/components/test_subject_coach_hints.py.
