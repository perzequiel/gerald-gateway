terraform {
  required_providers { datadog = { source = "DataDog/datadog", version = "~> 3.40" } }
}
provider "datadog" { 
  api_key = var.datadog_api_key
  app_key = var.datadog_app_key
}
resource "datadog_monitor" "error_rate" {
  name = "${var.service_name} - Error rate >2% (5m)"
  type = "query alert"
  
  # Query usando métricas de Prometheus scrapeadas por Datadog
  # Las métricas aparecen como terraform.service_errors_total y terraform.service_requests_total
  # (con namespace "terraform" según docker/datadog/prometheus/conf.yaml)
  # Usamos el label service_name para filtrar (sintaxis Datadog: service_name:valor)
  query = "sum(last_5m):sum:terraform.service_errors_total{service_name:\"${var.service_name}\"}.as_rate() / sum:terraform.service_requests_total{service_name:\"${var.service_name}\"}.as_rate() * 100"
  
  # Base message (will be overridden by enhanced message below)
  # message = "High error rate detected for ${var.service_name}."

  monitor_thresholds {
    critical = 2.0
    warning  = 1.0
  }

  tags = ["service:${var.service_name}", "team:bnpl"]
  
  # Permitir crear el monitor aunque las métricas no existan aún
  notify_no_data    = true
  no_data_timeframe = 10  # minutos
  require_full_window = false
  
  # Notification channels: Configure in Datadog UI or use datadog_monitor_notification resource
  # For SNS: Configure AWS SNS integration in Datadog UI, then reference here
  # For PagerDuty: Configure PagerDuty integration in Datadog UI, then use "@pagerduty" in message
  # Example: Add "@pagerduty" or "@slack-alerts" in the message template below
  notify_audit = false
  include_tags = true
  
  # Enhanced notification message
  # To add notifications, include @pagerduty, @slack-alerts, or email addresses in the message
  # Example: Add "@pagerduty" at the beginning of the message
  message = <<-EOT
    {{#is_alert}}
    @pagerduty @slack-alerts
    🚨 CRITICAL: Error rate exceeded 2% for ${var.service_name}
    
    Current error rate: {{value}}%
    Threshold: 2%
    
    Service: ${var.service_name}
    Time: {{date}}
    {{/is_alert}}
    
    {{#is_warning}}
    ⚠️ WARNING: Error rate approaching threshold for ${var.service_name}
    
    Current error rate: {{value}}%
    Threshold: 2%
    {{/is_warning}}
  EOT
}

resource "datadog_monitor" "approval_rate_drop" {
  name = "${var.service_name} - Approval rate drop >20% vs 24h"
  type = "query alert"
  
  # Query usando métricas de Prometheus scrapeadas por Datadog
  # Las métricas aparecen como terraform.gerald_approved_total y terraform.gerald_declined_total
  # (con namespace "terraform" según docker/datadog/prometheus/conf.yaml)
  query = <<-EOT
    (
      sum(last_5m):sum:terraform.gerald_approved_total{*}.as_rate() 
      / 
      (sum:terraform.gerald_approved_total{*}.as_rate() + sum:terraform.gerald_declined_total{*}.as_rate()) 
      * 100
    )
    -
    (
      avg(last_24h):sum:terraform.gerald_approved_total{*}.as_rate() 
      / 
      (sum:terraform.gerald_approved_total{*}.as_rate() + sum:terraform.gerald_declined_total{*}.as_rate()) 
      * 100
      * 0.8
    )
  EOT

  # Base message (will be overridden by enhanced message below)
  # message = "Approval rate dropped >20% vs 24h baseline for ${var.service_name}."

  monitor_thresholds {
    critical = 0  # Alert si la diferencia es negativa (dropped >20%)
    warning  = 5
  }

  tags = ["service:${var.service_name}", "team:bnpl"]
  
  # Permitir crear el monitor aunque las métricas no existan aún
  notify_no_data    = true
  no_data_timeframe = 30  # minutos
  require_full_window = false
  evaluation_delay  = 300  # 5 min delay para cálculo de baseline
  
  # Notification channels: Configure in Datadog UI or use datadog_monitor_notification resource
  # For SNS: Configure AWS SNS integration in Datadog UI, then reference here
  # For PagerDuty: Configure PagerDuty integration in Datadog UI, then use "@pagerduty" in message
  # Example: Add "@pagerduty" or "@slack-alerts" in the message template below
  notify_audit = false
  include_tags = true
  
  # Enhanced notification message
  # To add notifications, include @pagerduty, @slack-alerts, or email addresses in the message
  # Example: Add "@pagerduty" at the beginning of the message
  message = <<-EOT
    {{#is_alert}}
    @pagerduty @slack-alerts
    🚨 CRITICAL: Approval rate dropped >20% vs 24h baseline for ${var.service_name}
    
    Current approval rate: {{value}}%
    Baseline (24h avg): {{baseline_value}}%
    
    Service: ${var.service_name}
    Time: {{date}}
    {{/is_alert}}
    
    {{#is_warning}}
    ⚠️ WARNING: Approval rate dropping for ${var.service_name}
    
    Current approval rate: {{value}}%
    Baseline (24h avg): {{baseline_value}}%
    {{/is_warning}}
  EOT
}

# Notification channels resource (combines SNS, email, and PagerDuty)
locals {
  # Combine notification channels with PagerDuty if provided
  # PagerDuty integration key should be configured in Datadog UI first
  # Then use "@pagerduty" in notification_channels
  all_notification_channels = var.notification_channels
}
