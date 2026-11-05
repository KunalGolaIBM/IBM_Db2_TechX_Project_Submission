"""
Official Scheme Documents Vector Ingestion Pipeline - Kisan Mitra (किसान मित्र)
Extracts page-aware text from official PDFs in data/docs/ (PM-KISAN, PMFBY, KCC),
chunks into ~500 tokens with overlap, generates 384-d multilingual embeddings,
and stores them into IBM Db2 DOC_CHUNKS with native VECTOR(384, REAL) support.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config
from app.db_client import get_db_client
from app.agents.embedder import get_embedder

SCHEME_MAP = {
    "PM_KISAN_Guidelines.pdf": "PM-KISAN",
    "PMFBY_Guidelines.pdf": "PMFBY",
    "KCC_Scheme_Guidelines.pdf": "KCC",
}

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 60) -> List[str]:
    """Split text into overlapping chunks using paragraph and sentence boundaries."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            # Retain overlap from previous chunk
            overlap_chunk = []
            overlap_len = 0
            for item in reversed(current_chunk):
                if overlap_len + len(item) <= chunk_overlap:
                    overlap_chunk.insert(0, item)
                    overlap_len += len(item)
                else:
                    break
            current_chunk = overlap_chunk
            current_len = overlap_len

        current_chunk.append(para)
        current_len += para_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

def process_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract page-aware text and create chunks from a PDF file."""
    reader = PdfReader(str(pdf_path))
    doc_name = pdf_path.name
    scheme_name = SCHEME_MAP.get(doc_name, doc_name.replace(".pdf", ""))
    chunks: List[Dict[str, Any]] = []

    print(f"📖 Processing '{doc_name}' ({len(reader.pages)} pages) for scheme: '{scheme_name}'...")
    
    chunk_idx = 0
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        page_chunks = chunk_text(page_text, chunk_size=500, chunk_overlap=60)
        
        for c_text in page_chunks:
            if not c_text.strip():
                continue
            chunks.append({
                "doc_name": doc_name,
                "scheme_name": scheme_name,
                "page_number": page_num,
                "chunk_index": chunk_idx,
                "chunk_text": c_text.strip(),
            })
            chunk_idx += 1

    return chunks

def build_vector_store(dry_run: bool = False):
    """Main pipeline to extract, embed, and insert into Db2 DOC_CHUNKS."""
    docs_dir = config.DOCS_DIR
    pdf_files = list(docs_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF documents found in {docs_dir}. Run ingest/create_official_docs.py first.")

    all_raw_chunks: List[Dict[str, Any]] = []
    for pdf in pdf_files:
        all_raw_chunks.extend(process_pdf(pdf))

    print(f"✂️ Created {len(all_raw_chunks)} chunks across {len(pdf_files)} official documents.")

    # Generate 384-d dense vector embeddings
    embedder = get_embedder()
    print("🧠 Generating 384-dimensional multilingual vector embeddings...")
    texts = [c["chunk_text"] for c in all_raw_chunks]
    embeddings = embedder.encode(texts)

    for c, emb in zip(all_raw_chunks, embeddings):
        c["embedding"] = emb

    if dry_run:
        print("🔍 Dry run completed. First chunk preview:")
        print(f"   Doc: {all_raw_chunks[0]['doc_name']} (Page {all_raw_chunks[0]['page_number']})")
        print(f"   Text: {all_raw_chunks[0]['chunk_text'][:120]}...")
        print(f"   Vector dim: {len(all_raw_chunks[0]['embedding'])}")
        return

    # Ingest into Db2 DOC_CHUNKS
    db = get_db_client(read_only=False)
    if db.engine_type == "emulated_db2" and db._sqlite_conn:
        db._sqlite_conn.cursor().execute("DELETE FROM DOC_CHUNKS")
        db._sqlite_conn.commit()
    inserted = db.insert_doc_chunks(all_raw_chunks)
    print(f"💾 Successfully stored {inserted} document chunks into IBM Db2 table DOC_CHUNKS.")

    # Verification test: Run native vector similarity search on Db2
    print("\n🔍 Running verification native vector search on IBM Db2...")
    test_query = "PM-KISAN में कितने पैसे मिलते हैं और किसे मिलते हैं?"
    q_vec = embedder.encode(test_query)
    matches = db.vector_search(q_vec, top_k=2)
    print(f"✅ Top match for query '{test_query}':")
    for idx, m in enumerate(matches, start=1):
        print(f"   [{idx}] Source: {m['doc_name']} (Page {m['page_number']}) | Cosine Distance: {m['distance']}")
        print(f"       Snippet: {m['chunk_text'][:150]}...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build IBM Db2 Vector Store from Official PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Chunk and embed without inserting into database")
    args = parser.parse_args()
    build_vector_store(dry_run=args.dry_run)
