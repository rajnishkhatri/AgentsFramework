"""Architecture test: F-R6 read-only enforcement on the agents router.

S2.2.1 AC: "the FastAPI router has zero `POST/PUT/PATCH/DELETE` routes."

This is enforced by reflecting on the `APIRoute.methods` set after the router
is built -- so a future maintainer who naively adds `@router.post(...)` will
fail this test before any UI Suspend/Revoke button can be wired up.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from explainability_app.server import _build_agents_router

MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class _NullService:
    """Minimal duck-typed stub: the router is built without any traffic."""

    def list_agents(self):  # noqa: D401 - test stub
        return []

    def get_agent_card(self, agent_id):  # noqa: D401
        raise KeyError(agent_id)

    def get_agent_audit(self, agent_id):  # noqa: D401
        raise KeyError(agent_id)


def test_agents_router_has_zero_mutation_methods() -> None:
    router = _build_agents_router(_NullService())
    violations: list[tuple[str, str]] = []
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in MUTATION_METHODS:
                violations.append((method, route.path))
    assert violations == [], (
        f"F-R6 violation: agents router exposes mutation routes: {violations}"
    )


def test_agents_router_only_exposes_get_routes() -> None:
    router = _build_agents_router(_NullService())
    assert router.routes, "agents router should expose at least the catalog GET"
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = (route.methods or set()) - {"HEAD", "OPTIONS"}
        assert methods <= {"GET"}, (
            f"F-R6 violation: {route.path} exposes non-GET methods: {methods}"
        )
