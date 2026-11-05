"""AI / LLM Provider Configuration with LangChain and OpenRouter Free Models."""
import os
import logging
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from recipe_waste_optimizer.config import settings

logger = logging.getLogger("ai_provider")


def get_chat_model() -> Optional[BaseChatModel]:
    """Instantiate configured LangChain ChatModel (OpenRouter or mock fallback)."""
    api_key = settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")

    if settings.LLM_PROVIDER == "openrouter" and api_key and not api_key.startswith("replace_"):
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=settings.OPENROUTER_MODEL,
                openai_api_key=api_key,
                openai_api_base=settings.OPENROUTER_BASE_URL,
                temperature=0.2,
                max_tokens=1500,
            )
            logger.info(f"Initialized OpenRouter LLM: {settings.OPENROUTER_MODEL}")
            return llm
        except Exception as e:
            logger.warning(f"Failed to initialize ChatOpenAI for OpenRouter: {e}. Falling back to rule-based generator.")
            return None

    logger.info("Using deterministic rule-based recipe generator (zero external API keys required).")
    return None
