"""Endpoint + credential resolution for direct-call LLM providers.

Kept tiny and env-driven (no pydantic-settings needed yet): the only secret is
the GLM/Z.ai key, read from ``GLM_API_KEY`` (this repo's name) or ``ZAI_API_KEY``
(the upstream name; services/llm_config.py bridges one to the other at import).
"""

from __future__ import annotations

import os


def resolve_glm_api_key() -> str | None:
    """The GLM/Z.ai bearer key, or None if neither env var is set."""
    return os.environ.get("GLM_API_KEY") or os.environ.get("ZAI_API_KEY")
