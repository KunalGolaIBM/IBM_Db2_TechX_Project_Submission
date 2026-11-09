import streamlit as st
from src.repository import get_repository
from src.agent import run_workflow

st.set_page_config(page_title="MediFlow AI", page_icon="M", layout="wide")
st.title("MediFlow AI")
st.caption("Medicine inventory readiness · IBM Db2 + LangGraph")
if "mediflow_repository" not in st.session_state:
    st.session_state["mediflow_repository"] = get_repository()
repo = st.session_state["mediflow_repository"]
source = "IBM Db2" if repo.__class__.__name__ == "Db2Repository" else "Synthetic demo data"
st.info(f"Data source: {source}. Inventory decision-support prototype; not a clinical system.")
items = repo.list_inventory()
st.subheader("Inventory snapshot")
st.dataframe([{"Medicine": item.medicine_name, "On hand": item.on_hand,
    "Average daily use": item.avg_daily_use, "Days of cover": round(item.on_hand/item.avg_daily_use, 1),
    "Supplier lead (days)": item.supplier_lead_days, "Expiring quantity": item.expiring_quantity}
    for item in items], use_container_width=True, hide_index=True)

if st.button("Run inventory assessment", type="primary"):
    findings, drafts, engine = run_workflow(items, repo)
    st.session_state["findings"] = findings
    st.session_state["drafts"] = drafts
    st.session_state["engine"] = engine

if "findings" in st.session_state:
    st.subheader("Risk assessment")
    st.caption(f"Workflow engine: {st.session_state['engine']}")
    for finding in st.session_state["findings"]:
        if finding.stockout_risk or finding.expiry_risk:
            st.warning(f"**{finding.medicine_name}** · {finding.days_of_cover} days of cover\\n\\n" + " ".join(finding.reasons))
    st.subheader("Draft recommendations")
    for rec in st.session_state["drafts"]:
        with st.container(border=True):
            st.markdown(f"**{rec.medicine_name}**")
            quantity = st.number_input("Suggested units", min_value=0, value=rec.suggested_quantity, key=f"qty-{rec.recommendation_id}")
            for item in rec.rationale:
                st.caption("• " + item)
            st.caption("PENDING REVIEW — no order has been placed.")
            reviewer = st.text_input("Reviewer name", key=f"name-{rec.recommendation_id}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve draft", key=f"yes-{rec.recommendation_id}"):
                    if len(reviewer.strip()) < 2:
                        st.error("Enter reviewer name.")
                    else:
                        repo.review_recommendation(rec.recommendation_id, "APPROVED", reviewer, int(quantity))
                        st.success("Approval recorded in the configured data store.")
            with col2:
                if st.button("Reject draft", key=f"no-{rec.recommendation_id}"):
                    if len(reviewer.strip()) < 2:
                        st.error("Enter reviewer name.")
                    else:
                        repo.review_recommendation(rec.recommendation_id, "REJECTED", reviewer, int(quantity))
                        st.info("Draft rejection recorded in the configured data store.")
