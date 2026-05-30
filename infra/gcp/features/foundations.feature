# infra/gcp/features/foundations.feature
#
# BDD scenarios for Recipe 1 — GCP foundations. These map directly to the
# pytest assertions in tests/infra/gcp/test_foundations.py and the Rego
# policies in infra/gcp/policies/foundations.rego. The three views are
# complementary: BDD for stakeholder legibility, Rego for Conftest CI, pytest
# for fast TDD feedback loops.

Feature: GCP Tier A Foundations (Recipe 1)

  Background:
    Given I have google provider configured

  # ── API enablement ──────────────────────────────────────────────────────

  Scenario: All required GCP APIs are enabled
    Given I have google_project_service defined
    When its name is required
    Then it must contain disable_on_destroy

  Scenario: Project APIs have disable_on_destroy = false
    Given I have google_project_service defined
    Then it must contain disable_on_destroy
    And its value must match the "false" regex

  # ── Artifact Registry ───────────────────────────────────────────────────

  Scenario: A Docker Artifact Registry repository is declared
    Given I have google_artifact_registry_repository defined
    Then it must contain format
    And its value must match the "DOCKER" regex

  # ── Runtime service account ─────────────────────────────────────────────

  Scenario: A dedicated backend runtime service account is declared
    Given I have google_service_account defined
    Then it must contain account_id
