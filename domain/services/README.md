# Risk Scoring Services

This module contains the core risk calculation logic for the BNPL decision API.

## Overview

The risk scoring system evaluates user financial health based on transaction history and produces a credit limit recommendation.

## Key Components

### `RiskCalculationService`

Main service that orchestrates all risk calculations.

```python
from domain.services.risk_calculation import RiskCalculationService

svc = RiskCalculationService()
result = svc.calculate_risk(transactions)
```

**Returns:**
- `final_score`: 0-100 composite risk score
- `component_scores`: breakdown (balance, income_spend, nsf)
- `utilization_info`: utilization metrics with Gaussian scoring
- `limit_bucket`: recommended credit limit tier
- `reasons`: human-readable explainability strings

### `UtilizationService`

Calculates utilization metrics using **Gaussian (Bell Curve) Scoring**.

```python
from domain.services.utilizations import UtilizationService, PaycheckInfo, UtilizationConfig

# With default config
service = UtilizationService(transactions, paycheck_info)
result = service.calculate()

# With custom config
config = UtilizationConfig(
    utilization_params=(0.7, 0.35, 0.45),  # (mu, sigma, weight)
    burn_days_params=(25.0, 12.0, 0.35),
    daily_spend_params=(0.04, 0.025, 0.20)
)
service = UtilizationService(transactions, paycheck_info, config=config)
```

## Utilization Penalty Integration

The utilization signal affects `final_score` through a penalty system:

| Utilization Label | Penalty Applied |
|-------------------|-----------------|
| `critical-risk` | 15.0 points |
| `very-high-risk` | 15.0 points |
| `high-risk` | 15.0 points |
| `medium-risk` | 7.5 points |
| `healthy` | 0.0 points |
| `unknown` | 0.0 points |

**Formula:**
```
final_score = weighted_combination(balance, income_spend, nsf) - utilization_penalty
final_score = clamp(final_score, 0, 100)
```

## Paycheck Fallback

When no explicit paycheck detection is available, the system uses a fallback:

```python
paycheck_info = PaycheckInfo(
    avg_paycheck_cents=int(monthly_income) if monthly_income > 0 else None,
    period_days=30,  # assume monthly cycle
    paycheck_confidence=0.8 if monthly_income > 0 else 0.0
)
```

## Explainability

The `reasons` list in the response includes human-readable explanations:

```
[
  "avg_daily_balance negative",
  "monthly_income < monthly_spend", 
  "high cycle utilization (user burns paycheck quickly)",
  "utilization_label=critical-risk, utilization_pct=4.89"
]
```

## Configuration via Environment Variables

```bash
# Utilization Gaussian params
UTIL_MU=0.6        # ideal utilization %
UTIL_SIGMA=0.3     # tolerance
UTIL_WEIGHT=0.45   # weight in composite

# Burn days params  
BURN_MU=30.0       # ideal burn days
BURN_SIGMA=15.0
BURN_WEIGHT=0.35

# Daily spend params
SPEND_MU=0.033     # ideal daily spend ratio
SPEND_SIGMA=0.02
SPEND_WEIGHT=0.20

# Label thresholds
LABEL_HEALTHY=80
LABEL_MEDIUM=60
LABEL_HIGH=40
LABEL_VERY_HIGH=20
```

## Running Tests

```bash
# All risk-related tests
pytest tests/risk_calculation_test.py tests/utilization_test.py -v

# Quick smoke test
pytest tests/utilization_test.py::TestRiskCalculationSmoke -v
```

## Files

- `risk_calculation.py` - Main RiskCalculationService
- `utilizations.py` - UtilizationService with Gaussian scoring
- `basics_features.py` - Score calculation helpers
- `decision.py` - DecisionService for reasons generation
- `normalization.py` - Transaction normalization

