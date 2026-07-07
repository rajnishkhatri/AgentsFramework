"""Endpoint + credential resolution for direct-call LLM providers.

Kept tiny and env-driven (no pydantic-settings needed yet): the secrets are the
GLM/Z.ai key, read from ``GLM_API_KEY`` (this repo's name) or ``ZAI_API_KEY``
(the upstream name; services/llm_config.py bridges one to the other at import),
and the Fireworks key (``FIREWORKS_API_KEY``) — the second direct host, added by
ADR-0019 to re-host GLM-5.2 off Z.ai's stalling serving layer.
"""

from __future__ import annotations

import os


def resolve_glm_api_key() -> str | None:
    """The GLM/Z.ai bearer key, or None if neither env var is set."""
    return os.environ.get("GLM_API_KEY") or os.environ.get("ZAI_API_KEY")


def resolve_fireworks_api_key() -> str | None:
    """The Fireworks AI bearer key, or None if unset (ADR-0019).

    Single upstream name — Fireworks uses ``FIREWORKS_API_KEY``. Kept a distinct
    resolver (not a merged multi-host one) so the GLM path stays byte-identical.
    """
    return os.environ.get("FIREWORKS_API_KEY")
