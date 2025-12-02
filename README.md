# Gerald Gateway

BNPL (Buy Now Pay Later) Decision API with risk scoring based on transaction analysis.

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Unix/macOS

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Copy and configure environment
cp .env.example .env

# 4. Start mock services
make mock-up

# 5. Apply database schema
make db-schema

# 6. Run server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# 7. Run tests
python -m pytest
```

---

## Environment Variables

All configuration is done through environment variables. Copy `.env.example` to `.env` and adjust as needed.

### BNPL Tier Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BNPL_TIER_A_LIMIT` | 20000 | Tier A limit in cents ($200) |
| `BNPL_TIER_B_LIMIT` | 12000 | Tier B limit in cents ($120) |
| `BNPL_TIER_C_LIMIT` | 6000 | Tier C limit in cents ($60) |
| `BNPL_TIER_D_LIMIT` | 2000 | Tier D limit in cents ($20) |
| `BNPL_TIER_A_MIN_SCORE` | 75 | Minimum score for Tier A |
| `BNPL_TIER_B_MIN_SCORE` | 55 | Minimum score for Tier B |
| `BNPL_TIER_C_MIN_SCORE` | 35 | Minimum score for Tier C |

**Example - More Generous Limits:**
```bash
BNPL_TIER_A_LIMIT=50000  # $500
BNPL_TIER_B_LIMIT=30000  # $300
BNPL_TIER_C_LIMIT=15000  # $150
BNPL_TIER_D_LIMIT=5000   # $50
```

### Cooldown Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `COOLDOWN_HOURS` | 72 | Hours between allowed advances |

**Effect:** User must wait this many hours after taking an advance before requesting another.

### Risk Calculation Weights

| Variable | Default | Description |
|----------|---------|-------------|
| `RISK_BALANCE_WEIGHT` | 0.5 | Weight of balance score (50%) |
| `RISK_INCOME_SPEND_WEIGHT` | 0.3 | Weight of income/spend score (30%) |
| `RISK_NSF_WEIGHT` | 0.2 | Weight of NSF score (20%) |
| `RISK_BALANCE_NEG_CAP` | 10000 | Balance cap in cents for score 0 |
| `RISK_NSF_PENALTY` | 25.0 | Points deducted per NSF event |
| `RISK_PAYBACK_PENALTY` | 10.0 | Points deducted for negative payback |

**Note:** Weights must sum to 1.0

**Example - Focus on Balance:**
```bash
RISK_BALANCE_WEIGHT=0.6
RISK_INCOME_SPEND_WEIGHT=0.25
RISK_NSF_WEIGHT=0.15
```

### Utilization Penalties

| Variable | Default | Description |
|----------|---------|-------------|
| `UTIL_PENALTY_HIGH_RISK` | 15.0 | Points deducted for high/critical risk |
| `UTIL_PENALTY_MEDIUM_RISK` | 7.5 | Points deducted for medium risk |

---

## Gaussian Scoring System

The utilization score uses a **Gaussian (Bell Curve)** function to evaluate financial health.

### Formula

```
score = exp(-((x - μ)² / (2σ²)))
```

Where:
- `x` = actual value
- `μ` (mu) = ideal value
- `σ` (sigma) = tolerance

### Utilization Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `UTIL_MU` | 0.6 | Ideal utilization (60% of paycheck) |
| `UTIL_SIGMA` | 0.3 | Tolerance for deviation |
| `UTIL_WEIGHT` | 0.45 | Weight in composite score (45%) |

**Effects:**
| Change | Result |
|--------|--------|
| ↑ `UTIL_MU` to 0.8 | Tolerates spending 80% of paycheck |
| ↓ `UTIL_MU` to 0.4 | Expects frugal 40% spending |
| ↑ `UTIL_SIGMA` to 0.5 | More lenient on deviations |
| ↓ `UTIL_SIGMA` to 0.2 | Stricter, penalizes quickly |

### Burn Days Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `BURN_MU` | 30.0 | Ideal burn days (paycheck lasts 30 days) |
| `BURN_SIGMA` | 15.0 | Tolerance |
| `BURN_WEIGHT` | 0.35 | Weight in composite score (35%) |

**Formula:** `burn_days = avg_paycheck / avg_daily_spend`

**Effects:**
| Change | Result |
|--------|--------|
| ↑ `BURN_MU` to 45 | Expects 1.5 month runway |
| ↓ `BURN_MU` to 14 | Accepts 2-week runway |

### Daily Spend Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `SPEND_MU` | 0.033 | Ideal daily spend ratio (3.3% of paycheck/day) |
| `SPEND_SIGMA` | 0.02 | Tolerance |
| `SPEND_WEIGHT` | 0.20 | Weight in composite score (20%) |

### Label Thresholds

| Variable | Default | Label Assigned |
|----------|---------|----------------|
| `LABEL_HEALTHY` | 80 | score ≥ 80 → "healthy" |
| `LABEL_MEDIUM_RISK` | 60 | score ≥ 60 → "medium-risk" |
| `LABEL_HIGH_RISK` | 40 | score ≥ 40 → "high-risk" |
| `LABEL_VERY_HIGH_RISK` | 20 | score ≥ 20 → "very-high-risk" |
| (below 20) | - | "critical-risk" |

**Example - More Lenient Classification:**
```bash
LABEL_HEALTHY=60
LABEL_MEDIUM_RISK=40
LABEL_HIGH_RISK=20
LABEL_VERY_HIGH_RISK=10
```

---

## Risk Classification Examples

| User | Utilization | Burn Days | Score | Label |
|------|-------------|-----------|-------|-------|
| **GOOD** | 85.9% | 34.9 | 80.4 | ✅ healthy |
| **GIG** | 489% | 6.1 | 2.0 | 🔴 critical-risk |
| **HIGHUTIL** | 289% | 10.4 | 5.2 | 🔴 critical-risk |
| **OVERDRAFT** | 322% | 9.3 | 4.1 | 🔴 critical-risk |

---

## Tier Assignment Logic

BNPL Philosophy: **Everyone gets approved**, limit sized by risk.

| Tier | Default Limit | Requirements |
|------|---------------|--------------|
| **Tier A** | $200 | score ≥ 75, healthy/medium util, positive/neutral payback |
| **Tier B** | $120 | score ≥ 55, positive/neutral payback |
| **Tier C** | $60 | score ≥ 35 |
| **Tier D** | $20 | Everyone else (fallback) |
| **Deny** | $0 | Only if in cooldown period |

---

## Tuning Guide

| Goal | Adjustments |
|------|-------------|
| **Approve higher amounts** | Increase `BNPL_TIER_*_LIMIT` values |
| **More users in Tier A** | Lower `BNPL_TIER_A_MIN_SCORE` |
| **Stricter risk assessment** | Decrease `sigma` values, increase `LABEL_*` thresholds |
| **Tolerate gig workers** | Increase `UTIL_MU`, decrease `BURN_MU` |
| **Faster cooldown** | Decrease `COOLDOWN_HOURS` |
| **Harsher NSF penalty** | Increase `RISK_NSF_PENALTY` |

---

## API Endpoints

### POST /v1/decision

Request a cash advance decision.

```bash
curl -X POST http://localhost:8080/v1/decision \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: unique-id-123" \
  -d '{"user_id": "user_good", "amount_requested_cents": 5000}'
```

**Response:**
```json
{
  "id": "uuid",
  "user_id": "user_good",
  "approved": true,
  "credit_limit_cents": 12000,
  "amount_granted_cents": 5000,
  "score": 70.5,
  "plan": {
    "id": "uuid",
    "installments": [...]
  }
}
```

### GET /v1/plan/{plan_id}

Get plan details with installments.

### GET /v1/decision/history?user_id=...

Get user's decision history.

### GET /metrics

Prometheus metrics endpoint.

---

## Development

### Running Tests

```bash
# All tests
python -m pytest

# Specific test file
python -m pytest tests/risk_calculation_test.py -v

# With coverage
python -m pytest --cov=domain --cov-report=html
```

### Docker Compose

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

---

## Architecture

```
gerald-gateway/
├── domain/
│   ├── config.py           # Environment variable configuration
│   ├── entities/           # Domain entities (Decision, Plan)
│   ├── interfaces/         # Repository interfaces
│   └── services/
│       ├── risk_calculation.py  # Main risk scoring service
│       ├── utilizations.py      # Gaussian scoring
│       ├── payback_capacity.py  # Payback analysis
│       └── cooldown.py          # Cooldown logic
├── application/
│   └── service/            # Use cases
├── infrastructure/
│   ├── db/                 # Database repositories
│   └── clients/            # External service clients
├── presentation/
│   └── api/                # FastAPI routers
└── tests/
```

---

## License

MIT
