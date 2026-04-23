"""L1 Deterministic: Tests for trust.models.TrustTraceRecord.

Per AGENT_UI_ADAPTER_SPRINTS.md US-DP-1.1.
TDD Protocol A (Pure TDD), failure paths first per AGENTS.md TAP-4.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from trust.models import TrustTraceRecord


# ── Failure-path tests (write FIRST per TAP-4) ────────────────────────


class TestTrustTraceRecordRejection:
    def test_rejects_missing_event_id(self):
        with pytest.raises(ValidationError):
            TrustTraceRecord(
                timestamp=datetime.now(UTC),
                trace_id="trace-1",
                agent_id="a1",
                layer="L1",
                event_type="identity_verified",
                details={},
                outcome="pass",
            )

    def test_rejects_missing_trace_id(self):
        with pytest.raises(ValidationError):
            TrustTraceRecord(
                event_id="ev-1",
                timestamp=datetime.now(UTC),
                agent_id="a1",
                layer="L1",
                event_type="identity_verified",
                details={},
                outcome="pass",
            )

    def test_rejects_missing_agent_id(self):
        with pytest.raises(ValidationError):
            TrustTraceRecord(
                event_id="ev-1",
                timestamp=datetime.now(UTC),
                trace_id="trace-1",
                layer="L1",
                event_type="identity_verified",
                details={},
                outcome="pass",
            )

    def test_rejects_missing_timestamp(self):
        with pytest.raises(ValidationError):
            TrustTraceRecord(
                event_id="ev-1",
                trace_id="trace-1",
                agent_id="a1",
                layer="L1",
                event_type="identity_verified",
                details={},
                outcome="pass",
            )

    def test_rejects_invalid_layer(self):
        with pytest.raises(ValidationError):
            TrustTraceRecord(
                event_id="ev-1",
                timestamp=datetime.now(UTC),
                trace_id="trace-1",
                agent_id="a1",
                layer="L99",  # Not a valid L1-L7 value
                event_type="identity_verified",
                details={},
                outcome="pass",
            )

    def test_rejects_invalid_outcome(self):
        with pytest.raises(ValidationError):
            TrustTraceRecord(
                event_id="ev-1",
                timestamp=datetime.now(UTC),
                trace_id="trace-1",
                agent_id="a1",
                layer="L1",
                event_type="identity_verified",
                details={},
                outcome="maybe",  # Not pass/fail/alert
            )


# ── Acceptance-path tests (after rejections per TAP-4) ────────────────


class TestTrustTraceRecordSchema:
    def test_minimal_valid(self):
        record = TrustTraceRecord(
            event_id="ev-1",
            timestamp=datetime.now(UTC),
            trace_id="trace-1",
            agent_id="a1",
            layer="L1",
            event_type="identity_verified",
            details={},
            outcome=None,
        )
        assert record.event_id == "ev-1"
        assert record.layer == "L1"
        assert record.outcome is None

    def test_schema_version_defaults_to_2(self):
        record = TrustTraceRecord(
            event_id="ev-1",
            timestamp=datetime.now(UTC),
            trace_id="trace-1",
            agent_id="a1",
            layer="L1",
            event_type="identity_verified",
            details={},
            outcome="pass",
        )
        assert record.schema_version == 2, (
            "TrustTraceRecord schema_version must default to 2 per "
            "docs/Architectures/FOUR_LAYER_ARCHITECTURE.md §schema-version-2"
        )

    def test_optional_multi_agent_fields_default_none(self):
        record = TrustTraceRecord(
            event_id="ev-1",
            timestamp=datetime.now(UTC),
            trace_id="trace-1",
            agent_id="a1",
            layer="L1",
            event_type="identity_verified",
            details={},
            outcome="pass",
        )
        assert record.source_agent_id is None
        assert record.causation_id is None

    def test_full_multi_agent_fields(self):
        record = TrustTraceRecord(
            event_id="ev-2",
            source_agent_id="agent-a",
            causation_id="ev-1",
            timestamp=datetime.now(UTC),
            trace_id="trace-1",
            agent_id="agent-b",
            layer="L2",
            event_type="access_granted",
            details={"action": "read"},
            outcome="pass",
        )
        assert record.source_agent_id == "agent-a"
        assert record.causation_id == "ev-1"


# ── Round-trip tests (Pattern 1 from TDD §Pattern Catalog) ────────────


class TestTrustTraceRecordRoundTrip:
    def test_json_round_trip_preserves_all_fields(self):
        original = TrustTraceRecord(
            event_id="ev-1",
            source_agent_id="agent-a",
            causation_id="ev-0",
            timestamp=datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
            trace_id="trace-xyz",
            agent_id="agent-b",
            layer="L4",
            event_type="plan_captured",
            details={"plan_size": 7, "unicode": "café"},
            outcome="pass",
        )
        serialized = original.model_dump_json()
        rehydrated = TrustTraceRecord.model_validate_json(serialized)
        assert rehydrated == original

    def test_all_seven_layer_values_accepted(self):
        for layer in ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]:
            record = TrustTraceRecord(
                event_id=f"ev-{layer}",
                timestamp=datetime.now(UTC),
                trace_id="t1",
                agent_id="a1",
                layer=layer,
                event_type="x",
                details={},
                outcome=None,
            )
            assert record.layer == layer
