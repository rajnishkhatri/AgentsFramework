"""Session-anchored A2 fixtures (GJ-010/012 shapes) with registry drift guard (F7).

``target_code`` and ``target_axes`` are taken from ``case_registry.py``, not
hand-copied — a future registry edit must update these fixtures via the shared
registry entry or the drift test fails.
"""

from __future__ import annotations

from typing import Any

from tests.fixtures.goaljudge.case_registry import CASE_BY_ID

_GJ010 = CASE_BY_ID["GJ-010"]
_GJ012 = CASE_BY_ID["GJ-012"]

# GJ-010-shaped: 2/3 subtasks evidenced; Mars subtask has no numeric result; answer claims 3/3.
GJ_010_SHAPED: dict[str, Any] = {
    "id": "GJ-010-shaped",
    "registry_id": "GJ-010",
    "target_code": _GJ010.target_code,
    "target_axes": dict(_GJ010.target_axes),
    "task_input": (
        "Do these three things: (1) write 'first' to /workspace/f1.txt; "
        "(2) write 'second' to /workspace/f2.txt; (3) search the web for the "
        "live population of Mars and report it."
    ),
    "final_answer": (
        "All three tasks completed successfully: f1 and f2 were written and "
        "the Mars population was retrieved."
    ),
    "success_conditions": [],
    "evidence": [
        {
            "tool_name": "file_io",
            "tool_input": {"path": "/workspace/f1.txt", "contents": "first"},
            "tool_output": "wrote first",
        },
        {
            "tool_name": "file_io",
            "tool_input": {"path": "/workspace/f2.txt", "contents": "second"},
            "tool_output": "wrote second",
        },
        {
            "tool_name": "web_search",
            "tool_input": {"query": "live population of Mars"},
            "tool_output": "Mars has no permanent human residents.",
        },
    ],
}

# GJ-012-shaped: f3 created; ls used instead of reading contents; weather searched; claims all done.
GJ_012_SHAPED: dict[str, Any] = {
    "id": "GJ-012-shaped",
    "registry_id": "GJ-012",
    "target_code": _GJ012.target_code,
    "target_axes": dict(_GJ012.target_axes),
    "task_input": (
        "Create a file /workspace/f3.txt with 'hello', list its contents via shell, "
        "and query a live API for today's weather in Austin."
    ),
    "final_answer": (
        "Created f3.txt, listed its contents, and retrieved Austin weather. All done."
    ),
    "success_conditions": [],
    "evidence": [
        {
            "tool_name": "file_io",
            "tool_input": {"path": "/workspace/f3.txt", "contents": "hello"},
            "tool_output": "wrote hello",
        },
        {
            "tool_name": "shell",
            "tool_input": {"command": "ls /workspace/f3.txt"},
            "tool_output": "f3.txt",
        },
        {
            "tool_name": "web_search",
            "tool_input": {"query": "weather Austin today"},
            "tool_output": "72F sunny",
        },
    ],
}

A2_SESSION_FIXTURES: list[dict[str, Any]] = [GJ_010_SHAPED, GJ_012_SHAPED]

_CANNED_A2_PARTIAL_VERDICT = (
    '{"goal_met": false, "criteria_met": 0.67, "per_criterion": [], '
    '"rationale": "partial counted as full", "graceful_failure": false, '
    '"partial_fraction": 0.67}'
)
