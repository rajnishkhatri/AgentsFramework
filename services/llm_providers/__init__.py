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
from services.llm_providers.config import resolve_glm_api_key
from services.llm_providers.glm_direct import GLMDirectProvider
from trust.exceptions import ConfigurationError, TrustProviderError
from trust.protocols import LLMProvider

__all__ = ["get_direct_provider", "GLMDirectProvider"]


def get_direct_provider(profile: ModelProfile) -> LLMProvider:
    """Return the direct-call client for a ``provider="direct"`` profile.

    Dispatch is by the model family (``profile.name``/``litellm_id`` prefix).
    An unknown direct model, or a missing key, raises a typed
    ``TrustProviderError`` so the factory fails loudly rather than handing the
    loop an unusable client.
    """
    name = (profile.name or profile.litellm_id or "").lower()
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
