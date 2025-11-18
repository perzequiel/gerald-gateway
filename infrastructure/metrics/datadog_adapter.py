"""
Adapter para enviar métricas a Datadog con los nombres exactos que el Terraform espera.

Este módulo envía métricas adicionales usando DogStatsD para que aparezcan
con los nombres exactos que el terraform espera:
- service.{service_name}.errors
- service.{service_name}.requests
- gerald.approved
- gerald.declined
"""

import os
from typing import Optional

try:
    from datadog import DogStatsd
    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False
    DogStatsd = None

# Configuración de DogStatsD
STATSD_HOST = os.getenv("DD_AGENT_HOST", "localhost")
STATSD_PORT = int(os.getenv("DD_DOGSTATSD_PORT", "8125"))

_statsd_client: Optional[DogStatsd] = None


def get_statsd_client() -> Optional[DogStatsd]:
    """Obtiene o crea el cliente DogStatsD."""
    global _statsd_client
    if not DATADOG_AVAILABLE:
        return None
    
    if _statsd_client is None:
        _statsd_client = DogStatsd(
            host=STATSD_HOST,
            port=STATSD_PORT,
            constant_tags=[f"service_name:{os.getenv('SERVICE_NAME', 'gerald-gateway')}"]
        )
    
    return _statsd_client


def increment_service_errors(service_name: str = "gerald-gateway", count: int = 1):
    """
    Incrementa la métrica service.{service_name}.errors para compatibilidad con Terraform.
    
    Args:
        service_name: Nombre del servicio
        count: Cantidad a incrementar
    """
    statsd = get_statsd_client()
    if statsd:
        # Envía como service.{service_name}.errors
        metric_name = f"service.{service_name}.errors"
        statsd.increment(metric_name, count)


def increment_service_requests(service_name: str = "gerald-gateway", count: int = 1):
    """
    Incrementa la métrica service.{service_name}.requests para compatibilidad con Terraform.
    
    Args:
        service_name: Nombre del servicio
        count: Cantidad a incrementar
    """
    statsd = get_statsd_client()
    if statsd:
        # Envía como service.{service_name}.requests
        metric_name = f"service.{service_name}.requests"
        statsd.increment(metric_name, count)


def increment_gerald_approved(count: int = 1):
    """
    Incrementa la métrica gerald.approved para compatibilidad con Terraform.
    
    Args:
        count: Cantidad a incrementar
    """
    statsd = get_statsd_client()
    if statsd:
        statsd.increment("gerald.approved", count)


def increment_gerald_declined(count: int = 1):
    """
    Incrementa la métrica gerald.declined para compatibilidad con Terraform.
    
    Args:
        count: Cantidad a incrementar
    """
    statsd = get_statsd_client()
    if statsd:
        statsd.increment("gerald.declined", count)

