"""PubSubTraceSink: Pub/Sub streaming sink for TrustTraceRecord events.

Tier B+ implementation. Publishes each record as a JSON message to a
Cloud Pub/Sub topic. Implements the ``TraceSink`` protocol from
``services.trace_service``.

Wire now, activate later — at Tier A the composition root selects
``GcsTraceSink`` instead.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trust.models import TrustTraceRecord

if TYPE_CHECKING:
    from google.cloud.pubsub_v1 import PublisherClient

logger = logging.getLogger("services.trace_sinks.pubsub_sink")


class PubSubTraceSink:
    """Pub/Sub publisher sink for trust trace records.

    Tier B: decouples trace emission from storage via Pub/Sub topic.
    A subscription (e.g., GCS or BigQuery) handles persistence downstream.
    """

    name: str

    def __init__(
        self,
        topic_path: str,
        *,
        publisher: PublisherClient | None = None,
    ) -> None:
        """Initialize with a fully-qualified topic path.

        Args:
            topic_path: ``projects/{project}/topics/{topic}``
            publisher: Optional injected publisher client (for testing).
        """
        self._topic_path = topic_path
        self._publisher = publisher
        self.name = f"pubsub:{topic_path.split('/')[-1]}"

    def _get_publisher(self) -> PublisherClient:
        if self._publisher is None:
            from google.cloud.pubsub_v1 import PublisherClient

            self._publisher = PublisherClient()
        return self._publisher

    def emit(self, record: TrustTraceRecord) -> None:
        if not isinstance(record, TrustTraceRecord):
            raise TypeError(
                f"PubSubTraceSink.emit requires a TrustTraceRecord, "
                f"got {type(record).__name__}"
            )
        publisher = self._get_publisher()
        data = record.model_dump_json().encode("utf-8")
        future = publisher.publish(
            self._topic_path,
            data,
            trace_id=record.trace_id,
            event_type=record.event_type,
            agent_id=record.agent_id,
        )
        logger.debug(
            "Published trace record to %s (message_id=%s)",
            self._topic_path,
            future.result(),
        )


__all__ = ["PubSubTraceSink"]
