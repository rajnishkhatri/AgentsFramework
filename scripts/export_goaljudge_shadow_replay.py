#!/usr/bin/env python3
"""Export §8.3 shadow-replay JSON from eval_capture (logs/evals.log or Langfuse).

Produces the array shape consumed by
``tests/fixtures/goaljudge/langfuse_replay.py`` — Form B EvalRecord rows keyed
by ``trace_id``. Filter to §10.2 anchor trace IDs only so the export is safe to
point at ``GOALJUDGE_LANGFUSE_EXPORT`` for the behavioral shadow gate.

Usage (after local batch)::

    python scripts/run_goaljudge_synthetic_batch.py --anchors --yes
    python scripts/export_goaljudge_shadow_replay.py \\
        -o cache/goaljudge_eval/shadow_replay.json

Then::

    GOALJUDGE_LANGFUSE_EXPORT=$PWD/cache/goaljudge_eval/shadow_replay.json \\
      pytest tests/components/test_goal_judge_shadow_offline.py -q
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from scripts.export_goaljudge_corpus import (
    _eval_goal_judge_from_langfuse,
    load_eval_capture_verdicts,
)
from tests.fixtures.goaljudge.langfuse_replay import TRACE_ID_TO_REGISTRY_ID


def _anchor_trace_ids() -> frozenset[str]:
    return frozenset(TRACE_ID_TO_REGISTRY_ID.keys())


def _registry_trace_id(case_id: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, case_id).hex


def export_shadow_replay(
    *,
    evals_path: str = "logs/evals.log",
    out_path: str = "cache/goaljudge_eval/shadow_replay.json",
    use_langfuse_fallback: bool = True,
) -> tuple[int, list[str]]:
    """Write anchor-only replay rows. Returns (count, missing_registry_ids)."""
    anchors = _anchor_trace_ids()
    verdicts = load_eval_capture_verdicts(evals_path)

    rows: list[dict[str, Any]] = []
    missing: list[str] = []

    for trace_id, registry_id in TRACE_ID_TO_REGISTRY_ID.items():
        verdict = verdicts.get(trace_id)
        if not verdict and use_langfuse_fallback:
            verdict = _eval_goal_judge_from_langfuse(trace_id)
        if not verdict:
            missing.append(registry_id)
            continue
        rows.append(
            {
                "trace_id": trace_id,
                "target": "goal_judge",
                "ai_response": verdict,
            }
        )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return len(rows), missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export §8.3 shadow-replay JSON for gate-eligible anchors"
    )
    parser.add_argument(
        "--evals",
        default="logs/evals.log",
        help="Path to eval_capture log (default: logs/evals.log)",
    )
    parser.add_argument(
        "-o",
        "--out",
        default="cache/goaljudge_eval/shadow_replay.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--no-langfuse",
        action="store_true",
        help="Do not fall back to Langfuse eval.goal_judge observations",
    )
    args = parser.parse_args()

    count, missing = export_shadow_replay(
        evals_path=args.evals,
        out_path=args.out,
        use_langfuse_fallback=not args.no_langfuse,
    )
    print(f"wrote {count} anchor rows to {args.out}")
    if missing:
        print(f"missing anchors ({len(missing)}): {', '.join(sorted(missing))}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
