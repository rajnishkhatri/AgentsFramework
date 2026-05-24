###############################################################################
# infra/gcp/observability.tf
#
# GCP Tier A observability (Recipe 7): Cloud Monitoring dashboard, three alert
# policies (Cloud Run 5xx rate, request latency p95, Cloud SQL connections), and
# an optional billing budget alert.
#
# Resources:
#   * google_monitoring_dashboard.agent_tier_a — Tier A ops dashboard
#   * google_monitoring_notification_channel.email — optional email alerts
#   * google_monitoring_alert_policy.backend_5xx_rate
#   * google_monitoring_alert_policy.backend_latency_p95
#   * google_monitoring_alert_policy.cloud_sql_connections
#   * google_billing_budget.tier_a — project-scoped budget (when billing_account_id set)
#
# Depends on: foundations.tf (monitoring + cloudbilling APIs), cloud-run-backend.tf,
#             data.tf (Cloud SQL instance)
###############################################################################

data "google_project" "current" {
  project_id = var.gcp_project_id
}

locals {
  backend_service_name  = google_cloud_run_v2_service.backend_combined.name
  frontend_service_name = google_cloud_run_v2_service.frontend.name
  cloud_sql_instance    = google_sql_database_instance.main.name

  cloud_run_revision_filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${local.backend_service_name}\""

  observability_labels = {
    tier   = "a"
    recipe = "7-observability"
  }
}

# ── Optional email notification channel ──────────────────────────────────────

resource "google_monitoring_notification_channel" "email" {
  count = var.alert_notification_email != "" ? 1 : 0

  project      = var.gcp_project_id
  display_name = "Agent Tier A alerts"
  type         = "email"

  labels = {
    email_address = var.alert_notification_email
  }

  depends_on = [google_project_service.required]
}

# ── Cloud Monitoring dashboard ───────────────────────────────────────────────

resource "google_monitoring_dashboard" "agent_tier_a" {
  project = var.gcp_project_id

  dashboard_json = jsonencode({
    displayName = "AgentsFramework Tier A"
    labels = {
      tier   = "a"
      recipe = "7-observability"
    }
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Backend request rate"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" AND ${local.cloud_run_revision_filter}"
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                      groupByFields    = ["metric.labels.response_code_class"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 6
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Backend p95 latency (ms)"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_latencies\" AND ${local.cloud_run_revision_filter}"
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_95"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Backend 5xx error rate"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilterRatio = {
                    numerator = {
                      filter = "metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\" AND ${local.cloud_run_revision_filter}"
                      aggregation = {
                        alignmentPeriod  = "60s"
                        perSeriesAligner = "ALIGN_RATE"
                      }
                    }
                    denominator = {
                      filter = "metric.type=\"run.googleapis.com/request_count\" AND ${local.cloud_run_revision_filter}"
                      aggregation = {
                        alignmentPeriod  = "60s"
                        perSeriesAligner = "ALIGN_RATE"
                      }
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Cloud SQL connections"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"cloudsql.googleapis.com/database/network/connections\" AND resource.type=\"cloudsql_database\" AND resource.labels.database_id=\"${var.gcp_project_id}:${local.cloud_sql_instance}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos   = 0
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Frontend request rate"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${local.frontend_service_name}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
            }
          }
        },
      ]
    }
  })

  depends_on = [google_project_service.required]
}

# ── Alert: Cloud Run 5xx rate ────────────────────────────────────────────────

resource "google_monitoring_alert_policy" "backend_5xx_rate" {
  project      = var.gcp_project_id
  display_name = "Agent backend 5xx rate > ${var.cloud_run_5xx_rate_threshold * 100}%"
  combiner     = "OR"

  conditions {
    display_name = "Backend 5xx rate above threshold for 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\" AND ${local.cloud_run_revision_filter}"
      comparison      = "COMPARISON_GT"
      threshold_value = var.cloud_run_5xx_rate_threshold
      duration        = "300s"

      denominator_filter = "metric.type=\"run.googleapis.com/request_count\" AND ${local.cloud_run_revision_filter}"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
        group_by_fields    = ["resource.labels.service_name"]
      }

      denominator_aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
        group_by_fields    = ["resource.labels.service_name"]
      }
    }
  }

  documentation {
    content = "Cloud Run service `${local.backend_service_name}` returned more than ${var.cloud_run_5xx_rate_threshold * 100}% 5xx responses over 5 minutes. Check revision logs and recent deploys."
  }

  notification_channels = [
    for channel in google_monitoring_notification_channel.email : channel.name
  ]

  user_labels = local.observability_labels

  depends_on = [google_project_service.required]
}

# ── Alert: Cloud Run p95 latency ─────────────────────────────────────────────

resource "google_monitoring_alert_policy" "backend_latency_p95" {
  project      = var.gcp_project_id
  display_name = "Agent backend p95 latency > ${var.cloud_run_latency_p95_ms_threshold}ms"
  combiner     = "OR"

  conditions {
    display_name = "Backend p95 latency above threshold for 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_latencies\" AND ${local.cloud_run_revision_filter}"
      comparison      = "COMPARISON_GT"
      threshold_value = var.cloud_run_latency_p95_ms_threshold
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner     = "ALIGN_PERCENTILE_95"
        group_by_fields        = ["resource.labels.service_name"]
      }
    }
  }

  documentation {
    content = "Cloud Run service `${local.backend_service_name}` p95 latency exceeded ${var.cloud_run_latency_p95_ms_threshold} ms for 5 minutes. Inspect cold starts, LLM latency, and Postgres connection pool saturation."
  }

  notification_channels = [
    for channel in google_monitoring_notification_channel.email : channel.name
  ]

  user_labels = local.observability_labels

  depends_on = [google_project_service.required]
}

# ── Alert: Cloud SQL connections ─────────────────────────────────────────────

resource "google_monitoring_alert_policy" "cloud_sql_connections" {
  project      = var.gcp_project_id
  display_name = "Cloud SQL connections > ${var.cloud_sql_connections_threshold}"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL active connections above threshold for 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"cloudsql.googleapis.com/database/network/connections\" AND resource.type=\"cloudsql_database\" AND resource.labels.database_id=\"${var.gcp_project_id}:${local.cloud_sql_instance}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.cloud_sql_connections_threshold
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    content = "Cloud SQL instance `${local.cloud_sql_instance}` exceeded ${var.cloud_sql_connections_threshold} connections for 5 minutes. Check for connection leaks or scale up the instance tier."
  }

  notification_channels = [
    for channel in google_monitoring_notification_channel.email : channel.name
  ]

  user_labels = local.observability_labels

  depends_on = [google_project_service.required]
}

# ── Billing budget alert ─────────────────────────────────────────────────────

data "google_billing_account" "linked" {
  count = var.billing_account_id != "" ? 1 : 0

  billing_account = var.billing_account_id
}

resource "google_billing_budget" "tier_a" {
  count = var.billing_account_id != "" ? 1 : 0

  billing_account = data.google_billing_account.linked[0].id
  display_name    = "AgentsFramework Tier A (${var.gcp_project_id})"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.9
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  depends_on = [google_project_service.required]
}
