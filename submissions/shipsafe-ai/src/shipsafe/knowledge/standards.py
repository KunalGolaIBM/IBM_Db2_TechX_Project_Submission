"""Answer "what is our standard for X?" with a LangChain RAG chain over Db2 vectors.

retrieve (DB2VS, VECTOR_DISTANCE in Db2) -> prompt -> Granite (ChatOllama) -> text

The answer is grounded only in the retrieved policy sections and always returns
the citations it used, so the IDE can show where the rule comes from.
"""

import difflib
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from ..config import LlmConfig
from ..llm.granite import chat_model, require_models

PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are the engineering-standards assistant for a software team. Answer ONLY from the policy excerpts "
     "provided and only about the question asked. Cite the policy you used in square brackets, using exactly "
     "one of these ids: {ids}. If the excerpts do not answer the question, say so plainly. Be concise: at most "
     "6 sentences or a short list, and include a code example when it helps."),
    ("human", "Policy excerpts:\n\n{context}\n\nQuestion: {question}"),
])

_CITE = re.compile(r"\[?\b([A-Z]{2,}(?:-[A-Z0-9]+)*-\d{3})\b\]?")


def verify_citations(answer: str, allowed: List[str]) -> Tuple[str, List[str], List[str]]:
    """Check every [ID] in the answer against the ids Db2 actually returned.

    A near-miss (e.g. SEC-POL-001 written for POL-SEC-001) is corrected to the matching retrieved id;
    anything else is marked "(unverified)". Returns (answer, cited_ids, unverified_ids)."""
    cited: List[str] = []
    unverified: List[str] = []

    def fix(m: "re.Match[str]") -> str:
        cid = m.group(1)
        if cid in allowed:
            cited.append(cid)
            return m.group(0)
        same_parts = [a for a in allowed if sorted(a.split("-")) == sorted(cid.split("-"))]
        close = same_parts or difflib.get_close_matches(cid, allowed, n=1, cutoff=0.75)
        if close:
            cited.append(close[0])
            return m.group(0).replace(cid, close[0])
        unverified.append(cid)
        return m.group(0).replace(cid, f"{cid} (unverified)")

    fixed = _CITE.sub(fix, answer)
    return fixed, list(dict.fromkeys(cited)), unverified


def _format(hits: List[Dict[str, Any]]) -> str:
    return "\n\n".join(f"[{h['doc_id']}] {h['title']} / {h['section']} (v{h['version']}):\n{h['content']}" for h in hits)


class StandardsAdvisor:
    def __init__(self, knowledge_base: Any, llm_config: LlmConfig, top_k: int = 3):
        self.kb = knowledge_base
        self.cfg = llm_config
        self.top_k = top_k

    def chain(self, category: Optional[str] = None):
        retrieve = RunnableLambda(lambda q: self.kb.retrieve(q, top_k=self.top_k, category=category))
        return (
            {"hits": retrieve, "question": RunnablePassthrough()}
            | RunnablePassthrough.assign(
                answer=(
                    {"context": lambda x: _format(x["hits"]), "question": lambda x: x["question"],
                     "ids": lambda x: ", ".join(h["doc_id"] for h in x["hits"]) or "(none)"}
                    | PROMPT | chat_model(self.cfg) | StrOutputParser()
                ))
        )

    def ask(self, question: str, category: Optional[str] = None) -> Dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("question must not be empty")
        require_models(self.cfg, chat=True)
        started = time.perf_counter()
        out = self.chain(category).invoke(question.strip())
        hits = out["hits"]
        answer, cited, unverified = verify_citations(out["answer"].strip(), [h["doc_id"] for h in hits])
        return {
            "question": question.strip(),
            "answer": answer,
            "cited": cited,
            "unverified_citations": unverified,
            "model": self.cfg.chat_model,
            "citations": [{k: h[k] for k in ("doc_id", "title", "section", "version", "source", "similarity")}
                          for h in hits],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
