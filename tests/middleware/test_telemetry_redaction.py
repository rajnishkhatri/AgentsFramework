"""L2: relay and bridge must not leak raw PII/API keys to Langfuse export attrs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from agent_ui_adapter.wire.domain_events import LLMMessageEnded, LLMMessageStarted
from middleware.telemetry_bridge import emit_domain_event
from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.black_box_publisher import redact_text

_SECRET = "sk-proj-abc123def456ghi789jkl012mno345pqrstu678vwx"
_EMAIL = "alice.smith@example.com"


class _StubExporter:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def export_event(
        self,
        *,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> bool:
        self.events.append(
            {"name": name, "trace_id": trace_id, "attributes": attributes or {}}
        )
        return True

    def release_trace(self, trace_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


def _build_relay(storage: Path, exporter: _StubExporter):
    from middleware.sidecars.black_box_to_telemetry import BlackBoxToTelemetryRelay

    return BlackBoxToTelemetryRelay(
        storage_dir=storage,
        exporter=exporter,
        base_delay_s=0.0,
    )


class TestRedactText:
    def test_strips_api_key_and_email(self) -> None:
        text = f"email={_EMAIL} key={_SECRET}"
        redacted = redact_text(text)
        assert _EMAIL not in redacted
        assert _SECRET not in redacted
        assert "[REDACTED]" in redacted


class TestRelayOutputRedaction:
    def test_task_started_output_uses_redacted_details(
        self, tmp_path: Path,
    ) -> None:
        exporter = _StubExporter()
        storage = tmp_path / "black_box_recordings"
        recorder = BlackBoxRecorder(storage_dir=storage)
        recorder.record(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                workflow_id="wf-redact",
                event_type=EventType.TASK_STARTED,
                timestamp=datetime.now(UTC),
                details={
                    "task_input": f"Contact {_EMAIL} key {_SECRET}",
                },
            )
        )
        (storage / "wf-redact" / ".langfuse_offset").write_text("0")

        relay = _build_relay(storage, exporter)
        relay.run_once()

        assert len(exporter.events) == 1
        output = exporter.events[0]["attributes"]["__output"]
        output_str = str(output)
        assert _EMAIL not in output_str
        assert _SECRET not in output_str
        assert exporter.events[0]["attributes"]["details"]["task_input"] == output["task_input"]


class TestBridgeInputRedaction:
    def test_llm_input_text_redacted_on_merged_call(self) -> None:
        """Phase 3: input_text is redacted at buffer time and surfaces on the
        merged ``llm.call`` obs emitted by LLMMessageEnded."""
        exporter = _StubExporter()
        emit_domain_event(
            exporter,
            LLMMessageStarted(
                trace_id="trace-1",
                message_id="msg-1",
                input_text=f"User said {_EMAIL} with {_SECRET}",
            ),
        )
        emit_domain_event(
            exporter,
            LLMMessageEnded(trace_id="trace-1", message_id="msg-1", output_text="ok"),
        )
        assert len(exporter.events) == 1
        assert exporter.events[0]["name"] == "llm.call"
        input_text = exporter.events[0]["attributes"]["input_text"]
        assert _EMAIL not in input_text
        assert _SECRET not in input_text
        assert "[REDACTED]" in input_text
