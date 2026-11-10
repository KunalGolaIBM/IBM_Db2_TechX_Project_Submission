"""Recommendation Agent for ColdChain Guardian.

The agent consumes the workflow state produced by the Risk Assessment agent
and creates deterministic, human‑actionable recommendations.  It mirrors the
rule set used by the public API (`app.routes.recommendations`) so that both the
API and the LangGraph workflow stay in sync.

Key responsibilities:
* Validate required upstream fields (including a robust ``risk_score`` check).
* Generate a deterministic list of (action, justification, priority) tuples.
* Insert any missing recommendations into ``RECOMMENDATIONS`` while **not**
  treating duplicate rows as newly created.
* Record an audit entry **only** for successfully inserted rows and never
  pass an invalid ``incident_id`` to ``log_action``.
* Return the full set of recommendations for the incident and expose the IDs
  of rows that were actually inserted during this execution.
"""

from typing import List, Dict, Any
import math

# ----------------------------------------------------------------------
# Deterministic rule generation – identical to the API implementation.
# ----------------------------------------------------------------------

def _generate_rules(severity: str, risk_level: str, temperature_deviation: float, product_sensitivity: str) -> List[tuple]:
    """Return a deterministic list of (action, justification, priority) tuples.

    The logic mirrors ``app.routes.recommendations._generate_rules`` but also
    incorporates ``risk_level``, ``temperature_deviation`` and
    ``product_sensitivity`` to produce richer recommendations.
    """
    base = [
        (
            "Inspect refrigeration equipment",
            "Temperature out‑of‑range detected; equipment may be faulty.",
            1,
        ),
        (
            "Contact logistics operator",
            "Shipment could be compromised; operator needs to be notified.",
            2,
        ),
    ]
    # Severity‑driven actions
    if severity == "CRITICAL":
        base.append(
            (
                "Divert to qualified cold‑storage facility",
                "Immediate cooling required to prevent product loss.",
                1,
            )
        )
        base.append(("Escalate to supervisor", "High‑risk incident demands senior oversight.", 1))
    elif severity == "HIGH":
        base.append(
            (
                "Quarantine shipment pending expert assessment",
                "Risk is high; isolate until further analysis.",
                2,
            )
        )
    else:  # MEDIUM or LOW
        base.append(("Monitor closely", "Deviation modest; continue observation.", 3))

    # Risk‑level driven actions
    if risk_level in ("CRITICAL", "HIGH"):
        base.append(
            (
                "Perform product quality assessment",
                "High risk may have impacted product integrity.",
                2,
            )
        )

    # Temperature deviation driven action (significant deviation > 5°C)
    if temperature_deviation > 5.0:
        base.append(
            (
                "Stabilise temperature immediately",
                f"Deviation of {temperature_deviation:.1f}°C exceeds safe margin.",
                1,
            )
        )

    # Product‑sensitivity driven action
    if product_sensitivity.upper() == "HIGH":
        base.append(
            (
                "Increase monitoring frequency",
                "Highly sensitive product; tighter control required.",
                2,
            )
        )

    # Remove duplicate actions while preserving order
    seen = set()
    uniq = []
    for rec in base:
        if rec[0] not in seen:
            uniq.append(rec)
            seen.add(rec[0])
    return uniq
# Duplicate legacy implementations removed


# ----------------------------------------------------------------------

def _validate_state(state: Dict[str, Any]) -> tuple[bool, str]:
    """Validate that the upstream state contains everything we need.

    Returns ``(True, "")`` when valid, otherwise ``(False, error_message)``.
    """
    incident_id = state.get("incident_id")
    severity = state.get("severity")
    risk_score = state.get("risk_score")
    risk_level = state.get("risk_level")
    product = state.get("product")
    temperature_deviation = state.get("temperature_deviation")

    # incident_id must be a positive int (bools are rejected)
    if not isinstance(incident_id, int) or isinstance(incident_id, bool) or incident_id <= 0:
        return False, "Invalid or missing incident_id"

    if not isinstance(severity, str) or severity.upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return False, f"Invalid severity '{severity}'"

    # risk_score: numeric, finite, 0‑100, bool rejected
    if not isinstance(risk_score, (int, float)) or isinstance(risk_score, bool):
        return False, "Invalid or missing risk_score"
    try:
        rs_val = float(risk_score)
        if not math.isfinite(rs_val) or rs_val < 0 or rs_val > 100:
            raise ValueError()
    except Exception:
        return False, f"risk_score must be a finite number between 0 and 100 (got {risk_score})"

    if not isinstance(risk_level, str) or risk_level.upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return False, f"Invalid risk_level '{risk_level}'"

    if not isinstance(product, dict):
        return False, "Product must be a dictionary"
    sens = product.get("sensitivity") or product.get("sensitivity_level")
    if not isinstance(sens, str) or sens.upper() not in {"LOW", "MEDIUM", "HIGH"}:
        return False, f"Invalid product sensitivity '{sens}'"

    # temperature_deviation: numeric, finite, non‑negative
    try:
        td = float(temperature_deviation)
        if not math.isfinite(td) or td < 0:
            raise ValueError()
    except Exception:
        return False, f"Invalid temperature_deviation '{temperature_deviation}'"

    return True, ""


# ----------------------------------------------------------------------
def run(state: dict) -> dict:
    """Generate recommendations for the current incident.

    Expected keys in ``state`` (produced by the Risk Assessment agent):
        - incident_id (int)
        - severity (str)
        - risk_score (float)
        - risk_level (str)
        - product (dict) – contains ``sensitivity`` or ``sensitivity_level``
        - temperature_deviation (float)
        - sensor (optional)
        - shipment (optional)

    The function adds three keys to ``state``:
        - recommendations: list of *all* recommendation rows for the incident
        - recommendation_ids: list of IDs that were newly inserted
        - recommendations_generated: bool flag (True when we inserted at least one row)
    """
    # -----------------------------------------------------------------
    # Lazy imports – keep import‑time failures isolated.
    # -----------------------------------------------------------------
    try:
        from app.database.db import (
            execute_query,
            execute_query_one,
            execute_insert_get_id,
        )
    except Exception as exc:
        state["error"] = f"Database helpers unavailable: {exc}"
        state["status"] = "FAILED"
        return state

    try:
        from app.database.audit import log_action
    except Exception:
        # If audit cannot be imported, replace with a no‑op.
        def log_action(*_, **__):  # type: ignore
            pass

    # -----------------------------------------------------------------
    # 1️⃣ Validate required fields.
    # -----------------------------------------------------------------
    ok, err_msg = _validate_state(state)
    if not ok:
        state["error"] = err_msg
        state["status"] = "FAILED"
        return state

    incident_id = state["incident_id"]
    severity = state["severity"].upper()
    # Extract product dict for later use
    product = state["product"]

    # -----------------------------------------------------------------
    # 2️⃣ Generate deterministic rules based on severity, risk level, deviation and product sensitivity.
    # -----------------------------------------------------------------
    risk_level = state["risk_level"].upper()
    temperature_deviation = float(state["temperature_deviation"])
    product_sensitivity = (product.get("sensitivity") or product.get("sensitivity_level"))
    rules = _generate_rules(severity, risk_level, temperature_deviation, product_sensitivity)

    # -----------------------------------------------------------------
    # 3️⃣ Insert missing recommendations – collect only truly new IDs.
    # -----------------------------------------------------------------
    new_ids: List[int] = []
    for action, justification, priority in rules:
        # 1️⃣ Check for existing recommendation
        try:
            existing = execute_query_one(
                "SELECT RECOMMENDATION_ID FROM RECOMMENDATIONS WHERE INCIDENT_ID = ? AND ACTION = ?",
                (incident_id, action),
            )
        except Exception as e:
            try:
                log_action(
                    agent_name="RecommendationAgent",
                    action_taken="db_select_error",
                    details=f"Failed to check duplicate for action '{action}': {e}",
                    incident_id=incident_id,
                )
            except Exception:
                pass
            existing = None
        if existing:
            # duplicate – skip insertion
            continue

        # 2️⃣ Normal INSERT (no conditional part)
        insert_sql = """
            INSERT INTO RECOMMENDATIONS (
                INCIDENT_ID, ACTION, JUSTIFICATION, PRIORITY, APPROVAL_STATUS
            ) VALUES (?, ?, ?, ?, 'PENDING')
        """
        try:
            rec_id = execute_insert_get_id(insert_sql, (incident_id, action, justification, priority))
        except Exception as e:
            try:
                log_action(
                    agent_name="RecommendationAgent",
                    action_taken="db_insert_error",
                    details=f"Failed to insert recommendation '{action}': {e}",
                    incident_id=incident_id,
                )
            except Exception:
                pass
            continue

                # 3️⃣ Record successful insertion
        if isinstance(rec_id, int) and rec_id > 0:
            new_ids.append(rec_id)
            try:
                log_action(
                    agent_name="RecommendationAgent",
                    action_taken="generate",
                    details=f"Generated recommendation '{action}' for incident {incident_id}",
                    incident_id=incident_id,
                    recommendation_id=rec_id,
                )
            except Exception:
                pass
        else:
            # Insertion succeeded but returned an unexpected ID; log for debugging.
            try:
                log_action(
                    agent_name="RecommendationAgent",
                    action_taken="db_insert_unexpected_id",
                    details=f"Insert returned unexpected ID {rec_id} for action '{action}'",
                    incident_id=incident_id,
                )
            except Exception:
                pass


    # -----------------------------------------------------------------
    # 4️⃣ Retrieve **all** recommendations for the incident.
    # -----------------------------------------------------------------
    all_recs: List[Dict[str, Any]] = []
    try:
        all_recs = execute_query(
            """
            SELECT RECOMMENDATION_ID,
                   INCIDENT_ID,
                   ACTION,
                   JUSTIFICATION,
                   PRIORITY,
                   APPROVAL_STATUS,
                   CREATED_AT
            FROM RECOMMENDATIONS
            WHERE INCIDENT_ID = ?
            ORDER BY PRIORITY, CREATED_AT
            """,
            (incident_id,),
        )
    except Exception as e:
        # Log retrieval error; keep the state as‑is (empty list).
        try:
            log_action(
                agent_name="RecommendationAgent",
                action_taken="db_select_error",
                details=f"Failed to fetch recommendations for incident {incident_id}: {e}",
                incident_id=incident_id,
            )
        except Exception:
            pass
        # Do not raise – just leave ``all_recs`` empty.

    # -----------------------------------------------------------------
    # 5️⃣ Update workflow state.
    # -----------------------------------------------------------------
    state["recommendations"] = all_recs
    state["recommendation_ids"] = new_ids
    state["recommendations_generated"] = bool(new_ids)

    return state
