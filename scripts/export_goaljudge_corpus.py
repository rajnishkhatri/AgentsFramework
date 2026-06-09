"""Export GoalJudge runs from Langfuse → JSONL corpus for open coding (Phase 1).

Joins two surfaces (see the field-location map in the walkthrough):
  * Langfuse trace + observations (trajectory, goal_met, outcome, downgrade_reason)
  * goal_judge eval_capture records (full verdict: per_criterion, rationale,
    graceful_failure, partial_fraction, would_downgrade)

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST.
SDK: langfuse>=4 — verified API surface: api.trace.list / api.trace.get /
     api.observations.get_many (mirrors tests/synthetic/blackbox/langfuse_assertions.py).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langfuse import Langfuse

from components.schemas import GOAL_FAILURE_MODES

# Reuse the repo's tested fetch helpers rather than hand-rolling.
from tests.synthetic.blackbox.langfuse_assertions import (
    fetch_trace_details,
    fetch_trace_observations,
)


def _resolve_failure_mode(
    verdict: dict[str, Any],
    target_code: str,
) -> str | None:
    """Surface ``failure_mode`` for corpus export (Stage 5 harvest path).

    Prefer the eval_capture / Langfuse verdict axis when present; fall back to
    the registry ``target_code`` when it is an active Axis-A member code.
    """
    raw = verdict.get("failure_mode")
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped and stripped.lower() not in {"none", "null"}:
            if stripped in GOAL_FAILURE_MODES:
                return stripped
    if target_code in GOAL_FAILURE_MODES:
        return target_code
    return None


def _client() -> Langfuse:
    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )


def list_recent_trace_ids(hours: int = 2, user_id: str | None = None) -> list[str]:
    """List trace ids in a time window (v4: api.trace.list, cursor pagination)."""
    client = _client()
    now = datetime.now(timezone.utc)
    ids: list[str] = []
    page = 1
    while True:
        resp = client.api.trace.list(
            from_timestamp=now - timedelta(hours=hours),
            to_timestamp=now,
            user_id=user_id,  # omit/None to fetch all
            page=page,
            limit=100,
        )
        batch = resp.data or []
        ids.extend(t.id for t in batch)
        if len(batch) < 100:
            break
        page += 1
    return ids


def _task_completed_details(trace_id: str) -> dict:
    """Pull the task.completed observation's `details` (goal_met/outcome/...)."""
    for obs in fetch_trace_observations(trace_id):
        name = obs.get("name") if isinstance(obs, dict) else getattr(obs, "name", "")
        if name in ("task.completed", "task_completed"):
            body = obs.get("output") or obs.get("metadata") or obs.get("input") or {}
            if isinstance(body, dict):
                return body.get("details", body)
    return {}


def _eval_goal_judge_from_langfuse(trace_id: str) -> dict[str, Any]:
    """Load full GoalJudge verdict from E1 ``eval.goal_judge`` observation."""
    for obs in fetch_trace_observations(trace_id):
        name = obs.get("name") if isinstance(obs, dict) else getattr(obs, "name", "")
        if name not in ("eval.goal_judge", "eval_capture.goal_judge"):
            continue
        output = obs.get("output") if isinstance(obs, dict) else getattr(obs, "output", None)
        if isinstance(output, dict):
            return output
        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return {}


def load_eval_capture_verdicts(path: str = "logs/evals.log") -> dict[str, dict]:
    """Index goal_judge eval_capture records by task_id (== workflow_id/trace_id).

    The reliable source for the full verdict axes TODAY is a LOCAL run's
    logs/evals.log (a JSON FileHandler — same record schema as production,
    line-delimited JSON).

    On GCP this path is currently BROKEN (plan findings G3/T3/T4): the
    console/evals formatter is printf, not JSON (logging.json:4-8), and
    eval_capture emits logger.info("AI Response", extra=eval_record), so the
    extra= fields are dropped. The Cloud Run line is an unstructured
    textPayload of literally "AI Response", which means
        gcloud logging read 'jsonPayload.target="goal_judge"'
    matches NOTHING. The only Cloud Logging fallback is a brittle, NON-field-
    structured text grep that returns no parsed axes:
        gcloud logging read 'textPayload:"AI Response"' --format=json --freshness=2h
    Until the JSON-structured-logging follow-on lands
    (docs/plans/goaljudge_gcp_compatibility.plan.md, findings G3/T3/T4),
    capture the eval_capture half from a LOCAL run's logs/evals.log instead.
    """
    verdicts: dict[str, dict] = {}
    p = Path(path)
    if not p.exists():
        return verdicts
    for line in p.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("target") != "goal_judge":
            continue
        task_id = rec.get("task_id") or ""
        if task_id:
            verdicts[task_id] = rec.get("ai_response", {})
    return verdicts


import uuid


def export(
    out_path: str = "cache/goaljudge_eval/run.jsonl",
    hours: int = 2,
    user_id: str | None = None,
    case_map: dict[str, Any] | None = None,
) -> int:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    verdicts = load_eval_capture_verdicts()

    # Build default case map if none supplied, linking trace_id to the case
    if case_map is None:
        try:
            from tests.fixtures.goaljudge.case_registry import LIVE_CASES
            case_map = {}
            for c in LIVE_CASES:
                tid = uuid.uuid5(uuid.NAMESPACE_DNS, c.id).hex
                case_map[tid] = c
        except Exception:
            case_map = {}

    # Use targeted trace IDs if case_map is available, to avoid fetching thousands of unrelated traces
    if case_map:
        target_ids = list(case_map.keys())
    else:
        target_ids = list_recent_trace_ids(hours=hours, user_id=user_id)

    n = 0
    with open(out_path, "w") as fh:
        for trace_id in target_ids:
            trace = fetch_trace_details(trace_id)
            if not trace:
                continue
            details = _task_completed_details(trace_id)
            verdict = verdicts.get(trace_id) or _eval_goal_judge_from_langfuse(trace_id)
            
            case_info = case_map.get(trace_id) if case_map else None
            provenance = getattr(case_info, "provenance", "live") if case_info else "live"
            stratum = getattr(case_info, "stratum", "unknown") if case_info else "unknown"
            target_code = getattr(case_info, "target_code", "unknown") if case_info else "unknown"

            row = {
                "trace_id": trace_id,            # == workflow_id == task_id
                "task_input": trace.get("input"),
                "final_answer": trace.get("output"),
                "trajectory": fetch_trace_observations(trace_id),
                # Langfuse half:
                "outcome": details.get("outcome"),
                "goal_met": details.get("goal_met"),
                "criteria_met": details.get("criteria_met"),
                "unmet_conditions": details.get("unmet_conditions"),
                "downgrade_reason": details.get("downgrade_reason"),
                "termination_reason": details.get("termination_reason"),
                # eval_capture half (axes absent from Langfuse):
                "per_criterion": verdict.get("per_criterion"),
                "rationale": verdict.get("rationale"),
                "graceful_failure": verdict.get("graceful_failure"),
                "partial_fraction": verdict.get("partial_fraction"),
                "failure_mode": _resolve_failure_mode(verdict, target_code),
                "would_downgrade": verdict.get("would_downgrade"),
                "downgrade_applied": verdict.get("downgrade_applied"),
                # runtime config provenance (Recipe 15):
                "config_source": verdict.get("config_source"),
                "config_updated_at": verdict.get("config_updated_at"),
                "config_schema_version": verdict.get("config_schema_version"),
                # open-coding scaffolding (filled downstream):
                "open_codes": [],
                # synthetic saturation corpus tags:
                "provenance": provenance,
                "stratum": stratum,
                "target_code": target_code,
            }
            fh.write(json.dumps(row, default=str) + "\n")
            n += 1
    return n


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export GoalJudge runs")
    parser.add_argument("--user-id", help="Filter by user_id")
    parser.add_argument("--hours", type=int, default=2, help="Hours back to fetch")
    parser.add_argument("--out", default="cache/goaljudge_eval/run.jsonl", help="Output path")
    args = parser.parse_args()

    count = export(out_path=args.out, hours=args.hours, user_id=args.user_id)
    print(f"wrote {count} rows to {args.out}")
