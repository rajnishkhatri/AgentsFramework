# infra/gcp/policies/observability.rego
#
# Conftest/OPA policy for Recipe 7 observability — dashboard, alerts, budget.
# Run with:
#   cd infra/gcp && conftest test --policy policies/ \
#     --parser hcl2 --all-namespaces *.tf

package observability

import future.keywords.contains
import future.keywords.if
import future.keywords.in

dashboard_attrs contains attrs if {
  some name
  attrs := input.resource.google_monitoring_dashboard[name][_]
}

alert_policy_attrs contains attrs if {
  some name
  attrs := input.resource.google_monitoring_alert_policy[name][_]
}

budget_attrs contains attrs if {
  some name
  attrs := input.resource.google_billing_budget[name][_]
}

# ── Dashboard must exist ────────────────────────────────────────────────────

deny contains msg if {
  count(dashboard_attrs) == 0
  msg := "Recipe 7: google_monitoring_dashboard.agent_tier_a is required."
}

# ── Three alert policies required ─────────────────────────────────────────────

deny contains msg if {
  count(alert_policy_attrs) < 3
  msg := sprintf(
    "Recipe 7: expected at least 3 alert policies, found %d.",
    [count(alert_policy_attrs)],
  )
}

# ── 5xx alert must use denominator_filter (ratio) ─────────────────────────────

deny contains msg if {
  some name
  attrs := input.resource.google_monitoring_alert_policy[name][_]
  name == "backend_5xx_rate"
  some cond in attrs.conditions
  count(cond.condition_threshold) > 0
  some ct in cond.condition_threshold
  count(ct.denominator_filter) == 0
  msg := "Recipe 7: backend_5xx_rate alert must include denominator_filter for ratio alerting."
}

# ── Billing budget must gate on billing_account_id ────────────────────────────

deny contains msg if {
  some name
  attrs := input.resource.google_billing_budget[name][_]
  not attrs.count
  msg := sprintf(
    "Recipe 7: google_billing_budget.%s must use count gate on billing_account_id.",
    [name],
  )
}
