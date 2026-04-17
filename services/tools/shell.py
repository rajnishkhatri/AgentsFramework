"""Shell tool: command allowlist + blocklist enforcement via Pydantic validators."""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from pydantic import BaseModel, Field, field_validator

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


def execute_shell(args: dict[str, Any]) -> str:
    """Execute a validated shell command. Returns JSON string of ShellToolOutput."""
    try:
        validated = ShellToolInput(**args)
    except Exception as e:
        return f"Error: {e}"

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
        return output.model_dump_json()
    except subprocess.TimeoutExpired:
        return ShellToolOutput(stdout="", stderr="Command timed out", exit_code=-1).model_dump_json()
    except Exception as e:
        return ShellToolOutput(stdout="", stderr=str(e), exit_code=-1).model_dump_json()
