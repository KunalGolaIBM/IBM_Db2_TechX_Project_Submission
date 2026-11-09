"""LLM client with three behaviours that matter for reproducibility:

* ``mock``   - no key needed; templated narration from the rule trace
* ``live``   - any OpenAI-compatible chat-completions endpoint
* ``fallback`` - a live call that fails silently degrades to mock output so a
  demo can never hard-crash because a free-tier quota ran out.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings
from ..models import NormalizedProfile, coerce_facts
from ..rules import gap_hint
from . import prompts
from .extract import heuristic_normalize


class LLMError(RuntimeError):
    pass


# ---------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------
def _post(messages: List[Dict[str, str]], json_mode: bool) -> str:
    payload: Dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=settings.llm_timeout,
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    if response.status_code >= 400:
        body = response.text[:400]
        if json_mode and "response_format" in body:
            payload.pop("response_format", None)
            response = httpx.post(
                f"{settings.llm_base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=settings.llm_timeout,
            )
        if response.status_code >= 400:
            raise LLMError(f"LLM returned HTTP {response.status_code}: {body}")

    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {response.text[:300]}") from exc


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


# ---------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------
def normalize_profile(text: str) -> NormalizedProfile:
    if settings.llm_is_mock:
        return heuristic_normalize(text)

    messages = [
        {"role": "system", "content": prompts.NORMALIZE_SYSTEM},
        {"role": "user", "content": prompts.NORMALIZE_USER.format(text=text)},
    ]
    try:
        raw = _post(messages, json_mode=True)
        data = _parse_json(raw)
        facts = coerce_facts(data.get("facts", data))
        if not facts:
            raise LLMError("model returned no usable facts")
        unknowns = [str(u) for u in data.get("unknowns", [])][:12]
        query = str(data.get("retrieval_query") or text)[:800]
        return NormalizedProfile(facts=facts, retrieval_query=query, unknowns=unknowns,
                                 notes=["facts extracted by " + settings.llm_model])
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        profile = heuristic_normalize(text)
        profile.notes.append(f"LLM normalisation unavailable ({exc.__class__.__name__}); "
                             "used the deterministic extractor instead")
        return profile


# ---------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------
def narrate(contexts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return {scheme_id: {narrative, cited_chunk_ids}} for the given contexts."""
    if not contexts:
        return {}

    if settings.llm_is_mock:
        return {ctx["scheme_id"]: _mock_narrative(ctx) for ctx in contexts}

    messages = [
        {"role": "system", "content": prompts.EXPLAIN_SYSTEM},
        {"role": "user", "content": prompts.explain_user(contexts)},
    ]
    try:
        raw = _post(messages, json_mode=True)
        data = _parse_json(raw)
        produced = {str(s.get("scheme_id")): s for s in data.get("schemes", [])}
    except (LLMError, ValueError, json.JSONDecodeError, TypeError, IndexError):
        return {ctx["scheme_id"]: _mock_narrative(ctx) for ctx in contexts}

    output: Dict[str, Dict[str, Any]] = {}
    for ctx in contexts:
        item = produced.get(ctx["scheme_id"])
        if not item or not item.get("narrative"):
            output[ctx["scheme_id"]] = _mock_narrative(ctx)
            continue
        allowed = {c["chunk_id"] for c in ctx["clauses"]}
        cited = [c for c in item.get("cited_chunk_ids", []) if c in allowed]
        if not cited:
            cited = [c["chunk_id"] for c in ctx["clauses"][:1]]
        output[ctx["scheme_id"]] = {
            "narrative": str(item["narrative"])[:600],
            "cited_chunk_ids": cited,
        }
    return output


def _mock_narrative(ctx: Dict[str, Any]) -> Dict[str, Any]:
    label = ctx["label"]
    name = ctx["name"]
    rules = ctx["rules"]
    blocking = [r for r in rules if r["mandatory"] and r["verdict"] == "FAIL"]
    missing = [r for r in rules if r["mandatory"] and r["verdict"] == "UNKNOWN"]
    passed = sum(1 for r in rules if r["verdict"] == "PASS")
    clauses = ctx.get("clauses", [])
    cite = [clauses[0]["chunk_id"]] if clauses else []

    if label == "ELIGIBLE":
        text = (
            f"All mandatory criteria are met ({passed} of {len(rules)} checks pass). "
            f"{ctx.get('benefit_summary') or ''} Keep the documents named in "
            f"{rules[0]['clause_ref'] if rules else 'the scheme notice'} ready."
        )
    elif label == "NEAR_MISS":
        text = (
            f"One threshold stands between you and {name}: "
            f"{gap_hint(_as_rule(blocking[0]))}. Every other criterion matches, so this "
            f"is the single thing worth fixing."
        )
    elif label == "CLARIFY":
        keys = ", ".join(r["criterion_code"].replace("_", " ") for r in missing[:3])
        text = (
            f"Nothing disqualifies you here, but the decision needs: {keys}. "
            "Answer those and the same rules can be re-evaluated."
        )
    else:
        reasons = "; ".join(
            f"{r['criterion_code'].replace('_', ' ')} must be {r['threshold']}"
            for r in blocking[:2]
        )
        text = f"Not applicable at present. {reasons}."
    return {"narrative": text.strip(), "cited_chunk_ids": cite}


def _as_rule(row: Dict[str, Any]):
    from ..models import RuleRow

    return RuleRow(
        scheme_id=row.get("scheme_id", "unknown"),
        rule_id=int(row.get("rule_id", 0)),
        criterion_code=row["criterion_code"],
        rule_op=row["rule_op"],
        mandatory=int(row.get("mandatory", 1)),
        verdict=row.get("verdict", "FAIL"),
        clause_ref=row.get("clause_ref", ""),
        value_num=row.get("value_num"),
        value_text=row.get("value_text"),
    )
