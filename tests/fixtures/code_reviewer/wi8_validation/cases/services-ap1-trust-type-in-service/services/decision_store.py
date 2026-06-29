"""Service module that defines a trust-kernel type — violates AP-1."""

from pydantic import BaseModel


class VerdictRecord(BaseModel):
    """A trust-level verdict record.

    BUG (AP-1): this is a shared trust-kernel type (a signed/unsigned verdict
    field shape) and belongs in trust/models.py, not in a horizontal service.
    Placing it here means the trust kernel's re-signing contract can't see it
    and services grow hidden coupling to trust semantics.
    """

    status: str
    confidence: float
    signed: bool = False


def store(verdict: VerdictRecord) -> None:
    """Persist a verdict (placeholder)."""
    _ = verdict
