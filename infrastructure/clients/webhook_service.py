"""
Webhook service that sends webhooks and records attempts in the database.
"""
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from infrastructure.clients.webhook_client import WebhookClient
from infrastructure.db.models.webhook_attempts import OutboundWebhookModel
from infrastructure.logging.structlog_logs import logger


class WebhookService:
    """
    Service that sends webhooks to ledger and records attempts in the database.
    
    This service:
    - Creates/updates outbound_webhook record
    - Sends webhook using WebhookClient with retries
    - Updates webhook record with attempt results
    - Logs all attempts for observability
    """
    
    def __init__(
        self,
        webhook_client: WebhookClient,
        db_session: Optional[AsyncSession] = None,
        target_url: Optional[str] = None
    ):
        """
        Initialize the webhook service.
        
        Args:
            webhook_client: WebhookClient instance for sending webhooks
            db_session: Optional database session for recording attempts
            target_url: Target URL for the webhook (defaults to webhook_client base_url)
        """
        self.webhook_client = webhook_client
        self.db_session = db_session
        self.target_url = target_url or webhook_client.base_url
    
    async def send_webhook(
        self,
        plan_id: str,
        decision_id: str,
        user_id: str,
        amount_granted_cents: int,
        request_id: Optional[str] = None
    ) -> bool:
        """
        Send webhook to ledger and record attempts.
        
        This method:
        1. Creates or updates outbound_webhook record
        2. Sends webhook with retries
        3. Updates record with attempt results
        
        Args:
            plan_id: ID of the plan
            decision_id: ID of the decision
            user_id: ID of the user
            amount_granted_cents: Amount granted in cents
            request_id: Optional request ID for tracing
            
        Returns:
            True if webhook was sent successfully, False otherwise
        """
        log = logger.bind(
            request_id=request_id or "unknown",
            user_id=user_id,
            plan_id=plan_id,
            step="webhook_service"
        )
        
        # Build webhook payload
        payload: Dict[str, Any] = {
            "event": "BNPL_APPROVED",
            "plan_id": plan_id,
            "decision_id": decision_id,
            "user_id": user_id,
            "amount_granted_cents": amount_granted_cents,
            "request_id": request_id
        }
        
        # Create webhook record
        webhook_record = None
        if self.db_session:
            try:
                # Create new webhook record for each attempt
                params = "?mode=fail" if os.getenv("LEDGER_MODE_FAIL", "") == "fail" else ""
                webhook_id = str(uuid4())
                webhook_record = OutboundWebhookModel.create(
                    webhook_id=webhook_id,
                    event_type="BNPL_APPROVED",
                    payload=payload,
                    target_url=f"{self.target_url}/mock-ledger{params}"
                )
                self.db_session.add(webhook_record)
                # Don't flush yet - we'll commit after updating with results
                
                log.info(
                    "webhook_record_created",
                    step="webhook_service",
                    webhook_id=webhook_id
                )
                    
            except Exception as e:
                log.error(
                    "webhook_record_creation_failed",
                    step="webhook_service",
                    error=str(e),
                    exc_info=True
                )
                await self.db_session.rollback()
                webhook_record = None  # Ensure it's None if creation failed
        
        # Pass db_session and webhook_record to WebhookClient for recording individual attempts
        if self.db_session and webhook_record:
            self.webhook_client._db_session = self.db_session
            self.webhook_client._webhook_id = webhook_record.id
            self.webhook_client._webhook_record = webhook_record
        
        # Send webhook (WebhookClient handles retries internally)
        attempt_start = time.time()
        success, attempt_count = await self.webhook_client.send_webhook(
            plan_id=plan_id,
            decision_id=decision_id,
            user_id=user_id,
            amount_granted_cents=amount_granted_cents,
            request_id=request_id
        )
        attempt_duration = (time.time() - attempt_start) * 1000
        
        # Clear the references after use
        self.webhook_client._db_session = None
        self.webhook_client._webhook_id = None
        self.webhook_client._webhook_record = None
        
        # Update webhook record with attempt results and commit
        if self.db_session:
            if webhook_record:
                try:
                    # Update with actual attempt count from WebhookClient
                    webhook_record.update_attempt(success=success, latency_ms=int(attempt_duration), attempt_count=attempt_count)
                    # Ensure the record is still in the session
                    if webhook_record not in self.db_session:
                        self.db_session.add(webhook_record)
                    await self.db_session.commit()
                    
                    log.info(
                        "webhook_attempt_recorded",
                        step="webhook_service",
                        success=success,
                        attempts=webhook_record.attempts,
                        latency_ms=round(attempt_duration, 2),
                        status=webhook_record.status,
                        webhook_id=webhook_record.id
                    )
                except Exception as e:
                    log.error(
                        "webhook_attempt_update_failed",
                        step="webhook_service",
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True
                    )
                    # Don't fail the whole operation if recording fails
                    try:
                        await self.db_session.rollback()
                    except Exception as rollback_error:
                        log.error(
                            "webhook_rollback_failed",
                            step="webhook_service",
                            error=str(rollback_error),
                            exc_info=True
                        )
            else:
                # If webhook_record is None, try to create it now (fallback)
                try:
                    params = "?mode=fail" if os.getenv("LEDGER_MODE_FAIL", "") == "fail" else ""
                    webhook_id = str(uuid4())
                    webhook_record = OutboundWebhookModel.create(
                        webhook_id=webhook_id,
                        event_type="BNPL_APPROVED",
                        payload=payload,
                        target_url=f"{self.target_url}/mock-ledger{params}"
                    )
                    # Update with actual attempt count from WebhookClient
                    webhook_record.update_attempt(success=success, latency_ms=int(attempt_duration), attempt_count=attempt_count)
                    self.db_session.add(webhook_record)
                    await self.db_session.commit()
                    
                    log.info(
                        "webhook_record_created_and_recorded",
                        step="webhook_service",
                        webhook_id=webhook_id,
                        success=success,
                        attempts=webhook_record.attempts
                    )
                except Exception as e:
                    log.error(
                        "webhook_fallback_record_failed",
                        step="webhook_service",
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True
                    )
                    try:
                        await self.db_session.rollback()
                    except Exception:
                        pass
        
        return success

