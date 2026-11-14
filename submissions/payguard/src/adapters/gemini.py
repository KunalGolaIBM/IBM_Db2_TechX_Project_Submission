"""Minimal Google Gemini client (REST): text, JSON output and function calling.

Kept dependency-free (httpx only) so the agent loop is fully visible to judges.
"""
from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from typing import Any, Callable

import httpx

from config import settings

log = logging.getLogger("payguard.llm")
API = "https://generativelanguage.googleapis.com/v1beta/models"
deadline: ContextVar[float | None] = ContextVar("gemini_deadline", default=None)


class LLMUnavailable(RuntimeError):
    pass


def _post(body: dict, model: str | None = None) -> dict:
    if not settings.gemini_api_key:
        raise LLMUnavailable("GEMINI_API_KEY not set")
    selected_model = model or settings.gemini_model
    if selected_model.startswith("gemini-4-") and "generationConfig" in body:
        # Gemini 4 ignores sampling controls; keep schemas and other options intact.
        body = {**body, "generationConfig": {
            key: value for key, value in body["generationConfig"].items()
            if key not in {"temperature", "topP", "topK"}
        }}
    url = f"{API}/{selected_model}:generateContent"
    timeout = getattr(settings, "gemini_timeout", 5)
    limit = deadline.get()
    if limit is not None:
        timeout = min(timeout, limit - time.monotonic())
        if timeout <= 0:
            raise LLMUnavailable("Investigation deadline exceeded")
    r = httpx.post(url, json=body, headers={"x-goog-api-key": settings.gemini_api_key}, timeout=timeout)
    if r.status_code >= 400:
        raise LLMUnavailable(f"Gemini error {r.status_code}: {r.text[:300]}")
    return r.json()


def _text(resp: dict) -> str:
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def generate(prompt: str, system: str = "", temperature: float = 0.2) -> str:
    body: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": temperature}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return _text(_post(body)).strip()


def generate_json(prompt: str, system: str = "", schema: dict | None = None) -> dict:
    cfg: dict[str, Any] = {"temperature": 0.1, "responseMimeType": "application/json"}
    if schema:
        cfg["responseSchema"] = schema
    body: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    raw = _text(_post(body)).strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    return json.loads(raw)


def run_tool_agent(
    prompt: str,
    system: str,
    tools: list[dict],
    handlers: dict[str, Callable[..., Any]],
    max_steps: int = 6,
) -> tuple[str, list[dict]]:
    """Gemini function-calling loop. Returns (final_text, trace of tool calls)."""
    token = deadline.set(time.monotonic() + settings.investigation_timeout)
    try:
        return _run_tool_agent(prompt, system, tools, handlers, max_steps)
    finally:
        deadline.reset(token)


def _run_tool_agent(prompt, system, tools, handlers, max_steps):
    contents: list[dict] = [{"role": "user", "parts": [{"text": prompt}]}]
    trace: list[dict] = []
    for _ in range(max_steps):
        resp = _post({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": tools}],
            "generationConfig": {"temperature": 0.2},
        })
        cand = resp.get("candidates", [{}])[0].get("content", {"role": "model", "parts": []})
        calls = [p["functionCall"] for p in cand.get("parts", []) if "functionCall" in p]
        if not calls:
            return _text(resp).strip(), trace
        contents.append(cand)  # keep model turn verbatim (preserves thought signatures)
        responses = []
        for call in calls:
            limit = deadline.get()
            if limit is not None and time.monotonic() >= limit:
                raise LLMUnavailable("Investigation deadline exceeded")
            name, args = call.get("name"), call.get("args", {}) or {}
            try:
                result = handlers[name](**args)
            except Exception as exc:  # tool errors go back to the model, not the user
                result = {"error": str(exc)[:300]}
            trace.append({"tool": name, "args": args, "result_preview": json.dumps(result, default=str)[:400]})
            responses.append({"functionResponse": {"name": name, "response": {"result": result}}})
        contents.append({"role": "user", "parts": responses})
    return "I reached my investigation step limit; see the evidence above.", trace
