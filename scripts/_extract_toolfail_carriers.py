"""Extract tool-layer carriers per trace for the tool-failure report.

Walks a model_ab_eval candidate arm's BlackBox recordings and, per trace,
counts tool_called / error carriers and classifies the failure family the
same way the glm-5.2 report did. Read-only; prints a per-trace summary.

Usage: .venv/bin/python scripts/_extract_toolfail_carriers.py <candidate_dir>
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def classify(tool: str, error_text: str) -> str:
    t = error_text.lower()
    if "timed out" in t or "timeout" in t:
        return "timeout"
    if (
        "validation" in t
        or "illegal" in t
        or "blocked" in t
        or "not allowed" in t
        or "disallowed" in t
    ):
        return f"masked-validation({tool})"
    if "exit code" in t or "non-zero" in t or "nonzero" in t:
        return "nonzero-exit"
    return "other"


def messages_illegal(error_text: str) -> bool:
    t = error_text.lower()
    return "messages parameter is illegal" in t or "zaiexception" in t


def summarize(trace: Path) -> dict:
    tools: Counter[str] = Counter()
    errs: list[tuple[str, str]] = []
    outcome = goal_met = None
    illegal = 0
    for line in trace.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = e.get("event_type")
        d = e.get("details", {}) or {}
        if et == "tool_called":
            tools[d.get("tool", "?")] += 1
        elif et == "task_completed":
            outcome = d.get("outcome")
            goal_met = d.get("goal_met")
        # errors can live on step_executed/tool_called as an error/result string
        blob = json.dumps(e)
        if '"error"' in blob or "Error:" in blob or "error_class" in blob:
            tool = d.get("tool", "shell")
            text = ""
            for k in ("error", "result", "message", "stderr", "error_class"):
                v = d.get(k)
                if isinstance(v, str) and (
                    "error" in v.lower()
                    or "fail" in v.lower()
                    or "illegal" in v.lower()
                    or "timed out" in v.lower()
                    or "exit code" in v.lower()
                    or "validation" in v.lower()
                ):
                    text = v
                    break
            if text:
                if messages_illegal(text):
                    illegal += 1
                errs.append((tool, classify(tool, text)))
    return {
        "trace": trace.parent.name,
        "tools": dict(tools),
        "total_tools": sum(tools.values()),
        "errors": Counter(f"{t}:{fam}" for t, fam in errs),
        "total_errors": len(errs),
        "messages_illegal": illegal,
        "outcome": outcome,
        "goal_met": goal_met,
    }


def main() -> None:
    root = Path(sys.argv[1])
    traces = sorted(root.rglob("trace.jsonl"))
    print(f"# {len(traces)} traces under {root}\n")
    agg_err: Counter[str] = Counter()
    illegal_total = clean = 0
    for tr in traces:
        s = summarize(tr)
        agg_err.update(s["errors"])
        illegal_total += s["messages_illegal"]
        if s["total_errors"] == 0:
            clean += 1
        print(json.dumps(s))
    print("\n# ROLLUP")
    print(
        json.dumps(
            {
                "traces": len(traces),
                "clean_runs": clean,
                "error_families": dict(agg_err),
                "messages_illegal_total": illegal_total,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
