#!/usr/bin/env python
"""Export LIVE_CASES from case_registry.py to JSON for Playwright batch injection.

Output: frontend/e2e/fixtures/goaljudge_registry.json

Regenerate after registry edits:
    python scripts/export_goaljudge_registry_json.py
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(AGENT_ROOT))

from tests.fixtures.goaljudge.case_registry import LIVE_CASES

OUT_PATH = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "goaljudge_registry.json"

# Registry prompts use the local file_io sandbox; Playwright GCP batch needs /workspace.
_LOCAL_WORKSPACE_PREFIX = (
    "/Users/rajnishkhatri/Documents/AgentsFramework/agent/workspace"
)


def prompt_for_gcp(prompt: str) -> str:
    """Map local workspace paths to the Cloud Run file_io sandbox."""
    return prompt.replace(_LOCAL_WORKSPACE_PREFIX, "/workspace")


def main() -> None:
    rows = []
    for case in LIVE_CASES:
        trace_id = uuid.uuid5(uuid.NAMESPACE_DNS, case.id).hex
        rows.append(
            {
                "id": case.id,
                "prompt": prompt_for_gcp(case.prompt),
                "target_code": case.target_code,
                "target_axes": case.target_axes,
                "stratum": case.stratum,
                "domain": case.domain,
                "expected_feasibility": case.expected_feasibility,
                "provenance": case.provenance,
                "trace_id": trace_id,
                "session_id": f"session-{case.id.lower()}",
            }
        )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} cases to {OUT_PATH}")


if __name__ == "__main__":
    main()
