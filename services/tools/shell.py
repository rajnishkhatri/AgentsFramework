"""Shell tool: command allowlist + blocklist enforcement via Pydantic validators."""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from pydantic import BaseModel, Field, field_validator

from services.tools.registry import ToolExecutionResult

ALLOWED_COMMANDS = {"ls", "cat", "head", "tail", "grep", "find", "python", "wc"}
BLOCKED_PATTERNS = {"rm ", "curl ", "wget ", "nc ", "chmod ", "chown ", "sudo "}
SHELL_METACHARACTERS = frozenset(";&|$`<>")
BLOCKED_ARGS = frozenset({"-delete", "-exec", "-execdir"})


class ShellToolInput(BaseModel):
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(default=30, ge=1, le=60)

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        argv = shlex.split(v)
        if not argv:
            raise ValueError("Empty command")
        if argv[0] not in ALLOWED_COMMANDS:
            raise ValueError(f"Command '{argv[0]}' not in allowlist: {sorted(ALLOWED_COMMANDS)}")
        for token in argv:
            if any(ch in token for ch in SHELL_METACHARACTERS):
                raise ValueError(f"Shell metacharacter detected in token '{token}'")
        for token in argv:
            if token in BLOCKED_ARGS:
                raise ValueError(f"Blocked argument '{token}' detected")
        for pattern in BLOCKED_PATTERNS:
            if pattern in v:
                raise ValueError(f"Blocked pattern '{pattern.strip()}' detected in command")
        return v


class ShellToolOutput(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


def execute_shell(args: dict[str, Any]) -> ToolExecutionResult | str:
    """Execute a validated shell command. Returns JSON string of ShellToolOutput."""
    try:
        validated = ShellToolInput(**args)
    except Exception as e:
        # F1 un-mask: allowlist / metacharacter / blocked-arg rejections are
        # arg-validation failures (the model sent a command the validator
        # rejected), not a tool that ran-and-failed. Surface error_class so the
        # carrier reads `validation`, not the generic `tool_reported`.
        return ToolExecutionResult(
            output=f"Error: {e}",
            ok=False,
            error=str(e),
            error_class="validation",
        )

    try:
        argv = shlex.split(validated.command)
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=validated.timeout,
        )
        output = ShellToolOutput(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )
        payload = output.model_dump_json()
        if result.returncode == 0:
            return ToolExecutionResult(output=payload, ok=True)
        return ToolExecutionResult(
            output=payload,
            ok=False,
            error=f"exit code {result.returncode}",
        )
    except subprocess.TimeoutExpired:
        payload = ShellToolOutput(
            stdout="", stderr="Command timed out", exit_code=-1
        ).model_dump_json()
        # The tool ran but exceeded its time budget — a distinct class from a
        # malformed command (validation) or a non-zero exit (tool_reported).
        return ToolExecutionResult(
            output=payload,
            ok=False,
            error="Command timed out",
            error_class="timeout",
        )
    except Exception as e:
        payload = ShellToolOutput(stdout="", stderr=str(e), exit_code=-1).model_dump_json()
        return ToolExecutionResult(output=payload, ok=False, error=str(e))
