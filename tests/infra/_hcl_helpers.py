"""tests/infra/_hcl_helpers.py — HCL traversal utilities for the Sprint 2
infra suite. Kept separate from conftest.py so test modules can `import`
these helpers directly (pytest fixture DI is reserved for parsed-HCL
state, which is conftest's job).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def find_resources(
    resources: list[dict[str, Any]],
    *,
    resource_type: str,
    name: str | None = None,
) -> list[dict[str, Any]]:
    """Filter the flat resources list by type (and optionally local name)."""
    return [
        r
        for r in resources
        if r["type"] == resource_type
        and (name is None or r["name"] == name)
    ]


def get_one(items: Iterable[dict[str, Any]], context: str) -> dict[str, Any]:
    """Assert exactly one match and return it, with a stakeholder-legible
    error message when 0 or 2+ are found."""
    items = list(items)
    assert items, f"{context}: zero matches found"
    assert len(items) == 1, (
        f"{context}: expected exactly 1 match, got {len(items)} "
        f"({[i['name'] for i in items]!r})"
    )
    return items[0]


def unwrap_block(value: Any) -> dict[str, Any] | None:
    """python-hcl2 returns nested blocks as 1-element lists. Resolve that
    so test assertions can read attributes off a plain dict.

    Handles None, dict, and list-of-1-dict cases. Anything else returns
    None (the test surface decides whether that's a failure).
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return None


def unwrap_blocks(value: Any) -> list[dict[str, Any]]:
    """Like `unwrap_block` but for repeated blocks (e.g. multiple
    `containers {}` sub-blocks). Always returns a list, possibly empty."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []
