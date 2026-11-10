"""LangChain model construction with explicit missing-key handling."""
from src.config import get_settings


class LLMUnavailable(RuntimeError):
    pass


def get_chat_model():
    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMUnavailable("OPENAI_API_KEY is not configured. Add it to .env to use AI features.")
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
    except Exception as exc:
        raise LLMUnavailable("Could not initialize the configured LangChain OpenAI model.") from exc
