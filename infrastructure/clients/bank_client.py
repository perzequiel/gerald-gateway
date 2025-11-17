"""
Bank API Client using httpx for async HTTP calls.

This client follows the Clean Architecture pattern and implements
the bank API communication layer with proper error handling and metrics.
"""
import httpx
from typing import Any
from datetime import datetime

from infrastructure.metrics.metrics import bank_fetch_failures_total
from domain.exceptions import BankAPIError


class BankClient:
    """
    HTTP client for fetching transactions from the bank API.
    
    Uses httpx.AsyncClient with configurable timeouts:
    - connect_timeout: 2 seconds (default)
    - read_timeout: 5 seconds (default)
    
    On failure, increments bank_fetch_failures_total metric.
    """
    
    def __init__(
        self,
        base_url: str,
        connect_timeout: float = 2.0,
        read_timeout: float = 5.0,
        api_key: str | None = None,
    ):
        """
        Initialize the bank client.
        
        Args:
            base_url: Base URL of the bank API (e.g., "https://api.bank.com")
            connect_timeout: Connection timeout in seconds (default: 2.0)
            read_timeout: Read timeout in seconds (default: 5.0)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.api_key = api_key
        
        # Create httpx client with timeouts
        # httpx.Timeout requires either a default or all four parameters
        # Using default as the read timeout, and connect separately
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=read_timeout,
                pool=connect_timeout,
            ),
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        )
    
    async def fetch_transactions(self, user_id: str) -> list[dict[str, Any]]:
        """
        Fetch transactions for a given user from the bank API.
        
        Args:
            user_id: The user identifier
            
        Returns:
            List of transaction dictionaries from the API
            
        Raises:
            BankAPIError: If the API call fails (non-2xx, timeout, or network error)
        """
        url = f"{self.base_url}/bank/transactions?user_id={user_id}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Handle different API response formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "transactions" in data:
                return data["transactions"]
            elif isinstance(data, dict) and "data" in data:
                return data["data"]
            else:
                return []
                
        except httpx.HTTPStatusError as e:
            bank_fetch_failures_total.inc()
            raise BankAPIError(
                f"Bank API returned {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.TimeoutException as e:
            bank_fetch_failures_total.inc()
            raise BankAPIError(
                f"Bank API request timed out after {self.read_timeout}s"
            ) from e
        except httpx.RequestError as e:
            bank_fetch_failures_total.inc()
            raise BankAPIError(
                f"Bank API request failed: {str(e)}"
            ) from e
        except Exception as e:
            bank_fetch_failures_total.inc()
            raise BankAPIError(
                f"Unexpected error fetching transactions: {str(e)}"
            ) from e
    
    async def close(self):
        """Close the httpx client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

