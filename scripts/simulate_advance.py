#!/usr/bin/env python3
"""
BNPL Advance Eligibility Simulator

Simulates the full risk calculation flow using transaction data from a JSON file.

Usage:
    python scripts/simulate_advance.py tests/data/transactions_user_good.json
    python scripts/simulate_advance.py tests/data/transactions_user_gig.json --events events.json
    python scripts/simulate_advance.py tests/data/transactions_user_overdraft.json --verbose

Arguments:
    file_path: Path to transactions JSON file
    --events: Optional path to user events JSON (for cooldown check)
    --verbose: Show detailed breakdown
    --json: Output raw JSON instead of formatted text
"""
import argparse
import json
import os
import sys
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from domain.entities import Transaction
from domain.services.normalization import Normalization
from domain.services.risk_calculation import RiskCalculationService


def load_transactions(file_path: str) -> list[Transaction]:
    """Load transactions from JSON file."""
    with open(file_path, "r") as f:
        raw = json.load(f)
    
    transactions = []
    for t in raw["transactions"]:
        tx = Transaction(
            transaction_id=t["transaction_id"],
            date=datetime.strptime(t["date"], "%Y-%m-%d"),
            amount_cents=t["amount_cents"],
            type=t["type"],
            description=t.get("description", ""),
            category=t.get("category", ""),
            merchant=t.get("merchant", ""),
            balance_cents=t.get("balance_cents", 0),
            nsf=t.get("nsf", False),
        )
        transactions.append(tx)
    
    return Normalization.normalize_and_sort_trxns(transactions)


def load_events(file_path: str) -> list[dict]:
    """Load user events from JSON file."""
    with open(file_path, "r") as f:
        return json.load(f)


def format_result(result: dict, verbose: bool = False) -> str:
    """Format result for human-readable output."""
    lines = []
    
    # Header
    lines.append("=" * 60)
    lines.append("BNPL ADVANCE ELIGIBILITY RESULT")
    lines.append("=" * 60)
    
    # Decision
    approved = result.get("approved", False)
    status = "✅ APPROVED" if approved else "❌ DENIED"
    lines.append(f"\nStatus: {status}")
    lines.append(f"Tier: {result['limit_bucket']}")
    lines.append(f"Limit: ${result['limit_amount']/100:.2f}")
    lines.append(f"Final Score: {result['final_score']}/100")
    
    # Quick summary
    lines.append("\n--- Summary ---")
    lines.append(f"Avg Daily Balance: ${result['avg_daily_balance_cents']/100:,.2f}")
    lines.append(f"Monthly Income: ${result['monthly_income_cents']/100:,.2f}")
    lines.append(f"Monthly Spend: ${result['monthly_spend_cents']/100:,.2f}")
    lines.append(f"NSF Events: {result['nsf_count']}")
    
    # Signals
    util = result.get("utilization_info", {})
    payback = result.get("payback_capacity", {})
    cooldown = result.get("cooldown", {})
    
    lines.append("\n--- Signals ---")
    lines.append(f"Utilization: {util.get('utilization_label', 'N/A')} ({util.get('utilization_pct', 0)*100:.0f}%)")
    lines.append(f"Burn Days: {util.get('burn_days', 'N/A')}")
    lines.append(f"Payback: {payback.get('payback_label', 'N/A')} (${payback.get('payback_capacity_cents', 0)/100:,.2f})")
    lines.append(f"Cooldown: {'Active' if cooldown.get('is_in_cooldown') else 'Not Active'}")
    
    if verbose:
        # Component scores
        scores = result.get("component_scores", {})
        lines.append("\n--- Component Scores ---")
        lines.append(f"Balance Score: {scores.get('balance_score', 0)}/100")
        lines.append(f"Income/Spend Score: {scores.get('income_spend_score', 0)}/100")
        lines.append(f"NSF Score: {scores.get('nsf_score', 0)}/100")
        
        # Penalties
        penalties = result.get("penalties_applied", {})
        lines.append("\n--- Penalties ---")
        lines.append(f"Utilization Penalty: -{penalties.get('utilization_penalty', 0)} points")
        lines.append(f"Payback Penalty: -{penalties.get('payback_penalty', 0)} points")
        
        # Reasons
        lines.append("\n--- Reasons ---")
        for reason in result.get("reasons", []):
            lines.append(f"  • {reason}")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate BNPL advance eligibility check"
    )
    parser.add_argument(
        "file_path",
        help="Path to transactions JSON file"
    )
    parser.add_argument(
        "--events",
        help="Path to user events JSON (for cooldown)",
        default=None
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed breakdown"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON"
    )
    
    args = parser.parse_args()
    
    # Load data
    try:
        transactions = load_transactions(args.file_path)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.file_path}: {e}")
        sys.exit(1)
    
    # Load events if provided
    user_events = None
    if args.events:
        try:
            user_events = load_events(args.events)
        except FileNotFoundError:
            print(f"Warning: Events file not found: {args.events}")
    
    # Run calculation
    svc = RiskCalculationService()
    result = svc.calculate_risk(transactions, user_events=user_events)
    
    # Output
    if args.json:
        # Convert non-serializable objects
        output = {}
        for k, v in result.items():
            if k == "utilization_info":
                # Remove date objects
                v = {ik: iv for ik, iv in v.items() if not isinstance(iv, (datetime, type(None).__class__)) or iv is None}
                if "cycle_start" in v and v["cycle_start"]:
                    v["cycle_start"] = str(v["cycle_start"])
                if "cycle_end" in v and v["cycle_end"]:
                    v["cycle_end"] = str(v["cycle_end"])
            output[k] = v
        print(json.dumps(output, indent=2, default=str))
    else:
        print(format_result(result, verbose=args.verbose))


if __name__ == "__main__":
    main()

