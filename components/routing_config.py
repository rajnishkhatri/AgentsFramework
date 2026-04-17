"""Domain-specific routing thresholds.

NO langgraph or langchain imports allowed.

In Phase 1, these fields exist but the route node always returns default_model.
In Phase 2, the router reads these thresholds to make routing decisions.
The meta-optimizer (Phase 4) tunes these values.
"""

from __future__ import annotations

from pydantic import BaseModel


class RoutingConfig(BaseModel):
    default_model: str = "gpt-4o-mini"
    escalate_after_failures: int = 2
    max_escalations: int = 3
    budget_downgrade_threshold: float = 0.8
