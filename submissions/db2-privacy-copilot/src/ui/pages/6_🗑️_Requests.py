"""Create rights requests and review human approvals."""

import os
import secrets
import sys

import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from api_client import call_api  # noqa: E402


st.set_page_config(page_title="Rights requests", page_icon="🗑️", layout="wide")

if not st.session_state.get("authenticated"):
    st.warning("Please log in first.")
    if st.button("Go to login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

role = st.session_state.get("user_role", "VIEWER")
st.title("Rights requests")
st.caption("Create a reviewable plan, then let an authorized DPO approve execution.")

create_tab, approve_tab = st.tabs(["Create request", "Review approvals"])

with create_tab:
    st.subheader("Request erasure review")
    if role == "VIEWER":
        st.info("Analyst or DPO access is required to submit a request.")
    else:
        with st.form("create_erasure_request"):
            subject_id = st.number_input("Patient ID", min_value=1, step=1)
            submitted = st.form_submit_button(
                "Create request for DPO review", type="primary"
            )

        if submitted:
            try:
                result = call_api(
                    "POST",
                    "/requests",
                    role,
                    {"subject_id": int(subject_id)},
                )
                st.session_state["last_request_plan"] = result
                st.success("Request created. It is now waiting for DPO approval.")
            except RuntimeError as error:
                st.error(str(error))

        result = st.session_state.get("last_request_plan")
        if result:
            st.markdown("#### Dry-run plan")
            metrics = st.columns(3)
            metrics[0].metric("Plan steps", result.get("total_steps", 0))
            metrics[1].metric("Estimated rows", result.get("total_rows", 0))
            metrics[2].metric(
                "Retention review",
                "Needed" if result.get("has_unverified") else "Verified",
            )
            for index, step in enumerate(result.get("steps", []), start=1):
                with st.expander(
                    f"{index}. {step['action']} {step['table']} "
                    f"({step['est_rows']} estimated rows)"
                ):
                    st.write(step.get("reason", ""))
                    st.caption(
                        "Retention rule: "
                        + ("verified" if step.get("rule_verified") else "unverified")
                    )
            st.caption(f"Plan hash: `{result.get('plan_hash', 'unavailable')}`")

with approve_tab:
    st.subheader("Pending DPO approvals")
    if role != "DPO":
        st.info("Pending requests can be reviewed here. DPO access is required to approve.")

    try:
        pending = call_api("GET", "/requests?status_filter=PENDING_APPROVAL", role)
        requests = pending.get("requests", [])
        if not requests:
            st.success("There are no requests waiting for approval.")

        for request in requests:
            request_id = request["id"]
            details = call_api("GET", f"/requests/{request_id}", role)
            with st.container(border=True):
                heading = st.columns([2, 1, 1])
                heading[0].markdown(f"**Request #{request_id}** · {details['type']}")
                heading[1].write(f"Subject ID: `{details['plan']['subject_id']}`")
                heading[2].write(f"Due: {details['due_at']}")

                plan = details.get("plan") or {}
                steps = plan.get("steps", [])
                st.caption(f"Plan hash: `{details.get('plan_hash', '')}`")
                if plan.get("simulation", {}).get("has_unverified"):
                    st.warning("This plan includes unverified retention rules.")
                for step in steps:
                    st.write(
                        f"**{step['action']} {step['table']}** · "
                        f"{step['est_rows']} estimated rows · {step['reason']}"
                    )

                if role == "DPO":
                    token_key = f"approval_id_{request_id}"
                    st.session_state.setdefault(token_key, secrets.token_hex(16))
                    with st.form(f"approve_request_{request_id}"):
                        approval_id = st.text_input(
                            "Approval reference",
                            value=st.session_state[token_key],
                            help="A unique reference is recorded with this approval.",
                        )
                        confirmed = st.checkbox(
                            "I reviewed this plan and approve the listed actions."
                        )
                        approve = st.form_submit_button(
                            "Approve and execute", type="primary"
                        )

                    if approve:
                        if not confirmed:
                            st.error("Confirm that you reviewed the plan before approving.")
                        elif not approval_id.strip():
                            st.error("Enter an approval reference.")
                        else:
                            try:
                                outcome = call_api(
                                    "POST",
                                    f"/requests/{request_id}/approve",
                                    role,
                                    {"approval_id": approval_id.strip()},
                                )
                                st.success(
                                    f"Request completed for subject "
                                    f"{outcome['subject_id']}. The action was audited."
                                )
                                st.rerun()
                            except RuntimeError as error:
                                st.error(str(error))
    except RuntimeError as error:
        st.error(str(error))
