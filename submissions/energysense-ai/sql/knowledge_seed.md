# Maintenance knowledge seed

The `src/langchain_db2.py` module inserts these six maintenance guidance notes into the IBM Db2 vector store (`ESAI_KNOWLEDGE`) using LangChain's `DB2VS` connector. The included hashing embeddings are deterministic prototype embeddings; replace them with a validated embedding model before using semantic retrieval in a production system.
