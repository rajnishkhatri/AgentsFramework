"""File I/O tool: path-sandboxed read/write against $WORKSPACE_DIR."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FileIOInput(BaseModel):
    path: str
    operation: str  # "read" | "write"
    content: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        resolved = Path(v).resolve()
        workspace = Path(os.environ.get("WORKSPACE_DIR", "/workspace")).resolve()
        if not resolved.is_relative_to(workspace):
            raise ValueError(f"Path {v} is outside workspace boundary ({workspace})")
        return str(resolved)


class FileIOOutput(BaseModel):
    content: str | None = None
    bytes_written: int | None = None
    success: bool


def execute_file_io(args: dict[str, Any]) -> str:
    """Execute a validated file I/O operation."""
    try:
        validated = FileIOInput(**args)
    except Exception as e:
        return f"Error: {e}"

    try:
        p = Path(validated.path)
        if validated.operation == "read":
            content = p.read_text()
            return FileIOOutput(content=content, success=True).model_dump_json()
        elif validated.operation == "write":
            content = validated.content or ""
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return FileIOOutput(
                bytes_written=len(content),
                success=True,
            ).model_dump_json()
        else:
            return FileIOOutput(success=False).model_dump_json()
    except Exception as e:
        return f"Error: {e}"
