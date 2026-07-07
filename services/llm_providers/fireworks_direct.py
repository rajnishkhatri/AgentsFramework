"""Fireworks AI direct-call provider — the second ``provider="direct"`` host.

ADR-0019: GLM-5.2 clears the coach leakage judge's quality bar but Z.ai's
serving layer stalls (>180s hangs on random rows) break the FR-9 temp-0
zero-flip requirement — a serving problem, not the model. Fireworks re-hosts the
same open weights on a reliable inference host (dedicated endpoints for temp-0
determinism; grammar-constrained JSON available).

Fireworks exposes the **identical** OpenAI-compatible ``/chat/completions``
surface as Z.ai, so this adapter is a thin subclass of ``GLMDirectProvider``
that only changes the base URL and the error-attribution label — the proven
request/parse path (thinking-block stripping, tool-call mapping, usage
normalization) is inherited verbatim. No caller outside this package learns the
Fireworks base URL (H2); the wire model id (``accounts/fireworks/models/<m>``)
rides the profile's ``litellm_id`` and is passed to ``acompletion`` verbatim.

Hexagonal adapter (Horizontal layer): satisfies the ``LLMProvider`` port from the
Trust Foundation; imports only from ``trust/`` + stdlib + httpx (via the base).
"""

from __future__ import annotations

from services.llm_providers.glm_direct import GLMDirectProvider

# Fireworks OpenAI-compatible inference endpoint.
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"


class FireworksDirectProvider(GLMDirectProvider):
    """Direct REST client for Fireworks-hosted models. Satisfies ``LLMProvider``.

    Inherits the OpenAI-compatible request/parse path from ``GLMDirectProvider``;
    overrides only the base URL default and the error label so a Fireworks
    failure is attributed to ``fireworks`` (not ``glm``) in logs.
    """

    provider_label = "fireworks"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = FIREWORKS_BASE_URL,
        client=None,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(
            api_key=api_key, base_url=base_url, client=client, timeout=timeout
        )
