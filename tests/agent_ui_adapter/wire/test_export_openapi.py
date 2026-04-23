"""L1 Deterministic: Tests for agent_ui_adapter.wire.export_openapi.

Per AGENT_UI_ADAPTER_SPRINTS.md US-2.4 acceptance criteria:
- Output parses as YAML
- Two runs produce byte-identical output (deterministic)
- Every Pydantic model class name from wire/* appears in components.schemas
- All 6 routes (per plan §4 routes table) are present
"""

from __future__ import annotations

import inspect
import subprocess
import sys

import yaml
from pydantic import BaseModel

from agent_ui_adapter.wire import ag_ui_events, agent_protocol, domain_events
from agent_ui_adapter.wire.export_openapi import _build_spec


EXPECTED_ROUTES = {
    ("get", "/agent/threads"),
    ("post", "/agent/threads"),
    ("get", "/agent/threads/{thread_id}"),
    ("post", "/agent/runs/stream"),
    ("get", "/agent/runs/{run_id}"),
    ("delete", "/agent/runs/{run_id}"),
    ("get", "/healthz"),
}


def _wire_model_names() -> set[str]:
    names: set[str] = set()
    for module in (ag_ui_events, agent_protocol, domain_events):
        for cls_name, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseModel)
                and cls.__module__ == module.__name__
                and cls is not BaseModel
            ):
                names.add(cls_name)
    return names


def _run_cli() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "agent_ui_adapter.wire.export_openapi"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_openapi_export_is_valid_yaml():
    output = _run_cli()
    parsed = yaml.safe_load(output)
    assert isinstance(parsed, dict)
    assert parsed.get("openapi", "").startswith("3.1")
    assert "paths" in parsed
    assert "components" in parsed and "schemas" in parsed["components"]


def test_openapi_export_is_deterministic():
    a = _run_cli()
    b = _run_cli()
    assert a == b, "OpenAPI export must be byte-identical across runs"


def test_openapi_export_contains_every_wire_model():
    output = _run_cli()
    parsed = yaml.safe_load(output)
    schemas = parsed["components"]["schemas"]
    for name in _wire_model_names():
        assert name in schemas, (
            f"{name} from wire/ is missing from components.schemas. "
            "Add it via _build_spec()."
        )


def test_openapi_export_has_all_routes():
    output = _run_cli()
    parsed = yaml.safe_load(output)
    actual: set[tuple[str, str]] = set()
    for path, ops in parsed["paths"].items():
        for method in ops:
            actual.add((method.lower(), path))
    missing = EXPECTED_ROUTES - actual
    assert not missing, f"Missing required routes: {missing}"


def test_build_spec_is_pure_function():
    """_build_spec returns the same dict shape on repeat calls."""
    a = _build_spec()
    b = _build_spec()
    assert a == b
    assert isinstance(a, dict)
