from dataclasses import dataclass
from datetime import datetime

from .transaction import Transaction


@dataclass
class User:
    user_id: str
    transactions: list[Transaction]

    @staticmethod
    def get_transactions(user_id: str) -> list[Transaction]:
        return [Transaction(
            transaction_id="1", 
            date=datetime.now(), 
            amount_cents=1000, 
            type="debit", 
            description="FoodiePlace", 
            category="restaurants", 
            merchant="FoodiePlace", 
            balance_cents=1000, 
            nsf=False
        )]