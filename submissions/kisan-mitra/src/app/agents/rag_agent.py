"""
Native Db2 Vector RAG Agent for Kisan Mitra (किसान मित्र)
Retrieves official scheme guidelines from IBM Db2 DOC_CHUNKS using VECTOR_DISTANCE (Cosine metric)
and synthesizes grounded answers with strict document and page citations.
"""

from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from app.db_client import get_db_client
from app.agents.embedder import get_embedder
from app.agents.llm import get_llm

RAG_SYSTEM_PROMPT = """You are Kisan Mitra (किसान मित्र), an official AI agricultural advisor for Indian farmers.
Your job is to provide accurate, reliable answers about Government Welfare Schemes (PM-KISAN, PMFBY, KCC)
based STRICTLY on the official policy guideline excerpts retrieved from IBM Db2 Vector Search.

Grounding & Citation Rules:
1. Answer ONLY using the facts present in the retrieved official document chunks below. Do not speculate or invent numbers.
2. Reply in the user's language (Hindi Devanagari, Hinglish, or English).
3. Always include transparent source citations specifying the exact Document Name and Page Number for every key fact.
4. If the retrieved context does not contain the answer, politely state that the official documents do not contain that specific detail and recommend contacting the helpline.
5. Format key terms and monetary numbers in bold (e.g., **₹6,000/-**, **72 घंटे**, **4% वार्षिक ब्याज**).
"""

class RagAgent:
    """Agent that performs semantic retrieval via IBM Db2 VECTOR_DISTANCE and synthesizes grounded answers."""

    def __init__(self):
        self.db = get_db_client(read_only=True)
        self.embedder = get_embedder()
        self.llm = get_llm(temperature=0.1)

    def retrieve_chunks(self, query: str, top_k: int = 4, scheme_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Encode query and perform native Db2 vector similarity search."""
        query_vec = self.embedder.encode(query)
        chunks = self.db.vector_search(query_vec, top_k=top_k, scheme_filter=scheme_filter)
        return chunks

    def run(self, question: str, scheme_filter: Optional[str] = None) -> Dict[str, Any]:
        """End-to-end RAG pipeline: Query -> Embedding -> Db2 Vector Search -> Grounded Synthesis."""
        # 1. Retrieve top matching chunks
        chunks = self.retrieve_chunks(question, top_k=4, scheme_filter=scheme_filter)
        
        if not chunks:
            return {
                "question": question,
                "answer": "क्षमा करें, इस विषय पर डेटाबेस में कोई आधिकारिक दिशानिर्देश नहीं मिले।",
                "sources": [],
                "chunks": [],
                "engine": self.db.engine_type,
            }

        # 2. Build context string with citation markers
        context_blocks = []
        sources = []
        for idx, c in enumerate(chunks, start=1):
            doc = c.get("doc_name", "Unknown")
            page = c.get("page_number", 1)
            dist = c.get("distance", 0.0)
            text = c.get("chunk_text", "")
            
            context_blocks.append(f"[Excerpt {idx} - Source: {doc}, Page: {page}, Cosine Distance: {dist:.4f}]\n{text}\n")
            sources.append({
                "source_id": idx,
                "doc_name": doc,
                "scheme_name": c.get("scheme_name", ""),
                "page_number": page,
                "distance": round(float(dist), 4),
                "similarity_score": round(1.0 - float(dist), 4),
                "snippet": text[:200] + "..." if len(text) > 200 else text,
            })

        context_str = "\n".join(context_blocks)

        # 3. Synthesize Grounded Answer with Citations
        messages = [
            SystemMessage(content=RAG_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"User Question: {question}\n\n"
                f"Official Government Document Excerpts (Retrieved via IBM Db2 VECTOR_DISTANCE):\n"
                f"------------------------------------------------------------------------\n"
                f"{context_str}\n"
                f"------------------------------------------------------------------------\n"
                f"Provide a clear, helpful, grounded answer with document and page citations in the user's language:"
            ))
        ]
        
        try:
            response = self.llm.invoke(messages)
            answer = response.content.strip()
        except Exception:
            from app.agents.llm import MockOfflineChatModel
            response = MockOfflineChatModel().invoke(messages)
            answer = response.content.strip()

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "chunks": chunks,
            "engine": self.db.engine_type,
        }


def get_rag_agent() -> RagAgent:
    """Factory helper for RagAgent."""
    return RagAgent()
