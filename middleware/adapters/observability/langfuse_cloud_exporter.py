"""LangfuseCloudExporter -- ``TelemetryExporter`` adapter for Langfuse Cloud.

Implements ``middleware.ports.telemetry_exporter.TelemetryExporter`` using
the Langfuse Python SDK v4 observation API.

**Rule O1 (telemetry NEVER blocks):** every public method swallows
exceptions silently. A misconfigured exporter never aborts an agent run.

**SDK isolation (rule F-R2 / A1):** ``langfuse`` is imported only in
this file. Callers see the vendor-neutral Protocol return type (``None``).

**SDK pin (rule A9):** ``langfuse >= 4.0`` (declared in pyproject).

**Trace grouping:** Each ``export_event()`` creates an observation under
``trace_context={"trace_id": trace_id}`` so all events for a run share the
same Langfuse trace. ``release_trace()`` flushes buffered events for that
run (call on ``run.finished``).
"""

from __future__ import annotations

import logging
import os
from contextlib import nullcontext
from typing import Any, Literal, Mapping

logger = logging.getLogger("middleware.adapters.observability")

__all__ = ["LangfuseCloudExporter"]

ObservationType = Literal[
    "span",
    "generation",
    "agent",
    "tool",
    "chain",
    "retriever",
    "evaluator",
    "guardrail",
    "embedding",
]


def _observation_type(event_name: str) -> ObservationType:
    """Map domain-event export names to Langfuse observation types."""
    if event_name.startswith("tool."):
        return "tool"
    if event_name.startswith("llm."):
        return "generation"
    if event_name == "run.started":
        return "agent"
    return "span"


def _metadata(attributes: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Coerce attributes to Langfuse v4 metadata (dict[str, str], max 200 chars)."""
    if not attributes:
        return None
    out: dict[str, str] = {}
    for key, value in attributes.items():
        if value is None:
            continue
        text = str(value)
        if len(text) > 200:
            text = text[:200]
        out[str(key)] = text
    return out or None


class LangfuseCloudExporter:
    """Thin wrapper around the Langfuse SDK v4 that fails silently.

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
        self._started_traces: set[str] = set()

    @property
    def active_trace_count(self) -> int:
        """Number of in-flight trace IDs not yet released."""
        return len(self._started_traces)

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
            from langfuse import propagate_attributes

            attrs = dict(attributes) if attributes else {}
            propagate_kwargs: dict[str, Any] = {}

            subject = attrs.get("subject")
            if subject is not None:
                propagate_kwargs["user_id"] = str(subject)[:200]

            thread_id = attrs.get("thread_id")
            if thread_id is not None:
                propagate_kwargs["session_id"] = str(thread_id)[:200]

            if trace_id not in self._started_traces:
                propagate_kwargs.setdefault(
                    "trace_name", f"agent-run-{trace_id[:12]}"
                )
                self._started_traces.add(trace_id)

            trace_context = {"trace_id": trace_id}
            ctx = (
                propagate_attributes(**propagate_kwargs)
                if propagate_kwargs
                else nullcontext()
            )

            with ctx:
                observation = client.start_observation(
                    trace_context=trace_context,
                    name=name,
                    as_type=_observation_type(name),
                    input=attrs or None,
                    metadata=_metadata(attrs),
                )
                observation.end()
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
            self._started_traces.discard(trace_id)
            client = self._client()
            if client is not None:
                client.flush()
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
            if hasattr(client, "shutdown"):
                client.shutdown()
        except Exception as exc:
            logger.debug(
                "langfuse flush swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )
