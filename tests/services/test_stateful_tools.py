"""L2 contract tests for state-aware file/todo tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from services.tools.file_tools import execute_state_file_tool
from services.tools.task_tool import build_task_tool_executor, execute_task_tool
from services.tools.todo_tools import execute_state_todo_tool


class TestStateFileTool:
    def test_write_emits_files_state_delta(self):
        result = execute_state_file_tool(
            {
                "operation": "write",
                "file_path": "notes.md",
                "content": "hello",
            }
        )
        assert result.ok is True
        assert result.state_delta == {"files": {"notes.md": "hello"}}

    def test_read_uses_injected_state_files(self):
        result = execute_state_file_tool(
            {
                "operation": "read",
                "file_path": "notes.md",
                "_state": {"files": {"notes.md": "from-state"}},
            }
        )
        assert result.ok is True
        assert result.output == "from-state"

    def test_list_returns_sorted_names(self):
        result = execute_state_file_tool(
            {
                "operation": "list",
                "_state": {"files": {"b.txt": "b", "a.txt": "a"}},
            }
        )
        assert result.output.splitlines() == ["a.txt", "b.txt"]


class TestStateTodoTool:
    def test_set_todos_updates_state(self):
        result = execute_state_todo_tool(
            {
                "operation": "set",
                "todos": [
                    {"id": "1", "content": "task", "status": "pending"},
                ],
            }
        )
        assert result.ok is True
        assert result.state_delta is not None
        assert result.state_delta["todos"][0]["id"] == "1"

    def test_read_returns_current_todos_json(self):
        result = execute_state_todo_tool(
            {
                "operation": "read",
                "_state": {
                    "todos": [{"id": "1", "content": "task", "status": "pending"}]
                },
            }
        )
        parsed = json.loads(result.output)
        assert parsed[0]["status"] == "pending"

    def test_set_plan_ref_updates_plan_reference(self):
        result = execute_state_todo_tool(
            {
                "operation": "set_plan_ref",
                "plan_ref": "plan://s1",
            }
        )
        assert result.ok is True
        assert result.state_delta == {"plan_ref": "plan://s1"}


class TestTaskTool:
    def test_delegate_denied_by_policy_gate(self):
        result = execute_task_tool(
            {
                "operation": "delegate",
                "objective": "Investigate trace drift",
                "subagent_type": "research",
                "policy_mode": "deny",
            }
        )
        assert result.ok is False
        assert "DELEGATION_POLICY_DENY" in (result.error or "")

    def test_delegate_denied_by_budget_gate(self):
        result = execute_task_tool(
            {
                "operation": "delegate",
                "objective": "Analyze logs",
                "subagent_type": "analyst",
                "estimated_cost_usd": 0.6,
                "_state": {
                    "agent_capabilities": ["delegate.subagent.*"],
                    "total_cost_usd": 0.3,
                    "delegation_max_cost_usd": 0.8,
                },
            }
        )
        assert result.ok is False
        assert result.error == "DELEGATION_BUDGET_EXCEEDED"

    def test_delegate_denied_when_subagent_type_not_in_capabilities(self):
        result = execute_task_tool(
            {
                "operation": "delegate",
                "objective": "Analyze logs",
                "subagent_type": "analyst",
                "_state": {
                    "agent_capabilities": ["delegate.subagent.research"],
                },
            }
        )
        assert result.ok is False
        assert result.error == "DELEGATION_SUBAGENT_NOT_ALLOWED"

    def test_delegate_writes_deterministic_handoff_files(self):
        result = execute_task_tool(
            {
                "operation": "delegate",
                "objective": "Summarize compliance risks",
                "subagent_type": "compliance-agent",
                "_state": {
                    "workflow_id": "wf-123",
                    "step_count": 2,
                    "agent_capabilities": ["delegate.subagent.*"],
                },
            }
        )
        assert result.ok is True
        assert result.state_delta is not None
        files = result.state_delta["files"]
        keys = sorted(files.keys())
        assert keys[0].startswith(".agent_handoff/wf-123_step_2_compliance-agent/")
        assert keys[1].startswith(".agent_handoff/wf-123_step_2_compliance-agent/")
        payload = json.loads(files[keys[1]])
        assert payload["correlation_id"] == "wf-123:step:2:compliance-agent"

    def test_delegate_throttled_by_call_budget(self):
        result = execute_task_tool(
            {
                "operation": "delegate",
                "objective": "Run another branch",
                "subagent_type": "research",
                "_state": {
                    "agent_capabilities": ["delegate.subagent.*"],
                    "delegation_call_count": 2,
                    "delegation_max_calls_per_task": 2,
                },
            }
        )
        assert result.ok is False
        assert result.error == "DELEGATION_THROTTLED"

    def test_reconcile_reads_handoff_and_writes_reconciled_artifact(self):
        handoff_ref = ".agent_handoff/wf-abc_step_4_research/result.json"
        handoff_payload = {
            "correlation_id": "wf-abc:step:4:research",
            "status": "completed",
            "output": "child summary",
            "error": None,
        }
        result = execute_task_tool(
            {
                "operation": "reconcile",
                "objective": "Reconcile child output",
                "subagent_type": "research",
                "handoff_ref": handoff_ref,
                "_state": {"files": {handoff_ref: json.dumps(handoff_payload)}},
            }
        )
        assert result.ok is True
        assert result.state_delta is not None
        reconcile_files = result.state_delta["files"]
        reconcile_ref = ".agent_handoff/wf-abc_step_4_research/reconciled.json"
        assert reconcile_ref in reconcile_files
        reconciled = json.loads(reconcile_files[reconcile_ref])
        assert reconciled["status"] == "completed"

    def test_delegate_uses_bound_dispatcher_callback(self):
        dispatcher = MagicMock(
            return_value={
                "status": "completed",
                "output": "live child output",
                "error": None,
                "child_correlation_id": "wf-1:child:abc",
            }
        )
        executor = build_task_tool_executor(dispatcher)
        result = executor(
            {
                "operation": "delegate",
                "objective": "Collect sprint notes",
                "subagent_type": "research",
                "_state": {
                    "workflow_id": "wf-1",
                    "step_count": 3,
                    "agent_capabilities": ["delegate.subagent.*"],
                },
            }
        )
        assert result.ok is True
        assert dispatcher.call_count == 1
        call_payload = dispatcher.call_args.args[0]
        assert call_payload["objective"] == "Collect sprint notes"
        assert call_payload["correlation_id"] == "wf-1:step:3:research"
