"""Request/response models for the REST API (Pydantic validation at the boundary)."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9-]{2,29}$"


class IncidentCreate(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    source_ref: str = Field(pattern=ID_PATTERN, description="Ingredient lot ID or production batch ID")
    contaminant: str = Field(min_length=2, max_length=120)
    contamination_category: Literal["MICROBIAL", "CHEMICAL", "PHYSICAL", "ALLERGEN", "OTHER"]
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    supplier_id: str | None = Field(default=None, pattern=r"^SUP-\d{3}$")
    discovered_at: dt.datetime | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_demo: bool = False

    @field_validator("source_ref")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("title", "contaminant", "description")
    @classmethod
    def strip_ctrl(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return "".join(ch for ch in v if ch.isprintable() or ch in "\n\t").strip()


class Decision(BaseModel):
    comment: str = Field(default="", max_length=2000)


class GenerateRecall(BaseModel):
    incident_id: str = Field(pattern=ID_PATTERN)
    run_id: str | None = Field(default=None, max_length=40)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ActionUpdate(BaseModel):
    status: Literal["SENT", "ACKNOWLEDGED", "PENDING", "IN_PROGRESS", "DONE"]
    units_recovered: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class VerificationUpdate(BaseModel):
    status: Literal["UNVERIFIED", "VERIFIED", "DISPUTED"]


class Reinvestigate(BaseModel):
    reason: str = Field(default="", max_length=500)
