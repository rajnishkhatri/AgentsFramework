"""EmbeddingClient port — vendor-neutral embedding contract.

Per ``docs/plans/replace_mem0_pgvector.plan.md`` §Phase 1 and the
plan's §Architecture & TDD compliance table:

  * **Layer**: hexagonal port (lives next to ``memory_client.py``).
  * **M-ports invariant**: stdlib + typing only — NO SDK imports here.
    SDK imports live under ``middleware/adapters/embedding/`` exclusively.
  * **Contract surface**: ``embed(texts) → list[list[float]]`` and a
    ``dimension`` property. The dimension is fixed at construction time
    and MUST match what the provider actually returns (the adapter's
    contract test asserts this — Pattern 4 consumer-driven contract).

The dimension is load-bearing because ``services/memory_backends/pgvector.py``
(Phase 2) types its ``embedding`` column as ``VECTOR(<dimension>)``. A
mismatch between port-advertised and provider-returned dim corrupts the
table on INSERT.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


__all__ = ["EmbeddingClient", "EmbeddingClientError"]


class EmbeddingClientError(Exception):
    """Typed error for embedding-adapter failures.

    Adapters MUST translate vendor SDK errors into this type at the
    boundary so callers never see (e.g.) a ``litellm`` exception — the
    same A5/F-R8 discipline that ``MemoryClientError`` enforces.
    """


@runtime_checkable
class EmbeddingClient(Protocol):
    """Application-contract port for text embeddings.

    Implementations:
      * ``middleware.adapters.embedding.litellm_embedding_client.LiteLLMEmbeddingClient`` — real provider via LiteLLM.
      * ``middleware.adapters.embedding.fake.FakeEmbeddingClient`` — deterministic, content-free, test-only.

    Contract:
      * ``await client.embed(texts=[...])`` returns one vector per input,
        in input order, each of length ``client.dimension``.
      * Empty input list returns empty output (no network call).
      * Any provider error is raised as ``EmbeddingClientError``; the
        original cause is preserved via ``raise ... from`` for debugging.
    """

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` and return one vector per input, in order."""
        ...

    @property
    def dimension(self) -> int:
        """The fixed dimensionality of returned vectors."""
        ...
