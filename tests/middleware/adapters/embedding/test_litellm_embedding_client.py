"""Phase 1 — ``EmbeddingClient`` port + ``LiteLLMEmbeddingClient`` adapter.

Per ``docs/plans/replace_mem0_pgvector.plan.md`` §Phase 1 + TDD pyramid
**Protocol B** (contract-driven, mock I/O). Failure-paths-first per
AGENTS.md §Testing Rules and the plan's §Architecture & TDD compliance
table: rejection tests precede acceptance tests in this file.

The transport choice is ``litellm.aembedding`` — the same sanctioned
exception that ``services/llm_config.py`` uses for chat completions.
This keeps SDK isolation: ``litellm`` import lives only under
``middleware/adapters/embedding/`` and the existing ``services/`` callers.

CI invariant (AGENTS.md §Testing Rules + skill AP-7): no live LLM in
these tests. The real ``LiteLLMEmbeddingClient`` exercises a stubbed
``litellm.aembedding`` via ``monkeypatch``; the ``FakeEmbeddingClient``
fixture covers the deterministic fast-path.
"""

from __future__ import annotations

from typing import Any

import pytest

# Targets under test (do NOT relax these imports to forgive missing files —
# the L1 architecture test asserts the same placement.)
from middleware.adapters.embedding.fake import FakeEmbeddingClient
from middleware.adapters.embedding.litellm_embedding_client import (
    LiteLLMEmbeddingClient,
)
from middleware.ports.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
)


REQUIRED_DIMENSION = 1536  # text-embedding-3-small default


# ─────────────────────────────────────────────────────────────────────
# Rejection / failure-mode matrix (FIRST — failure-paths-first)
#
# Pattern 11 from TDD prompt: enumerate the ways the adapter can break
# before we assert the way it works.
# ─────────────────────────────────────────────────────────────────────


class TestLiteLLMEmbeddingClientRejections:
    """Pattern 11: failure-mode matrix for the LiteLLM adapter."""

    def test_empty_input_list_returns_empty(self) -> None:
        """Empty input → empty output, no network call. The adapter MUST
        short-circuit; calling the API with zero inputs is a contract
        violation by every embedding provider.
        """
        client = LiteLLMEmbeddingClient(
            model="text-embedding-3-small",
            dimension=REQUIRED_DIMENSION,
            api_key="sk-test-not-used-empty-path",
        )
        # pytest-asyncio isn't repo-wide; use asyncio.run so this test
        # doesn't depend on it.
        import asyncio

        result = asyncio.run(client.embed(texts=[]))
        assert result == []

    def test_provider_raises_is_translated_to_typed_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A1/A5: vendor SDK exceptions MUST be translated to
        ``EmbeddingClientError`` at the boundary. Callers never see a
        ``litellm`` exception directly (per the same discipline mem0 had).
        """
        import asyncio

        async def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("simulated litellm outage")

        monkeypatch.setattr(
            "middleware.adapters.embedding.litellm_embedding_client.litellm.aembedding",
            _boom,
        )
        client = LiteLLMEmbeddingClient(
            model="text-embedding-3-small",
            dimension=REQUIRED_DIMENSION,
            api_key="sk-test-not-used",
        )
        with pytest.raises(EmbeddingClientError) as excinfo:
            asyncio.run(client.embed(texts=["hello world"]))
        # The original cause is preserved for debugging but doesn't leak past
        # the boundary type.
        assert "simulated litellm outage" in str(excinfo.value)

    def test_dimension_mismatch_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pattern 11: if the provider returns a vector of unexpected
        dimension (e.g. someone misconfigured ``EMBEDDING_DIMENSION``),
        the adapter MUST refuse rather than write a bad row to pgvector
        — pgvector's column type is fixed and the INSERT would 500
        downstream with a cryptic error.
        """
        import asyncio

        async def _wrong_dim(*args: Any, **kwargs: Any) -> Any:
            # Return a 4-dim vector while client expects 1536.
            return {"data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}]}

        monkeypatch.setattr(
            "middleware.adapters.embedding.litellm_embedding_client.litellm.aembedding",
            _wrong_dim,
        )
        client = LiteLLMEmbeddingClient(
            model="text-embedding-3-small",
            dimension=REQUIRED_DIMENSION,
            api_key="sk-test-not-used",
        )
        with pytest.raises(EmbeddingClientError) as excinfo:
            asyncio.run(client.embed(texts=["mismatched"]))
        assert "dimension" in str(excinfo.value).lower()

    def test_response_missing_data_field_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The adapter MUST refuse malformed provider payloads rather
        than silently emit empty vectors.
        """
        import asyncio

        async def _empty(*args: Any, **kwargs: Any) -> Any:
            return {}  # no 'data' field at all

        monkeypatch.setattr(
            "middleware.adapters.embedding.litellm_embedding_client.litellm.aembedding",
            _empty,
        )
        client = LiteLLMEmbeddingClient(
            model="text-embedding-3-small",
            dimension=REQUIRED_DIMENSION,
            api_key="sk-test-not-used",
        )
        with pytest.raises(EmbeddingClientError):
            asyncio.run(client.embed(texts=["malformed"]))

    def test_constructor_rejects_non_positive_dimension(self) -> None:
        """Defensive: ``dimension`` defines the pgvector column shape;
        ≤0 is a configuration bug, not a runtime concern.
        """
        with pytest.raises(ValueError):
            LiteLLMEmbeddingClient(
                model="text-embedding-3-small",
                dimension=0,
                api_key="sk-test-not-used",
            )


# ─────────────────────────────────────────────────────────────────────
# FakeEmbeddingClient — deterministic, content-free, test-only
# (used by Phase 2 backend tests + this file's contract test)
# ─────────────────────────────────────────────────────────────────────


class TestFakeEmbeddingClient:
    def test_satisfies_embedding_client_protocol(self) -> None:
        """Pattern 4 consumer-driven contract: the fake satisfies the
        same Protocol as the real adapter.
        """
        fake = FakeEmbeddingClient(dimension=REQUIRED_DIMENSION)
        assert isinstance(fake, EmbeddingClient)

    def test_dimension_round_trips(self) -> None:
        fake = FakeEmbeddingClient(dimension=384)
        assert fake.dimension == 384

    def test_deterministic_same_input_same_vector(self) -> None:
        """Pattern 5 record/replay: identical input MUST produce
        identical vectors — Phase 2 backend dedup leans on this.
        """
        import asyncio

        fake = FakeEmbeddingClient(dimension=REQUIRED_DIMENSION)
        a = asyncio.run(fake.embed(texts=["What is pgvector?"]))
        b = asyncio.run(fake.embed(texts=["What is pgvector?"]))
        assert a == b

    def test_distinct_inputs_produce_distinct_vectors(self) -> None:
        import asyncio

        fake = FakeEmbeddingClient(dimension=REQUIRED_DIMENSION)
        result = asyncio.run(fake.embed(texts=["alpha", "beta"]))
        assert len(result) == 2
        assert result[0] != result[1]
        assert len(result[0]) == REQUIRED_DIMENSION
        assert len(result[1]) == REQUIRED_DIMENSION


# ─────────────────────────────────────────────────────────────────────
# Acceptance (LAST — happy path)
# ─────────────────────────────────────────────────────────────────────


class TestLiteLLMEmbeddingClientHappyPath:
    """Pattern 4: consumer-driven contract — embed returns the dim it
    advertises, in the order it received."""

    def test_embed_returns_dimension_it_advertises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio

        async def _stub(*args: Any, **kwargs: Any) -> Any:
            inputs = kwargs.get("input") or args[1]
            return {
                "data": [
                    {"embedding": [0.001 * (i + 1)] * REQUIRED_DIMENSION}
                    for i, _ in enumerate(inputs)
                ]
            }

        monkeypatch.setattr(
            "middleware.adapters.embedding.litellm_embedding_client.litellm.aembedding",
            _stub,
        )
        client = LiteLLMEmbeddingClient(
            model="text-embedding-3-small",
            dimension=REQUIRED_DIMENSION,
            api_key="sk-test-not-used",
        )
        out = asyncio.run(client.embed(texts=["a", "b", "c"]))
        assert len(out) == 3
        assert all(len(v) == REQUIRED_DIMENSION for v in out)
        assert client.dimension == REQUIRED_DIMENSION
