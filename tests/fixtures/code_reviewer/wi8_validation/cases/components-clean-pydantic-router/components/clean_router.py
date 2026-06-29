"""Clean component router — deterministic heuristics + Pydantic output (V2/V6)."""

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """The non-trivial output of the router — a Pydantic model (V6)."""

    target: str = Field(description="The selected target handler.")
    confidence: float = Field(ge=0.0, le=1.0, description="Heuristic confidence.")
    reasons: tuple[str, ...] = Field(default_factory=tuple)


def route(message: str) -> RouteDecision:
    """Route a message deterministically — no LLM, no peer component imports."""
    if not message:
        return RouteDecision(target="fallback", confidence=0.0, reasons=("empty",))
    lowered = message.lower()
    if "error" in lowered:
        return RouteDecision(
            target="error_handler", confidence=0.8, reasons=("keyword",)
        )
    return RouteDecision(target="default", confidence=0.6, reasons=("fallback",))
