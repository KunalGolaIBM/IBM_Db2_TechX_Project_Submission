"""Screening value objects."""
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ScreenRequest:
    merchant: str = ""
    payee_email: str = ""
    amount: float = 0.0
    currency: str = "USD"
    payment_method: str = "goods_services"
    message: str = ""
    region: str = "NG"
    seller_account_age_days: int | None = None
    market_price: float | None = None

@dataclass
class ScreenResult:
    risk_score: int
    verdict: str
    top_category: str | None
    reasons: list[dict]
    matched_patterns: list[dict]
    similar_reports: list[dict]
    entities: list[dict]
    advice: list[str]
    extracted: dict
    screening_id: int | None = None
    ai: dict[str, Any] = field(default_factory=dict)
    matched_examples: list[dict] = field(default_factory=list)
    degraded: bool = False
    unavailable: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()
