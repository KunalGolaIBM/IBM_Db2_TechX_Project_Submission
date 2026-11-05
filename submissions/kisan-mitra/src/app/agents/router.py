"""
Multi-Intent Router Agent for Kisan Mitra (किसान मित्र)
Classifies user queries into SQL, RAG, or HYBRID intents,
orchestrating execution across the Db2 Text-to-SQL Agent and Db2 Native Vector RAG Agent.
"""

import re
from typing import Dict, Any, Literal
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.sql_agent import get_sql_agent
from app.agents.rag_agent import get_rag_agent
from app.agents.llm import get_llm

ROUTER_PROMPT = """You are an intelligent triage agent for Kisan Mitra (किसान मित्र), an AI assistant for Indian farmers.
Your job is to classify the user's question into EXACTLY ONE of three routing categories:

1. SQL: The user is asking about daily mandi prices, commodity rates, market arrivals, historical price comparisons, or price trends.
   Examples:
   - "Mathura mandi me aaj aloo ka bhav kya hai?"
   - "UP me pichhle hafte sabse mehnga anaaj kaunsa tha?"
   - "Agra aur Aligarh me sarson ke bhav me kya antar hai?"
   - "What was the highest wheat price in Lucknow last week?"

2. RAG: The user is asking about Government Welfare Schemes (PM-KISAN, PMFBY crop insurance, Kisan Credit Card), eligibility rules, subsidy rates, application procedures, or claim processes.
   Examples:
   - "PM-KISAN me kon aavedan nahi kar sakta?"
   - "Fasal kharab hone par PMFBY me claim kaise karein?"
   - "KCC par kitna byaj lagta hai aur kitna loan milta hai?"
   - "What are the exclusion criteria for PM-KISAN?"

3. HYBRID: The user is asking a composite question requiring BOTH Mandi price intelligence AND Government scheme rules in the same query.
   Examples:
   - "Agra me gehun ka kya bhav hai aur fasal kharab hone par PMFBY claim kaise karein?"
   - "Mathura me aalu ka rate bataiye aur kya mujhe PM-KISAN ka labh mil sakta hai?"

Reply with ONLY ONE WORD: 'SQL', 'RAG', or 'HYBRID'. Do not add any punctuation or explanation.
"""

class KisanMitraRouter:
    """Orchestrates query routing between Relational Db2 Text-to-SQL and Native Db2 Vector RAG."""

    def __init__(self):
        self.sql_agent = get_sql_agent()
        self.rag_agent = get_rag_agent()
        self.llm = get_llm(temperature=0.0)

    def classify_intent(self, question: str) -> Literal["SQL", "RAG", "HYBRID"]:
        """Classify user intent using LLM with deterministic keyword heuristics guard."""
        q_lower = question.lower()
        
        # Fast heuristic checks (Latin and Devanagari)
        has_sql_kw = any(w in q_lower for w in [
            "bhav", "price", "rate", "mandi", "mehnga", "sasta", "kimat", "aloo", "potato",
            "gehun", "wheat", "sarson", "mustard", "tamatar", "tomato", "pyaz", "onion",
            "chawal", "rice", "dhan", "quintal", "rupaye", "anaaj", "भाव", "मंडी", "आलू",
            "गेहूं", "सरसों", "दाम", "दर", "टमाटर", "प्याज", "चावल", "अनाज"
        ])
        has_rag_kw = any(w in q_lower for w in [
            "pm-kisan", "pmkisan", "pmfby", "fasal bima", "crop insurance", "kcc", "kisan credit card",
            "yojana", "scheme", "eligibility", "patrata", "aptrata", "exclusion", "claim", "subsidy",
            "loan", "byaj", "interest", "insurance", "beema", "bima", "72 ghante", "72 hours",
            "पीएम किसान", "सम्मान निधि", "फसल बीमा", "क्रेडिट कार्ड", "केसीसी", "योजना",
            "अपात्र", "पात्रता", "आवेदन", "ब्याज", "ऋण", "सब्सिडी", "क्लेम", "नष्ट"
        ])

        if has_sql_kw and has_rag_kw:
            return "HYBRID"
        if has_rag_kw and not has_sql_kw:
            return "RAG"
        if has_sql_kw and not has_rag_kw:
            return "SQL"

        # Check for greeting or out-of-scope queries
        is_greeting_or_irrelevant = any(w in q_lower for w in [
            "hello", "hi", "namaste", "नमस्ते", "हेलो", "who are you", "kaun ho", "help",
            "kya kar sakte", "मदद", "cricket", "weather", "bitcoin", "football", "movie"
        ])
        if is_greeting_or_irrelevant or (not has_sql_kw and not has_rag_kw and len(q_lower.split()) < 3):
            return "OUT_OF_SCOPE"
        
        # Invoke Router LLM with fallback
        messages = [
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=f"Classify the user question into exactly one category: {question}")
        ]
        try:
            res = self.llm.invoke(messages)
            verdict = res.content.strip().upper()
        except Exception:
            from app.agents.llm import MockOfflineChatModel
            res = MockOfflineChatModel().invoke(messages)
            verdict = res.content.strip().upper()
        
        if "HYBRID" in verdict:
            return "HYBRID"
        elif "RAG" in verdict:
            return "RAG"
        elif "SQL" in verdict:
            return "SQL"
        
        # Fallback to heuristic
        if has_rag_kw:
            return "RAG"
        return "SQL"

    def run(self, question: str) -> Dict[str, Any]:
        """Execute appropriate agent based on classified intent."""
        intent = self.classify_intent(question)

        if intent == "OUT_OF_SCOPE":
            help_msg = (
                "**नमस्ते किसान भाई! 🙏 मैं किसान मित्र (Kisan Mitra) हूँ।**\n\n"
                "मैं IBM Db2 द्वारा संचालित आपका कृषि AI सहायक हूँ। मैं निम्नलिखित विषयों में आपकी सहायता कर सकता हूँ:\n\n"
                "1. **🌾 मंडी भाव (Text-to-SQL)**:\n"
                "   - *उदा.*: 'मथुरा मंडी में आलू का भाव क्या है?'\n"
                "   - *उदा.*: 'UP में पिछले हफ्ते सबसे महंगा अनाज कौनसा था?'\n\n"
                "2. **📋 सरकारी योजनाएं (Native Db2 Vector Search)**:\n"
                "   - **PM-KISAN**: ₹6,000 की किस्त, पात्रता व अपात्रता (Exclusion) नियम\n"
                "   - **PMFBY**: फसल नुकसान पर 72 घंटे में क्लेम व मुआवजा प्रक्रिया\n"
                "   - **KCC**: किसान क्रेडिट कार्ड पर 4% ब्याज व ₹1.60 लाख तक बिना गारंटी ऋण\n\n"
                "कृपया अपनी फसल, मंडी या सरकारी योजना से जुड़ा कोई प्रश्न पूछें!"
            )
            return {
                "question": question,
                "intent": "OUT_OF_SCOPE",
                "answer": help_msg,
                "generated_sql": None,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "latency_ms": 0.0,
                "chart_json": None,
                "sources": [],
                "chunks": [],
                "engine": self.sql_agent.db.engine_type,
                "error": None,
            }

        elif intent == "SQL":
            result = self.sql_agent.run(question)
            result["intent"] = "SQL"
            result["sources"] = []
            return result

        elif intent == "RAG":
            result = self.rag_agent.run(question)
            result["intent"] = "RAG"
            result["generated_sql"] = None
            result["rows"] = []
            result["columns"] = []
            result["chart_json"] = None
            result["latency_ms"] = 0.0
            return result

        else: # HYBRID
            sql_res = self.sql_agent.run(question)
            rag_res = self.rag_agent.run(question)

            combined_answer = (
                f"### 🌾 मंडी भाव (Mandi Intelligence)\n"
                f"{sql_res.get('answer', '')}\n\n"
                f"---\n\n"
                f"### 📋 सरकारी योजना परामर्श (Scheme Advisory)\n"
                f"{rag_res.get('answer', '')}"
            )

            return {
                "question": question,
                "intent": "HYBRID",
                "answer": combined_answer,
                "generated_sql": sql_res.get("generated_sql"),
                "columns": sql_res.get("columns", []),
                "rows": sql_res.get("rows", []),
                "row_count": sql_res.get("row_count", 0),
                "latency_ms": sql_res.get("latency_ms", 0.0),
                "chart_json": sql_res.get("chart_json"),
                "sources": rag_res.get("sources", []),
                "chunks": rag_res.get("chunks", []),
                "engine": sql_res.get("engine"),
                "error": sql_res.get("error"),
            }


def get_router() -> KisanMitraRouter:
    """Factory helper for KisanMitraRouter."""
    return KisanMitraRouter()
