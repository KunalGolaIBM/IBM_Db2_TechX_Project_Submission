"""
MediTwin AI — Retrieval Service
Parameterized Db2 query templates for evidence retrieval.
The model NEVER generates arbitrary SQL.
Supports temporal questions, comparative queries, panel groupings, and trend queries.
"""

import logging
import re
from typing import List, Dict, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# Standard clinical test aliases mapping colloquial expressions to formal test codes
TEST_CODE_ALIASES = {
    "hba1c": "HBA1C",
    "hemoglobin a1c": "HBA1C",
    "glycated hemoglobin": "HBA1C",
    "haemoglobin": "HGB",
    "hemoglobin": "HGB",
    "hgb": "HGB",
    "fasting blood sugar": "FBS",
    "fbs": "FBS",
    "fasting glucose": "FBS",
    "blood glucose": "FBS",
    "glucose": "FBS",
    "cholesterol": "CHOL",
    "total cholesterol": "CHOL",
    "hdl": "HDL",
    "ldl": "LDL",
    "triglycerides": "TG",
    "triglyceride": "TG",
    "creatinine": "CREAT",
    "urea": "UREA",
    "bun": "BUN",
    "tsh": "TSH",
    "thyroid": "TSH",
    "wbc": "WBC",
    "white blood cell": "WBC",
    "rbc": "RBC",
    "red blood cell": "RBC",
    "platelet": "PLT",
    "platelets": "PLT",
    "blood pressure": "BP",
    "systolic": "BP_SYS",
    "diastolic": "BP_DIA",
    "bmi": "BMI",
    "weight": "WEIGHT",
    "height": "HEIGHT",
    "vitamin d": "VITD",
    "vitamin b12": "VITB12",
    "iron": "IRON",
    "ferritin": "FERR",
    "calcium": "CA",
    "potassium": "K",
    "sodium": "NA",
    "alt": "ALT",
    "ast": "AST",
    "sgpt": "ALT",
    "sgot": "AST",
    "bilirubin": "BILI",
    "albumin": "ALB",
    "uric acid": "URIC",
    "esr": "ESR",
    "crp": "CRP",
}

# Panels for ambiguous or multi-test inquiries
PANEL_GROUPINGS = {
    "cholesterol": ["CHOL", "HDL", "LDL", "TG"],
    "lipid": ["CHOL", "HDL", "LDL", "TG"],
    "lipids": ["CHOL", "HDL", "LDL", "TG"],
    "cbc": ["HGB", "WBC", "RBC", "PLT"],
    "blood count": ["HGB", "WBC", "RBC", "PLT"],
    "kidney": ["CREAT", "UREA", "BUN"],
    "renal": ["CREAT", "UREA", "BUN"],
    "liver": ["ALT", "AST", "BILI", "ALB"],
    "hepatic": ["ALT", "AST", "BILI", "ALB"],
}

# Month keyword mapping for temporal queries
MONTH_NAMES = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}


def identify_test_code(question: str) -> Optional[str]:
    """
    Identify standard clinical test code from natural language question.
    Uses strict keyword priority matching — NEVER LLM-generated SQL.
    """
    q = question.lower()
    # Check multi-word aliases first
    sorted_aliases = sorted(TEST_CODE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    for alias, code in sorted_aliases:
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, q):
            return code
    return None


def identify_test_name_keyword(question: str) -> Optional[str]:
    """Extract candidate medical keyword from question."""
    q = question.lower()
    for alias in sorted(TEST_CODE_ALIASES.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return alias
    return None


def identify_panel_grouping(question: str) -> Optional[List[str]]:
    """Detect if question refers to a multi-test panel (e.g. cholesterol panel)."""
    q = question.lower()
    for panel_name, codes in PANEL_GROUPINGS.items():
        if re.search(rf"\b{re.escape(panel_name)}\b", q):
            return codes
    return None


def identify_month_filter(question: str) -> Optional[str]:
    """Extract month identifier (e.g. 'november' -> '-11-') from question."""
    q = question.lower()
    for mname, mnum in MONTH_NAMES.items():
        if re.search(rf"\b{re.escape(mname)}\b", q):
            return f"-{mnum}-"
    return None


class RetrievalService:
    """
    Retrieves evidence from IBM Db2 using pre-defined parameterized queries.
    All parameters are strictly bound via prepared statements.
    """

    def __init__(self, repository):
        self.repo = repository

    def get_latest_for_metric(self, patient_id: int, test_code: str) -> Dict:
        """Get the most recent approved observation for a metric."""
        obs = self.repo.get_latest_observation(patient_id, test_code)
        if obs:
            return {
                "found": True,
                "observation": obs,
                "summary": (
                    f"Latest {obs.get('TEST_NAME', test_code)}: "
                    f"{obs.get('VALUE_NUMERIC', 'N/A')} {obs.get('UNIT', '')} "
                    f"on {obs.get('OBSERVED_AT', 'unknown date')} "
                    f"(Source: {obs.get('FILE_NAME', 'unknown')})"
                ),
            }
        return {
            "found": False,
            "summary": f"No approved observations found for {test_code}.",
        }

    def get_metric_history(self, patient_id: int, test_code: str,
                           start_date: str = None,
                           end_date: str = None) -> Dict:
        """Get all approved observations for a metric ordered chronologically."""
        observations = self.repo.get_approved_observations(
            patient_id=patient_id,
            test_code=test_code,
            start_date=start_date,
            end_date=end_date,
        )
        return {
            "found": len(observations) > 0,
            "count": len(observations),
            "observations": observations,
        }

    def search_by_keyword(self, patient_id: int, keyword: str) -> Dict:
        """Search approved observations by test name keyword."""
        observations = self.repo.search_observations_by_keyword(
            patient_id=patient_id,
            keyword=keyword,
        )
        return {
            "found": len(observations) > 0,
            "count": len(observations),
            "observations": observations,
        }

    def retrieve_evidence_for_question(self, patient_id: int, question: str) -> Dict:
        """
        Main entry point: Dispatches natural question into pre-defined parameterized Db2 queries.
        Supports:
        - Specific metric longitudinal trend ("How did HbA1c change?")
        - Panel queries ("Show all cholesterol measurements")
        - Directional trend queries ("Which observations increased?", "Which decreased?")
        - Month-filtered queries ("What was recorded in November?")
        - Comparative queries ("Compare latest two readings")
        """
        q_lower = question.lower()
        test_code = identify_test_code(question)
        panel_codes = identify_panel_grouping(question)
        month_filter = identify_month_filter(question)
        keyword = identify_test_name_keyword(question)

        is_increase_query = any(w in q_lower for w in ["increased", "increase", "higher", "rose", "gone up"])
        is_decrease_query = any(w in q_lower for w in ["decreased", "decrease", "lower", "dropped", "fallen", "gone down"])
        is_comparison_query = any(w in q_lower for w in ["compare", "difference between", "comparison"])

        evidence = {
            "question": question,
            "patient_id": patient_id,
            "test_code_identified": test_code,
            "panel_codes_identified": panel_codes,
            "query_type": "metric",
            "observations": [],
            "source_documents": [],
            "sufficient_evidence": False,
        }

        # 1. Directional Trend Query ("Which observations increased / decreased?")
        if (is_increase_query or is_decrease_query) and not test_code:
            evidence["query_type"] = "directional_trend"
            all_codes = self.repo.get_distinct_test_codes(patient_id)
            matching_obs = []

            from services.timeline_service import compute_metric_trend
            for item in all_codes:
                code = item.get("TEST_CODE")
                if not code:
                    continue
                obs_list = self.repo.get_approved_observations(patient_id, test_code=code)
                trend = compute_metric_trend(obs_list, code)
                if trend.get("count", 0) >= 2 and "absolute_change" in trend:
                    delta = trend["absolute_change"]
                    if is_increase_query and delta > 0:
                        matching_obs.extend(obs_list)
                    elif is_decrease_query and delta < 0:
                        matching_obs.extend(obs_list)

            if matching_obs:
                evidence["observations"] = matching_obs
                evidence["sufficient_evidence"] = True

        # 2. Month-specific queries ("What was the value recorded in November?")
        elif month_filter:
            evidence["query_type"] = "month_filtered"
            all_approved = self.repo.get_approved_observations(patient_id)
            month_obs = [
                o for o in all_approved
                if month_filter in str(o.get("OBSERVED_AT") or o.get("observed_at") or "")
            ]
            if test_code:
                month_obs = [
                    o for o in month_obs
                    if (o.get("TEST_CODE") or o.get("test_code") or "").upper() == test_code.upper()
                ]

            if month_obs:
                evidence["observations"] = month_obs
                evidence["sufficient_evidence"] = True

        # 3. Panel Grouping Queries (e.g. "cholesterol", "lipids", "cbc")
        elif panel_codes and not test_code:
            evidence["query_type"] = "panel"
            panel_obs = []
            for pcode in panel_codes:
                p_records = self.repo.get_approved_observations(patient_id, test_code=pcode)
                panel_obs.extend(p_records)

            if panel_obs:
                evidence["observations"] = panel_obs
                evidence["sufficient_evidence"] = True

        # 4. Standard Metric or Keyword Query
        elif test_code:
            evidence["query_type"] = "metric"
            result = self.get_metric_history(patient_id, test_code)
            if result["found"]:
                # If specific comparison requested, can isolate latest 2
                if is_comparison_query and len(result["observations"]) >= 2:
                    evidence["observations"] = result["observations"][-2:]
                else:
                    evidence["observations"] = result["observations"]
                evidence["sufficient_evidence"] = True

        # 5. Keyword search fallback
        elif keyword:
            evidence["query_type"] = "keyword"
            result = self.search_by_keyword(patient_id, keyword)
            if result["found"]:
                evidence["observations"] = result["observations"]
                evidence["sufficient_evidence"] = True

        # Build clean source references
        sources_seen = set()
        for obs in evidence["observations"]:
            fname = obs.get("FILE_NAME") or obs.get("file_name") or obs.get("source_document_name") or ""
            if fname and fname not in sources_seen:
                sources_seen.add(fname)
                evidence["source_documents"].append({
                    "file_name": fname,
                    "page": obs.get("SOURCE_PAGE") or obs.get("source_page"),
                    "snippet": obs.get("SOURCE_SNIPPET") or obs.get("source_snippet") or "",
                })

        return evidence
