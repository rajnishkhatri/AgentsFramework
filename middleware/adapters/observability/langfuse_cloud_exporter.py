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


# Phase 4 (E3): metadata is a small allowlist of join/filter keys. Bulky or
# duplicative fields (input_text, details, args_json, result, integrity_hash,
# timestamps) ride ONLY on the observation ``input`` — never copied into
# metadata, which previously doubled the payload of every observation.
_METADATA_ALLOWLIST = frozenset(
    {"step", "workflow_id", "event_id", "tool_name", "model", "subject"}
)


def _metadata(attributes: Mapping[str, Any] | None) -> dict[str, str] | None:
    """Coerce allowlisted attributes to Langfuse v4 metadata (dict[str, str],
    max 200 chars)."""
    if not attributes:
        return None
    out: dict[str, str] = {}
    for key, value in attributes.items():
        if key not in _METADATA_ALLOWLIST or value is None:
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
        # I6: one live SDK step span per ``(trace_id, logical_step_key)``.
        # Children of a step nest under it via the SDK's real nesting API; the
        # span stays open until ``release_trace`` ends it (carrying the run's
        # lifetime). Keyed by the publisher's synthetic step key, never an SDK id.
        self._step_spans: dict[tuple[str, str], Any] = {}
        # I8: per-trace set of BlackBox event_ids already exported. The relay is
        # at-least-once (``run_forever`` + ``drain_workflow`` can read the same
        # byte offset under a crash/race) and Langfuse SDK v4 cannot upsert on a
        # caller-supplied observation id, so duplicate ``task.completed`` /
        # ``step.executed`` observations surface with identical metadata. This
        # guard drops the second export. Cleared per trace in ``release_trace``.
        self._seen_events: dict[str, set[str]] = {}

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

            # E11: the Langfuse SDK builds its OTel Resource from
            # ``OTEL_SERVICE_NAME``; when unset, every span surfaces
            # ``service.name: unknown_service`` (which breaks environment
            # filtering in the trace view). Seed a sane default *before*
            # constructing the client so the resource picks it up, but let an
            # operator-supplied value always win (deploy config / CI).
            os.environ.setdefault("OTEL_SERVICE_NAME", "agent-runtime")

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
    ) -> bool:
        """Export a single observation.

        Returns ``True`` when the event was handed to the SDK, ``False`` when a
        genuine export error was swallowed (rule O1 — telemetry never blocks, so
        the caller decides whether to dead-letter). An intentional no-op
        (kill-switch disabled or client unavailable) returns ``True`` so the
        relay does not dead-letter events it was never meant to publish.
        """
        if not self._enabled:
            return True
        client = self._client()
        if client is None:
            return True
        try:
            from langfuse import propagate_attributes

            attrs = dict(attributes) if attributes else {}

            # BlackBox relay hints — extract before building metadata so they
            # don't leak into the Langfuse metadata blob.
            bb_observation_id = attrs.pop("__bb_observation_id", None)  # not settable in SDK v4

            # I8: idempotency guard. Dedupe on the BlackBox ``event_id`` (the
            # relay also surfaces it as ``__bb_observation_id``). A repeat for an
            # already-exported event is a no-op success (return True) so the
            # at-least-once relay does not dead-letter it. We only mark an event
            # seen *after* a successful export so a genuine failure can retry.
            dedup_id = attrs.get("event_id") or bb_observation_id
            if dedup_id is not None and str(dedup_id) in self._seen_events.get(
                trace_id, set()
            ):
                return True

            bb_observation_type = attrs.pop("__bb_observation_type", None)
            bb_level = attrs.pop("__bb_level", None)
            bb_output = attrs.pop("__output", None)
            bb_parent_observation_id = attrs.pop("__bb_parent_observation_id", None)
            bb_model = attrs.pop("__bb_model", None)
            bb_usage = attrs.pop("__bb_usage", None)
            bb_cost = attrs.pop("__bb_cost", None)

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

            obs_type = bb_observation_type or _observation_type(name)
            obs_kwargs: dict[str, Any] = {
                "name": name,
                "as_type": obs_type,
                "input": attrs or None,
                "output": bb_output,
                "metadata": _metadata(attrs),
            }
            if bb_model is not None:
                obs_kwargs["model"] = bb_model
            # SDK v4 native generation fields are ``usage_details`` /
            # ``cost_details`` (a dict). The publisher (I5) emits ``usage`` as
            # ``{input,output,total}`` and ``cost`` as a float; normalise here.
            if bb_usage is not None:
                obs_kwargs["usage_details"] = bb_usage
            if bb_cost is not None:
                obs_kwargs["cost_details"] = (
                    dict(bb_cost)
                    if isinstance(bb_cost, Mapping)
                    else {"total": float(bb_cost)}
                )
            # NOTE: Langfuse SDK v4 ``start_observation()`` does not accept an
            # ``id`` kwarg (observation IDs are auto-generated OTel span IDs).
            # ``__bb_observation_id`` is popped above so it never reaches the
            # metadata blob; idempotency is enforced by the relay's byte-offset
            # outbox, not by a caller-supplied observation id.
            if bb_level is not None and bb_level != "DEFAULT":
                obs_kwargs["level"] = bb_level

            with ctx:
                if bb_parent_observation_id is not None:
                    # I6: translate the publisher's logical step key into a real
                    # per-(trace, step) span and nest this child under it using
                    # the SDK's real nesting API (``parent.start_observation``),
                    # never the synthetic ``workflow:step:N`` string.
                    step_span = self._get_or_create_step_span(
                        client, trace_id, str(bb_parent_observation_id)
                    )
                    child = step_span.start_observation(**obs_kwargs)
                    child.end()
                else:
                    observation = client.start_observation(
                        trace_context=trace_context, **obs_kwargs
                    )
                    observation.end()
            # I8: mark exported only after the SDK accepted it.
            if dedup_id is not None:
                self._seen_events.setdefault(trace_id, set()).add(str(dedup_id))
            return True
        except Exception as exc:
            logger.warning(
                "langfuse export_event swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )
            return False

    def _get_or_create_step_span(
        self, client: Any, trace_id: str, parent_key: str
    ) -> Any:
        """Return the live step span for ``(trace_id, parent_key)``, creating it once.

        ``parent_key`` is the publisher's synthetic ``workflow:step:N`` key. The
        span itself is created with the SDK's auto-generated id and kept open
        until :meth:`release_trace` ends it.
        """
        key = (trace_id, parent_key)
        span = self._step_spans.get(key)
        if span is None:
            step_label = parent_key.rsplit(":", 1)[-1]
            span = client.start_observation(
                trace_context={"trace_id": trace_id},
                name=f"step.{step_label}",
                as_type="span",
            )
            self._step_spans[key] = span
        return span

    def release_trace(self, trace_id: str) -> None:
        if not self._enabled:
            return
        try:
            self._started_traces.discard(trace_id)
            # I8: drop the per-trace idempotency set so a re-used trace_id starts
            # fresh (release_trace is the end-of-run boundary).
            self._seen_events.pop(trace_id, None)
            # I6: close any open step spans for this trace BEFORE flush so the
            # tree closes cleanly and each step carries the run's lifetime.
            for key in [k for k in self._step_spans if k[0] == trace_id]:
                span = self._step_spans.pop(key, None)
                if span is None:
                    continue
                try:
                    span.end()
                except Exception as exc:
                    logger.warning(
                        "langfuse step span end swallowed: %s: %s",
                        type(exc).__name__,
                        exc,
                    )
            client = self._client()
            if client is not None:
                client.flush()
        except Exception as exc:
            logger.warning(
                "langfuse release_trace swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )

    def create_dataset_item(
        self,
        *,
        dataset_name: str,
        input_data: dict[str, Any],
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._enabled:
            return
        client = self._client()
        if client is None:
            return
        try:
            # SDK v4 does NOT auto-create the dataset on first item insert; an
            # unknown dataset_name yields a 404. ``create_dataset`` is an upsert
            # (idempotent by name), so ensure the dataset exists before adding
            # the item.
            client.create_dataset(name=dataset_name)

            kwargs: dict[str, Any] = {
                "dataset_name": dataset_name,
                "input": input_data,
            }
            if item_id is not None:
                kwargs["id"] = item_id
            if metadata is not None:
                kwargs["metadata"] = metadata
            client.create_dataset_item(**kwargs)
        except Exception as exc:
            logger.warning(
                "langfuse create_dataset_item swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )

    def score_trace(
        self,
        *,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        if not self._enabled:
            return
        client = self._client()
        if client is None:
            return
        try:
            kwargs: dict[str, Any] = {
                "trace_id": trace_id,
                "name": name,
                "value": value,
            }
            if comment is not None:
                kwargs["comment"] = comment
            # SDK v4 renamed trace scoring: ``Langfuse.score`` no longer exists;
            # the API is ``create_score`` (the kwargs above match its signature).
            client.create_score(**kwargs)
        except Exception as exc:
            logger.warning(
                "langfuse score_trace swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )

    def flush(self) -> None:
        if not self._enabled:
            return
        client = self._client()
        if client is None:
            return
        try:
            client.flush()
        except Exception as exc:
            logger.warning(
                "langfuse flush swallowed: %s: %s",
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
            logger.warning(
                "langfuse flush swallowed: %s: %s",
                type(exc).__name__,
                exc,
            )
