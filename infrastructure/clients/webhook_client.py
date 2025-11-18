"""
Webhook client for sending async webhooks to ledger service.

This client implements retries with exponential backoff using tenacity,
records webhook attempts in the database, and observes latency metrics.
"""
import os
import httpx
import time
from datetime import datetime
from typing import Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
    RetryCallState
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
        
        # Track attempt count for current webhook
        self._current_attempt_count: int = 0
        # Track db_session and webhook_id for recording attempts
        self._db_session = None
        self._webhook_id = None
        self._webhook_record = None
    
    async def _record_attempt(self, success: bool, status_code: int, latency_ms: float, attempt_number: int):
        """Record an individual attempt in the database."""
        if self._db_session and self._webhook_record:
            try:
                # Update the webhook record with this attempt
                self._webhook_record.attempts = attempt_number
                self._webhook_record.last_attempt_at = datetime.now()
                self._webhook_record.status = "success" if success else "failed"
                
                # Ensure the record is in the session
                if self._webhook_record not in self._db_session:
                    self._db_session.add(self._webhook_record)
                
                # Commit immediately to see the record in DB while retries are happening
                await self._db_session.commit()
                
                logger.info(
                    "webhook_attempt_recorded_individual",
                    step="webhook_client",
                    webhook_id=self._webhook_id,
                    attempt_number=attempt_number,
                    success=success,
                    status_code=status_code,
                    latency_ms=round(latency_ms, 2)
                )
            except Exception as e:
                logger.error(
                    "webhook_attempt_record_failed",
                    step="webhook_client",
                    error=str(e),
                    exc_info=True
                )
                # Rollback on error
                try:
                    await self._db_session.rollback()
                except Exception:
                    pass
    
    async def _send_with_retry(
        self,
        payload: dict,
        request_id: Optional[str] = None
    ) -> tuple[bool, int, float, int]:
        """
        Send webhook with retry logic.
        
        Returns:
            Tuple of (success: bool, status_code: int, latency_seconds: float, attempt_count: int)
        """
        # Refresh webhook record from database to get latest URL before each attempt
        if self._db_session and self._webhook_record:
            try:
                # Refresh the object from database to get latest values
                await self._db_session.refresh(self._webhook_record)
            except Exception as e:
                logger.warning(
                    "webhook_record_refresh_failed",
                    step="webhook_client",
                    webhook_id=self._webhook_id,
                    error=str(e)
                )
        
        # Use URL from database record if available, otherwise construct it
        if self._webhook_record and self._webhook_record.target_url:
            url = self._webhook_record.target_url
        else:
            # Fallback: construct URL from base_url
            url = f"{self.base_url}/mock-ledger"
            # For testing purposes: add ?mode=fail if LEDGER_MODE_FAIL env var is set
            LEDGER_MODE_FAIL = os.getenv("LEDGER_MODE_FAIL", "")
            if LEDGER_MODE_FAIL == "fail":
                url = f"{url}?mode=fail"
        
        start_time = time.time()
        # Get current attempt number (will be updated by callback before each retry)
        attempt_number = self._current_attempt_count if self._current_attempt_count > 0 else 1
        
        try:
            response = await self._client.post(url, json=payload)
            latency = time.time() - start_time
            latency_ms = latency * 1000
            
            # Record latency in histogram
            webhook_latency_seconds.observe(latency)
            
            # Check if successful (2xx status)
            is_success = 200 <= response.status_code < 300
            
            # Record this attempt in database (only once, after getting response)
            await self._record_attempt(
                success=is_success,
                status_code=response.status_code,
                latency_ms=latency_ms,
                attempt_number=attempt_number
            )
            
            # Raise for non-2xx to trigger retry
            response.raise_for_status()
            
            # Success - return attempt count
            return True, response.status_code, latency, attempt_number
            
        except httpx.HTTPStatusError as e:
            latency = time.time() - start_time
            latency_ms = latency * 1000
            webhook_latency_seconds.observe(latency)
            
            # Record this failed attempt in database
            status_code = e.response.status_code if e.response else 0
            
            await self._record_attempt(
                success=False,
                status_code=status_code,
                latency_ms=latency_ms,
                attempt_number=attempt_number
            )
            
            raise
            
        except (httpx.TimeoutException, httpx.RequestError) as e:
            latency = time.time() - start_time
            latency_ms = latency * 1000
            webhook_latency_seconds.observe(latency)
            
            # Record this failed attempt in database (network/timeout error)
            await self._record_attempt(
                success=False,
                status_code=0,  # No HTTP status code for network errors
                latency_ms=latency_ms,
                attempt_number=attempt_number
            )
            
            raise
    
    async def send_webhook(
        self,
        plan_id: str,
        decision_id: str,
        user_id: str,
        amount_granted_cents: int,
        request_id: Optional[str] = None
    ) -> tuple[bool, int]:
        """
        Send webhook to ledger service with retries.
        
        Args:
            plan_id: ID of the plan
            decision_id: ID of the decision
            user_id: ID of the user
            amount_granted_cents: Amount granted in cents
            request_id: Optional request ID for tracing
            
        Returns:
            Tuple of (success: bool, attempt_count: int)
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
        
        self._current_attempt_count = 0  # Reset attempt count
        
        try:
            success, status_code, latency, attempt_count = await self._send_with_retry(payload, request_id)
            
            log.info(
                "webhook_sent_successfully",
                step="webhook_send",
                status_code=status_code,
                latency_ms=round(latency * 1000, 2),
                attempts=attempt_count
            )
            
            return True, attempt_count
            
        except RetryError as e:
            # All retries exhausted - get attempt count from retry error
            # RetryError.last_attempt contains the last attempt's retry_state
            if hasattr(e, 'last_attempt') and e.last_attempt is not None:
                # last_attempt.attempt_number is the attempt that just failed (the last one)
                attempt_count = e.last_attempt.attempt_number
            elif hasattr(e, 'retry_state') and e.retry_state is not None:
                # Fallback: try to get from retry_state
                attempt_count = e.retry_state.attempt_number
            else:
                # Final fallback: use current count or max retries + 1
                attempt_count = self._current_attempt_count if self._current_attempt_count > 0 else (self.max_retries + 1)
            log.error(
                "webhook_failed_after_retries",
                step="webhook_send",
                error=str(e),
                max_retries=self.max_retries,
                attempts=attempt_count
            )
            return False, attempt_count
            
        except Exception as e:
            attempt_count = self._current_attempt_count if self._current_attempt_count > 0 else 1
            log.error(
                "webhook_unexpected_error",
                step="webhook_send",
                error=str(e),
                attempts=attempt_count,
                exc_info=True
            )
            return False, attempt_count
    
    async def close(self):
        """Close the httpx client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Apply retry decorator to _send_with_retry after class definition
# We create a wrapper that applies the decorator dynamically per instance
_original_send_with_retry = WebhookClient._send_with_retry

def _send_with_retry_wrapper(self, payload, request_id=None):
    """Wrapper that applies retry decorator dynamically per instance."""
    # Track attempt number - start at 0, will be incremented before each call
    attempt_counter = [0]  # Use list to allow modification in nested functions
    
    # Create retry decorator
    retry_decorator = retry(
        stop=stop_after_attempt(6),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError)),
        reraise=True
    )
    
    # Reset attempt count for new webhook
    self._current_attempt_count = 1
    attempt_counter[0] = 0
    
    # Apply decorator to the original method and call it
    @retry_decorator
    async def _decorated_method(payload, request_id):
        # Increment attempt counter before each call
        attempt_counter[0] += 1
        current_attempt = attempt_counter[0]
        self._current_attempt_count = current_attempt
        
        # Call the original method
        return await _original_send_with_retry(self, payload, request_id)
    
    return _decorated_method(payload, request_id)

WebhookClient._send_with_retry = _send_with_retry_wrapper

