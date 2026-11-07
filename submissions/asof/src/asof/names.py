"""Person names in free text, found without a model so redaction stays deterministic and offline.

A name is taken where the text itself marks one:
- a title: "Mr. Patel", "Dr Ana Lima"
- a self-introduction or a name field: "my name is Jane Doe", "this is Omar", "passenger: Wei Zhang"
- a greeting or a sign-off: "Hi Jane,", "Dear Mrs. Okafor", "Thanks, Raj", "Regards,\nMaria Garcia"
- a family or other relation: "my grandmother, Eleanor Price, passed away", "my son Liam"
- a common given name, with the capitalised words after it: "Can Priya Sharma use my credit?"

The given-name list is short and not exhaustive, and cue words only catch names written with capitals.
Words that are policy or product terms in this project (fare classes, brands, months, days) are never
taken as names. This lowers what reaches the LLM provider and the ledger; it does not guarantee that no
name gets through.
"""

from __future__ import annotations

import re

# One capitalised name word: Jane, O'Neil, McDonald, Jean-Luc, Zoë.
_W = r"[A-Z][a-zÀ-ɏ]+(?:['’-][A-Z]?[a-zÀ-ɏ]+)*"
_NAME = rf"{_W}(?:\s+{_W}){{0,2}}"

# Capitalised words that are not names here: policy and product terms, brands, calendar words, pronouns.
NOT_NAMES = frozenset("""
Aurelia Air Fernhollow Bank Economy Premium Business Basic Standard First Class Everyday Checking Savings
Contact Centre Center Visa Mastercard Amex Interac Customer Customers Team Support Agent Service Sir Madam
Friend Friends There All Everyone Folks Valued Traveller Traveler Passenger Member Members Guest Guests
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August
September October November December Today Tomorrow Yesterday Morning Afternoon Evening Night
I The A An We You Your Our My It This That These Those Yes No Not Please Thanks Thank Hi Hello Dear Hey
Regards Best Cheers Sincerely Kind Warm Many Lisbon London Paris Tokyo Canada Toronto Montreal Vancouver
""".split())

GIVEN_NAMES = frozenset("""
Aaron Abdul Adam Adrian Ahmed Aisha Alan Alex Alexander Alexandra Ali Alice Amanda Amelia Amir Amy Ana Andrea
Andrew Angela Anil Anita Anna Anne Anthony Anton Arjun Ava Ben Benjamin Beth Bilal Brian Bruno Carlos Carmen
Caroline Catherine Charles Charlotte Chen Chloe Chris Christian Christopher Claire Daniel David Deepak Diana
Diego Dmitri Elena Elif Eliza Elizabeth Ella Emily Emma Eric Ethan Eva Fatima Felix Fernando Fiona Francesca
Francisco Gabriel George Grace Hannah Hao Harry Hassan Helen Henry Hiroshi Hugo Ian Igor Imran Isabel Isabella
Ivan Jack Jacob Jake James Jane Jasmine Javier Jean Jennifer Jessica Jin Joan John Jonathan Jorge Jose Joseph
Joshua Juan Julia Julian Karen Karim Kate Katherine Kenji Kevin Khalid Kim Laura Lauren Layla Lea Leah Leo Liam
Lin Linda Lisa Lucas Lucia Luis Luka Mai Manuel Marco Maria Mariam Mark Marta Martin Mary Mateo Matthew Max Maya
Mehmet Mei Melissa Mia Michael Michelle Miguel Mohammed Muhammad Nadia Naomi Natalia Nathan Neha Nicholas Nicole
Nikhil Nina Noah Nora Olga Oliver Olivia Omar Oscar Pablo Paolo Patrick Paul Pedro Peter Pierre Pooja Priya
Rachel Rahul Raj Rajesh Ravi Rebecca Ricardo Richard Robert Rohan Rosa Ryan Sakura Samuel Sandra Sara Sarah Scott
Sean Sergei Simon Sofia Sophia Sophie Stephen Steven Sunita Susan Tanvir Tara Thomas Tim Timothy Tom Tomas Valentina
Vanessa Victor Victoria Vikram Wei William Xin Yan Yasmin Yuki Yusuf Zainab Zara Zoe
""".split())

_RELATIONS = (r"mother|father|mom|mum|dad|wife|husband|partner|spouse|son|daughter|child|kid|brother|sister|sibling"
              r"|grandmother|grandfather|grandma|grandpa|granddaughter|grandson|aunt|uncle|cousin|niece|nephew"
              r"|stepmother|stepfather|stepson|stepdaughter|mother-in-law|father-in-law|sister-in-law"
              r"|brother-in-law|fianc[ée]e?|friend|colleague|boss|manager|guardian")

# Each pattern's group "n" is the name; everything else around it is kept.
_CUES = [
    re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof)\.?\s+(?P<n>{_NAME})"),
    re.compile(rf"\b(?i:my name is|my name's|name is|name:|this is|signed,?)\s+(?P<n>{_NAME})"),
    re.compile(rf"\b(?i:passenger|traveller|traveler|account holder|cardholder|card holder|customer)"
               rf"(?:'s name is|:| named| called| name:)\s+(?P<n>{_NAME})"),
    re.compile(rf"\b(?i:on behalf of)\s+(?P<n>{_NAME})"),
    re.compile(rf"(?:^|[.!?]\s+|\n)(?i:hi|hello|hey|dear|good (?:morning|afternoon|evening)|thanks|thank you)"
               rf",?\s+(?:(?:Mr|Mrs|Ms|Miss|Mx|Dr)\.?\s+)?(?P<n>{_NAME})(?=\s*[,.!?:;\n]|$)"),
    re.compile(rf"(?i:regards|best wishes|best|cheers|sincerely|thanks|thank you|kind regards|warm regards)"
               rf",?\s*\n\s*(?P<n>{_NAME})\s*$"),
    re.compile(rf"\b(?i:my|your|our|her|his|their)\s+(?i:{_RELATIONS})(?:'s name is|,| named| called)?\s+(?P<n>{_NAME})"),
]
# Given names that are also everyday words ("grace period", "max 8 kg") count only with a surname after them.
AMBIGUOUS = frozenset({"Grace", "Mark", "Max", "Jack", "Rosa", "Kim", "Mai", "Lea", "Will", "Victor"})
_WORD = re.compile(rf"\b{_W}")
_NAME_AT = re.compile(_NAME)


def _clean(name: str) -> str | None:
    """Drop trailing words that are not names ('Jane Monday' -> 'Jane'); None if nothing is left."""
    words = name.split()
    while words and words[-1] in NOT_NAMES:
        words.pop()
    if not words or words[0] in NOT_NAMES:
        return None
    return " ".join(words)


def find_names(text: str) -> list[tuple[int, int]]:
    """Character spans of person names in `text`, merged and in order."""
    spans: list[tuple[int, int]] = []
    for pattern in _CUES:
        for m in pattern.finditer(text):
            name = _clean(m.group("n"))
            if name:
                start = m.start("n")
                spans.append((start, start + len(name)))
    for w in _WORD.finditer(text):  # every capitalised word, so "Can Priya Sharma" finds Priya
        if w.group(0) in GIVEN_NAMES:
            name = _clean(_NAME_AT.match(text, w.start()).group(0))
            if name and (w.group(0) not in AMBIGUOUS or " " in name):
                spans.append((w.start(), w.start() + len(name)))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(e, merged[-1][1]))
        else:
            merged.append((s, e))
    return merged
