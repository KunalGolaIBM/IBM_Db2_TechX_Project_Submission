"""Demo payment adapter simulating UPI payments."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from payments.adapters.base import BasePaymentAdapter
from db.repositories.payment_repo import payment_repo
from ledger.service import ledger_service
from audit.service import audit_service


class DemoPaymentAdapter(BasePaymentAdapter):
    """Simulated payment adapter for demo environments."""

    provider_name = "DEMO_UPI"

    def initiate_payment(
        self,
        group_id: str,
        member_id: str,
        amount_minor: int,
        currency: str = "INR",
        idempotency_key: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Create a verified simulated payment and credit the member ledger."""
        if not idempotency_key:
            idempotency_key = f"demo_{group_id}_{member_id}_{uuid.uuid4()}"

        existing = payment_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        payment_id = str(uuid.uuid4())
        provider_txn_id = kwargs.get("provider_txn_id") or f"DEMO_TXN_{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)

        payment = payment_repo.create_payment(
            payment_id=payment_id,
            group_id=group_id,
            member_id=member_id,
            provider=self.provider_name,
            provider_txn_id=provider_txn_id,
            amount_minor=amount_minor,
            currency=currency,
            status="VERIFIED",
            source="DEMO",
            idempotency_key=idempotency_key,
            paid_at=now,
        )

        # Post CREDIT to ledger for member
        ledger_service.record_entry(
            group_id=group_id,
            member_id=member_id,
            entity_type="PAYMENT",
            entity_id=payment_id,
            entry_type="CREDIT",
            amount_minor=amount_minor,
            currency=currency,
        )

        audit_service.log(
            event_type="PAYMENT_RECORDED",
            group_id=group_id,
            actor_id=member_id,
            entity_type="PAYMENT",
            entity_id=payment_id,
            details={
                "amount_minor": amount_minor,
                "provider": self.provider_name,
                "provider_txn_id": provider_txn_id,
                "source": "DEMO",
            },
        )

        return payment

    def verify_payment(self, payment_id: str, provider_txn_id: str) -> bool:
        """In demo mode, payment is automatically verified."""
        payment = payment_repo.get_by_id(payment_id)
        return payment is not None and payment.get("STATUS") == "VERIFIED"


demo_payment_adapter = DemoPaymentAdapter()
