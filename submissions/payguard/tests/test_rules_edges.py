"""Every current rule family has a positive and negative example, including Pidgin."""
import math

import pytest

from signals import RULES, extract_amount, extract_entities, run_rules
from risk import RiskEngine, ScreenRequest

CASES = [
    ("FRIENDS_FAMILY", "Abeg send as friends and family make fees no chop am", "Use Goods and Services"),
    ("OFF_PLATFORM", "Make we chat on WhatsApp instead", "Keep this chat inside the app"),
    ("GIFT_CARD", "Buy steam card and send code give me", "Your paper receipt is ready"),
    ("CRYPTO_PAY", "Send USDT to my wallet abeg", "Pay at the shop after inspection"),
    ("URGENCY", "Pay now before another buyer carry am", "Take your time and inspect am"),
    ("CREDENTIALS", "Abeg read the OTP wey dem send you", "Never share your OTP with anyone."),
    ("ADVANCE_FEE", "Pay registration fee before we give you the job", "No payment required to apply"),
    ("OVERPAYMENT", "I mistakenly transferred extra, refund the difference", "Your invoice total is correct"),
    ("FAKE_ALERT", "See screenshot of the payment, send the goods", "Confirm cleared funds in your account"),
    ("IMPERSONATION", "Na bank officer dey talk, verify your account", "Call your bank using its official number"),
    ("TOO_GOOD", "We go double your money in one week", "Prices follow the market rate"),
    ("ACCOUNT_SWITCH", "No mind the name, use this other account", "The account name matches our registered shop"),
    ("REMOTE_ACCESS", "Install AnyDesk make I help you", "Visit the service desk in person"),
]


def test_all_rule_families_are_covered():
    assert {case[0] for case in CASES} == {rule.code for rule in RULES}


@pytest.mark.parametrize("code,positive,negative", CASES)
def test_rule_positive(code, positive, negative):
    assert code in {signal.code for signal in run_rules(positive)}


@pytest.mark.parametrize("code,positive,negative", CASES)
def test_rule_negative(code, positive, negative):
    assert code not in {signal.code for signal in run_rules(negative)}


@pytest.mark.parametrize("text", ["", "a" * 4000, "🛒🇳🇬😀💸", "Abeg your clothes don ready. Pickup tomorrow.",
                                  "Hello buyer, abeg send OTP now 🤑"])
def test_message_edges_are_finite_and_screenable(repo, embedder, text):
    result = RiskEngine(repo, embedder).screen(ScreenRequest(message=text), persist=False)
    assert 0 <= result.risk_score <= 100 and math.isfinite(result.risk_score)
    assert result.verdict in {"ALLOW", "REVIEW", "BLOCK"}


@pytest.mark.parametrize("text,accounts,phones", [
    ("0123456789", ["0123456789"], []),
    ("0012345678 and 0012345678", ["0012345678"], []),
    ("123456789 123456789012", [], []),
    ("08012345678", [], ["08012345678"]),
    ("+234 801 234 5678", [], ["08012345678"]),
    ("0801-234-5678", [], ["08012345678"]),
    ("+2348012345678", [], ["08012345678"]),
    ("1080123456789", [], []),
])
def test_nuban_and_phone_boundaries(text, accounts, phones):
    entities = extract_entities(text)
    assert entities.accounts == accounts
    assert entities.phones == phones


@pytest.mark.parametrize("text,amount,currency", [
    ("N350,000", 350000, "NGN"), ("₦5,000.50", 5000.5, "NGN"),
    ("Abeg 50k naira", 50000, "NGN"), ("USD 25", 25, "USD"),
    ("£12.50", 12.5, "GBP"), ("€20", 20, "EUR"), ("$210", 210, "USD"),
    ("no price given", 0, "USD"), ("N0", 0, "NGN"),
    ("N" + "9" * 3999, 0, "USD"),
])
def test_amount_parsing(text, amount, currency):
    assert extract_amount(text) == (amount, currency)
