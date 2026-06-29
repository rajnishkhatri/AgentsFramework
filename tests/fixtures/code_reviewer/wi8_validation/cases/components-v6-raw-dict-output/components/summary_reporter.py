"""Component returning a raw dict for a non-trivial output — violates V6."""

from typing import Any


def summarize(scores: dict[str, float]) -> dict[str, Any]:
    """Build a summary of a score map.

    BUG (V6): the output is a non-trivial, structured result (mean/max/min/
    count) returned as a raw dict. V6 requires Pydantic models for non-trivial
    outputs so callers get validation + field documentation instead of an
    untyped mapping.
    """
    values = list(scores.values())
    return {
        "mean": sum(values) / len(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "min": min(values) if values else 0.0,
        "count": len(values),
    }
