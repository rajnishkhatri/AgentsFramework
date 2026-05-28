"""tests/infra/gcp/test_observability.py — Recipe 7 observability tests.

Verifies the acceptance criteria for infra/gcp/observability.tf:

  * google_monitoring_dashboard.agent_tier_a with Tier A tiles
  * Three google_monitoring_alert_policy resources:
      - backend 5xx rate (ratio threshold)
      - backend p95 latency
      - Cloud SQL connections
  * google_billing_budget.tier_a gated on billing_account_id
  * monthly_budget_usd defaults to 50
  * Alert policies target agent-backend-combined and Cloud SQL instance
  * monitoring_dashboard_name + billing_budget_enabled outputs

Failure paths first (TAP-4 / AGENTS.md §Testing Anti-Patterns).
"""

from __future__ import annotations

import json

import pytest

from tests.infra._hcl_helpers import find_resources, get_one, unwrap_block


pytestmark = pytest.mark.infra_gcp

BACKEND_SERVICE = "agent-backend-combined"
ALERT_POLICY_NAMES = {
    "backend_5xx_rate",
    "backend_latency_p95",
    "cloud_sql_connections",
}


def _dashboard(resources):
    return get_one(
        find_resources(
            resources,
            resource_type="google_monitoring_dashboard",
            name="agent_tier_a",
        ),
        "Recipe 7 expects exactly one agent_tier_a monitoring dashboard",
    )


def _alert_policies(resources):
    return find_resources(resources, resource_type="google_monitoring_alert_policy")


def _dashboard_raw(resources) -> str:
    dash = _dashboard(resources)
    raw = dash["attrs"].get("dashboard_json")
    assert raw is not None, "Recipe 7: dashboard_json is required"
    return str(raw)


# ─────────────────────────────────────────────────────────────────────────────
# REJECT failures first
# ─────────────────────────────────────────────────────────────────────────────


def test_no_observability_dashboard_is_a_failure(resources):
    """REJECT: without a dashboard, Recipe 7 leaves operators blind post-deploy."""
    dashboards = find_resources(resources, resource_type="google_monitoring_dashboard")
    assert dashboards, (
        "Recipe 7: no google_monitoring_dashboard found in infra/gcp/. "
        "observability.tf must declare the Tier A dashboard."
    )


def test_fewer_than_three_alert_policies_is_a_failure(resources):
    """REJECT: Recipe 7 requires three alert policies (5xx, latency, SQL connections)."""
    policies = _alert_policies(resources)
    assert len(policies) >= 3, (
        f"Recipe 7: expected at least 3 alert policies, found {len(policies)}."
    )


def test_alert_policies_must_not_use_plaintext_secret_filters(resources):
    """REJECT: alert filters must not embed secret-shaped literals."""
    for policy in _alert_policies(resources):
        attrs = policy["attrs"]
        blob = json.dumps(attrs)
        assert "sk-" not in blob and "postgresql://" not in blob, (
            f"Recipe 7: alert policy {policy['name']} must not embed secrets in filters."
        )


def test_billing_budget_has_no_hardcoded_billing_account(resources):
    """REJECT: billing account ID must come from var.billing_account_id, not a literal."""
    budgets = find_resources(resources, resource_type="google_billing_budget")
    for budget in budgets:
        attrs = budget["attrs"]
        billing_ref = str(attrs.get("billing_account", ""))
        assert "XXXX" not in billing_ref and "000000" not in billing_ref, (
            "Recipe 7: billing_account must reference data source, not a placeholder literal."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard acceptance
# ─────────────────────────────────────────────────────────────────────────────


def test_dashboard_display_name_is_tier_a(resources):
    """ACCEPT: dashboard is discoverable in Cloud Console."""
    blob = _dashboard_raw(resources)
    assert "AgentsFramework Tier A" in blob, (
        f"Recipe 7: unexpected dashboard displayName in dashboard_json."
    )


def test_dashboard_includes_backend_and_sql_tiles(resources):
    """ACCEPT: dashboard covers Cloud Run backend metrics and Cloud SQL connections."""
    blob = _dashboard_raw(resources)
    assert (
        "cloud_run_revision_filter" in blob
        or "backend_service_name" in blob
        or BACKEND_SERVICE in blob
    ), (
        "Recipe 7: dashboard must chart the combined backend service."
    )
    assert "cloudsql.googleapis.com/database/network/connections" in blob, (
        "Recipe 7: dashboard must include Cloud SQL connection metric."
    )
    assert "run.googleapis.com/request_latencies" in blob, (
        "Recipe 7: dashboard must include Cloud Run latency metric."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Alert policy acceptance
# ─────────────────────────────────────────────────────────────────────────────


def test_three_named_alert_policies_exist(resources):
    """ACCEPT: all three Recipe 7 alert policies are declared."""
    found = {p["name"] for p in _alert_policies(resources)}
    missing = ALERT_POLICY_NAMES - found
    assert not missing, f"Recipe 7: missing alert policies: {sorted(missing)}"


def test_backend_5xx_alert_uses_ratio_threshold(resources):
    """ACCEPT: 5xx alert compares 5xx rate to total request rate."""
    policy = get_one(
        find_resources(
            resources,
            resource_type="google_monitoring_alert_policy",
            name="backend_5xx_rate",
        ),
        "Recipe 7: backend_5xx_rate alert policy required",
    )
    conditions = policy["attrs"].get("conditions") or []
    assert conditions, "Recipe 7: backend_5xx_rate must declare conditions"
    if isinstance(conditions, dict):
        conditions = [conditions]
    threshold = unwrap_block(conditions[0].get("condition_threshold"))
    assert threshold is not None
    assert "denominator_filter" in threshold, (
        "Recipe 7: 5xx alert must use ratio (denominator_filter)."
    )
    filt = str(threshold.get("filter", ""))
    assert "response_code_class" in filt and "5xx" in filt, (
        "Recipe 7: 5xx alert filter must target 5xx response class."
    )
    assert (
        BACKEND_SERVICE in filt
        or "cloud_run_revision_filter" in filt
        or "backend_service_name" in filt
    ), (
        "Recipe 7: 5xx alert must scope to agent-backend-combined."
    )


def test_backend_latency_alert_uses_p95_aligner(resources):
    """ACCEPT: latency alert tracks p95 request latency."""
    policy = get_one(
        find_resources(
            resources,
            resource_type="google_monitoring_alert_policy",
            name="backend_latency_p95",
        ),
        "Recipe 7: backend_latency_p95 alert policy required",
    )
    conditions = policy["attrs"].get("conditions") or []
    if isinstance(conditions, dict):
        conditions = [conditions]
    threshold = unwrap_block(conditions[0].get("condition_threshold"))
    assert threshold is not None
    assert "request_latencies" in str(threshold.get("filter", ""))
    aggs = threshold.get("aggregations") or []
    if isinstance(aggs, dict):
        aggs = [aggs]
    aligners = {unwrap_block(a).get("per_series_aligner") for a in aggs}
    assert "ALIGN_PERCENTILE_95" in aligners


def test_cloud_sql_connections_alert_targets_instance(resources, variables):
    """ACCEPT: SQL alert watches the Recipe 2 instance."""
    policy = get_one(
        find_resources(
            resources,
            resource_type="google_monitoring_alert_policy",
            name="cloud_sql_connections",
        ),
        "Recipe 7: cloud_sql_connections alert policy required",
    )
    conditions = policy["attrs"].get("conditions") or []
    if isinstance(conditions, dict):
        conditions = [conditions]
    threshold = unwrap_block(conditions[0].get("condition_threshold"))
    assert threshold is not None
    filt = str(threshold.get("filter", ""))
    assert "cloudsql.googleapis.com/database/network/connections" in filt
    instance = variables.get("cloud_sql_instance_name", {}).get("default", "agent-db")
    assert str(instance) in filt or "cloud_sql_instance" in filt


# ─────────────────────────────────────────────────────────────────────────────
# Budget + variables + outputs
# ─────────────────────────────────────────────────────────────────────────────


def test_monthly_budget_usd_defaults_to_fifty(variables):
    """ACCEPT: Tier A budget alert defaults to $50/mo per plan."""
    attrs = variables.get("monthly_budget_usd", {})
    assert attrs.get("default") == 50, (
        "Recipe 7: monthly_budget_usd must default to 50."
    )


def test_billing_budget_gated_on_billing_account_id(resources):
    """ACCEPT: budget is count-gated so CI validate works without billing account."""
    budgets = find_resources(resources, resource_type="google_billing_budget", name="tier_a")
    assert budgets, "Recipe 7: google_billing_budget.tier_a must be declared"
    budget = budgets[0]
    count = budget["attrs"].get("count")
    assert count is not None, "Recipe 7: billing budget must use count gate on billing_account_id"


def test_monitoring_dashboard_output_exists(outputs):
    """ACCEPT: dashboard name is exposed for runbook links."""
    assert "monitoring_dashboard_name" in outputs, (
        "Recipe 7: monitoring_dashboard_name output required."
    )


def test_billing_budget_enabled_output_exists(outputs):
    """ACCEPT: operators can see whether budget alert is active."""
    assert "billing_budget_enabled" in outputs, (
        "Recipe 7: billing_budget_enabled output required."
    )
