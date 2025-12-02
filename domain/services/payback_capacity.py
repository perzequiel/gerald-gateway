"""
Payback Capacity Module

Calculates user's ability to repay an advance based on their financial metrics.
Used as an additional signal in BNPL risk scoring.
"""
from typing import TypedDict, Optional


class PaybackCapacityResult(TypedDict):
    payback_capacity_cents: int
    payback_label: str  # "positive" | "neutral" | "negative"
    explanation: str


def compute_payback_capacity(
    avg_daily_balance_cents: int,
    burn_days: Optional[float],
    avg_daily_spend_cents: Optional[int],
    avg_paycheck_cents: Optional[int] = None
) -> PaybackCapacityResult:
    """
    Compute payback capacity: estimates projected balance at next pay date.
    
    Formula:
        payback_capacity = avg_daily_balance + (burn_days * avg_daily_spend * -1)
        
    Explanation:
        - burn_days * avg_daily_spend = total spending until paycheck depleted
        - Adding avg_daily_balance estimates remaining funds
        - Negative result means user likely won't have funds to repay
    
    Args:
        avg_daily_balance_cents: Average daily balance in cents
        burn_days: Days until paycheck depleted (from utilization)
        avg_daily_spend_cents: Average daily spending in cents (can be None)
        avg_paycheck_cents: Optional paycheck amount for threshold calculation
    
    Returns:
        PaybackCapacityResult with capacity, label, and explanation
    """
    # Handle missing values with sensible defaults
    effective_burn_days = burn_days if burn_days and burn_days > 0 else 30.0
    effective_daily_spend = avg_daily_spend_cents if avg_daily_spend_cents else 0
    
    # Calculate projected spending until next paycheck
    projected_spending = int(effective_burn_days * effective_daily_spend)
    
    # Payback capacity = current balance - projected spending
    # This represents estimated funds available at paycheck depletion
    payback_capacity_cents = avg_daily_balance_cents - projected_spending
    
    # Determine threshold for "neutral" zone (10% of paycheck or $50 default)
    threshold = int(avg_paycheck_cents * 0.1) if avg_paycheck_cents else 5000  # $50 default
    
    # Label based on capacity
    if payback_capacity_cents > 0:
        label = "positive"
        explanation = f"User has ${payback_capacity_cents/100:.2f} projected surplus at paycheck depletion"
    elif payback_capacity_cents >= -threshold:
        label = "neutral"
        explanation = f"User has ${abs(payback_capacity_cents)/100:.2f} projected shortfall (within 10% threshold)"
    else:
        label = "negative"
        explanation = f"User has ${abs(payback_capacity_cents)/100:.2f} projected deficit - high repayment risk"
    
    return PaybackCapacityResult(
        payback_capacity_cents=payback_capacity_cents,
        payback_label=label,
        explanation=explanation
    )

