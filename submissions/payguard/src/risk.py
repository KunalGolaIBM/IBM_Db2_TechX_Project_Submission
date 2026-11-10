"""PayGuard risk engine: fuses rule signals, Db2 entity intelligence, Db2 vector search and velocity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from config import settings
from signals import context_signals, extract_entities, run_rules


class Repo(Protocol):  # what the engine needs from Db2 (see db.Db2Repository)
    def lookup_entities(self, entities: list[tuple[str, str]]) -> list[dict]: ...
    def search_patterns(self, vec: list[float], region: str = "GLOBAL", k: int = 5) -> list[dict]: ...
    def search_reports(self, vec: list[float], k: int = 3) -> list[dict]: ...
    def payee_velocity(self, payee_email: str, hours: int = 24) -> dict: ...
    def insert_screening(self, s: dict) -> int: ...


# Cosine-similarity cut-offs differ by embedder: semantic models score higher overall.
THRESHOLDS = {
    "gemini": {"strong": 0.78, "weak": 0.70, "report": 0.82},
    "local": {"strong": 0.33, "weak": 0.25, "report": 0.45},
}

CATEGORY_LABELS = {
    "payment_method": "Unprotected payment method", "off_platform": "Off-platform payment",
    "gift_card": "Gift-card scam", "crypto": "Crypto payment scam", "pressure": "Pressure tactics",
    "phishing": "Phishing / credential theft", "advance_fee": "Advance-fee fraud",
    "overpayment": "Overpayment scam", "fake_alert": "Fake payment alert", "impersonation": "Impersonation",
    "too_good": "Too good to be true", "tech_support": "Remote-access scam", "amount": "High value",
    "known_scammer": "Reported scammer", "community": "Community reports", "velocity": "Unusual activity",
    "trusted": "Trusted payee", "account_switch": "Third-party account", "new_seller": "New seller",
}


@dataclass
class ScreenRequest:
    merchant: str = ""
    payee_email: str = ""
    amount: float = 0.0
    currency: str = "USD"
    payment_method: str = "goods_services"
    message: str = ""
    region: str = "NG"
    seller_account_age_days: int | None = None
    market_price: float | None = None


@dataclass
class ScreenResult:
    risk_score: int
    verdict: str
    top_category: str | None
    reasons: list[dict]
    matched_patterns: list[dict]
    similar_reports: list[dict]
    entities: list[dict]
    advice: list[str]
    extracted: dict
    screening_id: int | None = None
    ai: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class RiskEngine:
    def __init__(self, repo: Repo, embedder):
        self.repo = repo
        self.embedder = embedder
        kind = "gemini" if getattr(embedder, "name", "").startswith("gemini") else "local"
        self.th = THRESHOLDS[kind]

    def screen(self, req: ScreenRequest, persist: bool = True) -> ScreenResult:
        text = " \n".join(x for x in (req.merchant, req.message) if x)
        extracted = extract_entities(text, req.payee_email)
        if req.payee_email and req.payee_email.lower() not in extracted.emails:
            extracted.emails.append(req.payee_email.lower())
        if not req.payee_email and extracted.emails:  # pasted chats usually contain the seller's e-mail
            req.payee_email = extracted.emails[0]

        reasons: list[dict] = [s.as_dict() for s in run_rules(text)]
        reasons += [s.as_dict() for s in context_signals(merchant=req.merchant, payee_email=req.payee_email,
                                                         amount=req.amount, method=req.payment_method,
                                                         extracted=extracted,
                                                         seller_account_age_days=req.seller_account_age_days,
                                                         market_price=req.market_price)]
        floor = 0

        # 1) Db2 entity intelligence --------------------------------------------------------
        entities = self.repo.lookup_entities(extracted.as_entities())
        for e in entities:
            ev = f'{e["entity_type"]}: {e["entity_value"]}'
            n = int(e.get("report_count") or 0)
            if e["status"] == "BLOCKED":
                reasons.append({"source": "db2_entity", "code": "BLOCKED_ENTITY", "category": "known_scammer",
                                "label": f"On PayGuard blocklist ({n} reports)", "weight": 70, "evidence": ev})
                floor = max(floor, 85)
            elif e["status"] == "SUSPECT":
                reasons.append({"source": "db2_entity", "code": "SUSPECT_ENTITY", "category": "known_scammer",
                                "label": f"Previously reported ({n} report{'s' if n != 1 else ''})",
                                "weight": 20 + 6 * min(n, 5), "evidence": ev})
            elif e["status"] == "TRUSTED" and e["entity_type"] in ("email", "domain"):
                reasons.append({"source": "db2_entity", "code": "TRUSTED_ENTITY", "category": "trusted",
                                "label": "Verified trusted merchant", "weight": -20, "evidence": ev})

        # 2) Db2 vector search: known scam playbooks + community reports --------------------
        matched, similar = [], []
        if text.strip():
            vec = self.embedder.embed([text], task="query")[0]
            matched = self.repo.search_patterns(vec, region=req.region or "GLOBAL", k=3)
            similar = self.repo.search_reports(vec, k=3)
            for p in matched[:2]:
                sim = p["similarity"]
                if sim >= self.th["weak"]:
                    strength = 1.0 if sim >= self.th["strong"] else 0.6
                    reasons.append({"source": "db2_vector", "code": "PATTERN_MATCH", "category": p["category"],
                                    "label": f'Matches known scam: {p["title"]}',
                                    "weight": round(p["severity"] * 7 * strength),
                                    "evidence": f"cosine similarity {sim:.2f}"})
            close = [r for r in similar if r["similarity"] >= self.th["report"]]
            if close:
                reasons.append({"source": "db2_vector", "code": "COMMUNITY_MATCH", "category": "community",
                                "label": f"{len(close)} community report(s) describe a near-identical message",
                                "weight": 18, "evidence": close[0]["narrative"][:140]})

        # 3) Velocity from Db2 screening history ---------------------------------------------
        if req.payee_email:
            v = self.repo.payee_velocity(req.payee_email, hours=24)
            if int(v.get("blocked") or 0) >= 1:
                reasons.append({"source": "db2_history", "code": "RECENT_BLOCKS", "category": "velocity",
                                "label": f'Payee blocked {v["blocked"]}x in the last 24h', "weight": 18,
                                "evidence": f'{v["attempts"]} attempts'})
            elif int(v.get("attempts") or 0) >= 5:
                reasons.append({"source": "db2_history", "code": "HIGH_VELOCITY", "category": "velocity",
                                "label": "Many payments to this payee in 24h", "weight": 10,
                                "evidence": f'{v["attempts"]} attempts'})

        # Hard indicators: diagnostic on their own, whatever else the message says.
        hard = {"CREDENTIALS": 70, "GIFT_CARD": 65, "METHOD_GIFT_CARD": 65, "REMOTE_ACCESS": 65, "LOOKALIKE_DOMAIN": 65}
        for r in reasons:
            floor = max(floor, hard.get(r["code"], 0))
        # A contact other buyers already reported, now showing a known scam behaviour, is treated as a scam.
        scam_cats = {"payment_method", "off_platform", "gift_card", "crypto", "phishing", "advance_fee",
                     "overpayment", "fake_alert", "impersonation", "account_switch", "tech_support"}
        if any(r["code"] == "SUSPECT_ENTITY" for r in reasons) and any(
                r["source"] == "rule" and r["category"] in scam_cats and r["weight"] >= 20 for r in reasons):
            floor = max(floor, 70)
        score, top = self._score(reasons, floor)
        verdict = self._verdict(score)
        advice = self._advice(verdict, reasons, matched)
        result = ScreenResult(score, verdict, top, sorted(reasons, key=lambda r: -r["weight"]), matched, similar,
                              entities, advice, extracted.__dict__)
        if persist:
            result.screening_id = self.repo.insert_screening({
                "merchant": req.merchant, "payee_email": req.payee_email, "amount": req.amount,
                "currency": req.currency, "payment_method": req.payment_method, "message": req.message,
                "risk_score": score, "verdict": verdict, "top_category": top, "reasons": result.reasons,
            })
        return result

    @staticmethod
    def _score(reasons: list[dict], floor: int) -> tuple[int, str | None]:
        """Per category: strongest signal + 40% of the next (corroboration from another source).
        Across categories: the two strongest count fully, the rest at 60%."""
        by_cat: dict[str, list[int]] = {}
        for r in reasons:
            by_cat.setdefault(r["category"], []).append(r["weight"])
        best: dict[str, float] = {}
        for c, ws in by_cat.items():
            if c == "trusted":
                best[c] = min(ws)
                continue
            ws = sorted((w for w in ws if w > 0), reverse=True)
            best[c] = ws[0] + (0.4 * ws[1] if len(ws) > 1 else 0) if ws else 0
        positives = sorted((w for c, w in best.items() if w > 0), reverse=True)
        total = sum(w * (1.0 if i < 2 else 0.6) for i, w in enumerate(positives)) + best.get("trusted", 0)
        score = int(max(floor, min(100, round(total))))
        score = max(0, score)
        top = max((c for c in best if best[c] > 0), key=lambda c: best[c], default=None)
        return score, top

    @staticmethod
    def _verdict(score: int) -> str:
        if score >= settings.block_threshold:
            return "BLOCK"
        if score >= settings.review_threshold:
            return "REVIEW"
        return "ALLOW"

    @staticmethod
    def _advice(verdict: str, reasons: list[dict], matched: list[dict]) -> list[str]:
        tips: list[str] = []
        codes = {r["code"] for r in reasons}
        if "FRIENDS_FAMILY" in codes or "METHOD_FRIENDS_FAMILY" in codes:
            tips.append("Pay with PayPal 'Goods & Services' so you are covered by Purchase Protection.")
        if "CREDENTIALS" in codes:
            tips.append("Never share OTPs, PINs, BVN or passwords - no real merchant or bank will ask.")
        if "OFF_PLATFORM" in codes:
            tips.append("Keep the conversation and payment on the platform; scammers move you off it to remove protection.")
        if "GIFT_CARD" in codes or "CRYPTO_PAY" in codes:
            tips.append("Legitimate sellers do not demand gift cards or crypto. Treat it as a scam.")
        if "LOOKALIKE_DOMAIN" in codes:
            tips.append("Type the official website address yourself instead of clicking the link.")
        covered = {"payment_method": "FRIENDS_FAMILY", "phishing": "CREDENTIALS", "off_platform": "OFF_PLATFORM",
                   "gift_card": "GIFT_CARD", "crypto": "CRYPTO_PAY", "impersonation": "LOOKALIKE_DOMAIN"}
        if matched and verdict != "ALLOW" and matched[0].get("advice"):
            if covered.get(matched[0]["category"]) not in codes:
                tips.append(matched[0]["advice"])
        if verdict == "ALLOW" and not tips:
            tips.append("No known red flags. Still confirm the item and delivery details before paying.")
        return tips[:4]
