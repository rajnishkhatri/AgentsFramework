# infra/gcp/policies/cleanup.rego
#
# Conftest/OPA policy for Recipe 8 teardown safety — dev-tier buckets must
# allow empty-on-destroy and Cloud SQL must not block deletion.

package cleanup

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ── Data-tier GCS buckets must allow destroy ────────────────────────────────

data_bucket_names := {"agent_facts", "trust_traces"}

bucket_attrs contains {"name": name, "attrs": attrs} if {
  some name
  attrs := input[_].contents.resource.google_storage_bucket[name][_]
}

deny contains msg if {
  some b in bucket_attrs
  b.name in data_bucket_names
  b.attrs.force_destroy != true
  msg := sprintf(
    "Recipe 8: data-tier bucket %q must have force_destroy=true for dev teardown.",
    [b.name],
  )
}

# ── Cloud SQL must not block destroy at Tier A ───────────────────────────────

sql_instance_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_sql_database_instance[name][_]
}

deny contains msg if {
  some attrs in sql_instance_attrs
  attrs.deletion_protection == true
  msg := "Recipe 8: Cloud SQL deletion_protection must be false at Tier A dev."
}

# ── Secret versions abandon on destroy (retain shells cheaply) ───────────────

secret_version_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_secret_manager_secret_version[name][_]
}

deny contains msg if {
  some attrs in secret_version_attrs
  attrs.deletion_policy != "ABANDON"
  msg := "Recipe 8: secret versions must use deletion_policy=ABANDON so shells survive partial teardown."
}
