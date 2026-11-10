"""Turns engine evidence into short, plain-language copy a buyer can act on (English + Nigerian Pidgin)."""
from __future__ import annotations

HEADLINES = {
    "en": {"BLOCK": "Don't pay this seller", "REVIEW": "Be careful before you pay", "ALLOW": "No scam signs found"},
    "pcm": {"BLOCK": "No pay dis person", "REVIEW": "Shine your eye before you pay", "ALLOW": "We no see scam sign"},
}

SUBLINES = {
    "en": {"BLOCK": "PayGuard found strong signs of a scam. Keep your money.",
           "REVIEW": "Some things here don't look right. Read these before you pay.",
           "ALLOW": "Nothing suspicious found. Still confirm the item and delivery before paying."},
    "pcm": {"BLOCK": "PayGuard see strong scam sign for here. Hold your money.",
            "REVIEW": "Some things no too clear. Read dis one before you pay.",
            "ALLOW": "We no see any wahala. But still confirm the item and delivery before you pay."},
}

# category -> (English, Pidgin). One line per category keeps the buyer view short.
PLAIN = {
    "known_scammer": ("This contact has been reported for scams.", "People don report dis contact for scam."),
    "payment_method": ("They want a payment type with no buyer protection, so you can't get your money back.",
                       "Dem want make you pay the way wey you no fit collect your money back."),
    "off_platform": ("They want to move you off the app or skip safe payment.",
                     "Dem wan carry you comot from the app make dem fit chop your money."),
    "gift_card": ("Real sellers don't ask for gift cards.", "Real seller no dey collect gift card."),
    "crypto": ("They insist on crypto, which can't be reversed.", "Dem say make you pay with crypto - e no fit reverse."),
    "pressure": ("They are rushing you. Scammers create pressure.", "Dem dey rush you. Na so scammer dey do."),
    "phishing": ("They're asking for codes, PINs or login details. Never share these.",
                 "Dem dey ask for OTP, PIN or password. No ever give anybody."),
    "advance_fee": ("You're asked to pay a fee first to receive something.",
                    "Dem say make you pay fee first before you collect something."),
    "overpayment": ("Classic overpayment / refund trick.", "Na the 'I overpay, refund me' trick."),
    "fake_alert": ("Screenshots or 'pending' messages are not real payment.",
                   "Screenshot or 'pending' message no be real money."),
    "impersonation": ("Someone is pretending to be a bank, PayPal or a known brand.",
                      "Person dey pretend say e be bank, PayPal or big company."),
    "too_good": ("The price is too good to be true.", "The price too cheap - e get as e be."),
    "tech_support": ("They want remote access to your phone or computer.", "Dem want control your phone or computer."),
    "community": ("Other people reported a message just like this.", "Other people don report message wey be like dis."),
    "examples": ("This message matches a hand-reviewed Nigerian scam example.",
                 "Dis message resemble Nigerian scam example wey person don check."),
    "velocity": ("This seller is getting flagged a lot today.", "Dem don flag dis seller well-well today."),
    "account_switch": ("They want the money sent to someone else's account.",
                       "Dem say make you send am to another person account."),
    "new_seller": ("The seller's account is brand new.", "The seller account still new."),
    "amount": ("This is a large payment. Double-check everything.", "Dis money big. Check everything well."),
    "trusted": ("This is a verified seller.", "Dis seller don verify."),
}

ICONS = {"trusted": "check", "known_scammer": "flag", "phishing": "key", "community": "people",
         "payment_method": "shield-off", "pressure": "clock", "too_good": "tag"}


def present(result: dict, language: str = "en") -> dict:
    lang = "pcm" if language == "pcm" else "en"
    idx = 1 if lang == "pcm" else 0
    seen, lines = set(), []
    for r in sorted(result["reasons"], key=lambda r: -abs(r["weight"])):
        cat = r["category"]
        if cat in seen or (r["weight"] < 0 and cat != "trusted"):
            continue
        if result["verdict"] != "ALLOW" and cat == "trusted":
            continue
        seen.add(cat)
        text = PLAIN.get(cat, (r["label"], r["label"]))[idx]
        lines.append({"category": cat, "text": text, "icon": ICONS.get(cat, "alert"),
                      "tone": "good" if r["weight"] < 0 else "bad"})
    ex = result.get("extracted") or {}
    reportable = []
    status = {(e["entity_type"], e["entity_value"]): e["status"] for e in result.get("entities") or []}
    for etype, key in (("account", "accounts"), ("phone", "phones"), ("email", "emails"),
                       ("wallet", "wallets"), ("domain", "domains")):
        for v in ex.get(key) or []:
            if status.get((etype, v)) != "TRUSTED":
                reportable.append({"type": etype, "value": v})
    ai = result.get("ai") or {}
    subline = ai.get("summary") if ai.get("mode") == "gemini" and ai.get("summary") else SUBLINES[lang][result["verdict"]]
    return {"headline": HEADLINES[lang][result["verdict"]], "subline": subline, "reasons": lines[:3],
            "more_reasons": max(0, len(lines) - 3), "reportable": reportable[:5]}
