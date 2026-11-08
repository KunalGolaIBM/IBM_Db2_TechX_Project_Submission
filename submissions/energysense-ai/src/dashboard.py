"""Streamlit dashboard for appliance telemetry, anomaly history and AI assistance."""
from __future__ import annotations

import os
import requests
import streamlit as st

API = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = 6

st.set_page_config(page_title="EnergySense AI", page_icon="⚡", layout="wide")
st.title("⚡ EnergySense AI")
st.caption("Appliance runtime intelligence · IBM Db2 · Explainable anomaly monitoring")
st.info(
    "AI insights are advisory only. The local ESP32 threshold path remains the only relay-control path. "
    "Apparent power is shown in VA; this dashboard does not claim billing-grade kWh."
)

with st.sidebar:
    st.header("Monitor")
    appliance = st.text_input("Appliance ID", value="pump-01").strip()
    st.caption(f"API: `{API}`")
    refresh = st.button("Refresh data", type="primary", use_container_width=True)
    st.divider()
    st.caption("Sources are tagged as `wokwi_simulated`, `synthetic` or `esp32` so demo data is not confused with physical readings.")

if refresh:
    st.rerun()

if not appliance:
    st.warning("Enter an appliance ID to view its monitoring history.")
    st.stop()

try:
    health_response = requests.get(f"{API}/health", timeout=TIMEOUT)
    health_response.raise_for_status()
    health = health_response.json()
    telemetry_response = requests.get(
        f"{API}/api/v1/telemetry/{appliance}", params={"limit": 300}, timeout=TIMEOUT
    )
    telemetry_response.raise_for_status()
    event_response = requests.get(
        f"{API}/api/v1/events", params={"appliance_id": appliance, "limit": 100}, timeout=TIMEOUT
    )
    event_response.raise_for_status()
    readings = telemetry_response.json().get("items", [])
    events = event_response.json().get("items", [])
except requests.RequestException as exc:
    st.error(f"Cannot reach the API at {API}. Start it with `uvicorn src.api:app --reload`. Details: {exc}")
    st.stop()
except ValueError as exc:
    st.error(f"The API returned an invalid JSON response: {exc}")
    st.stop()

latest = readings[-1] if readings else {}
source = latest.get("source", "no data")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Database backend", str(health.get("database_backend", "unknown")).upper())
col2.metric("Stored readings", health.get("telemetry_count", 0))
col3.metric("Anomaly events", len(events))
col4.metric("Latest source", source)

st.divider()
st.subheader(f"Appliance overview · {appliance}")
if readings:
    a, b, c, d = st.columns(4)
    a.metric("RMS voltage", f"{latest.get('vrms_v') or 0:.1f} V")
    b.metric("RMS current", f"{latest.get('irms_a') or 0:.3f} A")
    c.metric("Apparent power", f"{latest.get('apparent_power_va') or 0:.1f} VA")
    runtime_hours = float(latest.get("runtime_s") or 0) / 3600.0
    d.metric("Reported runtime", f"{runtime_hours:.2f} h")

    if latest.get("recorded_at"):
        st.caption(f"Latest recorded at: {latest['recorded_at']} · Relay state reported by device: {latest.get('relay_state', 'UNKNOWN')}")

    # Trend inputs preserve the source readings and do not fabricate missing values.
    for field, label, unit in (
        ("irms_a", "RMS current", "A"),
        ("vrms_v", "RMS voltage", "V"),
        ("temperature_c", "Temperature", "°C"),
        ("vibration_rms", "Vibration RMS", ""),
    ):
        series = [row.get(field) for row in readings]
        if any(value is not None for value in series):
            st.markdown(f"**{label} trend** ({unit})" if unit else f"**{label} trend**")
            st.line_chart({label: series}, height=180)
else:
    st.warning("No readings yet. Use the demo seeder or post a telemetry sample to the API.")

st.divider()
st.subheader("Explainable anomaly history")
if events:
    st.dataframe(events, use_container_width=True, hide_index=True)
else:
    st.success("No anomaly events have been persisted for this appliance yet.")

st.divider()
st.subheader("Ask the EnergySense assistant")
st.caption("Optional LangChain tool-calling mode. Configure OPENAI_API_KEY and Db2 vector search before using the assistant.")
question = st.text_input(
    "Question",
    placeholder="Why is pump-01 drawing more current than its normal pattern?",
    key="assistant_question",
)
if st.button("Ask assistant", disabled=not question.strip()):
    try:
        response = requests.post(
            f"{API}/api/v1/assistant", json={"question": question.strip()}, timeout=45
        )
        response.raise_for_status()
        st.markdown(response.json().get("answer", "No answer returned."))
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = response.json().get("detail", "")
        except Exception:
            pass
        st.error(f"Assistant unavailable: {detail or exc}")
    except requests.RequestException as exc:
        st.error(f"Assistant request failed: {exc}")
