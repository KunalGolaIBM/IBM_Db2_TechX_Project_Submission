"""LangChain-backed LLM access with a provider-agnostic interface.

The rest of AEGIS depends on the small `LLMClient` protocol, never on a concrete
vendor SDK. Any OpenAI-compatible hosted provider can be selected through
environment variables; tests inject a scripted implementation.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, LLMUnavailableError

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LLMClient(Protocol):
    provider_name: str

    def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class LangChainLLMClient:
    """Wraps a LangChain chat model configured from the environment."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.llm_api_key:
            raise ConfigurationError(
                "LLM_API_KEY is not configured. Set a hosted provider key in the environment."
            )
        self.provider_name = self.settings.llm_provider
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - dependency error
            raise ConfigurationError(
                "LangChain dependencies are not installed. Run pip install -r requirements.txt."
            ) from exc

        model_kwargs = {
            "model": self.settings.llm_model,
            "api_key": self.settings.llm_api_key,
            "temperature": self.settings.llm_temperature,
            "timeout": self.settings.llm_timeout_seconds,
            "max_retries": self.settings.llm_max_retries,
            "max_tokens": self.settings.llm_max_tokens,
        }
        if self.settings.llm_base_url:
            model_kwargs["base_url"] = self.settings.llm_base_url

        self._model = ChatOpenAI(**model_kwargs)
        self._chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", "{system_prompt}"),
                    ("human", "{user_prompt}"),
                ]
            )
            | self._model
            | StrOutputParser()
        )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return self._chain.invoke(
                {"system_prompt": system_prompt, "user_prompt": user_prompt}
            )
        except Exception as exc:  # provider/network/rate-limit failures
            logger.warning("LLM call failed (%s)", type(exc).__name__)
            raise LLMUnavailableError(
                "The configured language model could not be reached or returned an error."
            ) from exc


def _escape_inner_quotes(text: str) -> str:
    """Escape unescaped quotes inside JSON string values.

    Local models sometimes quote an excerpt verbatim inside a JSON string
    without escaping it. A quote is treated as a closing delimiter only when
    the next non-space character is a JSON separator; otherwise it is data.
    """
    output: list[str] = []
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            output.append(char)
            escaped = False
            continue
        if in_string and char == "\\":
            output.append(char)
            escaped = True
            continue
        if char == '"':
            if not in_string:
                in_string = True
                output.append(char)
                continue
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead] in " \t\r\n":
                lookahead += 1
            following = text[lookahead] if lookahead < len(text) else ""
            if following in ",:}]" or following == "":
                in_string = False
                output.append(char)
            else:
                output.append('\\"')
            continue
        output.append(char)
    return "".join(output)


def extract_json_object(raw: str) -> dict:
    """Parse a JSON object from a model response, tolerating code fences/prose."""
    if not raw or not raw.strip():
        raise ValueError("Empty model response")
    text = raw.strip()
    fenced = _JSON_FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in model response")
        candidate = text[start : end + 1]
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            value = json.loads(_escape_inner_quotes(candidate))
    if not isinstance(value, dict):
        raise ValueError("Model response JSON must be an object")
    return value


def extract_json_array(raw: str) -> list:
    """Parse a JSON array, tolerating an object wrapper such as {"claims": [...]}."""
    text = raw.strip()
    fenced = _JSON_FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            value = json.loads(text[start : end + 1])
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end <= start:
                raise ValueError("No JSON array found in model response")
            wrapped = json.loads(text[start : end + 1])
            if not isinstance(wrapped, dict):
                raise ValueError("Model response is not a JSON array")
            for key in ("claims", "results", "items", "data"):
                if isinstance(wrapped.get(key), list):
                    return wrapped[key]
            raise ValueError("JSON object does not contain a claims array")
    if isinstance(value, dict):
        for key in ("claims", "results", "items", "data"):
            if isinstance(value.get(key), list):
                return value[key]
        raise ValueError("JSON object does not contain a claims array")
    if not isinstance(value, list):
        raise ValueError("Model response is not a JSON array")
    return value
