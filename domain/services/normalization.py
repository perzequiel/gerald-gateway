from .internal_transactions import InternalTransaction
from datetime import datetime

class Normalization:
    @staticmethod
    def normalize_and_sort_trxns(transactions: list[InternalTransaction]) -> list[InternalTransaction]:
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