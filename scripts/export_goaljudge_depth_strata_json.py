#!/usr/bin/env python
"""Export the planning-depth strata to a Playwright batch fixture.

These are NOT GoalJudge outcome cases — they exist to stress the D1
planning-depth dimension (L0/L1/L2 + adversarial bare-complex), which the
LIVE_CASES registry does not cover (a week of prod traces was ~all L0, zero L2).
Kept in a SEPARATE fixture so the production registry / gold set stays untouched.

Each case's intended depth + trigger family is carried in `stratum` as
`depth:{L0|L1|L2}:{family}` so open-coding can slice on it. The fired depth is
read back from the trace after the run (Langfuse eval.goal_judge input).

    python scripts/export_goaljudge_depth_strata_json.py
    -> frontend/e2e/fixtures/goaljudge_depth_strata.json
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
AGENT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(AGENT_ROOT))

# Reuse the exact authored set scored in diagnose_planning_strata.py.
from scripts.diagnose_planning_strata import CASES  # (intended, family, prompt)

OUT_PATH = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "goaljudge_depth_strata.json"


def main() -> None:
    rows = []
    for i, (intended, family, prompt) in enumerate(CASES, start=1):
        case_id = f"GJ-DEPTH-{i:03d}"
        rows.append(
            {
                "id": case_id,
                "prompt": prompt,  # already /workspace-relative or path-free
                "target_code": "planning-depth-probe",
                # Outcome axes unknown by design — this set probes depth, not goal_met.
                "target_axes": {},
                "stratum": f"depth:{intended}:{family}",
                "domain": "planning",
                "expected_feasibility": "achievable",
                "provenance": "synthetic",
                "trace_id": uuid.uuid5(uuid.NAMESPACE_DNS, case_id).hex,
                "session_id": f"session-{case_id.lower()}",
            }
        )
    OUT_PATH.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {len(rows)} depth-strata cases -> {OUT_PATH.relative_to(AGENT_ROOT)}")


if __name__ == "__main__":
    main()
