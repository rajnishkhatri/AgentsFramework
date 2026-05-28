# infra/gcp/features/secret_manager.feature
#
# BDD scenarios for Secret Manager hygiene (Recipe 1). Adapted from
# infra/dev-tier/features/secret_manager.feature.
#
# The 8 required secrets differ from dev-tier (neon-database-url is replaced
# by database-url; agent-facts-secret is new).

Feature: GCP Tier A Secret Manager (Recipe 1)

  Background:
    Given the OpenTofu stack at infra/gcp/ is parsed

  # ── Existence ───────────────────────────────────────────────────────────

  Scenario Outline: All required secrets are declared as google_secret_manager_secret
    Then a google_secret_manager_secret with secret_id = "<secret_id>" exists
    Examples:
      | secret_id           |
      | workos-api-key      |
      | openai-api-key      |
      | anthropic-api-key   |
      | langfuse-public-key |
      | langfuse-secret-key |
      | mem0-api-key        |
      | database-url        |
      | agent-facts-secret  |
      | workos-cookie-password |

  Scenario: Every secret has a replication block
    Then no google_secret_manager_secret is missing a replication block

  # ── Versions ────────────────────────────────────────────────────────────

  Scenario: Every secret has a paired google_secret_manager_secret_version
    Then every google_secret_manager_secret has at least one version resource

  Scenario: No secret_data is a plaintext literal (FE-AP-18 AUTO-REJECT)
    Then no google_secret_manager_secret_version has a literal secret_data value

  # ── IAM bindings ────────────────────────────────────────────────────────

  Scenario: Every secret grants secretAccessor to the backend runtime SA
    Then every google_secret_manager_secret has a google_secret_manager_secret_iam_member
    And the member uses role = "roles/secretmanager.secretAccessor"
    And the member references the backend_runtime service account

  Scenario Outline: No secret is accessible to broad principals (FE-AP-18 AUTO-REJECT)
    Then no google_secret_manager_secret_iam_member grants access to "<forbidden_prefix>"
    Examples:
      | forbidden_prefix       |
      | allUsers               |
      | allAuthenticatedUsers  |
      | user:                  |
      | group:                 |
      | domain:                |
