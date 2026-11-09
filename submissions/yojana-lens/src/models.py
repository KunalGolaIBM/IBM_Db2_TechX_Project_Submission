"""Domain models and fact normalisation.

Everything that comes out of an LLM passes through here before it can reach
SQL. Unknown keys and unparsable values are dropped rather than trusted.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# Canonical fact vocabulary. Kept in sync with data/schemes.json meta.
NUMERIC_FACTS = {
    "age",
    "income_annual",
    "land_holding_acres",
    "girl_age",
    "disability_percent",
}

TEXT_FACTS = {
    "gender",
    "state_code",
    "marital_status",
    "bpl_status",
    "residence",
    "house_type",
    "category",
    "occupation",
    "business_type",
    "education_level",
    "has_girl_child",
    "has_bank_account",
    "income_tax_payer",
}

ALL_FACTS = NUMERIC_FACTS | TEXT_FACTS

# Canonical spellings for closed vocabularies.
CANONICAL: Dict[str, Dict[str, str]] = {
    "gender": {"woman": "female", "women": "female", "f": "female", "m": "male", "man": "male"},
    "marital_status": {
        "widowed": "widow",
        "widow/widower": "widow",
        "single": "unmarried",
        "unmarried": "unmarried",
        "divorced": "divorced",
    },
    "bpl_status": {"true": "yes", "y": "yes", "1": "yes", "false": "no", "n": "no", "0": "no"},
    "has_girl_child": {"true": "yes", "y": "yes", "1": "yes", "false": "no", "n": "no", "0": "no"},
    "has_bank_account": {"true": "yes", "y": "yes", "1": "yes", "false": "no", "n": "no", "0": "no"},
    "income_tax_payer": {"true": "yes", "y": "yes", "1": "yes", "false": "no", "n": "no", "0": "no"},
    "residence": {"village": "rural", "rural": "rural", "city": "urban", "town": "urban", "urban": "urban"},
    "house_type": {"mud": "kutcha", "kaccha": "kutcha", "pucca": "pucca", "pakka": "pucca", "semi-pucca": "semi-pucca"},
    "education_level": {
        "10": "10th",
        "12": "12th",
        "class10": "10th",
        "class12": "12th",
        "matric": "10th",
        "intermediate": "12th",
        "degree": "graduate",
        "graduation": "graduate",
        "post_graduate": "postgraduate",
    },
    "occupation": {
        "farming": "farmer",
        "agriculture": "farmer",
        "kisan": "farmer",
        "craftsperson": "artisan",
        "craftsman": "artisan",
        "vendor": "street_vendor",
        "hawker": "street_vendor",
        "jobless": "unemployed",
    },
}


class RuleRow(BaseModel):
    """One rule evaluated against one applicant fact."""

    scheme_id: str
    rule_id: int
    criterion_code: str
    rule_op: str
    mandatory: int = 1
    observed_value: Optional[str] = None
    verdict: str  # PASS | FAIL | UNKNOWN
    clause_ref: str
    chunk_id: Optional[str] = None
    narrative: Optional[str] = None
    chunk_text: Optional[str] = None
    value_num: Optional[float] = None
    value_text: Optional[str] = None

    @property
    def blocking(self) -> bool:
        return bool(self.mandatory) and self.verdict == "FAIL"

    @property
    def needs_info(self) -> bool:
        return bool(self.mandatory) and self.verdict == "UNKNOWN"

    def limit_text(self) -> str:
        """The bare value a criterion is compared against."""
        if self.rule_op in ("lte", "gte"):
            return _pretty_num(self.value_num)
        if self.rule_op == "in":
            return "one of: " + (self.value_text or "").replace(",", ", ")
        return str(self.value_text or "")

    def threshold_label(self) -> str:
        if self.rule_op == "lte":
            return f"max {self.limit_text()}"
        if self.rule_op == "gte":
            return f"min {self.limit_text()}"
        return self.limit_text()


class SchemeResult(BaseModel):
    scheme_id: str
    name: str
    category: str
    gov_level: str
    state_code: str
    benefit_summary: Optional[str] = None
    source_url: Optional[str] = None
    label: str
    readiness: int
    rules: List[RuleRow] = Field(default_factory=list)
    blocking: List[RuleRow] = Field(default_factory=list)
    advisory: List[RuleRow] = Field(default_factory=list)
    missing: List[RuleRow] = Field(default_factory=list)
    narrative: Optional[str] = None
    citations: List[str] = Field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.rules if r.verdict == "PASS")


class NormalizedProfile(BaseModel):
    facts: Dict[str, Any] = Field(default_factory=dict)
    retrieval_query: str = ""
    unknowns: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    @field_validator("facts", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Dict[str, Any]:
        return coerce_facts(value)


def coerce_facts(raw: Any) -> Dict[str, Any]:
    """Keep only canonical keys, coerce types, drop junk."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, dict):
        return {}

    facts: Dict[str, Any] = {}
    for key, value in raw.items():
        key = str(key).strip().lower().replace(" ", "_")
        if key not in ALL_FACTS or value is None:
            continue
        if key in NUMERIC_FACTS:
            number = _to_float(value)
            if number is not None:
                facts[key] = number
            continue
        text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if not text:
            continue
        if key == "state_code":
            facts[key] = text.upper()
            continue
        facts[key] = CANONICAL.get(key, {}).get(text, text)
    return facts


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _pretty_num(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if value >= 100000:
        return f"{value / 100000:g} lakh"
    return f"{value:g}"


class AskRequest(BaseModel):
    text: str = Field(min_length=10, max_length=8000)
    category: Optional[str] = None
