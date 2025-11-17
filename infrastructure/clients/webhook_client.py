"""
Webhook client for sending async webhooks to ledger service.

This client implements retries with exponential backoff using tenacity,
records webhook attempts in the database, and observes latency metrics.
"""
import httpx
import time
from typing import Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)

from infrastructure.metrics.metrics import webhook_latency_seconds
from infrastructure.logging.structlog_logs import logger


class WebhookClient:
    """
    HTTP client for sending webhooks to the ledger service.
    
    Uses tenacity for retries with exponential backoff:
    - max_retries: 5 (configurable)
    - exponential backoff with jitter
    - retries on non-2xx responses and network errors
    """
    
    def __init__(
        self,
        base_url: str,
        max_retries: int = 5,
        connect_timeout: float = 2.0,
        read_timeout: float = 5.0,
    ):
        """
        Initialize the webhook client.
        
        Args:
            base_url: Base URL of the ledger webhook endpoint
            max_retries: Maximum number of retry attempts (default: 5)
            connect_timeout: Connection timeout in seconds (default: 2.0)
            read_timeout: Read timeout in seconds (default: 5.0)
        """
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        
        # Create httpx client with timeouts
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=read_timeout,
                pool=connect_timeout,
            ),
        )
    
    @retry(
        stop=stop_after_attempt(6),  # 1 initial + 5 retries = 6 total attempts
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError)),
        reraise=True
    )
    async def _send_with_retry(
        self,
        payload: dict,
        request_id: Optional[str] = None
    ) -> tuple[bool, int, float]:
        """
        Send webhook with retry logic.
        
        Returns:
            Tuple of (success: bool, status_code: int, latency_seconds: float)
        """
        url = f"{self.base_url}/mock-ledger"
        start_time = time.time()
        
        try:
            response = await self._client.post(url, json=payload)
            latency = time.time() - start_time
            
            # Record latency in histogram
            webhook_latency_seconds.observe(latency)
            
            # Raise for non-2xx to trigger retry
            response.raise_for_status()
            
            return True, response.status_code, latency
            
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError) as e:
            latency = time.time() - start_time
            webhook_latency_seconds.observe(latency)
            raise
    
    async def send_webhook(
        self,
        plan_id: str,
        decision_id: str,
        user_id: str,
        amount_granted_cents: int,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Send webhook to ledger service with retries.
        
        Args:
            plan_id: ID of the plan
            decision_id: ID of the decision
            user_id: ID of the user
            amount_granted_cents: Amount granted in cents
            request_id: Optional request ID for tracing
            
        Returns:
            True if webhook was sent successfully, False otherwise
        """
        payload = {
            "event": "BNPL_APPROVED",
            "plan_id": plan_id,
            "decision_id": decision_id,
            "user_id": user_id,
            "amount_granted_cents": amount_granted_cents,
            "request_id": request_id
        }
        
        log = logger.bind(
            request_id=request_id or "unknown",
            user_id=user_id,
            plan_id=plan_id,
            step="webhook_send"
        )
        
        try:
            success, status_code, latency = await self._send_with_retry(payload, request_id)
            
            log.info(
                "webhook_sent_successfully",
                step="webhook_send",
                status_code=status_code,
                latency_ms=round(latency * 1000, 2)
            )
            
            return True
            
        except RetryError as e:
            # All retries exhausted
            log.error(
                "webhook_failed_after_retries",
                step="webhook_send",
                error=str(e),
                max_retries=self.max_retries
            )
            return False
            
        except Exception as e:
            log.error(
                "webhook_unexpected_error",
                step="webhook_send",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def close(self):
        """Close the httpx client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

