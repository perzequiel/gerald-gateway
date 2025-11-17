"""
Transaction Repository implementation using the Bank API client.

This adapter implements the TransactionRepository protocol from domain/interfaces
by fetching transactions from an external bank API instead of a database.
"""
from typing import Any
from datetime import datetime

from domain.entities import Transaction
from domain.interfaces import TransactionRepository
from infrastructure.clients.bank_client import BankClient


class TransactionRepoAPI(TransactionRepository):
    """
    Repository implementation that fetches transactions from the bank API.
    
    This follows the Adapter pattern, implementing the domain protocol
    while delegating to the infrastructure BankClient.
    """
    
    def __init__(self, bank_client: BankClient):
        """
        Initialize the repository with a bank client.
        
        Args:
            bank_client: An instance of BankClient for API calls
        """
        self.bank_client = bank_client
    
    async def get_user_transactions(self, user_id: str) -> list[Transaction]:
        """
        Fetch user transactions from the bank API and convert them to domain entities.
        
        Args:
            user_id: The user identifier
            
        Returns:
            List of Transaction domain entities
            
        Raises:
            BankAPIError: If the API call fails
        """
        # Fetch raw transaction data from API
        raw_transactions = await self.bank_client.fetch_transactions(user_id)
        
        # Convert API response to domain entities
        transactions = []
        for raw_txn in raw_transactions:
            transaction = self._map_to_domain_entity(raw_txn)
            transactions.append(transaction)
        
        return transactions
    
    def _map_to_domain_entity(self, raw_txn: dict[str, Any]) -> Transaction:
        """
        Map a raw API transaction dictionary to a domain Transaction entity.
        
        This method handles different API response formats and converts
        them to the standard domain model.
        
        Args:
            raw_txn: Raw transaction dictionary from the API
            
        Returns:
            Transaction domain entity
        """
        # Parse date - handle multiple formats
        date_str = raw_txn.get("date") or raw_txn.get("transaction_date") or raw_txn.get("timestamp")
        if isinstance(date_str, str):
            # Try ISO format first, then other common formats
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                # Fallback to other formats if needed
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
        elif isinstance(date_str, (int, float)):
            # Unix timestamp
            date = datetime.fromtimestamp(date_str)
        else:
            date = datetime.now()
        
        # Map fields with fallbacks for different API formats
        return Transaction(
            transaction_id=str(raw_txn.get("id") or raw_txn.get("transaction_id") or ""),
            date=date,
            amount_cents=int(raw_txn.get("amount_cents") or raw_txn.get("amount") or 0),
            type=str(raw_txn.get("type") or raw_txn.get("transaction_type") or "debit").lower(),
            description=str(raw_txn.get("description") or raw_txn.get("memo") or ""),
            category=str(raw_txn.get("category") or ""),
            merchant=str(raw_txn.get("merchant") or raw_txn.get("merchant_name") or ""),
            balance_cents=int(raw_txn.get("balance_cents") or raw_txn.get("balance") or 0),
            nsf=bool(raw_txn.get("nsf") or raw_txn.get("is_nsf") or False),
        )

