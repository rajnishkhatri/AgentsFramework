"""L2 tests for LangfuseCloudExporter — contract-driven TDD.

Tests the hardened exporter (Phase 1 of Langfuse GCP Integration plan):
  - Trace grouping: two export_event() calls with same trace_id → one trace, two children
  - Kill switch: LANGFUSE_ENABLED=false makes all methods no-ops
  - release_trace(): clears in-memory handle so next call opens a new trace
  - Init failure: logs WARNING, returns None, never raises
  - shutdown: calls flush on SDK client

Layer: L2 (Reproducible Reality)
Strategy: Contract-driven TDD with mock SDK client
Anti-patterns avoided: Tautological (no reimplementation), Mock Addiction (single mock of SDK boundary)
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from middleware.adapters.observability.langfuse_cloud_exporter import (
    LangfuseCloudExporter,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


class FakeLangfuseClient:
    """In-memory stand-in for the Langfuse SDK client.

    Tracks trace creation and span generation calls to verify
    the exporter's trace-grouping contract without hitting real APIs.
    """

    def __init__(self) -> None:
        self.traces: dict[str, dict] = {}
        self.spans: list[dict] = []
        self.flushed = False

    def trace(self, *, id: str, name: str | None = None, **kwargs) -> "FakeTrace":
        self.traces[id] = {"id": id, "name": name, **kwargs}
        return FakeTrace(trace_id=id, client=self)

    def flush(self) -> None:
        self.flushed = True


class FakeTrace:
    """Fake trace handle returned by FakeLangfuseClient.trace()."""

    def __init__(self, trace_id: str, client: FakeLangfuseClient) -> None:
        self.trace_id = trace_id
        self._client = client

    def span(self, *, name: str, input: dict | None = None, **kwargs) -> "FakeSpan":
        span_data = {"trace_id": self.trace_id, "name": name, "input": input, **kwargs}
        self._client.spans.append(span_data)
        return FakeSpan(span_data)


class FakeSpan:
    """Fake span returned by FakeTrace.span()."""

    def __init__(self, data: dict) -> None:
        self.data = data

    def end(self) -> None:
        pass


@pytest.fixture
def fake_client() -> FakeLangfuseClient:
    return FakeLangfuseClient()


@pytest.fixture
def exporter(fake_client: FakeLangfuseClient) -> LangfuseCloudExporter:
    return LangfuseCloudExporter(
        public_key="pk-test",
        secret_key="sk-test",
        host="https://cloud.langfuse.com",
        sdk_client=fake_client,
    )


# ─────────────────────────────────────────────────────────────────────
# Trace Grouping Contract
# ─────────────────────────────────────────────────────────────────────


class TestTraceGrouping:
    """Two export_event() calls with same trace_id produce one trace with two children."""

    def test_first_export_creates_trace(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        assert "trace-001" in fake_client.traces

    def test_second_export_reuses_trace(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        exporter.export_event(name="tool.started", trace_id="trace-001")
        assert len(fake_client.traces) == 1, "Should create only one trace"

    def test_two_exports_same_trace_produce_two_child_spans(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="run.started",
            trace_id="trace-001",
            attributes={"run_id": "run-1"},
        )
        exporter.export_event(
            name="tool.started",
            trace_id="trace-001",
            attributes={"tool_name": "shell"},
        )
        assert len(fake_client.spans) == 2

    def test_different_trace_ids_create_separate_traces(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        exporter.export_event(name="run.started", trace_id="trace-002")
        assert len(fake_client.traces) == 2

    def test_child_span_carries_event_name(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.started",
            trace_id="trace-001",
            attributes={"tool_name": "shell"},
        )
        assert fake_client.spans[0]["name"] == "tool.started"

    def test_child_span_carries_attributes_as_input(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(
            name="tool.started",
            trace_id="trace-001",
            attributes={"tool_name": "shell", "tool_call_id": "tc-1"},
        )
        assert fake_client.spans[0]["input"] == {
            "tool_name": "shell",
            "tool_call_id": "tc-1",
        }


# ─────────────────────────────────────────────────────────────────────
# release_trace() Contract
# ─────────────────────────────────────────────────────────────────────


class TestReleaseTrace:
    """release_trace() clears the in-memory handle; next call opens a fresh trace."""

    def test_release_drops_handle(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.export_event(name="run.started", trace_id="trace-001")
        exporter.release_trace("trace-001")
        # After release, a new export should create a new trace call
        exporter.export_event(name="run.started", trace_id="trace-001")
        # Trace was opened twice (second time after release)
        assert len(fake_client.spans) == 2

    def test_release_nonexistent_trace_is_noop(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        # Should not raise
        exporter.release_trace("nonexistent-trace")


# ─────────────────────────────────────────────────────────────────────
# LANGFUSE_ENABLED Kill Switch
# ─────────────────────────────────────────────────────────────────────


class TestKillSwitch:
    """LANGFUSE_ENABLED=false makes every method a silent no-op."""

    def test_disabled_export_event_is_noop(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.traces) == 0
        assert len(fake_client.spans) == 0

    def test_disabled_shutdown_is_noop(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.shutdown()
        assert fake_client.flushed is False

    def test_disabled_release_trace_is_noop(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.release_trace("trace-001")  # Should not raise

    def test_enabled_by_default(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        """When LANGFUSE_ENABLED is not set, exporter is active."""
        exporter.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.traces) == 1

    def test_enabled_true_explicit(
        self, fake_client: FakeLangfuseClient
    ) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
                sdk_client=fake_client,
            )
        exp.export_event(name="run.started", trace_id="trace-001")
        assert len(fake_client.traces) == 1


# ─────────────────────────────────────────────────────────────────────
# Init Failure Handling (O1)
# ─────────────────────────────────────────────────────────────────────


class TestInitFailure:
    """Init failure logs WARNING, returns None client, never raises."""

    def test_init_failure_logs_warning_and_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with patch(
            "langfuse.Langfuse",
            side_effect=RuntimeError("connection refused"),
            create=True,
        ):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
            )
            # Force client init by calling export_event
            exp.export_event(name="run.started", trace_id="trace-001")
        assert "langfuse client init failed" in caplog.text

    def test_init_failure_export_event_does_not_raise(self) -> None:
        with patch(
            "langfuse.Langfuse",
            side_effect=RuntimeError("connection refused"),
            create=True,
        ):
            exp = LangfuseCloudExporter(
                public_key="pk-test",
                secret_key="sk-test",
            )
            # Must not raise
            exp.export_event(name="run.started", trace_id="trace-001")


# ─────────────────────────────────────────────────────────────────────
# Export Failure Handling (O1)
# ─────────────────────────────────────────────────────────────────────


class TestExportFailure:
    """Export failures are swallowed silently (O1)."""

    def test_export_event_swallows_sdk_exception(self) -> None:
        broken_client = MagicMock()
        broken_client.trace.side_effect = RuntimeError("SDK crash")
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=broken_client,
        )
        # Must not raise
        exp.export_event(name="run.started", trace_id="trace-001")

    def test_release_trace_swallows_exception(self) -> None:
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=MagicMock(),
        )
        # Force internal state then break it
        exp._traces = None  # type: ignore[attr-defined]
        # Must not raise
        exp.release_trace("trace-001")


# ─────────────────────────────────────────────────────────────────────
# Shutdown Contract
# ─────────────────────────────────────────────────────────────────────


class TestShutdown:
    """shutdown() calls flush on the SDK client."""

    def test_shutdown_calls_flush(
        self, exporter: LangfuseCloudExporter, fake_client: FakeLangfuseClient
    ) -> None:
        exporter.shutdown()
        assert fake_client.flushed is True

    def test_shutdown_swallows_flush_failure(self) -> None:
        broken_client = MagicMock()
        broken_client.flush.side_effect = RuntimeError("flush failed")
        exp = LangfuseCloudExporter(
            public_key="pk-test",
            secret_key="sk-test",
            sdk_client=broken_client,
        )
        # Must not raise
        exp.shutdown()


# ─────────────────────────────────────────────────────────────────────
# Port Protocol Compliance
# ─────────────────────────────────────────────────────────────────────


class TestPortCompliance:
    """LangfuseCloudExporter satisfies TelemetryExporter Protocol."""

    def test_is_telemetry_exporter(
        self, exporter: LangfuseCloudExporter
    ) -> None:
        from middleware.ports.telemetry_exporter import TelemetryExporter

        assert isinstance(exporter, TelemetryExporter)
