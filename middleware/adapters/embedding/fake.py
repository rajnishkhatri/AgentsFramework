"""Deterministic, content-free fake ``EmbeddingClient`` for tests.

Used by:
  * ``tests/middleware/adapters/embedding/test_litellm_embedding_client.py``
    (Pattern 4 consumer-driven contract — same suite the real adapter passes).
  * ``tests/services/memory_backends/test_pgvector_backend.py`` (Phase 2).
  * The Phase 0 spike at ``scripts/spike_pgvector_c3.py`` (uses the same
    SHA256-based recipe inline).

Rule: this fake MUST stay stdlib-only and MUST NOT import any SDK. The
architecture test asserts that ``litellm`` lives only in the real
adapter.
"""

from __future__ import annotations

import hashlib

from middleware.ports.embedding_client import EmbeddingClient


__all__ = ["FakeEmbeddingClient"]


class FakeEmbeddingClient(EmbeddingClient):
    """Deterministic SHA256-based fake.

    ``embed("foo")`` always yields the same vector; distinct inputs
    yield distinct vectors. Vectors are L2-normalized so cosine and
    dot-product agree, which keeps the Phase 2 backend tests stable.
    """

    def __init__(self, *, dimension: int = 1536) -> None:
        if dimension <= 0:
            raise ValueError(f"dimension must be positive, got {dimension}")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [(h[i % len(h)] / 255.0) - 0.5 for i in range(self._dimension)]
        norm = sum(x * x for x in raw) ** 0.5 or 1.0
        return [x / norm for x in raw]
