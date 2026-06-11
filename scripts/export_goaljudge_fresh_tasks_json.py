#!/usr/bin/env python3
"""Export FRESH_TEST_TASKS to JSON for Playwright GCP batch injection.

Output: frontend/e2e/fixtures/goaljudge_fresh_tasks.json

Regenerate after fresh_test_tasks.py edits:
    python scripts/export_goaljudge_fresh_tasks_json.py
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(AGENT_ROOT))

from tests.fixtures.goaljudge.fresh_test_tasks import FRESH_TEST_TASKS

OUT_PATH = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "goaljudge_fresh_tasks.json"


def main() -> None:
    rows = []
    for task in FRESH_TEST_TASKS:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, task.id).hex
        target_code = task.expected_failure_mode or ""
        rows.append(
            {
                "id": task.id,
                "prompt": task.prompt,
                "target_code": target_code,
                "target_axes": {
                    "goal_met": target_code == "",
                    "graceful_failure": target_code
                    in {"impossible-task-reported", "graceful-failure-honest"},
                    "partial_fraction": 0.0 if target_code else 1.0,
                },
                "stratum": task.stratum,
                "domain": task.domain,
                "expected_feasibility": "feasible",
                "provenance": "fresh-authored",
                "trace_id": trace_id,
                "session_id": f"session-{task.id.lower()}",
            }
        )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} fresh tasks to {OUT_PATH}")


if __name__ == "__main__":
    main()
