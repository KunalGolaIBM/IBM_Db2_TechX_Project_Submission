"""
MediTwin AI — Timeline Service
Builds chronological patient timelines and computes metric trends.
Strict unit compatibility, deterministic mathematics, and deduplication.
"""

import logging
from typing import List, Dict, Optional, Tuple, Set, Any
from datetime import datetime, date

logger = logging.getLogger(__name__)


def parse_safe_date(date_val: Any) -> Tuple[datetime, str]:
    """
    Safely parse any date value into a datetime object and ISO string.
    Returns (datetime, date_str). Fallback is datetime.min for invalid values.
    """
    if date_val is None:
        return datetime.min, "Unknown Date"

    if isinstance(date_val, datetime):
        return date_val, date_val.strftime("%Y-%m-%d")

    if isinstance(date_val, date):
        dt = datetime.combine(date_val, datetime.min.time())
        return dt, date_val.strftime("%Y-%m-%d")

    date_str = str(date_val).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(date_str[:19], fmt)
            return dt, dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return datetime.min, date_str


def build_patient_timeline(observations: List[Dict],
                            documents: List[Dict] = None) -> List[Dict]:
    """
    Build a chronological timeline from approved observations and documents.
    Orders newest first with deterministic secondary sort on ID.
    Deduplicates identical records.
    """
    timeline = []
    seen_obs_signatures: Set[Tuple] = set()

    # Add observation events
    for obs in observations:
        # Strictly omit rejected observations
        status = str(obs.get("REVIEW_STATUS") or obs.get("review_status") or "APPROVED").upper()
        if status == "REJECTED":
            continue

        obs_id = obs.get("OBSERVATION_ID") or obs.get("observation_id") or 0
        raw_date = obs.get("OBSERVED_AT") or obs.get("observed_at")
        dt, date_str = parse_safe_date(raw_date)

        test_name = obs.get("TEST_NAME") or obs.get("test_name", "Unknown Test")
        num_val = obs.get("VALUE_NUMERIC")
        if num_val is None:
            num_val = obs.get("value_numeric")
        txt_val = obs.get("VALUE_TEXT") or obs.get("value_text")
        unit = obs.get("UNIT") or obs.get("unit", "")
        source = obs.get("FILE_NAME") or obs.get("file_name", "")

        # Deduplication check: prevent identical readings on same date from same doc
        sig = (date_str, test_name, num_val, str(unit).strip(), source)
        if sig in seen_obs_signatures:
            continue
        seen_obs_signatures.add(sig)

        timeline.append({
            "date": dt,
            "date_str": date_str,
            "type": "observation",
            "title": test_name,
            "value": float(num_val) if num_val is not None else None,
            "value_text": txt_val,
            "unit": unit or "",
            "source": source,
            "page": obs.get("SOURCE_PAGE") or obs.get("source_page"),
            "snippet": obs.get("SOURCE_SNIPPET") or obs.get("source_snippet", ""),
            "observation_id": obs_id,
            "review_status": status,
        })

    # Add document upload events
    if documents:
        for doc in documents:
            uploaded_at = doc.get("UPLOADED_AT") or doc.get("uploaded_at")
            dt, date_str = parse_safe_date(uploaded_at)
            doc_id = doc.get("DOCUMENT_ID") or doc.get("document_id") or 0
            fname = doc.get("FILE_NAME") or doc.get("file_name", "Unknown Document")

            timeline.append({
                "date": dt,
                "date_str": date_str,
                "type": "document_upload",
                "title": f"Document Ingested: {fname}",
                "value": None,
                "value_text": None,
                "unit": "",
                "source": fname,
                "page": None,
                "snippet": f"Document ID: {doc_id}",
                "observation_id": doc_id,
            })

    # Sort newest first, with secondary sort on observation/document ID for determinism
    timeline.sort(key=lambda x: (x["date"], x.get("observation_id", 0)), reverse=True)
    return timeline


def compute_metric_trend(observations: List[Dict],
                          test_code: str) -> Dict:
    """
    Compute longitudinal trend statistics for a specific metric.
    Rules:
    - Filters to matching test code and non-null numeric values.
    - Rejects comparisons across incompatible units.
    - Sorts chronologically (earliest to latest), with secondary sort on ID.
    - Handles multiple observations on the same date.
    - Handles zero-value baselines without division by zero.
    """
    matching = [
        obs for obs in observations
        if (obs.get("TEST_CODE") or obs.get("test_code", "")).upper() == test_code.upper()
        and (obs.get("VALUE_NUMERIC") if obs.get("VALUE_NUMERIC") is not None else obs.get("value_numeric")) is not None
    ]

    if not matching:
        return {
            "test_code": test_code,
            "count": 0,
            "message": f"No approved observations found for metric '{test_code}'."
        }

    # Deterministic chronological sort: date first, then ID
    def sort_key(x):
        dt, _ = parse_safe_date(x.get("OBSERVED_AT") or x.get("observed_at"))
        obs_id = int(x.get("OBSERVATION_ID") or x.get("observation_id") or 0)
        return (dt, obs_id)

    matching.sort(key=sort_key)

    # Unit compatibility check
    units_seen = set()
    for obs in matching:
        u = obs.get("UNIT") or obs.get("unit")
        if u and str(u).strip():
            units_seen.add(str(u).strip().lower())

    if len(units_seen) > 1:
        raw_units = list(set(str(obs.get("UNIT") or obs.get("unit", "")).strip() for obs in matching))
        return {
            "test_code": test_code,
            "count": len(matching),
            "message": f"Incompatible units detected ({', '.join(raw_units)}). Cannot perform direct trend comparison without conversion.",
            "units": raw_units,
        }

    # Extract clean series
    values = []
    series_points = []
    for obs in matching:
        v = obs.get("VALUE_NUMERIC") if obs.get("VALUE_NUMERIC") is not None else obs.get("value_numeric")
        v_float = float(v)
        values.append(v_float)
        _, date_str = parse_safe_date(obs.get("OBSERVED_AT") or obs.get("observed_at"))
        series_points.append({
            "date": date_str,
            "value": v_float,
            "source": obs.get("FILE_NAME") or obs.get("file_name", ""),
            "page": obs.get("SOURCE_PAGE") or obs.get("source_page"),
            "observation_id": obs.get("OBSERVATION_ID") or obs.get("observation_id"),
        })

    first_obs = matching[0]
    last_obs = matching[-1]
    first_val = values[0]
    last_val = values[-1]

    unit = (first_obs.get("UNIT") or first_obs.get("unit", "")).strip()
    abs_diff = round(last_val - first_val, 4)

    # Safe percentage change
    pct_diff = None
    if first_val != 0.0:
        pct_diff = round((abs_diff / first_val) * 100, 2)

    _, first_date_str = parse_safe_date(first_obs.get("OBSERVED_AT") or first_obs.get("observed_at"))
    _, last_date_str = parse_safe_date(last_obs.get("OBSERVED_AT") or last_obs.get("observed_at"))

    direction = "INCREASING" if abs_diff > 0 else "DECREASING" if abs_diff < 0 else "STABLE"

    return {
        "test_code": test_code,
        "test_name": first_obs.get("TEST_NAME") or first_obs.get("test_name", test_code),
        "count": len(matching),
        "unit": unit,
        "first_value": first_val,
        "first_date": first_date_str,
        "first_source": first_obs.get("FILE_NAME") or first_obs.get("file_name", ""),
        "latest_value": last_val,
        "latest_date": last_date_str,
        "latest_source": last_obs.get("FILE_NAME") or last_obs.get("file_name", ""),
        "absolute_change": abs_diff,
        "percentage_change": pct_diff,
        "direction": direction,
        "is_zero_baseline": first_val == 0.0,
        "min_value": min(values),
        "max_value": max(values),
        "all_values": series_points,
    }


def format_trend_summary(trend: Dict) -> str:
    """Format a trend analysis into a human-readable, evidence-traceable summary."""
    if trend.get("count", 0) == 0:
        return trend.get("message", "No data available.")

    if "message" in trend and "incompatible" in trend.get("message", "").lower():
        return trend["message"]

    name = trend.get("test_name", trend["test_code"])
    unit = trend.get("unit", "")
    count = trend["count"]

    if count == 1:
        return (
            f"Only one approved {name} reading recorded: "
            f"**{trend['first_value']} {unit}** on {trend['first_date']} "
            f"(Source: `{trend['first_source']}`). Longitudinal trend requires at least 2 readings."
        )

    parts = [
        f"**{name} Longitudinal Trend** ({count} approved readings):",
        f"• **Initial:** {trend['first_value']} {unit} on {trend['first_date']} (`{trend['first_source']}`)",
        f"• **Latest:** {trend['latest_value']} {unit} on {trend['latest_date']} (`{trend['latest_source']}`)",
        f"• **Absolute Delta:** {trend['absolute_change']:+.4g} {unit}",
    ]
    if trend.get("percentage_change") is not None:
        parts.append(f"• **Percentage Delta:** {trend['percentage_change']:+.2f}%")
    elif trend.get("is_zero_baseline"):
        parts.append("• **Percentage Delta:** Undefined (baseline measurement was 0.0)")

    if count > 2:
        parts.append(f"• **Recorded Range:** {trend['min_value']} – {trend['max_value']} {unit}")

    return "\n".join(parts)
