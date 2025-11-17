# infrastructure/metrics/metrics.py
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

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

def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
