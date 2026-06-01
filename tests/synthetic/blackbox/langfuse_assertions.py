"""Langfuse API query and assertion helpers for BlackBox E2E validation.

Queries the Langfuse REST API (via the Python SDK) to verify that
BlackBox events were correctly exported as traces, observations, scores,
and dataset items.

Designed to work against Langfuse Cloud (https://cloud.langfuse.com)
with LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST set.

Used by:
  - scripts/validate_blackbox_langfuse.py (CLI driver)
  - tests/integration/test_blackbox_langfuse_gcp.py (pytest harness)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

from tests.synthetic.blackbox.dataset import (
    ComplianceExpectation,
    ExpectedObservation,
    Scenario,
    ScenarioID,
)

LANGFUSE_POLL_INTERVAL_S = 2.0
LANGFUSE_POLL_MAX_ATTEMPTS = 15


@dataclass
class AssertionResult:
    """Result of a single assertion check."""

    passed: bool
    description: str
    details: str = ""


@dataclass
class ScenarioVerification:
    """Full verification result for a scenario."""

    scenario_id: str
    trace_id: str
    assertions: list[AssertionResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(a.passed for a in self.assertions)

    @property
    def summary(self) -> str:
        passed = sum(1 for a in self.assertions if a.passed)
        total = len(self.assertions)
        status = "PASS" if self.all_passed else "FAIL"
        return f"[{status}] {self.scenario_id}: {passed}/{total} assertions passed"


def _get_langfuse_client():
    """Build a Langfuse client from environment variables."""
    try:
        from langfuse import Langfuse
    except ImportError as exc:
        raise RuntimeError(
            "langfuse package required for assertions. Install with: "
            "pip install langfuse"
        ) from exc

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = (
        os.environ.get("LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    )

    if not public_key or not secret_key:
        raise RuntimeError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set"
        )

    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def poll_trace(
    trace_id: str,
    *,
    max_attempts: int = LANGFUSE_POLL_MAX_ATTEMPTS,
    interval_s: float = LANGFUSE_POLL_INTERVAL_S,
) -> dict[str, Any] | None:
    """Poll Langfuse until a trace with the given ID appears.

    Returns the trace as a dict or None if not found after max_attempts.
    Uses the v4 SDK API (client.api.trace.get).
    """
    client = _get_langfuse_client()
    for attempt in range(max_attempts):
        try:
            trace = client.api.trace.get(trace_id)
            if trace and trace.id:
                return trace.__dict__ if hasattr(trace, "__dict__") else {"id": trace.id}
        except Exception:
            pass
        if attempt < max_attempts - 1:
            time.sleep(interval_s)
    return None


def _to_dict(obj: Any) -> dict[str, Any]:
    """Normalise a Langfuse SDK model or plain dict to a dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return {}


def fetch_trace_details(trace_id: str) -> dict[str, Any] | None:
    """Fetch a trace with embedded observations and scores.

    Langfuse SDK v4 ``observations.get_many()`` returns ``ObservationV2``
    rows whose ``name`` / ``level`` / ``input`` fields are often null in the
    list response. ``trace.get()`` embeds the full observation payloads the
    BlackBox assertions expect (``task.started``, ``guardrail.checked``, …).
    """
    client = _get_langfuse_client()
    try:
        trace = client.api.trace.get(trace_id)
        if trace and getattr(trace, "id", None):
            return _to_dict(trace)
    except Exception:
        pass
    return None


def fetch_trace_observations(trace_id: str) -> list[dict[str, Any]]:
    """Fetch all observations for a given trace_id via v4 SDK API."""
    trace = fetch_trace_details(trace_id)
    if trace and trace.get("observations"):
        return [_to_dict(obs) for obs in trace["observations"]]

    # Fallback: list API (names may be absent on v2 list rows).
    client = _get_langfuse_client()
    try:
        resp = client.api.observations.get_many(trace_id=trace_id, limit=100)
        if resp and resp.data:
            return [_to_dict(obs) for obs in resp.data]
    except Exception:
        pass
    return []


def fetch_trace_scores(trace_id: str) -> list[dict[str, Any]]:
    """Fetch all scores attached to a trace via v4 SDK API."""
    trace = fetch_trace_details(trace_id)
    if trace and trace.get("scores"):
        return [_to_dict(s) for s in trace["scores"]]

    client = _get_langfuse_client()
    try:
        resp = client.api.scores.get_many(trace_id=trace_id, limit=100)
        if resp and resp.data:
            return [_to_dict(s) for s in resp.data]
    except Exception:
        pass
    return []


def fetch_dataset_items(dataset_name: str) -> list[dict[str, Any]]:
    """Fetch items from a named Langfuse dataset via v4 SDK API."""
    client = _get_langfuse_client()
    try:
        resp = client.api.dataset_items.list(dataset_name=dataset_name, limit=100)
        if resp and resp.data:
            return [
                item.__dict__ if hasattr(item, "__dict__") else item
                for item in resp.data
            ]
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────────────────────────────
# Assertion functions
# ─────────────────────────────────────────────────────────────────────


def assert_trace_exists(trace_id: str) -> AssertionResult:
    """Assert that a trace with the given ID exists in Langfuse."""
    trace = poll_trace(trace_id)
    if trace is not None:
        return AssertionResult(
            passed=True,
            description=f"Trace {trace_id} exists in Langfuse",
        )
    return AssertionResult(
        passed=False,
        description=f"Trace {trace_id} NOT found in Langfuse",
        details=f"Polled {LANGFUSE_POLL_MAX_ATTEMPTS} times at "
        f"{LANGFUSE_POLL_INTERVAL_S}s intervals",
    )


def assert_observations_present(
    trace_id: str,
    expected: list[ExpectedObservation],
) -> list[AssertionResult]:
    """Assert that all expected observations exist under the trace."""
    results: list[AssertionResult] = []
    observations = fetch_trace_observations(trace_id)
    obs_names = {_get_obs_name(obs) for obs in observations}
    obs_by_name: dict[str, list[dict]] = {}
    for obs in observations:
        name = _get_obs_name(obs)
        obs_by_name.setdefault(name, []).append(obs)

    for exp in expected:
        if exp.name in obs_names:
            matching = obs_by_name.get(exp.name, [])
            type_match = any(
                _get_obs_type(obs) == exp.observation_type for obs in matching
            )
            level_match = True
            if exp.level != "DEFAULT":
                level_match = any(
                    _get_obs_level(obs) == exp.level for obs in matching
                )

            if type_match and level_match:
                results.append(AssertionResult(
                    passed=True,
                    description=f"Observation '{exp.name}' (type={exp.observation_type}, "
                    f"level={exp.level}) present",
                ))
            else:
                details_parts = []
                if not type_match:
                    actual_types = [_get_obs_type(o) for o in matching]
                    details_parts.append(
                        f"expected type={exp.observation_type}, got {actual_types}"
                    )
                if not level_match:
                    actual_levels = [_get_obs_level(o) for o in matching]
                    details_parts.append(
                        f"expected level={exp.level}, got {actual_levels}"
                    )
                results.append(AssertionResult(
                    passed=False,
                    description=f"Observation '{exp.name}' type/level mismatch",
                    details="; ".join(details_parts),
                ))
        else:
            results.append(AssertionResult(
                passed=False,
                description=f"Observation '{exp.name}' MISSING from trace",
                details=f"Found observations: {sorted(obs_names)}",
            ))

    return results


def poll_for_observation(
    trace_id: str,
    observation_name: str,
    *,
    max_attempts: int = LANGFUSE_POLL_MAX_ATTEMPTS,
    interval_s: float = LANGFUSE_POLL_INTERVAL_S,
) -> bool:
    """Poll until an observation with *observation_name* appears on the trace."""
    for attempt in range(max_attempts):
        observations = fetch_trace_observations(trace_id)
        if any(_get_obs_name(obs) == observation_name for obs in observations):
            return True
        if attempt < max_attempts - 1:
            time.sleep(interval_s)
    return False


def assert_no_redacted_content(
    trace_id: str,
    forbidden_strings: list[str],
) -> list[AssertionResult]:
    """Assert that raw PII/key strings do NOT appear in observation bodies."""
    results: list[AssertionResult] = []
    observations = fetch_trace_observations(trace_id)
    all_metadata_str = _serialize_observations_metadata(observations)

    for forbidden in forbidden_strings:
        if forbidden in all_metadata_str:
            results.append(AssertionResult(
                passed=False,
                description=f"REDACTION FAILURE: '{forbidden[:30]}...' found in trace",
                details="Raw PII/API key leaked to Langfuse (input/output/metadata)",
            ))
        else:
            results.append(AssertionResult(
                passed=True,
                description=f"Redacted: '{forbidden[:30]}...' NOT in trace bodies",
            ))

    return results


def assert_compliance_score(
    trace_id: str,
    expected: ComplianceExpectation,
) -> AssertionResult:
    """Assert hash_chain_valid score matches expectation."""
    scores = fetch_trace_scores(trace_id)
    chain_scores = [
        s for s in scores
        if _get_score_name(s) == "hash_chain_valid"
    ]

    if not chain_scores:
        return AssertionResult(
            passed=False,
            description="hash_chain_valid score MISSING",
            details=f"Found scores: {[_get_score_name(s) for s in scores]}",
        )

    actual_value = _get_score_value(chain_scores[0])
    if actual_value == expected.hash_chain_valid_score:
        return AssertionResult(
            passed=True,
            description=f"hash_chain_valid={actual_value} (expected "
            f"{expected.hash_chain_valid_score})",
        )
    return AssertionResult(
        passed=False,
        description=f"hash_chain_valid={actual_value} (expected "
        f"{expected.hash_chain_valid_score})",
    )


def assert_dataset_item_exists(
    trace_id: str,
    expected: ComplianceExpectation,
) -> AssertionResult:
    """Assert that a dataset item exists for this trace in the expected dataset."""
    items = fetch_dataset_items(expected.dataset_name)
    matching = [
        item for item in items
        if _get_item_id(item) == trace_id
        or _item_has_workflow_id(item, trace_id)
    ]

    if matching:
        return AssertionResult(
            passed=True,
            description=f"Dataset item in '{expected.dataset_name}' for trace {trace_id}",
        )
    return AssertionResult(
        passed=False,
        description=f"Dataset item MISSING in '{expected.dataset_name}' for trace {trace_id}",
        details=f"Found {len(items)} total items in dataset",
    )


# ─────────────────────────────────────────────────────────────────────
# High-level verification
# ─────────────────────────────────────────────────────────────────────


def verify_scenario(
    scenario: Scenario,
    trace_id: str,
) -> ScenarioVerification:
    """Run all assertions for a scenario against a known trace_id."""
    verification = ScenarioVerification(
        scenario_id=scenario.id.value,
        trace_id=trace_id,
    )

    verification.assertions.append(assert_trace_exists(trace_id))

    if not verification.assertions[0].passed:
        return verification

    verification.assertions.extend(
        assert_observations_present(trace_id, scenario.expected_observations)
    )

    if scenario.redaction_assertions:
        verification.assertions.extend(
            assert_no_redacted_content(trace_id, scenario.redaction_assertions)
        )

    verification.assertions.append(
        assert_compliance_score(trace_id, scenario.compliance)
    )
    verification.assertions.append(
        assert_dataset_item_exists(trace_id, scenario.compliance)
    )

    return verification


# ─────────────────────────────────────────────────────────────────────
# Phase 5 — Cross-scenario compliance dataset + score verification
# ─────────────────────────────────────────────────────────────────────


AUDIT_DATASET = "agent-compliance-audit"
INCIDENT_DATASET = "agent-incident-replay"

AUDIT_SCENARIOS = {ScenarioID.S1, ScenarioID.S2, ScenarioID.S3, ScenarioID.S4, ScenarioID.S6, ScenarioID.S8}
INCIDENT_SCENARIOS = {ScenarioID.S5}


@dataclass
class ComplianceDatasetReport:
    """Aggregate Phase 5 report for compliance dataset verification."""

    audit_results: list[AssertionResult] = field(default_factory=list)
    incident_results: list[AssertionResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.audit_results + self.incident_results)

    @property
    def summary(self) -> str:
        total = len(self.audit_results) + len(self.incident_results)
        passed = sum(
            1 for r in self.audit_results + self.incident_results if r.passed
        )
        status = "PASS" if self.all_passed else "FAIL"
        return (
            f"[{status}] Phase 5 Compliance Datasets: {passed}/{total} checks passed"
        )


def verify_compliance_datasets(
    trace_map: dict[str, str],
) -> ComplianceDatasetReport:
    """Verify compliance datasets contain correct items and scores for all scenarios.

    Args:
        trace_map: Mapping of scenario ID string (e.g. "S1") to trace_id.
                   For S8, may contain "S8-A" and "S8-B" entries.

    Returns:
        ComplianceDatasetReport with per-item pass/fail results.
    """
    from tests.synthetic.blackbox.dataset import ALL_SCENARIOS, ScenarioID

    report = ComplianceDatasetReport()

    audit_items = fetch_dataset_items(AUDIT_DATASET)
    incident_items = fetch_dataset_items(INCIDENT_DATASET)

    for scenario_id in AUDIT_SCENARIOS:
        sid_str = scenario_id.value
        trace_ids_for_scenario = _resolve_trace_ids(trace_map, sid_str)

        if not trace_ids_for_scenario:
            report.audit_results.append(AssertionResult(
                passed=False,
                description=f"{sid_str}: No trace_id available (scenario not run?)",
            ))
            continue

        scenario = ALL_SCENARIOS[scenario_id]

        for tid in trace_ids_for_scenario:
            found = any(
                _item_matches(item, tid) for item in audit_items
            )
            report.audit_results.append(AssertionResult(
                passed=found,
                description=(
                    f"{sid_str}: Dataset item in '{AUDIT_DATASET}' for trace {tid}"
                    if found
                    else f"{sid_str}: Dataset item MISSING in '{AUDIT_DATASET}' for trace {tid}"
                ),
                details="" if found else f"{len(audit_items)} total items in dataset",
            ))

            scores = fetch_trace_scores(tid)
            chain_scores = [
                s for s in scores if _get_score_name(s) == "hash_chain_valid"
            ]
            if chain_scores:
                val = _get_score_value(chain_scores[0])
                expected = scenario.compliance.hash_chain_valid_score
                report.audit_results.append(AssertionResult(
                    passed=val == expected,
                    description=(
                        f"{sid_str}: hash_chain_valid={val} "
                        f"(expected {expected}) for trace {tid}"
                    ),
                ))
            else:
                report.audit_results.append(AssertionResult(
                    passed=False,
                    description=f"{sid_str}: hash_chain_valid score MISSING for trace {tid}",
                    details=f"Found scores: {[_get_score_name(s) for s in scores]}",
                ))

    for scenario_id in INCIDENT_SCENARIOS:
        sid_str = scenario_id.value
        trace_ids_for_scenario = _resolve_trace_ids(trace_map, sid_str)

        if not trace_ids_for_scenario:
            report.incident_results.append(AssertionResult(
                passed=False,
                description=f"{sid_str}: No trace_id available (scenario not run?)",
            ))
            continue

        for tid in trace_ids_for_scenario:
            found = any(
                _item_matches(item, tid) for item in incident_items
            )
            report.incident_results.append(AssertionResult(
                passed=found,
                description=(
                    f"{sid_str}: Dataset item in '{INCIDENT_DATASET}' for trace {tid}"
                    if found
                    else f"{sid_str}: Dataset item MISSING in '{INCIDENT_DATASET}' for trace {tid}"
                ),
                details="" if found else f"{len(incident_items)} total items in dataset",
            ))

    return report


def _resolve_trace_ids(trace_map: dict[str, str], scenario_id: str) -> list[str]:
    """Resolve trace_ids for a scenario, handling S8-A/S8-B split."""
    results: list[str] = []
    if scenario_id in trace_map:
        results.append(trace_map[scenario_id])
    suffixed = [k for k in trace_map if k.startswith(f"{scenario_id}-")]
    for key in sorted(suffixed):
        results.append(trace_map[key])
    return results


def _item_matches(item: Any, trace_id: str) -> bool:
    """Check if a dataset item corresponds to a trace_id."""
    if _get_item_id(item) == trace_id:
        return True
    return _item_has_workflow_id(item, trace_id)


# ─────────────────────────────────────────────────────────────────────
# UI Checklist printer
# ─────────────────────────────────────────────────────────────────────


def print_ui_checklist(scenario: Scenario, trace_id: str) -> str:
    """Generate a human-readable UI checklist for manual Langfuse verification.

    Returns the checklist text (also suitable for docs/runbook).
    """
    lines = [
        f"## UI Checklist — {scenario.id.value}: {scenario.description[:60]}",
        f"",
        f"**Trace ID:** `{trace_id}`",
        f"**Langfuse URL:** $LANGFUSE_HOST/trace/{trace_id}",
        f"",
        "### Observations to verify in Langfuse UI:",
        "",
    ]

    for i, obs in enumerate(scenario.expected_observations, 1):
        lines.append(
            f"- [ ] {i}. `{obs.name}` — type=`{obs.observation_type}`, level=`{obs.level}`"
        )

    lines.append("")
    lines.append("### Compliance checks:")
    lines.append(
        f"- [ ] Dataset: `{scenario.compliance.dataset_name}` contains item for this trace"
    )
    lines.append(
        f"- [ ] Score: `hash_chain_valid` = {scenario.compliance.hash_chain_valid_score}"
    )

    if scenario.redaction_assertions:
        lines.append("")
        lines.append("### Redaction checks (metadata must NOT contain):")
        for secret in scenario.redaction_assertions:
            lines.append(f"- [ ] `{secret[:40]}...` is NOT visible")

    if scenario.notes:
        lines.append("")
        lines.append(f"### Notes:")
        lines.append(f"  {scenario.notes}")

    checklist = "\n".join(lines)
    return checklist


# ─────────────────────────────────────────────────────────────────────
# Internal helpers — safe attribute access across SDK versions
# ─────────────────────────────────────────────────────────────────────


def _get_obs_name(obs: Any) -> str:
    if isinstance(obs, dict):
        return obs.get("name", "")
    return getattr(obs, "name", "")


def _get_obs_type(obs: Any) -> str:
    if isinstance(obs, dict):
        raw = obs.get("type", obs.get("observation_type", ""))
    else:
        raw = getattr(obs, "type", getattr(obs, "observation_type", ""))
    return str(raw).lower() if raw else ""


def _get_obs_level(obs: Any) -> str:
    if isinstance(obs, dict):
        raw = obs.get("level", "DEFAULT")
    else:
        raw = getattr(obs, "level", "DEFAULT")
    return str(raw).upper() if raw else "DEFAULT"


def _get_score_name(score: Any) -> str:
    if isinstance(score, dict):
        return score.get("name", "")
    return getattr(score, "name", "")


def _get_score_value(score: Any) -> float:
    if isinstance(score, dict):
        return float(score.get("value", 0.0))
    return float(getattr(score, "value", 0.0))


def _get_item_id(item: Any) -> str:
    if isinstance(item, dict):
        return item.get("id", "")
    return getattr(item, "id", "")


def _item_has_workflow_id(item: Any, workflow_id: str) -> bool:
    if isinstance(item, dict):
        metadata = item.get("metadata", {}) or {}
        input_data = item.get("input", {}) or {}
    else:
        metadata = getattr(item, "metadata", {}) or {}
        input_data = getattr(item, "input", {}) or {}
    return (
        metadata.get("workflow_id") == workflow_id
        or input_data.get("workflow_id") == workflow_id
    )


def _serialize_observations_metadata(observations: list[Any]) -> str:
    """Flatten observation metadata, input, and output into a searchable string."""
    import json

    parts: list[str] = []
    for obs in observations:
        if isinstance(obs, dict):
            metadata = obs.get("metadata", {})
            input_data = obs.get("input", {})
            output_data = obs.get("output", {})
        else:
            metadata = getattr(obs, "metadata", {})
            input_data = getattr(obs, "input", {})
            output_data = getattr(obs, "output", {})
        parts.append(json.dumps(metadata, default=str))
        parts.append(json.dumps(input_data, default=str))
        parts.append(json.dumps(output_data, default=str))
    return " ".join(parts)
