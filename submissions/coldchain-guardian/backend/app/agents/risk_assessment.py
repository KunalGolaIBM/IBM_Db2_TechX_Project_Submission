"""Risk Assessment Agent.

Consumes the state from the Incident agent and calculates a deterministic
risk score (0-100) based on four weighted factors:

* Severity - weight 30
* Product sensitivity - weight 25
* Temperature deviation - weight 25
* Exposure duration - weight 20 (optional, fallback to 0)

The total score is mapped to a textual risk level:

* 0-24   -> LOW
* 25-49  -> MEDIUM
* 50-74  -> HIGH
* 75-100 -> CRITICAL

An existing RISK_ASSESSMENTS row for the incident is reused. The deterministic
score stored in Db2 stays authoritative. A new row is inserted with
INSERT ... VALUES so Db2 IDENTITY_VAL_LOCAL() returns the real assessment id.
INSERT ... SELECT does not populate that function and previously surfaced id 0.
"""

from typing import Any, Dict
import math


_SEVERITY_SCORE = {
    "LOW": 0,
    "MEDIUM": 10,
    "HIGH": 20,
    "CRITICAL": 30,
}

_SENSITIVITY_SCORE = {
    "LOW": 0,
    "MEDIUM": 12.5,
    "HIGH": 25,
}

_MAX_DEVIATION = 10.0


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _fail(state: Dict[str, Any], message: str, incident_id: int | None = None) -> Dict[str, Any]:
    state["error"] = message
    state["status"] = "FAILED"
    if incident_id and incident_id > 0:
        try:
            from app.database.audit import log_action

            log_action(
                agent_name="RiskAssessmentAgent",
                action_taken="error",
                details=message,
                incident_id=incident_id,
            )
        except Exception:
            pass
    return state


def _normalize_deviation(deviation: float) -> float:
    capped = min(deviation, _MAX_DEVIATION)
    return (capped / _MAX_DEVIATION) * 25.0


def _map_score_to_level(score: float) -> str:
    if score <= 24:
        return "LOW"
    if score <= 49:
        return "MEDIUM"
    if score <= 74:
        return "HIGH"
    return "CRITICAL"


def _validate_state(state: Dict[str, Any]) -> tuple[bool, str]:
    incident_id = _as_int(state.get("incident_id"))
    severity = state.get("severity")
    product = state.get("product")
    deviation = _as_float(state.get("temperature_deviation"))

    if incident_id <= 0:
        return False, "Invalid or missing incident_id"

    if not isinstance(severity, str) or severity.upper() not in _SEVERITY_SCORE:
        return False, f"Invalid severity '{severity}'. Expected LOW, MEDIUM, HIGH, CRITICAL"

    if not isinstance(product, dict):
        return False, "Product must be a dictionary containing sensitivity"
    sensitivity = product.get("sensitivity") or product.get("sensitivity_level")
    if not isinstance(sensitivity, str) or sensitivity.upper() not in _SENSITIVITY_SCORE:
        return False, f"Invalid product sensitivity '{sensitivity}'. Expected LOW, MEDIUM, HIGH"

    if deviation is None or deviation < 0:
        return False, (
            f"Invalid temperature_deviation '{state.get('temperature_deviation')}'. "
            "Must be a finite non-negative number"
        )

    exposure = state.get("exposure_duration")
    if exposure is not None and _as_float(exposure) is None:
        return False, f"Invalid exposure_duration '{exposure}'. Must be a finite non-negative number"
    if exposure is not None and _as_float(exposure) < 0:
        return False, f"Invalid exposure_duration '{exposure}'. Must be a finite non-negative number"

    return True, ""


def _apply_existing(state: Dict[str, Any], existing: Dict[str, Any], incident_id: int) -> Dict[str, Any]:
    assessment_id = _as_int(existing.get("assessment_id"))
    risk_score = _as_float(existing.get("risk_score"))
    risk_level = existing.get("risk_level")
    if assessment_id <= 0 or risk_score is None or not isinstance(risk_level, str):
        return _fail(
            state,
            f"Stored risk assessment for incident {incident_id} is incomplete.",
            incident_id,
        )

    state.update(
        {
            "risk_assessment_id": assessment_id,
            "risk_score": risk_score,
            "risk_level": str(risk_level).upper(),
            "risk_explanation": existing.get("explanation"),
            "risk_reused": True,
        }
    )
    return state


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate or reuse a deterministic risk assessment for an incident."""
    try:
        from app.database.db import execute_query_one, execute_insert_get_id
    except Exception as exc:
        return _fail(state, f"Database helper import failed: {exc}")

    try:
        from app.database.audit import log_action
    except Exception as exc:
        return _fail(state, f"Audit helper import failed: {exc}")

    valid, err_msg = _validate_state(state)
    if not valid:
        incident_id = _as_int(state.get("incident_id"))
        if "incident_id" not in err_msg.lower() and incident_id > 0:
            try:
                log_action(
                    agent_name="RiskAssessmentAgent",
                    action_taken="validation_error",
                    details=err_msg,
                    incident_id=incident_id,
                )
            except Exception:
                pass
        return _fail(state, err_msg, incident_id if incident_id > 0 else None)

    incident_id = _as_int(state["incident_id"])
    state["incident_id"] = incident_id
    severity = state["severity"].upper()
    product = state.get("product", {})
    deviation = _as_float(state.get("temperature_deviation")) or 0.0
    exposure = state.get("exposure_duration")

    try:
        existing = execute_query_one(
            """
            SELECT ASSESSMENT_ID, RISK_SCORE, RISK_LEVEL, EXPLANATION
            FROM RISK_ASSESSMENTS
            WHERE INCIDENT_ID = ?
            ORDER BY ASSESSMENT_ID
            FETCH FIRST 1 ROW ONLY
            """,
            (incident_id,),
        )
    except Exception as exc:
        return _fail(state, f"Failed to query existing assessment: {exc}", incident_id)

    if existing:
        updated = _apply_existing(state, existing, incident_id)
        if updated.get("status") != "FAILED":
            try:
                log_action(
                    agent_name="RiskAssessmentAgent",
                    action_taken="duplicate_skip",
                    details=(
                        f"Assessment {updated.get('risk_assessment_id')} already exists "
                        f"for incident {incident_id}."
                    ),
                    incident_id=incident_id,
                )
            except Exception:
                pass
        return updated

    severity_score = _SEVERITY_SCORE[severity]
    sensitivity_val = product.get("sensitivity") or product.get("sensitivity_level")
    sensitivity_score = _SENSITIVITY_SCORE[str(sensitivity_val).upper()]
    deviation_score = _normalize_deviation(deviation)

    exposure_score = 0.0
    exposure_value = _as_float(exposure) if exposure is not None else None
    if exposure_value is not None and exposure_value >= 0:
        max_exposure = 120.0
        capped = min(exposure_value, max_exposure)
        exposure_score = (capped / max_exposure) * 20.0

    total_score = severity_score + sensitivity_score + deviation_score + exposure_score
    total_score = min(max(total_score, 0.0), 100.0)
    risk_level = _map_score_to_level(total_score)
    explanation = (
        f"Severity={severity} ({severity_score}), "
        f"Sensitivity={sensitivity_val} ({sensitivity_score}), "
        f"TempDeviation={deviation}°C ({deviation_score:.2f}), "
        f"ExposureScore={exposure_score:.2f}; total={total_score:.2f}."
    )

    # VALUES is required. INSERT ... SELECT leaves IDENTITY_VAL_LOCAL() null,
    # which the helper turns into 0 even though Db2 stored a real id.
    insert_sql = """
        INSERT INTO RISK_ASSESSMENTS (
            INCIDENT_ID,
            RISK_SCORE,
            RISK_LEVEL,
            EXPLANATION,
            ASSESSED_AT
        )
        VALUES (?, ?, ?, ?, CURRENT TIMESTAMP)
    """
    try:
        assessment_id = _as_int(
            execute_insert_get_id(
                insert_sql,
                (
                    incident_id,
                    round(total_score, 2),
                    risk_level,
                    explanation,
                ),
            )
        )
    except Exception as exc:
        return _fail(state, f"Failed to insert assessment: {exc}", incident_id)

    if assessment_id <= 0:
        try:
            stored = execute_query_one(
                """
                SELECT ASSESSMENT_ID, RISK_SCORE, RISK_LEVEL, EXPLANATION
                FROM RISK_ASSESSMENTS
                WHERE INCIDENT_ID = ?
                ORDER BY ASSESSMENT_ID DESC
                FETCH FIRST 1 ROW ONLY
                """,
                (incident_id,),
            )
        except Exception as exc:
            return _fail(state, f"Failed to re-read assessment: {exc}", incident_id)
        if not stored:
            return _fail(
                state,
                "Risk assessment insert did not return an id and no row was stored.",
                incident_id,
            )
        return _apply_existing(state, stored, incident_id)

    try:
        log_action(
            agent_name="RiskAssessmentAgent",
            action_taken="create",
            details=(
                f"Created risk assessment {assessment_id} for incident {incident_id} "
                f"(score={total_score:.2f}, level={risk_level})."
            ),
            incident_id=incident_id,
        )
    except Exception:
        pass

    state.update(
        {
            "risk_assessment_id": assessment_id,
            "risk_score": round(total_score, 2),
            "risk_level": risk_level,
            "risk_explanation": explanation,
            "risk_reused": False,
        }
    )
    return state
