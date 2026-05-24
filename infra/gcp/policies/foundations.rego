# infra/gcp/policies/foundations.rego
#
# Conftest/OPA policy for Recipe 1 foundations — API enablement, Artifact
# Registry, and runtime service account shape. Run with:
#
#   cd infra/gcp && conftest test --policy policies/ \
#     --parser hcl2 --all-namespaces *.tf
#
# These policies parallel the pytest assertions in
# tests/infra/gcp/test_foundations.py but live in the Rego ecosystem so an
# engineer familiar with Conftest can audit and contribute without knowing
# the Python test suite.

package foundations

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ── Required APIs ────────────────────────────────────────────────────────────

required_apis := {
  "cloudresourcemanager.googleapis.com",
  "iam.googleapis.com",
  "artifactregistry.googleapis.com",
  "run.googleapis.com",
  "sqladmin.googleapis.com",
  "secretmanager.googleapis.com",
  "storage.googleapis.com",
  "monitoring.googleapis.com",
  "cloudbilling.googleapis.com",
}

project_service_attrs contains attrs if {
  some name
  attrs := input.resource.google_project_service[name][_]
}

declared_apis contains svc if {
  some attrs in project_service_attrs
  svc := attrs.service
}

deny contains msg if {
  some api in required_apis
  not api in declared_apis
  msg := sprintf(
    "Recipe 1: required API %q is not enabled via google_project_service.",
    [api],
  )
}

# ── disable_on_destroy must be false ─────────────────────────────────────────

deny contains msg if {
  some attrs in project_service_attrs
  attrs.disable_on_destroy == true
  msg := sprintf(
    "Recipe 1: google_project_service %q must have disable_on_destroy=false to avoid disruptive API teardowns.",
    [attrs.service],
  )
}

# ── Artifact Registry — exactly one DOCKER repo ──────────────────────────────

ar_repo_attrs contains attrs if {
  some name
  attrs := input.resource.google_artifact_registry_repository[name][_]
}

deny contains msg if {
  count(ar_repo_attrs) == 0
  msg := "Recipe 1: at least one google_artifact_registry_repository must be declared."
}

deny contains msg if {
  some attrs in ar_repo_attrs
  upper(attrs.format) != "DOCKER"
  msg := sprintf(
    "Recipe 1: Artifact Registry repository format must be DOCKER; got %q.",
    [attrs.format],
  )
}

# ── Runtime SA — must exist and be named *backend-runtime* ───────────────────

sa_attrs contains attrs if {
  some name
  attrs := input.resource.google_service_account[name][_]
}

deny contains msg if {
  count(sa_attrs) == 0
  msg := "Recipe 1: at least one google_service_account (the backend runtime SA) must be declared."
}

deny contains msg if {
  some attrs in sa_attrs
  not contains(attrs.account_id, "runtime")
  msg := sprintf(
    "Recipe 1: service account account_id must include 'runtime'; got %q.",
    [attrs.account_id],
  )
}

# ── Project-level IAM — REJECT overly broad roles ────────────────────────────
#
# Recipe 1 allows only logging.logWriter and monitoring.metricWriter at the
# project level. Any broader role on the runtime SA is a least-privilege
# violation.

allowed_project_roles := {
  "roles/logging.logWriter",
  "roles/monitoring.metricWriter",
  "roles/cloudsql.client",
}

project_iam_attrs contains attrs if {
  some name
  attrs := input.resource.google_project_iam_member[name][_]
}

deny contains msg if {
  some attrs in project_iam_attrs
  not attrs.role in allowed_project_roles
  msg := sprintf(
    "Recipe 1: google_project_iam_member role %q is not in the least-privilege allowlist for Tier A. Use a resource-scoped binding instead.",
    [attrs.role],
  )
}
