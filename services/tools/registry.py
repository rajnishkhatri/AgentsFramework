"""Tool dispatch: name -> validated executor (with cacheable flag)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass
class ToolDefinition:
    executor: Callable[[dict[str, Any]], str | ToolExecutionResult]
    schema: type[BaseModel]
    cacheable: bool = False


@dataclass
class ToolExecutionResult:
    """Normalized tool execution envelope.

    This keeps tool dispatch backward-compatible with existing executors that
    return plain strings while enabling richer state-aware results.
    """

    output: str
    ok: bool = True
    error: str | None = None
    state_delta: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ToolRegistry:
    def __init__(self, tools: dict[str, ToolDefinition]) -> None:
        self._tools = tools

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def execute(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        """Backward-compatible execution path returning text output only."""
        return self.execute_with_result(tool_name, tool_args).output

    def execute_with_result(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> ToolExecutionResult:
        if tool_name not in self._tools:
            raise KeyError(f"Unknown tool: {tool_name!r}. Available: {list(self._tools.keys())}")
        defn = self._tools[tool_name]
        raw_result = defn.executor(tool_args)
        if isinstance(raw_result, ToolExecutionResult):
            return raw_result
        output = str(raw_result)
        is_error = output.startswith("Error:")
        return ToolExecutionResult(
            output=output,
            ok=not is_error,
            error=output if is_error else None,
        )

    def is_cacheable(self, tool_name: str) -> bool:
        return self._tools[tool_name].cacheable

    def get_schemas(self) -> list[dict[str, Any]]:
        """Returns tool schemas for LLM bind_tools()."""
        schemas = []
        for name, defn in self._tools.items():
            schema = defn.schema.model_json_schema()
            properties = schema.get("properties", {})
            hidden_keys = [key for key in properties.keys() if key.startswith("_")]
            for hidden_key in hidden_keys:
                properties.pop(hidden_key, None)
            if hidden_keys:
                required = schema.get("required", [])
                schema["required"] = [key for key in required if key not in hidden_keys]
            schemas.append({
                "name": name,
                "description": schema.get("description", ""),
                "parameters": schema,
            })
        return schemas
