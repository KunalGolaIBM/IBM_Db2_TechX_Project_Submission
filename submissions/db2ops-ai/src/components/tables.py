"""Reusable result table and CSV download controls."""
import streamlit as st

def result_table(df, key: str):
    if df.empty:
        st.info("No matching records were returned.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8-sig"), file_name=f"{key}.csv", mime="text/csv", key=f"csv_{key}")
