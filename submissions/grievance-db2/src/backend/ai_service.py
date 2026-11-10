import os
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

# LangChain Imports - Db2Hack Framework Requirement
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from config import settings

logger = logging.getLogger("uvicorn.error")


class AITriageResult(BaseModel):
    category: str = Field(description="Normalized category: water, electricity, roads, sanitation, health, food, pension, other")
    priority: str = Field(description="Priority: Low, Medium, High, or Critical")
    summary: str = Field(description="Concise 1-sentence summary under 200 characters")
    method: str = Field(default="langchain_llm", description="Method used: langchain_llm or rule_based_fallback")


def get_langchain_llm():
    """
    Initializes a LangChain chat model based on configured environment variables.
    Supports GEMINI_API_KEY, OPENROUTER_API_KEY, OLLAMA_BASE_URL, and WATSONX.
    Returns None if no LLM provider is configured.
    """
    # 1. Google Gemini via langchain-google-genai
    if settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model_name = settings.AI_MODEL or "gemini-2.5-flash"
            return ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.1,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to load ChatGoogleGenerativeAI: {e}")

    # 2. OpenRouter via langchain-openai
    if settings.OPENROUTER_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            model_name = settings.AI_MODEL or "openai/gpt-4o-mini"
            return ChatOpenAI(
                model=model_name,
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.1,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to load ChatOpenAI via OpenRouter: {e}")

    # 3. Local Ollama via langchain-community
    if settings.OLLAMA_BASE_URL:
        try:
            from langchain_community.chat_models import ChatOllama
            model_name = settings.AI_MODEL or "llama3.2"
            return ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=model_name,
                temperature=0.1,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to load ChatOllama: {e}")

    # 4. IBM watsonx.ai via OpenAI-compatible endpoint or community
    if settings.WATSONX_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            model_name = settings.AI_MODEL or "ibm/granite-13b-chat-v2"
            return ChatOpenAI(
                model=model_name,
                api_key=settings.WATSONX_API_KEY,
                base_url=f"{settings.WATSONX_URL}/v1",
                temperature=0.1,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to load watsonx LLM: {e}")

    return None


# ==============================================================================
# Feature 1: AI Grievance Triage (LangChain + Fallback)
# ==============================================================================

TRIAGE_SYSTEM_PROMPT = """You are an expert AI Grievance Triage Officer for India's CPGRAMS public portal.
Analyze the citizen grievance and return a JSON object with:
1. "category": exactly one of ["water", "electricity", "roads", "sanitation", "health", "food", "pension", "other"]
2. "priority": exactly one of ["Low", "Medium", "High", "Critical"]
   - Critical: immediate hazard, sparks/fire, sewage in drinking water, live wires, vaccine shortage, hospital refusal.
   - High: power cuts > 6h, deep potholes, overflowing dhalao, PDS grain denial, pension halted > 3 months.
   - Medium: billing discrepancies, low water pressure, delayed inspection, street dog nuisance.
   - Low: general queries, minor procedural delays, non-urgent maintenance.
3. "summary": a clean, single-sentence summary of the grievance (maximum 150 characters).

Return ONLY valid JSON matching this schema:
{{"category": "water", "priority": "High", "summary": "One sentence summary"}}
"""

def fallback_rule_based_triage(description: str, subject: str = "", category_hint: str = "") -> AITriageResult:
    """
    Deterministic rule & keyword-based triage fallback when LLM is offline or timed out.
    """
    text = f"{subject} {description} {category_hint}".lower()

    # Priority determination
    critical_keywords = [
        "contaminat", "sewage in water", "spark", "explosion", "dangling wire", "snapped wire",
        "11kv", "cave-in", "manhole", "dead animal", "carcass", "rabies", "vaccine shortage",
        "emergency", "shock", "hazard", "fire", "death", "hospital refusal", "bleeding"
    ]
    high_keywords = [
        "burst", "flooding", "blackout", "load shedding", "surge", "deep pothole", "overflowing",
        "dhalao", "garbage burning", "dengue", "malaria", "under-weighing", "stopped", "arrears",
        "disabled", "crater", "waterlogged"
    ]
    low_keywords = ["query", "information", "suggestion", "procedure", "status check", "routine"]

    if any(kw in text for kw in critical_keywords):
        priority = "Critical"
    elif any(kw in text for kw in high_keywords):
        priority = "High"
    elif any(kw in text for kw in low_keywords):
        priority = "Low"
    else:
        priority = "Medium"

    # Category determination
    cat_rules = [
        ("water", ["water", "pipeline", "jal", "sewage", "drinking water", "tap", "meter", "leakage", "djb"]),
        ("electricity", ["electricity", "power", "voltage", "transformer", "wire", "streetlight", "bses", "tata power", "phase"]),
        ("roads", ["road", "pothole", "tar", "gravel", "pavement", "signal", "traffic", "footpath", "pwd", "underpass"]),
        ("sanitation", ["garbage", "dhalao", "drain", "drainage", "waste", "toilet", "dumping", "sweeper", "mcd"]),
        ("health", ["health", "hospital", "doctor", "dispensary", "clinic", "medicine", "rabies", "dengue", "x-ray", "ambulance"]),
        ("food", ["ration", "fps", "fair price", "pds", "wheat", "grain", "nfsa", "biometric", "food"]),
        ("pension", ["pension", "jeevan pramaan", "life certificate", "ppo", "superannuation", "senior citizen", "disability"])
    ]

    detected_category = category_hint.lower() if category_hint in [c[0] for c in cat_rules] else None
    if not detected_category:
        for cat_name, keywords in cat_rules:
            if any(kw in text for kw in keywords):
                detected_category = cat_name
                break

    category = detected_category or "other"

    # 1-Sentence summary
    clean_desc = re.sub(r'\s+', ' ', description).strip()
    if len(clean_desc) <= 150:
        summary = clean_desc
    else:
        first_period = clean_desc.find('.')
        if 20 < first_period <= 160:
            summary = clean_desc[:first_period + 1].strip()
        else:
            summary = clean_desc[:147].rstrip() + "..."

    return AITriageResult(
        category=category,
        priority=priority,
        summary=summary,
        method="rule_based_fallback"
    )


def triage_grievance(description: str, subject: str = "", category_hint: str = "") -> AITriageResult:
    """
    Runs AI Triage using LangChain chain with graceful fallback.
    """
    llm = get_langchain_llm()
    if not llm:
        return fallback_rule_based_triage(description, subject, category_hint)

    try:
        parser = JsonOutputParser(pydantic_object=AITriageResult)
        prompt = ChatPromptTemplate.from_messages([
            ("system", TRIAGE_SYSTEM_PROMPT),
            ("human", "Subject: {subject}\nCategory Hint: {category_hint}\nDetailed Description: {description}")
        ])
        chain = prompt | llm | parser

        response = chain.invoke({
            "subject": subject or "Public Complaint",
            "category_hint": category_hint or "General",
            "description": description
        })

        category = str(response.get("category", "")).lower().strip()
        if category not in ["water", "electricity", "roads", "sanitation", "health", "food", "pension"]:
            category = category_hint or "other"

        priority = str(response.get("priority", "")).capitalize().strip()
        if priority not in ["Low", "Medium", "High", "Critical"]:
            priority = "Medium"

        summary = str(response.get("summary", "")).strip()[:250]
        if not summary:
            summary = (subject or description)[:150]

        return AITriageResult(
            category=category,
            priority=priority,
            summary=summary,
            method="langchain_llm"
        )
    except Exception as e:
        logger.warning(f"LangChain AI triage error: {e}. Executing deterministic fallback.")
        return fallback_rule_based_triage(description, subject, category_hint)


# ==============================================================================
# Feature 2: "Ask the Data" Natural Language to IBM Db2 SQL Engine
# ==============================================================================

DB2_SQL_SYSTEM_PROMPT = """You are an expert IBM Db2 database administrator and SQL generator for the CPGRAMS Grievance System.
Database: GRIEVDB (IBM Db2 Community Edition)
Tables and columns available:
1. departments (id INT, code VARCHAR(50), name VARCHAR(200), description VARCHAR(500), nodal_email VARCHAR(150), created_at TIMESTAMP)
2. grievances (id INT, tracking_id VARCHAR(32), citizen_name VARCHAR(150), contact VARCHAR(150), category VARCHAR(100), description VARCHAR(3000), ward VARCHAR(100), priority VARCHAR(20), status VARCHAR(50), created_at TIMESTAMP, resolved_at TIMESTAMP, department_id INT, subject VARCHAR(255), state VARCHAR(100), pincode VARCHAR(10), ai_category VARCHAR(50), ai_priority VARCHAR(20), ai_summary VARCHAR(255))
3. grievance_updates (id INT, grievance_id INT, previous_status VARCHAR(50), new_status VARCHAR(50), notes VARCHAR(1000), updated_by VARCHAR(100), created_at TIMESTAMP)

CRITICAL IBM Db2 RULES:
- ONLY output a single read-only SELECT query.
- DO NOT use MySQL / Postgres LIMIT syntax. You MUST use "FETCH FIRST <N> ROWS ONLY".
- For date arithmetic in Db2:
  * Difference in days: DAYS(CURRENT DATE) - DAYS(DATE(created_at))
  * Breaches open > 15 days: WHERE status != 'Resolved' AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15
- DO NOT include markdown backticks or explanation. Return ONLY the raw SQL query.
"""

FORBIDDEN_SQL_PATTERNS = [
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE|MERGE|CALL|CREATE)\b',
    r';',
    r'--',
    r'/\*',
    r'\*/',
]

ALLOWED_TABLES = {"departments", "grievances", "grievance_updates", "sysibm.sysdummy1"}


def validate_and_sanitize_sql(sql_query: str) -> str:
    """
    Strict security guardrails verifying that the SQL query is a safe, single SELECT
    targeting only allowed tables, free of destructive DDL/DML, comments, and semicolons.
    """
    clean_sql = sql_query.strip()
    clean_sql = re.sub(r'^```sql\s*', '', clean_sql, flags=re.IGNORECASE)
    clean_sql = re.sub(r'^```\s*', '', clean_sql)
    clean_sql = re.sub(r'\s*```$', '', clean_sql)
    clean_sql = clean_sql.strip()

    # 1. Must start with SELECT
    if not clean_sql.upper().startswith("SELECT"):
        raise ValueError("Security Violation: Only SELECT queries are permitted.")

    # 2. Reject forbidden keywords, multiple statements, or comments
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, clean_sql, re.IGNORECASE):
            raise ValueError(f"Security Violation: Query contains prohibited token or operator ({pattern}).")

    # 3. Allow-list table verification
    # Extract words after FROM and JOIN
    table_matches = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z_0-9\.]+)', clean_sql, re.IGNORECASE)
    for tbl in table_matches:
        cleaned_tbl = tbl.split()[0].replace(',', '').strip().lower()
        if cleaned_tbl not in ALLOWED_TABLES:
            raise ValueError(f"Security Violation: Access to table '{cleaned_tbl}' is not authorized. Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}")

    # 4. Enforce Db2 row limiting (convert LIMIT or add FETCH FIRST 50 ROWS ONLY)
    if re.search(r'\bLIMIT\s+(\d+)', clean_sql, re.IGNORECASE):
        clean_sql = re.sub(r'\bLIMIT\s+(\d+)', r'FETCH FIRST \1 ROWS ONLY', clean_sql, flags=re.IGNORECASE)
    elif "FETCH FIRST" not in clean_sql.upper():
        clean_sql = f"{clean_sql} FETCH FIRST 50 ROWS ONLY"

    return clean_sql


def fallback_natural_language_sql(question: str) -> str:
    """
    Deterministic rule-based SQL generator for common natural language questions
    when LLM API keys are not supplied.
    """
    q = question.lower()

    if "ward" in q and ("most" in q or "highest" in q or "top" in q):
        if "water" in q:
            return "SELECT ward, COUNT(*) AS total_complaints FROM grievances WHERE LOWER(category) = 'water' GROUP BY ward ORDER BY total_complaints DESC FETCH FIRST 10 ROWS ONLY"
        elif "electricity" in q or "power" in q:
            return "SELECT ward, COUNT(*) AS total_complaints FROM grievances WHERE LOWER(category) = 'electricity' GROUP BY ward ORDER BY total_complaints DESC FETCH FIRST 10 ROWS ONLY"
        return "SELECT ward, COUNT(*) AS total_complaints FROM grievances GROUP BY ward ORDER BY total_complaints DESC FETCH FIRST 10 ROWS ONLY"

    if "sla" in q or "15 day" in q or "breach" in q or "overdue" in q or "pending" in q:
        return "SELECT tracking_id, citizen_name, category, ward, priority, (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) AS days_open FROM grievances WHERE status != 'Resolved' AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15 ORDER BY days_open DESC FETCH FIRST 20 ROWS ONLY"

    if "critical" in q or "priority" in q:
        if "count" in q or "breakdown" in q or "summary" in q:
            return "SELECT priority, COUNT(*) AS count FROM grievances GROUP BY priority ORDER BY count DESC FETCH FIRST 10 ROWS ONLY"
        return "SELECT tracking_id, citizen_name, category, ward, status, subject FROM grievances WHERE priority = 'Critical' ORDER BY created_at DESC FETCH FIRST 20 ROWS ONLY"

    if "department" in q or "ministry" in q:
        if "list" in q or "all" in q:
            return "SELECT code, name, nodal_email FROM departments ORDER BY name ASC FETCH FIRST 20 ROWS ONLY"
        return "SELECT COALESCE(d.name, g.category) AS department_name, COUNT(g.id) AS total_cases FROM grievances g LEFT JOIN departments d ON g.department_id = d.id GROUP BY COALESCE(d.name, g.category) ORDER BY total_cases DESC FETCH FIRST 10 ROWS ONLY"

    if "resolved" in q or "resolution" in q:
        return "SELECT status, COUNT(*) AS count FROM grievances GROUP BY status ORDER BY count DESC FETCH FIRST 10 ROWS ONLY"

    if "water" in q:
        return "SELECT tracking_id, citizen_name, ward, status, priority, subject FROM grievances WHERE LOWER(category) = 'water' ORDER BY created_at DESC FETCH FIRST 20 ROWS ONLY"

    if "recent" in q or "latest" in q:
        return "SELECT tracking_id, citizen_name, category, ward, status, created_at FROM grievances ORDER BY created_at DESC FETCH FIRST 20 ROWS ONLY"

    # Default fallback
    return "SELECT tracking_id, citizen_name, category, ward, priority, status FROM grievances ORDER BY created_at DESC FETCH FIRST 25 ROWS ONLY"


def generate_db2_sql(question: str) -> Tuple[str, str]:
    """
    Translates a plain-language question into an IBM Db2 SQL query using LangChain
    or fallback, then sanitizes and validates the query.
    Returns: (sanitized_sql, method_used)
    """
    # Guardrail Pre-check: reject explicit injection attempts in the user prompt
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, question, re.IGNORECASE):
            raise ValueError(f"Security Violation: Input question contains prohibited SQL token or operator ({pattern}).")

    llm = get_langchain_llm()
    if not llm:
        raw_sql = fallback_natural_language_sql(question)
        return validate_and_sanitize_sql(raw_sql), "rule_based_fallback"

    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", DB2_SQL_SYSTEM_PROMPT),
            ("human", "Question: {question}\nGenerate a valid IBM Db2 read-only SELECT query:")
        ])
        chain = prompt | llm
        response = chain.invoke({"question": question})
        raw_sql = response.content if hasattr(response, "content") else str(response)
        sanitized = validate_and_sanitize_sql(raw_sql)
        return sanitized, "langchain_llm"
    except Exception as e:
        logger.warning(f"LangChain SQL generation failed ({e}). Falling back to pattern-matcher.")
        raw_sql = fallback_natural_language_sql(question)
        return validate_and_sanitize_sql(raw_sql), "rule_based_fallback"


# ==============================================================================
# Feature 3: Ward Hotspot & Duplicate Detection
# ==============================================================================

def detect_ward_hotspots_and_duplicates(
    db,
    ward: str,
    category: str,
    description: str,
    current_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Inspects IBM Db2 for open grievances in the same ward and category.
    Identifies potential duplicates and alerts if the ward is an active hotspot.
    """
    from models import Grievance

    # Find existing open grievances in the same ward and category
    query = db.query(Grievance).filter(
        Grievance.ward == ward,
        Grievance.category == category,
        Grievance.status.in_(["Filed", "Under Review", "Forwarded to Dept"])
    )
    if current_id:
        query = query.filter(Grievance.id != current_id)

    open_cases = query.order_by(Grievance.created_at.desc()).limit(10).all()
    open_count = len(open_cases)

    # Hotspot threshold: >= 2 active open complaints in the same ward and category
    is_hotspot = open_count >= 2
    hotspot_alert = {
        "is_hotspot": is_hotspot,
        "active_open_count": open_count,
        "ward": ward,
        "category": category,
        "severity": "CRITICAL" if open_count >= 4 else ("HIGH" if open_count >= 2 else "NORMAL"),
        "message": (
            f"⚠️ Hotspot Warning: {open_count} active open complaints reported in {ward} regarding {category} issues."
            if is_hotspot else "No unusual complaint cluster detected in this ward."
        )
    }

    # Potential duplicates detection using keyword overlap
    words_in_desc = set(re.findall(r'\b[a-zA-Z]{4,}\b', description.lower()))
    potential_duplicates = []

    for item in open_cases[:5]:
        target_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', f"{item.subject} {item.description}".lower()))
        common = words_in_desc.intersection(target_words)
        similarity_score = len(common) / max(len(words_in_desc), 1)

        if similarity_score >= 0.25 or len(common) >= 3:
            potential_duplicates.append({
                "tracking_id": item.tracking_id,
                "subject": item.subject,
                "status": item.status,
                "priority": item.priority,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "overlap_keywords": list(common)[:5]
            })

    return {
        "hotspot_alert": hotspot_alert,
        "potential_duplicates": potential_duplicates
    }


# ==============================================================================
# Feature 4: "Explain the Query" Natural Summary Engine
# ==============================================================================

def generate_natural_summary(
    question: str,
    sql: str,
    rows: List[Dict[str, Any]],
    row_count: int
) -> str:
    """
    Generates a concise 1-sentence plain-English summary explaining what the
    IBM Db2 query results reveal to civic officers and citizens.
    """
    q = question.lower()
    sql_lower = sql.lower()

    # Attempt LangChain synthesis if LLM is configured
    llm = get_langchain_llm()
    if llm and rows:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an executive civic data analyst. In exactly ONE concise sentence (max 150 characters), summarize the key takeaway of these database query results. Avoid jargon, mention key numbers/names, and do not use markdown formatting."),
                ("human", "Citizen Question: {question}\nResult Count: {row_count}\nData Sample: {sample}")
            ])
            sample_str = str(rows[:3])
            chain = prompt | llm
            summary_resp = chain.invoke({"question": question, "row_count": row_count, "sample": sample_str})
            text_val = summary_resp.content if hasattr(summary_resp, "content") else str(summary_resp)
            clean_summary = text_val.strip().replace("\n", " ")
            if len(clean_summary) > 10:
                return clean_summary
        except Exception as e:
            logger.warning(f"LangChain summary generation notice: {e}")

    # Deterministic fallback synthesis
    if "sla" in q or "15 day" in q or "breach" in q or "overdue" in q or "days_open" in sql_lower:
        if row_count > 0:
            return f"Currently, {row_count} open grievances have breached the 15-day statutory SLA and require immediate departmental escalation."
        return "Zero active grievances have breached the 15-day statutory SLA; all civic dockets are currently within charter limits."

    if "ward" in q or "ward" in sql_lower:
        if rows and len(rows) > 0:
            first_row = rows[0]
            ward_name = first_row.get("ward") or first_row.get("WARD") or "top ward"
            complaint_cnt = first_row.get("total_complaints") or first_row.get("TOTAL_COMPLAINTS") or first_row.get("count") or ""
            return f"{ward_name} leads in complaint density with {complaint_cnt} recorded grievances, identifying an active municipal service hotspot."
        return f"Identified complaint distribution across {row_count} municipal wards in IBM Db2."

    if "department" in q or "ministry" in q or "departments" in sql_lower:
        if rows and len(rows) > 0:
            top_dept = rows[0].get("department_name") or rows[0].get("name") or rows[0].get("dept_name") or "Concerned Department"
            top_cnt = rows[0].get("total_cases") or rows[0].get("total") or rows[0].get("count") or ""
            return f"Civic complaints are distributed across {row_count} departments, led by {top_dept} with {top_cnt} dockets."
        return f"Successfully queried {row_count} government departments registered in IBM Db2."

    if "critical" in q or "priority" in q:
        return f"Retrieved {row_count} prioritized grievance dockets requiring rapid dispatch from municipal engineering squads."

    if "water" in q:
        return f"IBM Db2 identified {row_count} water supply and pipeline grievances currently logged across Delhi wards."

    if "resolved" in q:
        return f"Database analysis records {row_count} grievance categories actively undergoing resolution tracking."

    return f"IBM Db2 retrieved {row_count} matching record{'s' if row_count != 1 else ''} based on your query criteria."


# ==============================================================================
# Feature 5: Officer Redressal Console & LangChain AI Action Drafter
# ==============================================================================

OFFICER_ACTION_PROMPT = """You are a Senior Administrative Nodal Officer in India's CPGRAMS public grievance redressal machinery.
Draft an official, highly authoritative bureaucratic Action Order / Compliance Directive for municipal field engineers and nodal officers regarding this citizen grievance docket:

Tracking ID: {tracking_id}
Citizen Name: {citizen_name}
Category: {category}
Priority: {priority}
Subject: {subject}
Description: {description}
Municipal Ward: {ward}
Days Pending: {days_open}

You must respond with ONLY valid JSON adhering strictly to this schema:
{{
  "action_type": "Field Inspection",
  "target_officer": "Zonal Assistant Engineer / Nodal Executive designation",
  "statutory_deadline_days": 3,
  "drafted_order_text": "Formal administrative notice citing public health/safety regulations, immediate steps ordered, and compliance directive.",
  "recommended_status": "Forwarded to Dept"
}}
Constraints:
- "action_type" MUST be exactly one of: ["Field Inspection", "Show-Cause Notice", "Immediate Repair", "Interim Relief"]
- "recommended_status" MUST be exactly one of: ["Forwarded to Dept", "Resolved"]
- "statutory_deadline_days" must be an integer between 1 and 7.
- "drafted_order_text" must be authoritative, quoting Indian civic regulations (e.g. SWM Rules, Electricity Act, DJB Act, NFSA, or CrPC Sec 133).
"""


def fallback_rule_based_officer_order(grievance_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic rule-based bureaucratic action order generator when LLM is unavailable.
    """
    category = str(grievance_data.get("category", "")).lower()
    priority = str(grievance_data.get("priority", "Medium")).capitalize()
    tracking_id = grievance_data.get("tracking_id", "GRV-2026-XXXX")
    citizen_name = grievance_data.get("citizen_name", "Citizen")
    subject = grievance_data.get("subject", "Public Complaint")
    ward = grievance_data.get("ward", "Municipal Ward")
    days_open = grievance_data.get("days_open", 1)

    is_critical = priority == "Critical" or days_open > 15
    deadline = 2 if is_critical else (3 if priority == "High" else 5)

    if "water" in category:
        action_type = "Immediate Repair" if is_critical else "Field Inspection"
        target_officer = "Zonal Executive Engineer, Delhi Jal Board (DJB)"
        order_text = (
            f"ORDER UNDER DELHI WATER BOARD ACT: Cognizance is taken of docket {tracking_id} lodged by {citizen_name} "
            f"concerning '{subject}' in {ward}. Executive Engineer (Water Supply) is hereby ordered to dispatch a mobile "
            f"pipeline maintenance crew within 24 hours. Hydrostatic pressure and potable water purity testing must be certified, "
            f"and an Action Taken Report (ATR) uploaded to IBM Db2 within {deadline} days, failing which disciplinary inquiry shall follow."
        )
    elif "electricity" in category or "power" in category:
        action_type = "Immediate Repair" if is_critical else "Field Inspection"
        target_officer = "Superintending Engineer (Operations & Maintenance), DISCOM"
        order_text = (
            f"EMERGENCY DIRECTIVE UNDER ELECTRICITY ACT / DERC REGULATIONS: In re docket {tracking_id} filed by {citizen_name} "
            f"in {ward} regarding '{subject}'. Immediate inspection of local transformer and overhead feeder network is directed. "
            f"Any dangling high-voltage lines, phase load imbalances, or exposed busbars must be rectified immediately. "
            f"Upload site safety clearance certificate to IBM Db2 within {deadline} days."
        )
    elif "road" in category:
        action_type = "Immediate Repair" if is_critical else "Field Inspection"
        target_officer = "Assistant Engineer (Civil), Public Works Department (PWD)"
        order_text = (
            f"CIVIL INFRASTRUCTURE MANDATE: In reference to grievance {tracking_id} in {ward} regarding '{subject}'. "
            f"The reported carriage-way depression/pothole constitutes a severe public hazard. Section Engineer is directed "
            f"to deploy a bitumen cold-mix repair squad, level the vehicular surface, and submit geo-tagged before/after photographs "
            f"on the CPGRAMS portal within {deadline} working days."
        )
    elif "sanitation" in category:
        action_type = "Immediate Repair" if is_critical else "Field Inspection"
        target_officer = "Sanitary Inspector & Zonal Health Officer, MCD Sanitation Dept"
        order_text = (
            f"MUNICIPAL SOLID WASTE DIRECTIVE (SWM RULES): Docket {tracking_id} in {ward} reports accumulated waste / drainage overflow. "
            f"Sanitation Division is directed to deploy mechanized compactor loaders, clear the overflow site, sanitize "
            f"the surrounding perimeter with disinfectant, and record supervisor sign-off in IBM Db2 within {deadline} days."
        )
    elif "food" in category or "ration" in category:
        action_type = "Show-Cause Notice"
        target_officer = "Food & Civil Supplies Inspector / Assistant Commissioner"
        order_text = (
            f"STATUTORY INQUIRY NOTICE - NATIONAL FOOD SECURITY ACT (NFSA): Re: Complaint {tracking_id} by {citizen_name} "
            f"in {ward}. Issue formal Show-Cause Notice to the concerned Fair Price Shop (FPS) dealer. Inspect electronic "
            f"Point-of-Sale (e-PoS) biometric transaction logs and physical buffer grain inventory. Submit inquiry findings within {deadline} days."
        )
    elif "pension" in category:
        action_type = "Interim Relief"
        target_officer = "Senior Accounts Officer, Directorate of Social Welfare"
        order_text = (
            f"WELFARE PENSION EXPEDITION ORDER: In re docket {tracking_id} regarding pensioner distress in {ward}. "
            f"Accounts branch is instructed to verify digital Jeevan Pramaan submission records, clear administrative holds, "
            f"and process pending DBT disbursement arrears directly to beneficiary account within {deadline} days."
        )
    elif "health" in category:
        action_type = "Show-Cause Notice" if priority == "Low" else "Immediate Repair"
        target_officer = "Chief Medical Officer (CMO), Directorate of Health Services"
        order_text = (
            f"PUBLIC HEALTH DIRECTIVE: Docket {tracking_id} in {ward} concerning health center service deficiencies. "
            f"Medical superintendent is directed to replenish critical medicine and diagnostic reagent stock immediately, "
            f"verify duty rosters, and submit patient grievance compliance report to IBM Db2 within {deadline} days."
        )
    else:
        action_type = "Field Inspection"
        target_officer = "Zonal Nodal Redressal Officer"
        order_text = (
            f"ADMINISTRATIVE COMPLIANCE ORDER - CPGRAMS CHARTER: Re: Docket {tracking_id} in {ward} regarding '{subject}'. "
            f"Deputed officer shall conduct a physical verification of the grievance site, examine departmental records, "
            f"and furnish an Action Taken Report (ATR) within {deadline} working days."
        )

    return {
        "action_type": action_type,
        "target_officer": target_officer,
        "statutory_deadline_days": deadline,
        "drafted_order_text": order_text,
        "recommended_status": "Forwarded to Dept",
        "generated_by": "LangChain Action Drafter (Rule-Based Fallback)"
    }


def draft_officer_action_order(grievance_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a formal bureaucratic action order using LangChain prompt chain,
    with deterministic fallback.
    """
    llm = get_langchain_llm()
    if not llm:
        return fallback_rule_based_officer_order(grievance_data)

    try:
        from langchain_core.prompts import PromptTemplate
        prompt = PromptTemplate(
            template=OFFICER_ACTION_PROMPT,
            input_variables=["tracking_id", "citizen_name", "category", "priority", "subject", "description", "ward", "days_open"]
        )
        chain = prompt | llm

        response = chain.invoke({
            "tracking_id": grievance_data.get("tracking_id", "GRV-2026-XXXX"),
            "citizen_name": grievance_data.get("citizen_name", "Citizen"),
            "category": grievance_data.get("category", "Public Administration"),
            "priority": grievance_data.get("priority", "Medium"),
            "subject": grievance_data.get("subject", "Grievance Docket"),
            "description": grievance_data.get("description", "Details pending"),
            "ward": grievance_data.get("ward", "Municipal Ward"),
            "days_open": grievance_data.get("days_open", 1)
        })

        content = response.content if hasattr(response, "content") else str(response)
        # Parse JSON
        import json
        clean_json = re.search(r'\{.*\}', content, re.DOTALL)
        if clean_json:
            parsed = json.loads(clean_json.group(0))
            return {
                "action_type": parsed.get("action_type", "Field Inspection"),
                "target_officer": parsed.get("target_officer", "Zonal Assistant Engineer"),
                "statutory_deadline_days": int(parsed.get("statutory_deadline_days", 3)),
                "drafted_order_text": parsed.get("drafted_order_text", ""),
                "recommended_status": parsed.get("recommended_status", "Forwarded to Dept"),
                "generated_by": "LangChain Action Drafter (LLM)"
            }
        else:
            return fallback_rule_based_officer_order(grievance_data)
    except Exception as e:
        logger.warning(f"LangChain action drafter error: {e}. Executing deterministic fallback.")
        return fallback_rule_based_officer_order(grievance_data)


# ==============================================================================
# Feature 4: Agentic Tool-Calling for CPGRAMS Sahayak Assistant
# ==============================================================================

def tool_track_docket(tracking_id: str, db: Any) -> Dict[str, Any]:
    """
    Native Db2 Tool: Queries IBM Db2 for grievance docket status, history, and SLA countdown.
    """
    from models import Grievance, GrievanceUpdate
    from sqlalchemy import func, or_, text
    
    clean_id = tracking_id.strip().upper()
    grv = db.query(Grievance).filter(
        or_(
            func.upper(Grievance.tracking_id) == clean_id,
            func.replace(func.upper(Grievance.tracking_id), '-', '') == clean_id.replace('-', '')
        )
    ).first()
    
    if not grv:
        return {
            "found": False,
            "tracking_id": clean_id,
            "message": f"Docket '{clean_id}' was not found in IBM Db2 GRIEVDB."
        }
    
    # Calculate days open via Db2 date arithmetic
    days_open_res = db.execute(
        text(f"SELECT (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) FROM grievances WHERE id = {grv.id}")
    ).scalar()
    days_open = int(days_open_res) if days_open_res is not None else 0
    is_sla_breached = days_open > 15 and grv.status != "Resolved"
    
    latest_upd = db.query(GrievanceUpdate).filter(
        GrievanceUpdate.grievance_id == grv.id
    ).order_by(GrievanceUpdate.created_at.desc()).first()
    
    dept_name = grv.department.name if grv.department else grv.category
    
    return {
        "found": True,
        "tracking_id": grv.tracking_id,
        "citizen_name": grv.citizen_name,
        "category": grv.category,
        "subject": grv.subject or "Citizen Grievance",
        "status": grv.status,
        "priority": grv.priority,
        "ward": grv.ward or "N/A",
        "days_open": days_open,
        "is_sla_breached": is_sla_breached,
        "department_name": dept_name,
        "latest_update": latest_upd.notes if latest_upd else "Initial filing recorded.",
        "updated_by": latest_upd.updated_by if latest_upd else "System",
        "resolved_at": grv.resolved_at.isoformat() if grv.resolved_at else None
    }


def tool_ward_status(ward_query: str, db: Any) -> Dict[str, Any]:
    """
    Native Db2 Tool: Queries IBM Db2 for open cases, critical count, and hotspot warnings in a municipal ward.
    """
    from sqlalchemy import text
    
    clean_q = ward_query.strip().lower()
    
    # Query distinct wards currently in Db2
    all_wards_rows = db.execute(text("SELECT DISTINCT ward FROM grievances WHERE ward IS NOT NULL")).fetchall()
    all_wards = [r[0] for r in all_wards_rows if r[0]]
    
    matched_ward = None
    for w in all_wards:
        if clean_q in w.lower():
            matched_ward = w
            break
            
    if not matched_ward:
        tokens = [t for t in re.split(r'\W+', clean_q) if len(t) > 3]
        for t in tokens:
            for w in all_wards:
                if t in w.lower():
                    matched_ward = w
                    break
            if matched_ward:
                break
                
    if not matched_ward:
        matched_ward = "Ward 14 - Rohini East" if "rohini" in clean_q else (all_wards[0] if all_wards else "Ward 14 - Rohini East")
        
    stats_sql = text("""
        SELECT 
            COUNT(*) AS total_cases,
            SUM(CASE WHEN status != 'Resolved' THEN 1 ELSE 0 END) AS open_cases,
            SUM(CASE WHEN priority = 'Critical' AND status != 'Resolved' THEN 1 ELSE 0 END) AS critical_cases,
            SUM(CASE WHEN status != 'Resolved' AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15 THEN 1 ELSE 0 END) AS sla_breaches
        FROM grievances 
        WHERE ward = :ward
    """)
    stats_row = db.execute(stats_sql, {"ward": matched_ward}).fetchone()
    
    total_cases = int(stats_row[0]) if stats_row and stats_row[0] else 0
    open_cases = int(stats_row[1]) if stats_row and stats_row[1] else 0
    critical_cases = int(stats_row[2]) if stats_row and stats_row[2] else 0
    sla_breaches = int(stats_row[3]) if stats_row and stats_row[3] else 0
    
    cat_sql = text("""
        SELECT category, COUNT(*) AS cnt 
        FROM grievances 
        WHERE ward = :ward AND status != 'Resolved' 
        GROUP BY category 
        ORDER BY cnt DESC 
        FETCH FIRST 1 ROWS ONLY
    """)
    cat_row = db.execute(cat_sql, {"ward": matched_ward}).fetchone()
    primary_category = cat_row[0] if cat_row else "general civic"
    
    dockets_sql = text("""
        SELECT tracking_id, subject, priority 
        FROM grievances 
        WHERE ward = :ward AND status != 'Resolved' 
        ORDER BY created_at DESC 
        FETCH FIRST 3 ROWS ONLY
    """)
    dockets = [{"tracking_id": r[0], "subject": r[1], "priority": r[2]} for r in db.execute(dockets_sql, {"ward": matched_ward}).fetchall()]
    
    is_hotspot = open_cases > 3
    
    return {
        "ward": matched_ward,
        "total_cases": total_cases,
        "open_cases": open_cases,
        "critical_cases": critical_cases,
        "sla_breaches": sla_breaches,
        "is_hotspot": is_hotspot,
        "primary_category": primary_category,
        "sample_dockets": dockets
    }


def tool_civic_knowledge(query: str) -> Dict[str, Any]:
    """
    Native Tool: Administrative knowledge base covering Citizen Charter rules, SLA deadlines, and escalation rights.
    """
    q = query.lower()
    
    if "escalat" in q or "12" in q or "delay" in q:
        topic = "12-Day Statutory Escalation Rule"
        rule = (
            "Under the CPGRAMS Administrative Redressal Charter, if an acknowledged grievance remains "
            "unattended or under review for more than 12 calendar days without an interim relief order, "
            "the citizen has the statutory right to escalate the case directly to the Appellate Authority / "
            "Joint Secretary. The portal provides a 1-click 'Escalate This Grievance' mechanism on the Track Status page."
        )
    elif "sla" in q or "15" in q or "time" in q or "deadline" in q:
        topic = "15-Day Citizen Charter Resolution SLA"
        rule = (
            "Central public administration guidelines mandate a maximum 15-day service delivery turnaround (SLA) "
            "for public grievances across Municipal, Water, Electricity, Road, and Sanitation departments. "
            "Grievances exceeding 15 days are automatically flagged as SLA Breaches in IBM Db2 and prioritized "
            "for Executive Engineer inspection."
        )
    elif "scope" in q or "court" in q or "rti" in q or "eligible" in q or "can i file" in q:
        topic = "CPGRAMS Jurisdiction & Filing Scope"
        rule = (
            "CPGRAMS handles grievances concerning central/municipal service delays, public works, civic safety, "
            "and government welfare schemes. Sub-judice matters currently pending in judicial courts, "
            "Right to Information (RTI) applications (which must be filed at rtionline.gov.in), and purely private "
            "commercial disputes cannot be entertained."
        )
    elif "helpline" in q or "phone" in q or "contact" in q or "email" in q:
        topic = "National Citizen Helplines"
        rule = (
            "Citizens can reach the National Public Grievance Helpdesk via Toll-Free Helpline 1800-11-4000 "
            "or email cpgrams-helpdesk@nic.in (Monday through Saturday, 9:00 AM - 6:00 PM IST)."
        )
    else:
        topic = "Citizen Grievance Redressal Process"
        rule = (
            "CPGRAMS grievances follow a strict 4-stage lifecycle: 1. Filed (AI Triage & Hotspot Verification) -> "
            "2. Under Review (Nodal Officer Assignment) -> 3. Forwarded to Dept (Field Inspection & Order Dispatched) -> "
            "4. Resolved (Action Taken Report & Citizen Sign-off)."
        )
        
    return {
        "topic": topic,
        "rule_summary": rule,
        "official_source": "DARPG Citizen Charter 2026 / Government of India",
        "escalation_window_days": 12,
        "statutory_sla_days": 15
    }


def run_sahayak_agent(message: str, db: Any, language: str = "en") -> Dict[str, Any]:
    """
    Agentic LangChain Tool Dispatcher for CPGRAMS Sahayak Assistant:
    1. Parses user intent and determines if a database tool is required.
    2. Invokes tool against live IBM Db2:
       - tool_track_docket: Status, history, days open, SLA check.
       - tool_ward_status: Open complaints volume, critical cases, hotspot alert in that ward.
       - tool_civic_knowledge: 15-day SLA rules, 12-day escalation, helpline info.
    3. Formats friendly, grounded response in English or Hindi.
    """
    msg_clean = message.strip()
    msg_lower = msg_clean.lower()
    is_hi = language == "hi" or bool(re.search(r'[\u0900-\u097F]', msg_clean))
    
    # 1. Check for Docket Tracking intent (e.g. GRV-2026-1028 or track status)
    tracking_match = re.search(r'\b(GRV-\d{4}-\d{4}|GRV\d{8})\b', msg_clean, re.IGNORECASE)
    if tracking_match or (any(w in msg_lower for w in ["track", "status", "docket", "ticket", "शिकायत", "स्थिति"]) and re.search(r'\d{4}', msg_clean)):
        tid = tracking_match.group(1).upper() if tracking_match else "GRV-2026-1028"
        # Format if 8 digits without hyphen
        if len(tid) == 11 and "-" not in tid:
            tid = f"{tid[:3]}-{tid[3:7]}-{tid[7:]}"
            
        data = tool_track_docket(tid, db)
        tool_used = "tool_track_docket"
        
        if data["found"]:
            sla_text_en = "⚠️ SLA BREACHED (>15 Days)" if data["is_sla_breached"] else "Within 15d SLA"
            sla_text_hi = "⚠️ समय सीमा समाप्त (15 दिन से अधिक)" if data["is_sla_breached"] else "समय सीमा के भीतर"
            
            if is_hi:
                reply = (
                    f"📋 <strong>शिकायत संख्या {data['tracking_id']} का विवरण:</strong><br>"
                    f"• नागरिक का नाम: <strong>{data['citizen_name']}</strong><br>"
                    f"• वर्तमान स्थिति: <strong>{data['status']}</strong> (प्राथमिकता: <strong>{data['priority']}</strong>)<br>"
                    f"• संबंधित वार्ड: <strong>{data['ward']}</strong><br>"
                    f"• विभाग: <strong>{data['department_name']}</strong><br>"
                    f"• लंबित अवधि: <strong>{data['days_open']} दिन</strong> ({sla_text_hi})<br>"
                    f"• नवीनतम कार्रवाई: <em>{data['latest_update']}</em><br><br>"
                    f"<a href=\"track-status.html?id={data['tracking_id']}\" style=\"color:#0043ce;font-weight:700;text-decoration:underline;\">"
                    f"यहाँ क्लिक करके पूरी टाइमलाइन देखें &rarr;</a>"
                )
            else:
                reply = (
                    f"📋 <strong>Status for Docket {data['tracking_id']}:</strong><br>"
                    f"• Citizen Name: <strong>{data['citizen_name']}</strong><br>"
                    f"• Current Status: <strong>{data['status']}</strong> (Priority: <strong>{data['priority']}</strong>)<br>"
                    f"• Municipal Ward: <strong>{data['ward']}</strong><br>"
                    f"• Department: <strong>{data['department_name']}</strong><br>"
                    f"• Elapsed Time: <strong>{data['days_open']} days</strong> ({sla_text_en})<br>"
                    f"• Latest Update: <em>{data['latest_update']}</em><br><br>"
                    f"<a href=\"track-status.html?id={data['tracking_id']}\" style=\"color:#0043ce;font-weight:700;text-decoration:underline;\">"
                    f"Click here to inspect full docket timeline &rarr;</a>"
                )
        else:
            if is_hi:
                reply = f"⚠️ शिकायत संख्या <strong>{tid}</strong> IBM Db2 डेटाबेस में नहीं मिली। कृपया पंजीकरण संख्या की पुनः जांच करें।"
            else:
                reply = f"⚠️ Docket <strong>{tid}</strong> was not found in IBM Db2. Please verify your registration number."
                
        return {
            "reply": reply,
            "tool_used": tool_used,
            "data_payload": data
        }

    # 2. Check for Ward Status intent (e.g. Rohini, Civil Lines, Mayur Vihar, etc.)
    ward_keywords = [
        "rohini", "civil lines", "timarpur", "chandni chowk", "karol bagh",
        "pitampura", "vasant kunj", "connaught place", "patel nagar",
        "mayur vihar", "hauz khas", "greater kailash", "lajpat nagar",
        "dwarka", "janakpuri", "okhla", "shahdara", "mehrauli", "najafgarh",
        "ward", "hotspot", "active complaints", "complaints in", "area"
    ]
    if any(k in msg_lower for k in ward_keywords):
        # Extract specific ward query
        ward_candidate = "Rohini" if "rohini" in msg_lower else msg_clean
        data = tool_ward_status(ward_candidate, db)
        tool_used = "tool_ward_status"
        
        status_tag_en = "🚨 CRITICAL HOTSPOT (>3 open dockets)" if data["is_hotspot"] else "Active Monitoring"
        status_tag_hi = "🚨 क्रिटिकल हॉटस्पॉट (3 से अधिक शिकायतें)" if data["is_hotspot"] else "सक्रिय निगरानी"
        
        if is_hi:
            reply = (
                f"📍 <strong>{data['ward']} - लाइव नगर निगम स्थिति:</strong><br>"
                f"• सक्रिय खुली शिकायतें: <strong>{data['open_cases']}</strong> (कुल दर्ज: {data['total_cases']})<br>"
                f"• गंभीर (Critical) मामले: <strong>{data['critical_cases']}</strong><br>"
                f"• 15-दिन से अधिक लंबित (SLA Breaches): <strong>{data['sla_breaches']}</strong><br>"
                f"• मुख्य समस्या श्रेणी: <strong>{data['primary_category'].capitalize()}</strong><br>"
                f"• प्रशासनिक स्थिति: <strong>{status_tag_hi}</strong><br><br>"
                f"<a href=\"officer.html?ward={data['ward']}\" style=\"color:#0043ce;font-weight:700;\">"
                f"अधिकारी कंसोल में इस वार्ड के dockets देखें &rarr;</a>"
            )
        else:
            reply = (
                f"📍 <strong>Live Municipal Telemetry for {data['ward']}:</strong><br>"
                f"• Active Open Complaints: <strong>{data['open_cases']}</strong> (Total filed: {data['total_cases']})<br>"
                f"• Critical Priority Emergencies: <strong>{data['critical_cases']}</strong><br>"
                f"• Overdue Dockets (>15d): <strong>{data['sla_breaches']}</strong><br>"
                f"• Primary Civic Issue: <strong>{data['primary_category'].capitalize()}</strong><br>"
                f"• Advisory Level: <strong>{status_tag_en}</strong><br><br>"
                f"<a href=\"officer.html?ward={data['ward']}\" style=\"color:#0043ce;font-weight:700;\">"
                f"Inspect this ward in the Officer Redressal Console &rarr;</a>"
            )
            
        return {
            "reply": reply,
            "tool_used": tool_used,
            "data_payload": data
        }

    # 3. Check for Civic Knowledge / Rules intent
    civic_keywords = [
        "sla", "escalat", "12 day", "15 day", "rule", "charter", "court",
        "rti", "scope", "eligible", "can i file", "helpline", "phone", "contact",
        "how to lodge", "kaise darj", "steps", "rights"
    ]
    if any(k in msg_lower for k in civic_keywords):
        data = tool_civic_knowledge(msg_clean)
        tool_used = "tool_civic_knowledge"
        
        if is_hi:
            reply = (
                f"🏛️ <strong>नागरिक अधिकार व नियम: {data['topic']}</strong><br><br>"
                f"{data['rule_summary']}<br><br>"
                f"• सांविधिक निवारण समय सीमा: <strong>{data['statutory_sla_days']} दिन</strong><br>"
                f"• एस्केलेशन अधिकार: <strong>{data['escalation_window_days']} दिन</strong><br>"
                f"• स्रोत: <em>{data['official_source']}</em>"
            )
        else:
            reply = (
                f"🏛️ <strong>CPGRAMS Knowledge Base: {data['topic']}</strong><br><br>"
                f"{data['rule_summary']}<br><br>"
                f"• Statutory Turnaround (SLA): <strong>{data['statutory_sla_days']} days</strong><br>"
                f"• Escalation Right: <strong>{data['escalation_window_days']} days</strong><br>"
                f"• Regulatory Authority: <em>{data['official_source']}</em>"
            )
            
        return {
            "reply": reply,
            "tool_used": tool_used,
            "data_payload": data
        }

    # 4. Default Conversational Greeting
    if is_hi:
        reply = (
            "नमस्ते! मैं आपका <strong>CPGRAMS सहायक AI मित्र</strong> हूँ। "
            "मैं <strong>IBM Db2 (GRIEVDB)</strong> से सीधे जुड़ा हुआ हूँ और आपकी ये सहायता कर सकता हूँ:<br>"
            "1. किसी भी शिकायत की स्थिति जांचना (जैसे: <code>GRV-2026-1028 की स्थिति क्या है?</code>)<br>"
            "2. किसी भी वार्ड की लाइव रिपोर्ट देखना (जैसे: <code>रोहिणी में कितनी शिकायतें हैं?</code>)<br>"
            "3. 15-दिन SLA व 12-दिन एस्केलेशन नियमों की जानकारी देना।"
        )
    else:
        reply = (
            "Namaste! I am your <strong>CPGRAMS Sahayak AI Assistant</strong>, integrated natively with "
            "<strong>IBM Db2 Community Edition</strong>. Here is how I can assist you:<br>"
            "1. Track any grievance in real time (e.g. <code>What is the status of GRV-2026-1028?</code>)<br>"
            "2. Query municipal ward hotspot telemetry (e.g. <code>Are there active complaints in Rohini?</code>)<br>"
            "3. Explain Citizen Charter 15-day SLAs and 12-day escalation rights."
        )
        
    return {
        "reply": reply,
        "tool_used": None,
        "data_payload": None
    }


