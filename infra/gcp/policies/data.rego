# infra/gcp/policies/data.rego
#
# Conftest/OPA policy for Recipe 2 data tier — Cloud SQL, GCS buckets,
# and associated IAM bindings. Run with:
#
#   cd infra/gcp && conftest test --policy policies/ \
#     --parser hcl2 --all-namespaces *.tf
#
# These policies parallel the pytest assertions in
# tests/infra/gcp/test_data.py but live in the Rego ecosystem.

package data

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ── Cloud SQL ─────────────────────────────────────────────────────────────

sql_instance_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_sql_database_instance[name][_]
}

deny contains msg if {
  count(sql_instance_attrs) == 0
  msg := "Recipe 2: at least one google_sql_database_instance must be declared."
}

deny contains msg if {
  some attrs in sql_instance_attrs
  not startswith(attrs.database_version, "POSTGRES_15")
  msg := sprintf(
    "Recipe 2: Cloud SQL database_version must be POSTGRES_15; got %q.",
    [attrs.database_version],
  )
}

deny contains msg if {
  some attrs in sql_instance_attrs
  some s in attrs.settings
  s.availability_type != "ZONAL"
  msg := sprintf(
    "Recipe 2 Tier A: availability_type must be ZONAL (single-AZ); got %q.",
    [s.availability_type],
  )
}

# ── GCS buckets ───────────────────────────────────────────────────────────

bucket_attrs contains {"name": name, "attrs": attrs} if {
  some name
  attrs := input[_].contents.resource.google_storage_bucket[name][_]
}

deny contains msg if {
  some b in bucket_attrs
  b.attrs.uniform_bucket_level_access != true
  msg := sprintf(
    "Recipe 2: GCS bucket %q must have uniform_bucket_level_access = true.",
    [b.name],
  )
}

deny contains msg if {
  some b in bucket_attrs
  b.attrs.public_access_prevention != "enforced"
  msg := sprintf(
    "Recipe 2: GCS bucket %q must have public_access_prevention = 'enforced'.",
    [b.name],
  )
}

# ── Bucket IAM — REJECT overly broad roles ────────────────────────────────

bucket_iam_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_storage_bucket_iam_member[name][_]
}

forbidden_bucket_roles := {
  "roles/storage.admin",
  "roles/storage.objectAdmin",
}

deny contains msg if {
  some attrs in bucket_iam_attrs
  attrs.role in forbidden_bucket_roles
  msg := sprintf(
    "Recipe 2: bucket IAM role %q is too broad; use objectViewer or objectCreator.",
    [attrs.role],
  )
}

# ── Cloud SQL user — REJECT literal passwords ────────────────────────────

sql_user_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_sql_user[name][_]
}

deny contains msg if {
  some attrs in sql_user_attrs
  is_string(attrs.password)
  not is_tofu_ref(attrs.password)
  msg := "Recipe 2 / FE-AP-18: google_sql_user password must be a Tofu reference (var.X), not a literal."
}

# ── Helpers ───────────────────────────────────────────────────────────────

is_tofu_ref(v) if {
  is_string(v)
  regex.match(`\$\{[^}]+\}|^(var|local|data|module)\.`, v)
}
