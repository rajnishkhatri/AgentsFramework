"""L2 Contract: BlackBoxPublisher — pure event-to-Langfuse mapping + redaction.

Sprint A of the BlackBox→Langfuse plan. Tests follow Protocol B (Contract-Driven
TDD) from research/tdd_agentic_systems_prompt.md.

Layer: services/governance (Horizontal Services)
Pyramid level: L2 — Reproducible. Deterministic, fast, no I/O, no LLM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from services.governance.black_box import EventType, TraceEvent

# Import under test — intentionally failing until GREEN phase.
from services.governance.black_box_publisher import (
    redact_details,
    to_export_kwargs,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


def _event(
    event_type: EventType,
    *,
    step: int | None = 1,
    details: dict | None = None,
    workflow_id: str = "wf-abc-123",
    event_id: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        event_id=event_id or str(uuid.uuid4()),
        workflow_id=workflow_id,
        event_type=event_type,
        timestamp=datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC),
        step=step,
        details=details or {"info": "ok"},
    )


# ─────────────────────────────────────────────────────────────────────
# A. Event-type → Langfuse observation mapping — all 9
# ─────────────────────────────────────────────────────────────────────


_EXPECTED_MAPPINGS: list[tuple[EventType, str, str]] = [
    (EventType.TASK_STARTED, "agent", "task.started"),
    (EventType.TASK_COMPLETED, "agent", "task.completed"),
    (EventType.STEP_PLANNED, "chain", "step.planned"),
    (EventType.STEP_EXECUTED, "span", "step.executed"),
    (EventType.TOOL_CALLED, "tool", "tool.called"),
    (EventType.MODEL_SELECTED, "generation", "model.selected"),
    (EventType.GUARDRAIL_CHECKED, "guardrail", "guardrail.checked"),
    (EventType.PARAMETER_CHANGED, "span", "parameter.changed"),
    (EventType.ERROR_OCCURRED, "span", "error.occurred"),
]


class TestEventTypeMapping:
    """Verify every EventType maps to the correct Langfuse observation type and name."""

    @pytest.mark.parametrize(
        "event_type,expected_obs_type,expected_name",
        _EXPECTED_MAPPINGS,
        ids=[et.value for et, _, _ in _EXPECTED_MAPPINGS],
    )
    def test_mapping_correct(
        self,
        event_type: EventType,
        expected_obs_type: str,
        expected_name: str,
    ) -> None:
        result = to_export_kwargs(_event(event_type))
        assert result["observation_type"] == expected_obs_type
        assert result["name"] == expected_name

    def test_all_event_types_covered(self) -> None:
        """No EventType should be unmapped — prevents silent data loss."""
        mapped_types = {et for et, _, _ in _EXPECTED_MAPPINGS}
        all_types = set(EventType)
        assert mapped_types == all_types, (
            f"Unmapped EventTypes: {all_types - mapped_types}"
        )

    def test_error_event_gets_error_level(self) -> None:
        result = to_export_kwargs(_event(EventType.ERROR_OCCURRED))
        assert result["level"] == "ERROR"

    def test_non_error_event_default_level(self) -> None:
        result = to_export_kwargs(_event(EventType.TASK_STARTED))
        assert result["level"] == "DEFAULT"


# ─────────────────────────────────────────────────────────────────────
# B. Attributes contract — every export has the required keys
# ─────────────────────────────────────────────────────────────────────


class TestExportAttributes:
    """Verify the attributes dict produced by to_export_kwargs."""

    def test_required_attribute_keys(self) -> None:
        ev = _event(EventType.STEP_EXECUTED, step=3)
        result = to_export_kwargs(ev)
        attrs = result["attributes"]
        assert attrs["event_id"] == ev.event_id
        assert attrs["workflow_id"] == ev.workflow_id
        assert attrs["step"] == 3
        assert "timestamp" in attrs
        assert "integrity_hash" in attrs

    def test_details_included_in_attributes(self) -> None:
        ev = _event(EventType.TOOL_CALLED, details={"tool": "shell", "args": "ls"})
        result = to_export_kwargs(ev)
        assert result["attributes"]["details"]["tool"] == "shell"

    def test_trace_id_equals_workflow_id(self) -> None:
        ev = _event(EventType.TASK_STARTED, workflow_id="wf-trace-match")
        result = to_export_kwargs(ev)
        assert result["trace_id"] == "wf-trace-match"

    def test_observation_id_equals_event_id(self) -> None:
        eid = str(uuid.uuid4())
        ev = _event(EventType.TASK_STARTED, event_id=eid)
        result = to_export_kwargs(ev)
        assert result["observation_id"] == eid


# ─────────────────────────────────────────────────────────────────────
# C. Redaction — PII stripping
# ─────────────────────────────────────────────────────────────────────


class TestRedactPII:
    """Failure paths first: redaction MUST strip PII before Langfuse gets it."""

    def test_email_redacted(self) -> None:
        details = {"contact": "alice@example.com", "status": "ok"}
        result = redact_details(details)
        assert "alice@example.com" not in result["contact"]
        assert "[REDACTED]" in result["contact"]

    def test_ssn_redacted(self) -> None:
        details = {"ssn": "123-45-6789", "name": "Alice"}
        result = redact_details(details)
        assert "123-45-6789" not in result["ssn"]
        assert "[REDACTED]" in result["ssn"]

    def test_phone_redacted(self) -> None:
        details = {"phone": "(555) 123-4567"}
        result = redact_details(details)
        assert "(555) 123-4567" not in result["phone"]
        assert "[REDACTED]" in result["phone"]

    def test_multiple_pii_in_single_field(self) -> None:
        details = {"msg": "Contact alice@example.com or 555-123-4567 for info"}
        result = redact_details(details)
        assert "alice@example.com" not in result["msg"]
        assert "555-123-4567" not in result["msg"]

    def test_clean_text_unchanged(self) -> None:
        details = {"info": "step executed successfully", "count": "42"}
        result = redact_details(details)
        assert result["info"] == "step executed successfully"
        assert result["count"] == "42"


# ─────────────────────────────────────────────────────────────────────
# D. Redaction — API key stripping
# ─────────────────────────────────────────────────────────────────────


class TestRedactAPIKeys:
    """API keys MUST be stripped — failure here is a security incident."""

    def test_openai_key_redacted(self) -> None:
        details = {"config": "key=sk-abcdefghijklmnopqrstuvwx"}
        result = redact_details(details)
        assert "sk-abcdefghijklmnopqrstuvwx" not in result["config"]
        assert "[REDACTED]" in result["config"]

    def test_aws_access_key_redacted(self) -> None:
        details = {"cred": "AKIAIOSFODNN7EXAMPLE"}
        result = redact_details(details)
        assert "AKIAIOSFODNN7EXAMPLE" not in result["cred"]
        assert "[REDACTED]" in result["cred"]

    def test_github_pat_redacted(self) -> None:
        details = {"token": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"}
        result = redact_details(details)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in result["token"]
        assert "[REDACTED]" in result["token"]


# ─────────────────────────────────────────────────────────────────────
# E. Truncation — 200-char cap per detail value
# ─────────────────────────────────────────────────────────────────────


class TestTruncation:
    """Detail values exceeding 200 chars MUST be truncated."""

    def test_long_value_truncated(self) -> None:
        details = {"big": "x" * 300}
        result = redact_details(details)
        assert len(result["big"]) <= 200

    def test_exactly_200_chars_unchanged(self) -> None:
        details = {"exact": "y" * 200}
        result = redact_details(details)
        assert result["exact"] == "y" * 200

    def test_short_value_unchanged(self) -> None:
        details = {"short": "hello"}
        result = redact_details(details)
        assert result["short"] == "hello"

    def test_truncation_applied_before_redaction_check(self) -> None:
        """A long string ending with PII should be truncated then redacted."""
        padding = "a" * 190
        details = {"mixed": padding + " alice@example.com"}
        result = redact_details(details)
        assert len(result["mixed"]) <= 200


# ─────────────────────────────────────────────────────────────────────
# F. Edge cases
# ─────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_details(self) -> None:
        result = redact_details({})
        assert result == {}

    def test_non_string_values_coerced(self) -> None:
        details = {"count": 42, "flag": True, "nested": {"a": 1}}
        result = redact_details(details)
        assert isinstance(result["count"], str)
        assert isinstance(result["flag"], str)
        assert isinstance(result["nested"], str)

    def test_none_value_handled(self) -> None:
        details = {"missing": None}
        result = redact_details(details)
        assert result["missing"] == "None"

    def test_to_export_kwargs_applies_redaction_to_details(self) -> None:
        """Integration: to_export_kwargs should use redacted details."""
        ev = _event(
            EventType.TOOL_CALLED,
            details={"secret": "sk-abcdefghijklmnopqrstuvwx", "tool": "shell"},
        )
        result = to_export_kwargs(ev)
        assert "sk-abcdefghijklmnopqrstuvwx" not in str(result["attributes"]["details"])


# ─────────────────────────────────────────────────────────────────────
# G. Dependency boundary — publisher MUST NOT import SDKs
# ─────────────────────────────────────────────────────────────────────


class TestLayeringInvariant:
    """Architecture invariant: publisher has zero SDK imports."""

    def test_no_langfuse_import(self) -> None:
        import ast
        from pathlib import Path

        src = Path("services/governance/black_box_publisher.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("langfuse"), (
                        f"Forbidden import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("langfuse"), (
                        f"Forbidden import from: {node.module}"
                    )

    def test_no_langgraph_import(self) -> None:
        import ast
        from pathlib import Path

        src = Path("services/governance/black_box_publisher.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("langgraph"), (
                        f"Forbidden import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("langgraph"), (
                        f"Forbidden import from: {node.module}"
                    )
