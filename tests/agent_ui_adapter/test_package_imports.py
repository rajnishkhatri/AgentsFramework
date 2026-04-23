"""US-0.1 sanity test: agent_ui_adapter package and subpackages are importable."""

from __future__ import annotations

import importlib

import pytest


SUBPACKAGES = [
    "agent_ui_adapter",
    "agent_ui_adapter.ports",
    "agent_ui_adapter.adapters",
    "agent_ui_adapter.adapters.runtime",
    "agent_ui_adapter.wire",
    "agent_ui_adapter.translators",
    "agent_ui_adapter.transport",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_importable(name: str) -> None:
    module = importlib.import_module(name)
    assert module is not None, f"{name} must be importable"
