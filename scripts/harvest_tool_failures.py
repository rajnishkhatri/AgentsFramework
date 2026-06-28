"""Harvest tool-failure cases from BlackBox recordings for open coding.

The Stage-4 open-coding sample was file_io-dominated. This script broadens the
DATA (not the codes) to cover ``shell`` and every other non-file_io tool by
walking the BlackBox ``trace.jsonl`` recordings already on disk, extracting the
``tool_called`` / ``error_occurred`` trajectory per workflow, and emitting one
open-coding case per (workflow, arm) in the cases.json schema.

KEY CONSTRAINT: almost all on-disk recordings predate the Stage-2 ``error_class``
instrument, so the failure category is recovered from the ``details.error``
STRING via :func:`classify_failure_mode`. Any real ``error_class`` on a
post-Stage-2 carrier is preserved alongside the derived ``failure_mode``.

The cardinal open-coding rule is honored: this emits DATA only (prompt,
trajectory, outcome). It assigns NO codes — the human coder does that.

Usage::

    .venv/bin/python scripts/harvest_tool_failures.py \
        --root cache --out cache/open_coding/tool-calling-failures/harvested_cases.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# The non-file_io tools whose failures we want to surface. file_io is excluded
# (it is already richly coded); the hallucinated names (python/read) are kept
# because an unknown-tool call IS a tool-calling failure.
_FILE_IO = "file_io"


# ── Failure-mode classifier (the unit under test) ────────────────────────────
#
# Ordered first-match: each entry is (compiled regex, mode, token-group-or-None).
# The token group, when present, captures the offending command / metacharacter
# so the worksheet can show "echo not in allowlist" vs "git not in allowlist"
# as distinct rows without re-parsing the error string downstream.
_RULES: list[tuple[re.Pattern[str], str, int | None]] = [
    (re.compile(r"Command '([^']+)' not in allowlist"), "command-not-in-allowlist", 1),
    (
        re.compile(r"metacharacter detected in token '([^']+)'"),
        "metacharacter-blocked",
        1,
    ),
    (re.compile(r"Blocked argument"), "blocked-arg", None),
    (re.compile(r"Blocked pattern"), "blocked-pattern", None),
    (re.compile(r"exit code \d+"), "shell-exit-nonzero", None),
    (re.compile(r"timed out|timeout", re.I), "shell-timeout", None),
    # web_search typed errors (order: empty before the generic validation match).
    (re.compile(r"empty_results"), "web-search-empty", None),
    (re.compile(r"provider_error"), "web-search-provider-error", None),
    (re.compile(r"validation_error"), "web-search-validation", None),
    # task-tool gating codes (e.g. DELEGATION_SUBAGENT_NOT_ALLOWED).
    (re.compile(r"_NOT_ALLOWED|RECONCILE_|DELEGATION_"), "task-gating-denied", None),
    (re.compile(r"Unknown tool '([^']+)'"), "unknown-tool", 1),
    # stateful-tool typed failures recovered from the message text.
    (re.compile(r"File '([^']+)' not found"), "state-file-not-found", 1),
    (re.compile(r"is required for \w+ operation"), "state-todo-missing-arg", None),
    (re.compile(r"validation error for ThinkToolInput"), "think-validation", None),
]


def classify_failure_mode(error: str) -> tuple[str, str | None]:
    """Map a ``details.error`` string to (failure_mode, captured_token).

    First-match over :data:`_RULES`; falls through to ``tool-reported-other``
    (carrying the raw error for manual review) when nothing matches. Pure
    function — no I/O, deterministic.
    """
    if not error:
        return "tool-reported-other", None
    for pattern, mode, group in _RULES:
        m = pattern.search(error)
        if m:
            token = m.group(group) if group is not None else None
            return mode, token
    return "tool-reported-other", None


# ── Per-workflow case builder (pure over an event list) ──────────────────────
def case_from_workflow(
    workflow_id: str,
    events: list[dict[str, Any]],
    *,
    model: str,
    source: str = "blackbox",
) -> dict[str, Any]:
    """Collapse one workflow's event list into a single cases.json object.

    Reads carriers as ground truth (the prompt from ``task_started``, the
    outcome from ``task_completed``, the trajectory from ``tool_called`` /
    ``error_occurred``). Assigns no codes.
    """
    prompt = ""
    outcome: str | None = None
    trajectory: list[dict[str, Any]] = []
    tools_touched: list[str] = []
    error_classes: list[str] = []
    failure_modes: list[str] = []

    for ev in events:
        et = ev.get("event_type")
        details = ev.get("details", {}) or {}
        if et == "task_started":
            prompt = details.get("task_input", "") or prompt
        elif et == "task_completed":
            outcome = details.get("outcome", outcome)
        elif et == "tool_called":
            tool = details.get("tool", "")
            if tool and tool not in tools_touched:
                tools_touched.append(tool)
            trajectory.append(
                {
                    "ev": "tool_called",
                    "tool": tool,
                    "cached": bool(details.get("cached", False)),
                }
            )
        elif et == "error_occurred":
            # Only TOOL-execution errors are tool-calling failures. An
            # ``llm_call`` error (rate-limit, provider 5xx, empty output) is an
            # infra/model failure, not a tool failure — skip it so it can't
            # inflate the carriers (the gpt-4o-mini quota runs would otherwise
            # show as a wall of bogus ``tool-reported-other`` events).
            if details.get("source") != "tool_execution":
                continue
            tool = details.get("tool", "")
            if tool and tool not in tools_touched:
                tools_touched.append(tool)
            error = details.get("error", "") or ""
            mode, token = classify_failure_mode(error)
            if mode not in failure_modes:
                failure_modes.append(mode)
            err_ev: dict[str, Any] = {
                "ev": "error.occurred",
                "tool": tool,
                "failure_mode": mode,
            }
            if token:
                err_ev["token"] = token
            # Preserve a real error_class (post-Stage-2 carriers) verbatim.
            ec = details.get("error_class")
            if ec:
                err_ev["error_class"] = ec
                if ec not in error_classes:
                    error_classes.append(ec)
            trajectory.append(err_ev)

    return {
        "trace_id": workflow_id,
        "prompt": prompt,
        "final_answer": "",
        "model": model,
        "goal_met": outcome == "success",
        "outcome": outcome,
        "source": source,
        "tools_touched": tools_touched,
        "error_classes": error_classes,
        "failure_modes": failure_modes,
        "trajectory": trajectory,
    }


# ── Disk walk ────────────────────────────────────────────────────────────────
def _load_trace(trace_file: Path) -> list[dict[str, Any]]:
    """Read a trace.jsonl as a list of event dicts (mirrors the reader pattern in
    scripts/analyze_planning_traces.py:_load_blackbox_events)."""
    events: list[dict[str, Any]] = []
    text = trace_file.read_text().strip()
    if not text:
        return events
    for line in text.split("\n"):
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _infer_model(trace_file: Path) -> str:
    """Best-effort model label from the run-dir path (e.g. .../<arm>/cache/...).

    The A/B harness writes each arm under a named dir (baseline/candidate or the
    run-id); we surface the nearest meaningful path segment so the coder can
    stratify by arm. Falls back to 'unknown'.
    """
    for part in trace_file.parts:
        low = part.lower()
        if any(
            k in low
            for k in (
                "gpt",
                "haiku",
                "deepseek",
                "glm",
                "opus",
                "sonnet",
                "candidate",
                "baseline",
            )
        ):
            return part
    return "unknown"


def harvest(root: Path) -> list[dict[str, Any]]:
    """Walk ``root`` for trace.jsonl files; emit a case for every workflow that
    touches a non-file_io tool. Idempotent over a fixed tree.

    The same ``workflow_id`` is replayed across many A/B run dirs (baseline +
    candidate × every run), so a given id can appear in dozens of trace files.
    We dedupe by ``workflow_id``, keeping the copy with the richest trajectory
    (most events) so one workflow contributes exactly one case.
    """
    best: dict[str, dict[str, Any]] = {}
    for trace_file in sorted(root.rglob("trace.jsonl")):
        events = _load_trace(trace_file)
        if not events:
            continue
        workflow_id = trace_file.parent.name
        model = _infer_model(trace_file)
        case = case_from_workflow(workflow_id, events, model=model)
        # Keep only workflows touching a tool other than file_io.
        if not any(t != _FILE_IO for t in case["tools_touched"]):
            continue
        prev = best.get(workflow_id)
        if prev is None or len(case["trajectory"]) > len(prev["trajectory"]):
            best[workflow_id] = case
    return list(best.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="cache", help="dir to walk for trace.jsonl")
    ap.add_argument(
        "--out",
        default="cache/open_coding/tool-calling-failures/harvested_cases.json",
        help="output cases.json path",
    )
    ap.add_argument(
        "--with-errors-only",
        action="store_true",
        help="keep only workflows that have at least one error.occurred carrier",
    )
    args = ap.parse_args()

    cases = harvest(Path(args.root))
    if args.with_errors_only:
        cases = [
            c
            for c in cases
            if any(e["ev"] == "error.occurred" for e in c["trajectory"])
        ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, indent=2))

    # A quick coverage summary to stderr-ish stdout (not part of the artifact).
    by_mode: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    for c in cases:
        for m in c["failure_modes"]:
            by_mode[m] = by_mode.get(m, 0) + 1
        for t in c["tools_touched"]:
            if t != _FILE_IO:
                by_tool[t] = by_tool.get(t, 0) + 1
    print(f"harvested {len(cases)} cases -> {out}")
    print("by non-file_io tool:", dict(sorted(by_tool.items(), key=lambda kv: -kv[1])))
    print("by failure_mode:", dict(sorted(by_mode.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
