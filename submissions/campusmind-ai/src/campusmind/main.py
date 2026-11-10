import re

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from campusmind.pdf_processor import process_pdf
from campusmind.retrieval import CampusMindRetriever


app = FastAPI(
    title="CampusMind AI",
    description="Student knowledge assistant using Haystack BM25 retrieval",
    version="1.1.0"
)

retriever = CampusMindRetriever()


class Question(BaseModel):
    question: str


def extractive_answer(question, passage):
    """Select the most relevant sentence from a retrieved passage."""
    sentences = re.split(r"(?<=[.!?])\s+", passage.strip())

    stopwords = {
        "what", "is", "a", "an", "the", "of", "in",
        "to", "and", "for", "explain", "describe",
        "define", "tell", "me", "about"
    }

    terms = [
        word for word in re.findall(r"\b\w+\b", question.lower())
        if word not in stopwords
    ]

    if not terms:
        return sentences[0] if sentences else passage

    def sentence_score(sentence):
        text = sentence.lower()
        coverage = sum(term in text for term in terms) / len(terms)
        score = coverage

        phrase = " ".join(terms)
        if len(terms) > 1 and phrase in text:
            score += 1

        return score

    best_sentence = max(sentences, key=sentence_score, default=passage)

    if sentence_score(best_sentence) == 0:
        return sentences[0] if sentences else passage

    return best_sentence


@app.get("/")
def home():
    return {
        "message": "Welcome to CampusMind AI",
        "status": "running"
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted."
        )

    try:
        content = await file.read(10 * 1024 * 1024 + 1)

        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="PDF must be smaller than 10 MB."
            )

        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file."
            )

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
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question."
        )

    documents = retriever.search(question)

    if not documents:
        return {
            "question": question,
            "answer": None,
            "message": "No relevant information found in uploaded notes.",
            "sources": []
        }

    best_document = documents[0]
    answer = extractive_answer(question, best_document.content)

    sources = [
        {
            "filename": doc.meta["filename"],
            "page": doc.meta["page"],
            "relevance_score": doc.meta.get("combined_relevance_score"),
            "bm25_score": doc.meta.get("bm25_score"),
            "relevant_text": doc.content
        }
        for doc in documents[:3]
    ]

    return {
        "question": question,
        "answer": answer,
        "answer_type": "Extractive answer",
        "retrieval_method": "Haystack BM25 with answer-focused reranking",
        "message": "Answer extracted from uploaded study notes.",
        "sources": sources
    }
