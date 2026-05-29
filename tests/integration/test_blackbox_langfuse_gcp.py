"""Integration test harness: BlackBox → Langfuse on GCP via BFF (Route A).

Drives synthetic scenarios from tests/synthetic/blackbox/dataset.py through
the authenticated frontend BFF and verifies the Langfuse pipeline end-to-end.

**Markers:** @pytest.mark.live_llm + @pytest.mark.simulation — NEVER in CI.
These tests incur real LLM costs and require a running GCP deployment.

**Environment variables required:**
    FRONTEND_URL        — Frontend BFF base URL
    WOS_SESSION_COOKIE  — session cookie from browser
    LANGFUSE_PUBLIC_KEY — Langfuse project public key
    LANGFUSE_SECRET_KEY — Langfuse project secret key
    LANGFUSE_HOST       — Langfuse base URL (default: https://cloud.langfuse.com)

Run:
    pytest tests/integration/test_blackbox_langfuse_gcp.py -v --timeout=300
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from tests.synthetic.blackbox.dataset import (
    ALL_SCENARIOS,
    SCENARIO_ORDER,
    Scenario,
    ScenarioID,
)
from tests.synthetic.blackbox.langfuse_assertions import (
    AUDIT_DATASET,
    ComplianceDatasetReport,
    INCIDENT_DATASET,
    ScenarioVerification,
    assert_compliance_score,
    assert_dataset_item_exists,
    assert_no_redacted_content,
    assert_observations_present,
    assert_trace_exists,
    fetch_dataset_items,
    verify_compliance_datasets,
    verify_scenario,
)

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.simulation,
]

RELAY_FLUSH_WAIT_S = 8


def _skip_if_missing_env():
    """Skip test if required env vars are missing."""
    required = ["FRONTEND_URL", "WOS_SESSION_COOKIE", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Missing env vars: {', '.join(missing)}")


@pytest.fixture(scope="module")
def bff_client():
    """Build BFF client from environment."""
    _skip_if_missing_env()
    from scripts.validate_blackbox_langfuse import BFFClient

    frontend_url = os.environ["FRONTEND_URL"]
    cookie = os.environ["WOS_SESSION_COOKIE"]
    return BFFClient(frontend_url, cookie)


@pytest.fixture(scope="module")
def event_loop():
    """Module-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _drive_scenario(bff_client, scenario: Scenario) -> str:
    """POST scenario to BFF, return trace_id."""
    trace_id, raw = await bff_client.post_run_stream(scenario.bff_payload)
    if trace_id is None:
        import re
        uuid_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        )
        matches = uuid_pattern.findall(raw)
        if matches:
            trace_id = matches[0]
        else:
            hex_pattern = re.compile(r"[0-9a-f]{32}")
            hex_matches = hex_pattern.findall(raw)
            if hex_matches:
                trace_id = hex_matches[0]
    assert trace_id is not None, (
        f"Could not extract trace_id for {scenario.id.value}"
    )
    return trace_id


# ─────────────────────────────────────────────────────────────────────
# S1: Simple Q&A
# ─────────────────────────────────────────────────────────────────────


class TestS1SimpleQA:
    """S1: Simple Q&A exercises the 6 standard event types."""

    @pytest.fixture(scope="class")
    def trace_id(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S1]
        tid = event_loop.run_until_complete(_drive_scenario(bff_client, scenario))
        time.sleep(RELAY_FLUSH_WAIT_S)
        return tid

    def test_trace_exists(self, trace_id):
        result = assert_trace_exists(trace_id)
        assert result.passed, result.details

    def test_all_observations_present(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S1]
        results = assert_observations_present(trace_id, scenario.expected_observations)
        failures = [r for r in results if not r.passed]
        assert not failures, "\n".join(f.description for f in failures)

    def test_hash_chain_score(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S1]
        result = assert_compliance_score(trace_id, scenario.compliance)
        assert result.passed, result.details

    def test_compliance_dataset_item(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S1]
        result = assert_dataset_item_exists(trace_id, scenario.compliance)
        assert result.passed, result.details


# ─────────────────────────────────────────────────────────────────────
# S2: Tool-using task
# ─────────────────────────────────────────────────────────────────────


class TestS2ToolUsing:
    """S2: Tool-using task adds TOOL_CALLED observation."""

    @pytest.fixture(scope="class")
    def trace_id(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S2]
        tid = event_loop.run_until_complete(_drive_scenario(bff_client, scenario))
        time.sleep(RELAY_FLUSH_WAIT_S)
        return tid

    def test_trace_exists(self, trace_id):
        result = assert_trace_exists(trace_id)
        assert result.passed, result.details

    def test_tool_called_observation(self, trace_id):
        from tests.synthetic.blackbox.dataset import ExpectedObservation
        results = assert_observations_present(
            trace_id, [ExpectedObservation(name="tool.called", observation_type="tool")]
        )
        assert all(r.passed for r in results), "\n".join(
            r.description for r in results if not r.passed
        )

    def test_compliance_dataset_item(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S2]
        result = assert_dataset_item_exists(trace_id, scenario.compliance)
        assert result.passed, result.details


# ─────────────────────────────────────────────────────────────────────
# S3: Tool error + recovery
# ─────────────────────────────────────────────────────────────────────


class TestS3ErrorRecovery:
    """S3: ERROR_OCCURRED fires on tool failure, then agent recovers."""

    @pytest.fixture(scope="class")
    def trace_id(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S3]
        tid = event_loop.run_until_complete(_drive_scenario(bff_client, scenario))
        time.sleep(RELAY_FLUSH_WAIT_S)
        return tid

    def test_trace_exists(self, trace_id):
        result = assert_trace_exists(trace_id)
        assert result.passed, result.details

    def test_error_occurred_observation(self, trace_id):
        from tests.synthetic.blackbox.dataset import ExpectedObservation
        results = assert_observations_present(
            trace_id,
            [ExpectedObservation(name="error.occurred", observation_type="span", level="ERROR")],
        )
        assert all(r.passed for r in results), "\n".join(
            r.description for r in results if not r.passed
        )

    def test_task_still_completes(self, trace_id):
        from tests.synthetic.blackbox.dataset import ExpectedObservation
        results = assert_observations_present(
            trace_id,
            [ExpectedObservation(name="task.completed", observation_type="agent")],
        )
        assert all(r.passed for r in results)

    def test_hash_chain_valid(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S3]
        result = assert_compliance_score(trace_id, scenario.compliance)
        assert result.passed, result.details


# ─────────────────────────────────────────────────────────────────────
# S4: Routing tier change
# ─────────────────────────────────────────────────────────────────────


class TestS4RoutingTierChange:
    """S4: Complex task triggers PARAMETER_CHANGED for model escalation."""

    @pytest.fixture(scope="class")
    def trace_id(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S4]
        tid = event_loop.run_until_complete(_drive_scenario(bff_client, scenario))
        time.sleep(RELAY_FLUSH_WAIT_S)
        return tid

    def test_trace_exists(self, trace_id):
        result = assert_trace_exists(trace_id)
        assert result.passed, result.details

    def test_parameter_changed_observation(self, trace_id):
        """PARAMETER_CHANGED may not always fire (depends on router heuristics)."""
        from tests.synthetic.blackbox.dataset import ExpectedObservation
        results = assert_observations_present(
            trace_id,
            [ExpectedObservation(name="parameter.changed", observation_type="span")],
        )
        if not all(r.passed for r in results):
            pytest.xfail(
                "PARAMETER_CHANGED not emitted — router did not escalate "
                "(acceptable; depends on task complexity heuristics)"
            )

    def test_compliance_dataset_item(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S4]
        result = assert_dataset_item_exists(trace_id, scenario.compliance)
        assert result.passed, result.details


# ─────────────────────────────────────────────────────────────────────
# S5: Forced failing workflow
# ─────────────────────────────────────────────────────────────────────


class TestS5ForcedFailure:
    """S5: Workflow failure → agent-incident-replay dataset."""

    @pytest.fixture(scope="class")
    def trace_id(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S5]
        tid = event_loop.run_until_complete(_drive_scenario(bff_client, scenario))
        time.sleep(RELAY_FLUSH_WAIT_S)
        return tid

    def test_trace_exists(self, trace_id):
        result = assert_trace_exists(trace_id)
        assert result.passed, result.details

    def test_task_completed_present(self, trace_id):
        from tests.synthetic.blackbox.dataset import ExpectedObservation
        results = assert_observations_present(
            trace_id,
            [ExpectedObservation(name="task.completed", observation_type="agent")],
        )
        assert all(r.passed for r in results)

    def test_incident_replay_dataset(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S5]
        result = assert_dataset_item_exists(trace_id, scenario.compliance)
        assert result.passed, result.details

    def test_hash_chain_valid_score(self, trace_id):
        """Chain is valid even for failed tasks (integrity != success)."""
        scenario = ALL_SCENARIOS[ScenarioID.S5]
        result = assert_compliance_score(trace_id, scenario.compliance)
        assert result.passed, result.details


# ─────────────────────────────────────────────────────────────────────
# S6: PII/API-key redaction
# ─────────────────────────────────────────────────────────────────────


class TestS6Redaction:
    """S6: PII and API keys are redacted in Langfuse observations."""

    @pytest.fixture(scope="class")
    def trace_id(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S6]
        tid = event_loop.run_until_complete(_drive_scenario(bff_client, scenario))
        time.sleep(RELAY_FLUSH_WAIT_S)
        return tid

    def test_trace_exists(self, trace_id):
        result = assert_trace_exists(trace_id)
        assert result.passed, result.details

    def test_pii_not_in_metadata(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S6]
        results = assert_no_redacted_content(
            trace_id, scenario.redaction_assertions
        )
        failures = [r for r in results if not r.passed]
        assert not failures, "\n".join(f.description for f in failures)

    def test_compliance_dataset_item(self, trace_id):
        scenario = ALL_SCENARIOS[ScenarioID.S6]
        result = assert_dataset_item_exists(trace_id, scenario.compliance)
        assert result.passed, result.details


# ─────────────────────────────────────────────────────────────────────
# S8: Two concurrent workflows — isolation
# ─────────────────────────────────────────────────────────────────────


class TestS8ConcurrentIsolation:
    """S8: Two concurrent workflows produce independent traces."""

    @pytest.fixture(scope="class")
    def trace_ids(self, bff_client, event_loop):
        scenario = ALL_SCENARIOS[ScenarioID.S8]

        async def _run_both():
            results = await asyncio.gather(
                _drive_scenario(bff_client, scenario),
                _drive_scenario(bff_client, scenario),
            )
            return results

        ids = event_loop.run_until_complete(_run_both())
        time.sleep(RELAY_FLUSH_WAIT_S)
        return ids

    def test_distinct_trace_ids(self, trace_ids):
        assert trace_ids[0] != trace_ids[1], "Concurrent runs must have distinct traces"

    def test_both_traces_exist(self, trace_ids):
        for tid in trace_ids:
            result = assert_trace_exists(tid)
            assert result.passed, f"Trace {tid}: {result.details}"

    def test_independent_observations(self, trace_ids):
        scenario = ALL_SCENARIOS[ScenarioID.S8]
        for tid in trace_ids:
            results = assert_observations_present(
                tid, scenario.expected_observations
            )
            failures = [r for r in results if not r.passed]
            assert not failures, (
                f"Trace {tid}: " + "\n".join(f.description for f in failures)
            )

    def test_independent_compliance_items(self, trace_ids):
        scenario = ALL_SCENARIOS[ScenarioID.S8]
        for tid in trace_ids:
            result = assert_dataset_item_exists(tid, scenario.compliance)
            assert result.passed, f"Trace {tid}: {result.details}"


# ─────────────────────────────────────────────────────────────────────
# Phase 5 — Cross-scenario compliance dataset integrity
# ─────────────────────────────────────────────────────────────────────


class TestPhase5ComplianceDatasets:
    """Phase 5: Verify compliance datasets contain correct items and scores.

    Asserts:
      - agent-compliance-audit has items for S1, S2, S3, S4, S6, S8
        with hash_chain_valid=1.0
      - agent-incident-replay has the S5 item
    """

    @pytest.fixture(scope="class")
    def trace_map(self, bff_client, event_loop):
        """Run all scenarios and collect trace_id mapping."""
        _skip_if_missing_env()

        async def _run_all():
            results: dict[str, str] = {}
            for sid in SCENARIO_ORDER:
                scenario = ALL_SCENARIOS[sid]
                if sid == ScenarioID.S8:
                    tid_a = await _drive_scenario(bff_client, scenario)
                    tid_b = await _drive_scenario(bff_client, scenario)
                    results["S8-A"] = tid_a
                    results["S8-B"] = tid_b
                else:
                    tid = await _drive_scenario(bff_client, scenario)
                    results[sid.value] = tid
            return results

        ids = event_loop.run_until_complete(_run_all())
        time.sleep(RELAY_FLUSH_WAIT_S + 5)
        return ids

    def test_audit_dataset_has_s1(self, trace_map):
        result = assert_dataset_item_exists(
            trace_map["S1"], ALL_SCENARIOS[ScenarioID.S1].compliance
        )
        assert result.passed, result.details

    def test_audit_dataset_has_s2(self, trace_map):
        result = assert_dataset_item_exists(
            trace_map["S2"], ALL_SCENARIOS[ScenarioID.S2].compliance
        )
        assert result.passed, result.details

    def test_audit_dataset_has_s3(self, trace_map):
        result = assert_dataset_item_exists(
            trace_map["S3"], ALL_SCENARIOS[ScenarioID.S3].compliance
        )
        assert result.passed, result.details

    def test_audit_dataset_has_s4(self, trace_map):
        result = assert_dataset_item_exists(
            trace_map["S4"], ALL_SCENARIOS[ScenarioID.S4].compliance
        )
        assert result.passed, result.details

    def test_audit_dataset_has_s6(self, trace_map):
        result = assert_dataset_item_exists(
            trace_map["S6"], ALL_SCENARIOS[ScenarioID.S6].compliance
        )
        assert result.passed, result.details

    def test_audit_dataset_has_s8_both(self, trace_map):
        for key in ("S8-A", "S8-B"):
            result = assert_dataset_item_exists(
                trace_map[key], ALL_SCENARIOS[ScenarioID.S8].compliance
            )
            assert result.passed, f"{key}: {result.details}"

    def test_incident_replay_has_s5(self, trace_map):
        result = assert_dataset_item_exists(
            trace_map["S5"], ALL_SCENARIOS[ScenarioID.S5].compliance
        )
        assert result.passed, result.details

    def test_hash_chain_valid_scores_audit(self, trace_map):
        """All audit scenarios must have hash_chain_valid=1.0."""
        audit_keys = ["S1", "S2", "S3", "S4", "S6", "S8-A", "S8-B"]
        for key in audit_keys:
            sid = ScenarioID(key.split("-")[0])
            scenario = ALL_SCENARIOS[sid]
            result = assert_compliance_score(trace_map[key], scenario.compliance)
            assert result.passed, f"{key}: {result.description}"

    def test_hash_chain_valid_score_incident(self, trace_map):
        """S5 also has hash_chain_valid=1.0 (integrity != task success)."""
        result = assert_compliance_score(
            trace_map["S5"], ALL_SCENARIOS[ScenarioID.S5].compliance
        )
        assert result.passed, result.description

    def test_aggregate_compliance_report(self, trace_map):
        """Run the full Phase 5 verify_compliance_datasets aggregate check."""
        report = verify_compliance_datasets(trace_map)
        failures = [
            r for r in report.audit_results + report.incident_results
            if not r.passed
        ]
        assert not failures, (
            f"Phase 5 compliance failures:\n"
            + "\n".join(f"  - {f.description}" for f in failures)
        )
