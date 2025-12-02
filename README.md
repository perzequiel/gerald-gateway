# Gerald Gateway

BNPL (Buy Now Pay Later) Decision API with risk scoring based on transaction analysis.

## Dependencies

- Python 3.10+
- Docker
- PostgreSQL
- Terraform

## Local Install using virtual environment (venv)

1) Create virtual env
```bash
python -m venv venv
```

2) Activate environment
```bash
# Unix / Linux / macOS
source venv/bin/activate
# Windows (CMD)
venv\Scripts\activate.bat
```

3) Install dependencies
```bash
# For deveopment and testing purpose
pip install -r requirements-dev.txt
# For production or just running
pip install -r requirements.txt
```

4) Run test
```bash
python -m pytest
```

5) Copy env (create apikey and app key in Datadog)
```bash
cp .env.example .env
```

6) Run Datadog Agent 
```bash
docker compose up -d
## to restart the agent (apply changes)
docker restart dd-agent
```

7) Run Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

8) Build Datadog Dashboard
```bash
DD_API_KEY=dd_api_key DD_APP_KEY=dd_app_key python scripts/import_dashboard.py
```

---

## Risk Scoring System

### Overview

The system uses a **Gaussian (Bell Curve) Scoring Model** to evaluate user financial health based on transaction data. The composite score combines three weighted metrics to produce a risk label.

### Risk Classification Table

| Usuario | Utilization % | Burn Days | Composite Score | Label |
|---------|---------------|-----------|-----------------|-------|
| **GOOD** | 85.9% | 34.9 | 80.4 | ✅ healthy |
| **GIG** | 489% | 6.1 | 2.0 | 🔴 critical-risk |
| **HIGHUTIL** | 289% | 10.4 | 5.2 | 🔴 critical-risk |
| **OVERDRAFT** | 322% | 9.3 | 4.1 | 🔴 critical-risk |

### Gaussian Scoring Formula

The score for each metric is calculated using a Gaussian (bell curve) function:

```
score = exp(-((x - μ)² / (2σ²)))
```

Where:
- `x` = actual value of the metric
- `μ` (mu) = ideal/optimal value
- `σ` (sigma) = standard deviation (controls how quickly score drops)

**Visual representation:**

```
Score
  1.0 |        ****
      |      **    **
      |    **        **
  0.5 |  **            **
      | *                *
  0.0 |*__________________*____
           μ-2σ   μ   μ+2σ     Value
```

---

## Configurable Parameters

All scoring parameters are defined in `domain/services/utilizations.py` and can be adjusted to tune the risk model.

### 1. `UTILIZATION_PARAMS`

```python
UTILIZATION_PARAMS = (0.6, 0.3, 0.45)  # (mu, sigma, weight)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mu` | 0.6 (60%) | Ideal utilization percentage. Users spending ~60% of income are considered healthy. |
| `sigma` | 0.3 | How quickly score drops as utilization deviates from ideal. Lower = stricter. |
| `weight` | 0.45 (45%) | Contribution to final composite score. |

**Effect of changing values:**

| Change | Effect |
|--------|--------|
| ↑ mu (e.g., 0.8) | More tolerant of higher spending. Users at 80% util get max score. |
| ↓ mu (e.g., 0.4) | Stricter. Expects users to spend only 40% of income. |
| ↑ sigma (e.g., 0.5) | More lenient. Score drops slowly as util deviates. |
| ↓ sigma (e.g., 0.2) | Stricter. Score drops quickly for any deviation. |
| ↑ weight (e.g., 0.6) | Utilization has more impact on final score. |

**Note:** Uses **asymmetric Gaussian** - overspending (>μ) is penalized more harshly than underspending (<μ).

---

### 2. `BURN_DAYS_PARAMS`

```python
BURN_DAYS_PARAMS = (30.0, 15.0, 0.35)  # (mu, sigma, weight)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mu` | 30.0 days | Ideal burn days. User's paycheck should last ~30 days. |
| `sigma` | 15.0 | Tolerance for deviation from ideal. |
| `weight` | 0.35 (35%) | Contribution to final composite score. |

**Burn Days Formula:**
```
burn_days = avg_paycheck / avg_daily_spend
```

**Effect of changing values:**

| Change | Effect |
|--------|--------|
| ↑ mu (e.g., 45) | Expects users to have 1.5 months of runway. Stricter. |
| ↓ mu (e.g., 14) | More tolerant. 2-week runway is acceptable. |
| ↑ sigma (e.g., 25) | More tolerant of variation in burn rate. |
| ↓ sigma (e.g., 7) | Stricter. Burns < 23 or > 37 days penalized heavily. |

**Note:** Uses **asymmetric Gaussian** - low burn days (<μ) penalized more than high burn days (>μ), since saving is good.

---

### 3. `DAILY_SPEND_PARAMS`

```python
DAILY_SPEND_PARAMS = (0.033, 0.02, 0.20)  # (mu, sigma, weight)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mu` | 0.033 (3.3%) | Ideal daily spend as % of monthly paycheck. ~3.3%/day = 100%/month. |
| `sigma` | 0.02 | Tolerance for deviation. |
| `weight` | 0.20 (20%) | Contribution to final composite score. |

**Daily Spend Ratio Formula:**
```
daily_spend_ratio = avg_daily_spend / avg_paycheck
```

**Effect of changing values:**

| Change | Effect |
|--------|--------|
| ↑ mu (e.g., 0.05) | Tolerates higher daily spending (5% of paycheck/day). |
| ↓ mu (e.g., 0.02) | Stricter. Expects very frugal daily spending. |
| ↑ sigma (e.g., 0.04) | More tolerant of spending variation. |
| ↓ sigma (e.g., 0.01) | Very strict. Any deviation penalized heavily. |

---

### 4. `LABEL_THRESHOLDS`

```python
LABEL_THRESHOLDS = [
    (80, "healthy"),        # score >= 80
    (60, "medium-risk"),    # score >= 60
    (40, "high-risk"),      # score >= 40
    (20, "very-high-risk"), # score >= 20
    (0, "critical-risk"),   # score < 20
]
```

**Effect of changing thresholds:**

| Change | Effect |
|--------|--------|
| Lower thresholds | More users classified as healthy. Approves more loans. |
| Higher thresholds | Fewer users classified as healthy. More conservative. |
| Add more buckets | Finer granularity in risk classification. |

**Example - More Conservative:**
```python
LABEL_THRESHOLDS = [
    (90, "healthy"),        # Only top 10% are healthy
    (75, "medium-risk"),    
    (50, "high-risk"),      
    (25, "very-high-risk"), 
    (0, "critical-risk"),   
]
```

**Example - More Lenient:**
```python
LABEL_THRESHOLDS = [
    (60, "healthy"),        # 60+ score is healthy
    (40, "medium-risk"),    
    (20, "high-risk"),      
    (10, "very-high-risk"), 
    (0, "critical-risk"),   
]
```

---

## Composite Score Calculation

The final composite score (0-100) is calculated as:

```
composite_score = (
    utilization_score × utilization_weight +
    burn_days_score × burn_days_weight +
    daily_spend_score × daily_spend_weight
) × 100
```

**Default weights must sum to 1.0:**
- Utilization: 45%
- Burn Days: 35%
- Daily Spend: 20%

---

## Example Scenarios

### Healthy User (GOOD)
```
Utilization: 85.9% → score: 0.585 (close to ideal 60%)
Burn Days: 34.9 → score: 0.987 (close to ideal 30)
Daily Spend: 2.8%/day → score: 0.976 (close to ideal 3.3%)

Composite = (0.585×0.45 + 0.987×0.35 + 0.976×0.20) × 100 = 80.4
Label: healthy ✅
```

### High-Risk User (GIG)
```
Utilization: 489% → score: 0.0 (way over ideal)
Burn Days: 6.1 → score: 0.058 (burns paycheck in < 1 week)
Daily Spend: 16.3%/day → score: 0.0 (unsustainable)

Composite = (0.0×0.45 + 0.058×0.35 + 0.0×0.20) × 100 = 2.0
Label: critical-risk 🔴
```

---

## Tuning Recommendations

| Goal | Adjustments |
|------|-------------|
| **Approve more users** | Lower `LABEL_THRESHOLDS`, increase `sigma` values |
| **Be more conservative** | Raise `LABEL_THRESHOLDS`, decrease `sigma` values |
| **Focus on utilization** | Increase `UTILIZATION_PARAMS` weight |
| **Focus on runway** | Increase `BURN_DAYS_PARAMS` weight |
| **Tolerate gig workers** | Increase `mu` in `UTILIZATION_PARAMS`, lower burn_days `mu` |