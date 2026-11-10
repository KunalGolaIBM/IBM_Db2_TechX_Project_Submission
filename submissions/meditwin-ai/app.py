"""
MediTwin AI — Complete Agentic Healthcare Record Intelligence Platform
IBM Db2Hack 2026 Submission
Genuinely connected to IBM Db2 Community Edition, LangChain, LangGraph, and Google Gemini.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Load settings
from config.settings import app_settings, DISCLAIMER, gemini_settings
from db.connection import get_db2_connection, test_connection
from db.repository import Db2Repository
from db.seed_demo_data import seed_patients
from ingestion.pdf_parser import parse_document, validate_file
from ingestion.validation import ExtractedObservation, ReviewDecision
from graph.workflow import run_upload_workflow, run_question_workflow
from services.timeline_service import build_patient_timeline, compute_metric_trend, format_trend_summary
from services.retrieval_service import RetrievalService
from services.answer_service import AnswerService
from services.audit_service import AuditService

# Page configuration
st.set_page_config(
    page_title="MediTwin AI — Healthcare Record Intelligence",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for medical technology styling
st.markdown("""
<style>
    :root {
        --primary: #0A2540;
        --secondary: #0066CC;
        --accent: #00A3A6;
        --background: #F8FAFC;
        --card-bg: #FFFFFF;
        --text-primary: #1A202C;
        --text-secondary: #4A5568;
        --border: #E2E8F0;
        --success: #38A169;
        --warning: #DD6B20;
        --danger: #E53E3E;
    }

    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    h1, h2, h3 {
        color: #0A2540 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .metric-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #0066CC;
        margin: 0.3rem 0;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #4A5568;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .evidence-card {
        background: white;
        border-left: 4px solid #0066CC;
        border: 1px solid #E2E8F0;
        border-left-width: 4px;
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }

    .badge-approved {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-pending {
        background-color: #FEF08A;
        color: #713F12;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-rejected {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .disclaimer-banner {
        background: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #92400E;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)


# Helper singletons
def get_repo() -> Db2Repository:
    conn = get_db2_connection()
    return Db2Repository(conn)


def get_audit() -> AuditService:
    return AuditService(get_repo())


def get_answer_svc() -> AnswerService:
    return AnswerService(get_repo(), api_key=gemini_settings.api_key)


# Initialize connection on start
if "db_connected" not in st.session_state:
    conn = get_db2_connection()
    st.session_state.db_connected = conn.connect()
    if st.session_state.db_connected:
        schema_path = os.path.join(os.path.dirname(__file__), "db", "schema.sql")
        conn.initialize_schema(schema_path)
        seed_patients(Db2Repository(conn))


# ================================================================
# SIDEBAR
# ================================================================
with st.sidebar:
    st.markdown("### 🧬 MediTwin AI")
    st.markdown("**Healthcare Record Intelligence**")
    st.caption("IBM Db2Hack 2026 Submission")

    st.markdown("---")

    # Connection Status
    conn = get_db2_connection()
    if conn.is_connected:
        st.success("🟢 IBM Db2: Connected")
        info = conn.get_server_info()
        st.caption(f"Server: {info.get('dbms_name', 'Db2')} {info.get('dbms_ver', '')}")
    else:
        st.error("🔴 IBM Db2: Disconnected")
        st.caption("Local port 50000 unreachable. Using offline state.")
        if st.button("Retry Db2 Connection"):
            st.session_state.db_connected = conn.connect()
            st.rerun()

    # Gemini Status
    if gemini_settings.api_key or os.environ.get("GEMINI_API_KEY"):
        st.success("🟢 Gemini API: Configured")
    else:
        st.warning("🟡 Gemini API: Not Configured")
        api_key_input = st.text_input("Enter Gemini API Key", type="password")
        if api_key_input:
            gemini_settings.api_key = api_key_input
            os.environ["GEMINI_API_KEY"] = api_key_input
            st.rerun()

    st.markdown("---")

    # Patient Selector
    repo = get_repo()
    try:
        patients = repo.list_patients() if conn.is_connected else []
    except Exception:
        patients = []

    if patients:
        patient_options = {p["PATIENT_ID"]: f"{p['DISPLAY_NAME']} ({p['DEMO_CODE']})"
                           for p in patients}
        selected_pid = st.selectbox(
            "Selected Patient",
            options=list(patient_options.keys()),
            format_func=lambda x: patient_options[x],
            key="current_patient_id",
        )
    else:
        st.info("No patients found. Connect Db2 and seed demo data.")
        selected_pid = 1  # Fallback demo patient ID for offline review

    st.markdown("---")

    # Navigation
    page = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "👤 Patient Workspace",
            "📄 Document Upload",
            "✅ Human Review",
            "💬 Ask MediTwin",
            "📋 Audit History",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.75rem; color:#718096; text-align:center;'>"
        "Synthetic Data Demonstration<br>Not a Medical Device"
        "</div>",
        unsafe_allow_html=True,
    )


# ================================================================
# DISCLAIMER BANNER
# ================================================================
st.markdown(f'<div class="disclaimer-banner">⚠️ {DISCLAIMER}</div>', unsafe_allow_html=True)


# ================================================================
# PAGE 1: DASHBOARD
# ================================================================
if page == "📊 Dashboard":
    st.markdown("## System Dashboard")
    st.caption("Overview of the MediTwin AI clinical record intelligence platform")

    repo = get_repo()
    stats = repo.get_dashboard_stats() if conn.is_connected else {
        "total_patients": 3,
        "total_documents": 3,
        "total_observations": 18,
        "pending_reviews": 0,
    }

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Synthetic Patients</div>'
            f'<div class="metric-value">{stats.get("total_patients", 0)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Documents Ingested</div>'
            f'<div class="metric-value">{stats.get("total_documents", 0)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Approved Observations</div>'
            f'<div class="metric-value">{stats.get("total_observations", 0)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c4:
        pending = stats.get("pending_reviews", 0)
        color = "#DD6B20" if pending > 0 else "#38A169"
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Pending Reviews</div>'
            f'<div class="metric-value" style="color:{color}">{pending}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.markdown("### System Architecture Status")
        arch_data = {
            "Component": ["IBM Db2", "LangChain", "LangGraph", "Gemini API", "PyMuPDF"],
            "Role": ["System of Record", "Extraction & Generation", "Workflow Orchestration", "Language Model", "PDF Extraction"],
            "Status": [
                "Connected" if conn.is_connected else "Offline / Standby",
                "Available",
                "Available (Compiled)",
                "Configured" if (gemini_settings.api_key or os.environ.get("GEMINI_API_KEY")) else "Needs Key",
                "Available",
            ],
        }
        st.dataframe(pd.DataFrame(arch_data), use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("### Quick Actions")
        if st.button("🌱 Seed Demo Data", use_container_width=True):
            if conn.is_connected:
                seed_patients(repo)
                st.success("Demo data seeded successfully.")
                st.rerun()
            else:
                st.warning("Db2 not connected. Please start Db2 server first.")

        if st.button("🔄 Refresh Statistics", use_container_width=True):
            st.rerun()

    st.markdown("---")
    st.markdown("### Recent System Activity")
    try:
        activity = repo.get_audit_log(limit=10) if conn.is_connected else []
        if activity:
            activity_data = []
            for a in activity:
                activity_data.append({
                    "Time": str(a.get("LOGGED_AT", ""))[:19],
                    "Action": a.get("ACTION", ""),
                    "Entity": f"{a.get('ENTITY_TYPE', '')} #{a.get('ENTITY_ID', '')}",
                    "Actor": a.get("ACTOR_ID", ""),
                })
            st.dataframe(pd.DataFrame(activity_data), use_container_width=True, hide_index=True)
        else:
            st.info("No activity recorded yet.")
    except Exception as e:
        st.info("Activity log unavailable.")


# ================================================================
# PAGE 2: PATIENT WORKSPACE
# ================================================================
elif page == "👤 Patient Workspace":
    st.markdown("## Patient Longitudinal Workspace")

    repo = get_repo()
    patient = repo.get_patient(selected_pid) if conn.is_connected else {
        "DISPLAY_NAME": "Synthetic Patient Alpha",
        "DEMO_CODE": "DEMO-001",
        "BIRTH_YEAR": 1985
    }

    if patient:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Name:** {patient.get('DISPLAY_NAME', '')}")
        with c2:
            st.markdown(f"**Code:** `{patient.get('DEMO_CODE', '')}`")
        with c3:
            by = patient.get('BIRTH_YEAR', '')
            st.markdown(f"**Birth Year:** {by if by else 'Not recorded'}")

        st.markdown("---")

        approved_obs = repo.get_approved_observations(selected_pid) if conn.is_connected else []

        if not approved_obs:
            st.info("No approved observations found for this patient. "
                    "Upload and approve medical documents to build the patient timeline.")
        else:
            distinct_tests = repo.get_distinct_test_codes(selected_pid)
            test_codes = [t.get("TEST_CODE") for t in distinct_tests if t.get("TEST_CODE")]

            if test_codes:
                st.markdown("### Metric Trend Analysis")
                selected_metric = st.selectbox("Select Metric to Analyze", options=test_codes, index=0)
                trend = compute_metric_trend(approved_obs, selected_metric)

                if trend.get("count", 0) > 0:
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    with sc1:
                        st.metric("First Value", f"{trend['first_value']} {trend['unit']}", trend['first_date'])
                    with sc2:
                        st.metric("Latest Value", f"{trend['latest_value']} {trend['unit']}", trend['latest_date'])
                    with sc3:
                        chg = trend['absolute_change']
                        st.metric("Absolute Change", f"{chg:+.4g} {trend['unit']}")
                    with sc4:
                        pct = trend['percentage_change']
                        st.metric("Percentage Change", f"{pct:+.2f}%" if pct is not None else "N/A")

                    chart_data = pd.DataFrame(trend["all_values"])
                    fig = px.line(
                        chart_data,
                        x="date",
                        y="value",
                        markers=True,
                        title=f"{trend.get('test_name', selected_metric)} Over Time",
                        labels={"date": "Observation Date", "value": f"Value ({trend['unit']})"},
                    )
                    fig.update_traces(line_color="#0066CC", marker=dict(size=8, color="#0A2540"))
                    fig.update_layout(
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        xaxis=dict(showgrid=True, gridcolor="#E2E8F0"),
                        yaxis=dict(showgrid=True, gridcolor="#E2E8F0"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.markdown(f"**Evidence Summary:**\n{format_trend_summary(trend)}")

            st.markdown("---")
            st.markdown("### Chronological Observation History")
            docs = repo.list_documents(selected_pid)
            timeline = build_patient_timeline(approved_obs, docs)

            timeline_data = []
            for item in timeline:
                if item["type"] == "observation":
                    timeline_data.append({
                        "Date": item["date_str"],
                        "Test Name": item["title"],
                        "Value": f"{item['value']} {item['unit']}" if item['value'] is not None else item.get('value_text', ''),
                        "Source Document": item["source"],
                        "Page": item.get("page", ""),
                        "Source Snippet": item.get("snippet", "")[:70] + "..." if item.get("snippet") else "",
                    })

            if timeline_data:
                st.dataframe(pd.DataFrame(timeline_data), use_container_width=True, hide_index=True)


# ================================================================
# PAGE 3: DOCUMENT UPLOAD
# ================================================================
elif page == "📄 Document Upload":
    st.markdown("## Ingest Synthetic Medical Document")
    st.caption("Pipeline A: Upload → Validate → SHA-256 Check → LangGraph Workflow → Review Gate")

    repo = get_repo()
    patient = repo.get_patient(selected_pid) if conn.is_connected else {
        "DISPLAY_NAME": "Synthetic Patient Alpha",
        "DEMO_CODE": "DEMO-001"
    }
    st.info(f"Target Patient: **{patient.get('DISPLAY_NAME')}** (`{patient.get('DEMO_CODE')}`)")

    # Upload options
    uploaded_file = st.file_uploader(
        "Choose a synthetic medical report (PDF or TXT)",
        type=["pdf", "txt"],
        help="Maximum file size: 10 MB. Synthetic documents only.",
    )

    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data", "synthetic_reports")
    sample_files = [f for f in os.listdir(sample_dir) if f.endswith(".pdf")] if os.path.exists(sample_dir) else []

    if sample_files:
        st.markdown("---")
        st.markdown("**Or load a pre-generated synthetic sample report:**")
        selected_sample = st.selectbox("Sample Reports", options=sample_files)
        load_sample = st.button("Load Selected Sample Report")
    else:
        load_sample = False
        selected_sample = None

    # Resolve file bytes and name
    file_bytes = None
    file_name = None

    if uploaded_file:
        file_bytes = uploaded_file.read()
        file_name = uploaded_file.name
    elif load_sample and selected_sample:
        sample_path = os.path.join(sample_dir, selected_sample)
        with open(sample_path, "rb") as f:
            file_bytes = f.read()
        file_name = selected_sample

    if file_bytes and file_name:
        st.markdown("---")
        st.markdown(f"### Selected Document: `{file_name}`")

        # Step 1: File Validation
        is_valid, err = validate_file(file_name, file_bytes)
        if not is_valid:
            st.error(f"Validation failed: {err}")
        else:
            parsed_doc = parse_document(file_name, file_bytes)
            st.success(f"✅ Validated: {parsed_doc.total_pages} page(s) | SHA-256: `{parsed_doc.source_hash[:16]}...`")

            # Check duplicate in Db2
            is_duplicate = False
            existing_doc_id = None
            if conn.is_connected:
                existing_doc = repo.get_document_by_hash(selected_pid, parsed_doc.source_hash)
                if existing_doc:
                    is_duplicate = True
                    existing_doc_id = existing_doc["DOCUMENT_ID"]
                    st.warning(f"⚠️ Document already registered in Db2 (ID: {existing_doc_id}, Status: {existing_doc.get('PARSE_STATUS')}).")

            # Step tabs for pages
            page_tabs = st.tabs([f"Page {p.page_number}" for p in parsed_doc.pages])
            for i, tab in enumerate(page_tabs):
                with tab:
                    st.text_area(f"Page {i+1} Text", value=parsed_doc.pages[i].text, height=180, disabled=True)

            # Step 2: Ingest into Db2 Button
            st.markdown("---")
            c_btn1, c_btn2 = st.columns(2)

            with c_btn1:
                ingest_btn = st.button("📥 Step 1: Register Document in Db2", type="secondary")
                if ingest_btn:
                    if not conn.is_connected:
                        st.error("IBM Db2 is offline. Cannot register document.")
                    elif is_duplicate:
                        st.info(f"Using already registered document ID: {existing_doc_id}")
                        st.session_state["active_doc_id"] = existing_doc_id
                    else:
                        try:
                            doc_id = repo.create_document(
                                patient_id=selected_pid,
                                file_name=file_name,
                                document_type="LAB_REPORT",
                                extracted_text=parsed_doc.full_text,
                                source_hash=parsed_doc.source_hash,
                            )
                            repo.update_document_status(doc_id, "PARSED")
                            get_audit().log_upload(doc_id, file_name, selected_pid)
                            st.session_state["active_doc_id"] = doc_id
                            st.success(f"✅ Registered in Db2 (Document ID: {doc_id})")
                        except Exception as e:
                            st.error(f"Error registering document: {e}")

            with c_btn2:
                extract_btn = st.button("🚀 Step 2: Run LangGraph Extraction Workflow", type="primary")
                if extract_btn:
                    target_doc_id = st.session_state.get("active_doc_id", existing_doc_id)
                    api_key = gemini_settings.api_key or os.environ.get("GEMINI_API_KEY", "")

                    if not api_key:
                        st.error("Gemini API key is required. Please set it in the sidebar.")
                    else:
                        with st.spinner("Executing compiled LangGraph Ingestion StateGraph..."):
                            workflow_result = run_upload_workflow(
                                file_name=file_name,
                                file_bytes=file_bytes,
                                patient_id=selected_pid,
                                repo=repo if conn.is_connected else None,
                                document_id=target_doc_id,
                                gemini_api_key=api_key,
                                gemini_model=gemini_settings.model,
                            )

                        extracted = workflow_result.get("extracted_observations", [])
                        st.success(f"✅ LangGraph completed! Nodes executed: `{' → '.join(workflow_result.get('completed_nodes', []))}`")
                        st.info(f"Extracted {len(extracted)} structured observations.")

                        if extracted:
                            st.dataframe(pd.DataFrame(extracted), use_container_width=True)

                            # Audit logging and UI notification from LangGraph persistence node
                            saved_count = workflow_result.get("observations_saved", 0)
                            if conn.is_connected and target_doc_id and saved_count > 0:
                                get_audit().log_extraction(target_doc_id, saved_count)
                                st.success(f"✅ LangGraph `persist_to_db2` stored {saved_count} observations with review_status='PENDING'. Go to **Human Review**.")
                            elif not conn.is_connected:
                                st.info("Extracted observations verified in memory. Connect Db2 to persist records.")


# ================================================================
# PAGE 4: HUMAN REVIEW
# ================================================================
elif page == "✅ Human Review":
    st.markdown("## Human Verification Gate")
    st.caption("Mandatory review: Extracted observations default to PENDING. "
               "Only APPROVED observations enter the trusted timeline.")

    repo = get_repo()
    audit = get_audit()

    if not conn.is_connected:
        st.warning("IBM Db2 is currently offline. Human review requires an active database connection.")
    else:
        pending_obs = repo.get_pending_observations(selected_pid)

        if not pending_obs:
            st.success("🎉 No observations pending review for this patient.")
        else:
            st.info(f"**{len(pending_obs)}** observation(s) awaiting your verification.")

            for i, obs in enumerate(pending_obs):
                obs_id = obs.get("OBSERVATION_ID")
                curr_val = obs.get("VALUE_NUMERIC")
                curr_unit = obs.get("UNIT") or ""
                curr_date = str(obs.get("OBSERVED_AT") or "")
                curr_code = obs.get("TEST_CODE") or ""
                curr_name = obs.get("TEST_NAME") or "Unknown"

                with st.expander(
                    f"Observation #{obs_id}: **{curr_name}** ({curr_code}) = "
                    f"{curr_val} {curr_unit} | {curr_date} (Doc: {obs.get('FILE_NAME')})",
                    expanded=(i == 0),
                ):
                    c1, c2 = st.columns([2, 1])

                    with c1:
                        col_val, col_unit = st.columns(2)
                        with col_val:
                            # Safely handle 0.0 values without falling back to 0.0 accidentally
                            default_val = float(curr_val) if curr_val is not None else 0.0
                            new_val = st.number_input(
                                "Numeric Value",
                                value=default_val,
                                format="%.4f",
                                key=f"val_{obs_id}",
                            )
                        with col_unit:
                            new_unit = st.text_input("Unit", value=curr_unit, key=f"unit_{obs_id}")

                        col_date, col_code = st.columns(2)
                        with col_date:
                            new_date = st.text_input("Observation Date (YYYY-MM-DD)", value=curr_date, key=f"date_{obs_id}")
                        with col_code:
                            new_code = st.text_input("Test Code", value=curr_code, key=f"code_{obs_id}")

                    with c2:
                        st.markdown("**Evidence Provenance:**")
                        st.markdown(f"• **Source Document:** `{obs.get('FILE_NAME')}`")
                        st.markdown(f"• **Page:** {obs.get('SOURCE_PAGE', 1)}")
                        conf = obs.get("EXTRACTION_CONFIDENCE")
                        if conf:
                            st.markdown(f"• **Confidence:** {float(conf):.0%}")
                        snippet = obs.get("SOURCE_SNIPPET")
                        if snippet:
                            st.markdown(f"• **Snippet:** *\"{snippet}\"*")

                    # Review action buttons
                    btn_col1, btn_col2, _ = st.columns([1, 1, 3])

                    with btn_col1:
                        if st.button("✅ Approve", key=f"app_{obs_id}", type="primary"):
                            # Validate using ReviewDecision model first
                            try:
                                decision = ReviewDecision(
                                    observation_id=obs_id,
                                    action="APPROVED",
                                    corrected_value_numeric=float(new_val),
                                    corrected_unit=new_unit.strip() if new_unit else None,
                                    corrected_date=new_date.strip() if new_date else None,
                                    corrected_test_code=new_code.strip() if new_code else None,
                                    reviewed_by="CLINICAL_REVIEWER",
                                )
                                # Atomic update + audit logging
                                repo.update_observation_review(
                                    observation_id=obs_id,
                                    status="APPROVED",
                                    reviewed_by=decision.reviewed_by,
                                    value_numeric=decision.corrected_value_numeric,
                                    unit=decision.corrected_unit,
                                    observed_at=decision.corrected_date,
                                    test_code=decision.corrected_test_code,
                                    reviewer_notes="Approved via verification gate",
                                )
                                st.success(f"Observation #{obs_id} approved into trusted record.")
                                st.rerun()
                            except Exception as val_err:
                                st.error(f"Validation error: {val_err}")

                    with btn_col2:
                        if st.button("❌ Reject", key=f"rej_{obs_id}"):
                            try:
                                repo.update_observation_review(
                                    observation_id=obs_id,
                                    status="REJECTED",
                                    reviewed_by="CLINICAL_REVIEWER",
                                    reviewer_notes="Rejected by reviewer",
                                )
                                st.warning(f"Observation #{obs_id} marked as REJECTED.")
                                st.rerun()
                            except Exception as rej_err:
                                st.error(f"Error rejecting observation: {rej_err}")

            # Safe bulk actions with explicit confirmation checkbox
            st.markdown("---")
            confirm_bulk = st.checkbox("I confirm that I have verified the clinical accuracy of all remaining pending observations.")
            if st.button("✅ Approve All Pending Observations", type="secondary", disabled=not confirm_bulk):
                for obs in pending_obs:
                    o_id = obs.get("OBSERVATION_ID")
                    repo.update_observation_review(
                        observation_id=o_id,
                        status="APPROVED",
                        reviewed_by="CLINICAL_REVIEWER",
                        reviewer_notes="Batch approved with confirmation",
                    )
                st.success(f"Batch approved {len(pending_obs)} observations.")
                st.rerun()


# ================================================================
# PAGE 5: ASK MEDITWIN
# ================================================================
elif page == "💬 Ask MediTwin":
    st.markdown("## Ask MediTwin — Evidence-Grounded Q&A")
    st.caption("Pipeline B: Question → Parameterized Db2 Retrieval → Grounded Gemini Answer → Evidence Cards")

    repo = get_repo()
    patient = repo.get_patient(selected_pid) if conn.is_connected else {
        "DISPLAY_NAME": "Synthetic Patient Alpha",
        "DEMO_CODE": "DEMO-001"
    }

    st.info(f"Querying Patient: **{patient.get('DISPLAY_NAME')}** (`{patient.get('DEMO_CODE')}`)")

    st.markdown("**Example clinical questions:**")
    eq1, eq2 = st.columns(2)
    with eq1:
        b1 = st.button("How did HbA1c change over time?")
        b2 = st.button("What was the latest fasting blood sugar?")
        b3 = st.button("Which observations increased?")
    with eq2:
        b4 = st.button("Show all cholesterol measurements")
        b5 = st.button("What was the value recorded in November?")
        b6 = st.button("What is the latest hemoglobin?")

    user_query = st.text_input(
        "Ask a question about this patient's medical history:",
        placeholder="e.g., How did HbA1c change between reports?",
        key="qa_box",
    )

    active_q = None
    if b1: active_q = "How did HbA1c change over time?"
    elif b2: active_q = "What was the latest fasting blood sugar?"
    elif b3: active_q = "Which observations increased?"
    elif b4: active_q = "Show all cholesterol measurements"
    elif b5: active_q = "What was the value recorded in November?"
    elif b6: active_q = "What is the latest hemoglobin?"
    elif user_query: active_q = user_query

    if active_q:
        st.markdown("---")
        st.markdown(f"**Query:** *{active_q}*")

        api_key = gemini_settings.api_key or os.environ.get("GEMINI_API_KEY", "")

        with st.spinner("Executing LangGraph Q&A StateGraph & Parameterized Db2 retrieval..."):
            graph_result = run_question_workflow(
                question=active_q,
                patient_id=selected_pid,
                repo=repo if conn.is_connected else None,
                gemini_api_key=api_key,
                gemini_model=gemini_settings.model,
            )

        st.caption(f"LangGraph execution nodes: `{' → '.join(graph_result.get('completed_nodes', []))}`")

        # Display Grounded Answer
        st.markdown("### Answer")
        answer_text = graph_result.get("generated_answer") or graph_result.get("final_response", "")
        st.markdown(answer_text)

        # Evidence Cards
        evidence_cards = graph_result.get("evidence_cards", [])
        if evidence_cards:
            st.markdown("---")
            st.markdown(f"### Supporting Evidence ({len(evidence_cards)} records)")
            for card in evidence_cards:
                st.markdown(
                    f'<div class="evidence-card">'
                    f'<strong>{card["test_name"]}</strong> ({card.get("test_code", "")}): '
                    f'<strong>{card["value"]} {card["unit"]}</strong><br>'
                    f'<span style="font-size:0.85rem; color:#4A5568;">'
                    f'Observation Date: {card["date"]} | Source: `{card["source_file"]}` (p. {card.get("source_page", 1)})<br>'
                    f'<em>"{card["snippet"]}"</em>'
                    f'</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Source Document References
        sources = graph_result.get("answer_sources", [])
        if sources:
            st.markdown("---")
            st.markdown("### Source Documents Cited")
            for src in sources:
                st.markdown(f"• `{src['file_name']}` (Page {src.get('page', 1)})")


# ================================================================
# PAGE 6: AUDIT HISTORY
# ================================================================
elif page == "📋 Audit History":
    st.markdown("## Audit & Compliance Log")
    st.caption("Immutable append-only record of platform events for regulatory compliance")

    repo = get_repo()

    if not conn.is_connected:
        st.warning("IBM Db2 is currently offline. Audit history requires database connection.")
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            entity_filter = st.selectbox("Filter by Entity Type", options=["ALL", "PATIENT", "DOCUMENT", "OBSERVATION"])
        with c2:
            log_limit = st.selectbox("Rows to Show", options=[20, 50, 100], index=1)

        try:
            f_type = None if entity_filter == "ALL" else entity_filter
            logs = repo.get_audit_log(entity_type=f_type, limit=log_limit)

            if logs:
                log_data = []
                for l in logs:
                    log_data.append({
                        "Audit ID": l.get("AUDIT_ID"),
                        "Timestamp": str(l.get("LOGGED_AT", ""))[:19],
                        "Actor": l.get("ACTOR_ID"),
                        "Action": l.get("ACTION"),
                        "Entity Type": l.get("ENTITY_TYPE"),
                        "Entity ID": l.get("ENTITY_ID"),
                        "Details": l.get("DETAILS_JSON", "")[:80] if l.get("DETAILS_JSON") else "",
                    })
                st.dataframe(pd.DataFrame(log_data), use_container_width=True, hide_index=True)
            else:
                st.info("No audit logs found.")
        except Exception as e:
            st.error(f"Error reading audit log: {e}")
