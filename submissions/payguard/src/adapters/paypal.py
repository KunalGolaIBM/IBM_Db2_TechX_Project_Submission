"""PayPal Orders v2 (sandbox) client. Server-side only: the client secret never reaches the browser."""
from __future__ import annotations

import time
import uuid

import httpx

from config import settings


class PayPalError(RuntimeError):
    def __init__(self, message: str, status: int = 502, details: dict | None = None):
        super().__init__(message)
        self.status, self.details = status, details or {}


class PayPalClient:
    def __init__(self, client_id: str | None = None, secret: str | None = None, base_url: str | None = None):
        self.client_id = client_id or settings.paypal_client_id
        self.secret = secret or settings.paypal_client_secret
        self.base = (base_url or settings.paypal_base_url).rstrip("/")
        self._token: str | None = None
        self._token_exp = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.secret)

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = httpx.post(f"{self.base}/v1/oauth2/token", data={"grant_type": "client_credentials"},
                       auth=(self.client_id, self.secret), timeout=30)
        if r.status_code >= 400:
            raise PayPalError("PayPal authentication failed - check PAYPAL_CLIENT_ID / SECRET", r.status_code)
        body = r.json()
        self._token, self._token_exp = body["access_token"], time.time() + int(body.get("expires_in", 300))
        return self._token

    def _call(self, method: str, path: str, json_body: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json",
                   "PayPal-Request-Id": str(uuid.uuid4()), "Prefer": "return=representation"}
        r = httpx.request(method, f"{self.base}{path}", json=json_body, headers=headers, timeout=30)
        if r.status_code >= 400:
            try:
                details = r.json()
            except ValueError:
                details = {"raw": r.text[:300]}
            raise PayPalError(details.get("message") or f"PayPal error {r.status_code}", r.status_code, details)
        return r.json()

    def create_order(self, *, amount: float, currency: str, description: str, screening_id: int,
                     risk_score: int, verdict: str) -> dict:
        """Create an order whose custom_id ties it back to the Db2 screening row."""
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": f"PG-{screening_id}",
                "custom_id": f"payguard:{screening_id}:{verdict}:{risk_score}",
                "description": description[:127] or "PayGuard protected purchase",
                "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
            }],
            "payment_source": {"paypal": {"experience_context": {
                "shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW", "brand_name": "PayGuard Checkout"}}},
        }
        return self._call("POST", "/v2/checkout/orders", body)

    def capture_order(self, order_id: str) -> dict:
        return self._call("POST", f"/v2/checkout/orders/{order_id}/capture", {})

    def get_order(self, order_id: str) -> dict:
        return self._call("GET", f"/v2/checkout/orders/{order_id}")
