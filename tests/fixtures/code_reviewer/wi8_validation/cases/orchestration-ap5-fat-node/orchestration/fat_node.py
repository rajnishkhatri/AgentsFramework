"""A graph node carrying domain logic — violates AP-5 (thin wrappers)."""

from components.router import route_request
from components.evaluator import score_response
from services.prompt_service import PromptService


async def review_node(state: dict) -> dict:
    """Review node — all of this logic should live in components/, not the node.

    AP-5 violation: orchestration nodes are thin wrappers (<=10-15 lines) that
    delegate to components/ and services/. This node inlines routing, scoring,
    low-confidence flagging, prompt rendering, and verdict assembly — domain
    logic that must be pushed down into a component.
    """
    routes = route_request(state["messages"])
    scores = []
    for r in routes:
        result = score_response(r, state["expected"])
        if result.confidence < 0.5:
            scores.append({"route": r, "flag": "low_confidence", "score": result.score})
        else:
            scores.append({"route": r, "score": result.score})
    prompt = PromptService().render_prompt("review_summary", scores=scores)
    summary = {"scores": scores, "prompt": prompt, "verdict": "needs_review"}
    if any(s.get("flag") for s in scores):
        summary["verdict"] = "reject"
    state["summary"] = summary
    return state
