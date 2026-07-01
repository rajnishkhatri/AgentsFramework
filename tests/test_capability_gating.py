"""L1 unit tests for the capability-gating component (ADR-0007, FR-3/4/5).

Red/green (TAP-4): these are written failure-first — watch them fail before
`components/capability_gating.py` exists / is implemented.

The component makes ``AgentFacts.capabilities`` load-bearingly gate the tool set:
only the tools an agent declares are bound to its LLM. A capability that names a
tool absent from the registry is a *config bug* and must fail fast (FR-5), not
degrade to a silent empty tool set.
"""

from __future__ import annotations

import pytest

from components.capability_gating import (
    CapabilityGateResult,
    CapabilityToolMissingError,
    derive_bound_tools,
    filter_registry_schemas,
)


class TestDeriveBoundTools:
    def test_intersection_binds_only_declared_tools(self) -> None:
        """FR-3/FR-4: the coach declares think+file_io; shell/web_search/python
        exist in the registry but are NOT bound."""
        result = derive_bound_tools(
            capability_names=["think", "file_io"],
            available_tool_names=["think", "file_io", "shell", "web_search", "python"],
        )
        assert isinstance(result, CapabilityGateResult)
        assert set(result.bound_tool_names) == {"think", "file_io"}
        assert "shell" not in result.bound_tool_names
        assert "web_search" not in result.bound_tool_names
        assert "python" not in result.bound_tool_names

    def test_declared_equals_bound(self) -> None:
        """The result records the declared capabilities alongside the bound set so
        the arch test / trace can assert declared == bound."""
        result = derive_bound_tools(
            capability_names=["think", "file_io"],
            available_tool_names=["think", "file_io", "shell"],
        )
        assert set(result.bound_tool_names) == set(result.capabilities)

    def test_missing_tool_fails_fast(self) -> None:
        """FR-5: a capability naming a tool absent from the registry raises — a
        declared-but-unavailable tool is a deployment bug, not a silent no-op."""
        with pytest.raises(CapabilityToolMissingError) as exc:
            derive_bound_tools(
                capability_names=["think", "does_not_exist"],
                available_tool_names=["think", "file_io"],
            )
        # The error names the offending capability and the available set so an
        # operator can fix the contract/registry drift immediately.
        message = str(exc.value)
        assert "does_not_exist" in message
        assert "file_io" in message or "think" in message

    def test_empty_capabilities_binds_nothing(self) -> None:
        """An agent declaring no capabilities is bound no tools (least privilege)."""
        result = derive_bound_tools(
            capability_names=[],
            available_tool_names=["think", "file_io", "shell"],
        )
        assert result.bound_tool_names == []

    def test_ordering_is_deterministic(self) -> None:
        """Bound names follow the declared order (stable evidence object)."""
        result = derive_bound_tools(
            capability_names=["file_io", "think"],
            available_tool_names=["think", "file_io", "shell"],
        )
        assert result.bound_tool_names == ["file_io", "think"]


class TestFilterRegistrySchemas:
    def _schemas(self) -> list[dict]:
        # Mirrors ToolRegistry.get_schemas() shape: list of {name, description, parameters}.
        return [
            {"name": "think", "description": "reason", "parameters": {}},
            {"name": "file_io", "description": "read/write", "parameters": {}},
            {"name": "shell", "description": "run", "parameters": {}},
            {"name": "web_search", "description": "search", "parameters": {}},
        ]

    def test_filter_keeps_only_bound(self) -> None:
        filtered = filter_registry_schemas(self._schemas(), ["think", "file_io"])
        names = {s["name"] for s in filtered}
        assert names == {"think", "file_io"}

    def test_filter_excludes_shell_and_web_search(self) -> None:
        filtered = filter_registry_schemas(self._schemas(), ["think", "file_io"])
        names = {s["name"] for s in filtered}
        assert "shell" not in names
        assert "web_search" not in names

    def test_filter_preserves_schema_objects(self) -> None:
        """Filtering selects — it does not mutate — the schema dicts."""
        schemas = self._schemas()
        filtered = filter_registry_schemas(schemas, ["think"])
        assert filtered == [
            {"name": "think", "description": "reason", "parameters": {}}
        ]
