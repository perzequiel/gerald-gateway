# Risk Scoring Services

BNPL risk calculation module for Gerald Gateway.

## Overview

This module evaluates user financial health and determines BNPL (Buy Now Pay Later) eligibility. It combines multiple signals using weighted scoring and Gaussian analysis.

## Key Components

### `RiskCalculationService`

Main orchestrator for all risk calculations.

```python
from domain.services.risk_calculation import RiskCalculationService

svc = RiskCalculationService()
result = svc.calculate_risk(transactions, user_events=events)
```

### Signals Used

| Signal | Description | Weight/Impact |
|--------|-------------|---------------|
| `balance_score` | Average daily balance health | 50% |
| `income_spend_score` | Income vs spending ratio | 30% |
| `nsf_score` | NSF/overdraft penalty | 20% |
| `utilization` | Gaussian-scored burn rate | -15 to 0 penalty |
| `payback_capacity` | Projected repayment ability | -10 to 0 penalty |
| `cooldown` | Recent advance check | Blocks if active |

## BNPL Tiers

| Tier | Limit | Criteria |
|------|-------|----------|
| **Tier A** | $200 | score≥80, healthy util, positive payback |
| **Tier B** | $120 | score≥65, healthy/medium util, positive/neutral payback |
| **Tier C** | $60 | score≥50, NSF<3 |
| **Tier D** | $20 | score≥35, NSF<2 (trial) |
| **Deny** | $0 | Does not meet criteria |

## Penalties

### Utilization Penalty
Based on Gaussian-scored utilization label:
- `high-risk`, `very-high-risk`, `critical-risk`: **-15 points**
- `medium-risk`: **-7.5 points**
- `healthy`, `unknown`: **0 points**

### Payback Penalty
Based on projected payback capacity:
- `negative`: **-10 points** (configurable via `payback_penalty` param)
- `neutral`, `positive`: **0 points**

## Payback Capacity

Estimates user's ability to repay an advance:

```
payback_capacity = avg_daily_balance - (burn_days × avg_daily_spend)
```

**Labels:**
- `positive`: Surplus projected at paycheck depletion
- `neutral`: Shortfall within 10% of paycheck
- `negative`: Significant deficit - high repayment risk

## Cooldown

Prevents rapid successive advances:
- Default: **72 hours** between advances
- Configurable via `cooldown_hours` param
- Checks `user_events` for `advance_taken` type
- Fallback: Scans transactions for advance markers

## Explainability

Every decision includes detailed `reasons` array:
```python
[
    "Detected monthly income: $3,500.00 (confidence: 80%)",
    "Average daily balance: $450.00",
    "Monthly surplus: $500.00",
    "✓ No NSF/overdraft events",
    "Utilization: 65% (healthy)",
    "Burn rate: paycheck lasts 32 days",
    "Payback capacity: positive - User has $200.00 projected surplus",
    "📋 Decision: Tier B approved: score=72, acceptable utilization"
]
```

## Usage

### Basic Usage
```python
from domain.services.risk_calculation import RiskCalculationService

svc = RiskCalculationService()
result = svc.calculate_risk(transactions)

print(result["approved"])      # True/False
print(result["limit_amount"])  # cents
print(result["reasons"])       # human-readable list
```

### With Cooldown Events
```python
events = [
    {"type": "advance_taken", "timestamp": "2025-01-01T10:00:00Z"}
]
result = svc.calculate_risk(transactions, user_events=events)
```

### Custom Parameters
```python
svc = RiskCalculationService(
    balance_neg_cap=15000,      # Stricter balance penalty
    payback_penalty=15.0,       # Higher payback penalty
    cooldown_hours=48           # Shorter cooldown
)
```

## CLI Simulator

Test eligibility using JSON transaction files:

```bash
# Basic usage
python scripts/simulate_advance.py tests/data/transactions_user_good.json

# Verbose output
python scripts/simulate_advance.py tests/data/transactions_user_good.json -v

# With events (cooldown check)
python scripts/simulate_advance.py tests/data/transactions_user_good.json --events events.json

# JSON output
python scripts/simulate_advance.py tests/data/transactions_user_good.json --json
```

## Running Tests

```bash
# All risk-related tests
pytest tests/test_payback_capacity.py tests/test_decision_buckets.py tests/test_cooldown.py -v

# Quick smoke test
pytest tests/utilization_test.py -v

# All tests
pytest -q
```

## Files

| File | Description |
|------|-------------|
| `risk_calculation.py` | Main RiskCalculationService with tier decision |
| `utilizations.py` | Gaussian-scored utilization analysis |
| `payback_capacity.py` | Payback capacity computation |
| `cooldown.py` | Cooldown period enforcement |
| `basics_features.py` | Score calculation helpers |
| `decision.py` | Legacy decision service |
| `normalization.py` | Transaction normalization |

## Configuration

### Environment Variables (via UtilizationConfig)
```bash
UTIL_MU=0.6         # Ideal utilization %
BURN_MU=30.0        # Ideal burn days
LABEL_HEALTHY=80    # Healthy threshold
```

### Service Parameters
```python
RiskCalculationService(
    balance_neg_cap=10000,      # Balance penalty cap
    nsf_penalty=25.0,           # NSF score penalty
    balance_weight=0.5,         # Balance weight
    income_spend_weight=0.3,    # Income/spend weight
    nsf_weight=0.2,             # NSF weight
    payback_penalty=10.0,       # Payback negative penalty
    cooldown_hours=72           # Cooldown period
)
```
