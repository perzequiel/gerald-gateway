# Risk Calculation Service — README

**Quick Summary**

This module calculates a simple *risk score* and maps it to *limit buckets* from a list of transactions. It's designed to be integrated into a backend (e.g., FastAPI) or worker, and is intentionally explicit and easy to tune.

---

## What it does

1. Normalizes and sorts transactions by date.
2. Calculates **Average Daily Balance** with *carry-forward* (if there were no transactions on a day, it uses the last known balance).
3. Sums **income vs expenses** and monthlyizes them according to the analysis window.
4. Counts **NSF / overdraft events** (flag `nsf` or post-debit with `balance_cents < 0`).
5. Generates three components (balance, income/spend, nsf), weights them, and produces a `final_score` in 0–100.
6. Maps the `final_score` to a `limit_bucket` and `limit_amount` (e.g., `$0`, `$100-$400`, `$500`, `$1000+`).

---

## Design and contracts

* **Expected input:** a list of `InternalTransaction`. Each transaction must have at least:

  * `date` (date | str `YYYY-MM-DD` | datetime)
  * `type` (`'debit'` | `'credit'`)
  * `amount_cents` (int)
  * `balance_cents` (int | None) — recommended
  * `nsf` (bool | None)

* **Output:** `RiskScore` (TypedDict). Key fields:

  * `avg_daily_balance_cents`
  * `monthly_income_cents`, `monthly_spend_cents`
  * `nsf_count`
  * `component_scores` (balance, income_spend, nsf)
  * `final_score` (0–100)
  * `limit_bucket`, `limit_amount`
  * `reasons` (short list explaining the decision)

---

## Installation / Requirements

* Python 3.10+
* Optional typing (mypy recommended)
* Dependencies: no external dependencies.

### Folder location

The service is located at `domain/services/risk_calculation.py`

---

## Configuration (tunable parameters)

`RiskCalculationService` accepts parameters in its constructor so you can adapt it to your product:

* `balance_neg_cap: int` — negative cap where the balance component becomes 0. Default: `10_000` (cents). Adjust to your currency and risk appetite.
* `nsf_penalty: float` — how much each NSF event subtracts from the `nsf_score` component. Default: `25.0` (points).
* `balance_weight`, `income_spend_weight`, `nsf_weight` — weights for the final combination. Default: `0.5`, `0.3`, `0.2`.
* `max_amount_for_limit_bucket: int` — maximum value that represents the `$1000+` bucket. Default: `100_000` (cents).

**Rule of thumb:** try first with `balance_neg_cap` in the range of 5k–100k (depending on currency), and `nsf_penalty` between 10–40 to calibrate sensitivity.

---

## Usage examples (minimal usage, script)

```python
from domain.entities import Transaction
from domain.services.risk_calculation import RiskCalculationService
from datetime import datetime

# build transactions (minimal example)
transactions = [
    Transaction(
        transaction_id="1",
        date=datetime.now(),
        type="debit",
        amount_cents=19660,
        balance_cents=20340,
        nsf=False,
        description="Purchase",
        category="shopping",
        merchant="Store"
    ),
    Transaction(
        transaction_id="2",
        date=datetime.now(),
        type="credit",
        amount_cents=50000,
        balance_cents=70340,
        nsf=False,
        description="Salary",
        category="income",
        merchant="Bank"
    ),
    # ... more transactions
]

svc = RiskCalculationService()
result = svc.calculate_risk(transactions)
print(result)
# Output: {
#   "avg_daily_balance_cents": 45340,
#   "monthly_income_cents": 50000,
#   "monthly_spend_cents": 19660,
#   "nsf_count": 0,
#   "component_scores": {"balance_score": 100.0, "income_spend_score": 100.0, "nsf_score": 100.0},
#   "final_score": 100.0,
#   "limit_bucket": "$1000+",
#   "limit_amount": 100000,
#   "reasons": []
# }
```

---

## Local testing (unit tests)

Recommended tests to cover (pytest):

1. **Daily average**: period with days without transactions (carry-forward) and verify avg.
2. **Income vs spend**: short period and correct monthlyization.
3. **NSF counting**: nsf flag true and post-debit negative count, but don't duplicate.
4. **Score boundaries**: avg=0 => balance_score 100; avg <= -cap => balance_score 0.
5. **Bucket mapping**: test boundary values of `final_score`.

### Example tests (pytest)

The service accepts `Transaction` entities from `domain.entities` (or any object with the required attributes: `date`, `amount_cents`, `type`, `balance_cents`, `nsf`). The result is a dictionary-like `RiskScore` that can be accessed with keys.

### Running tests

Run tests with pytest:
```bash
python -m pytest tests/risk_calculation_test.py -v
```

Or run all tests:
```bash
python -m pytest
```

---

## Debugging / Observability

* Log `avg_daily_balance`, `monthly_income`, `monthly_spend`, `nsf_count` and `component_scores` per request to track calibration.
* Add metrics (Prometheus): `risk_requests_total`, `risk_score_histogram`, `nsf_events_total`.
* Store raw input along with the result in an S3 bucket or DB for 30 days to reproduce and audit decisions.

---

## Edge cases and important notes

* **Without `balance_cents` in transactions:** the service does carry-forward using the *last* known `balance_cents`; if there never is one, it assumes 0. This can skew the score: prefer normalizing transactions to always include balance whenever possible.
* **Out-of-order transactions or with timestamps different from the day:** the implementation uses stable sort by `date` (day). If you need time granularity (hours), expand `Transaction` and normalization.
* **Currency / cents:** this version assumes `amount_cents` and `balance_cents` are in the same currency and in cents. Convert beforehand if you need multi-currency.
* **Double counting NSF:** the implementation avoids duplicates using `elif` to not add twice if `nsf == True` and `balance_cents < 0` in the same transaction.

---

## How to tune in production

1. Collect a set of `N` real labeled cases (eligible / not eligible).
2. Run the service with default parameters and compare with labels.
3. Adjust `balance_neg_cap` and `nsf_penalty` seeking the best precision/recall according to your tradeoff.
4. If you need more performance: pre-aggregate daily balances upstream and pass only a daily summary.

---

## Performance and limits

* Complexity: `O(n)` in number of transactions for most operations + `O(num_days)` for daily fill. For month/year windows with many transactions, it's still reasonable.
* If you process millions of users: run in batch or with a worker pool and cache results.

---

## Quick integration checklist

* [ ] Ensure that `domain.entities.Transaction` exists and has the expected fields.
* [ ] Decide on API input format (Pydantic schema).
* [ ] Instrument logs and metrics.
* [ ] Add unit and integration tests.

---

## Example output (format)

```json
{
  "avg_daily_balance_cents": -35000,
  "monthly_income_cents": 45415,
  "monthly_spend_cents": 160000,
  "nsf_count": 6,
  "component_scores": {
    "balance_score": 0.0,
    "income_spend_score": 28.4,
    "nsf_score": 0.0
  },
  "final_score": 8.5,
  "limit_bucket": "$0",
  "limit_amount": 0,
  "max_amount_for_limit_bucket": 100000,
  "reasons": [
    "avg_daily_balance negative",
    "monthly spend > income",
    "6 overdraft/nsf events"
  ]
}
```
