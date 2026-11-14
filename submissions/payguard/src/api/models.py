"""Public request schemas (v1 and legacy aliases)."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator

Method = Literal["goods_services", "friends_family", "gift_card", "crypto", "wire"]


class ScreenIn(BaseModel):
    merchant: str = Field("", max_length=200)
    payee_email: str = Field("", max_length=320)
    amount: float = Field(0, ge=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    payment_method: Method = "goods_services"
    message: str = Field("", max_length=4000)
    region: str = Field("NG", max_length=20)
    language: Literal["en", "pcm"] = "en"
    explain: bool = True
    seller_account_age_days: int | None = Field(None, ge=0, le=100_000)
    market_price: float | None = Field(None, ge=0)
    source: Literal["paste", "screenshot", "share", "platform", "agent"] = "paste"

    @field_validator("currency")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()


class PurchaseIn(BaseModel):
    instruction: str = Field(..., min_length=5, max_length=3000)
    language: Literal["en", "pcm"] = "en"


class ReportIn(BaseModel):
    entity_type: Literal["email", "phone", "domain", "wallet", "account"]
    value: str = Field(..., min_length=3, max_length=320)
    category: str = Field("other", max_length=40)
    amount: float = Field(0, ge=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    narrative: str = Field(..., min_length=10, max_length=2000)
    reporter: str = Field("anonymous", max_length=100)


class QuestionIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class OrderIn(BaseModel):
    screening_id: int
    acknowledge_risk: bool = False


class CaptureIn(BaseModel):
    screening_id: int



class ChatLine(BaseModel):
    sender: Literal["buyer", "seller"]
    text: str = Field(..., max_length=2000)


class PlatformCheckIn(BaseModel):
    platform: str = Field(..., max_length=60)
    seller_name: str = Field("", max_length=200)
    seller_email: str = Field("", max_length=320)
    seller_phone: str = Field("", max_length=40)
    seller_account_number: str = Field("", max_length=20)
    seller_account_age_days: int | None = Field(None, ge=0)
    listing_title: str = Field("", max_length=200)
    amount: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    market_price: float | None = Field(None, ge=0)
    payment_method: Method = "goods_services"
    chat: list[ChatLine] = Field(default_factory=list, max_length=60)
    language: Literal["en", "pcm"] = "en"


class DemoCheckIn(BaseModel):
    listing_id: Literal["ps5", "books"]


