"""LLM provider selection and schema-validated calls.

Three providers sit behind one interface:
- openrouter: any model on OpenRouter through its OpenAI-compatible API (default for dev).
- openai_compatible: any other OpenAI-compatible endpoint (OpenAI, Gemini, vLLM, ...).
- ollama: a local model, so the project runs with no API key at all.

Every call returns a Pydantic object or raises LLMError. Callers treat LLMError as a
reason to fail closed; nothing downstream ever sees unvalidated model output.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from .config import ConfigError, Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

APP_URL = "https://github.com/JustJay7/asof"
APP_TITLE = "AsOf"


class LLMError(RuntimeError):
    """The model call failed, timed out, or returned output that does not fit the schema."""


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    value: T
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    attempts: int


def _run_with_deadline(fn, deadline_s: float):
    """Run fn() in a daemon thread and stop waiting after deadline_s seconds.

    The thread cannot be killed, but it no longer blocks the caller or interpreter exit,
    and the output-token cap set on every provider bounds how long it keeps running.
    """
    box: dict = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller's thread
            box["error"] = exc

    worker = threading.Thread(target=target, name="asof-llm-call", daemon=True)
    worker.start()
    worker.join(deadline_s)
    if worker.is_alive():
        raise TimeoutError(f"no answer within {deadline_s}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


class LLMClient:
    """A configured chat model plus the provider details needed for structured output."""

    def __init__(
        self, chat_model: BaseChatModel, provider: str, model_name: str, attempts: int, deadline_s: float
    ):
        self.chat_model = chat_model
        self.provider = provider
        self.model_name = model_name
        self._attempts = max(1, attempts)
        self._deadline_s = deadline_s

    @property
    def info(self) -> str:
        return f"{self.provider}:{self.model_name}"

    def run(self, fn):
        """Run any LLM-backed callable (for example a LangChain chain) under the same deadline."""
        try:
            return _run_with_deadline(fn, self._deadline_s)
        except TimeoutError as exc:
            raise LLMError(f"{self.info} did not answer within {self._deadline_s:.0f}s") from exc
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"{self.info} call failed: {type(exc).__name__}") from exc

    def structured(self, schema: type[T], messages: list[tuple[str, str]],
                   choices: dict[str, list[str]] | None = None) -> LLMResult[T]:
        """Call the model and parse its reply into `schema`, or raise LLMError.

        `choices` maps a field name to the only values it may take. For a local model the
        decoding grammar enforces them (see bounded_schema); hosted models are steered by the
        prompt and checked by the gate afterwards, as before.

        Each attempt runs under a hard wall-clock deadline, because client read timeouts do
        not fire while a model keeps streaming (a local model stuck in a generation loop
        does exactly that). A timeout is final; only malformed output or a transport error
        gets one more attempt.
        """
        if self.provider == "ollama":
            runnable = _bounded_ollama_runnable(self.chat_model, schema, choices)
        else:
            runnable = self.chat_model.with_structured_output(
                schema, method="json_schema", include_raw=True, strict=True)

        last_error: Exception | None = None
        started = time.monotonic()
        for attempt in range(1, self._attempts + 1):
            try:
                out = _run_with_deadline(lambda: runnable.invoke(messages), self._deadline_s)
            except TimeoutError as exc:
                raise LLMError(f"{self.info} did not answer within {self._deadline_s:.0f}s") from exc
            except Exception as exc:  # noqa: BLE001 - every provider raises its own types
                last_error = exc
                log.warning("LLM call failed (attempt %d, %s): %s", attempt, self.info, type(exc).__name__)
                continue
            parsed, error = out.get("parsed"), out.get("parsing_error")
            if isinstance(parsed, schema) and error is None:
                usage = getattr(out.get("raw"), "usage_metadata", None) or {}
                return LLMResult(
                    value=parsed,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    attempts=attempt,
                )
            last_error = error or ValueError("model returned no parseable output")
            log.warning("LLM output rejected (attempt %d, %s): %s", attempt, self.info, last_error)
        raise LLMError(f"{self.info} gave no valid {schema.__name__}: {last_error}") from last_error


MAX_STRING_CHARS = 400  # every string any schema needs is far shorter


def bounded_schema(schema: type[BaseModel], max_chars: int = MAX_STRING_CHARS,
                   choices: dict[str, list[str]] | None = None) -> dict:
    """The model's JSON schema with maxLength on every free-text string.

    Ollama turns the schema into a decoding grammar. Without a length bound, a local model
    can keep appending to a string forever: qwen2.5:7b once filled `quoted_span` with
    "[2026-06-02 is the date of the claim.]" until the output cap. With maxLength the
    grammar forces the string, and so the JSON, to close.

    `choices` restricts named string fields to fixed values. The judge uses it so a local
    model can only quote a real sentence of a retrieved clause and cite a retrieved clause
    ID: qwen2.5:7b judged correctly but paraphrased its quotes, which the verbatim-quote
    rule (rightly) rejects.
    """
    def restrict(prop: dict, values: list[str]) -> None:
        options = [{"type": "string", "enum": values}]
        if any(o.get("type") == "null" for o in prop.get("anyOf", [])):
            options.append({"type": "null"})
        for key in ("anyOf", "type", "maxLength"):
            prop.pop(key, None)
        prop["anyOf"] = options

    def walk(node):
        if isinstance(node, dict):
            for name, prop in (node.get("properties") or {}).items():
                if choices and name in choices and choices[name]:
                    restrict(prop, choices[name])
        if isinstance(node, dict):
            if node.get("type") == "string" and "enum" not in node and "maxLength" not in node:
                node["maxLength"] = max_chars
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        return node

    return walk(schema.model_json_schema())


def _bounded_ollama_runnable(chat_model: BaseChatModel, schema: type[T], choices: dict[str, list[str]] | None = None):
    """Same contract as with_structured_output(include_raw=True), with a bounded grammar."""
    bound = chat_model.bind(format=bounded_schema(schema, choices=choices))

    class _Runnable:
        @staticmethod
        def invoke(messages):
            raw = bound.invoke(messages)
            try:
                return {"raw": raw, "parsed": schema.model_validate_json(raw.content), "parsing_error": None}
            except Exception as exc:  # noqa: BLE001 - reported as a parsing error, then retried once
                return {"raw": raw, "parsed": None, "parsing_error": exc}

    return _Runnable()


def _non_streaming_ollama():
    """ChatOllama that asks for one complete response instead of a token stream.

    With streaming, a model stuck in a generation loop keeps sending tokens, so the HTTP
    read timeout never fires and an abandoned request keeps the local server busy. Without
    streaming, the timeout fires, the client disconnects and Ollama cancels the generation.
    """
    from langchain_ollama import ChatOllama

    class NonStreamingChatOllama(ChatOllama):
        def _chat_params(self, messages, stop=None, **kwargs):
            kwargs.setdefault("stream", False)
            return super()._chat_params(messages, stop, **kwargs)

    return NonStreamingChatOllama


def build_llm(settings: Settings, provider: str | None = None, model: str | None = None) -> LLMClient:
    """Create the configured LLM client. `provider` and `model` override settings (used by eval)."""
    provider = provider or settings.llm_provider
    attempts = 2
    deadline = settings.llm_timeout_s
    max_out = settings.llm_max_output_tokens

    if provider == "ollama":
        name = model or settings.ollama_model
        chat = _non_streaming_ollama()(
            model=name,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_ctx=8192,
            num_predict=max_out,
            client_kwargs={"timeout": settings.llm_timeout_s},
        )
        return LLMClient(chat, provider, name, attempts, deadline)

    from langchain_openai import ChatOpenAI

    if provider == "openrouter":
        settings.require("openrouter_api_key")
        name = model or settings.openrouter_model
        chat = ChatOpenAI(
            model=name,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            max_tokens=max_out,
            use_responses_api=False,
            default_headers={"HTTP-Referer": APP_URL, "X-Title": APP_TITLE},
            # Only route to upstream providers that honour every request parameter,
            # including the JSON schema. Otherwise OpenRouter may silently drop it.
            extra_body={"provider": {"require_parameters": True}},
        )
        return LLMClient(chat, provider, name, attempts, deadline)

    if provider == "openai_compatible":
        settings.require("openai_compat_base_url", "openai_compat_api_key", "openai_compat_model")
        name = model or settings.openai_compat_model or ""
        chat = ChatOpenAI(
            model=name,
            api_key=settings.openai_compat_api_key,
            base_url=settings.openai_compat_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            max_tokens=max_out,
            use_responses_api=False,
        )
        return LLMClient(chat, provider, name, attempts, deadline)

    raise ConfigError(f"Unknown LLM_PROVIDER {provider!r}")
