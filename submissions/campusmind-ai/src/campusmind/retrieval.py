from haystack import Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever


class CampusMindRetriever:
    def __init__(self):
        self.store = InMemoryDocumentStore()
        self.retriever = InMemoryBM25Retriever(
            document_store=self.store,
            top_k=3
        )

    def add_chunks(self, filename, chunks):
        documents = [
            Document(
                content=chunk["text"],
                meta={
                    "filename": filename,
                    "page": chunk["page"]
                }
            )
            for chunk in chunks
        ]
        self.store.write_documents(documents)

    def search(self, question):
        result = self.retriever.run(query=question)
        return result["documents"]
