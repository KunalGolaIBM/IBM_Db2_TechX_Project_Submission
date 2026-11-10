from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["donor", "ngo", "volunteer", "admin"]


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class FoodCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category: str = Field(min_length=2, max_length=60)
    quantity_kg: float = Field(gt=0, le=5000)
    prepared_at: datetime
    use_by: datetime
    storage_type: Literal["cold", "hot", "frozen", "ambient"]
    storage_temp_c: float | None = Field(default=None, ge=-50, le=100)
    allergens: list[str] = Field(default_factory=list, max_length=40)
    allergens_confirmed: bool = False
    ingredients: list[str] = Field(default_factory=list, max_length=100)
    pickup_address: str = Field(min_length=5, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    storage_note: str = Field(min_length=4, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("prepared_at", "use_by")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @model_validator(mode="after")
    def use_by_after_prep(self):
        if self.use_by <= self.prepared_at:
            raise ValueError("use_by must be later than prepared_at")
        if self.prepared_at > datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError("prepared_at cannot be in the future")
        return self


class VerifyInput(BaseModel):
    decision: Literal["verified", "hold", "rejected"]
    notes: str = Field(min_length=8, max_length=1000)


class EvidenceUpdate(BaseModel):
    storage_temp_c: float | None = Field(default=None, ge=-50, le=100)
    storage_note: str = Field(min_length=4, max_length=500)
    allergens: list[str] = Field(default_factory=list, max_length=40)
    allergens_confirmed: bool


class RescueFailure(BaseModel):
    reason: str = Field(min_length=8, max_length=500)


class NgoCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    available_kg: float = Field(ge=0, le=100000)
    accepted_categories: list[str] = Field(min_length=1, max_length=30)
    storage_capabilities: list[str] = Field(default_factory=list, max_length=20)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    receiving_hours: str = Field(min_length=3, max_length=160)


class CapacityUpdate(BaseModel):
    available_kg: float = Field(ge=0, le=100000)
    active: bool = True


class VerifyStage(BaseModel):
    stage: Literal["pickup", "delivery", "distribution"]
    otp: str = Field(pattern=r"^\d{6}$")
    actual_distributed_kg: float | None = Field(default=None, gt=0, le=5000)

    @model_validator(mode="after")
    def distribution_quantity_matches_stage(self):
        if self.stage == "distribution" and self.actual_distributed_kg is None:
            raise ValueError("actual_distributed_kg is required for distribution confirmation")
        if self.stage != "distribution" and self.actual_distributed_kg is not None:
            raise ValueError("actual_distributed_kg is only accepted for distribution confirmation")
        return self


class PolicyQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    batch_id: str | None = None
