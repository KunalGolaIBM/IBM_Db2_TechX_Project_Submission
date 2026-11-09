import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()


def get_ai_response(question, educational_context=""):

    model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

    base_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434"
    )

    try:
        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.2
        )

        prompt = f"""
        You are CyberAware AI, a cybersecurity education assistant.

        Help users understand cybersecurity in simple English.

        Focus on:
        - Phishing messages
        - Online scams
        - Fake links
        - Mobile money fraud
        - Password security
        - Online privacy

        Educational information:
        {educational_context}

        User question:
        {question}

        Give a clear, practical and safe answer.
        Never ask users to reveal passwords or PINs.
        """

        response = llm.invoke(prompt)

        return response.content

    except Exception:
        return (
            "The AI service is currently unavailable. "
            "Please try again later. Meanwhile, never share "
            "your passwords, PINs or verification codes."
        )
