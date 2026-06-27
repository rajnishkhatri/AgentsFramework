"""State-aware virtual file tools for long-running task context.

These tools operate on the in-state ``files`` dictionary rather than disk.
They are intended for context offloading and intermediate artifact storage.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from services.tools.registry import ToolExecutionResult


class StateFileToolInput(BaseModel):
    operation: Literal["list", "read", "write"]
    file_path: str | None = None
    content: str | None = None
    state: dict[str, Any] = Field(default_factory=dict, alias="_state")

    model_config = ConfigDict(populate_by_name=True)


def execute_state_file_tool(args: dict[str, Any]) -> ToolExecutionResult:
    """Execute file operations against the in-state virtual filesystem."""
    try:
        validated = StateFileToolInput(**args)
    except Exception as exc:
        # F1 un-mask: a schema-construction failure is malformed args.
        return ToolExecutionResult(
            output=f"Error: {exc}", ok=False, error=str(exc), error_class="validation"
        )

    files = validated.state.get("files", {}) or {}
    if not isinstance(files, dict):
        files = {}

    if validated.operation == "list":
        names = sorted(str(name) for name in files.keys())
        return ToolExecutionResult(output="\n".join(names) if names else "(no files)")

    if validated.operation == "read":
        if not validated.file_path:
            err = "file_path is required for read operation"
            return ToolExecutionResult(
                output=f"Error: {err}", ok=False, error=err, error_class="validation"
            )
        if validated.file_path not in files:
            err = f"File '{validated.file_path}' not found"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        return ToolExecutionResult(output=str(files[validated.file_path]))

    if validated.operation == "write":
        if not validated.file_path:
            err = "file_path is required for write operation"
            return ToolExecutionResult(
                output=f"Error: {err}", ok=False, error=err, error_class="validation"
            )
        return ToolExecutionResult(
            output=f"Updated virtual file {validated.file_path}",
            ok=True,
            state_delta={
                "files": {
                    str(validated.file_path): validated.content or "",
                }
            },
        )

    err = f"Unsupported operation '{validated.operation}'"
    return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
