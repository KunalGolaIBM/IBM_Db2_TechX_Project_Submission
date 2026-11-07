"""Small LLM client over plain HTTP (no vendor SDKs needed).

Providers:
  ollama   - local models, e.g. IBM Granite via `ollama pull granite3.3:2b`
  watsonx  - IBM watsonx.ai chat API (IAM API key + project id)
  openai   - any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, Gemini's OpenAI endpoint)
  none     - no LLM; agents use deterministic fallbacks (the app still works end to end)
"""
from __future__ import annotations

import json
import re
import time

import requests

from .config import Settings


class LLMUnavailable(RuntimeError):
    pass


class BaseLLM:
    name = "none"

    def chat(self, system: str, user: str, temperature: float = 0.1) -> str:
        raise LLMUnavailable("No LLM provider configured (LLM_PROVIDER=none).")

    @property
    def available(self) -> bool:
        return self.name != "none"


class NoLLM(BaseLLM):
    pass


class OllamaLLM(BaseLLM):
    def __init__(self, url: str, model: str) -> None:
        self.url, self.model = url.rstrip("/"), model
        self.name = f"ollama:{model}"

    def chat(self, system: str, user: str, temperature: float = 0.1) -> str:
        try:
            r = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "options": {"temperature": temperature},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=240,
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
        except Exception as exc:
            raise LLMUnavailable(f"Ollama call failed: {exc}") from exc


class OpenAICompatibleLLM(BaseLLM):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.name = f"openai-compatible:{model}"

    def chat(self, system: str, user: str, temperature: float = 0.1) -> str:
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": temperature,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=180,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMUnavailable(f"OpenAI-compatible call failed: {exc}") from exc


class WatsonxLLM(BaseLLM):
    IAM_URL = "https://iam.cloud.ibm.com/identity/token"

    def __init__(self, url: str, apikey: str, project_id: str, model: str) -> None:
        self.url, self.apikey, self.project_id, self.model = url.rstrip("/"), apikey, project_id, model
        self.name = f"watsonx:{model}"
        self._token: str | None = None
        self._token_exp = 0.0

    def _iam_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = requests.post(
            self.IAM_URL,
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.apikey},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        self._token, self._token_exp = body["access_token"], float(body.get("expiration", time.time() + 3000))
        return self._token

    def chat(self, system: str, user: str, temperature: float = 0.1) -> str:
        try:
            r = requests.post(
                f"{self.url}/ml/v1/text/chat?version=2024-10-08",
                headers={"Authorization": f"Bearer {self._iam_token()}", "Content-Type": "application/json"},
                json={
                    "model_id": self.model,
                    "project_id": self.project_id,
                    "temperature": temperature,
                    "max_tokens": 1500,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=180,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMUnavailable(f"watsonx.ai call failed: {exc}") from exc


def get_llm(settings: Settings) -> BaseLLM:
    p = settings.llm_provider
    if p == "ollama":
        return OllamaLLM(settings.ollama_url, settings.ollama_model)
    if p == "openai" and settings.openai_api_key:
        return OpenAICompatibleLLM(settings.openai_base_url, settings.openai_api_key, settings.openai_model)
    if p == "watsonx" and settings.watsonx_apikey and settings.watsonx_project_id:
        return WatsonxLLM(settings.watsonx_url, settings.watsonx_apikey, settings.watsonx_project_id, settings.watsonx_model)
    return NoLLM()


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (tolerates ``` fences and chatter)."""
    cleaned = re.sub(r"```(?:json)?", "", text)
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("No JSON object in model output")
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])
    raise ValueError("Unbalanced JSON object in model output")
