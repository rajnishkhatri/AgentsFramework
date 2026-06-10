#!/usr/bin/env python3
"""Real-SDK adapter implementing the ``LangfuseDatasetClient`` Protocol.

This is the production wrapper that :class:`InMemoryLangfuseDatasetClient`
(``services/governance/goaljudge_goldset_dataset.py``) was designed against.
The wrapper lives in ``scripts/`` rather than ``services/governance/`` to keep
the governance module free of the Langfuse SDK / network surface — the
governance module owns shape + invariants, this module owns provider I/O.

Authentication is via environment:

    LANGFUSE_PUBLIC_KEY  required
    LANGFUSE_SECRET_KEY  required
    LANGFUSE_HOST        optional (default: https://cloud.langfuse.com)

The Stage-5 plan calls out the **EU** host explicitly — past sessions wasted
debugging time on a stray ``us.cloud.langfuse.com`` lookup that returned 502.
The default here matches the rest of the codebase.

Usage::

    from scripts.langfuse_dataset_client import build_real_langfuse_dataset_client
    from services.governance.goaljudge_goldset_dataset import GoalJudgeGoldsetRepository

    repo = GoalJudgeGoldsetRepository(build_real_langfuse_dataset_client())
    repo.upsert_many(items)

NO ``langgraph`` / ``langchain`` imports (AGENTS.md invariant #4).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langfuse import Langfuse

logger = logging.getLogger("scripts.langfuse_dataset_client")

DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com"


class RealLangfuseDatasetClient:
    """Thin pass-through to the Langfuse SDK's dataset CRUD.

    Implements the ``LangfuseDatasetClient`` Protocol defined in
    ``services.governance.goaljudge_goldset_dataset``. The Protocol is the
    contract; this class is the implementation. The in-memory test double
    (``InMemoryLangfuseDatasetClient``) implements the same Protocol so the
    repository code is identical against either.

    Constructor injection of the SDK client allows tests to swap in a recorded
    fake without monkeypatching the SDK itself.
    """

    def __init__(self, client: Langfuse) -> None:
        self._client = client

    def create_dataset(self, *, name: str, **kwargs: Any) -> dict[str, Any]:
        """Idempotent-from-the-caller's-perspective create.

        The Langfuse SDK returns a typed ``Dataset`` object; we coerce to a
        plain dict so the Protocol's return shape (``dict[str, Any]``) holds.
        """
        result = self._client.create_dataset(name=name, **kwargs)
        return _to_dict(result, fallback_name=name)

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input: dict[str, Any],
        id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create one labeled item under ``dataset_name``."""
        result = self._client.create_dataset_item(
            dataset_name=dataset_name,
            input=input,
            id=id,
            metadata=metadata,
            **kwargs,
        )
        return _to_dict(result)


def build_real_langfuse_dataset_client(
    *,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
) -> RealLangfuseDatasetClient:
    """Construct the SDK client from env (with optional overrides).

    Raises ``RuntimeError`` (not ``KeyError``) when required env is missing so
    the assemble script can produce a single readable error.
    """
    pk = public_key or os.environ.get("LANGFUSE_PUBLIC_KEY")
    sk = secret_key or os.environ.get("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        raise RuntimeError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set to "
            "construct a real Langfuse dataset client"
        )
    resolved_host = host or os.environ.get("LANGFUSE_HOST", DEFAULT_LANGFUSE_HOST)
    sdk = Langfuse(public_key=pk, secret_key=sk, host=resolved_host)
    logger.debug("constructed real Langfuse dataset client host=%s", resolved_host)
    return RealLangfuseDatasetClient(sdk)


def _to_dict(result: Any, *, fallback_name: str | None = None) -> dict[str, Any]:
    """Coerce an SDK Dataset / DatasetItem (pydantic-typed) to plain dict.

    The SDK objects expose ``model_dump`` (pydantic v2) on recent versions.
    Fall back to attribute scrape so the wrapper is resilient to minor SDK
    version drift — the repository only needs ``name``/``id``-shaped fields
    from this dict, not the full payload.
    """
    if isinstance(result, dict):
        return result
    dump = getattr(result, "model_dump", None)
    if callable(dump):
        try:
            return dict(dump())
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(result, "__dict__"):
        return {k: v for k, v in vars(result).items() if not k.startswith("_")}
    return {"name": fallback_name} if fallback_name else {}
