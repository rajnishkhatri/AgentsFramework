"""Direct-call LLM provider adapters — the LiteLLM extension layer.

Horizontal hexagonal adapters that call a provider's REST API directly for
models LiteLLM cannot serve. Each adapter satisfies the ``LLMProvider`` port
(trust/protocols.py); ``get_direct_provider`` is the factory the LLM service
calls when a ``ModelProfile`` has ``provider="direct"``.

Mirrors services/cloud_providers/: a factory keyed by a profile attribute,
returning a port-conforming adapter. Imports only from ``trust/`` + ``services/``.
"""

from __future__ import annotations

from services.base_config import ModelProfile
from services.llm_providers.config import (
    resolve_fireworks_api_key,
    resolve_glm_api_key,
)
from services.llm_providers.fireworks_direct import FireworksDirectProvider
from services.llm_providers.glm_direct import GLMDirectProvider
from trust.exceptions import ConfigurationError, TrustProviderError
from trust.protocols import LLMProvider

__all__ = ["get_direct_provider", "GLMDirectProvider", "FireworksDirectProvider"]


def get_direct_provider(profile: ModelProfile) -> LLMProvider:
    """Return the direct-call client for a ``provider="direct"`` profile.

    Dispatch is by the model family (``profile.name``/``litellm_id`` prefix).
    An unknown direct model, or a missing key, raises a typed
    ``TrustProviderError``/``ConfigurationError`` so the factory fails loudly
    rather than handing the loop an unusable client.
    """
    name = (profile.name or profile.litellm_id or "").lower()

    # Fireworks (ADR-0019) is checked BEFORE the GLM branch on purpose: a
    # Fireworks profile is named ``<model>-fireworks`` and ``glm-5.2-fireworks``
    # matches BOTH the ``-fireworks`` suffix AND ``startswith("glm")`` — if the
    # GLM branch ran first the coach judge would silently run on Z.ai (the host
    # this ADR moves OFF because its serving stalls). Suffix-first keeps them
    # disjoint without string-munging the profile in the caller (H2).
    if name.endswith("-fireworks"):
        api_key = resolve_fireworks_api_key()
        if not api_key:
            raise ConfigurationError(
                "Fireworks direct provider requires FIREWORKS_API_KEY",
                provider="fireworks",
                operation="get_direct_provider",
            )
        return FireworksDirectProvider(api_key=api_key)

    if name.startswith("glm"):
        api_key = resolve_glm_api_key()
        if not api_key:
            raise ConfigurationError(
                "GLM direct provider requires GLM_API_KEY (or ZAI_API_KEY)",
                provider="glm",
                operation="get_direct_provider",
            )
        return GLMDirectProvider(api_key=api_key)

    raise TrustProviderError(
        f"No direct provider registered for model '{profile.name}' "
        f"(litellm_id={profile.litellm_id!r})",
        provider="unknown",
        operation="get_direct_provider",
    )
