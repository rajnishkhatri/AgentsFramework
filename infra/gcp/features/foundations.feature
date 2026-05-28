# infra/gcp/features/foundations.feature
#
# BDD scenarios for Recipe 1 — GCP foundations. These map directly to the
# pytest assertions in tests/infra/gcp/test_foundations.py and the Rego
# policies in infra/gcp/policies/foundations.rego. The three views are
# complementary: BDD for stakeholder legibility, Rego for Conftest CI, pytest
# for fast TDD feedback loops.

Feature: GCP Tier A Foundations (Recipe 1)

  Background:
    Given the OpenTofu stack at infra/gcp/ is parsed

  # ── API enablement ──────────────────────────────────────────────────────

  Scenario: All required GCP APIs are enabled
    Then google_project_service resources enable all of:
      | cloudresourcemanager.googleapis.com |
      | iam.googleapis.com                  |
      | artifactregistry.googleapis.com     |
      | run.googleapis.com                  |
      | sqladmin.googleapis.com             |
      | secretmanager.googleapis.com        |
      | storage.googleapis.com              |
      | monitoring.googleapis.com           |
      | cloudbilling.googleapis.com         |
      | billingbudgets.googleapis.com       |
      | cloudscheduler.googleapis.com       |

  Scenario: Project APIs have disable_on_destroy = false
    Then no google_project_service resource has disable_on_destroy = true

  # ── Artifact Registry ───────────────────────────────────────────────────

  Scenario: A Docker Artifact Registry repository is declared
    Then at least one google_artifact_registry_repository with format = "DOCKER" exists

  Scenario: The Artifact Registry repository ID matches the variable default
    Then the repository repository_id is sourced from var.artifact_registry_repo_id or equals "agent-backend"

  # ── Runtime service account ─────────────────────────────────────────────

  Scenario: A dedicated backend runtime service account is declared
    Then a google_service_account with account_id containing "backend-runtime" exists

  Scenario: The runtime SA has AR reader access
    Then a google_artifact_registry_repository_iam_member grants roles/artifactregistry.reader
    And the member references google_service_account.backend_runtime

  Scenario: The runtime SA has log writer access at the project level
    Then a google_project_iam_member grants roles/logging.logWriter
    And the member references google_service_account.backend_runtime

  Scenario: The runtime SA has metric writer access at the project level
    Then a google_project_iam_member grants roles/monitoring.metricWriter
    And the member references google_service_account.backend_runtime

  Scenario Outline: No overly broad project-level roles are granted
    Then no google_project_iam_member grants <forbidden_role>
    Examples:
      | forbidden_role          |
      | roles/editor            |
      | roles/owner             |
      | roles/iam.securityAdmin |
