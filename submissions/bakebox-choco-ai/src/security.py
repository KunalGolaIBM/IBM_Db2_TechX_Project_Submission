"""
Security Guardrails, Input Validation, PII Masking, and Rate Limiting for BAKEBOX Choco AI.

Enforces defense-in-depth across Db2, API, and LLM boundaries:
1. Unicode NFKC normalization + zero-width character stripping prior to security checks.
2. Multi-tier bilingual (English & Hinglish) prompt injection, secret-exfiltration,
   SQL DDL/DML, and XSS blocking.
3. Strict identifier validation (session_id, doc_id, 10-digit phone normalization).
4. XML delimiter containment for untrusted customer input and multi-turn history.
5. LLM output scrubbing against credential, connection-string, and script leaks.
6. Database-boundary PII masking and thread-safe 2FA brute-force protection.
"""
import re
import time
import threading
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
DOC_ID_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,64}$")

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|preceding)\s+(instructions?|rules?|guidance)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|rules?|constraints?)", re.IGNORECASE),
    re.compile(r"(purane|pichle|pehle\s+ke)\s+(nirdesh|instructions?|rules?)\s+(bhool|ignore|hata)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer|admin|unrestricted|DAN|jailbreak)\s+mode", re.IGNORECASE),
    re.compile(r"(system\s*prompt\s*override|reveal\s+(your\s+)?system\s*prompt|print\s+(your\s+)?instructions|system\s*prompt\s*(dikhao|batao))", re.IGNORECASE),
    re.compile(r"(reveal|print|dump|show|leak|export)\s+.*(api[_\s]?key|db2[_\s]?password|credentials|connection\s*string|\.env\b)", re.IGNORECASE),
    re.compile(r"(price\s*[:=]\s*0|set\s+(all\s+)?prices?\s+to\s+0|make\s+everything\s+free)", re.IGNORECASE),
    re.compile(r"(drop\s+table|delete\s+from\s+bb_|truncate\s+table|alter\s+table|grant\s+all\s+on)", re.IGNORECASE),
    re.compile(r"(</customer_input>|</conversation_history>)", re.IGNORECASE),
    re.compile(r"(<script>|javascript:|onerror\s*=|onload\s*=|alert\()", re.IGNORECASE),
]

SECRET_LEAK_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"(PWD|PASSWORD|DB2_PASSWORD|GEMINI_API_KEY)\s*=\s*[^;\s]+", re.IGNORECASE), r"\1=********"),
    (re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL), ""),
]


def normalize_untrusted_text(text: str) -> str:
    """Normalize Unicode (NFKC) and strip invisible zero-width evasion characters."""
    normalized = unicodedata.normalize("NFKC", text or "")
    return ZERO_WIDTH_RE.sub("", normalized)


def check_prompt_security(message: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluate input message against compiled prompt-injection, SQL/DDL, and XSS rules
    after Unicode normalization to neutralize homoglyph/zero-width evasion.
    """
    if not isinstance(message, str) or not message.strip():
        return False, "Empty or non-string message"
    if len(message) > 2000:
        return False, "Message exceeds maximum allowed length (2000 chars)"

    cleaned = normalize_untrusted_text(message)
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            return False, f"Malicious pattern detected: {pattern.pattern}"
    return True, None


def sanitize_llm_output(reply: str) -> str:
    """Scrub potential credential strings, connection parameters, or script tags from replies."""
    sanitized = reply or ""
    for pattern, replacement in SECRET_LEAK_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized.strip()


def validate_session_id(session_id: str) -> str:
    """Validate session_id against strict alphanumeric/dash/underscore format."""
    if not isinstance(session_id, str) or not SESSION_ID_RE.match(session_id):
        raise ValueError("Invalid session_id: must be 1-64 chars matching [a-zA-Z0-9_-].")
    return session_id


def validate_doc_id(doc_id: str) -> str:
    """Validate document ID before DB2LlamaVS operations to prevent interpolated SQL injection."""
    if not isinstance(doc_id, str) or not DOC_ID_RE.match(doc_id):
        raise ValueError("Invalid doc_id: must be 1-64 safe identifier characters.")
    return doc_id


def extract_phone_last10(phone: Optional[str]) -> Optional[str]:
    """Extract canonical last 10 numeric digits from phone strings; return None if invalid."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else None


def wrap_untrusted_user_input(message: str) -> str:
    """Isolate untrusted customer text inside explicit XML delimiters."""
    safe_text = normalize_untrusted_text(message).replace("</customer_input>", "")
    return f"<customer_input>\n{safe_text}\n</customer_input>"


def wrap_untrusted_history_turn(role: str, text: str) -> str:
    """Safely format prior conversation turn text without permitting tag breakout."""
    safe_text = normalize_untrusted_text(text)
    safe_text = safe_text.replace("</conversation_history>", "").replace("</customer_input>", "")
    return f"{role}: {safe_text}"


def mask_customer_name(name: str) -> str:
    """Mask customer name, e.g. 'Rahul Sharma' -> 'R**** S*****'."""
    parts = (name or "").strip().split()
    masked = []
    for part in parts:
        masked.append(part[0] + "*" if len(part) <= 2 else part[0] + "*" * (len(part) - 1))
    return " ".join(masked) if masked else "C*******"


def mask_phone_number(phone: str) -> str:
    """Mask phone number showing only last 4 digits, e.g. '+91 ******3210'."""
    last10 = extract_phone_last10(phone)
    if last10:
        return f"+91 ******{last10[-4:]}"
    return "******"


def mask_delivery_address(addr: str) -> str:
    """Mask street-level address while retaining broad city/state context."""
    parts = [p.strip() for p in (addr or "").split(",") if p.strip()]
    if len(parts) >= 2:
        return f"***, {parts[-2]}, {parts[-1]} (Confidential)"
    if parts:
        return f"***, {parts[-1]} (Confidential)"
    return "Mathura, UP (Confidential)"


def mask_order_pii(order: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy of an order record with all customer PII masked at the boundary."""
    masked = dict(order)
    masked["CUSTOMER_NAME"] = mask_customer_name(str(order.get("CUSTOMER_NAME", "Customer")))
    masked["CUSTOMER_PHONE"] = mask_phone_number(str(order.get("CUSTOMER_PHONE", "")))
    masked["DELIVERY_ADDRESS"] = mask_delivery_address(str(order.get("DELIVERY_ADDRESS", "")))
    masked.pop("USER_ID", None)
    masked.pop("PHONE_LAST10", None)
    return masked


def extract_client_ip(request: Any = None) -> str:
    """Extract caller IP safely for rate-limit partitioning (defaults to 'local')."""
    if request is None:
        return "local"
    headers = getattr(request, "headers", None)
    if headers is not None:
        fwd = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if fwd:
            return str(fwd).split(",")[0].strip()[:64] or "local"
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return str(host)[:64] if host else "local"


class OrderAuthRateLimiter:
    """
    Thread-safe sliding-window brute-force protector for 2FA order/refund phone verification.
    Partitions lockouts by `(client_ip, order_id)` so an attacker cannot DoS legitimate buyers.
    """
    def __init__(self, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._failures: Dict[Tuple[str, int], List[float]] = {}

    def is_locked(self, order_id: int, client_ip: str = "local", now: Optional[float] = None) -> bool:
        t = now or time.time()
        bucket = (str(client_ip or "local"), int(order_id))
        with self._lock:
            timestamps = [ts for ts in self._failures.get(bucket, []) if (t - ts) <= self.window_seconds]
            self._failures[bucket] = timestamps
            return len(timestamps) >= self.max_failures

    def record_failure(self, order_id: int, client_ip: str = "local", now: Optional[float] = None) -> int:
        t = now or time.time()
        bucket = (str(client_ip or "local"), int(order_id))
        with self._lock:
            timestamps = [ts for ts in self._failures.get(bucket, []) if (t - ts) <= self.window_seconds]
            timestamps.append(t)
            self._failures[bucket] = timestamps
            return len(timestamps)

    def reset(self, order_id: Optional[int] = None, client_ip: Optional[str] = None) -> None:
        with self._lock:
            if order_id is None and client_ip is None:
                self._failures.clear()
            elif order_id is not None and client_ip is None:
                for key in [k for k in self._failures if k[1] == int(order_id)]:
                    self._failures.pop(key, None)
            elif order_id is None and client_ip is not None:
                for key in [k for k in self._failures if k[0] == str(client_ip)]:
                    self._failures.pop(key, None)
            else:
                self._failures.pop((str(client_ip), int(order_id)), None)


order_auth_limiter = OrderAuthRateLimiter(max_failures=5, window_seconds=300)
