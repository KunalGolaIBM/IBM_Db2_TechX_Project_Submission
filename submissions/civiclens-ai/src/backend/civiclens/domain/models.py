"""Pydantic request/response models shared by the API and the agent tools."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(StrEnum):
    POTHOLE = "POTHOLE"
    STREETLIGHT = "STREETLIGHT"
    WATER_LEAK = "WATER_LEAK"
    SEWAGE = "SEWAGE"
    GARBAGE = "GARBAGE"
    DRAINAGE = "DRAINAGE"
    ROAD_DAMAGE = "ROAD_DAMAGE"
    TRAFFIC_SIGNAL = "TRAFFIC_SIGNAL"
    OTHER = "OTHER"


class ComplaintStatus(StrEnum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    DUPLICATE = "DUPLICATE"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class ComplaintCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: Category
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    ward: str | None = Field(default=None, max_length=64)
    severity: int = Field(default=3, ge=1, le=5)
    reported_at: datetime | None = None
    external_ref: str | None = Field(default=None, max_length=64)
    source: str = Field(default="API", max_length=32, pattern=r"^[A-Z0-9_]+$")
    is_synthetic: bool = False

    @field_validator("reported_at")
    @classmethod
    def _naive_utc(cls, value: datetime | None) -> datetime | None:
        # Db2 TIMESTAMP has no zone: store UTC, drop tzinfo.
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value


class Complaint(BaseModel):
    complaint_id: int
    external_ref: str | None
    category: Category
    title: str
    description: str
    latitude: float
    longitude: float
    geo_cell: str
    ward: str | None
    severity: int
    status: ComplaintStatus
    source: str
    duplicate_of: int | None
    is_synthetic: bool
    reported_at: datetime
    created_at: datetime


class DuplicateCandidate(BaseModel):
    complaint_id: int
    title: str
    distance_m: float
    text_similarity: float
    score: float


class Hotspot(BaseModel):
    geo_cell: str
    category: Category
    complaint_count: int
    avg_severity: float
    center_latitude: float
    center_longitude: float
    first_reported_at: datetime
    last_reported_at: datetime


class ComplaintCreated(BaseModel):
    complaint: Complaint
    duplicate_candidates: list[DuplicateCandidate]
