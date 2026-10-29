from fastapi import FastAPI
from pydantic import BaseModel

from db2_client import Db2Client
from llm_service import generate_sql_from_question

app = FastAPI(title="Sharthi AI", version="0.1.0")
client = Db2Client()


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "sharthi-ai"}


@app.post("/ask")
def ask_question(request: AskRequest):
    question = request.question.strip()
    if not question:
        return {"answer": "Please provide a valid question."}

    sql_query = generate_sql_from_question(question)
    rows = client.execute_query(sql_query)

    return {
        "question": question,
        "sql_query": sql_query,
        "rows": rows,
        "answer": summarize(rows, question),
    }


def summarize(rows, question: str) -> str:
    if not rows:
        return "No matching records found for your question."

    sample = rows[0]
    return (
        f"Based on the available records, here is the result for: '{question}'. "
        f"The first matching row is: {sample}."
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
