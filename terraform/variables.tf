variable "datadog_api_key" { type = string }
variable "datadog_app_key" { type = string }
variable "service_name" { 
    type = string
    default = "gerald-gateway"
}

# Notification channels
variable "notification_channels" {
  type = list(string)
  default = []
  description = "List of notification channels (e.g., ['@slack-alerts', 'sns-topic-arn:arn:aws:sns:...'])"
}

# PagerDuty integration key (optional)
variable "pagerduty_integration_key" {
  type = string
  default = ""
  description = "PagerDuty integration key for critical alerts"
  sensitive = true
}
