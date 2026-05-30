Feature: GCP Tier A observability (Recipe 7)
  Cloud Monitoring dashboard, alert policies, and billing budget.

  Background:
    Given I have google provider configured

  Scenario: Monitoring dashboard is declared
    Given I have google_monitoring_dashboard defined
    When it contains dashboard_json
    Then its value must contain "AgentsFramework Tier A"

  Scenario: Backend 5xx alert uses ratio threshold
    Given I have google_monitoring_alert_policy defined
    When it contains backend_5xx_rate
    Then it must contain denominator_filter

  Scenario: Billing budget is count-gated
    Given I have google_billing_budget defined
    When it contains tier_a
    Then it must contain count
