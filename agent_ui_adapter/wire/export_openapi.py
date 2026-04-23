"""OpenAPI 3.1 exporter for the AG-UI Agent Protocol surface.

CLI: ``python -m agent_ui_adapter.wire.export_openapi`` prints OpenAPI 3.1
YAML to stdout. Output is deterministic (byte-identical across runs) so the
S8 codegen drift-detection step can reliably block merges on schema changes.

Per AGENT_UI_ADAPTER_PLAN.md §9 codegen pipeline. ``_build_spec()`` is a
pure function returning a dict so it is unit-testable without subprocess.

Per rule R4 / plan §15.2 T4, this module imports stdlib + pydantic + yaml
only. FastAPI is deliberately NOT used here -- it is not yet a project
dependency (S6 owns adding it). We hand-roll the spec from Pydantic JSON
Schemas via ``pydantic.json_schema.models_json_schema``.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, models_json_schema

from agent_ui_adapter.wire import ag_ui_events, agent_protocol, domain_events


_OPENAPI_VERSION = "3.1.0"
_ADAPTER_VERSION = "0.1.0"
_REF_TEMPLATE = "#/components/schemas/{model}"


def _wire_models() -> list[type[BaseModel]]:
    """Collect every ``BaseModel`` subclass declared in the wire ring.

    Order is sorted by class name so the resulting OpenAPI document is
    deterministic regardless of import order.
    """
    seen: dict[str, type[BaseModel]] = {}
    for module in (ag_ui_events, agent_protocol, domain_events):
        for cls_name, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseModel)
                and cls.__module__ == module.__name__
                and cls is not BaseModel
            ):
                seen[cls_name] = cls
    return [seen[name] for name in sorted(seen)]


def _build_components_schemas() -> dict[str, Any]:
    """Build ``components.schemas`` covering every wire model + their $defs."""
    models = _wire_models()
    inputs = [(m, "validation") for m in models]
    _refs, top = models_json_schema(
        inputs,
        ref_template=_REF_TEMPLATE,
        schema_generator=GenerateJsonSchema,
    )
    schemas: dict[str, Any] = {}
    for model_cls in models:
        schemas[model_cls.__name__] = model_cls.model_json_schema(
            ref_template=_REF_TEMPLATE
        )
    for name, schema in (top.get("$defs") or {}).items():
        schemas.setdefault(name, schema)
    return dict(sorted(schemas.items()))


def _request_body(schema_name: str) -> dict[str, Any]:
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{schema_name}"}
            }
        },
    }


def _json_response(schema_name: str, description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/{schema_name}"}
            }
        },
    }


def _sse_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "text/event-stream": {
                "schema": {"type": "string", "format": "event-stream"}
            }
        },
    }


def _build_paths() -> dict[str, Any]:
    """Hand-rolled paths dictionary mirroring plan §4 routes table."""
    return {
        "/agent/threads": {
            "get": {
                "summary": "List threads",
                "operationId": "listThreads",
                "responses": {
                    "200": {
                        "description": "List of threads",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/ThreadState"
                                    },
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "summary": "Create a thread",
                "operationId": "createThread",
                "requestBody": _request_body("ThreadCreateRequest"),
                "responses": {"200": _json_response("ThreadState", "Created thread")},
            },
        },
        "/agent/threads/{thread_id}": {
            "get": {
                "summary": "Get a thread",
                "operationId": "getThread",
                "parameters": [
                    {
                        "name": "thread_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"200": _json_response("ThreadState", "Thread state")},
            },
        },
        "/agent/runs/stream": {
            "post": {
                "summary": "Open an SSE stream of AG-UI events for a run",
                "operationId": "streamRun",
                "requestBody": _request_body("RunCreateRequest"),
                "responses": {
                    "200": _sse_response("AG-UI event stream"),
                    "401": {"description": "Unauthorized"},
                },
            },
        },
        "/agent/runs/{run_id}": {
            "get": {
                "summary": "Get run state",
                "operationId": "getRun",
                "parameters": [
                    {
                        "name": "run_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": _json_response("RunStateView", "Run state"),
                    "404": {"description": "Run not found"},
                },
            },
            "delete": {
                "summary": "Cancel a run",
                "operationId": "cancelRun",
                "parameters": [
                    {
                        "name": "run_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": _json_response("RunStateView", "Cancelled run state"),
                    "404": {"description": "Run not found"},
                },
            },
        },
        "/healthz": {
            "get": {
                "summary": "Liveness probe",
                "operationId": "healthz",
                "responses": {"200": _json_response("HealthResponse", "Healthy")},
            },
        },
    }


def _build_spec() -> dict[str, Any]:
    """Pure function: assemble the OpenAPI 3.1 document as a dict.

    Determinism is guaranteed by:
    - sorted iteration of wire models in ``_build_components_schemas``
    - sorted top-level keys via ``yaml.safe_dump(..., sort_keys=True)``
    - no calls to ``datetime.now`` or RNGs in this code path
    """
    return {
        "openapi": _OPENAPI_VERSION,
        "info": {
            "title": "Agent UI Adapter",
            "version": _ADAPTER_VERSION,
            "description": (
                "AG-UI Agent Protocol routes exposed by agent_ui_adapter. "
                "Generated from Pydantic wire models."
            ),
        },
        "paths": _build_paths(),
        "components": {"schemas": _build_components_schemas()},
    }


def main() -> None:
    spec = _build_spec()
    sys.stdout.write(yaml.safe_dump(spec, sort_keys=True, default_flow_style=False))


if __name__ == "__main__":
    main()
