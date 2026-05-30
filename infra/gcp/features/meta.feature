Feature: GCP Tier A meta ring (Recipe 6)
  Optional Cloud Scheduler + Cloud Run Job for nightly meta/run_eval.py.

  Background:
    Given I have google provider configured

  Scenario: Meta Cloud Run Job invokes meta.run_eval module
    Given I have google_cloud_run_v2_job defined
    When it contains template
    Then it must contain template
    And it must contain command
    And it must contain python
    And it must contain meta.run_eval

  Scenario: Meta job does not inject DATABASE_URL
    Given I have google_cloud_run_v2_job defined
    When it contains env
    Then it must not contain DATABASE_URL

  Scenario: Cloud Scheduler uses oauth_token for job invocation
    Given I have google_cloud_scheduler_job defined
    When it contains http_target
    Then it must contain oauth_token
