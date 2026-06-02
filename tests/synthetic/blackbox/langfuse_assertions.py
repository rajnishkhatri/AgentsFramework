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
    PhaseExpectation,
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
# Phase 5 — Negative-path bundle assertions (G7/G8/G9)
#
# These operate on a *compliance bundle* (the dict published as a dataset
# item's ``input_data``), not on a live Langfuse query, so they are reusable
# by the deterministic L2 relay contract test and zero-flake in CI. They prove
# the gate-failure modes a pristine dataset would otherwise hide (TAP-4).
# ─────────────────────────────────────────────────────────────────────


def _bundle_events(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    events = bundle.get("events")
    return events if isinstance(events, list) else []


def _last_terminal_details(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return the chronologically last ``task_completed`` event's details."""
    details: dict[str, Any] = {}
    for ev in _bundle_events(bundle):
        if ev.get("event_type") == "task_completed":
            details = ev.get("details") or {}
    return details


def assert_broken_chain_bundle(bundle: dict[str, Any]) -> list[AssertionResult]:
    """G8: a tampered chain must report ``hash_chain_valid=False`` and name the
    first broken event so an auditor can jump straight to the tamper point."""
    results: list[AssertionResult] = []

    chain_valid = bundle.get("hash_chain_valid")
    results.append(AssertionResult(
        passed=chain_valid is False,
        description=f"hash_chain_valid is False (got {chain_valid!r})",
    ))

    broken_at = bundle.get("broken_at_event_id")
    results.append(AssertionResult(
        passed=bool(broken_at),
        description=(
            f"broken_at_event_id populated ({broken_at!r})"
            if broken_at
            else "broken_at_event_id MISSING on a broken chain"
        ),
    ))
    return results


def assert_rejected_outcome(
    bundle: dict[str, Any],
    expected_reason: str | None = None,
) -> list[AssertionResult]:
    """G7: a rejected terminal outcome must surface in the summary block so a
    reviewer sees the gate fired without walking ``events[]``."""
    results: list[AssertionResult] = []
    summary = bundle.get("summary") or {}

    outcome = summary.get("outcome")
    results.append(AssertionResult(
        passed=outcome == "rejected",
        description=f"summary.outcome == 'rejected' (got {outcome!r})",
    ))

    if expected_reason is not None:
        reason = summary.get("reason")
        results.append(AssertionResult(
            passed=reason == expected_reason,
            description=f"summary.reason == {expected_reason!r} (got {reason!r})",
        ))
    return results


def assert_error_trace_present(
    bundle: dict[str, Any],
    expected_error_types: list[str] | tuple[str, ...] = (),
) -> list[AssertionResult]:
    """G9: an ``error.occurred`` event must exist and the terminal event must
    carry a non-null ``error_type`` (optionally one of *expected_error_types*)."""
    results: list[AssertionResult] = []

    error_events = [
        ev for ev in _bundle_events(bundle)
        if ev.get("event_type") == "error_occurred"
    ]
    results.append(AssertionResult(
        passed=len(error_events) >= 1,
        description=f"error.occurred present ({len(error_events)} event(s))",
    ))

    error_type = _last_terminal_details(bundle).get("error_type")
    results.append(AssertionResult(
        passed=error_type is not None,
        description=f"terminal error_type non-null (got {error_type!r})",
    ))

    if expected_error_types:
        results.append(AssertionResult(
            passed=error_type in expected_error_types,
            description=(
                f"terminal error_type in {list(expected_error_types)} "
                f"(got {error_type!r})"
            ),
        ))
    return results


def assert_bundle_event_types(
    bundle: dict[str, Any],
    expected: list[ExpectedObservation],
) -> list[AssertionResult]:
    """Assert every expected observation maps to an event type in the bundle.

    Observation names (``error.occurred``) map to event_type values
    (``error_occurred``) by swapping ``.`` for ``_`` — the inverse of the
    publisher's ``_EVENT_TYPE_TO_OBSERVATION`` table.
    """
    results: list[AssertionResult] = []
    present = {ev.get("event_type") for ev in _bundle_events(bundle)}
    for exp in expected:
        event_type = exp.name.replace(".", "_")
        results.append(AssertionResult(
            passed=event_type in present,
            description=(
                f"event_type '{event_type}' present"
                if event_type in present
                else f"event_type '{event_type}' MISSING (have {sorted(present)})"
            ),
        ))
    return results


def assert_dataset_routing(
    dataset_name: str,
    expected: ComplianceExpectation,
) -> AssertionResult:
    """Assert the bundle was published to the dataset the scenario expects."""
    return AssertionResult(
        passed=dataset_name == expected.dataset_name,
        description=(
            f"routed to '{dataset_name}' (expected '{expected.dataset_name}')"
        ),
    )


# ─────────────────────────────────────────────────────────────────────
# Phase 3 — PhaseLogger (Reasoning pillar) bundle assertions
#
# The phase track (``phase_events[]`` / ``phase_decisions[]``) is published
# inside the compliance dataset item's ``input_data``, NOT as live
# observations. These assertions therefore operate on a bundle dict so they
# are reusable by both the live driver (after fetching the item) and any
# deterministic test that builds a bundle directly.
# ─────────────────────────────────────────────────────────────────────


def fetch_compliance_bundle(
    trace_id: str,
    dataset_names: tuple[str, ...] = (AUDIT_DATASET, INCIDENT_DATASET),
) -> dict[str, Any] | None:
    """Return the published compliance bundle (dataset item ``input``) for a trace."""
    for ds in dataset_names:
        for item in fetch_dataset_items(ds):
            if _item_matches(item, trace_id):
                if isinstance(item, dict):
                    inp = item.get("input")
                else:
                    inp = getattr(item, "input", None)
                if isinstance(inp, dict):
                    return inp
    return None


def _bundle_phase_events(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    events = bundle.get("phase_events")
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


def _bundle_phase_decisions(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    decisions = bundle.get("phase_decisions")
    return [d for d in decisions if isinstance(d, dict)] if isinstance(decisions, list) else []


def _phase_ends(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in _bundle_phase_events(bundle) if e.get("event") == "phase_end"]


def assert_phase_schema_versions(bundle: dict[str, Any]) -> list[AssertionResult]:
    """``phase_log_schema_version='1'`` is present and ``bundle_schema_version``
    is still ``'2'`` (phase versioning never forces a bundle bump)."""
    results: list[AssertionResult] = []
    plv = bundle.get("phase_log_schema_version")
    results.append(AssertionResult(
        passed=plv == "1",
        description=f"phase_log_schema_version == '1' (got {plv!r})",
    ))
    bsv = bundle.get("bundle_schema_version")
    results.append(AssertionResult(
        passed=bsv == "2",
        description=f"bundle_schema_version == '2' (got {bsv!r})",
    ))
    return results


def assert_phase_ends_present(
    bundle: dict[str, Any],
    expected_phases: tuple[str, ...],
) -> list[AssertionResult]:
    """Every expected phase has at least one ``phase_end`` row with ``duration_ms``."""
    results: list[AssertionResult] = []
    ends = _phase_ends(bundle)
    ended = {e.get("phase") for e in ends}
    for phase in expected_phases:
        present = phase in ended
        results.append(AssertionResult(
            passed=present,
            description=(
                f"phase_end for '{phase}' present"
                if present
                else f"phase_end for '{phase}' MISSING (have {sorted(ended)})"
            ),
        ))
    # Durations are non-negative where present.
    bad_durations = [
        e for e in ends
        if "duration_ms" in e and (not isinstance(e["duration_ms"], int) or e["duration_ms"] < 0)
    ]
    results.append(AssertionResult(
        passed=not bad_durations,
        description=(
            "all phase_end duration_ms >= 0"
            if not bad_durations
            else f"{len(bad_durations)} phase_end row(s) with invalid duration_ms"
        ),
    ))
    return results


def assert_no_phase_ends(
    bundle: dict[str, Any],
    forbidden_phases: tuple[str, ...],
) -> list[AssertionResult]:
    """Negative check: none of *forbidden_phases* produced a ``phase_end``."""
    results: list[AssertionResult] = []
    ended = {e.get("phase") for e in _phase_ends(bundle)}
    for phase in forbidden_phases:
        absent = phase not in ended
        results.append(AssertionResult(
            passed=absent,
            description=(
                f"no '{phase}' phase_end (as expected)"
                if absent
                else f"UNEXPECTED '{phase}' phase_end present"
            ),
        ))
    return results


def assert_phase_outcomes(
    bundle: dict[str, Any],
    pairs: tuple[tuple[str, str], ...],
) -> list[AssertionResult]:
    """Each ``(phase, outcome)`` pair appears on some ``phase_end`` row."""
    results: list[AssertionResult] = []
    ends = _phase_ends(bundle)
    for phase, outcome in pairs:
        found = any(
            e.get("phase") == phase and e.get("outcome") == outcome for e in ends
        )
        results.append(AssertionResult(
            passed=found,
            description=(
                f"phase '{phase}' ended with outcome '{outcome}'"
                if found
                else f"phase '{phase}' never ended with outcome '{outcome}'"
            ),
        ))
    return results


def assert_completion_fires_once(
    bundle: dict[str, Any],
    expected_count: int | None = 1,
    expected_outcome: str | None = None,
) -> list[AssertionResult]:
    """COMPLETION single-flight: exactly *expected_count* ``completion``
    ``phase_end`` rows, optionally with *expected_outcome*."""
    results: list[AssertionResult] = []
    completion_ends = [e for e in _phase_ends(bundle) if e.get("phase") == "completion"]

    if expected_count is not None:
        results.append(AssertionResult(
            passed=len(completion_ends) == expected_count,
            description=(
                f"COMPLETION phase_end count == {expected_count} "
                f"(got {len(completion_ends)})"
            ),
        ))

    if expected_outcome is not None:
        outcomes = {e.get("outcome") for e in completion_ends}
        results.append(AssertionResult(
            passed=outcomes == {expected_outcome},
            description=(
                f"COMPLETION outcome == '{expected_outcome}' (got {sorted(outcomes)})"
            ),
        ))
    return results


def assert_routing_step_counts(
    bundle: dict[str, Any],
    expected_step_counts: tuple[int, ...],
) -> list[AssertionResult]:
    """Per-step keying: each expected ``step_count`` has its own ``routing``
    ``phase_end`` (step 0 and step 1 are independent, not one overwritten span)."""
    results: list[AssertionResult] = []
    routing_steps = {
        e.get("step_count")
        for e in _phase_ends(bundle)
        if e.get("phase") == "routing"
    }
    for sc in expected_step_counts:
        present = sc in routing_steps
        results.append(AssertionResult(
            passed=present,
            description=(
                f"routing phase_end at step_count={sc} present"
                if present
                else f"routing phase_end at step_count={sc} MISSING "
                f"(have {sorted(s for s in routing_steps if s is not None)})"
            ),
        ))
    return results


def assert_unique_decision_ids(bundle: dict[str, Any]) -> AssertionResult:
    """No duplicate ``decision_id`` across ``phase_decisions[]`` in a workflow."""
    ids = [d.get("decision_id") for d in _bundle_phase_decisions(bundle) if d.get("decision_id")]
    unique = len(ids) == len(set(ids))
    return AssertionResult(
        passed=unique,
        description=(
            f"decision_ids unique ({len(ids)} rows)"
            if unique
            else f"DUPLICATE decision_id across {len(ids)} rows: {ids}"
        ),
    )


def assert_decision_id_join(bundle: dict[str, Any]) -> AssertionResult:
    """Cross-pillar join: the routing decision's ``decision_id`` equals the
    ``MODEL_SELECTED`` event's ``details.decision_id``."""
    routing = [
        d for d in _bundle_phase_decisions(bundle) if d.get("phase") == "routing"
    ]
    if not routing or not routing[0].get("decision_id"):
        return AssertionResult(
            passed=False,
            description="no routing decision with a decision_id in phase_decisions[]",
        )
    decision_id = routing[0]["decision_id"]

    model_selected = [
        ev for ev in _bundle_events(bundle)
        if ev.get("event_type") == "model_selected"
    ]
    event_ids = {
        (ev.get("details") or {}).get("decision_id") for ev in model_selected
    }
    matched = decision_id in event_ids
    return AssertionResult(
        passed=matched,
        description=(
            f"decision_id {decision_id!r} joins routing decision to MODEL_SELECTED"
            if matched
            else f"decision_id {decision_id!r} NOT found on any MODEL_SELECTED "
            f"event (have {sorted(i for i in event_ids if i)})"
        ),
    )


def assert_no_phase_pii(
    bundle: dict[str, Any],
    forbidden_strings: tuple[str, ...],
) -> list[AssertionResult]:
    """No raw PII/key appears anywhere in the serialized phase track."""
    import json

    serialized = json.dumps(
        {
            "phase_events": _bundle_phase_events(bundle),
            "phase_decisions": _bundle_phase_decisions(bundle),
        },
        default=str,
    )
    results: list[AssertionResult] = []
    for forbidden in forbidden_strings:
        leaked = forbidden in serialized
        results.append(AssertionResult(
            passed=not leaked,
            description=(
                f"phase track redacted: '{forbidden[:30]}...' NOT present"
                if not leaked
                else f"REDACTION FAILURE: '{forbidden[:30]}...' in phase track"
            ),
        ))
    return results


def verify_phase_expectation(
    bundle: dict[str, Any],
    phase: PhaseExpectation,
) -> list[AssertionResult]:
    """Run every configured phase assertion against a compliance bundle."""
    results: list[AssertionResult] = []
    results.extend(assert_phase_schema_versions(bundle))

    if phase.expected_phase_ends:
        results.extend(assert_phase_ends_present(bundle, phase.expected_phase_ends))
    if phase.forbidden_phase_ends:
        results.extend(assert_no_phase_ends(bundle, phase.forbidden_phase_ends))
    if phase.expected_phase_outcomes:
        results.extend(assert_phase_outcomes(bundle, phase.expected_phase_outcomes))
    if phase.expected_completion_count is not None or phase.expected_completion_outcome is not None:
        results.extend(assert_completion_fires_once(
            bundle,
            expected_count=phase.expected_completion_count,
            expected_outcome=phase.expected_completion_outcome,
        ))
    if phase.expected_routing_step_counts:
        results.extend(assert_routing_step_counts(bundle, phase.expected_routing_step_counts))
    if phase.require_unique_decision_ids:
        results.append(assert_unique_decision_ids(bundle))
    if phase.check_decision_id_join:
        results.append(assert_decision_id_join(bundle))
    if phase.phase_redaction_forbidden:
        results.extend(assert_no_phase_pii(bundle, phase.phase_redaction_forbidden))
    return results


def verify_phase_scenario(
    scenario: Scenario,
    trace_id: str,
    bundle: dict[str, Any] | None = None,
) -> ScenarioVerification:
    """Verify a Phase 3 scenario.

    Runs the base live-observation assertions, then fetches the compliance
    bundle (unless *bundle* is supplied) and runs the phase-track assertions.
    """
    verification = ScenarioVerification(
        scenario_id=scenario.id.value,
        trace_id=trace_id,
    )

    verification.assertions.append(assert_trace_exists(trace_id))
    if verification.assertions[0].passed:
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

    if scenario.phase is not None:
        if bundle is None:
            bundle = fetch_compliance_bundle(
                trace_id,
                dataset_names=(scenario.compliance.dataset_name, AUDIT_DATASET, INCIDENT_DATASET),
            )
        if bundle is None:
            verification.assertions.append(AssertionResult(
                passed=False,
                description="compliance bundle (dataset item input) NOT found",
                details="phase-track assertions skipped — is the relay/publisher running?",
            ))
        else:
            verification.assertions.extend(
                verify_phase_expectation(bundle, scenario.phase)
            )

    return verification


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

    if scenario.phase is not None:
        lines.extend(_phase_checklist_lines(scenario.phase, scenario.compliance.dataset_name))

    if scenario.notes:
        lines.append("")
        lines.append(f"### Notes:")
        lines.append(f"  {scenario.notes}")

    checklist = "\n".join(lines)
    return checklist


def _phase_checklist_lines(phase: PhaseExpectation, dataset_name: str) -> list[str]:
    """Render the Reasoning-pillar (phase track) checklist for a scenario.

    The phase track lives in the dataset item's ``input_data`` JSON, not in
    live observations — the checklist points the reviewer there.
    """
    lines = [
        "",
        "### Reasoning pillar (phase track):",
        f"  Open Datasets → `{dataset_name}` → item for this trace → inspect `input_data`.",
        "- [ ] `phase_log_schema_version` == `1` and `bundle_schema_version` == `2`",
    ]
    for ph in phase.expected_phase_ends:
        lines.append(f"- [ ] `phase_events[]` has a `phase_end` for `{ph}`")
    for ph in phase.forbidden_phase_ends:
        lines.append(f"- [ ] `phase_events[]` has NO `phase_end` for `{ph}`")
    for ph, outcome in phase.expected_phase_outcomes:
        lines.append(f"- [ ] `{ph}` `phase_end` has `outcome` == `{outcome}`")
    if phase.expected_completion_count is not None:
        lines.append(
            f"- [ ] exactly `{phase.expected_completion_count}` `completion` `phase_end` row(s)"
        )
    if phase.expected_completion_outcome is not None:
        lines.append(
            f"- [ ] `completion` `phase_end` `outcome` == `{phase.expected_completion_outcome}`"
        )
    for sc in phase.expected_routing_step_counts:
        lines.append(f"- [ ] independent `routing` `phase_end` at `step_count` == `{sc}`")
    if phase.require_unique_decision_ids:
        lines.append("- [ ] every `phase_decisions[]` row has a distinct `decision_id`")
    if phase.check_decision_id_join:
        lines.append(
            "- [ ] routing `decision_id` matches `model.selected` `details.decision_id`"
        )
    for secret in phase.phase_redaction_forbidden:
        lines.append(f"- [ ] `{secret[:40]}...` is NOT in `phase_events[]`/`phase_decisions[]`")
    return lines


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
