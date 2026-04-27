# infra/dev-tier/features/secret_manager.feature
#
# Sprint 2 §S2.1.4 — terraform-compliance BDD scenarios for Secret Manager
# hygiene. Run during apply phase against a real plan JSON.

Feature: Secret Manager satisfies Sprint 2 §S2.1.4 cross-cutting DoD

    Background:
        Given I have google_secret_manager_secret defined

    Scenario: Every secret has an automatic replication policy
        Then it must contain replication

    Scenario: All secret IAM bindings use the secretAccessor role
        Given I have google_secret_manager_secret_iam_member defined
        Then it must contain role
        And its value must be "roles/secretmanager.secretAccessor"

    Scenario: No secret IAM binding grants to allUsers
        Given I have google_secret_manager_secret_iam_member defined
        Then it must contain member
        And its value must not match the "^allUsers$" regex

    Scenario: No secret IAM binding grants to allAuthenticatedUsers
        Given I have google_secret_manager_secret_iam_member defined
        Then it must contain member
        And its value must not match the "^allAuthenticatedUsers$" regex

    Scenario: No secret IAM binding grants to a personal user account
        Given I have google_secret_manager_secret_iam_member defined
        Then it must contain member
        And its value must not match the "^user:" regex
