import re

from haystack import Document
from haystack.document_stores.types import DuplicatePolicy
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever


class CampusMindRetriever:
    def __init__(self):
        self.store = InMemoryDocumentStore()
        self.retriever = InMemoryBM25Retriever(
            document_store=self.store,
            top_k=10
        )

    def add_chunks(self, filename, chunks):
        documents = [
            Document(
                content=chunk["text"],
                meta={"filename": filename, "page": chunk["page"]}
            )
            for chunk in chunks
        ]

        self.store.write_documents(
            documents,
            policy=DuplicatePolicy.OVERWRITE
        )

    def _answer_relevance(self, question, document):
        text = document.content.lower()
        query = question.lower().strip()

        stopwords = {
            "what", "is", "a", "an", "the", "of", "in",
            "to", "and", "for", "explain", "describe",
            "define", "tell", "me", "about"
        }

        terms = [
            word for word in re.findall(r"\b\w+\b", query)
            if word not in stopwords
        ]

        if not terms:
            return 0.0

        coverage = sum(term in text for term in terms) / len(terms)
        score = coverage * 2.0

        phrase = " ".join(terms)

        if len(terms) > 1 and phrase in text:
            score += 1.5

        definition_pattern = (
            r"\b(?:a|an|the)?\s*"
            + re.escape(phrase)
            + r"\s+(?:is|are|refers to|means|is defined as|"
              r"can be defined as|is used to)\b"
        )

        if re.search(definition_pattern, text):
            score += 3.0

        revision_patterns = (
            r"\brevision question\b",
            r"\bquick revision\b",
            r"\bpractice question\b",
            r"\bself[- ]assessment\b",
            r"\bquiz question\b"
        )

        if any(re.search(pattern, text) for pattern in revision_patterns):
            score -= 1.5

        return score

    def search(self, question):
        result = self.retriever.run(query=question)

        ranked_documents = []

        for doc in result["documents"]:
            bm25_score = doc.score or 0.0
            answer_score = self._answer_relevance(question, doc)
            combined_score = bm25_score + answer_score

            ranked_documents.append((doc, combined_score, bm25_score))

        ranked_documents.sort(
            key=lambda item: (item[1], item[2]),
            reverse=True
        )

        for doc, combined_score, bm25_score in ranked_documents:
            doc.meta["combined_relevance_score"] = round(combined_score, 4)
            doc.meta["bm25_score"] = round(bm25_score, 4)

        return [item[0] for item in ranked_documents]
