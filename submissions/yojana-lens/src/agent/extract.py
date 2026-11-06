"""Deterministic fact extraction.

Used when no LLM key is configured, and as the fallback whenever the model
is unreachable or returns something that fails validation. Deliberately
conservative: a fact is only recorded when the text supports it. Missing
facts become "unknown", which the UI turns into a follow-up question
instead of a guess.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from ..models import NormalizedProfile

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "half": 0.5,
}

STATES = {
    "uttar pradesh": "UP", "up": "UP",
    "madhya pradesh": "MP", "mp": "MP",
    "bihar": "BR", "rajasthan": "RJ", "maharashtra": "MH", "karnataka": "KA",
    "tamil nadu": "TN", "west bengal": "WB", "delhi": "DL", "gujarat": "GJ",
    "punjab": "PB", "haryana": "HR", "odisha": "OD", "kerala": "KL",
    "telangana": "TS", "andhra pradesh": "AP", "jharkhand": "JH",
    "chhattisgarh": "CG", "assam": "AS", "uttarakhand": "UK",
    "himachal pradesh": "HP", "goa": "GA",
}

CLASS_TO_AGE = {12: 17, 11: 16, 10: 15, 9: 14, 8: 13, 7: 12, 6: 11, 5: 10}

_NUM = r"(\d+(?:\.\d+)?|" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r")"


def _num(token: str) -> float:
    token = token.lower()
    return float(WORD_NUMBERS[token]) if token in WORD_NUMBERS else float(token)


def _money(text: str) -> float | None:
    match = re.search(
        r"(?:income|earning|earn|salary|pension|turnover)[^\d]{0,30}" + _NUM +
        r"\s*(lakh|lac|lacs|crore|cr|thousand|k)?",
        text,
    )
    if not match:
        match = re.search(_NUM + r"\s*(lakh|lac|lacs|crore|cr|thousand|k)\b", text)
    if not match:
        return None
    value = _num(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit in {"lakh", "lac", "lacs"}:
        value *= 100_000
    elif unit in {"crore", "cr"}:
        value *= 10_000_000
    elif unit in {"thousand", "k"}:
        value *= 1_000
    return value


def _land(text: str) -> float | None:
    match = re.search(_NUM + r"\s*(acre|acres|hectare|hectares|bigha|bighas)\b", text)
    if not match:
        return None
    value = _num(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("hectare"):
        value *= 2.471
    elif unit.startswith("bigha"):
        value *= 0.4  # approximate, varies by state
    return round(value, 2)


def heuristic_normalize(text: str) -> NormalizedProfile:
    lower = text.lower()
    facts: Dict[str, Any] = {}
    notes: List[str] = []

    age = re.search(r"(\d{1,3})\s*(?:-|\s)?\s*(?:year|yr)s?\s*(?:old)?", lower)
    if age:
        facts["age"] = float(age.group(1))

    income = _money(lower)
    if income is not None:
        facts["income_annual"] = income

    land = _land(lower)
    if land is not None:
        facts["land_holding_acres"] = land

    if re.search(r"\b(widow|widowed)\b", lower):
        facts["marital_status"] = "widow"
    elif re.search(r"\bdivorced\b", lower):
        facts["marital_status"] = "divorced"
    elif re.search(r"\b(unmarried|single)\b", lower):
        facts["marital_status"] = "unmarried"
    elif re.search(r"\bmarried\b", lower):
        facts["marital_status"] = "married"

    if re.search(r"\b(woman|women|female|lady|mother|widow)\b", lower):
        facts["gender"] = "female"
    elif re.search(r"\b(man|men|male|father)\b", lower):
        facts["gender"] = "male"

    for phrase, code in sorted(STATES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"\b" + re.escape(phrase) + r"\b", lower):
            facts["state_code"] = code
            break

    if re.search(r"\b(village|rural|gram|panchayat)\b", lower):
        facts["residence"] = "rural"
    elif re.search(r"\b(city|urban|town|municipal|nagar)\b", lower):
        facts["residence"] = "urban"

    if re.search(r"\b(kutcha|kaccha|mud house|thatched)\b", lower):
        facts["house_type"] = "kutcha"
    elif re.search(r"\b(pucca|pakka|cement house)\b", lower):
        facts["house_type"] = "pucca"
    elif re.search(r"\bsemi[- ]?pucca\b", lower):
        facts["house_type"] = "semi-pucca"

    if re.search(r"\bscheduled caste\b|\bsc\b", lower):
        facts["category"] = "sc"
    elif re.search(r"\bscheduled tribe\b|\bst\b", lower):
        facts["category"] = "st"
    elif re.search(r"\bobc\b|other backward", lower):
        facts["category"] = "obc"
    elif re.search(r"\bminority\b", lower):
        facts["category"] = "minority"
    elif re.search(r"\bgeneral category\b", lower):
        facts["category"] = "general"

    if re.search(r"\b(farm|farmer|farming|agriculture|kisan|crop)\b", lower):
        facts["occupation"] = "farmer"
    elif re.search(r"\b(artisan|craft|weaver|carpenter|potter|tailor|blacksmith|cobbler)\b", lower):
        facts["occupation"] = "artisan"
    elif re.search(r"\b(vendor|hawker|rehri|street seller)\b", lower):
        facts["occupation"] = "street_vendor"
    elif re.search(r"\b(student|studying|college)\b", lower):
        facts["occupation"] = "student"
    elif re.search(r"\b(unemployed|jobless|no work)\b", lower):
        facts["occupation"] = "unemployed"
    elif re.search(r"\b(salaried|government job|private job)\b", lower):
        facts["occupation"] = "salaried"

    class_match = re.search(r"\bclass\s*(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)\b", lower)
    # "my daughter is in class 12" describes the child, not the applicant.
    applicant_class = class_match
    if class_match:
        prefix = lower[max(0, class_match.start() - 30):class_match.start()]
        if re.search(r"daughter|son|child|children|girl", prefix):
            applicant_class = None

    if applicant_class:
        level = int(applicant_class.group(1) or applicant_class.group(2))
        if level >= 12:
            facts["education_level"] = "12th"
        elif level == 10:
            facts["education_level"] = "10th"
        elif level < 10:
            facts["education_level"] = "below_10th"
    elif re.search(r"\bgraduate|graduation|degree\b", lower):
        facts["education_level"] = "graduate"
    elif re.search(r"\bdropout\b", lower):
        facts["education_level"] = "below_10th"

    if re.search(r"\b(daughter|girl child|girls)\b", lower):
        facts["has_girl_child"] = "yes"
        girl_age = re.search(r"daughter[^\d]{0,20}?(\d{1,2})\s*(?:year|yr)", lower)
        if girl_age and 0 < int(girl_age.group(1)) < 25:
            facts["girl_age"] = float(girl_age.group(1))
        elif class_match:
            facts["girl_age"] = float(CLASS_TO_AGE.get(int(class_match.group(1) or class_match.group(2)), 17))

    if re.search(r"\bbpl\b|below poverty|antyodaya", lower):
        facts["bpl_status"] = "yes"
    elif re.search(r"\bapl\b|above poverty", lower):
        facts["bpl_status"] = "no"

    if re.search(r"\bbank account\b|\bjan dhan\b", lower):
        facts["has_bank_account"] = "yes"

    if re.search(r"\bincome tax\b|\btaxpayer\b|\btax payer\b", lower):
        facts["income_tax_payer"] = "yes"
    elif "income_annual" in facts and facts["income_annual"] <= 500_000:
        facts["income_tax_payer"] = "no"
        notes.append("income_tax_payer was inferred as 'no' from a stated income below Rs 5 lakh")

    query_parts = [
        str(facts.get("occupation", "")),
        str(facts.get("marital_status", "")),
        str(facts.get("residence", "")),
        str(facts.get("category", "")),
        str(facts.get("house_type", "")),
        text,
    ]
    query = " ".join(part for part in query_parts if part.strip()).strip()
    return NormalizedProfile(facts=facts, retrieval_query=query, notes=notes)
