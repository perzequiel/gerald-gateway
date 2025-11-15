from dataclasses import dataclass
from datetime import datetime

@dataclass
class Transaction:
    transaction_id: str
    date: datetime
    amount_cents: int
    type: str
    description: str
    category: str
    merchant: str
    balance_cents: int
    nsf: bool