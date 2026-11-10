from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from campusmind.pdf_processor import process_pdf
from campusmind.retrieval import CampusMindRetriever

app = FastAPI(
    title="CampusMind AI",
    description="Student knowledge assistant using Haystack BM25 retrieval",
    version="1.0.0"
)

retriever = CampusMindRetriever()


class Question(BaseModel):
    question: str


@app.get("/")
def home():
    return {
        "message": "Welcome to CampusMind AI",
        "status": "running"
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        content = await file.read(10 * 1024 * 1024 + 1)

        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="PDF must be smaller than 10 MB.")

        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Invalid PDF file.")

        result = process_pdf(content)

        retriever.add_chunks(file.filename, result["chunks"])

        return {
            "filename": file.filename,
            "total_pages": result["total_pages"],
            "total_chunks": result["total_chunks"],
            "retrieval_method": "Haystack BM25",
            "message": "PDF processed and indexed successfully."
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    finally:
        await file.close()


@app.post("/ask")
def ask_question(request: Question):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")

    documents = retriever.search(request.question)

    if not documents:
        return {
            "question": request.question,
            "message": "No relevant information found in uploaded notes.",
            "sources": []
        }

    sources = [
        {
            "filename": doc.meta["filename"],
            "page": doc.meta["page"],
            "relevance_score": round(doc.score, 4) if doc.score is not None else None,
            "relevant_text": doc.content
        }
        for doc in documents
    ]

    return {
        "question": request.question,
        "answer": documents[0].content,
        "retrieval_method": "Haystack BM25 (in-memory)",
        "message": "Relevant content retrieved from uploaded study notes.",
        "sources": sources
    }
