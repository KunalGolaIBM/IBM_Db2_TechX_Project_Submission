"""
MediTwin AI — Pydantic Validation Models
Strict models for extracted medical observations and data validation.
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class ExtractedObservation(BaseModel):
    """A single medical observation extracted from a document."""
    test_name: str = Field(..., min_length=1, max_length=200,
                           description="Name of the medical test or measurement")
    test_code: Optional[str] = Field(None, max_length=50,
                                      description="Standardized code for the test (e.g., HBA1C, CBC)")
    value_numeric: Optional[float] = Field(None,
                                            description="Numeric value of the measurement")
    value_text: Optional[str] = Field(None, max_length=500,
                                       description="Text value when not numeric")
    unit: Optional[str] = Field(None, max_length=50,
                                 description="Unit of measurement (e.g., %, mg/dL, mmol/L)")
    reference_low: Optional[float] = Field(None,
                                            description="Lower bound of reference range from source")
    reference_high: Optional[float] = Field(None,
                                             description="Upper bound of reference range from source")
    observed_at: Optional[str] = Field(None,
                                        description="Date of observation in YYYY-MM-DD format")
    source_page: Optional[int] = Field(None, ge=1,
                                        description="Page number where this was found")
    source_snippet: Optional[str] = Field(None, max_length=500,
                                           description="Exact text snippet from the source document")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0,
                                         description="Extraction confidence score 0-1")

    @field_validator('observed_at')
    @classmethod
    def validate_date(cls, v):
        """Validate date format if provided."""
        if v is None:
            return v
        # Try to parse as YYYY-MM-DD
        try:
            parsed = datetime.strptime(v, "%Y-%m-%d")
            # Sanity check: date should not be in the far future
            if parsed.date() > date(2030, 12, 31):
                return None  # Flag for review
            return v
        except ValueError:
            # Try other common formats
            for fmt in ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"]:
                try:
                    parsed = datetime.strptime(v, fmt)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return None  # Could not parse — flag for review

    @field_validator('test_code')
    @classmethod
    def normalize_test_code(cls, v):
        """Normalize test code to uppercase."""
        if v:
            return v.upper().strip()
        return v

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v):
        """Basic unit validation."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        return v

    @model_validator(mode='after')
    def check_value_exists(self):
        """Ensure at least one value field is populated."""
        if self.value_numeric is None and not self.value_text:
            # Mark as lower confidence if no value found
            if self.confidence and self.confidence > 0.5:
                self.confidence = 0.5
        return self

    @property
    def needs_review(self) -> bool:
        """Determine if this observation requires mandatory review."""
        reasons = []
        if self.observed_at is None:
            reasons.append("missing_date")
        if self.unit is None and self.value_numeric is not None:
            reasons.append("missing_unit")
        if self.value_numeric is None and not self.value_text:
            reasons.append("missing_value")
        if self.confidence is not None and self.confidence < 0.7:
            reasons.append("low_confidence")
        return len(reasons) > 0

    @property
    def review_reasons(self) -> List[str]:
        """List specific reasons why review is needed."""
        reasons = []
        if self.observed_at is None:
            reasons.append("Date could not be identified")
        if self.unit is None and self.value_numeric is not None:
            reasons.append("Unit could not be identified")
        if self.value_numeric is None and not self.value_text:
            reasons.append("No value extracted")
        if self.confidence is not None and self.confidence < 0.7:
            reasons.append(f"Low confidence ({self.confidence:.0%})")
        return reasons


class ExtractionResult(BaseModel):
    """Result of extracting observations from a document page or section."""
    observations: List[ExtractedObservation] = Field(default_factory=list)
    document_date: Optional[str] = Field(None,
                                          description="Overall document date if identified")
    patient_name_found: Optional[str] = Field(None,
                                               description="Patient name found in document (for matching)")
    extraction_notes: Optional[str] = Field(None,
                                             description="Any notes about the extraction process")


class ReviewDecision(BaseModel):
    """A human review decision for an observation."""
    observation_id: int
    action: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    corrected_test_code: Optional[str] = None
    corrected_value_numeric: Optional[float] = None
    corrected_value_text: Optional[str] = None
    corrected_unit: Optional[str] = None
    corrected_date: Optional[str] = None
    reviewer_notes: Optional[str] = None
    reviewed_by: str = "CLINICAL_REVIEWER"

    @field_validator('corrected_date')
    @classmethod
    def validate_corrected_date(cls, v):
        if v is None or not str(v).strip():
            return None
        v = str(v).strip()
        try:
            parsed = datetime.strptime(v, "%Y-%m-%d")
            if parsed.date() > date(2030, 12, 31):
                raise ValueError("Observation date cannot be in the distant future.")
            if parsed.date() < date(1900, 1, 1):
                raise ValueError("Observation date cannot be before 1900.")
            return parsed.strftime("%Y-%m-%d")
        except ValueError as e:
            if "format" in str(e).lower() or "does not match" in str(e).lower():
                raise ValueError(f"Invalid date format '{v}'. Expected YYYY-MM-DD.")
            raise

    @field_validator('corrected_test_code')
    @classmethod
    def normalize_code(cls, v):
        if v and str(v).strip():
            return str(v).upper().strip()
        return None


def validate_observations(observations: list) -> tuple:
    """
    Validate a list of raw observation dictionaries or objects.
    Returns (valid_observations, validation_errors).
    """
    valid_list = []
    errors = []

    for idx, item in enumerate(observations, start=1):
        try:
            if isinstance(item, ExtractedObservation):
                obs = item
            elif isinstance(item, dict):
                obs = ExtractedObservation(**item)
            else:
                errors.append(f"Observation {idx}: Unsupported type {type(item)}")
                continue
            valid_list.append(obs)
        except Exception as e:
            errors.append(f"Observation {idx}: Validation error - {str(e)}")

    return valid_list, errors


