"""Tests for PubSubTraceSink.

Failure paths first (TAP-4):
  - Non-TrustTraceRecord → TypeError
  - Publish failure → propagates exception
  - Happy path: emit publishes correct data with attributes
  - Implements TraceSink protocol
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from services.trace_sinks.pubsub_sink import PubSubTraceSink
from trust.models import TrustTraceRecord


def _make_record(trace_id: str = "t-1") -> TrustTraceRecord:
    return TrustTraceRecord(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        trace_id=trace_id,
        agent_id="test-agent",
        layer="L4",
        event_type="test_event",
        details={"key": "value"},
        outcome="pass",
    )


class TestPubSubTraceSinkFailurePaths:
    def test_non_trust_trace_record_raises_type_error(self) -> None:
        mock_publisher = MagicMock()
        sink = PubSubTraceSink(
            "projects/my-proj/topics/traces", publisher=mock_publisher
        )
        with pytest.raises(TypeError, match="TrustTraceRecord"):
            sink.emit("not a record")  # type: ignore[arg-type]

    def test_publish_failure_propagates(self) -> None:
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.side_effect = RuntimeError("publish failed")
        mock_publisher.publish.return_value = mock_future

        sink = PubSubTraceSink(
            "projects/my-proj/topics/traces", publisher=mock_publisher
        )
        record = _make_record()

        with pytest.raises(RuntimeError, match="publish failed"):
            sink.emit(record)


class TestPubSubTraceSinkHappyPath:
    def test_emit_publishes_correct_data_and_attributes(self) -> None:
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "msg-id-123"
        mock_publisher.publish.return_value = mock_future

        topic = "projects/my-proj/topics/trust-traces"
        sink = PubSubTraceSink(topic, publisher=mock_publisher)

        record = _make_record(trace_id="trace-xyz")
        sink.emit(record)

        mock_publisher.publish.assert_called_once()
        call_args = mock_publisher.publish.call_args

        assert call_args[0][0] == topic
        published_data = call_args[0][1]
        parsed = json.loads(published_data.decode("utf-8"))
        assert parsed["trace_id"] == "trace-xyz"

        assert call_args[1]["trace_id"] == "trace-xyz"
        assert call_args[1]["event_type"] == "test_event"
        assert call_args[1]["agent_id"] == "test-agent"

    def test_implements_trace_sink_protocol(self) -> None:
        from services.trace_service import TraceSink

        mock_publisher = MagicMock()
        sink = PubSubTraceSink("projects/p/topics/t", publisher=mock_publisher)
        assert isinstance(sink, TraceSink)

    def test_name_attribute(self) -> None:
        mock_publisher = MagicMock()
        sink = PubSubTraceSink(
            "projects/my-proj/topics/trust-traces", publisher=mock_publisher
        )
        assert sink.name == "pubsub:trust-traces"

    def test_lazy_publisher_initialization(self) -> None:
        with patch(
            "services.trace_sinks.pubsub_sink.PubSubTraceSink._get_publisher"
        ) as mock_get:
            mock_publisher = MagicMock()
            mock_future = MagicMock()
            mock_future.result.return_value = "msg-1"
            mock_publisher.publish.return_value = mock_future
            mock_get.return_value = mock_publisher

            sink = PubSubTraceSink("projects/p/topics/t")
            record = _make_record()
            sink.emit(record)

            mock_get.assert_called_once()
