from datetime import datetime, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .security import normalize_email, validate_password

Role = Literal["donor", "ngo", "volunteer", "admin"]


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


class DemoLoginInput(BaseModel):
    role: Literal["admin", "donor", "ngo", "volunteer"]
    password: str = Field(min_length=6, max_length=128)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email", mode="before")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordResetToken(BaseModel):
    token: str = Field(min_length=6, max_length=6)

    @field_validator("token")
    @classmethod
    def validate_reset_credential(cls, value: str) -> str:
        if re.fullmatch(r"[0-9]{6}", value):
            return value
        raise ValueError("Enter a valid six-digit, locally approved recovery code.")


class PasswordResetConfirm(PasswordResetToken):
    password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(min_length=6, max_length=128)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")
        return self


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


class NgoVerification(BaseModel):
    verified: bool
    notes: str = Field(min_length=8, max_length=500)


class SignupInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    confirm_password: str = Field(min_length=6, max_length=128)
    role: Literal["donor", "ngo", "volunteer"]
    ngo_profile: NgoCreate | None = None
    service_area: str | None = Field(default=None, min_length=2, max_length=160)

    @field_validator("email", mode="before")
    @classmethod
    def canonical_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Name must contain at least two non-space characters.")
        return normalized

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)

    @model_validator(mode="after")
    def validate_signup_fields(self):
        if self.password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")
        if self.role == "ngo" and self.ngo_profile is None:
            raise ValueError("Complete NGO receiving details are required for NGO signup.")
        if self.role != "ngo" and self.ngo_profile is not None:
            raise ValueError("NGO profile details are only valid for NGO signup.")
        if self.role == "volunteer" and not (self.service_area or "").strip():
            raise ValueError("Service area is required for volunteer signup.")
        if self.role != "volunteer" and self.service_area is not None:
            raise ValueError("Service area is only valid for volunteer signup.")
        return self


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
