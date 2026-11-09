import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()


def get_ai_response(question):
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:0.5b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Retrieve educational information from IBM Db2
    try:
        from lessons import get_lesson_context
        lesson_context = get_lesson_context()
    except Exception:
        lesson_context = "No Db2 lessons are currently available."

    prompt = f"""
You are CyberAware AI, a friendly cybersecurity education assistant.

Explain cybersecurity in simple language.
Give practical safety advice.
Never ask users to share passwords, PINs, or verification codes.

Use these lessons from the IBM Db2 database when relevant:

{lesson_context}

User question: {question}

Give a clear, helpful answer.
"""

    try:
        model = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.3
        )

        response = model.invoke(prompt)
        return response.content

    except Exception:
        return (
            "The AI assistant is temporarily unavailable. "
            "Please make sure Ollama is running and the required model is installed."
        )
