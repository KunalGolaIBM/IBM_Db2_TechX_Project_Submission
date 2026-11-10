"""
MediTwin AI — Answer Service
Generates evidence-grounded answers using Gemini.
All answers must be backed by retrieved Db2 records.
"""

import os
import json
import logging
from typing import Dict, List, Optional

from services.retrieval_service import RetrievalService, identify_test_code
from services.timeline_service import compute_metric_trend, format_trend_summary

logger = logging.getLogger(__name__)

ANSWER_PROMPT = """You are MediTwin AI, a clinical record intelligence assistant.

CRITICAL MEDICAL SAFETY & EVIDENCE RULES:
1. You are NOT a medical doctor. You NEVER diagnose disease, determine prognosis, or recommend medications/treatments.
2. You ONLY report measurements, dates, and changes explicitly present in the provided Db2 evidence.
3. Every factual claim must reference its source document and date.
4. If the retrieved evidence is insufficient or inconclusive, state clearly: "I could not find sufficient approved records to answer this question."
5. Never invent or speculate about clinical measurements or normal values.
6. This is a synthetic data demonstration prototype.

USER QUESTION:
{question}

RETRIEVED APPROVED DATABASE EVIDENCE:
{evidence_text}

DETERMINISTIC TREND ANALYSIS:
{trend_text}

Provide a concise, professional summary answering the user's question using ONLY the provided evidence.
Always cite the source document, page number, and observation date.
"""


class AnswerService:
    """Generates evidence-grounded answers to patient questions."""

    def __init__(self, repository, api_key: str = None,
                 model_name: str = "gemini-2.0-flash"):
        self.repo = repository
        self.retrieval = RetrievalService(repository)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name

    def answer_question(self, patient_id: int, question: str) -> Dict:
        """
        Answer a patient question using Db2 evidence + Gemini generation.
        Returns structured response with answer, evidence, and sources.
        """
        # Step 1: Parameterized Db2 retrieval
        evidence = self.retrieval.retrieve_evidence_for_question(
            patient_id=patient_id,
            question=question,
        )

        # Step 2: Honest insufficient evidence handling
        if not evidence.get("sufficient_evidence") or not evidence.get("observations"):
            return {
                "answer": "I could not find sufficient approved records to answer this question.",
                "has_evidence": False,
                "evidence_cards": [],
                "sources": [],
                "test_code": evidence.get("test_code_identified"),
                "query_type": evidence.get("query_type", "metric"),
            }

        # Step 3: Compute deterministic trend(s)
        test_code = evidence.get("test_code_identified")
        query_type = evidence.get("query_type", "metric")
        trend = {}
        trend_text_parts = []

        if test_code:
            trend = compute_metric_trend(evidence["observations"], test_code)
            trend_text_parts.append(format_trend_summary(trend))
        elif query_type in ("directional_trend", "panel"):
            # Compute trend for each distinct code present
            codes_in_evidence = list(set(
                (o.get("TEST_CODE") or "").upper() for o in evidence["observations"] if o.get("TEST_CODE")
            ))
            for code in codes_in_evidence:
                sub_trend = compute_metric_trend(evidence["observations"], code)
                if sub_trend.get("count", 0) > 0:
                    trend_text_parts.append(format_trend_summary(sub_trend))

        trend_text = "\n\n".join(trend_text_parts) if trend_text_parts else "No multi-point trend available."

        # Step 4: Build evidence text
        evidence_text = self._format_evidence_text(evidence["observations"])

        # Step 5: Generate grounded answer via Gemini
        answer = self._generate_answer(question, evidence_text, trend_text)

        # Step 6: Build structured evidence cards
        evidence_cards = self._build_evidence_cards(evidence["observations"])

        return {
            "answer": answer,
            "has_evidence": True,
            "evidence_cards": evidence_cards,
            "sources": evidence.get("source_documents", []),
            "test_code": test_code,
            "query_type": query_type,
            "trend": trend,
            "observation_count": len(evidence["observations"]),
        }

    def _format_evidence_text(self, observations: List[Dict]) -> str:
        """Format observations into structured text for LLM grounding."""
        if not observations:
            return "No records found in database."

        lines = []
        for i, obs in enumerate(observations, 1):
            val = obs.get("VALUE_NUMERIC") if obs.get("VALUE_NUMERIC") is not None else obs.get("value_numeric")
            if val is None:
                val = obs.get("VALUE_TEXT") if obs.get("VALUE_TEXT") is not None else obs.get("value_text", "N/A")
            unit = obs.get("UNIT") or obs.get("unit", "")
            date_str = str(obs.get("OBSERVED_AT") or obs.get("observed_at", "unknown date"))
            source = obs.get("FILE_NAME") or obs.get("file_name") or obs.get("source_document_name", "unknown source")
            page = obs.get("SOURCE_PAGE") if obs.get("SOURCE_PAGE") is not None else obs.get("source_page", "")
            snippet = obs.get("SOURCE_SNIPPET") or obs.get("source_snippet", "")
            test_name = obs.get("TEST_NAME") or obs.get("test_name", "Unknown")
            test_code = obs.get("TEST_CODE") or obs.get("test_code", "")

            line = (
                f"Observation {i}: {test_name} ({test_code}) = "
                f"{val} {unit} | Date: {date_str} | Source: {source} (p. {page})"
            )
            if snippet:
                line += f' | Excerpt: "{snippet}"'
            lines.append(line)

        return "\n".join(lines)

    def _generate_answer(self, question: str, evidence_text: str, trend_text: str) -> str:
        """Synthesize response using Gemini with fallback to deterministic summary."""
        if not self.api_key:
            return self._deterministic_answer(evidence_text, trend_text)

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage

            llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0.1,  # Low temperature to eliminate speculation
            )

            prompt = ANSWER_PROMPT.format(
                question=question,
                evidence_text=evidence_text,
                trend_text=trend_text,
            )

            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content

        except Exception as e:
            logger.error(f"Gemini grounded answer generation failed: {e}")
            return self._deterministic_answer(evidence_text, trend_text)

    def _deterministic_answer(self, evidence_text: str, trend_text: str) -> str:
        """Deterministic fallback when Gemini API is unconfigured or unreachable."""
        return (
            f"### Approved Records Retrieved from IBM Db2:\n\n{evidence_text}\n\n"
            f"### Longitudinal Trend Analysis:\n\n{trend_text}\n\n"
            f"---\n"
            f"*Generated via deterministic database retrieval. "
            f"All measurements verified against stored source documents.*"
        )

    def _build_evidence_cards(self, observations: List[Dict]) -> List[Dict]:
        """Build structured evidence cards for UI inspection."""
        cards = []
        for obs in observations:
            val = obs.get("VALUE_NUMERIC") if obs.get("VALUE_NUMERIC") is not None else obs.get("value_numeric")
            if val is None:
                val = obs.get("VALUE_TEXT") if obs.get("VALUE_TEXT") is not None else obs.get("value_text", "N/A")
            cards.append({
                "test_name": obs.get("TEST_NAME") or obs.get("test_name", "Unknown"),
                "test_code": obs.get("TEST_CODE") or obs.get("test_code", ""),
                "value": val,
                "unit": obs.get("UNIT") or obs.get("unit", ""),
                "date": str(obs.get("OBSERVED_AT") or obs.get("observed_at", "")),
                "source_file": obs.get("FILE_NAME") or obs.get("file_name") or obs.get("source_document_name", ""),
                "source_page": obs.get("SOURCE_PAGE") if obs.get("SOURCE_PAGE") is not None else obs.get("source_page"),
                "snippet": obs.get("SOURCE_SNIPPET") or obs.get("source_snippet", ""),
                "review_status": obs.get("REVIEW_STATUS") or obs.get("review_status", "APPROVED"),
            })
        return cards
