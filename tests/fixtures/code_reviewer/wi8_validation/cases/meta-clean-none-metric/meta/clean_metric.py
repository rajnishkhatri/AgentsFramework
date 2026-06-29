"""Clean meta/ metric — returns None when undecidable (AP-6), no orchestration import (AP-4)."""

from __future__ import annotations


def failure_rate(tp: int, fn: int, fp: int, tn: int) -> float | None:
    """Return the failure-detection rate, or None when undecidable (AP-6).

    When ``tp + fn == 0`` there is no gold-positive data, so the rate is
    undecidable — return None so downstream gates fail-closed rather than
    trusting a fabricated 0.0.
    """
    total = tp + fn
    if total == 0:
        return None
    return tp / total
