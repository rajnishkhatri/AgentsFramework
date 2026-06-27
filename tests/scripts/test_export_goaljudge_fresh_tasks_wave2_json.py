"""L1 unit test for the wave-2 fresh-task JSON exporter (no live LLM, no I/O).

Pins the contract the Playwright `wave2` batch mode depends on: every wave-2
FreshTask projects to one row with the registry-case shape, a deterministic
``trace_id = uuid5(dns, id)`` (FE-AP-7: the join key is derived, never client-sent),
and a ``target_axes.goal_met`` that agrees with whether a failure mode was declared.
"""

from __future__ import annotations

import uuid

from scripts.export_goaljudge_fresh_tasks_wave2_json import build_rows
from tests.fixtures.goaljudge.fresh_test_tasks_wave2 import FRESH_TEST_TASKS_WAVE2


def test_exports_one_row_per_task_with_required_keys() -> None:
    rows = build_rows()
    assert len(rows) == len(FRESH_TEST_TASKS_WAVE2)
    required = {
        "id", "prompt", "target_code", "target_axes", "stratum", "domain",
        "expected_feasibility", "provenance", "trace_id", "session_id",
    }
    for row in rows:
        assert required <= row.keys()
        assert row["provenance"] == "fresh-authored"


def test_trace_id_is_derived_not_arbitrary() -> None:
    for row in build_rows():
        assert row["trace_id"] == uuid.uuid5(uuid.NAMESPACE_DNS, row["id"]).hex


def test_goal_met_axis_tracks_declared_failure_mode() -> None:
    by_id = {t.id: t for t in FRESH_TEST_TASKS_WAVE2}
    for row in build_rows():
        task = by_id[row["id"]]
        expect_success = task.expected_failure_mode is None
        assert row["target_axes"]["goal_met"] is expect_success
        assert row["target_code"] == (task.expected_failure_mode or "")
