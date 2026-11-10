import streamlit as st
import pandas as pd
from repository import Repository
from agents import investigate_shipment

st.set_page_config(page_title="SupplyChain Sentinel", page_icon="🛰️", layout="wide")
st.markdown("""
<style>
.stApp {background: #0b1220; color: #e8eef7;}
[data-testid="stMetric"] {background:#142238; padding:16px; border:1px solid #263b56; border-radius:12px;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-color:#263b56;}
h1,h2,h3 {letter-spacing:-0.03em;}
.small-muted {color:#9fb1c8;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_repo():
    return Repository()

repo=get_repo()
st.sidebar.title("🛰️ SupplyChain Sentinel")
st.sidebar.caption("IBM Db2 • LangGraph • Evidence-led decisions")
if repo.mode == "IBM Db2":
    st.sidebar.success("IBM Db2 connected")
else:
    st.sidebar.warning("SQLite demo mode — configure Db2 for judging")
st.sidebar.markdown("---")
st.sidebar.markdown("**Workflow**")
st.sidebar.markdown("1. Monitor signal\n2. Investigate Db2 records\n3. Assess impact\n4. Plan mitigations\n5. Verify evidence\n6. Human approval")

st.title("SupplyChain Sentinel")
st.caption("Agentic control tower for manufacturing supply disruption detection and explainable recovery planning")

col1,col2,col3=st.columns(3)
col1.metric("Tracked disruption", "SHIP-1008", "Delayed shipment")
col2.metric("Component criticality", "CRITICAL", "Motor controller")
col3.metric("Data source", repo.mode, "Operational records")

st.markdown("## Investigate a disruption")
shipment_id=st.selectbox("Shipment event",["SHIP-1008","SHIP-1009"],index=0)
if st.button("▶ Run agent investigation", type="primary", use_container_width=True):
    try:
        with st.spinner("LangGraph agents are investigating operational records..."):
            result=investigate_shipment(repo,shipment_id)
        st.session_state["sentinel_result"]=result
        st.session_state["sentinel_shipment"]=shipment_id
        st.success("Investigation complete. Review evidence before approving any recommendation.")
    except Exception as exc:
        st.error(f"Investigation failed: {exc}")

result=st.session_state.get("sentinel_result")
if result:
    c=result["context"]; impact=result["impact"]
    st.markdown("---")
    st.markdown(f"## Risk case · {result['case_id']}")
    severity=result["severity"]
    st.error(f"{severity} RISK — {c['component_name']} / {c['shipment_id']}")
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Inventory runway",f"{impact['inventory_runway_days']} days")
    m2.metric("Shipment delay",f"{impact['delay_days']} days")
    m3.metric("Exposed production orders",impact["exposed_order_count"])
    m4.metric("Available inventory",f"{impact['available_inventory']} units")

    left,right=st.columns([1.15,0.85])
    with left:
        st.markdown("### Retrieved Db2 evidence")
        evidence=pd.DataFrame([
            ["Shipment",c["shipment_id"],c["event_status"]],
            ["Purchase order",c["po_id"],f"{c['order_qty']} units"],
            ["Supplier",c["supplier_name"],f"{c['on_time_rate']}% on-time"],
            ["Component",c["component_name"],c["criticality"]],
            ["Inventory",c["component_id"],f"{c['on_hand_qty']} on hand / {c['reserved_qty']} reserved"],
            ["Quality",c["component_id"],c["quality_status"]],
            ["Original ETA",c["shipment_id"],str(c["original_eta"])],
            ["Revised ETA",c["shipment_id"],str(c["revised_eta"])]
        ],columns=["Entity","Record ID","Retrieved value"])
        st.dataframe(evidence,use_container_width=True,hide_index=True)
        st.markdown("### Production orders in scope")
        st.dataframe(pd.DataFrame(impact["exposed_orders"]),use_container_width=True,hide_index=True)
    with right:
        st.markdown("### Agent verification")
        for name,passed in result["verification"]["checks"].items():
            st.write(("✅ " if passed else "⚠️ ")+name.replace("_"," ").title())
        st.caption(result["verification"]["note"])
        st.markdown("### Ranked mitigation options")
        option_labels=[f"{i+1}. {o['name']}" for i,o in enumerate(result["options"])]
        selected=st.radio("Choose an option to submit for human approval",option_labels)
        selected_idx=option_labels.index(selected)
        st.info(result["options"][selected_idx]["rationale"])
        approver=st.text_input("Approver name",placeholder="Planner / reviewer")
        rationale=st.text_area("Approval rationale",placeholder="Why is this option appropriate?")
        if st.button("Record human approval",disabled=not approver.strip(),use_container_width=True):
            rid=f"{result['case_id']}-R{selected_idx+1}"
            try:
                audit=repo.record_approval(result["case_id"],rid,"APPROVED",approver.strip(),rationale.strip())
                st.success(f"Approval audit recorded: {audit}")
            except Exception as exc:
                st.error(f"Could not record approval: {exc}")

st.markdown("---")
st.markdown("### Recent risk cases")
try:
    recent=repo.list_recent_cases()
    if recent:
        st.dataframe(pd.DataFrame(recent),use_container_width=True,hide_index=True)
    else:
        st.caption("No persisted cases yet. Run an investigation to create the first case.")
except Exception as exc:
    st.caption(f"Case history unavailable: {exc}")

st.caption("Decision-support prototype • Synthetic sample data • Human approval required for operational action")
