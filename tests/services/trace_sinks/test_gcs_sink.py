"""Tests for GcsTraceSink.

Failure paths first (TAP-4):
  - Non-TrustTraceRecord → TypeError
  - GCS upload failure → propagates exception
  - Happy path: emit writes correct key structure with JSON body
  - Implements TraceSink protocol
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from services.trace_sinks.gcs_sink import GcsTraceSink
from trust.models import TrustTraceRecord


def _make_record(
    trace_id: str = "t-1",
    event_id: str | None = None,
    ts: datetime | None = None,
) -> TrustTraceRecord:
    return TrustTraceRecord(
        event_id=event_id or str(uuid.uuid4()),
        timestamp=ts or datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC),
        trace_id=trace_id,
        agent_id="test-agent",
        layer="L4",
        event_type="test_event",
        details={"key": "value"},
        outcome="pass",
    )


class TestGcsTraceSinkFailurePaths:
    def test_non_trust_trace_record_raises_type_error(self) -> None:
        mock_client = MagicMock()
        sink = GcsTraceSink("test-bucket", client=mock_client)
        with pytest.raises(TypeError, match="TrustTraceRecord"):
            sink.emit("not a record")  # type: ignore[arg-type]

    def test_gcs_upload_failure_propagates(self) -> None:
        mock_client = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string.side_effect = RuntimeError("upload failed")
        mock_client.bucket.return_value.blob.return_value = mock_blob

        sink = GcsTraceSink("test-bucket", client=mock_client)
        record = _make_record()

        with pytest.raises(RuntimeError, match="upload failed"):
            sink.emit(record)


class TestGcsTraceSinkHappyPath:
    def test_emit_writes_correct_key_and_body(self) -> None:
        mock_client = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        sink = GcsTraceSink("my-traces-bucket", client=mock_client, prefix="traces")

        event_id = "evt-123"
        ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=UTC)
        record = _make_record(trace_id="trace-abc", event_id=event_id, ts=ts)
        sink.emit(record)

        expected_key = f"traces/2025-06-15/trace-abc/{event_id}.json"
        mock_client.bucket.assert_called_once_with("my-traces-bucket")
        mock_client.bucket.return_value.blob.assert_called_once_with(expected_key)
        mock_blob.upload_from_string.assert_called_once()

        call_args = mock_blob.upload_from_string.call_args
        uploaded_json = call_args[0][0]
        assert json.loads(uploaded_json)["trace_id"] == "trace-abc"
        assert call_args[1]["content_type"] == "application/json"

    def test_implements_trace_sink_protocol(self) -> None:
        from services.trace_service import TraceSink

        mock_client = MagicMock()
        sink = GcsTraceSink("bucket", client=mock_client)
        assert isinstance(sink, TraceSink)

    def test_custom_prefix(self) -> None:
        mock_client = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value.blob.return_value = mock_blob

        sink = GcsTraceSink("bucket", client=mock_client, prefix="custom/path/")

        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        record = _make_record(trace_id="t-x", event_id="e-1", ts=ts)
        sink.emit(record)

        blob_key = mock_client.bucket.return_value.blob.call_args[0][0]
        assert blob_key.startswith("custom/path/")

    def test_lazy_client_initialization(self) -> None:
        with patch("services.trace_sinks.gcs_sink.GcsTraceSink._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            mock_client.bucket.return_value.blob.return_value = MagicMock()

            sink = GcsTraceSink("bucket")
            record = _make_record()
            sink.emit(record)

            mock_get.assert_called_once()

    def test_name_attribute(self) -> None:
        mock_client = MagicMock()
        sink = GcsTraceSink("my-bucket", client=mock_client, prefix="traces")
        assert sink.name == "gcs:my-bucket/traces"
