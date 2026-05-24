Feature: GCP Tier A cleanup safety (Recipe 8)
  Teardown-friendly dev settings for data tier and secrets.

  Background:
    Given I have google provider configured

  Scenario: Data-tier GCS buckets allow force destroy
    Given I declare google_storage_bucket
    When it contains agent_facts
    Then it must contain force_destroy

  Scenario: Cloud SQL deletion protection is disabled at Tier A
    Given I declare google_sql_database_instance
    When it contains main
    Then it must contain deletion_protection

  Scenario: Secret versions use ABANDON deletion policy
    Given I declare google_secret_manager_secret_version
    When it contains workos_api_key
    Then it must contain deletion_policy
