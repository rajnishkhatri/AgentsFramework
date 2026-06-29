"""Clean thin orchestration node — delegates all logic to components/ (AP-5)."""

from components.clean_router import route


async def route_node(state: dict) -> dict:
    """Thin wrapper: route the latest message, store the decision, return.

    No domain logic here — AP-5 respected (<=10-15 lines, all work delegated).
    """
    decision = route(state["messages"][-1])
    state["route"] = decision.model_dump()
    return state
