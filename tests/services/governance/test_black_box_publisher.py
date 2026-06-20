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
    redact_compliance_bundle,
    redact_details,
    redact_text,
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
    # Phase 1 (E5): MODEL_SELECTED is a routing DECISION, not an LLM call. It
    # carries no usage/cost, so typing it ``generation`` polluted generation-level
    # cost analytics. Retyped to ``chain``; the real LLM call is the wire
    # ``llm.call`` generation (Phase 3).
    (EventType.MODEL_SELECTED, "chain", "model.selected"),
    (EventType.GUARDRAIL_CHECKED, "guardrail", "guardrail.checked"),
    (EventType.PARAMETER_CHANGED, "span", "parameter.changed"),
    (EventType.ERROR_OCCURRED, "span", "error.occurred"),
    # Phase 1 memory wiring: recall/store activity events (no usage/cost) typed
    # ``span``; the relay must export them so the four-pillar audit reads "memory
    # ran" from the trace. Consumer-driven contract for the new EventTypes.
    (EventType.MEMORY_RECALLED, "span", "memory.recalled"),
    (EventType.MEMORY_STORED, "span", "memory.stored"),
    (EventType.MEMORY_SUPPRESSED, "span", "memory.suppressed"),
    # A1 consolidation (Hermes adoption): write-side eviction activity, span like
    # the other memory carriers. Consumer-driven contract for the new EventType.
    (EventType.MEMORY_CONSOLIDATED, "span", "memory.consolidated"),
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


class TestGuardrailLevel:
    """Phase 4: a clean guardrail pass is DEBUG (filterable noise); a blocked or
    redacting check is WARNING (a real signal). ERROR_OCCURRED stays ERROR."""

    def test_clean_pass_is_debug(self) -> None:
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={"checked": True, "blocked": False, "redacted": False, "failed_rules": []},
        )
        assert to_export_kwargs(ev)["level"] == "DEBUG"

    def test_blocked_is_warning(self) -> None:
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={"checked": True, "blocked": True, "redacted": False, "failed_rules": ["r1"]},
        )
        assert to_export_kwargs(ev)["level"] == "WARNING"

    def test_redacted_is_warning(self) -> None:
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={"checked": True, "blocked": False, "redacted": True, "failed_rules": []},
        )
        assert to_export_kwargs(ev)["level"] == "WARNING"

    def test_failed_rules_nonempty_is_warning(self) -> None:
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={"checked": True, "blocked": False, "redacted": False, "failed_rules": ["x"]},
        )
        assert to_export_kwargs(ev)["level"] == "WARNING"

    def test_missing_flags_default_to_debug(self) -> None:
        """A sparse clean-pass payload (only ``checked``) is still DEBUG."""
        ev = _event(EventType.GUARDRAIL_CHECKED, details={"checked": True})
        assert to_export_kwargs(ev)["level"] == "DEBUG"

    def test_error_occurred_still_error(self) -> None:
        assert to_export_kwargs(_event(EventType.ERROR_OCCURRED))["level"] == "ERROR"


class TestCarrierGateLevel:
    """Governance carrier gate (enforcement gate Phase 1, shadow): the gate
    records a missing-pillar gap as a ``GUARDRAIL_CHECKED`` carrier with
    ``source: "carrier_gate"`` + ``outcome: "alert"`` / ``would_enforce: true``,
    but NONE of blocked/redacted/failed_rules. Without a special case it would
    relay at ``DEBUG`` — indistinguishable from a clean pass, burying the gap as
    filterable noise and defeating the gate's "never a silent skip" purpose. An
    alert must surface at ``WARNING``; a clean carrier_gate pass stays ``DEBUG``."""

    def test_carrier_gate_alert_is_warning(self) -> None:
        """The core fix: a real missing-pillar gap (alert) must be WARNING even
        though no blocked/redacted/failed_rules flag is set."""
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={
                "source": "carrier_gate",
                "outcome": "alert",
                "would_enforce": True,
                "missing_pillars": ["validation"],
                "missing_carriers": ["guardrail_checked"],
            },
        )
        assert to_export_kwargs(ev)["level"] == "WARNING"

    def test_carrier_gate_alert_via_would_enforce_alone_is_warning(self) -> None:
        """``would_enforce`` truthy is equivalent to ``outcome: alert`` — either
        signal alone is enough to surface the gap."""
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={"source": "carrier_gate", "would_enforce": True},
        )
        assert to_export_kwargs(ev)["level"] == "WARNING"

    def test_carrier_gate_pass_is_debug(self) -> None:
        """A clean carrier_gate check (no gap) is the provable negative — kept as
        DEBUG noise so the audit skill sees the check ran, not promoted to WARNING."""
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={
                "source": "carrier_gate",
                "outcome": "pass",
                "would_enforce": False,
                "missing_pillars": [],
                "missing_carriers": [],
            },
        )
        assert to_export_kwargs(ev)["level"] == "DEBUG"

    def test_non_carrier_gate_clean_pass_still_debug(self) -> None:
        """The source gate must be specific: a generic guardrail clean pass
        (no carrier_gate source) is unaffected and stays DEBUG."""
        ev = _event(
            EventType.GUARDRAIL_CHECKED,
            details={"checked": True, "blocked": False, "outcome": "pass"},
        )
        assert to_export_kwargs(ev)["level"] == "DEBUG"


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
# B2. Honest timestamps — event_time first-class (Phase 2, D-0a)
# ─────────────────────────────────────────────────────────────────────


class TestEventTimeFirstClass:
    """D-0a resolution (langfuse 4.7.1): no observation start-time backdating.

    The Langfuse span is stamped at relay-export time (~0.9s after the real
    event). So the authoritative event instant must survive *in the
    attributes* as ``event_time`` (= ``event.timestamp`` ISO string), letting a
    reader reconstruct true ordering. We do NOT fabricate ``start_time`` /
    ``end_time`` — that would invert the span (real start, backdated end).
    """

    _SAMPLE_TYPES = [
        EventType.TASK_STARTED,
        EventType.STEP_EXECUTED,
        EventType.TOOL_CALLED,
        EventType.MODEL_SELECTED,
        EventType.GUARDRAIL_CHECKED,
        EventType.TASK_COMPLETED,
    ]

    @pytest.mark.parametrize("event_type", _SAMPLE_TYPES)
    def test_event_time_present_on_every_observation_type(
        self, event_type: EventType
    ) -> None:
        ev = _event(event_type)
        attrs = to_export_kwargs(ev)["attributes"]
        assert attrs["event_time"] == ev.timestamp.isoformat()

    def test_event_time_is_authoritative_instant_not_export_time(self) -> None:
        """event_time reflects the recorded event, not 'now'."""
        ev = _event(EventType.TOOL_CALLED)
        attrs = to_export_kwargs(ev)["attributes"]
        assert attrs["event_time"] == "2026-05-28T12:00:00+00:00"

    def test_no_fabricated_start_or_end_time(self) -> None:
        """We must never emit span start_time/end_time kwargs (D-0a: NO backdating)."""
        ev = _event(EventType.STEP_EXECUTED)
        result = to_export_kwargs(ev)
        assert "start_time" not in result
        assert "end_time" not in result
        assert "start_time" not in result["attributes"]
        assert "end_time" not in result["attributes"]

    def test_legacy_timestamp_key_retained_for_back_compat(self) -> None:
        """The pre-existing ``timestamp`` attribute stays (consumers may read it)."""
        ev = _event(EventType.TASK_COMPLETED)
        attrs = to_export_kwargs(ev)["attributes"]
        assert attrs["timestamp"] == ev.timestamp.isoformat()


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

    def test_redact_text_strips_inline_pii(self) -> None:
        text = "Contact alice@example.com for help"
        assert "alice@example.com" not in redact_text(text)
        assert "[REDACTED]" in redact_text(text)

    def test_redact_compliance_bundle_scrubs_event_details(self) -> None:
        bundle = {
            "workflow_id": "wf-1",
            "events": [
                {
                    "event_id": "e1",
                    "details": {"task_input": "sk-proj-abcdefghijklmnopqrstuvwx"},
                }
            ],
        }
        redacted = redact_compliance_bundle(bundle)
        assert "sk-proj-abcdefghijklmnopqrstuvwx" not in str(redacted["events"][0]["details"])

    def test_redact_compliance_bundle_scrubs_phase_event_details(self) -> None:
        bundle = {
            "workflow_id": "wf-phase",
            "phase_events": [
                {
                    "event": "phase_end",
                    "phase": "routing",
                    "details": {"note": "Contact alice@example.com for routing"},
                }
            ],
        }
        redacted = redact_compliance_bundle(bundle)
        details = redacted["phase_events"][0]["details"]
        assert "alice@example.com" not in details["note"]
        assert "[REDACTED]" in details["note"]

    def test_redact_compliance_bundle_leaves_phase_events_without_details(self) -> None:
        bundle = {
            "workflow_id": "wf-phase",
            "phase_events": [
                {
                    "event": "phase_end",
                    "phase": "completion",
                    "outcome": "done",
                }
            ],
        }
        redacted = redact_compliance_bundle(bundle)
        assert redacted["phase_events"][0]["outcome"] == "done"
        assert "details" not in redacted["phase_events"][0]


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

    def test_short_openai_project_key_redacted(self) -> None:
        """Regression (walkthrough G1.2): a short sk-proj- key must redact.

        The previous {20,} quantifier only matched long keys, so this exact
        17-char-payload form leaked. Tests only exercised long keys, so the
        gap went uncaught (TAP-4). Pin the short form to prevent resurfacing.
        """
        details = {"config": "my key is sk-proj-abc123456789 thanks"}
        result = redact_details(details)
        assert "sk-proj-abc123456789" not in result["config"]
        assert "[REDACTED]" in result["config"]

    def test_safe_numeric_keys_not_corrupted_by_key_rule(self) -> None:
        """The broadened sk- rule must not touch known-safe numeric telemetry.

        Phase 1 (E4): safe numerics now keep their native type rather than being
        stringified, so they remain numerically filterable in Langfuse.
        """
        details = {"latency_ms": 1234567890, "step": 42, "cost_usd": 0.0123}
        result = redact_details(details)
        assert result["latency_ms"] == 1234567890
        assert result["step"] == 42
        assert result["cost_usd"] == 0.0123

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

    def test_unknown_non_string_values_coerced(self) -> None:
        """Unknown keys (not in safe sets) still stringify so PII redaction
        applies to arbitrary content and nested structures stay flat."""
        details = {"count": 42, "flag": True, "nested": {"a": 1}}
        result = redact_details(details)
        assert isinstance(result["count"], str)
        assert isinstance(result["flag"], str)
        assert isinstance(result["nested"], str)

    def test_none_value_passes_through_as_none(self) -> None:
        """Phase 1 (E4): a ``None`` detail must surface as null, not the string
        'None' — stringified Nones are pure trace noise (``error: 'None'``,
        ``downgrade_reason: 'None'`` in the reviewed trace)."""
        details = {"missing": None}
        result = redact_details(details)
        assert result["missing"] is None


# ─────────────────────────────────────────────────────────────────────
# F2. Native type preservation for safe keys (Phase 1 / E4)
# ─────────────────────────────────────────────────────────────────────


class TestNativeTypePreservation:
    """Safe numeric/bool telemetry keys keep their native type so Langfuse can
    filter and aggregate them numerically (the reviewed trace carried
    ``"criteria_met": "0.0"`` and ``"plan_valid": "True"`` as strings)."""

    def test_safe_numeric_keys_keep_native_numbers(self) -> None:
        details = {
            "criteria_met": 0.0,
            "task_completion_score": 0.887,
            "branch_coverage": 0.625,
            "cost_fraction": 0.01,
            "tokens_in": 2153,
        }
        result = redact_details(details)
        assert result["criteria_met"] == 0.0
        assert isinstance(result["criteria_met"], float)
        assert result["task_completion_score"] == 0.887
        assert result["branch_coverage"] == 0.625
        assert result["cost_fraction"] == 0.01
        assert result["tokens_in"] == 2153
        assert isinstance(result["tokens_in"], int)

    def test_safe_bool_keys_keep_native_bools(self) -> None:
        details = {
            "plan_valid": True,
            "blocked": False,
            "redacted": False,
            "goal_met": False,
            "termination_clean": True,
            "would_downgrade": True,
            "cached": False,
            "plan_changed": True,
        }
        result = redact_details(details)
        for key, expected in details.items():
            assert result[key] is expected, f"{key} lost native bool"

    def test_safe_numeric_none_still_passes_through(self) -> None:
        """A safe key carrying None (e.g. goal_met before judge ran) is null."""
        result = redact_details({"goal_met": None, "criteria_met": None})
        assert result["goal_met"] is None
        assert result["criteria_met"] is None

    def test_oversized_safe_string_still_capped(self) -> None:
        """Failure path: a safe key carrying a huge string is still length-capped
        (native preservation applies to numbers/bools, not giant strings)."""
        result = redact_details({"latency_ms": "9" * 300})
        assert len(str(result["latency_ms"])) <= 200

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


# ─────────────────────────────────────────────────────────────────────
# H. I4 — numeric telemetry keys survive redaction unredacted
# ─────────────────────────────────────────────────────────────────────


class TestNumericKeysSurviveRedaction:
    """Failure path first: the credit-card pattern MUST NOT corrupt numeric telemetry.

    Regression guard for I4: a float like ``total_cost_usd=4242424242424242.0``
    is credit-card-shaped and was being redacted to ``[REDACTED]`` before the
    safe-key exemption, silently destroying cost/latency metrics.
    """

    @pytest.mark.parametrize(
        "key,value",
        [
            ("latency_ms", 1234.5),
            ("total_cost_usd", 0.0042),
            ("cost_usd", 0.0042),
            ("tokens_in", 512),
            ("tokens_out", 256),
            ("input_tokens", 512),
            ("output_tokens", 256),
            ("step_count", 7),
            ("step", 3),
            ("budget_limit", 1.0),
            ("total_tokens", 768),
        ],
    )
    def test_safe_numeric_key_survives_unredacted(self, key, value) -> None:
        # Phase 1 (E4): safe numerics now keep their native type (no longer
        # stringified), but the I4 intent holds — they are never regex-redacted.
        result = redact_details({key: value})
        assert result[key] == value
        assert "[REDACTED]" not in str(result[key])

    def test_credit_card_shaped_float_on_safe_key_not_redacted(self) -> None:
        """The exact I4 regression: a 16-digit cost float must survive intact."""
        cc_shaped = 4242424242424242.0
        result = redact_details({"total_cost_usd": cc_shaped})
        assert result["total_cost_usd"] == cc_shaped
        assert "[REDACTED]" not in str(result["total_cost_usd"])

    def test_same_value_on_unsafe_key_is_still_redacted(self) -> None:
        """Proves the redaction is still live — only the safe keys are exempt."""
        result = redact_details({"note": "4242424242424242"})
        assert "[REDACTED]" in result["note"]


class TestPhaseBMemoryCarrierTypes:
    """Phase B: recall keys list + suppress bool keep native types through redact."""

    def test_recall_keys_list_survives_native(self) -> None:
        result = redact_details({"keys": ["k1", "k2"], "count": 2})
        assert result["keys"] == ["k1", "k2"]

    def test_suppressed_bool_survives_native(self) -> None:
        result = redact_details({"suppressed": True, "key": "k1"})
        assert result["suppressed"] is True


# ─────────────────────────────────────────────────────────────────────
# I. I5 — native generation field promotion
# ─────────────────────────────────────────────────────────────────────


class TestNativeGenerationFields:
    """STEP_EXECUTED promotes native model/usage/cost fields.

    Phase 1 (E5): MODEL_SELECTED no longer promotes generation fields — it is a
    ``chain`` routing decision with no LLM usage. STEP_EXECUTED remains the
    relay's usage carrier until the wire ``llm.call`` generation takes over
    (Phase 3) and STEP_EXECUTED export is suppressed (Phase 4).
    """

    def test_model_selected_does_not_promote_model(self) -> None:
        """Failure path: a routing decision must NOT emit a native model field."""
        ev = _event(EventType.MODEL_SELECTED, details={"model": "gpt-4o-mini"})
        result = to_export_kwargs(ev)
        assert "model" not in result

    def test_model_selected_does_not_promote_usage_or_cost(self) -> None:
        """Failure path: MODEL_SELECTED never carries usage/cost into analytics."""
        ev = _event(
            EventType.MODEL_SELECTED,
            details={
                "model": "gpt-4o-mini",
                "tokens_in": 100,
                "tokens_out": 50,
                "cost_usd": 0.0012,
            },
        )
        result = to_export_kwargs(ev)
        assert "usage" not in result
        assert "cost" not in result

    def test_step_executed_promotes_usage_and_cost(self) -> None:
        ev = _event(
            EventType.STEP_EXECUTED,
            details={
                "model": "gpt-4o-mini",
                "tokens_in": 80,
                "tokens_out": 30,
                "cost_usd": 0.0009,
            },
        )
        result = to_export_kwargs(ev)
        assert result["model"] == "gpt-4o-mini"
        assert result["usage"] == {"input": 80, "output": 30, "total": 110}
        assert result["cost"] == pytest.approx(0.0009)

    def test_non_generation_event_does_not_promote_native_fields(self) -> None:
        """Failure path: a tool event must NOT leak model/usage/cost kwargs."""
        ev = _event(
            EventType.TOOL_CALLED,
            details={"tool": "shell", "model": "gpt-4o-mini", "cost_usd": 0.01},
        )
        result = to_export_kwargs(ev)
        assert "model" not in result
        assert "usage" not in result
        assert "cost" not in result

    def test_task_event_does_not_promote_native_fields(self) -> None:
        ev = _event(EventType.TASK_COMPLETED, details={"cost_usd": 0.02}, step=None)
        result = to_export_kwargs(ev)
        assert "model" not in result
        assert "usage" not in result
        assert "cost" not in result


# ─────────────────────────────────────────────────────────────────────
# J. I6 — step-based parent observation hierarchy
# ─────────────────────────────────────────────────────────────────────


class TestParentObservationHierarchy:
    """Non-task events nest under a per-step parent; task events are roots."""

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.STEP_PLANNED,
            EventType.STEP_EXECUTED,
            EventType.TOOL_CALLED,
            EventType.MODEL_SELECTED,
            EventType.GUARDRAIL_CHECKED,
            EventType.PARAMETER_CHANGED,
            EventType.ERROR_OCCURRED,
        ],
    )
    def test_non_task_event_gets_step_parent(self, event_type) -> None:
        ev = _event(event_type, step=4, workflow_id="wf-xyz")
        result = to_export_kwargs(ev)
        assert result["parent_observation_id"] == "wf-xyz:step:4"

    @pytest.mark.parametrize(
        "event_type", [EventType.TASK_STARTED, EventType.TASK_COMPLETED]
    )
    def test_task_event_is_root(self, event_type) -> None:
        ev = _event(event_type, step=4, workflow_id="wf-xyz")
        result = to_export_kwargs(ev)
        assert "parent_observation_id" not in result

    def test_event_without_step_has_no_parent(self) -> None:
        ev = _event(EventType.STEP_PLANNED, step=None)
        result = to_export_kwargs(ev)
        assert "parent_observation_id" not in result


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
