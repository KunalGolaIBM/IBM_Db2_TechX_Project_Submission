"""
IBM Db2 TechX Summit 2026 - Official LangChain Db2 Integration Quickstart
Implements the 5-step challenge architecture:
1. Connect to Db2 (local Docker or VS Code extension)
2. Turn student notes into Document objects
3. Embed them and store them into Db2 using langchain-db2 (DB2VS)
4. Ask a student question -> Db2 returns closest notes via native vector search
5. Pass retrieved notes + question to LLM (watsonx.ai Granite / Gemini / Ollama)
"""

import os
from pathlib import Path

# Step 1: Connect to your local or remote Db2
print("[Step 1] Connecting to IBM Db2...")
db2_conn_str = os.getenv(
    "DB2_CONNECTION_STRING",
    f"DATABASE={os.getenv('DB2_DATABASE', 'testdb')};"
    f"HOSTNAME={os.getenv('DB2_HOST', 'localhost')};"
    f"PORT={os.getenv('DB2_PORT', '50000')};"
    f"PROTOCOL=TCPIP;"
    f"UID={os.getenv('DB2_USER', 'db2inst1')};"
    f"PWD={os.getenv('DB2_PASSWORD', 'password')};"
)

conn = None
try:
    import ibm_db_dbi
    conn = ibm_db_dbi.connect(db2_conn_str, "", "")
    print("  -> Connected successfully to IBM Db2!")
except Exception as e:
    print(f"  -> Note: Local Db2 connection standby ({e}). Using resilient mode.")

# Step 2: Turn your notes into documents
print("\n[Step 2] Processing student notes into LangChain documents...")
from chunker import StudentNotesChunker

notes_path = Path(__file__).resolve().parent.parent / "data" / "notes.md"
chunker = StudentNotesChunker(chunk_size=800, chunk_overlap=150)
notes = chunker.process_file(str(notes_path))
print(f"  -> Generated {len(notes)} document chunks with topic tags and math formulas.")

# Step 3: Embed them and store them in Db2
print("\n[Step 3] Embedding and indexing notes in IBM Db2...")
from db2_client import get_or_create_vector_store

store = get_or_create_vector_store(documents=notes)
print(f"  -> Vectors stored in table '{os.getenv('DB2_TABLE_NAME', 'STUDENT_NOTES_VS')}'.")

# Step 4: Ask a question — Db2 returns the closest notes
question = "Explain the Friis transmission equation and its decibel form"
print(f"\n[Step 4] Querying Db2 vector store: '{question}'...")
retrieved_docs = store.similarity_search(question, k=3)
for i, doc in enumerate(retrieved_docs, 1):
    title = doc.metadata.get("section_title", "Section")
    print(f"  [{i}] {title}: {doc.page_content[:150]}...\n")

# Step 5: Pass these notes + question to LLM to write the answer
print("[Step 5] Passing context notes + question to LLM...")
from rag_engine import StudentNotesRAG

rag = StudentNotesRAG(vector_store=store)
result = rag.answer_question(question)

print("\n" + "=" * 65)
print("FINAL EXAM ANSWER:")
print("=" * 65)
print(result["answer"])
print("=" * 65)
print(f"Provider: {result['provider']} | Sources retrieved: {result['retrieved_count']}")

