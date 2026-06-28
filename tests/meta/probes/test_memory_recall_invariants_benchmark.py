"""Phase 6 (replace-mem0-pgvector) — offline CI regression replay for the
Tier-A recall invariant validator.

Per the agentsframework-eval-probe skill's Phase 4 Done-when:
  - A frozen <seam>_benchmark_v1.json (must-accept / must-reject) holds the
    failure modes the seam MUST always catch
  - A pytest replay runs the pure L1 check over the fixture and asserts every
    row lands on the right side — this IS the merge gate

The fixture is `meta/probes/memory_recall_invariants_benchmark_v1.json`. A v2
file supersedes; v1 is never mutated. The acceptance/rejection convention:

  - `must_pass_all: true`  → every invariant in the result must `.passed`
  - `must_fail: [<name>, …]` → exactly those invariants must `.passed == False`,
                                all others must pass

Skill TAP-1 / TAP-2 / TAP-4 disciplines:
  - Don't re-implement the validator in the test (would be tautological).
  - Don't mock anything — the validator is a pure function over a Pydantic type.
  - The fixture has >= as many rejection rows as acceptance rows (5 vs 4).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.governance.memory_recall_validator import validate_recall
from services.long_term_memory import MemoryRecord

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "meta"
    / "probes"
    / "memory_recall_invariants_benchmark_v1.json"
)


def _load_rows() -> list[dict]:
    with FIXTURE.open() as f:
        data = json.load(f)
    assert data["schema_version"] == 1
    assert data["seam"] == "memory_recall"
    return data["rows"]


def _to_records(rows: list[dict]) -> list[MemoryRecord]:
    return [MemoryRecord(**r) for r in rows]


@pytest.mark.parametrize("row", _load_rows(), ids=lambda r: r["id"])
def test_benchmark_row_lands_on_expected_side(row: dict) -> None:
    """Replay one fixture row through the validator and assert the outcome
    matches the row's expectation. Fixture-driven: every must_fail / must_pass
    row is the merge-blocking gate."""
    results = validate_recall(
        user_id=row["user_id"],
        requested_limit=row["requested_limit"],
        kept=_to_records(row["kept"]),
    )
    by_name = {r.name: r for r in results}

    if row.get("must_pass_all"):
        failed = [r.name for r in results if not r.passed]
        assert not failed, (
            f"acceptance row {row['id']!r} expected all invariants to pass; "
            f"failed: {failed}"
        )
        return

    expected_failures: list[str] = row.get("must_fail", [])
    assert expected_failures, (
        f"row {row['id']!r} has neither must_pass_all nor must_fail — "
        "every fixture row needs a verdict"
    )
    for name in expected_failures:
        assert name in by_name, (
            f"row {row['id']!r} expects {name!r} to fail but the validator "
            f"emitted no result for that invariant"
        )
        assert by_name[name].passed is False, (
            f"row {row['id']!r}: expected {name!r} to FAIL but it passed"
        )
    # Every invariant NOT in must_fail must pass — a rejection row pins ONLY
    # the named failure modes; nothing else is allowed to regress.
    for name, r in by_name.items():
        if name in expected_failures:
            continue
        assert r.passed is True, (
            f"row {row['id']!r}: invariant {name!r} regressed (passed: False) "
            f"but is not in must_fail; details: {r.details!r}"
        )


def test_fixture_has_rejection_majority() -> None:
    """TAP-4 / AGENTS.md §Testing Rules: rejection rows >= acceptance rows."""
    rows = _load_rows()
    acceptance = [r for r in rows if r.get("must_pass_all")]
    rejection = [r for r in rows if r.get("must_fail")]
    assert rejection, "benchmark must include rejection rows"
    assert len(rejection) >= len(acceptance), (
        f"failure-paths-first: have {len(rejection)} rejection vs "
        f"{len(acceptance)} acceptance rows"
    )


def test_fixture_covers_every_invariant_at_least_once() -> None:
    """Coverage gate: each invariant the validator emits must appear in at
    least one must_fail row. If we add a new invariant to the validator and
    forget to extend the benchmark, this test goes red."""
    rows = _load_rows()
    seen: set[str] = set()
    for r in rows:
        for name in r.get("must_fail", []):
            seen.add(name)

    # Run the validator on a synthetic clean recall to enumerate the
    # invariants it actually emits — the benchmark must cover every one.
    clean = validate_recall(
        user_id="probe",
        requested_limit=1,
        kept=[
            MemoryRecord(user_id="probe", key="k", payload={"text": "x"}, metadata={})
        ],
    )
    invariant_names = {r.name for r in clean}
    missing = invariant_names - seen
    assert not missing, (
        f"benchmark missing rejection coverage for invariants: {missing}. "
        "Add a must_fail row for each in memory_recall_invariants_benchmark_v1.json."
    )
