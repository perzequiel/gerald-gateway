"""
Cooldown Module

Implements cooldown logic to prevent users from taking multiple advances
within a short time period (72 hours default).
"""
from datetime import datetime, timedelta
from typing import TypedDict, Optional


class CooldownResult(TypedDict):
    is_in_cooldown: bool
    remaining_hours: Optional[float]
    last_advance_at: Optional[str]
    explanation: str


# Default cooldown period in hours
DEFAULT_COOLDOWN_HOURS = 72


def compute_cooldown(
    user_events: Optional[list[dict]] = None,
    transactions: Optional[list] = None,
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS
) -> CooldownResult:
    """
    Check if user is in cooldown period after a recent advance.
    
    Args:
        user_events: List of event dicts with 'type' and 'timestamp' keys.
                    Look for type='advance_taken' or 'cash_advance'.
        transactions: Alternative - check transactions for advance markers
                     (description containing 'advance' or 'gerald' disbursement)
        cooldown_hours: Cooldown period in hours (default 72)
    
    Returns:
        CooldownResult with cooldown status and remaining time
    """
    now = datetime.now()
    cooldown_threshold = now - timedelta(hours=cooldown_hours)
    
    last_advance_time = None
    
    # Check user_events first (preferred source)
    if user_events:
        for event in user_events:
            event_type = event.get("type", "").lower()
            if event_type in ("advance_taken", "cash_advance", "disbursement"):
                timestamp = event.get("timestamp") or event.get("created_at")
                if timestamp:
                    if isinstance(timestamp, str):
                        try:
                            event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            # Make naive for comparison
                            if event_time.tzinfo:
                                event_time = event_time.replace(tzinfo=None)
                        except ValueError:
                            continue
                    else:
                        event_time = timestamp
                    
                    if last_advance_time is None or event_time > last_advance_time:
                        last_advance_time = event_time
    
    # Fallback: check transactions for advance markers
    if last_advance_time is None and transactions:
        for tx in transactions:
            description = getattr(tx, 'description', '') or ''
            category = getattr(tx, 'category', '') or ''
            tx_type = getattr(tx, 'type', '')
            
            # Look for advance indicators
            is_advance = (
                'advance' in description.lower() or
                'gerald' in description.lower() or
                'disbursement' in description.lower() or
                category.lower() == 'cash_advance'
            )
            
            if is_advance and tx_type == 'credit':
                tx_date = getattr(tx, 'date', None)
                if tx_date:
                    if isinstance(tx_date, datetime):
                        event_time = tx_date
                    else:
                        # It's a date object, convert to datetime
                        event_time = datetime.combine(tx_date, datetime.min.time())
                    
                    if last_advance_time is None or event_time > last_advance_time:
                        last_advance_time = event_time
    
    # Determine cooldown status
    if last_advance_time is None:
        return CooldownResult(
            is_in_cooldown=False,
            remaining_hours=None,
            last_advance_at=None,
            explanation="No previous advance found - eligible for new advance"
        )
    
    if last_advance_time > cooldown_threshold:
        # In cooldown
        elapsed = now - last_advance_time
        remaining = timedelta(hours=cooldown_hours) - elapsed
        remaining_hours = remaining.total_seconds() / 3600
        
        return CooldownResult(
            is_in_cooldown=True,
            remaining_hours=round(remaining_hours, 1),
            last_advance_at=last_advance_time.isoformat(),
            explanation=f"Cooldown active: {remaining_hours:.1f} hours remaining (last advance: {last_advance_time.strftime('%Y-%m-%d %H:%M')})"
        )
    else:
        return CooldownResult(
            is_in_cooldown=False,
            remaining_hours=0,
            last_advance_at=last_advance_time.isoformat(),
            explanation=f"Cooldown expired - eligible for new advance (last advance: {last_advance_time.strftime('%Y-%m-%d %H:%M')})"
        )

