"""State-aware todo tools for structured task tracking."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from services.tools.registry import ToolExecutionResult


class TodoItem(BaseModel):
    id: str
    content: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]


class StateTodoToolInput(BaseModel):
    operation: Literal["read", "set", "append", "update_status", "set_plan_ref"]
    todo: TodoItem | None = None
    todos: list[TodoItem] | None = None
    todo_id: str | None = None
    status: Literal["pending", "in_progress", "completed", "cancelled"] | None = None
    plan_ref: str | None = None
    state: dict[str, Any] = Field(default_factory=dict, alias="_state")

    model_config = ConfigDict(populate_by_name=True)


def execute_state_todo_tool(args: dict[str, Any]) -> ToolExecutionResult:
    """Execute todo operations against in-state ``todos`` and ``plan_ref``."""
    try:
        validated = StateTodoToolInput(**args)
    except Exception as exc:
        return ToolExecutionResult(output=f"Error: {exc}", ok=False, error=str(exc))

    todos_raw = validated.state.get("todos", []) or []
    current_todos: list[dict[str, Any]] = [
        t.model_dump(mode="json") if isinstance(t, TodoItem) else dict(t)
        for t in todos_raw
        if isinstance(t, (dict, TodoItem))
    ]

    if validated.operation == "read":
        return ToolExecutionResult(output=json.dumps(current_todos))

    if validated.operation == "set":
        if validated.todos is None:
            err = "todos is required for set operation"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        next_todos = [todo.model_dump(mode="json") for todo in validated.todos]
        return ToolExecutionResult(
            output=f"Set {len(next_todos)} todos",
            state_delta={"todos": next_todos},
        )

    if validated.operation == "append":
        if validated.todo is None:
            err = "todo is required for append operation"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        next_todos = current_todos + [validated.todo.model_dump(mode="json")]
        return ToolExecutionResult(
            output=f"Appended todo {validated.todo.id}",
            state_delta={"todos": next_todos},
        )

    if validated.operation == "update_status":
        if not validated.todo_id or not validated.status:
            err = "todo_id and status are required for update_status operation"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        updated = False
        next_todos: list[dict[str, Any]] = []
        for todo in current_todos:
            if todo.get("id") == validated.todo_id:
                patched = dict(todo)
                patched["status"] = validated.status
                next_todos.append(patched)
                updated = True
            else:
                next_todos.append(todo)
        if not updated:
            err = f"Todo '{validated.todo_id}' not found"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        return ToolExecutionResult(
            output=f"Updated todo {validated.todo_id} to {validated.status}",
            state_delta={"todos": next_todos},
        )

    if validated.operation == "set_plan_ref":
        if not validated.plan_ref:
            err = "plan_ref is required for set_plan_ref operation"
            return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
        return ToolExecutionResult(
            output=f"Set plan reference to {validated.plan_ref}",
            state_delta={"plan_ref": validated.plan_ref},
        )

    err = f"Unsupported operation '{validated.operation}'"
    return ToolExecutionResult(output=f"Error: {err}", ok=False, error=err)
