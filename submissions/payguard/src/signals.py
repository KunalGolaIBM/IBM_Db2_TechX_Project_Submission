"""Deterministic fraud signals: entity extraction, red-flag rules and look-alike domain detection.

These run before any AI call, so PayGuard still gives a sound verdict offline,
and the LLM can never talk its way past a hard signal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})(?:/[^\s]*)?", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?234[\s-]?|0)[789][01]\d[\s-]?\d{3}[\s-]?\d{4}(?!\d)|\+\d{1,3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3,4}")
BTC_RE = re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b")
ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
ACCOUNT_RE = re.compile(r"(?<![\d+])\d{10}(?!\d)")  # Nigerian NUBAN bank account number

FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "ymail.com", "proton.me",
             "protonmail.com", "icloud.com", "aol.com", "mail.com", "gmx.com"}
BRANDS = ["paypal", "amazon", "apple", "microsoft", "google", "netflix", "jumia", "konga", "opay",
          "palmpay", "moniepoint", "gtbank", "zenithbank", "firstbank", "accessbank", "kuda", "binance",
          "coinbase", "dhl", "fedex", "ups", "nipost", "facebook", "instagram", "whatsapp"]
_HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "$": "s"})


@dataclass
class Signal:
    code: str
    label: str
    weight: int
    category: str
    evidence: str = ""

    def as_dict(self) -> dict:
        return {"source": "rule", "code": self.code, "label": self.label, "weight": self.weight,
                "category": self.category, "evidence": self.evidence}


@dataclass
class RuleSpec:
    code: str
    label: str
    weight: int
    category: str
    patterns: list[str] = field(default_factory=list)


RULES: list[RuleSpec] = [
    RuleSpec("FRIENDS_FAMILY", "Seller wants 'Friends & Family' payment (no buyer protection)", 30, "payment_method",
             [r"friends?\s*(?:and|&|n)\s*family", r"\bf\s*&\s*f\b", r"\bf&f\b", r"personal payment",
              r"send (?:it )?as (?:a )?gift", r"don'?t (?:select|choose|use) goods"]),
    RuleSpec("OFF_PLATFORM", "Asks to pay or talk outside the platform", 18, "off_platform",
             [r"pay (?:me )?outside", r"(?:chat|talk|move|continue) (?:on|to) (?:whatsapp|telegram|signal)",
              r"don'?t use (?:the )?(?:app|platform|escrow)", r"direct (?:bank )?transfer only",
              r"cancel (?:the )?order and pay", r"no pay on delivery", r"no (?:pay on delivery|pod)\b"]),
    RuleSpec("GIFT_CARD", "Payment in gift cards / vouchers", 32, "gift_card",
             [r"gift ?cards?", r"itunes card", r"steam card", r"google play card", r"amazon card",
              r"scratch (?:the )?card", r"voucher code"]),
    RuleSpec("CRYPTO_PAY", "Insists on crypto payment", 22, "crypto",
             [r"\b(?:usdt|btc|bitcoin|eth|ethereum|crypto|binance pay|trc-?20)\b"]),
    RuleSpec("URGENCY", "Pressure / urgency language", 12, "pressure",
             [r"\burgent(?:ly)?\b", r"right now", r"within (?:\d+|one|two|24) (?:mins?|minutes|hours?)",
              r"last chance", r"before (?:it|the offer) expires", r"act (?:now|fast)", r"immediately",
              r"\basap\b", r"only (?:one|1|two|2) left", r"many people (?:are |dey )?(?:waiting|interested|ask)",
              r"before (?:another|other) (?:person|people|buyer)", r"pay now"]),
    RuleSpec("CREDENTIALS", "Asks for OTP, PIN, password, BVN or card details", 40, "phishing",
             [r"\botp\b", r"\bpin\b", r"\bbvn\b", r"\bnin\b", r"password", r"card (?:number|details)",
              r"\bcvv\b", r"verification code", r"login details", r"recovery phrase", r"seed phrase"]),
    RuleSpec("ADVANCE_FEE", "Upfront fee to release money, prize, job or delivery", 28, "advance_fee",
             [r"(?:clearance|processing|registration|release|activation|customs|delivery|transfer|unlock)"
              r" (?:fee|charge)", r"pay .{0,20}to (?:receive|release|claim|unlock)",
              r"you (?:have )?won", r"inheritance", r"lottery", r"grant approved", r"\bagent fee\b"]),
    RuleSpec("OVERPAYMENT", "Overpayment / refund-the-difference trick", 30, "overpayment",
             [r"over ?paid", r"refund (?:the )?(?:balance|difference|excess)", r"sent (?:you )?(?:extra|more)",
              r"mistakenly (?:sent|transferred)", r"return the extra"]),
    RuleSpec("FAKE_ALERT", "Relies on screenshots / 'payment pending' alerts instead of real funds", 26,
             "fake_alert", [r"screenshot (?:of )?(?:the )?(?:payment|alert|receipt)", r"payment (?:is )?pending",
                            r"funds? (?:on|in) hold", r"check your (?:email|spam) for (?:the )?(?:payment|confirmation)",
                            r"bank alert", r"reversal"]),
    RuleSpec("IMPERSONATION", "Claims to be PayPal / bank / support staff", 26, "impersonation",
             [r"paypal (?:support|team|security|staff)", r"(?:bank|account) (?:officer|manager|team)",
              r"customer care", r"your account (?:has been|will be) (?:limited|suspended|locked|closed)",
              r"verify your account", r"unusual (?:activity|login)"]),
    RuleSpec("TOO_GOOD", "Price or return looks too good to be true", 14, "too_good",
             [r"\b(?:\d{2,3})% (?:off|discount)\b", r"brand new .{0,30}(?:cheap|half price)",
              r"double your (?:money|investment)", r"guaranteed (?:profit|returns?)", r"\broi\b",
              r"(?:daily|weekly) returns?"]),
    RuleSpec("ACCOUNT_SWITCH", "Asks you to pay into a different / third-party account", 22, "account_switch",
             [r"(?:pay|send|transfer) (?:it )?(?:to|into) (?:my )?(?:other|another|second|new|brother'?s|sister'?s|"
              r"wife'?s|cousin'?s|friend'?s|agent'?s|manager'?s) account", r"account name (?:is|will be) (?:different|"
              r"not mine)", r"don'?t mind the (?:account )?name", r"use this (?:other|new) account",
              r"account name na (?:my )?\w+", r"no mind (?:am|the name)"]),
    RuleSpec("REMOTE_ACCESS", "Asks to install remote-access app", 35, "tech_support",
             [r"anydesk", r"teamviewer", r"quick ?support", r"screen ?share"]),
]


@dataclass
class Extracted:
    emails: list[str]
    domains: list[str]
    phones: list[str]
    wallets: list[str]
    accounts: list[str] = field(default_factory=list)

    def as_entities(self) -> list[tuple[str, str]]:
        out = [("email", e) for e in self.emails] + [("domain", d) for d in self.domains]
        out += [("phone", p) for p in self.phones] + [("wallet", w) for w in self.wallets]
        out += [("account", a) for a in self.accounts]
        return out


_AMOUNT = re.compile(r"(?P<cur>usd|ngn|gbp|eur|\$|£|€|₦|\bn(?=\d))\s?(?P<a>\d[\d,]*(?:\.\d+)?)\s?(?P<k>k\b)?|"
                     r"(?P<b>\d[\d,]*(?:\.\d+)?)\s?(?P<k2>k\b)?\s?(?P<cur2>usd|dollars|ngn|naira|gbp|eur)", re.I)
_CUR = {"$": "USD", "usd": "USD", "dollars": "USD", "£": "GBP", "gbp": "GBP", "€": "EUR", "eur": "EUR",
        "₦": "NGN", "ngn": "NGN", "naira": "NGN", "n": "NGN"}


def extract_amount(text: str) -> tuple[float, str]:
    """First money amount in the text: '$210', 'N350,000', '50k naira', 'USD 25'. Returns (0, 'USD') if none."""
    m = _AMOUNT.search(text or "")
    if not m:
        return 0.0, "USD"
    raw = (m.group("a") or m.group("b")).replace(",", "")
    value = float(raw) * (1000 if (m.group("k") or m.group("k2")) else 1)
    return value, _CUR.get((m.group("cur") or m.group("cur2") or "usd").lower(), "USD")


def normalize_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p)
    if digits.startswith("234") and len(digits) == 13:
        return "0" + digits[3:]
    return digits


def extract_entities(*texts: str) -> Extracted:
    blob = " \n".join(t for t in texts if t)
    emails = sorted({e.lower() for e in EMAIL_RE.findall(blob)})
    email_domains = {e.split("@", 1)[1] for e in emails}
    domains = set()
    for m in URL_RE.finditer(blob):
        d = m.group(1).lower()
        # skip the domain part of e-mail addresses and plain numbers like "25.00"
        start = m.start()
        if start > 0 and blob[start - 1] == "@":
            continue
        if re.fullmatch(r"[\d.]+", d):
            continue
        domains.add(d)
    domains |= {d for d in email_domains if d not in FREE_MAIL}
    phones = sorted({normalize_phone(p) for p in PHONE_RE.findall(blob)})
    wallets = sorted(set(BTC_RE.findall(blob)) | {w.lower() for w in ETH_RE.findall(blob)})
    accounts = sorted(set(ACCOUNT_RE.findall(blob)))
    return Extracted(emails, sorted(domains), phones, wallets, accounts)


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lookalike_brand(domain: str) -> str | None:
    """Return the brand a domain imitates (paypa1-secure.com -> paypal), or None if legit/unrelated."""
    host = domain.lower().split(":")[0]
    labels = host.split(".")
    registrable = labels[-2] if len(labels) >= 2 else labels[0]
    if registrable in BRANDS:
        return None  # the real brand domain (or a subdomain of it)
    lure_words = ("secure", "verify", "support", "login", "account", "help", "service", "update",
                  "team", "refund", "billing", "resolution", "center", "centre", "online", "pay", "ng")
    tokens = [t for t in re.split(r"[-.]", ".".join(labels[:-1])) if t]
    for token in tokens:
        plain = token.translate(_HOMOGLYPHS)
        for brand in BRANDS:
            if len(brand) < 4:
                continue
            if plain == brand:  # paypal-secure.com, paypa1.com
                return brand
            if abs(len(plain) - len(brand)) <= 1 and _levenshtein(plain, brand) == 1:  # paypall, paypl
                return brand
            if plain.startswith(brand) and plain[len(brand):] in lure_words:  # paypalsecure.com
                return brand
    return None


def run_rules(text: str) -> list[Signal]:
    low = text.lower()
    out: list[Signal] = []
    for rule in RULES:
        candidate = low
        if rule.code == "CREDENTIALS":
            # A warning not to share credentials is not a request for credentials.
            # Mask a complete warning ending in "with anyone", without exceptions
            # or additional instructions; any actual request still triggers.
            candidate = re.sub(r"(?:^|(?<=[.!?;\n]))\s*(?:never|do not|don't)\s+"
                               r"(?:share|send|give|disclose|reveal|provide)\b[^.!?;\n]*?"
                               r"\b(?:with|to)\s+(?:anyone|anybody)\s*(?=[.!?;\n]|$)", "", low)
        for pat in rule.patterns:
            m = re.search(pat, candidate)
            if m:
                out.append(Signal(rule.code, rule.label, rule.weight, rule.category, m.group(0)))
                break
    return out


def context_signals(*, merchant: str, payee_email: str, amount: float, method: str,
                    extracted: Extracted, seller_account_age_days: int | None = None,
                    market_price: float | None = None) -> list[Signal]:
    out: list[Signal] = []
    if seller_account_age_days is not None and seller_account_age_days < 14:
        out.append(Signal("NEW_SELLER", "Seller account is brand new", 12, "new_seller",
                          f"{seller_account_age_days} days old"))
    if market_price and amount and amount < 0.55 * market_price:
        out.append(Signal("BELOW_MARKET", "Price is far below the normal market price", 18, "too_good",
                          f"{amount:,.0f} vs about {market_price:,.0f}"))
    for d in extracted.domains + [e.split("@", 1)[1] for e in extracted.emails]:
        brand = lookalike_brand(d)
        if brand:
            out.append(Signal("LOOKALIKE_DOMAIN", f"Domain imitates {brand.title()}", 35, "impersonation", d))
            break
    if payee_email:
        dom = payee_email.split("@", 1)[-1].lower()
        mtokens = [t for t in re.findall(r"[a-z0-9]+", merchant.lower()) if len(t) > 3]
        if dom in FREE_MAIL and mtokens and any(t in {"ltd", "limited", "store", "official", "inc", "plc", "bank"}
                                                for t in merchant.lower().split()):
            out.append(Signal("FREE_MAIL_BUSINESS", "Business seller paid through a free personal e-mail", 10,
                              "impersonation", payee_email))
    if method and method.lower() in {"friends_family", "gift_card", "crypto", "wire"}:
        weights = {"friends_family": 30, "gift_card": 32, "crypto": 22, "wire": 12}
        out.append(Signal("METHOD_" + method.upper(), f"Payment method '{method}' removes buyer protection",
                          weights[method.lower()], "payment_method", method))
    if amount >= 1000:
        out.append(Signal("HIGH_AMOUNT", "High-value payment", 8, "amount", f"{amount:,.2f}"))
    return out
