'''Incident Detection Agent

Creates an incident when a temperature violation is reported by the Monitoring
agent.  It uses the actual ``INCIDENTS`` table schema:

    INCIDENT_ID (identity)
    SHIPMENT_ID
    INCIDENT_TYPE
    SEVERITY
    DESCRIPTION
    STATUS
    CREATED_AT

The agent:
* Prevents duplicate *active* incidents for the same shipment.
* Derives a deterministic severity from product sensitivity and temperature
  deviation (same weighting as the Incident agent).
* Stores the sensor‑reading details in the free‑form ``DESCRIPTION`` column.
* Sets ``INCIDENT_TYPE`` to ``'TEMPERATURE_EXCURSION'`` and ``STATUS`` to
  ``'OPEN'``.  ``CREATED_AT`` is populated with ``CURRENT TIMESTAMP``.
* Logs every action via ``log_action``.
'''

from typing import Dict, Any

from app.database.db import execute_query_one, execute_insert_get_id
from app.database.audit import log_action


def _calc_severity(sensitivity: str, deviation: float) -> str:
    """Deterministic severity mapping (weights total 100).

    * Sensitivity base weight: HIGH = 30, MEDIUM = 20, LOW = 10.
    * Deviation weight: ≤2 °C → 0, 2‑5 °C → 10, 5‑10 °C → 20, >10 °C → 30.
    * Sum is capped at 100 and mapped to a textual severity.
    """
    base = {"HIGH": 30, "MEDIUM": 20, "LOW": 10}.get(sensitivity.upper(), 10)
    if deviation <= 2:
        dev_score = 0
    elif deviation <= 5:
        dev_score = 10
    elif deviation <= 10:
        dev_score = 20
    else:
        dev_score = 30
    total = min(base + dev_score, 100)
    if total <= 30:
        return "LOW"
    if total <= 60:
        return "MEDIUM"
    if total <= 85:
        return "HIGH"
    return "CRITICAL"


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Detect a temperature violation and create an INCIDENT row.

    Expected keys in ``state`` (produced by the Monitoring agent):
        - ``sensor`` (dict with ``reading_id``, ``shipment_id``, ``temperature``)
        - ``shipment`` (dict with ``shipment_id``, ``product_id``)
        - ``product`` (dict with ``product_id`` and ``sensitivity``)
        - ``temperature_status`` ("VIOLATION" or "NORMAL")
        - ``temperature_deviation`` (float, 0.0 when normal)

    The function adds ``incident_id``, ``incident_created`` (bool) and
    ``severity`` to the state.
    """
    sensor = state.get('sensor')
    shipment = state.get('shipment')
    product = state.get('product')
    # Adjust key name for sensitivity level as defined in monitoring agent
    if product and 'sensitivity_level' in product:
        product['sensitivity'] = product['sensitivity_level']
    temp_status = state.get('temperature_status')
    deviation = state.get('temperature_deviation', 0.0)

    if not (sensor and shipment and product and temp_status):
        log_action(
            agent_name='IncidentAgent',
            action_taken='missing_context',
            details='Required keys from monitoring step are absent.',
        )
        state['error'] = 'Required keys from monitoring step are absent.'
        state['status'] = 'FAILED'
        return state

    # Only act on a temperature violation
    if temp_status != 'VIOLATION':
        state.update({
            'incident_id': None,
            'incident_created': False,
            'severity': None,
        })
        return state

    shipment_id = sensor['shipment_id']
    reading_id = sensor['reading_id']
    temperature = sensor['temperature']
    product_id = product['product_id']
    sensitivity = product['sensitivity']

    # -----------------------------------------------------------------
    # 1️⃣ Duplicate guard – look for an active incident for this shipment.
    # -----------------------------------------------------------------
    existing = execute_query_one(
        """
        SELECT INCIDENT_ID, STATUS, SEVERITY
        FROM INCIDENTS
        WHERE SHIPMENT_ID = ?
          AND STATUS <> 'RESOLVED'
        """,
        (shipment_id,)
    )
    if existing:
        incident_id = int(existing['incident_id'])
        state.update({
            'incident_id': incident_id,
            'incident_created': False,
            'severity': existing.get('severity'),
        })
        log_action(
            agent_name='IncidentAgent',
            action_taken='duplicate_skip',
            details=(
                f"Active incident {incident_id} already exists for shipment {shipment_id}."
            ),
            incident_id=incident_id,
        )
        return state

    # -----------------------------------------------------------------
    # 2️⃣ Compute severity deterministically.
    # -----------------------------------------------------------------
    severity = _calc_severity(sensitivity, deviation)

    # -----------------------------------------------------------------
    # 3️⃣ Insert new incident using only columns that exist in the schema.
    # -----------------------------------------------------------------
    description = (
        f"Reading ID {reading_id}, Temp {temperature}°C, Deviation {deviation}°C, "
        f"Product ID {product_id}."
    )
    # VALUES populates IDENTITY_VAL_LOCAL(). INSERT ... SELECT does not.
    insert_sql = """
        INSERT INTO INCIDENTS (
            SHIPMENT_ID,
            INCIDENT_TYPE,
            SEVERITY,
            DESCRIPTION,
            STATUS,
            CREATED_AT
        )
        VALUES (?, ?, ?, ?, ?, CURRENT TIMESTAMP)
    """
    incident_id = execute_insert_get_id(
        insert_sql,
        (
            shipment_id,
            'TEMPERATURE_EXCURSION',
            severity,
            description,
            'OPEN',
        ),
    )
    try:
        incident_id = int(incident_id)
    except (TypeError, ValueError):
        incident_id = 0
    if incident_id <= 0:
        stored = execute_query_one(
            """
            SELECT INCIDENT_ID, SEVERITY
            FROM INCIDENTS
            WHERE SHIPMENT_ID = ?
              AND STATUS <> 'RESOLVED'
            ORDER BY INCIDENT_ID DESC
            FETCH FIRST 1 ROW ONLY
            """,
            (shipment_id,),
        )
        if stored:
            incident_id = int(stored['incident_id'])
            severity = stored.get('severity') or severity
    if incident_id <= 0:
        state['error'] = 'Incident insert did not return an id.'
        state['status'] = 'FAILED'
        return state

    # -----------------------------------------------------------------
    # 4️⃣ Audit log.
    # -----------------------------------------------------------------
    log_action(
        agent_name='IncidentAgent',
        action_taken='create',
        details=(
            f"Created incident {incident_id} for shipment {shipment_id} "
            f"(severity={severity}, deviation={deviation})"
        ),
        incident_id=incident_id,
    )

    # -----------------------------------------------------------------
    # 5️⃣ Update state.
    # -----------------------------------------------------------------
    state.update({
        'incident_id': incident_id,
        'incident_created': True,
        'severity': severity,
    })
    return state
