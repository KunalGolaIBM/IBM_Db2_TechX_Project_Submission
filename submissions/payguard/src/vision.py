"""Screenshot understanding: Gemini vision turns a chat / listing / e-mail screenshot into a screenable payment."""
from __future__ import annotations

import base64

import llm

MAX_BYTES = 8 * 1024 * 1024
ALLOWED = {"image/png", "image/jpeg", "image/webp", "image/heic", "image/heif"}

PROMPT = """You are reading a screenshot a buyer took before paying someone (WhatsApp, Instagram, Facebook,
marketplace chat, SMS, e-mail or a web page). Extract exactly what is visible - never invent values.
- transcript: the visible messages in order, one per line, prefixed "Seller:" or "Buyer:" (or "Sender:" for e-mail/SMS).
  Keep the original wording, including Pidgin.
- seller_name: display name, page or shop name of the other party.
- contacts: every phone number, e-mail, website/link, bank account number (10 digits), bank name and crypto wallet shown.
- amount/currency: the price or amount the buyer is asked to pay (0 if none). Use NGN for naira (N, ₦), USD for $.
- payment_method: friends_family if they ask for PayPal Friends & Family / personal payment; gift_card; crypto;
  wire for bank transfer / OPay / Moniepoint / PalmPay transfer; otherwise goods_services.
- platform: where this conversation is happening.
- is_payment_related: true if someone is asking for money, a fee, a code/OTP or login details."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "platform": {"type": "STRING"},
        "seller_name": {"type": "STRING"},
        "transcript": {"type": "STRING"},
        "phones": {"type": "ARRAY", "items": {"type": "STRING"}},
        "emails": {"type": "ARRAY", "items": {"type": "STRING"}},
        "links": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bank_accounts": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bank_names": {"type": "ARRAY", "items": {"type": "STRING"}},
        "wallets": {"type": "ARRAY", "items": {"type": "STRING"}},
        "amount": {"type": "NUMBER"},
        "currency": {"type": "STRING"},
        "payment_method": {"type": "STRING",
                           "enum": ["goods_services", "friends_family", "gift_card", "crypto", "wire"]},
        "is_payment_related": {"type": "BOOLEAN"},
    },
    "required": ["transcript", "seller_name", "amount", "currency", "payment_method", "is_payment_related"],
}


class ImageError(ValueError):
    pass


def read_screenshot(data: bytes, mime: str) -> dict:
    if not data:
        raise ImageError("The image is empty.")
    if len(data) > MAX_BYTES:
        raise ImageError("Image is larger than 8 MB.")
    mime = (mime or "").lower()
    if mime not in ALLOWED:
        raise ImageError("Please upload a PNG, JPG or WEBP screenshot.")
    body = {
        "contents": [{"role": "user", "parts": [
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}},
            {"text": PROMPT},
        ]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    resp = llm._post(body)
    import json

    out = json.loads(llm._text(resp) or "{}")
    for k in ("phones", "emails", "links", "bank_accounts", "bank_names", "wallets"):
        out[k] = [str(v).strip() for v in out.get(k) or [] if str(v).strip()][:10]
    out["amount"] = max(0.0, float(out.get("amount") or 0))
    out["currency"] = (out.get("currency") or "USD").upper()[:3]
    return out


def to_message(ex: dict) -> str:
    """Flatten the extraction into text the risk engine (rules, entities, vectors) can screen."""
    lines = [ex.get("transcript", "")]
    extras = ex["phones"] + ex["emails"] + ex["links"] + ex["bank_accounts"] + ex["wallets"]
    if ex.get("bank_names"):
        extras.append("Bank: " + ", ".join(ex["bank_names"]))
    if extras:
        lines.append("Contacts shown: " + " ".join(extras))
    return "\n".join(x for x in lines if x).strip()
