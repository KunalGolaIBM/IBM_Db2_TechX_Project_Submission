from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re

def normalize_email(value):
    value=value.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",value):
        raise ValueError("Enter a valid email address.")
    return value

class SafetyChecks(BaseModel):
    handling_verified: bool = False
    temperature_verified: bool = False
    allergens_verified: bool = False
    packaging_verified: bool = False
    local_requirements_verified: bool = False

class ListingCreate(BaseModel):
    donor_name: str = Field(min_length=2, max_length=100)
    food_type: str = Field(min_length=2, max_length=100)
    portions: int = Field(gt=0, le=100000)
    pickup_area: str = Field(min_length=2, max_length=100)
    deadline: datetime
    prepared_at: datetime | None = None
    safety_verified_by: str = Field(default="", max_length=100)
    safety: SafetyChecks

    @field_validator("donor_name", "food_type", "pickup_area")
    @classmethod
    def trim_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("safety_verified_by")
    @classmethod
    def trim_verifier(cls, value):
        return value.strip()

    @field_validator("deadline", "prepared_at")
    @classmethod
    def local_naive_only(cls, value):
        if value is not None and value.tzinfo is not None and value.utcoffset() is not None:
            raise ValueError("Use a local time without timezone suffix in this demo.")
        return value

class AvailabilityUpdate(BaseModel):
    available: bool

class RescueProposal(BaseModel):
    recipient_id: int | None = Field(default=None, gt=0)

class RescueDecision(BaseModel):
    recipient_id: int = Field(gt=0)
    reason: str = Field(default="", max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        return value.strip()

class RescueTransition(BaseModel):
    status: Literal["ready_for_pickup", "collected", "delivered", "cancelled"]
    pickup_notes: str | None = Field(default=None, max_length=1000)
    delivery_notes: str | None = Field(default=None, max_length=1000)

    @field_validator("pickup_notes", "delivery_notes")
    @classmethod
    def trim_notes(cls, value):
        return value.strip() if value is not None else None

class SignupRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["DONOR", "RECIPIENT", "VOLUNTEER"]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        if not re.search(r"[A-Z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Use at least 8 characters, including one uppercase letter and one number.")
        return value

class RoleProfileCreate(BaseModel):
    role: Literal["DONOR", "RECIPIENT", "VOLUNTEER"]

class RoleSwitch(BaseModel):
    role: Literal["DONOR", "RECIPIENT", "VOLUNTEER", "ADMIN"]

class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    role: Literal["DONOR", "RECIPIENT", "VOLUNTEER", "ADMIN"] | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email(value)

class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm_email: str = Field(min_length=5, max_length=254)

    @field_validator("confirm_email")
    @classmethod
    def normalize_confirm_email(cls, value):
        return normalize_email(value)

class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    role: Literal["DONOR", "RECIPIENT", "VOLUNTEER", "ADMIN"] | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email(value)

class PasswordResetConfirm(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value):
        if not re.search(r"[A-Z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Use at least 8 characters, including one uppercase letter and one number.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return normalize_email(value)

class ProfileUpdate(BaseModel):
    profile: dict[str, object]

class OrganizationApplicationRequest(BaseModel):
    profile: dict[str, object]
    certificate_filename: str = Field(min_length=1, max_length=255)
    certificate_base64: str = Field(min_length=1, max_length=28_000_000)

class VerificationDecision(BaseModel):
    decision: Literal["approved", "rejected", "resubmission_required"]
    reason: str = Field(default="", max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_review_reason(cls, value):
        return value.strip()

class VolunteerAssignment(BaseModel):
    volunteer_user_id: int = Field(gt=0)
