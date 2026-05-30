# infra/gcp/policies/secret_manager.rego
#
# Conftest/OPA policy for Secret Manager hygiene (adapted from
# infra/dev-tier/policies/secret_manager.rego for the GCP Tier A stack).
# Run with `conftest test --policy policies/ --parser hcl2
# --all-namespaces *.tf`.
#
# Key difference from dev-tier: the runtime SA is `backend_runtime` (not
# `middleware_runtime`), and `database-url` replaces `neon-database-url`.

package secret_manager

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ── Walk per-resource attr dicts ──────────────────────────────────────────

secret_version_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_secret_manager_secret_version[name][_]
}

iam_member_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_secret_manager_secret_iam_member[name][_]
}

# ── AUTO-REJECT (FE-AP-18): no plaintext secret_data ─────────────────────

deny contains msg if {
  some attrs in secret_version_attrs
  is_string(attrs.secret_data)
  not is_tofu_ref(attrs.secret_data)
  msg := "Recipe 1 / FE-AP-18: secret_data must be a Tofu reference (var.X / local.X), not a literal string."
}

# ── REJECT bindings to broad principals ──────────────────────────────────

deny contains msg if {
  some attrs in iam_member_attrs
  forbidden_member(attrs.member)
  msg := sprintf(
    "Recipe 1: secret IAM member must be the backend runtime SA only; got %v",
    [attrs.member],
  )
}

forbidden_member(member) if startswith(member, "allUsers")
forbidden_member(member) if startswith(member, "allAuthenticatedUsers")
forbidden_member(member) if startswith(member, "user:")
forbidden_member(member) if startswith(member, "group:")
forbidden_member(member) if startswith(member, "domain:")

# ── REJECT roles broader than secretAccessor on per-secret bindings ──────

deny contains msg if {
  some attrs in iam_member_attrs
  attrs.role != "roles/secretmanager.secretAccessor"
  msg := sprintf(
    "Recipe 1: secret-level IAM bindings must use roles/secretmanager.secretAccessor only; got %v",
    [attrs.role],
  )
}

# ── Helpers ──────────────────────────────────────────────────────────────

is_tofu_ref(v) if {
  is_string(v)
  regex.match(`\$\{[^}]+\}|^(var|local|data|module)\.`, v)
}
