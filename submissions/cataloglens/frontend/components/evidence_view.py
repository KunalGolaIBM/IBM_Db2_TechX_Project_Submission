"""
Evidence Ledger Renderer.
Visualizes traceable evidence backing every claim, distinguishing
verified facts from AI hypotheses with progress meters and source citations.
"""
from typing import Any, Dict, List
import streamlit as st


def render_evidence_ledger(evidence_claims: List[Dict[str, Any]]):
    """Renders structured evidence claims as professional enterprise cards."""
    if not evidence_claims:
        st.info("No evidence records available.")
        return

    for idx, claim in enumerate(evidence_claims):
        status = claim.get("status", "ai_hypothesis").lower()
        conf = float(claim.get("confidence", 0.85))
        claim_text = claim.get("claim", "")
        evidence_items = claim.get("evidence", [])
        discrepancies = claim.get("discrepancies", [])
        verified = claim.get("verified_by_engine", False)

        # Status badge styling
        if status == "verified_fact":
            badge_html = "<span style='background-color:#198038; color:white; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:600;'>VERIFIED FACT</span>"
        elif status == "metadata_supported":
            badge_html = "<span style='background-color:#0043CE; color:white; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:600;'>METADATA SUPPORTED</span>"
        elif status == "ai_hypothesis":
            badge_html = "<span style='background-color:#BA8500; color:white; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:600;'>AI HYPOTHESIS</span>"
        else:
            badge_html = "<span style='background-color:#DA1E28; color:white; padding:3px 8px; border-radius:4px; font-size:12px; font-weight:600;'>UNVERIFIED ASSUMPTION</span>"

        with st.container():
            st.markdown(
                f"""
                <div style="border: 1px solid #393939; border-left: 5px solid {'#198038' if verified else '#BA8500'}; padding: 12px 16px; border-radius: 6px; margin-bottom: 12px; background: rgba(255,255,255,0.02);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div>{badge_html}</div>
                        <div style="font-size: 13px; color: #8D8D8D;">Confidence: <b>{conf*100:.0f}%</b></div>
                    </div>
                    <div style="font-size: 15px; font-weight: 500; margin-bottom: 8px;">
                        {claim_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Details expander for citations
            with st.expander(f"Inspect Citations & Catalog Observations ({len(evidence_items)} sources)", expanded=False):
                if discrepancies:
                    for d in discrepancies:
                        st.error(f"Engine Warning: {d}")

                for e in evidence_items:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        st.markdown(f"**Source:** `{e.get('source')}`")
                        st.caption(f"Type: {e.get('type')}")
                    with col2:
                        st.markdown(f"*{e.get('observation')}*")
                    st.divider()
