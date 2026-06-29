"""Fabricates a metric where undecidable — violates AP-6 (None not 0.0)."""


def failure_rate(tp: int, fn: int, fp: int, tn: int) -> float:
    """Return the failure-detection rate.

    BUG (AP-6): when ``tp + fn == 0`` there is no gold-positive data, so the
    rate is *undecidable*. Returning 0.0 fabricates a real-looking number from
    no data — it must be ``None`` so downstream gates fail-closed instead of
    silently trusting a zero.
    """
    total = tp + fn
    if total == 0:
        return 0.0  # WRONG: should be None
    return tp / total
