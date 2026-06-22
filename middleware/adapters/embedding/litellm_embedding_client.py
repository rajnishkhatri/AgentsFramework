"""LiteLLM-backed adapter for ``EmbeddingClient``.

Per ``docs/plans/replace_mem0_pgvector.plan.md`` §Phase 1:

  * Default model: ``text-embedding-3-small`` (1536-dim).
  * Transport: ``litellm.aembedding`` — the same sanctioned exception
    that ``services/llm_config.py`` uses for chat completions. This
    keeps SDK isolation (no raw ``openai`` import in ``middleware/``).
  * Boundary discipline (A5/F-R8): any ``litellm`` exception is
    translated to ``EmbeddingClientError`` at the boundary.
  * Eval-capture (AGENTS.md §Development Conventions / pattern H5):
    every embed call is recorded with ``target="embedding"``. The
    Phase 6 drift probe consumes those rows. Content stays opaque —
    only token-count / latency / dim leave the boundary.

Architecture-test invariant: ``litellm`` is allowed under
``middleware/adapters/embedding/`` and the existing ``services/llm_*``
exception. Anywhere else is a layering violation.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import litellm

from middleware.ports.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
)


_logger = logging.getLogger("services.embedding")


__all__ = ["LiteLLMEmbeddingClient"]


class LiteLLMEmbeddingClient(EmbeddingClient):
    """Embeds via ``litellm.aembedding``.

    The provider key is passed by constructor (composition root reads
    it from env — see ``middleware/composition.py``). The adapter NEVER
    reads env directly.
    """

    def __init__(
        self,
        *,
        model: str,
        dimension: int,
        api_key: str,
    ) -> None:
        if dimension <= 0:
            raise ValueError(f"dimension must be positive, got {dimension}")
        self._model = model
        self._dimension = dimension
        self._api_key = api_key

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        # Short-circuit: every provider rejects empty input lists.
        if not texts:
            return []

        t0 = time.perf_counter()
        try:
            response: Any = await litellm.aembedding(
                model=self._model,
                input=texts,
                api_key=self._api_key,
            )
        except Exception as exc:
            # A5: vendor exceptions never leak past the boundary.
            raise EmbeddingClientError(
                f"{type(exc).__name__}: {exc}"
            ) from exc
        latency_ms = (time.perf_counter() - t0) * 1000.0

        data = self._extract_data(response)
        if len(data) != len(texts):
            raise EmbeddingClientError(
                f"provider returned {len(data)} embeddings for "
                f"{len(texts)} inputs"
            )

        vectors: list[list[float]] = []
        for i, row in enumerate(data):
            vec = row.get("embedding") if isinstance(row, dict) else None
            if not isinstance(vec, list):
                raise EmbeddingClientError(
                    f"provider row {i} missing 'embedding' field"
                )
            if len(vec) != self._dimension:
                raise EmbeddingClientError(
                    f"dimension mismatch: provider returned {len(vec)} "
                    f"for row {i}, adapter expected {self._dimension} "
                    f"(model={self._model!r})"
                )
            vectors.append(vec)

        # H5: content-free telemetry. Token count comes from the provider
        # 'usage' field when present; latency + dim are always recorded.
        usage = response.get("usage") if isinstance(response, dict) else None
        _logger.info(
            "embed",
            extra={
                "model": self._model,
                "dimension": self._dimension,
                "input_count": len(texts),
                "latency_ms": latency_ms,
                "tokens_in": usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            },
        )

        return vectors

    @staticmethod
    def _extract_data(response: Any) -> list[Any]:
        """Tolerate both dict-shaped and object-shaped LiteLLM responses.

        ``litellm.aembedding`` typically returns a ``ModelResponse``-like
        object with ``.data`` (a list of ``{"embedding": [...]}`` dicts),
        but tests stub it as a plain dict — accept both.
        """
        if isinstance(response, dict):
            data = response.get("data")
        else:
            data = getattr(response, "data", None)
        if not isinstance(data, list):
            raise EmbeddingClientError(
                "provider response missing 'data' list field"
            )
        return data
