from datetime import timedelta
from .normalization import Normalization
from .internal_transactions import InternalTransaction

class MonthlyIncomeVsSpend:
    def __init__(self, income: float, spend: float):
        self.income = income
        self.spend = spend

class BasicsFeatures:
    def __init__(self):
        pass

    @staticmethod   
    def clamp(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    @staticmethod
    def calculate_avg_daily_balance(transactions: list[InternalTransaction]) -> float:
        # --- normalize and sort ---
        trxns = Normalization.normalize_and_sort_trxns(transactions)
        # --- build day -> last balance available that day ---
        day_last_balance = BasicsFeatures.fill_days_with_carry_forward(trxns)
        # --- calculate average daily balance ---
        start = trxns[0].date
        end = trxns[-1].date
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
    
    @staticmethod
    def fill_days_with_carry_forward(transactions: list[InternalTransaction]) -> list[InternalTransaction]:
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

    @staticmethod
    def calculate_monthly_income_vs_spend(transactions: list[InternalTransaction]) -> MonthlyIncomeVsSpend:
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
        txs_norm = Normalization.normalize_and_sort_trxns(transactions)
        start = txs_norm[0].date
        end = txs_norm[-1].date
        period_days = max(1, (end - start).days + 1)
        months = period_days / 30.0
        months = max(months, 1/30)  # avoid div by 0
        monthly_income = total_income / months
        monthly_spend = total_spend / months
        return MonthlyIncomeVsSpend(income=monthly_income, spend=monthly_spend)

    @staticmethod
    def calculate_nsf_count(transactions: list[InternalTransaction]) -> int:
        # --- NSF / overdraft count ---
        nsf_count = 0
        for t in transactions:
            if t.nsf is True:
                nsf_count += 1
            # if is debit and has balance_cents and after the debit the balance is < 0 -> counts as overdraft
            # (only count if nsf is not already True to avoid double counting)
            elif t.type == 'debit' and t.balance_cents is not None and t.balance_cents < 0:
                nsf_count += 1
        return nsf_count

    @staticmethod
    def calculate_balance_score(avg_daily_balance: float, balance_neg_cap: int) -> float:
        if avg_daily_balance >= 0:
            balance_score = 100.0
        else:
            balance_score = 100.0 * (1 - (min(abs(avg_daily_balance), balance_neg_cap) / balance_neg_cap))
        return BasicsFeatures.clamp(balance_score, 0.0, 100.0)

    @staticmethod
    def calculate_income_spend_score(monthly_income: float, monthly_spend: float) -> float:
        if monthly_spend <= 0:
            income_spend_score = 100.0
        else:
            ratio = monthly_income / monthly_spend
            income_spend_score = BasicsFeatures.clamp(ratio * 100.0, 0.0, 100.0)
        return income_spend_score

    @staticmethod
    def calculate_nsf_score(nsf_count: int, nsf_penalty: float) -> float:
        return BasicsFeatures.clamp(100.0 - nsf_count * nsf_penalty, 0.0, 100.0)
    
    @staticmethod
    def calculate_final_score(
        balance_score: float, 
        income_spend_score: float, 
        nsf_score: float, 
        balance_weight: float, 
        income_spend_weight: float, 
        nsf_weight: float,
        utilization_penalty: float = 0.0
    ) -> float:
        """Calculate final score with optional utilization penalty."""
        base_score = balance_score * balance_weight + income_spend_score * income_spend_weight + nsf_score * nsf_weight
        return BasicsFeatures.clamp(base_score - utilization_penalty, 0.0, 100.0)
    
    @staticmethod
    def calculate_limit_bucket(final_score: float, max_amount_for_limit_bucket: int) -> tuple[str, int]:
        if final_score < 20:
            return "0", 0
        elif final_score < 4000:
            return "100-400", 40000
        elif final_score < 7000:
            return "500", 50000
        else:
            return "1000", max_amount_for_limit_bucket