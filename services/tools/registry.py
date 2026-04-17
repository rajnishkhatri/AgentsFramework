"""Tool dispatch: name -> validated executor (with cacheable flag)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass
class ToolDefinition:
    executor: Callable[[dict[str, Any]], str]
    schema: type[BaseModel]
    cacheable: bool = False


class ToolRegistry:
    def __init__(self, tools: dict[str, ToolDefinition]) -> None:
        self._tools = tools

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def execute(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        if tool_name not in self._tools:
            raise KeyError(f"Unknown tool: {tool_name!r}. Available: {list(self._tools.keys())}")
        defn = self._tools[tool_name]
        return defn.executor(tool_args)

    def is_cacheable(self, tool_name: str) -> bool:
        return self._tools[tool_name].cacheable

    def get_schemas(self) -> list[dict[str, Any]]:
        """Returns tool schemas for LLM bind_tools()."""
        schemas = []
        for name, defn in self._tools.items():
            schema = defn.schema.model_json_schema()
            schemas.append({
                "name": name,
                "description": schema.get("description", ""),
                "parameters": schema,
            })
        return schemas
