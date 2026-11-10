"""Data shapes shared by intake, trace and UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

SUPPORTED_FUNCTION = "external_diameter"
SUPPORTED_UNIT = "mm"

REVIEW_SCOPE = "REVIEW_SCOPE"
OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

CROSSES = "CROSSES_LIMIT_UNDER_ASSUMPTION"
WITHIN = "WITHIN_LIMITS_UNDER_ASSUMPTION"


# ---------- AI extraction schema (LangChain structured output) ----------

class EvidenceQuote(BaseModel):
    field: str = Field(description="Name of the extracted field this quote supports, e.g. instrument_id.")
    quote: str = Field(description="Exact, verbatim substring copied from the notice. Never paraphrase.")


class NoticeExtraction(BaseModel):
    report_reference: Optional[str] = Field(None, description="Calibration report identifier exactly as written, or null.")
    instrument_id: Optional[str] = Field(
        None,
        description="Instrument identifier exactly as written in the notice (keep hyphens and leading zeros). Null if absent or ambiguous.",
    )
    function_code: Literal["external_diameter", "unsupported", "unknown"] = Field(
        description="external_diameter if the failed check concerns external diameter; unsupported for another measurement function; unknown if unclear."
    )
    detected_at: Optional[str] = Field(None, description="ISO-8601 UTC timestamp of the failed check, only if the notice states date and time. Null otherwise.")
    observed_error_magnitude_mm: Optional[float] = Field(None, description="Absolute as-found error in millimetres if stated, else null.")
    observed_direction: Literal["low", "high", "unknown"] = Field(description="Direction of as-found error.")
    scope_limitations: list[str] = Field(
        default_factory=list,
        description="Any restriction the notice places on scope (test-point ranges, units, date limits, contradictions). Empty if none.",
    )
    evidence: list[EvidenceQuote] = Field(default_factory=list, description="One exact quote per extracted non-null field.")
    missing_fields: list[str] = Field(default_factory=list, description="Fields the notice does not state.")


# ---------- Trace records ----------

@dataclass(frozen=True)
class InspectionFact:
    inspection_id: str
    instrument_id: Optional[str]
    instrument_name: Optional[str]
    lot_id: str
    product_name: Optional[str]
    produced_quantity: Optional[int]
    measured_at: Optional[datetime]
    function_code: Optional[str]
    unit: Optional[str]
    recorded_value: Optional[Decimal]
    lower_limit: Optional[Decimal]
    upper_limit: Optional[Decimal]
    original_decision: Optional[str]


@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    lot_id: str
    customer_name: str
    shipped_quantity: int
    shipped_at: datetime


@dataclass(frozen=True)
class Scope:
    instrument_id: str
    function_code: str
    review_start: datetime
    review_end: datetime
    unit: str = SUPPORTED_UNIT


@dataclass
class Finding:
    fact: InspectionFact
    classification: str
    reason: str
    shipments: list[Shipment] = field(default_factory=list)
    hypothetical: Optional[str] = None
    hypothetical_interval: Optional[tuple[Decimal, Decimal]] = None


@dataclass
class Totals:
    review_lots: list[str]
    review_shipments: list[str]
    review_shipped_units: int
    review_unshipped_units: int
    review_produced_units: int
    insufficient_lots: list[str]
    insufficient_shipments: list[str]
    insufficient_shipped_units: int
    outside_inspections: int
