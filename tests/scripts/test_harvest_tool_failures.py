"""L2 Reproducible: failure-mode classifier for the tool-failure harvester.

The harvester (scripts/harvest_tool_failures.py) walks BlackBox ``trace.jsonl``
recordings and turns each ``error_occurred`` carrier into an open-coding case.
Most on-disk recordings PREDATE the Stage-2 ``error_class`` instrument, so the
failure category has to be recovered from the ``details.error`` STRING.

This module tests that recovery — ``classify_failure_mode`` — failure-paths-first
(TAP Anti-Pattern 6): every rejection branch is pinned with a REAL error string
pulled off disk before the catch-all. No live LLM, no trace I/O — the classifier
is a pure string→label function (deterministic, CI-safe).
"""

from __future__ import annotations

import pytest

from scripts.harvest_tool_failures import (
    classify_failure_mode,
    case_from_workflow,
)


class TestClassifyFailureMode:
    """Ordered first-match string classifier. Fixtures are verbatim ``details.error``
    strings harvested from cache/**/trace.jsonl (so the test fails the day the
    error wording drifts away from what the classifier matches)."""

    # ── shell allowlist ──────────────────────────────────────────────────────
    def test_command_not_in_allowlist(self):
        err = (
            "Error: 1 validation error for ShellToolInput\ncommand\n  Value error, "
            "Command 'echo' not in allowlist: ['cat', 'find', 'grep', 'head', 'ls', "
            "'python', 'tail', 'wc'] [type=value_error, input_value='echo $((12!))']"
        )
        mode, token = classify_failure_mode(err)
        assert mode == "command-not-in-allowlist"
        assert token == "echo"  # the rejected command is captured

    def test_python3_not_python_is_allowlist_with_python3_token(self):
        err = (
            "Error: 1 validation error for ShellToolInput\ncommand\n  Value error, "
            "Command 'python3' not in allowlist: ['cat', 'find', 'grep'] [type=value_error]"
        )
        mode, token = classify_failure_mode(err)
        assert mode == "command-not-in-allowlist"
        assert token == "python3"

    # ── shell metacharacter ──────────────────────────────────────────────────
    def test_metacharacter_blocked(self):
        err = (
            "Error: 1 validation error for ShellToolInput\ncommand\n  Value error, "
            "Shell metacharacter detected in token '|' [type=value_error, input_value='ls | wc']"
        )
        mode, token = classify_failure_mode(err)
        assert mode == "metacharacter-blocked"
        assert token == "|"

    # ── shell blocked-arg / blocked-pattern (live-slice modes) ───────────────
    def test_blocked_argument(self):
        err = (
            "Error: 1 validation error for ShellToolInput\ncommand\n  Value error, "
            "Blocked argument '-exec' detected [type=value_error]"
        )
        mode, _ = classify_failure_mode(err)
        assert mode == "blocked-arg"

    def test_blocked_pattern(self):
        err = (
            "Error: 1 validation error for ShellToolInput\ncommand\n  Value error, "
            "Blocked pattern 'rm ' detected [type=value_error]"
        )
        mode, _ = classify_failure_mode(err)
        assert mode == "blocked-pattern"

    # ── shell runtime (non-validation) ───────────────────────────────────────
    def test_shell_exit_nonzero(self):
        mode, _ = classify_failure_mode("exit code 1")
        assert mode == "shell-exit-nonzero"

    def test_shell_timeout(self):
        mode, _ = classify_failure_mode("Command timed out")
        assert mode == "shell-timeout"

    # ── unknown / hallucinated tool ──────────────────────────────────────────
    def test_unknown_tool(self):
        mode, token = classify_failure_mode("Unknown tool 'python'")
        assert mode == "unknown-tool"
        assert token == "python"

    # ── web_search typed errors ──────────────────────────────────────────────
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Error: empty_results: no hits for query", "web-search-empty"),
            ("Error: provider_error: 503 from backend", "web-search-provider-error"),
            ("Error: Invalid input: validation_error: bad query", "web-search-validation"),
        ],
    )
    def test_web_search_typed(self, raw, expected):
        mode, _ = classify_failure_mode(raw)
        assert mode == expected

    # ── task gating ──────────────────────────────────────────────────────────
    def test_task_gating_denied(self):
        mode, _ = classify_failure_mode("DELEGATION_SUBAGENT_NOT_ALLOWED")
        assert mode == "task-gating-denied"

    # ── stateful-tool typed failures (recovered from the message) ────────────
    def test_state_file_not_found(self):
        mode, token = classify_failure_mode("File '/workspace/config.json' not found")
        assert mode == "state-file-not-found"
        assert token == "/workspace/config.json"

    def test_state_todo_missing_arg(self):
        mode, _ = classify_failure_mode("todo is required for append operation")
        assert mode == "state-todo-missing-arg"

    def test_think_validation(self):
        err = (
            "1 validation error for ThinkToolInput\nthought\n  String should have at "
            "most 500 characters [type=string_too_long]"
        )
        mode, _ = classify_failure_mode(err)
        assert mode == "think-validation"

    # ── catch-all ────────────────────────────────────────────────────────────
    def test_unmatched_falls_through_to_other(self):
        mode, _ = classify_failure_mode("some entirely novel backend hiccup xyzzy")
        assert mode == "tool-reported-other"

    def test_empty_string_is_other(self):
        mode, token = classify_failure_mode("")
        assert mode == "tool-reported-other"
        assert token is None


class TestCaseFromWorkflow:
    """The per-workflow case builder: events list → one cases.json object. Pure
    function over an event list (no disk), so it's deterministic and CI-safe."""

    def _events(self):
        return [
            {"event_type": "task_started", "details": {"task_input": "run echo"}},
            {
                "event_type": "tool_called",
                "details": {"tool": "shell", "args": {"command": "echo hi"}, "cached": False},
            },
            {
                "event_type": "error_occurred",
                "details": {
                    "source": "tool_execution",
                    "tool": "shell",
                    "error": "Error: Value error, Command 'echo' not in allowlist: [...]",
                },
            },
            {"event_type": "task_completed", "details": {"outcome": "failed"}},
        ]  # already carries source:tool_execution (matches real carriers)

    def test_builds_case_with_prompt_and_trajectory(self):
        case = case_from_workflow("wf-123", self._events(), model="gpt-4o-mini")
        assert case["trace_id"] == "wf-123"
        assert case["prompt"] == "run echo"
        assert case["model"] == "gpt-4o-mini"
        assert case["goal_met"] is False
        # trajectory carries the tool_called + error.occurred with a failure_mode
        evs = case["trajectory"]
        assert {"ev": "tool_called", "tool": "shell", "cached": False} in evs
        err_ev = next(e for e in evs if e["ev"] == "error.occurred")
        assert err_ev["tool"] == "shell"
        assert err_ev["failure_mode"] == "command-not-in-allowlist"

    def test_touches_non_file_io_tool(self):
        case = case_from_workflow("wf-123", self._events(), model="m")
        assert case["tools_touched"] == ["shell"]
        assert case["error_classes"] == []  # no error_class on this pre-Stage-2 carrier
        assert "command-not-in-allowlist" in case["failure_modes"]

    def test_keeps_real_error_class_when_present(self):
        events = [
            {"event_type": "task_started", "details": {"task_input": "p"}},
            {
                "event_type": "error_occurred",
                "details": {
                    "source": "tool_execution",
                    "tool": "python",
                    "error": "Unknown tool 'python'",
                    "error_class": "unknown_tool",
                },
            },
            {"event_type": "task_completed", "details": {"outcome": "failed"}},
        ]
        case = case_from_workflow("wf-x", events, model="m")
        assert case["error_classes"] == ["unknown_tool"]
        err_ev = next(e for e in case["trajectory"] if e["ev"] == "error.occurred")
        assert err_ev["error_class"] == "unknown_tool"
        assert err_ev["failure_mode"] == "unknown-tool"

    def test_ignores_non_tool_execution_errors(self):
        """A ``source:llm_call`` error (e.g. a RateLimitError) is NOT a tool
        failure and must not appear as an error.occurred in the trajectory — only
        ``source:tool_execution`` errors count. Regression: the gpt-4o-mini
        rate-limit runs would otherwise inflate the tool-failure carriers."""
        events = [
            {"event_type": "task_started", "details": {"task_input": "p"}},
            {
                "event_type": "error_occurred",
                "details": {
                    "source": "llm_call",
                    "model": "gpt-4o-mini",
                    "error": "litellm.RateLimitError: You exceeded your quota",
                },
            },
            {
                "event_type": "tool_called",
                "details": {"tool": "shell", "cached": False},
            },
            {
                "event_type": "error_occurred",
                "details": {
                    "source": "tool_execution",
                    "tool": "shell",
                    "error": "exit code 1",
                },
            },
            {"event_type": "task_completed", "details": {"outcome": "partial"}},
        ]
        case = case_from_workflow("wf-rl", events, model="gpt-4o-mini")
        err_evs = [e for e in case["trajectory"] if e["ev"] == "error.occurred"]
        # Only the tool_execution error survives; the llm_call rate-limit is dropped.
        assert len(err_evs) == 1
        assert err_evs[0]["tool"] == "shell"
        assert err_evs[0]["failure_mode"] == "shell-exit-nonzero"

    def test_file_io_only_workflow_is_skippable(self):
        """A workflow whose only tool is file_io carries no non-file_io tool, so
        the harvester's filter can drop it (covered here via tools_touched)."""
        events = [
            {"event_type": "task_started", "details": {"task_input": "p"}},
            {"event_type": "tool_called", "details": {"tool": "file_io", "cached": False}},
            {"event_type": "task_completed", "details": {"outcome": "success"}},
        ]
        case = case_from_workflow("wf-f", events, model="m")
        assert case["tools_touched"] == ["file_io"]
        assert case["goal_met"] is True
