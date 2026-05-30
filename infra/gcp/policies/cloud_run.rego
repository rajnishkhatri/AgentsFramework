# infra/gcp/policies/cloud_run.rego
#
# Conftest/OPA policy for Cloud Run v2 services in the GCP Tier A stack.
# Adapted from infra/dev-tier/policies/cloud_run.rego.
#
# Recipe 1 has NO Cloud Run resources (those come in Recipe 4). This policy
# is a forward-compatibility gate: it will enforce correct shape on the
# `google_cloud_run_v2_service` resources that Recipe 4 adds so that
# `conftest test` continues to pass across all recipes.
#
# Run with:
#   cd infra/gcp && conftest test --policy policies/ \
#     --parser hcl2 --all-namespaces *.tf

package cloud_run

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ── Walk every Cloud Run service block ────────────────────────────────────

cloud_run_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_cloud_run_v2_service[name][_]
}

# ── min_instance_count must be 0 (scale-to-zero, Tier A cost constraint) ──

deny contains msg if {
  some attrs in cloud_run_attrs
  some t in attrs.template
  some s in t.scaling
  not zero_min_instance(s.min_instance_count)
  msg := sprintf(
    "Tier A cost constraint: scaling.min_instance_count must be 0 (scale-to-zero); got %v",
    [s.min_instance_count],
  )
}

zero_min_instance(v) if v == 0
zero_min_instance(v) if is_var_ref(v)

# ── timeout must be 3600s (SSE + long ReAct runs) ─────────────────────────

deny contains msg if {
  some attrs in cloud_run_attrs
  some t in attrs.template
  not valid_timeout(t.timeout)
  msg := sprintf(
    "Tier A Cloud Run: template.timeout must be 3600s for SSE and long ReAct runs; got %v",
    [t.timeout],
  )
}

valid_timeout(v) if v == "3600s"
valid_timeout(v) if is_var_ref(v)

# ── startup_cpu_boost must be true ────────────────────────────────────────

deny contains msg if {
  some attrs in cloud_run_attrs
  some t in attrs.template
  some c in t.containers
  some r in c.resources
  r.startup_cpu_boost != true
  msg := sprintf(
    "Tier A Cloud Run: container.resources.startup_cpu_boost must be true; got %v",
    [r.startup_cpu_boost],
  )
}

# ── dedicated runtime SA required ────────────────────────────────────────

deny contains msg if {
  some attrs in cloud_run_attrs
  some t in attrs.template
  not contains(t.service_account, "google_service_account")
  msg := "Tier A Cloud Run: must reference a dedicated google_service_account, not a literal SA email."
}

# ── Cloud SQL connector volume required (Recipe 4 backend only) ───────────

deny contains msg if {
  some attrs in cloud_run_attrs
  attrs.name == "agent-backend-combined"
  some t in attrs.template
  count(t.volumes) == 0
  msg := "Recipe 4: backend Cloud Run template must declare a volumes block with cloud_sql_instance for the built-in connector."
}

# ── startup probe path: /healthz for backend, / for frontend ────────────

deny contains msg if {
  some attrs in cloud_run_attrs
  attrs.name == "agent-backend-combined"
  some t in attrs.template
  some c in t.containers
  some p in c.startup_probe
  some hg in p.http_get
  hg.path != "/healthz"
  msg := sprintf(
    "Recipe 4 backend: startup_probe path must be /healthz; got %v",
    [hg.path],
  )
}

deny contains msg if {
  some attrs in cloud_run_attrs
  attrs.name == "agent-frontend"
  some t in attrs.template
  some c in t.containers
  some p in c.startup_probe
  some hg in p.http_get
  hg.path != "/"
  msg := sprintf(
    "Recipe 5 frontend: startup_probe path must be /; got %v",
    [hg.path],
  )
}

# ── Helpers ──────────────────────────────────────────────────────────────

is_var_ref(v) if {
  is_string(v)
  contains(v, "var.")
}
