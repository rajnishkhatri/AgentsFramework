"""Env-driven LLM selection for the reusable CodeReviewer wrapper.

Loads settings from the project-root ``.env`` via ``pydantic-settings``
(already in ``pyproject.toml``; no new dependency) and maps a LiteLLM
model id to a :class:`services.base_config.ModelProfile`.

Usage::

    profile = reviewer_profile_from_env()                     # MODEL_NAME
    judge   = reviewer_profile_from_env("MODEL_NAME_JUDGE")   # MODEL_NAME_JUDGE

If the requested env var is unset or contains a model id we do not
know about, we fall back to :func:`services.base_config.default_fast_profile`
so callers never crash on a missing configuration -- a warning is logged
so the gap is auditable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from services.base_config import ModelProfile, default_fast_profile

logger = logging.getLogger("meta.CodeReviewerAgentTest.env_settings")

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


class EnvSettings(BaseSettings):
    """Typed view over the environment variables this package consumes.

    Field names match the lower-cased env var names (``MODEL_NAME`` ->
    ``model_name``). Anything else in ``.env`` is silently ignored so we
    do not collide with unrelated keys (LangSmith, Pinecone, etc.).
    """

    model_name: str | None = None
    model_name_judge: str | None = None
    model_name_reviewer: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    together_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(AGENT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


# ── Built-in model registry ────────────────────────────────────────
#
# Maps a LiteLLM id (the value users put in MODEL_NAME) to the
# tier/context/cost metadata we need to construct a ModelProfile. Add
# new ids here when you want first-class cost reporting; unknown ids
# still work via the defensive fallback below.

_MODEL_REGISTRY: dict[str, dict[str, float | int | str]] = {
    "anthropic/claude-3-haiku-20240307": {
        "name": "claude-3-haiku",
        "tier": "fast",
        "context_window": 200_000,
        "cost_per_1k_input": 0.00025,
        "cost_per_1k_output": 0.00125,
    },
    "anthropic/claude-3-sonnet-20240229": {
        "name": "claude-3-sonnet",
        "tier": "balanced",
        "context_window": 200_000,
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
    },
    "openai/gpt-4o-mini": {
        "name": "gpt-4o-mini",
        "tier": "fast",
        "context_window": 128_000,
        "cost_per_1k_input": 0.00015,
        "cost_per_1k_output": 0.0006,
    },
    "openai/gpt-4.1-nano": {
        "name": "gpt-4.1-nano",
        "tier": "fast",
        "context_window": 128_000,
        "cost_per_1k_input": 0.00010,
        "cost_per_1k_output": 0.00040,
    },
    "openai/gpt-4o": {
        "name": "gpt-4o",
        "tier": "balanced",
        "context_window": 128_000,
        "cost_per_1k_input": 0.0025,
        "cost_per_1k_output": 0.01,
    },
    "together_ai/mistralai/Mixtral-8x7B-Instruct-v0.1": {
        "name": "mixtral-8x7b",
        "tier": "balanced",
        "context_window": 32_768,
        "cost_per_1k_input": 0.0006,
        "cost_per_1k_output": 0.0006,
    },
}


def _profile_from_litellm_id(litellm_id: str) -> ModelProfile:
    """Map a LiteLLM id to a :class:`ModelProfile`.

    Unknown ids return a defensive fallback profile (so we never crash)
    and emit a single warning log so the gap is observable.
    """
    spec = _MODEL_REGISTRY.get(litellm_id)
    if spec is None:
        logger.warning(
            "Unknown LiteLLM id %r -- falling back to a defensive profile. "
            "Add it to _MODEL_REGISTRY for first-class cost reporting.",
            litellm_id,
        )
        return ModelProfile(
            name=litellm_id.split("/")[-1] or litellm_id,
            litellm_id=litellm_id,
            tier="unknown",
            context_window=8_192,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )

    return ModelProfile(
        name=str(spec["name"]),
        litellm_id=litellm_id,
        tier=str(spec["tier"]),
        context_window=int(spec["context_window"]),
        cost_per_1k_input=float(spec["cost_per_1k_input"]),
        cost_per_1k_output=float(spec["cost_per_1k_output"]),
    )


def reviewer_profile_from_env(env_var: str = "MODEL_NAME") -> ModelProfile:
    """Read the named env var from ``.env`` + os.environ and build a :class:`ModelProfile`.

    ``env_var`` lets callers pick between ``MODEL_NAME``,
    ``MODEL_NAME_JUDGE``, and ``MODEL_NAME_REVIEWER`` (all already used
    in ``.env``). Comparison is case-insensitive.

    Returns :func:`default_fast_profile` if the env var is absent or
    empty -- never raises.
    """
    settings = EnvSettings()
    field_name = env_var.lower()
    litellm_id = getattr(settings, field_name, None)

    if not litellm_id:
        logger.info(
            "%s is unset; falling back to default_fast_profile().", env_var
        )
        return default_fast_profile()

    return _profile_from_litellm_id(litellm_id)
