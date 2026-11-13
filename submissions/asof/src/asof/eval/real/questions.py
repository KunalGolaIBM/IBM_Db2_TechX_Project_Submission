"""The demonstration's questions: each asked on a date before and a date after the 2024 refund rule.

Written after reading the regulation, so this is a demonstration, not a blind evaluation. The date is when the
refund question arises (the cancellation, or the refund request), which is the date AsOf checks against. `reading`
is what the loaded excerpt says on that date, in plain words; it is not legal advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

BEFORE, AFTER, BETWEEN = date(2023, 3, 15), date(2025, 2, 10), date(2024, 7, 15)


@dataclass(frozen=True)
class Question:
    id: str
    as_of: date
    question: str
    draft: str
    reading: str


_AUTO = ("The airline cancelled my flight and I turned down the rebooking it offered. Do I get my money back "
         "automatically, without asking?",
         "Yes. Because the airline cancelled your flight and you rejected the alternative it offered, a full refund of "
         "the airfare is due to you automatically.")
_CASH = ("I paid cash for my ticket and sent the airline a complete refund request. How long does it have to refund me?",
         "The airline must refund you within 20 days after it receives your complete refund request.")
_FEE = ("Can the airline keep a processing fee out of the refund it owes me?",
        "Yes. The airline may keep a small processing fee from the refund.")
_VOUCHER = ("Instead of a refund for my cancelled flight, the airline offered me a travel voucher. How long must the "
            "voucher stay valid?",
            "A voucher offered instead of the refund must stay valid for at least five years from the date it is issued.")
_MILES = ("I paid by credit card. Can the airline give me my refund in airline miles instead?",
          "Not unless you agree. The refund must go back in your original form of payment, unless you accept a "
          "different form that is a cash equivalent.")

QUESTIONS = (
    Question("D1a", BEFORE, *_AUTO, "Not stated: 259.5(b)(5) only says refunds that are due must be prompt; it does not "
             "say when a refund is due."),
    Question("D1b", AFTER, *_AUTO, "260.6(a)(2)(ii): a full refund is due when the consumer rejects the significantly "
             "changed flight or the rebooking."),
    Question("D2a", BEFORE, *_CASH, "259.5(b)(5): within 20 days after receiving a complete refund request, for cash "
             "and check purchases."),
    Question("D2b", AFTER, *_CASH, "Not stated in the excerpt: 259.5(b)(5) as amended says prompt refunds in the original "
             "form of payment; the day counts are in 260.2's definitions, which were not loaded."),
    Question("D3a", BEFORE, *_FEE, "Not stated: 259.5(b)(5) says nothing about processing fees."),
    Question("D3b", AFTER, *_FEE, "259.5(b)(5) as amended: carriers may not retain a processing fee for issuing refunds "
             "that are due."),
    Question("D4a", BEFORE, *_VOUCHER, "Not stated: there is no voucher rule before part 260."),
    Question("D4b", AFTER, *_VOUCHER, "260.6(c)(2): valid and redeemable for at least five years from issuance."),
    Question("D5a", BEFORE, *_MILES, "Not stated: 259.5(b)(5) before the rule says nothing about the form of payment."),
    Question("D5b", BETWEEN, *_MILES, "259.5(b)(5) as amended on 2024-06-25: the original form of payment, unless the "
             "consumer agrees to a cash-equivalent payment."),
)
