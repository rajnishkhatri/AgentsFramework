"""MemoryClient port -- vendor-neutral long-term memory contract.

Per Sprint 1 §S1.1.2: composition wires a memory client behind this
port. v3 default = ``Mem0CloudClient`` (Mem0 Hobby tier). v2 graduation
= ``SelfHostedMem0Client``. Both implement this Protocol; neither leaks
SDK types past the boundary (rule **F-R8 / A4**).

Full behavioral contract + adapter conformance tests land in Sprint 2.
This file declares the wire shape and the Protocol so the composition
root in Sprint 1 has a typed return value.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


__all__ = ["MemoryRecord", "MemoryClient", "MemoryClientError"]


class MemoryRecord(BaseModel):
    """One long-term-memory entry, vendor-neutral."""

    id: str
    user_id: str
    content: str
    score: float | None = None
    created_at: datetime

    model_config = ConfigDict(frozen=True)


class MemoryClientError(Exception):
    """Typed error for adapter-level failures.

    Adapters MUST translate vendor SDK errors into this type at the
    boundary -- callers never see a Mem0 SDK exception (rule A5).
    """


@runtime_checkable
class MemoryClient(Protocol):
    """Application-contract port for long-term memory."""

    async def add(self, *, user_id: str, content: str) -> None:
        """Persist ``content`` against ``user_id``. Idempotent on retry."""
        ...

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Return at most ``limit`` records ranked by relevance to ``query``."""
        ...
