"""Base abstract payment adapter."""

from abc import ABC, abstractmethod
from typing import Optional


class BasePaymentAdapter(ABC):
    """Abstract interface for payment gateway providers."""

    @abstractmethod
    def initiate_payment(
        self,
        group_id: str,
        member_id: str,
        amount_minor: int,
        currency: str = "INR",
        idempotency_key: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Initiate or simulate a payment transaction."""
        pass

    @abstractmethod
    def verify_payment(self, payment_id: str, provider_txn_id: str) -> bool:
        """Verify payment confirmation with provider."""
        pass
