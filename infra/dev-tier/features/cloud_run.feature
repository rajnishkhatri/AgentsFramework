# infra/dev-tier/features/cloud_run.feature
#
# Sprint 2 §S2.1.1 — terraform-compliance BDD scenarios.
#
# Run against a real `tofu plan` JSON during the apply phase:
#
#   cd infra/dev-tier
#   tofu plan -out=tfplan -var-file=terraform.tfvars
#   tofu show -json tfplan > tfplan.json
#   terraform-compliance -p tfplan.json -f features/
#
# Static (no-cloud-creds) checks live in tests/infra/test_cloud_run.py
# and infra/dev-tier/policies/cloud_run.rego — those run against parsed
# HCL and have full nested-attr grammar support. terraform-compliance's
# DSL is intentionally coarse (existence + leaf-value checks); we use it
# here for the apply-time signal that the *resolved* plan still names
# the right resources, with the deeper structural assertions deferred to
# pytest/Rego.

Feature: Cloud Run middleware service satisfies Sprint 2 §S2.1.1

    Background:
        Given I have google_cloud_run_v2_service defined

    Scenario: Service is named agent-middleware
        Then it must contain name
        And its value must match the "agent-middleware" regex

    Scenario: Service has a template block (sized via pytest + Rego)
        Then it must contain template

    Scenario: Service has a location pinned by var.gcp_region
        Then it must contain location

    Scenario: Service uses a dedicated (non-default) runtime SA
        # The default Compute Engine SA looks like
        # `<project-number>-compute@developer.gserviceaccount.com`. Our
        # runtime SA is `agent-middleware-runtime@<project>.iam.gserviceaccount.com`.
        # Asserting the SA exists is enough at this layer; the
        # default-SA-rejection check lives in pytest.
        When it contains template
        Then it must contain service_account
