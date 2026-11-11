"""Payment service handling QR generation and demo payment processing."""

import base64
import io
import logging
from typing import Optional

from config import settings
from db.repositories.member_repo import member_repo
from db.repositories.payment_repo import payment_repo
from payments.adapters.demo import demo_payment_adapter
from ledger.service import ledger_service
from audit.service import audit_service
from api.middleware import AppError

logger = logging.getLogger(__name__)


class PaymentService:
    """Handles UPI QR generation and demo settlement payments."""

    def _require_membership(self, group_id: str, user_id: str) -> dict:
        """Verify user is an active member of group."""
        member = member_repo.get_member_by_group_and_user(group_id, user_id)
        if not member:
            raise AppError(403, "Access denied. You are not a member of this group.")
        return member

    def generate_qr(self, group_id: str, amount_minor: Optional[int] = None) -> dict:
        """Generate simulated UPI payment QR code as base64 PNG."""
        upi_uri = (
            f"upi://pay?pa={settings.demo_upi_id}&pn=SplitSyncGroup&mc=0000&tid={group_id}"
        )
        if amount_minor is not None and amount_minor > 0:
            upi_uri += f"&am={amount_minor / 100:.2f}&cu=INR"

        qr_base64 = ""
        try:
            import qrcode  # type: ignore

            qr = qrcode.QRCode(box_size=8, border=2)
            qr.add_data(upi_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as exc:
            logger.debug("QR code generation fallback: %s", exc)
            # 1x1 transparent png data fallback if qrcode/pillow is uninstalled
            qr_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

        return {
            "qr_code_base64": qr_base64,
            "upi_uri": upi_uri,
            "demo_upi_id": settings.demo_upi_id,
            "group_id": group_id,
            "amount_minor": amount_minor,
            "demo_mode": True,
        }

    def record_demo_payment(
        self,
        group_id: str,
        user_id: str,
        amount_minor: int,
        provider_txn_id: Optional[str] = None,
    ) -> dict:
        """Create and verify a simulated demo payment."""
        member = self._require_membership(group_id, user_id)
        if amount_minor <= 0:
            raise AppError(400, "Payment amount must be greater than zero")

        payment = demo_payment_adapter.initiate_payment(
            group_id=group_id,
            member_id=member["GROUP_MEMBER_ID"],
            amount_minor=amount_minor,
            currency="INR",
            provider_txn_id=provider_txn_id,
        )
        return self._format_payment(payment)

    def list_payments(self, group_id: str, user_id: str) -> list[dict]:
        """Fetch all payments for a group."""
        self._require_membership(group_id, user_id)
        payments = payment_repo.get_by_group(group_id)
        return [self._format_payment(p) for p in payments]

    def reverse_payment(self, group_id: str, payment_id: str, user_id: str) -> dict:
        """Reverse a payment event (Admin only), posting a reversing debit entry."""
        if not member_repo.is_admin(group_id, user_id):
            raise AppError(403, "Only group administrators can reverse payments")

        payment = payment_repo.get_by_id(payment_id)
        if not payment or payment.get("GROUP_ID") != group_id:
            raise AppError(404, "Payment not found")

        if payment.get("STATUS") == "REVERSED":
            raise AppError(400, "Payment has already been reversed")

        payment_repo.update_status(payment_id, "REVERSED")

        # Post reversing DEBIT to ledger
        ledger_service.record_entry(
            group_id=group_id,
            member_id=payment.get("MEMBER_ID"),
            entity_type="PAYMENT_REVERSAL",
            entity_id=payment_id,
            entry_type="DEBIT",
            amount_minor=int(payment.get("AMOUNT_MINOR", 0) or 0),
            currency=payment.get("CURRENCY", "INR"),
        )

        audit_service.log(
            event_type="PAYMENT_REVERSED",
            group_id=group_id,
            actor_id=user_id,
            entity_type="PAYMENT",
            entity_id=payment_id,
            details={
                "amount_minor": payment.get("AMOUNT_MINOR"),
                "reversed_by": user_id,
            },
        )

        updated_payment = payment_repo.get_by_id(payment_id)
        return self._format_payment(updated_payment or payment)

    @staticmethod
    def _format_payment(p: dict) -> dict:
        """Format raw DB payment event into clean response dictionary."""
        return {
            "payment_id": p.get("PAYMENT_ID"),
            "group_id": p.get("GROUP_ID"),
            "member_id": p.get("MEMBER_ID"),
            "provider": p.get("PROVIDER"),
            "provider_txn_id": p.get("PROVIDER_TXN_ID"),
            "amount_minor": int(p.get("AMOUNT_MINOR", 0) or 0),
            "currency": p.get("CURRENCY", "INR"),
            "status": p.get("STATUS"),
            "source": p.get("SOURCE"),
            "idempotency_key": p.get("IDEMPOTENCY_KEY"),
            "paid_at": str(p.get("PAID_AT", "")),
            "created_at": str(p.get("CREATED_AT", "")),
            "display_name": p.get("DISPLAY_NAME"),
            "email": p.get("EMAIL"),
        }


payment_service = PaymentService()
