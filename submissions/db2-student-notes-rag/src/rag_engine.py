"""
Production RAG Engine for Student Exam Notes.
Orchestrates IBM Db2 Vector Search retrieval, prompt engineering,
and multi-LLM synthesis (IBM watsonx.ai, Gemini, OpenAI, Ollama, or local).
"""

import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import Db2RAGConfig
from db2_client import get_or_create_vector_store
from chunker import StudentNotesChunker

logger = logging.getLogger("rag_engine")


STUDENT_SYSTEM_PROMPT = """You are an expert Professor and AI Exam Tutor specializing in engineering and computer science.
A student is asking you a technical question. Use ONLY the provided context notes retrieved from IBM Db2 Vector Search to answer.

Guidelines:
1. Provide a clear, thorough, exam-ready answer.
2. If mathematical formulas or derivations are in the notes, display them clearly (use LaTeX notation like $$...$$ or $...$).
3. Highlight key definitions, practical implications, and limitations.
4. Reference the specific note sections (e.g., "[Section: Friis Transmission Equation]").
5. If the notes do not contain sufficient information to answer the question, state honestly what is covered in the notes and what is missing.
"""


class StudentNotesRAG:
    """End-to-end RAG orchestrator backed by IBM Db2 Native Vector Search."""

    def __init__(self, vector_store=None):
        self.vector_store = vector_store or get_or_create_vector_store()
        # Auto-index default notes if running in fallback mode with an empty store
        if hasattr(self.vector_store, "documents") and not self.vector_store.documents:
            default_notes = Path(__file__).resolve().parent.parent / "data" / "notes.md"
            if default_notes.is_file():
                try:
                    self.index_notes_file(str(default_notes))
                except Exception as e:
                    logger.debug(f"Auto-index skipped: {e}")

    def index_notes_file(self, file_path: str) -> int:
        """Parse, chunk, and embed a notes document into IBM Db2 vector store."""
        chunker = StudentNotesChunker(
            chunk_size=Db2RAGConfig.CHUNK_SIZE,
            chunk_overlap=Db2RAGConfig.CHUNK_OVERLAP,
        )
        documents = chunker.process_file(file_path)
        logger.info(f"Chunked notes into {len(documents)} semantic document pieces.")
        self.vector_store = get_or_create_vector_store(documents=documents)
        return len(documents)

    def retrieve_relevant_notes(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query IBM Db2 vector store for top-k similar notes."""
        top_k = k or Db2RAGConfig.TOP_K
        results = []

        try:
            if hasattr(self.vector_store, "similarity_search_with_score"):
                hits = self.vector_store.similarity_search_with_score(query, k=top_k)
                for doc, score in hits:
                    results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": round(float(score), 4)
                    })
            else:
                docs = self.vector_store.similarity_search(query, k=top_k)
                for doc in docs:
                    results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": 1.0
                    })
        except Exception as e:
            logger.error(f"Db2 similarity search failed: {e}")

        return results

    def _call_gemini(self, prompt: str) -> Optional[str]:
        """Generate response via Google Gemini API."""
        if not Db2RAGConfig.GEMINI_API_KEY:
            return None
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{Db2RAGConfig.GEMINI_MODEL}:generateContent?key={Db2RAGConfig.GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": f"{STUDENT_SYSTEM_PROMPT}\n\n{prompt}"}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning(f"Gemini LLM call failed: {e}")
            return None

    def _call_watsonx(self, prompt: str) -> Optional[str]:
        """Generate response via IBM watsonx.ai Granite model."""
        if not Db2RAGConfig.WATSONX_APIKEY or not Db2RAGConfig.WATSONX_PROJECT_ID:
            return None
        try:
            # 1. Exchange IAM API Key for Bearer token
            iam_url = "https://iam.cloud.ibm.com/identity/token"
            iam_data = f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={Db2RAGConfig.WATSONX_APIKEY}".encode("utf-8")
            iam_req = urllib.request.Request(iam_url, data=iam_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(iam_req, timeout=15) as iam_res:
                token = json.loads(iam_res.read().decode("utf-8"))["access_token"]

            # 2. Call watsonx text generation
            gen_url = f"{Db2RAGConfig.WATSONX_URL}/ml/v1/text/generation?version=2024-05-31"
            payload = {
                "model_id": Db2RAGConfig.WATSONX_MODEL_ID,
                "project_id": Db2RAGConfig.WATSONX_PROJECT_ID,
                "input": f"{STUDENT_SYSTEM_PROMPT}\n\n{prompt}",
                "parameters": {"decoding_method": "greedy", "max_new_tokens": 1000}
            }
            gen_req = urllib.request.Request(
                gen_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(gen_req, timeout=30) as gen_res:
                data = json.loads(gen_res.read().decode("utf-8"))
                return data["results"][0]["generated_text"]
        except Exception as e:
            logger.warning(f"watsonx.ai generation call failed: {e}")
            return None

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Generate response via local Ollama instance."""
        try:
            url = f"{Db2RAGConfig.OLLAMA_BASE_URL}/api/generate"
            payload = {
                "model": Db2RAGConfig.OLLAMA_MODEL,
                "prompt": f"{STUDENT_SYSTEM_PROMPT}\n\n{prompt}",
                "stream": False
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response")
        except Exception as e:
            logger.debug(f"Ollama call failed or not running: {e}")
            return None

    def _offline_synthesizer(self, query: str, retrieved_notes: List[Dict[str, Any]]) -> str:
        """
        Synthesizes an exam-focused answer directly from retrieved Db2 vector chunks
        when no external cloud API key is configured.
        """
        if not retrieved_notes:
            return "No matching notes found in IBM Db2 vector store for this question."

        lines = [
            f"### 📘 Exam Study Response (Derived from IBM Db2 Vector Search)\n",
            f"**Question:** {query}\n\n",
            "**Key Concepts & Summary from Your Notes:**\n"
        ]

        for i, item in enumerate(retrieved_notes[:3], 1):
            meta = item.get("metadata", {})
            title = meta.get("section_title", "General")
            topic = meta.get("topic", "Exam Notes")
            score = item.get("score", 0.0)
            score_text = f" (Cosine Similarity: {score:.2f})" if score else ""
            lines.append(f"#### {i}. {title}{score_text}")
            lines.append(f"*Category: {topic}*\n")
            lines.append(item["content"])
            lines.append("\n---\n")

        lines.append(
            "\n💡 **Exam Preparation Tip:** Pay close attention to definitions, unit notations (dB/dBm/Watts), "
            "and stated boundary assumptions in the sections above."
        )
        return "\n".join(lines)

    def answer_question(self, query: str, k: Optional[int] = None) -> Dict[str, Any]:
        """
        Main RAG pipeline:
        1. Embeds the student's question
        2. Retrieves nearest notes from IBM Db2 Vector Store
        3. Assembles prompt and queries LLM (or offline synthesizer)
        4. Returns structured answer with source citations
        """
        retrieved = self.retrieve_relevant_notes(query, k=k)

        if not retrieved:
            return {
                "question": query,
                "answer": "No relevant notes were retrieved from the IBM Db2 database. Please make sure notes have been ingested.",
                "retrieved_count": 0,
                "sources": [],
                "provider": "none"
            }

        # Build context block
        context_parts = []
        for idx, hit in enumerate(retrieved, 1):
            meta = hit["metadata"]
            title = meta.get("section_title", "Note Section")
            context_parts.append(f"[Document {idx} - Section: {title}]\n{hit['content']}\n")

        context_str = "\n".join(context_parts)
        user_prompt = f"RETRIEVED NOTES FROM IBM Db2:\n{context_str}\n\nSTUDENT QUESTION:\n{query}\n\nEXAM-FOCUSED ANSWER:"

        # Try providers in order of preference
        answer = None
        provider = "local_synthesizer"

        # 1. Watsonx if configured
        if Db2RAGConfig.WATSONX_APIKEY:
            answer = self._call_watsonx(user_prompt)
            if answer:
                provider = f"watsonx.ai ({Db2RAGConfig.WATSONX_MODEL_ID})"

        # 2. Gemini if configured
        if not answer and Db2RAGConfig.GEMINI_API_KEY:
            answer = self._call_gemini(user_prompt)
            if answer:
                provider = f"Google Gemini ({Db2RAGConfig.GEMINI_MODEL})"

        # 3. Ollama local
        if not answer:
            answer = self._call_ollama(user_prompt)
            if answer:
                provider = f"Ollama ({Db2RAGConfig.OLLAMA_MODEL})"

        # 4. Fallback offline synthesis
        if not answer:
            answer = self._offline_synthesizer(query, retrieved)
            provider = "Db2 Direct Semantic Synthesizer"

        return {
            "question": query,
            "answer": answer,
            "retrieved_count": len(retrieved),
            "sources": [
                {
                    "section_title": h["metadata"].get("section_title", "Unknown"),
                    "topic": h["metadata"].get("topic", "General"),
                    "score": h.get("score"),
                    "doc_id": h["metadata"].get("doc_id"),
                    "has_formula": h["metadata"].get("has_formula", False),
                    "snippet": h["content"][:200] + "..."
                }
                for h in retrieved
            ],
            "provider": provider,
            "db2_table": Db2RAGConfig.DB2_TABLE_NAME
        }
