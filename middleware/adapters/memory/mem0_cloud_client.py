"""Mem0CloudClient -- ``MemoryClient`` adapter backed by Mem0 Cloud.

Implements ``middleware.ports.memory_client.MemoryClient`` using the
``mem0ai`` SDK. **No SDK type escapes past this boundary** (rule
**F-R8 / A4**) -- every return value is a ``MemoryRecord`` from
``middleware.ports.memory_client``.

This is the v3 default. Sprint 2 will land the full conformance suite
(``tests/middleware/adapters/memory/``); for Sprint 1 the adapter is
constructible and the composition root wires it.

**SDK pin (rule A9):** ``mem0ai >= 0.1.100`` (declared in pyproject).

**Async safety:** The ``mem0ai`` SDK client is synchronous. All blocking
calls are wrapped in ``asyncio.to_thread()`` to avoid blocking the
event loop during I/O (e.g. HTTP round-trips to Mem0 Cloud).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from middleware.ports.memory_client import (
    MemoryClient,  # type: ignore[unused-import]  # for IDE Protocol hint
    MemoryClientError,
    MemoryRecord,
)

logger = logging.getLogger("middleware.adapters.memory")

__all__ = ["Mem0CloudClient"]


class Mem0CloudClient:
    """Thin wrapper around the ``mem0ai`` SDK client.

    The ``mem0ai`` SDK is synchronous; blocking calls are offloaded to a
    thread via ``asyncio.to_thread()`` so the FastAPI event loop is never
    blocked.

    Args:
        api_key: Mem0 Cloud API key (``MEM0_API_KEY``).
        base_url: Mem0 endpoint (``MEM0_BASE_URL``); defaults to
            ``https://api.mem0.ai``.
        sdk_client: optional pre-built SDK client for tests.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.mem0.ai",
        sdk_client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Mem0CloudClient requires a non-empty api_key")
        self._api_key = api_key
        self._base_url = base_url
        self._sdk_client = sdk_client  # lazy import below

    def _client(self) -> Any:
        if self._sdk_client is not None:
            return self._sdk_client
        # Lazy import: keeps module-load fast and confines SDK to the
        # method body. The architecture test only checks top-level
        # imports, but lazy-import is also defensive.
        from mem0 import MemoryClient as _SdkClient

        self._sdk_client = _SdkClient(api_key=self._api_key, host=self._base_url)
        return self._sdk_client

    def _sync_add(self, *, user_id: str, content: str) -> None:
        self._client().add(messages=content, user_id=user_id)

    def _sync_search(
        self, *, user_id: str, query: str, limit: int
    ) -> list[dict[str, Any]]:
        return self._client().search(query=query, user_id=user_id, limit=limit) or []

    async def add(self, *, user_id: str, content: str) -> None:
        try:
            await asyncio.to_thread(
                self._sync_add, user_id=user_id, content=content
            )
        except MemoryClientError:
            raise
        except Exception as exc:
            logger.warning("mem0 add failed: %s: %s", type(exc).__name__, exc)
            raise MemoryClientError(f"mem0 add failed: {exc}") from exc

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        try:
            results = await asyncio.to_thread(
                self._sync_search, user_id=user_id, query=query, limit=limit
            )
        except MemoryClientError:
            raise
        except Exception as exc:
            logger.warning("mem0 search failed: %s: %s", type(exc).__name__, exc)
            raise MemoryClientError(f"mem0 search failed: {exc}") from exc

        records: list[MemoryRecord] = []
        for item in results:
            records.append(
                MemoryRecord(
                    id=str(item.get("id", "")),
                    user_id=user_id,
                    content=str(item.get("memory") or item.get("text") or ""),
                    score=item.get("score"),
                    created_at=_parse_iso(item.get("created_at")),
                )
            )
        return records


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)
