# infra/dev-tier/policies/cloud_run.rego
#
# Conftest/OPA policy for Cloud Run (Sprint 2 §S2.1.1). Run:
#
#   cd infra/dev-tier && conftest test --policy policies/ \
#     --parser hcl2 --all-namespaces *.tf
#
# Conftest's HCL2 parser wraps every resource block's attrs in a
# 1-element list. We therefore unwrap with `[_]` at every level the HCL
# block syntax introduces a list (template, scaling, containers,
# resources, http_get, ...).
#
# These policies parallel the pytest assertions in
# tests/infra/test_cloud_run.py but live in the Rego ecosystem so a
# Cloudflare/AWS engineer who knows Conftest but not pytest can also
# read & contribute.

package cloud_run

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ── Walk every Cloud Run service block ────────────────────────────────────
#
# `input.resource.google_cloud_run_v2_service.<name>` is a list of attr
# dicts (single-element in normal usage). Iterating with `[_]` flattens
# that without losing context.

cloud_run_attrs contains attrs if {
    some name
    attrs := input.resource.google_cloud_run_v2_service[name][_]
}

# ── Sprint 2 §S2.1.1 — min_instance_count must be 0 ───────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    some s in t.scaling
    not zero_min_instance(s.min_instance_count)
    msg := sprintf(
        "Sprint 2 §S2.1.1: scaling.min_instance_count must be 0; got %v",
        [s.min_instance_count],
    )
}

zero_min_instance(v) if v == 0
zero_min_instance(v) if is_var_ref(v)

# ── Sprint 2 §S2.1.1 — timeout must be 3600s ──────────────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    not valid_timeout(t.timeout)
    msg := sprintf(
        "Sprint 2 §S2.1.1: template.timeout must be 3600s; got %v",
        [t.timeout],
    )
}

valid_timeout(v) if v == "3600s"
valid_timeout(v) if is_var_ref(v)

# ── Sprint 2 §S2.1.1 — startup_cpu_boost must be true ─────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    some c in t.containers
    some r in c.resources
    r.startup_cpu_boost != true
    msg := sprintf(
        "Sprint 2 §S2.1.1: container.resources.startup_cpu_boost must be true; got %v",
        [r.startup_cpu_boost],
    )
}

# ── Sprint 2 §S2.1.1 — startup probe must hit /healthz ────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    some c in t.containers
    some p in c.startup_probe
    some hg in p.http_get
    hg.path != "/healthz"
    msg := sprintf(
        "Sprint 2 §S2.1.1 DoD: startup_probe path must be /healthz; got %v",
        [hg.path],
    )
}

# ── Sprint 2 §S2.1.4 — dedicated runtime SA wired ────────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    not contains(t.service_account, "google_service_account")
    msg := "Sprint 2 §S2.1.4: Cloud Run must reference a dedicated google_service_account, not a literal SA email."
}

# ── Sprint 2 §S2.1.1 — CPU is 1 vCPU ─────────────────────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    some c in t.containers
    some r in c.resources
    not valid_cpu(r.limits.cpu)
    msg := sprintf(
        "Sprint 2 §S2.1.1: container CPU must be 1 vCPU (1000m); got %v",
        [r.limits.cpu],
    )
}

valid_cpu(v) if v == "1000m"
valid_cpu(v) if v == "1"
valid_cpu(v) if is_var_ref(v)

# ── Sprint 2 §S2.1.1 — memory is 2 GB ────────────────────────────────────

deny contains msg if {
    some attrs in cloud_run_attrs
    some t in attrs.template
    some c in t.containers
    some r in c.resources
    not valid_memory(r.limits.memory)
    msg := sprintf(
        "Sprint 2 §S2.1.1: container memory must be 2Gi; got %v",
        [r.limits.memory],
    )
}

valid_memory(v) if v == "2Gi"
valid_memory(v) if v == "2048Mi"
valid_memory(v) if is_var_ref(v)

# ── Helpers ──────────────────────────────────────────────────────────────

is_var_ref(v) if {
    is_string(v)
    contains(v, "var.")
}
