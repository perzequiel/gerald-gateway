# infrastructure/metrics/metrics.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Métricas principales (usadas por el código)
gerald_decision_total = Counter(
    "gerald_decision_total",
    "Total BNPL decisions",
    ["outcome"]  # approved|declined|error
)

gerald_credit_limit_bucket = Counter(
    "gerald_credit_limit_bucket",
    "Credit limit buckets",
    ["bucket"]  # "$0-$100", "$100-$400", etc.
)

bank_fetch_failures_total = Counter(
    "bank_fetch_failures_total",
    "Bank fetch failures"
)

webhook_latency_seconds = Histogram(
    "webhook_latency_seconds",
    "Webhook latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]
)

# Métricas adicionales para compatibilidad con Terraform
# Estas métricas se incrementan automáticamente cuando se usan las métricas principales

# Para error_rate monitor: service.{service_name}.errors y service.{service_name}.requests
# Nota: Estas métricas se exponen sin namespace para que Datadog las encuentre como service.*
service_errors = Counter(
    "service_errors",
    "Service errors (for Terraform compatibility)",
    ["service_name"]
)

service_requests = Counter(
    "service_requests",
    "Service requests (for Terraform compatibility)",
    ["service_name"]
)

# Para approval_rate_drop monitor: gerald.approved y gerald.declined
# Nota: Estas métricas se exponen sin namespace para que Datadog las encuentre como gerald.*
gerald_approved = Counter(
    "gerald_approved",
    "Approved decisions (for Terraform compatibility)"
)

gerald_declined = Counter(
    "gerald_declined",
    "Declined decisions (for Terraform compatibility)"
)

def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
