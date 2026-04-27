# infra/dev-tier/features/cross_cutting_dod.feature
#
# Cross-cutting Definition-of-Done items from
# `docs/plan/frontend/SPRINT_BOARD.md` that are testable at IaC plan time.

Feature: Cross-cutting Sprint 2 DoD invariants

    Scenario: Cloud Run service uses a dedicated, non-default service account
        Given I have google_cloud_run_v2_service defined
        When it contains template
        Then it must contain service_account
        And its value must not match the "[0-9]+-compute@developer\\.gserviceaccount\\.com" regex

    Scenario: No google_cloud_run_v2_service env var has a literal secret
        Given I have google_cloud_run_v2_service defined
        When it contains template
        And it contains containers
        And it contains env
        # Tofu env blocks for secrets carry value_source.secret_key_ref
        # rather than `value`. terraform-compliance lacks a "must NOT
        # contain literal" assertion for sibling fields, so the deeper
        # check lives in tests/infra/test_cross_cutting.py.
        Then it must contain name
