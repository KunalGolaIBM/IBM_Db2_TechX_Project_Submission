"""Authoritative checkout authorization always re-reads the persisted screening."""
from domain.ports import Repository, PaymentProvider
from adapters.paypal import PayPalError


class CheckoutRejected(ValueError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


class Checkout:
    def __init__(self, repo: Repository, paypal: PaymentProvider):
        self.repo, self.paypal = repo, paypal

    def create_order(self, screening_id: int, acknowledge_risk: bool = False):
        if not self.paypal.enabled:
            raise CheckoutRejected(503, "PayPal sandbox keys are not configured.")
        sc = self.repo.get_screening(screening_id)
        if not sc:
            raise CheckoutRejected(404, "Screening not found")
        if sc["verdict"] == "BLOCK":
            raise CheckoutRejected(403, "PayGuard blocked this payment.")
        if sc["verdict"] == "REVIEW" and not acknowledge_risk:
            raise CheckoutRejected(409, "This payment needs review. Confirm you understand the risks to continue.")
        if sc["paypal_order_id"] and sc["paypal_status"] in ("COMPLETED",):
            raise CheckoutRejected(409, "This screening was already paid.")
        if float(sc["amount"]) <= 0:
            raise CheckoutRejected(422, "Amount must be greater than zero.")
        desc = f'{sc["merchant"] or "Purchase"} (PayGuard {sc["verdict"]}, risk {sc["risk_score"]})'
        try:
            order = self.paypal.create_order(amount=float(sc["amount"]), currency=sc["currency"], description=desc,
                                          screening_id=sc["id"], risk_score=sc["risk_score"], verdict=sc["verdict"])
        except PayPalError as exc:
            raise CheckoutRejected(exc.status if exc.status < 500 else 502, str(exc))
        self.repo.update_screening_paypal(sc["id"], order["id"], order.get("status", "CREATED"))
        return {"id": order["id"], "status": order.get("status")}

    def capture_order(self, order_id: str, screening_id: int):
        sc = self.repo.get_screening(screening_id)
        if not sc or sc["paypal_order_id"] != order_id:
            raise CheckoutRejected(404, "Order does not belong to this screening.")
        if sc["verdict"] == "BLOCK":
            raise CheckoutRejected(403, "PayGuard blocked this payment.")
        try:
            result = self.paypal.capture_order(order_id)
        except PayPalError as exc:
            raise CheckoutRejected(exc.status if exc.status < 500 else 502, str(exc))
        status = result.get("status", "UNKNOWN")
        self.repo.update_screening_paypal(sc["id"], order_id, status)
        capture = (((result.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or [{}])[0]
        return {"id": order_id, "status": status, "capture_id": capture.get("id"),
                "payer": (result.get("payer") or {}).get("email_address")}
