# infra/gcp/features/cloud_run_backend.feature
#
# Recipe 4 — terraform-compliance BDD scenarios for the combined backend.
#
# Run against a real `tofu plan` JSON during the apply phase:
#
#   cd infra/gcp
#   tofu plan -out=tfplan -var-file=terraform.tfvars
#   tofu show -json tfplan > tfplan.json
#   terraform-compliance -p tfplan.json -f features/
#
# Static checks live in tests/infra/gcp/test_cloud_run_backend.py and
# infra/gcp/policies/cloud_run.rego.

Feature: Combined backend Cloud Run service satisfies Recipe 4 Tier A constraints

    Background:
        Given I have google_cloud_run_v2_service defined

    Scenario: Service is named agent-backend-combined
        Then it must contain name
        And its value must match the "agent-backend-combined" regex

    Scenario: Service has a template block (sized via pytest + Rego)
        Then it must contain template

    Scenario: Service has a location pinned by var.gcp_region
        Then it must contain location

    Scenario: Service uses a dedicated backend runtime SA
        When it contains template
        Then it must contain service_account
