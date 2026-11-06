"""
Tests for Suspicious Activity Report (SAR) generation and export utilities.
"""

from pathlib import Path
import pytest
from src.db.schema import initialize_schema
from src.db.seed_data import seed_database
from src.agents.workflow import SentinelWorkflow
from src.utils.report_exporter import export_sar_to_markdown, export_sar_to_pdf


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_schema()
    seed_database(force=True)


def test_sar_narrative_contents():
    workflow = SentinelWorkflow()
    result = workflow.run_investigation("TX-STRUCT-01", auto_approve=True)

    narrative = result["sar_narrative"]
    assert "SUSPICIOUS ACTIVITY REPORT" in narrative
    assert "PART I: SUBJECT & ENTITY INFORMATION" in narrative
    assert "PART II: SUSPICIOUS TRANSACTION DETAILS" in narrative
    assert "PART III: FORENSIC EVIDENCE" in narrative
    assert "PART IV: NARRATIVE SUMMARY" in narrative
    assert "TX-STRUCT-01" in narrative


def test_export_sar(tmp_path):
    workflow = SentinelWorkflow()
    result = workflow.run_investigation("TX-STRUCT-01", auto_approve=True)
    narrative = result["sar_narrative"]

    md_file = tmp_path / "sar_test.md"
    pdf_file = tmp_path / "sar_test.pdf"

    exported_md = export_sar_to_markdown(narrative, md_file)
    assert exported_md.exists()
    assert exported_md.stat().st_size > 100

    exported_pdf = export_sar_to_pdf(narrative, pdf_file)
    assert exported_pdf.exists()
    assert exported_pdf.stat().st_size > 100
