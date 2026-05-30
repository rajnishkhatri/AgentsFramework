# infra/gcp/policies/meta.rego
#
# Conftest/OPA policy for Recipe 6 meta ring — Cloud Run Job + Scheduler.
# Run with:
#   cd infra/gcp && conftest test --policy policies/ \
#     --parser hcl2 --all-namespaces *.tf

package meta

import future.keywords.contains
import future.keywords.if
import future.keywords.in

meta_job_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_cloud_run_v2_job[name][_]
}

meta_scheduler_attrs contains attrs if {
  some name
  attrs := input[_].contents.resource.google_cloud_scheduler_job[name][_]
}

# ── Job command must invoke meta.run_eval ─────────────────────────────────

deny contains msg if {
  some attrs in meta_job_attrs
  some t in attrs.template
  some inner in t.template
  some c in inner.containers
  not run_eval_command(c.command)
  msg := sprintf(
    "Recipe 6: meta Cloud Run Job command must be [python, -m, meta.run_eval]; got %v",
    [c.command],
  )
}

run_eval_command(cmd) if {
  cmd == ["python", "-m", "meta.run_eval"]
}

# ── Job must not inject DATABASE_URL ──────────────────────────────────────

deny contains msg if {
  some attrs in meta_job_attrs
  some t in attrs.template
  some inner in t.template
  some c in inner.containers
  some e in c.env
  e.name == "DATABASE_URL"
  msg := "Recipe 6: meta job must not inject DATABASE_URL (offline GCS eval only)."
}

# ── Scheduler must use oauth_token ────────────────────────────────────────

deny contains msg if {
  some attrs in meta_scheduler_attrs
  some ht in attrs.http_target
  count(ht.oauth_token) == 0
  msg := "Recipe 6: Cloud Scheduler http_target must include oauth_token for Cloud Run Job invocation."
}

# ── Meta bucket IAM must not target agent-facts ───────────────────────────

deny contains msg if {
  some name
  attrs := input[_].contents.resource.google_storage_bucket_iam_member[name][_]
  contains(name, "meta")
  contains(attrs.bucket, "agent-facts")
  msg := sprintf(
    "Recipe 6: meta IAM binding %q must not target the agent-facts bucket.",
    [name],
  )
}
