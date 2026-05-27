"""LangfuseCloudExporter -- ``TelemetryExporter`` adapter for Langfuse Cloud.

Implements ``middleware.ports.telemetry_exporter.TelemetryExporter`` using
the ``langfuse`` SDK.

**Rule O1 (telemetry NEVER blocks):** every public method swallows
exceptions silently. A misconfigured exporter never aborts an agent run.

**SDK isolation (rule F-R2 / A1):** ``langfuse`` is imported only in
this file. Callers see the vendor-neutral Protocol return type (``None``).

**SDK pin (rule A9):** ``langfuse >= 3.0`` (declared in pyproject).

**Trace grouping (Phase 1):** On first ``export_event()`` for a given
``trace_id``, a Langfuse trace is opened with ``id=trace_id``. Subsequent
calls create child spans under that trace. The bridge calls
``release_trace()`` on ``run.finished`` to free the handle.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

logger = logging.getLogger("middleware.adapters.observability")

__all__ = ["LangfuseCloudExporter"]


class LangfuseCloudExporter:
    """Thin wrapper around the ``langfuse`` SDK that fails silently.

    Args:
        public_key: Langfuse project public key (``LANGFUSE_PUBLIC_KEY``).
        secret_key: Langfuse project secret key (``LANGFUSE_SECRET_KEY``).
        host: Langfuse base URL (``LANGFUSE_HOST``).
        sdk_client: optional pre-built SDK client for tests.
    """

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str = "https://cloud.langfuse.com",
        sdk_client: Any | None = None,
    ) -> None:
        if not public_key or not secret_key:
            raise ValueError(
                "LangfuseCloudExporter requires both public_key and secret_key"
            )
        self._public_key = public_key
        self._secret_key = secret_key
        self._host = host
        self._sdk_client = sdk_client
        self._enabled = os.environ.get("LANGFUSE_ENABLED", "true").lower() != "false"
        self._traces: dict[str, Any] = {}

    def _client(self) -> Any | None:
        if not self._enabled:
            return None
        if self._sdk_client is not None:
            return self._sdk_client
        try:
            from langfuse import Langfuse

            self._sdk_client = Langfuse(
                public_key=self._public_key,
                secret_key=self._secret_key,
                host=self._host,
            )
            return self._sdk_client
        except Exception as exc:
            logger.warning(
                "langfuse client init failed (telemetry disabled): %s: %s",
                type(exc).__name__,
                exc,
            )
            return None

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        if not self._enabled:
            return
        client = self._client()
        if client is None:
            return
        try:
            trace_handle = self._traces.get(trace_id)
            if trace_handle is None:
                trace_handle = client.trace(id=trace_id, name=trace_id)
                self._traces[trace_id] = trace_handle
            span = trace_handle.span(
                name=name,
                input=dict(attributes) if attributes else None,
            )
            span.end()
        except Exception as exc:
            logger.debug(
                "langfuse export_event swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )

    def release_trace(self, trace_id: str) -> None:
        if not self._enabled:
            return
        try:
            self._traces.pop(trace_id, None)
        except Exception as exc:
            logger.debug(
                "langfuse release_trace swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )

    def shutdown(self) -> None:
        if not self._enabled:
            return
        client = self._client()
        if client is None:
            return
        try:
            client.flush()
        except Exception as exc:
            logger.debug(
                "langfuse flush swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )
