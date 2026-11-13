"""Khata AI - web UI (optional).
Install once:   pip install streamlit pandas
Run:            streamlit run ui.py
"""
import pandas as pd
import streamlit as st

from db import (
    add_entry,
    get_history,
    get_pending,
    get_total_outstanding,
    load_demo_data,
    setup_schema,
)
from llm import ai_available, parse_entry, write_reminder

st.set_page_config(page_title="Khata AI", page_icon="📒", layout="centered")
st.title("📒 Khata AI")
st.caption("Dukaan ka smart udhaar khata  •  IBM Db2 + LangChain")

if "ready" not in st.session_state:
    try:
        setup_schema()
        st.session_state.ready = True
    except Exception as err:  # noqa: BLE001
        st.error(f"Db2 se connect nahi ho paya: {err}")
        st.stop()

st.sidebar.write("AI mode:", "🟢 Gemini" if ai_available() else "🟠 offline parser")
if st.sidebar.button("Demo data load karo"):
    st.sidebar.success(f"{load_demo_data()} entries add ho gayi")

tab_add, tab_pending, tab_history = st.tabs(["➕ Nayi entry", "⏳ Pending", "🔎 History"])

with tab_add:
    text = st.text_input("Bolo ya likho", placeholder="Sharma ji ne 200 ka udhaar liya, doodh aur bread")
    if st.button("Samjho"):
        try:
            entry, source = parse_entry(text)
            st.session_state.pending_entry = (entry, source)
        except Exception as err:  # noqa: BLE001
            st.session_state.pop("pending_entry", None)
            st.error(f"Samajh nahi aaya: {err}")

    if "pending_entry" in st.session_state:
        entry, source = st.session_state.pending_entry
        st.info(
            f"**{entry.name}**  |  {entry.entry_type}  |  Rs {entry.amount:.2f}  |  "
            f"{entry.note or '-'}   \n_Samjha by: {source}_"
        )
        if st.button("✅ Save karo"):
            add_entry(entry.name, entry.amount, entry.entry_type, entry.note)
            st.session_state.pop("pending_entry")
            st.success("Saved!")

with tab_pending:
    rows = get_pending()
    if not rows:
        st.success("Koi udhaar baaki nahi 🎉")
    else:
        st.metric("Total baaki", f"Rs {get_total_outstanding():,.2f}")
        df = pd.DataFrame(rows, columns=["Naam", "Baaki (Rs)", "Din purana"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        who = st.selectbox("Reminder kisko bhejna hai?", [r[0] for r in rows])
        if st.button("📲 Reminder likho"):
            name, balance, days = next(r for r in rows if r[0] == who)
            st.code(write_reminder(name, balance, days), language=None)

with tab_history:
    q = st.text_input("Customer ka naam")
    if q:
        hist = get_history(q)
        if hist:
            st.dataframe(
                pd.DataFrame(hist, columns=["Naam", "Date", "Type", "Amount", "Note"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("Koi entry nahi mili.")
