"""AI layer: a Gemini tool-calling investigator whose tools are Db2 queries.

Safety principle: the AI may *raise* risk or explain it, but can never lower a verdict
produced by the deterministic + Db2 evidence. Without a GEMINI_API_KEY every feature
falls back to deterministic logic, so the app always works.
"""
from __future__ import annotations

import json
import re
from typing import Any

import llm
from langchain_db2_tools import run_investigation
from risk import CATEGORY_LABELS, RiskEngine, ScreenRequest, ScreenResult

INVESTIGATOR_SYSTEM = """You are PayGuard, a payment-fraud investigator protecting buyers in Nigeria and worldwide.
You get a payment someone is about to make plus PayGuard's evidence (rule signals, Db2 blocklist hits,
vector matches against known scam playbooks). Use the tools (they query the IBM Db2 fraud database) to
check anything still unclear, then answer ONLY with JSON:
{"summary": "2-3 plain sentences for a non-technical buyer",
 "advice": ["short actionable tip", "..."],
 "escalate": true|false,
 "extra_risk": 0-20,
 "escalation_reason": "why, or empty"}
Rules: never tell the user a payment is safe if evidence shows red flags; you may only add risk, never remove it;
do not invent facts not present in the evidence or tool results."""

PIDGIN_NOTE = "Write summary and advice in clear Nigerian Pidgin English."

TOOLS = [
    {"name": "lookup_entity", "description": "Check an email, phone, domain or wallet against the Db2 blocklist and report counts.",
     "parameters": {"type": "object", "properties": {
         "entity_type": {"type": "string", "enum": ["email", "phone", "domain", "wallet", "account"]},
         "value": {"type": "string"}}, "required": ["entity_type", "value"]}},
    {"name": "search_scam_patterns", "description": "Vector-search known scam playbooks stored in Db2.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"},
                                                     "region": {"type": "string"}}, "required": ["query"]}},
    {"name": "search_community_reports", "description": "Vector-search scam reports submitted by other users.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "search_scam_examples", "description": "Search hand-reviewed Nigerian messages and labels in Db2 SCAM_EXAMPLES using LangChain DB2VS.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "payee_history", "description": "Screening attempts and blocks for a payee e-mail in the last N hours.",
     "parameters": {"type": "object", "properties": {"payee_email": {"type": "string"},
                                                     "hours": {"type": "integer"}}, "required": ["payee_email"]}},
]


class Investigator:
    def __init__(self, repo, embedder, engine: RiskEngine):
        self.repo, self.embedder, self.engine = repo, embedder, engine

    # ---- tool handlers: each one is a Db2 query -----------------------------------------
    def _handlers(self) -> dict[str, Any]:
        def lookup_entity(entity_type: str, value: str):
            return self.repo.lookup_entities([(entity_type, value)]) or {"status": "not_found"}

        def search_scam_patterns(query: str, region: str = "NG"):
            vec = self.embedder.embed([query], task="query")[0]
            return [{k: p[k] for k in ("title", "category", "severity", "similarity", "red_flags")}
                    for p in self.repo.search_patterns(vec, region=region, k=3)]

        def search_community_reports(query: str):
            vec = self.embedder.embed([query], task="query")[0]
            return [{k: r[k] for k in ("category", "amount", "currency", "narrative", "entity_value", "similarity")}
                    for r in self.repo.search_reports(vec, k=3)]

        def payee_history(payee_email: str, hours: int = 72):
            return self.repo.payee_velocity(payee_email, hours=int(hours))

        def search_scam_examples(query: str):
            vec = self.embedder.embed([query], task="query")[0]
            return self.repo.search_examples(vec, k=3)

        return {"lookup_entity": lookup_entity, "search_scam_patterns": search_scam_patterns,
                "search_community_reports": search_community_reports, "payee_history": payee_history,
                "search_scam_examples": search_scam_examples}

    def explain(self, req: ScreenRequest, result: ScreenResult, language: str = "en") -> dict:
        evidence = {
            "payment": {"merchant": req.merchant, "payee_email": req.payee_email, "amount": req.amount,
                        "currency": req.currency, "method": req.payment_method, "message": req.message[:1500]},
            "risk_score": result.risk_score, "verdict": result.verdict,
            "signals": [{k: r[k] for k in ("label", "weight", "evidence", "source")} for r in result.reasons[:10]],
            "top_pattern_matches": [{k: p[k] for k in ("title", "similarity", "category")} for p in result.matched_patterns],
            "top_example_matches": result.matched_examples,
        }
        system = INVESTIGATOR_SYSTEM + ("\n" + PIDGIN_NOTE if language == "pcm" else "")
        try:
            text, trace = run_investigation(
                "Investigate this payment and return the JSON verdict.\n" + json.dumps(evidence, default=str),
                system, TOOLS, self._handlers(),
            )
            data = _parse_json(text)
            extra = max(0, min(20, int(data.get("extra_risk") or 0)))
            out = {
                "mode": "gemini",
                "summary": str(data.get("summary", "")).strip(),
                "advice": [str(a) for a in data.get("advice", [])][:4],
                "escalate": bool(data.get("escalate")) and extra > 0,
                "extra_risk": extra,
                "escalation_reason": str(data.get("escalation_reason", "")),
                "trace": trace,
            }
            if not out["summary"]:
                raise ValueError("empty summary")
            return out
        except Exception as exc:  # LLM unavailable or malformed -> deterministic explanation
            out = fallback_explanation(result, language)
            out["note"] = f"AI explanation unavailable ({type(exc).__name__}); showing rule-based summary."
            return out

    # ---- agentic commerce: turn a sentence into a structured, screenable order ----------
    def parse_purchase(self, instruction: str) -> dict:
        schema = {"type": "OBJECT", "properties": {
            "item": {"type": "STRING"}, "merchant": {"type": "STRING"}, "payee_email": {"type": "STRING"},
            "amount": {"type": "NUMBER"}, "currency": {"type": "STRING"},
            "payment_method": {"type": "STRING", "enum": ["goods_services", "friends_family", "gift_card", "crypto", "wire"]},
            "seller_message": {"type": "STRING"}},
            "required": ["item", "merchant", "amount", "currency", "payment_method"]}
        try:
            data = llm.generate_json(
                "Extract the purchase the user wants an agent to make. If the seller asked for a specific payment "
                "method (e.g. friends and family, gift card, crypto) set payment_method accordingly, otherwise "
                "goods_services. Copy any quoted seller message verbatim into seller_message.\n\nUser: " + instruction,
                schema=schema)
            data["mode"] = "gemini"
        except Exception:
            data = parse_purchase_fallback(instruction)
        data["currency"] = (data.get("currency") or "USD").upper()[:3]
        data.setdefault("payee_email", "")
        data.setdefault("seller_message", "")
        return data

    # ---- free-form question answering over the Db2 fraud database ------------------------
    def ask(self, question: str, analyst) -> dict:
        handlers = self._handlers()
        handlers["run_analytics_sql"] = lambda question: analyst.answer(question, summarize=False)
        tools = TOOLS + [{"name": "run_analytics_sql",
                          "description": "Answer a statistical question by generating and running a read-only Db2 SQL query.",
                          "parameters": {"type": "object", "properties": {"question": {"type": "string"}},
                                         "required": ["question"]}}]
        try:
            text, trace = run_investigation(
                question,
                "You are PayGuard's assistant. Answer questions about scams, payment safety and the fraud data in "
                "IBM Db2. Use tools for any factual or numeric claim. Be concise.",
                tools, handlers)
            return {"mode": "gemini", "answer": text, "trace": trace}
        except Exception as exc:
            return {"mode": "fallback", "answer": "The AI assistant needs a GEMINI_API_KEY. "
                    "Try the Analyst console's quick questions, which run without AI.", "error": str(exc)[:200]}


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in model output")
    return json.loads(m.group(0))


def fallback_explanation(result: ScreenResult, language: str = "en") -> dict:
    top = [r for r in result.reasons if r["weight"] > 0][:3]
    cat = CATEGORY_LABELS.get(result.top_category or "", "risk")
    if result.verdict == "BLOCK":
        summary = f"Stop. This payment looks like a {cat.lower()}. " + "; ".join(r["label"] for r in top) + "."
        if language == "pcm":
            summary = f"Abeg no pay. Dis one get k-leg - e resemble {cat.lower()}. " + "; ".join(r["label"] for r in top) + "."
    elif result.verdict == "REVIEW":
        summary = "Be careful. Some warning signs were found: " + "; ".join(r["label"] for r in top) + "."
        if language == "pcm":
            summary = "Shine your eye well. Some wahala signs dey: " + "; ".join(r["label"] for r in top) + "."
    else:
        summary = "No known scam signals were found for this payment."
        if language == "pcm":
            summary = "We no see any scam sign for dis payment, but still confirm everything well."
    return {"mode": "rules", "summary": summary, "advice": result.advice, "escalate": False,
            "extra_risk": 0, "escalation_reason": "", "trace": []}


_AMOUNT = re.compile(r"(?:(?P<cur>usd|ngn|gbp|eur|\$|£|€|₦)\s?)(?P<a>\d[\d,]*(?:\.\d+)?)|(?P<b>\d[\d,]*(?:\.\d+)?)\s?(?P<cur2>usd|dollars|ngn|naira|gbp|eur)", re.I)
_CUR = {"$": "USD", "usd": "USD", "dollars": "USD", "£": "GBP", "gbp": "GBP", "€": "EUR", "eur": "EUR",
        "₦": "NGN", "ngn": "NGN", "naira": "NGN"}


def parse_purchase_fallback(text: str) -> dict:
    low = text.lower()
    amount, currency = 0.0, "USD"
    m = _AMOUNT.search(text)
    if m:
        raw = m.group("a") or m.group("b")
        amount = float(raw.replace(",", ""))
        currency = _CUR.get((m.group("cur") or m.group("cur2") or "usd").lower(), "USD")
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    seller = re.search(r"(?:from|seller|vendor|store)\s+@?([\w .'-]{2,40}?)(?:\s+(?:for|at|on|who|they|and)\b|[,.]|$)", text, re.I)
    item = re.search(r"\b(?:buy|order|purchase|get)\s+(?:a |an |the |my )?(.{2,60}?)(?:\s+from|\s+for|[,.]|$)", text, re.I)
    method = "goods_services"
    if re.search(r"friends?\s*(?:and|&|n)\s*family|f&f", low):
        method = "friends_family"
    elif "gift card" in low:
        method = "gift_card"
    elif re.search(r"\b(usdt|btc|bitcoin|crypto)\b", low):
        method = "crypto"
    quote = re.search(r"[\"“](.+?)[\"”]", text, re.S)
    return {"mode": "rules", "item": item.group(1).strip() if item else "item",
            "merchant": seller.group(1).strip() if seller else "", "payee_email": email.group(0) if email else "",
            "amount": amount, "currency": currency, "payment_method": method,
            "seller_message": quote.group(1) if quote else text}
