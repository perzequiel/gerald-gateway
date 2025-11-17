from datetime import datetime, timedelta
from typing import TypedDict

class InternalTransaction:
    date: datetime
    amount_cents: int
    type: str
    balance_cents: int
    nsf: bool


class ComponentScores(TypedDict):
    balance_score: float
    income_spend_score: float
    nsf_score: float

class RiskScore(TypedDict):
    def __init__(
        self,
        avg_daily_balance_cents: int,
        monthly_income_cents: int,
        monthly_spend_cents: int,
        nsf_count: int,
        balance_score: float,
        income_spend_score: float,
        nsf_score: float,
        final_score: float,
        max_amount_for_limit_bucket: int,
        limit_bucket: str,
        limit_amount: int,
        reasons: list[str],
    ):
        self.avg_daily_balance_cents = avg_daily_balance_cents
        self.monthly_income_cents = monthly_income_cents
        self.monthly_spend_cents = monthly_spend_cents
        self.nsf_count = nsf_count
        self.balance_score = balance_score
        self.income_spend_score = income_spend_score
        self.nsf_score = nsf_score
        self.final_score = final_score
        self.limit_bucket = limit_bucket
        self.limit_amount = limit_amount
        self.reasons = reasons
        self.max_amount_for_limit_bucket = max_amount_for_limit_bucket
        self.component_scores = ComponentScores(
            balance_score=balance_score,
            income_spend_score=income_spend_score,
            nsf_score=nsf_score
        )

class RiskCalculationService:
    def __init__(self, balance_neg_cap: int = 10_000,
        nsf_penalty: float = 25.0,
        balance_weight: float = 0.5,
        income_spend_weight: float = 0.3,
        nsf_weight: float = 0.2,
        max_amount_for_limit_bucket: int = 100_000
    ):
        # this is the balance negative cap, if the average daily balance is less than this value, the score is 0
        self.balance_neg_cap = balance_neg_cap
        # this is the penalty for each NSF event, if the number of NSF events is greater than 0, the score is reduced by this value
        self.nsf_penalty = nsf_penalty
        # this is the weight for the balance score, if the balance score is greater than 0, the score is increased by this value
        self.balance_weight = balance_weight
        # this is the weight for the income vs spend score, if the income vs spend score is greater than 0, the score is increased by this value
        self.income_spend_weight = income_spend_weight
        # this is the weight for the NSF score, if the NSF score is greater than 0, the score is increased by this value
        self.nsf_weight = nsf_weight
        # maximum amount for the limit bucket $1000+
        self.max_amount_for_limit_bucket = max_amount_for_limit_bucket

    # private method
    def __clamp(self, x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    # private method
    def __normalize_and_sort_transactions(self, transactions: list[InternalTransaction]) -> list[InternalTransaction]:
        # Normalize dates to date objects (drop time) deterministically
        for t in transactions:
            if isinstance(t.date, str):
                t.date = datetime.strptime(t.date, "%Y-%m-%d").date()
            elif isinstance(t.date, datetime):
                t.date = t.date.date()
            # if already a date, keep it
        # Stable sort by date (preserves input order within the same day)
        txs = sorted(transactions, key=lambda t: t.date)
        return txs

    # private method
    def __fill_days_with_carry_forward(self, transactions: list[InternalTransaction]) -> list[InternalTransaction]:
        day_last_balance = {}
        last_known_balance = 0
        for t in transactions:
            day = t.date
            # Update rolling last known balance if this txn reports one
            if t.balance_cents is not None:
                last_known_balance = t.balance_cents
            # Record the FIRST value for the day only (first-of-day policy)
            if day not in day_last_balance:
                if t.balance_cents is not None:
                    day_last_balance[day] = t.balance_cents
                else:
                    day_last_balance[day] = last_known_balance
        return day_last_balance

    def __calculate_avg_daily_balance(self, transactions: list[InternalTransaction]) -> float:
        # --- normalize and sort ---
        txs = self.__normalize_and_sort_transactions(transactions)
        # --- build day -> last balance available that day ---
        day_last_balance = self.__fill_days_with_carry_forward(txs)
        # --- calculate average daily balance ---
        start = txs[0].date
        end = txs[-1].date
        daily_balances = []
        num_days = (end - start).days + 1
        last_known = None
        for i in range(num_days):
            d = start + timedelta(days=i)
            if d in day_last_balance:
                last_known = day_last_balance[d]
                daily_balances.append(last_known)
            else:
                daily_balances.append(last_known if last_known is not None else 0)
        return sum(daily_balances) / max(1, len(daily_balances))

    def calculate_risk(self, transactions: list[InternalTransaction]) -> RiskScore:
        """
        Input: list of transactions (each with keys: 'date' YYYY-MM-DD, 'amount_cents', 'type' ('debit'|'credit'),
            'balance_cents' (opcional), 'nsf' (optional bool)).
        Output: dict with metrics and decision: avg_daily_balance, monthly_income_cents, monthly_spend_cents,
                nsf_count, score (0-100), limit_bucket (string) y razones básicas.
        Logic:
        - Avg daily balance: fill days without tx with the last known balance (carry-forward).
        - Income vs spend: sum credits and debits and monthlyize them according to the date range.
        - NSF/overdrafts: count events where nsf==True or where after a debit the balance (reported) is < 0.
        - Score: weighted combination of (balance, income/spend ratio, nsf_count).
        - Bucket: simple mapping of the score to predefined limits.
        """
        if not transactions:
            return {"error": "no transactions"}

        # average daily balance
        avg_daily_balance = self.__calculate_avg_daily_balance(transactions)

        # income vs spend (sum totals)
        total_income = 0
        total_spend = 0 
        for t in transactions:
            if t.type == 'credit':
                total_income += t.amount_cents
            else:
                total_spend += t.amount_cents

        # monthlyize: calculate factor months in the period (portions of 30 days)
        # Use normalized, sorted transactions for deterministic start/end
        txs_norm = self.__normalize_and_sort_transactions(transactions)
        start = txs_norm[0].date
        end = txs_norm[-1].date
        period_days = max(1, (end - start).days + 1)
        months = period_days / 30.0
        months = max(months, 1/30)  # avoid div by 0
        monthly_income = total_income / months
        monthly_spend = total_spend / months

        # --- NSF / overdraft count ---
        nsf_count = 0
        for t in transactions:
            if t.nsf is True:
                nsf_count += 1
            # if is debit and has balance_cents and after the debit the balance is < 0 -> counts as overdraft
            # (only count if nsf is not already True to avoid double counting)
            elif t.type == 'debit' and t.balance_cents is not None and t.balance_cents < 0:
                nsf_count += 1

        # --- scoring components ---
        # 1) balance_score: if avg >= 0 => 100, if avg <= -self.balance_neg_cap => 0, linear between medias  
        if avg_daily_balance >= 0:
            balance_score = 100.0
        else:
            balance_score = 100.0 * (1 - (min(abs(avg_daily_balance), self.balance_neg_cap) / self.balance_neg_cap))
        balance_score = self.__clamp(balance_score, 0.0, 100.0)

        # 2) income vs spend score: ratio = income / spend (if spend=0 => 100)
        if monthly_spend <= 0:
            income_spend_score = 100.0
        else:
            ratio = monthly_income / monthly_spend
            income_spend_score = self.__clamp(ratio * 100.0, 0.0, 100.0)

        # 3) nsf score: penalize quickly for each event (eg: 0 events => 100, 4+ => 0)
        nsf_score = self.__clamp(100.0 - nsf_count * self.nsf_penalty, 0.0, 100.0)

        # weighted combination (adjust weights if you want)
        final_score = (self.balance_weight * balance_score) + (self.income_spend_weight * income_spend_score) + (self.nsf_weight * nsf_score)
        final_score = self.__clamp(final_score, 0.0, 100.0)

        # --- bucket mapping (simple example) ---
        if final_score < 20:
            limit_bucket = "$0"
            limit_amount = 0
        elif final_score < 40:
            limit_bucket = "$100 - $400"
            limit_amount = 400
        elif final_score < 70:
            limit_bucket = "$500"
            limit_amount = 500
        else:
            limit_bucket = "$1000+"
            limit_amount = self.max_amount_for_limit_bucket
        # reasons breakdown
        reasons = []
        if avg_daily_balance < 0:
            reasons.append("avg_daily_balance negative")
        if monthly_income < monthly_spend:
            reasons.append("monthly spend > income")
        if nsf_count > 0:
            reasons.append(f"{nsf_count} overdraft/nsf events")

        return RiskScore(
            avg_daily_balance_cents=int(avg_daily_balance), 
            monthly_income_cents=int(monthly_income),
            monthly_spend_cents=int(monthly_spend),
            nsf_count=nsf_count,
            balance_score=round(balance_score, 1),
            income_spend_score=round(income_spend_score, 1),
            nsf_score=round(nsf_score, 1),
            final_score=round(final_score, 1),
            limit_bucket=limit_bucket,
            limit_amount=limit_amount,
            reasons=reasons,
            component_scores=ComponentScores(
                balance_score=round(balance_score, 1),
                income_spend_score=round(income_spend_score, 1),
                nsf_score=round(nsf_score, 1)
            ),
            max_amount_for_limit_bucket=self.max_amount_for_limit_bucket
        )