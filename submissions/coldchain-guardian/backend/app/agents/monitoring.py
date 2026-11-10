'''Temperature Monitoring Agent

This agent receives a ``state`` dict that contains a ``reading_id`` (the primary key of the
``SENSOR_READINGS`` table). It loads the sensor reading together with its shipment and
product using a **single parameterised JOIN query**. The product defines the allowed
temperature range (``MIN_TEMPERATURE`` / ``MAX_TEMPERATURE``). The agent determines whether the reading
is within that range and, if not, computes the absolute deviation from the nearest bound.

The function updates the workflow ``state`` with the following keys:
- ``sensor``: dict containing the raw sensor‑reading row.
- ``shipment``: dict with the shipment row.
- ``product``: dict with the product row.
- ``temperature_status``: ``"NORMAL"`` or ``"VIOLATION"``.
- ``temperature_deviation``: ``0.0`` for normal readings, otherwise the absolute
  deviation (positive float).

All database access uses the shared helper ``execute_query_one`` from
``app.database.db``.  An audit entry is written via ``log_action``.
'''

from typing import Dict, Any

from app.database.db import execute_query_one
from app.database.audit import log_action


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process a sensor reading and attach temperature‑validation information.

    Expected ``state`` keys:
        - ``reading_id`` (int): primary key of ``SENSOR_READINGS``.
    The function adds ``sensor``, ``shipment``, ``product``,
    ``temperature_status`` and ``temperature_deviation`` to the state and returns it.

    Errors such as a missing ``reading_id`` or a failed lookup are logged via
    ``log_action`` and the original state is returned unchanged.
    """
    reading_id = state.get('reading_id')
    if not reading_id:
        # No reading ID – nothing to do.
        return state

    # -----------------------------------------------------------------
    # 1️⃣ Retrieve reading, shipment and product in a single JOIN.
    # -----------------------------------------------------------------
    sql = """
        SELECT
            r.reading_id               AS reading_id,
            r.shipment_id              AS shipment_id,
            r.temperature              AS temperature,
            r.humidity                 AS humidity,
            r.recorded_at              AS recorded_at,
            s.shipment_id              AS s_shipment_id,
            s.product_id               AS product_id,
            s.vehicle_id               AS vehicle_id,
            s.source_location          AS source_location,
            s.destination_location     AS destination_location,
            s.shipment_status          AS shipment_status,
            s.departure_time           AS departure_time,
            s.expected_arrival         AS expected_arrival,
            p.product_id               AS p_product_id,
            p.product_name             AS product_name,
            p.product_category         AS product_category,
            p.min_temperature          AS min_temperature,
            p.max_temperature          AS max_temperature,
            p.sensitivity_level       AS sensitivity_level
        FROM SENSOR_READINGS r
        JOIN SHIPMENTS s ON r.shipment_id = s.shipment_id
        JOIN PRODUCTS p  ON s.product_id   = p.product_id
        WHERE r.reading_id = ?
    """
    # DB helper expects a positional parameters tuple.
    row = execute_query_one(sql, (reading_id,))
    if not row:
        log_action(
            agent_name='MonitoringAgent',
            action_taken='missing_reading',
            details=f'Reading id {reading_id} not found.'
        )
        state['error'] = f'Reading id {reading_id} not found.'
        state['status'] = 'FAILED'
        state['is_violation'] = False
        return state

    # -----------------------------------------------------------------
    # 2️⃣ Build sub‑dicts for sensor, shipment and product.
    # -----------------------------------------------------------------
    sensor = {
        'reading_id': row.get('reading_id'),
        'shipment_id': row.get('shipment_id'),
        'temperature': row.get('temperature'),
        'humidity': row.get('humidity'),
        'recorded_at': row.get('recorded_at'),
    }
    shipment = {
        'shipment_id': row.get('s_shipment_id'),
        'product_id': row.get('product_id'),
        'vehicle_id': row.get('vehicle_id'),
        'source_location': row.get('source_location'),
        'destination_location': row.get('destination_location'),
        'shipment_status': row.get('shipment_status'),
        'departure_time': row.get('departure_time'),
        'expected_arrival': row.get('expected_arrival'),
    }
    product = {
        'product_id': row.get('p_product_id'),
        'product_name': row.get('product_name'),
        'product_category': row.get('product_category'),
        'min_temperature': row.get('min_temperature'),
        'max_temperature': row.get('max_temperature'),
        'sensitivity_level': row.get('sensitivity_level'),
    }

    # -----------------------------------------------------------------
    # 3️⃣ Temperature validation.
    # -----------------------------------------------------------------
    temperature = sensor.get('temperature')
    min_temp = product.get('min_temperature')
    max_temp = product.get('max_temperature')

    if temperature is None or min_temp is None or max_temp is None:
        state['error'] = f'Reading {reading_id} is missing a temperature or product limit.'
        state['status'] = 'FAILED'
        state['is_violation'] = False
        state.update({
            'sensor': sensor,
            'shipment': shipment,
            'product': product,
        })
        return state

    temperature = float(temperature)
    min_temp = float(min_temp)
    max_temp = float(max_temp)
    sensor['temperature'] = temperature
    product['min_temperature'] = min_temp
    product['max_temperature'] = max_temp

    if temperature < min_temp:
        temperature_status = 'VIOLATION'
        temperature_deviation = min_temp - temperature
    elif temperature > max_temp:
        temperature_status = 'VIOLATION'
        temperature_deviation = temperature - max_temp
    else:
        temperature_status = 'NORMAL'
        temperature_deviation = 0.0

    # -----------------------------------------------------------------
    # 4️⃣ Audit log for the monitoring step.
    # -----------------------------------------------------------------
    log_action(
        agent_name='MonitoringAgent',
        action_taken='monitor',
        details=(
            f'Reading {reading_id}: temp={temperature}, '
            f'limits=({min_temp},{max_temp}), '
            f'status={temperature_status}, deviation={temperature_deviation}'
        )
    )

    # -----------------------------------------------------------------
    # 5️⃣ Update workflow state.
    # -----------------------------------------------------------------
    state.update({
        'sensor': sensor,
        'shipment': shipment,
        'product': product,
        'temperature_status': temperature_status,
        'temperature_deviation': temperature_deviation,
    })
    return state
