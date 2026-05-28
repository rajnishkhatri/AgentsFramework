Feature: GCP Tier A observability (Recipe 7)
  Cloud Monitoring dashboard, alert policies, and billing budget.

  Background:
    Given I have google provider configured

  Scenario: Monitoring dashboard is declared
    Given I declare google_monitoring_dashboard
    When it contains dashboard_json
    Then it must contain AgentsFramework Tier A

  Scenario: Backend 5xx alert uses ratio threshold
    Given I declare google_monitoring_alert_policy
    When it contains backend_5xx_rate
    Then it must contain denominator_filter

  Scenario: Billing budget is count-gated
    Given I declare google_billing_budget
    When it contains tier_a
    Then it must contain count
