"""FastAPI endpoints for telemetry ingestion, explainable alerts and assistant queries."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .assistant import ask_assistant
from .store import get_store
from .workflow import run_agent_workflow

logger = logging.getLogger("energysense.api")

app = FastAPI(
    title="EnergySense AI API",
    description=(
        "Appliance telemetry, IBM Db2 storage, explainable anomaly detection and "
        "an optional LangChain tool-calling assistant. AI insights never control a relay."
    ),
    version="1.1.0",
)


class TelemetryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_id: str = Field(min_length=1, max_length=64)
    appliance_id: str = Field(min_length=1, max_length=64)
    appliance_name: str | None = Field(default=None, max_length=128)
    vrms_v: float | None = Field(default=None, strict=True, ge=0, le=600, allow_inf_nan=False)
    irms_a: float | None = Field(default=None, strict=True, ge=0, le=500, allow_inf_nan=False)
    apparent_power_va: float | None = Field(default=None, strict=True, ge=0, le=100000, allow_inf_nan=False)
    runtime_s: float | None = Field(default=None, strict=True, ge=0, le=10**9, allow_inf_nan=False)
    temperature_c: float | None = Field(default=None, strict=True, ge=-40, le=250, allow_inf_nan=False)
    vibration_rms: float | None = Field(default=None, strict=True, ge=0, le=1000, allow_inf_nan=False)
    relay_state: Literal["ON", "OFF", "UNKNOWN"] = "UNKNOWN"
    source: Literal["wokwi_simulated", "esp32", "synthetic"] = "synthetic"
    recorded_at: str | None = Field(default=None, max_length=64)

    @field_validator("equipment_id", "appliance_id")
    @classmethod
    def strip_identifiers(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identifier must contain non-whitespace characters")
        return value

    @field_validator("appliance_name")
    @classmethod
    def normalize_appliance_name(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None

    @field_validator("recorded_at")
    @classmethod
    def normalize_timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("recorded_at must be a valid ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    @model_validator(mode="after")
    def require_at_least_one_measurement(self):
        fields = ("vrms_v", "irms_a", "apparent_power_va", "runtime_s", "temperature_c", "vibration_rms")
        if all(getattr(self, name) is None for name in fields):
            raise ValueError("At least one numeric telemetry measurement is required")
        return self


class AssistantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question must not be blank")
        return value


@app.get("/health")
def health():
    store = get_store()
    return {
        "status": "ok",
        "api_version": app.version,
        "database_backend": store.backend,
        **store.counts(),
    }


@app.post("/api/v1/telemetry")
def ingest_telemetry(payload: TelemetryIn):
    try:
        store = get_store()
        row = store.insert_telemetry(payload.model_dump())
        analysis = run_agent_workflow(store, row)
        return {"stored": True, "telemetry": row, "analysis": analysis}
    except Exception as exc:
        logger.exception("telemetry_processing_failed", extra={"appliance_id": payload.appliance_id})
        raise HTTPException(status_code=500, detail="Telemetry processing failed; check server logs.") from exc


@app.get("/api/v1/devices/{appliance_id}/status")
def get_device_status(appliance_id: str):
    """Return the latest recorded device state without inferring online connectivity."""
    appliance_id = appliance_id.strip()
    if not appliance_id:
        raise HTTPException(status_code=422, detail="appliance_id must not be blank")
    try:
        rows = get_store().recent_telemetry(appliance_id, limit=1)
        if not rows:
            return {"appliance_id": appliance_id, "has_readings": False, "latest": None}
        latest = rows[-1]
        return {
            "appliance_id": appliance_id,
            "has_readings": True,
            "latest": latest,
            "reported_relay_state": latest.get("relay_state", "UNKNOWN"),
            "source": latest.get("source", "unknown"),
            "last_recorded_at": latest.get("recorded_at"),
        }
    except Exception as exc:
        logger.exception("device_status_query_failed", extra={"appliance_id": appliance_id})
        raise HTTPException(status_code=500, detail="Device status query failed; check server logs.") from exc


@app.get("/api/v1/telemetry/{appliance_id}")
def get_telemetry(appliance_id: str, limit: int = Query(default=100, ge=1, le=500)):
    try:
        return {"items": get_store().recent_telemetry(appliance_id.strip(), limit)}
    except Exception as exc:
        logger.exception("telemetry_query_failed", extra={"appliance_id": appliance_id})
        raise HTTPException(status_code=500, detail="Telemetry query failed; check server logs.") from exc


@app.get("/api/v1/events")
def get_events(appliance_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)):
    try:
        appliance_id = appliance_id.strip() if appliance_id else None
        return {"items": get_store().list_events(appliance_id, limit)}
    except Exception as exc:
        logger.exception("event_query_failed", extra={"appliance_id": appliance_id})
        raise HTTPException(status_code=500, detail="Event query failed; check server logs.") from exc


@app.post("/api/v1/assistant")
def assistant_query(payload: AssistantIn):
    try:
        answer = ask_assistant(get_store(), payload.question)
        return {"answer": answer, "mode": "langchain_read_only_tool_agent"}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("assistant_request_failed")
        raise HTTPException(status_code=500, detail="Assistant request failed; check server logs.") from exc
