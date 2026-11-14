"""
Intelligent Document Chunker for Student Exam Notes.
Preserves mathematical formulas, equations, derivations, and header structure
while producing LangChain Document objects ready for IBM Db2 vector search.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from langchain_core.documents import Document
except ImportError:
    # Lightweight fallback Document class if langchain_core is still downloading
    class Document:  # type: ignore
        def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
            self.page_content = page_content
            self.metadata = metadata or {}

        def __repr__(self):
            return f"Document(page_content='{self.page_content[:40]}...', metadata={self.metadata})"


class StudentNotesChunker:
    """Splits markdown student study notes into semantically rich chunks with metadata."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def detect_formulas(text: str) -> bool:
        """Detect whether a chunk contains math expressions, equations, or decibel formulas."""
        patterns = [
            r"\$\$.*?\$\$",
            r"\$.*?\$",
            r"[P|G|L|d|f]_[rt\w]",
            r"\\frac",
            r"\\log",
            r"\b(dB|dBm|dBi|kHz|MHz|GHz)\b",
            r"=\s*[\d\w\(\)\.\+\-\*\/]+",
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def extract_sections(content: str) -> List[Dict[str, Any]]:
        """Split document by top-level and second-level Markdown headers."""
        lines = content.splitlines()
        sections: List[Dict[str, Any]] = []
        current_title = "Introduction / Overview"
        current_lines: List[str] = []

        for line in lines:
            if re.match(r"^#{1,3}\s+", line):
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        sections.append({
                            "title": current_title,
                            "content": text
                        })
                current_title = re.sub(r"^#{1,3}\s+", "", line).strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                sections.append({
                    "title": current_title,
                    "content": text
                })

        return sections

    def chunk_text(self, text: str, header_context: str = "") -> List[str]:
        """Split long text into sliding windows with overlap, respecting paragraph boundaries."""
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_len = len(para)

            if current_len + para_len > self.chunk_size and current_chunk:
                chunk_str = "\n\n".join(current_chunk).strip()
                if header_context and not chunk_str.startswith(header_context):
                    chunk_str = f"[{header_context}]\n\n" + chunk_str
                chunks.append(chunk_str)

                # Overlap retention: keep the last paragraph if small enough
                if len(current_chunk[-1]) <= self.chunk_overlap:
                    current_chunk = [current_chunk[-1], para]
                    current_len = len(current_chunk[0]) + para_len
                else:
                    current_chunk = [para]
                    current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len

        if current_chunk:
            chunk_str = "\n\n".join(current_chunk).strip()
            if header_context and not chunk_str.startswith(header_context):
                chunk_str = f"[{header_context}]\n\n" + chunk_str
            chunks.append(chunk_str)

        return chunks

    def process_file(self, file_path: str, source_name: Optional[str] = None) -> List[Document]:
        """Read a notes file and turn it into indexed LangChain Document objects."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Notes file not found: {file_path}")

        source = source_name or path.name
        content = path.read_text(encoding="utf-8", errors="ignore")
        sections = self.extract_sections(content)

        documents: List[Document] = []
        doc_counter = 0

        for sec in sections:
            sec_title = sec["title"]
            raw_chunks = self.chunk_text(sec["content"], header_context=sec_title)

            for idx, chunk in enumerate(raw_chunks):
                doc_counter += 1
                has_math = self.detect_formulas(chunk)

                # Extract topic category (e.g. Wireless, Modulation, Traffic, Propagation)
                topic = "General Engineering"
                lower_title = sec_title.lower()
                if any(w in lower_title for w in ["friis", "propagation", "los", "path loss"]):
                    topic = "Radio Wave Propagation"
                elif any(w in lower_title for w in ["rake", "combining", "mrc", "diversity"]):
                    topic = "Diversity & Multipath"
                elif any(w in lower_title for w in ["ofdm", "dsss", "subcarrier"]):
                    topic = "Modulation & Spread Spectrum"
                elif any(w in lower_title for w in ["traffic", "poisson", "gos", "trunking", "erlang"]):
                    topic = "Cellular Traffic & Teletraffic"
                elif any(w in lower_title for w in ["handover", "handoff", "cell"]):
                    topic = "Cellular Architecture & Mobility"
                elif any(w in lower_title for w in ["frequency reuse", "cluster"]):
                    topic = "Frequency Management"

                metadata = {
                    "doc_id": f"chunk_{doc_counter:04d}",
                    "source": source,
                    "section_title": sec_title,
                    "topic": topic,
                    "chunk_index": idx + 1,
                    "has_formula": has_math,
                    "char_count": len(chunk),
                }

                documents.append(Document(page_content=chunk, metadata=metadata))

        return documents

