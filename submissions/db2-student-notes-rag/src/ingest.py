"""
Ingestion Pipeline for IBM Db2 Vector Search.
Reads student notes, chunks them into semantic sections, computes embeddings,
and stores them into IBM Db2's native VECTOR column.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from config import Db2RAGConfig
from chunker import StudentNotesChunker
from db2_client import get_or_create_vector_store, verify_db2_connection


def run_ingestion(notes_path: str, table_name: Optional[str] = None) -> int:
    """Ingest notes into IBM Db2 vector store."""
    path = Path(notes_path)
    if not path.is_file():
        # Look relative to project root or current dir
        alt_path = Path(__file__).resolve().parent.parent / "data" / "notes.md"
        if alt_path.is_file():
            path = alt_path
        else:
            raise FileNotFoundError(f"Notes file not found at: {notes_path}")

    print("=" * 65)
    print(" IBM Db2 Vector Search Ingestion Pipeline")
    print("=" * 65)
    print(f"Notes Source:      {path.resolve()}")
    print(f"Target Db2 Table:  {table_name or Db2RAGConfig.DB2_TABLE_NAME}")
    print(f"Embedding Model:   {Db2RAGConfig.EMBEDDING_MODEL} ({Db2RAGConfig.EMBEDDING_DIM}-dim)")
    print(f"Distance Metric:   {Db2RAGConfig.DISTANCE_STRATEGY}")
    print("-" * 65)

    # 1. Health check
    is_healthy, status_msg = verify_db2_connection()
    print(f"Db2 Health Status: {status_msg}")

    # 2. Chunking
    print("\n[Step 1/3] Chunking markdown notes into semantic passages...")
    chunker = StudentNotesChunker(
        chunk_size=Db2RAGConfig.CHUNK_SIZE,
        chunk_overlap=Db2RAGConfig.CHUNK_OVERLAP,
    )
    docs = chunker.process_file(str(path))
    print(f"  -> Extracted {len(docs)} document chunks.")

    # Show category breakdown
    categories = {}
    formulas_count = 0
    for d in docs:
        topic = d.metadata.get("topic", "General")
        categories[topic] = categories.get(topic, 0) + 1
        if d.metadata.get("has_formula"):
            formulas_count += 1

    print(f"  -> Formulas & Math detected in {formulas_count} chunks.")
    print("  -> Topic Breakdown:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"     • {cat}: {count} chunks")

    # 3. Embedding and Indexing into Db2
    print("\n[Step 2/3] Generating vector embeddings & writing to IBM Db2...")
    if table_name:
        Db2RAGConfig.DB2_TABLE_NAME = table_name

    store = get_or_create_vector_store(documents=docs, recreate=True)

    # 4. Verification test
    print("\n[Step 3/3] Verifying similarity search on Db2 vector store...")
    test_query = "What is the Friis transmission equation?"
    matches = store.similarity_search(test_query, k=2)
    print(f"  -> Verification query '{test_query}' returned {len(matches)} matches.")
    if matches:
        print(f"  -> Top match section: '{matches[0].metadata.get('section_title')}'")

    print("\n" + "=" * 65)
    print(f" SUCCESS: {len(docs)} chunks successfully indexed and ready for student queries!")
    print("=" * 65)
    return len(docs)


def main():
    parser = argparse.ArgumentParser(description="Ingest student notes into IBM Db2 Vector Store")
    parser.add_argument(
        "--file",
        "-f",
        default=str(Path(__file__).resolve().parent.parent / "data" / "notes.md"),
        help="Path to markdown notes file",
    )
    parser.add_argument(
        "--table",
        "-t",
        default=Db2RAGConfig.DB2_TABLE_NAME,
        help="Db2 target table name",
    )
    args = parser.parse_args()

    try:
        run_ingestion(args.file, args.table)
    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

