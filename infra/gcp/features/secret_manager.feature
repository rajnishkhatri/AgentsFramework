# infra/gcp/features/secret_manager.feature
#
# BDD scenarios for Secret Manager hygiene (Recipe 1). Adapted from
# infra/dev-tier/features/secret_manager.feature.
#
# The 8 required secrets differ from dev-tier (neon-database-url is replaced
# by database-url; agent-facts-secret is new).

Feature: GCP Tier A Secret Manager (Recipe 1)

  Background:
    Given I have google provider configured

  # ── Existence ───────────────────────────────────────────────────────────

  Scenario: All required secrets are declared as google_secret_manager_secret
    Given I have google_secret_manager_secret defined
    Then it must contain secret_id

  Scenario: Every secret has a replication block
    Given I have google_secret_manager_secret defined
    Then it must contain replication

  # ── Versions ────────────────────────────────────────────────────────────

  Scenario: Every secret has a paired google_secret_manager_secret_version
    Given I have google_secret_manager_secret_version defined
    Then it must contain secret_data

  # ── IAM bindings ────────────────────────────────────────────────────────

  Scenario: Every secret grants secretAccessor to the backend runtime SA
    Given I have google_secret_manager_secret_iam_member defined
    Then it must contain role
    And its value must match the "roles/secretmanager.secretAccessor" regex
