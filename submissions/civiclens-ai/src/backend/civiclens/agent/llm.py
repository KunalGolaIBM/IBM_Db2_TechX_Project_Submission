"""LLM provider factory. Credentials come only from settings/environment; none are hardcoded.

Supported providers (optional extras, see requirements-llm.txt):
  openai    -> langchain-openai    ChatOpenAI     (OPENAI_API_KEY, LLM_MODEL)
  anthropic -> langchain-anthropic ChatAnthropic  (ANTHROPIC_API_KEY, LLM_MODEL)
  watsonx   -> langchain-ibm       ChatWatsonx    (WATSONX_APIKEY, WATSONX_PROJECT_ID, LLM_MODEL)

``build_llm`` returns ``None`` when LLM_PROVIDER is "none". It raises ``LlmConfigError`` (with a
non-secret message) when a provider is selected but incomplete, its package is missing, or the client
cannot be created. Creating the OpenAI and Anthropic clients does not contact the provider; creating
the watsonx client authenticates against IBM Cloud, so a wrong key or an unreachable endpoint fails
here (as ``LlmConfigError``, naming only the exception class, never its text).
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any

from civiclens.config import Settings


class LlmConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class LlmHandle:
    model: Any  # a LangChain BaseChatModel
    provider: str
    model_name: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model_name}"


def _need(value: Any, what: str) -> Any:
    if value is None or (hasattr(value, "get_secret_value") and not value.get_secret_value()):
        raise LlmConfigError(f"{what} is not set.")
    return value.get_secret_value() if hasattr(value, "get_secret_value") else value


def llm_configured(settings: Settings) -> bool:
    return settings.llm_provider != "none"


def build_llm(settings: Settings) -> LlmHandle | None:
    provider = settings.llm_provider
    if provider == "none":
        return None
    model_name = _need(settings.llm_model, "LLM_MODEL")
    timeout = settings.llm_timeout_s
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            model: Any = ChatOpenAI(
                model=model_name,
                api_key=_need(settings.openai_api_key, "OPENAI_API_KEY"),
                timeout=timeout,
                max_retries=1,
                temperature=0,
            )
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            model = ChatAnthropic(
                model=model_name,
                api_key=_need(settings.anthropic_api_key, "ANTHROPIC_API_KEY"),
                timeout=timeout,
                max_retries=1,
                temperature=0,
            )
        elif provider == "watsonx":
            from langchain_ibm import ChatWatsonx

            model = ChatWatsonx(
                model_id=model_name,
                url=settings.watsonx_url,
                apikey=_need(settings.watsonx_apikey, "WATSONX_APIKEY"),
                project_id=_need(settings.watsonx_project_id, "WATSONX_PROJECT_ID"),
                params={"temperature": 0, "max_tokens": 1500},
            )
        else:  # pragma: no cover - guarded by the Literal type
            raise LlmConfigError(f"Unknown provider {provider!r}.")
    except LlmConfigError:
        raise
    except ImportError as exc:
        raise LlmConfigError(
            f"Provider package for {provider!r} is not installed (pip install -r requirements-llm.txt)."
        ) from exc
    except Exception as exc:  # a provider SDK failure (authentication, network, bad parameters ...)
        # The exception text can carry request details, so only its class is kept.
        raise LlmConfigError(
            f"The {provider!r} client could not be created ({type(exc).__name__})."
        ) from None
    return LlmHandle(model=model, provider=provider, model_name=model_name)


_PROVIDER_PACKAGE = {
    "openai": "langchain_openai",
    "anthropic": "langchain_anthropic",
    "watsonx": "langchain_ibm",
}


def llm_status(settings: Settings) -> dict[str, Any]:
    """Non-secret description of the LLM configuration for operators.

    ``configured`` means "``build_llm`` would succeed" (provider, model, credentials and package are
    present). It does NOT mean the provider has been contacted or works.
    """
    provider = settings.llm_provider
    if provider == "none":
        return {"configured": False, "provider": "none", "model": None, "problem": None}
    required: dict[str, Any] = {
        "openai": {"OPENAI_API_KEY": settings.openai_api_key},
        "anthropic": {"ANTHROPIC_API_KEY": settings.anthropic_api_key},
        "watsonx": {
            "WATSONX_APIKEY": settings.watsonx_apikey,
            "WATSONX_PROJECT_ID": settings.watsonx_project_id,
        },
    }[provider]
    problems: list[str] = []
    if not settings.llm_model:
        problems.append("LLM_MODEL is not set.")
    for name, value in required.items():
        raw = value.get_secret_value() if hasattr(value, "get_secret_value") else value
        if not raw:
            problems.append(f"{name} is not set.")
    package = _PROVIDER_PACKAGE[provider]
    if importlib.util.find_spec(package) is None:
        problems.append(f"Package {package} is not installed.")
    return {
        "configured": not problems,
        "provider": provider,
        "model": settings.llm_model,
        "problem": " ".join(problems) or None,
    }
