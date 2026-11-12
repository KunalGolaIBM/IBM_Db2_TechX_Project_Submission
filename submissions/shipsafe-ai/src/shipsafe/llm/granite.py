"""Local IBM Granite models through Ollama.

ShipSafe talks to one local Ollama server. Nothing leaves the machine.
`ollama_status()` is used by `shipsafe doctor`, the API readiness probe and the
tests to report exactly which models are present.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

from ..config import LlmConfig

# CrewAI and LiteLLM send anonymous telemetry by default; ShipSafe keeps everything local.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("LITELLM_TELEMETRY", "False")


class ModelUnavailable(RuntimeError):
    """Raised when Ollama is not running or a required Granite model is not pulled."""


def _get(url: str, timeout: float) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed local URL from config
        return json.loads(resp.read().decode("utf-8"))


def ollama_status(cfg: LlmConfig, timeout: float = 3.0) -> Dict[str, Any]:
    """Whether Ollama answers and which of the configured models are installed."""
    try:
        version = _get(f"{cfg.host}/api/version", timeout).get("version")
        models: List[str] = [m.get("name", "") for m in _get(f"{cfg.host}/api/tags", timeout).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"running": False, "host": cfg.host, "error": str(exc)[:200],
                "chat_model": cfg.chat_model, "embed_model": cfg.embed_model,
                "chat_model_ready": False, "embed_model_ready": False, "models": []}

    def present(name: str) -> bool:
        return any(m == name or m == f"{name}:latest" for m in models)

    return {"running": True, "host": cfg.host, "version": version, "models": models,
            "chat_model": cfg.chat_model, "embed_model": cfg.embed_model,
            "chat_model_ready": present(cfg.chat_model), "embed_model_ready": present(cfg.embed_model)}


def require_models(cfg: LlmConfig, chat: bool = True, embed: bool = False) -> None:
    st = ollama_status(cfg)
    if not st["running"]:
        raise ModelUnavailable(f"Ollama is not reachable at {cfg.host}. Start it with `ollama serve`.")
    if chat and not st["chat_model_ready"]:
        raise ModelUnavailable(f"Granite chat model '{cfg.chat_model}' is not installed. Run: ollama pull {cfg.chat_model}")
    if embed and not st["embed_model_ready"]:
        raise ModelUnavailable(f"Embedding model '{cfg.embed_model}' is not installed. Run: ollama pull {cfg.embed_model}")


def chat_model(cfg: LlmConfig, temperature: float = None):
    """LangChain chat model for Granite."""
    from langchain_ollama import ChatOllama

    return ChatOllama(model=cfg.chat_model, base_url=cfg.host,
                      temperature=cfg.temperature if temperature is None else temperature,
                      num_ctx=8192, client_kwargs={"timeout": cfg.timeout_s})


def crew_llm(cfg: LlmConfig, temperature: float = None):
    """CrewAI LLM handle for Granite (routed through LiteLLM's Ollama provider)."""
    from crewai import LLM

    return LLM(model=f"ollama/{cfg.chat_model}", base_url=cfg.host,
               temperature=cfg.temperature if temperature is None else temperature, timeout=cfg.timeout_s)
