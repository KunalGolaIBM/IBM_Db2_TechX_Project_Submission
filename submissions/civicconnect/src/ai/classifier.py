"""
CivicConnect – AI Complaint Classification with LangChain
Uses LangChain's chain composition with IBM watsonx.ai (or a local Ollama fallback)
to classify incoming civic complaints into categories, assign departments,
determine priority, and generate an executive summary for administrators.
"""

import os
import json
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough

# IBM watsonx.ai integration via langchain-ibm
try:
    from langchain_ibm import WatsonxLLM
    _WATSONX_AVAILABLE = True
except ImportError:
    _WATSONX_AVAILABLE = False

# Local Ollama fallback for development / offline use
try:
    from langchain_ollama import ChatOllama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Category → Department mapping (mirrors Db2 DEPARTMENTS seed data)
# ---------------------------------------------------------------------------

CATEGORY_DEPARTMENT_MAP: dict[str, str] = {
    "Garbage Collection":    "Sanitation Department",
    "Road Damage / Potholes": "Public Works Department",
    "Streetlight Problems":  "Electricity Department",
    "Water Leakage":         "Water Supply Department",
    "Drainage and Sewage":   "Drainage Department",
    "Public Property Damage": "Public Works Department",
    "Other Civic Issues":    "Municipal Administration",
}


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a civic AI assistant for a municipal grievance system integrated with IBM Db2.
Your task is to classify a citizen's complaint into one of the predefined categories and return structured JSON.

Categories (use EXACT strings):
1. "Garbage Collection"
2. "Road Damage / Potholes"
3. "Streetlight Problems"
4. "Water Leakage"
5. "Drainage and Sewage"
6. "Public Property Damage"
7. "Other Civic Issues"

Priority levels: "low" | "medium" | "high" | "urgent"
- urgent: immediate safety hazard (open manhole, live wire, burst main)
- high:   severe infrastructure failure (deep pothole, heavy sewer overflow)
- medium: standard civic defect requiring scheduled repair
- low:    minor cosmetic issue or nuisance

Return ONLY valid JSON in this exact structure:
{{
  "category": "<exact category string>",
  "department": "<corresponding department>",
  "priority": "<priority level>",
  "keywords": ["<term1>", "<term2>", "<term3>"],
  "summary": "<1-2 sentence factual summary for administrators>"
}}""",
    ),
    (
        "human",
        "Complaint Title: {title}\n\nComplaint Description: {description}",
    ),
])


# ---------------------------------------------------------------------------
# Heuristic fallback (zero-dependency)
# ---------------------------------------------------------------------------

def _heuristic_classify(title: str, description: str) -> dict:
    text = f"{title} {description}".lower()
    category = "Other Civic Issues"
    priority = "medium"

    if any(w in text for w in ["pothole", "road", "crater", "asphalt", "pavement"]):
        category = "Road Damage / Potholes"
        priority = "high" if any(w in text for w in ["deep", "accident", "severe", "tire"]) else "medium"
    elif any(w in text for w in ["garbage", "trash", "waste", "dump", "rubbish", "litter"]):
        category = "Garbage Collection"
        priority = "high" if any(w in text for w in ["overflow", "disease", "rotting"]) else "medium"
    elif any(w in text for w in ["light", "streetlight", "lamp", "dark", "spark", "electric"]):
        category = "Streetlight Problems"
        priority = "urgent" if any(w in text for w in ["spark", "exposed", "shock", "fire"]) else "low"
    elif any(w in text for w in ["water", "pipe", "leak", "burst", "pressure", "tap"]):
        category = "Water Leakage"
        priority = "high" if any(w in text for w in ["burst", "flooding", "gushing"]) else "medium"
    elif any(w in text for w in ["drain", "sewage", "gutter", "manhole", "stagnant"]):
        category = "Drainage and Sewage"
        priority = "urgent" if any(w in text for w in ["overflow", "manhole open", "monsoon"]) else "high"
    elif any(w in text for w in ["park", "bench", "bus stop", "shelter", "fence", "wall"]):
        category = "Public Property Damage"
        priority = "low"

    dept = CATEGORY_DEPARTMENT_MAP.get(category, "Municipal Administration")
    words = [w for w in text.replace(",", " ").split() if len(w) > 4]
    keywords = list(dict.fromkeys(words))[:5] or ["civic", "infrastructure"]

    return {
        "category": category,
        "department": dept,
        "priority": priority,
        "keywords": keywords,
        "summary": f"Citizen reported {category.lower()} at the specified location. Recommended for inspection by {dept}.",
        "ai_powered": False,
    }


# ---------------------------------------------------------------------------
# LangChain classification chain builder
# ---------------------------------------------------------------------------

def _build_llm():
    """Return best available LLM: watsonx → Ollama → None."""
    if _WATSONX_AVAILABLE and os.getenv("WATSONX_API_KEY") and os.getenv("WATSONX_PROJECT_ID"):
        return WatsonxLLM(
            model_id=os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2"),
            url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
            project_id=os.getenv("WATSONX_PROJECT_ID"),
            params={
                "decoding_method": "greedy",
                "max_new_tokens": 512,
                "temperature": 0.1,
            },
        )
    if _OLLAMA_AVAILABLE:
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "granite3.3:8b"),
            temperature=0.1,
        )
    return None


def classify_complaint(title: str, description: str) -> dict:
    """
    Classify a civic complaint using LangChain + IBM watsonx.ai (or Ollama).
    Falls back to the heuristic classifier if no LLM is configured.

    Returns a dict with keys: category, department, priority, keywords, summary, ai_powered.
    """
    llm = _build_llm()

    if llm is None:
        return _heuristic_classify(title, description)

    try:
        parser = JsonOutputParser()
        chain = CLASSIFICATION_PROMPT | llm | parser

        result: dict = chain.invoke({"title": title, "description": description})

        # Validate and sanitise output
        category = result.get("category", "Other Civic Issues")
        if category not in CATEGORY_DEPARTMENT_MAP:
            category = "Other Civic Issues"
        dept = CATEGORY_DEPARTMENT_MAP[category]
        priority = result.get("priority", "medium")
        if priority not in ("low", "medium", "high", "urgent"):
            priority = "medium"

        return {
            "category": category,
            "department": dept,
            "priority": priority,
            "keywords": result.get("keywords", [])[:6],
            "summary": result.get("summary", f"{title}: Reported for municipal inspection."),
            "ai_powered": True,
        }
    except Exception:
        # Always fall back; never block complaint submission
        return _heuristic_classify(title, description)
