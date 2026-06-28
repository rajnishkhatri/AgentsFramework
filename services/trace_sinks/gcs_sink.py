"""GcsTraceSink: GCS object-per-batch sink for TrustTraceRecord events.

Tier A direct-write implementation. Uploads one JSON object per emit() call
to a GCS bucket under a date-partitioned key structure. Implements the
``TraceSink`` protocol from ``services.trace_service``.

Key layout: ``traces/{date}/{trace_id}/{event_id}.json``
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from trust.models import TrustTraceRecord

if TYPE_CHECKING:
    from google.cloud.storage import Client as StorageClient

logger = logging.getLogger("services.trace_sinks.gcs_sink")


class GcsTraceSink:
    """Direct GCS write sink for trust trace records.

    Tier A: one PutObject per event. At dev-tier volume (<1 GB/mo) this is
    effectively free and avoids the Pub/Sub complexity of Tier B.
    """

    name: str

    def __init__(
        self,
        bucket_name: str,
        *,
        client: StorageClient | None = None,
        prefix: str = "traces",
    ) -> None:
        self._bucket_name = bucket_name
        self._prefix = prefix.rstrip("/")
        self._client = client
        self.name = f"gcs:{bucket_name}/{prefix}"

    def _get_client(self) -> StorageClient:
        if self._client is None:
            from google.cloud.storage import Client

            self._client = Client()
        return self._client

    def emit(self, record: TrustTraceRecord) -> None:
        if not isinstance(record, TrustTraceRecord):
            raise TypeError(
                f"GcsTraceSink.emit requires a TrustTraceRecord, "
                f"got {type(record).__name__}"
            )
        client = self._get_client()
        bucket = client.bucket(self._bucket_name)

        date_str = record.timestamp.strftime("%Y-%m-%d")
        key = f"{self._prefix}/{date_str}/{record.trace_id}/{record.event_id}.json"

        blob = bucket.blob(key)
        blob.upload_from_string(
            record.model_dump_json(),
            content_type="application/json",
        )
        logger.debug("Wrote trace record to gs://%s/%s", self._bucket_name, key)


__all__ = ["GcsTraceSink"]
