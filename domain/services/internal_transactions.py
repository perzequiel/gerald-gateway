from datetime import datetime

class InternalTransaction:
    date: datetime
    amount_cents: int
    type: str
    balance_cents: int
    nsf: bool