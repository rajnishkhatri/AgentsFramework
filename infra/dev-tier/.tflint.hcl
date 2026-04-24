###############################################################################
# infra/dev-tier/.tflint.hcl — Sprint 2 deep-TDD: tflint config.
#
# Reads:
#   * Built-in `terraform` ruleset for general HCL hygiene
#     (deprecated_interpolation, unused_declarations, etc.).
#   * The `google` plugin for GCP-specific rules (Cloud Run / Secret Manager
#     deprecated fields, recommended labels, naming conventions).
#   * The `cloudflare` plugin (lighter — primarily resource-name validation).
#
# Run: `cd infra/dev-tier && tflint --init && tflint`
###############################################################################

config {
  call_module_type = "all"
  force            = false
}

plugin "terraform" {
  enabled = true
  version = "0.14.1"
  source  = "github.com/terraform-linters/tflint-ruleset-terraform"
  preset  = "recommended"
}

plugin "google" {
  enabled = true
  version = "0.34.0"
  source  = "github.com/terraform-linters/tflint-ruleset-google"
}

# ── Rule overrides ─────────────────────────────────────────────────────────

# Treat unused declarations as errors so dead code can't accumulate.
rule "terraform_unused_declarations" {
  enabled = true
}

# Cloud Run + Secret Manager rules from the google ruleset are enabled by
# default. We don't override here; the deep-TDD signal comes from running
# `tflint` and treating any rule firing as a blocker.

# Disable the documented_outputs rule on outputs.tf temporarily — every
# output already has a `description`, but the rule sometimes false-positives
# on map outputs with multiline descriptions.
rule "terraform_documented_outputs" {
  enabled = true
}

rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_naming_convention" {
  enabled = true
  format  = "snake_case"
}
