import pytest
from src.ai.llm import LLMUnavailable
from src.ai.sql_generator import generate_sql


def test_missing_openai_key(monkeypatch):
    from src.config import get_settings
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(LLMUnavailable):
        generate_sql("total revenue")
    get_settings.cache_clear()


def test_llm_failure_is_reported(monkeypatch):
    from src.ai import sql_generator
    class Broken:
        def invoke(self, _): raise RuntimeError("network")
    class Prompt:
        def __or__(self, model): return model
    monkeypatch.setattr(sql_generator, "_sql_prompt", lambda: Prompt())
    monkeypatch.setattr(sql_generator, "get_chat_model", lambda: Broken())
    with pytest.raises(RuntimeError):
        generate_sql("total revenue")
