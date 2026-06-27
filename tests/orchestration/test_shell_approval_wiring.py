"""Wiring: _execute_tools_impl routes the shell tool through the approval gate.

Proves the L4 gate is actually invoked from the tool-execution seam (not just
unit-tested in isolation) and that it records exactly one ``GUARDRAIL_CHECKED``
carrier per shell call, runs the subprocess only on an EXECUTE outcome, and
fails closed on the deny band — all without a live LLM and with a *fake* shell
executor (so no real subprocess runs).

Discipline mirrors ``test_tool_error_class``: a real ``ToolRegistry`` + real
``BlackBoxRecorder`` on ``tmp_path``; only the leaf ``shell`` executor is a stub
that records the commands it was asked to run.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from services.base_config import AgentConfig
from services.governance.black_box import BlackBoxRecorder, EventType
from services.tools.registry import (
    ToolDefinition,
    ToolExecutionResult,
    ToolRegistry,
)


class _ShellInput(BaseModel):
    command: str = ""
    timeout: int = 30


class _FakeShell:
    """Stub shell executor — records commands, never spawns a subprocess."""

    def __init__(self) -> None:
        self.ran: list[str] = []

    def __call__(self, args: dict) -> ToolExecutionResult:
        cmd = args.get("command", "")
        self.ran.append(cmd)
        return ToolExecutionResult(output=f"ran:{cmd}", ok=True)


def _registry(executor) -> ToolRegistry:
    return ToolRegistry(
        {"shell": ToolDefinition(executor=executor, schema=_ShellInput, cacheable=False)}
    )


def _state_calling_shell(command: str) -> dict:
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "shell", "args": {"command": command}, "id": "c1", "type": "tool_call"}
        ],
    )
    return {"workflow_id": "wf-shellgate", "messages": [ai], "step_count": 1}


def _run(state: dict, registry: ToolRegistry, config: AgentConfig, tmp_path):
    from orchestration.react_loop import _execute_tools_impl

    black_box = BlackBoxRecorder(storage_dir=tmp_path)
    _execute_tools_impl(
        state, tool_registry=registry, black_box=black_box, agent_config=config
    )
    events = black_box.replay("wf-shellgate")
    guardrail = [e for e in events if e.event_type == EventType.GUARDRAIL_CHECKED]
    return guardrail


def test_disabled_flag_runs_unchanged_no_guardrail_carrier(tmp_path):
    shell = _FakeShell()
    config = AgentConfig(shell_approval_enabled=False)
    carriers = _run(_state_calling_shell("mkdir build"), _registry(shell), config, tmp_path)
    assert shell.ran == ["mkdir build"]
    assert carriers == []  # gate off → byte-identical to today


def test_low_command_auto_runs_with_one_carrier(tmp_path):
    shell = _FakeShell()
    config = AgentConfig(shell_approval_enabled=True, shell_approval_enforce=True)
    carriers = _run(_state_calling_shell("ls -la"), _registry(shell), config, tmp_path)
    assert shell.ran == ["ls -la"]
    assert len(carriers) == 1
    assert carriers[0].details["band"] == "auto"
    assert carriers[0].details["guardrail"] == "shell_severity"


def test_critical_command_is_denied_and_never_runs(tmp_path):
    shell = _FakeShell()
    config = AgentConfig(shell_approval_enabled=True, shell_approval_enforce=True)
    carriers = _run(_state_calling_shell("rm -rf /"), _registry(shell), config, tmp_path)
    assert shell.ran == []  # hard-deny: subprocess never invoked
    assert len(carriers) == 1
    assert carriers[0].details["band"] == "deny"
    assert carriers[0].details["decision"] == "deny"


def test_shadow_ask_runs_anyway_and_marks_would_enforce(tmp_path):
    shell = _FakeShell()
    # enforce=False (Phase A shadow): the ask band records but does not interrupt.
    config = AgentConfig(
        shell_approval_enabled=True,
        shell_approval_enforce=False,
        shell_approval_severity_threshold="medium",
    )
    carriers = _run(_state_calling_shell("mkdir build"), _registry(shell), config, tmp_path)
    assert shell.ran == ["mkdir build"]
    assert len(carriers) == 1
    assert carriers[0].details["would_enforce"] is True
