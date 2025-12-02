class DecisionService:
    def __init__(self,
        avg_daily_balance: float,
        monthly_income: str,
        monthly_spend: int,
        nsf_count: int,
        utilization_info: dict
    ):
        self.avg_daily_balance = avg_daily_balance
        self.monthly_income = monthly_income
        self.monthly_spend = monthly_spend
        self.nsf_count = nsf_count
        self.utilization_info = utilization_info

    def make_decision(self) -> str:
        reasons = []
        if self.avg_daily_balance < 0:
            reasons.append("avg_daily_balance negative")
        if self.monthly_income < self.monthly_spend:
            reasons.append("monthly_income < monthly_spend")
        if self.nsf_count > 0:
            reasons.append(f"{self.nsf_count} overdraft/nsf events")
        if self.utilization_info.get("utilization_label") == "high-risk":
            reasons.append("high cycle utilization (user burns paycheck quickly)")
        elif self.utilization_info.get("utilization_label") == "medium-risk":
            reasons.append("medium cycle utilization")
        return reasons