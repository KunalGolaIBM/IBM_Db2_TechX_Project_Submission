"""Test fixtures. FakeRepo mirrors Db2Repository in memory (test-only; the app itself always uses Db2)."""
import json
import math
import sys
from pathlib import Path

import os

import pytest

for _k in ("GEMINI_API_KEY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"):
    os.environ[_k] = ""  # tests never call external services
os.environ["EMBED_PROVIDER"] = "local"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from embeddings import LocalHashEmbedder  # noqa: E402
from seed_data import ENTITIES, PATTERNS, REPORTS  # noqa: E402


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / ((math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1)


class FakeRepo:
    def __init__(self, embedder):
        self.patterns, self.entities, self.reports, self.screenings = [], {}, [], []
        self.examples = {}
        for p in PATTERNS:
            v = embedder.embed([f'{p["title"]}. {p["description"]} Red flags: {p.get("red_flags", "")}'])[0]
            self.patterns.append({**p, "id": len(self.patterns) + 1, "vec": v})
        for t, v, status, notes in ENTITIES:
            self.upsert_entity(t, v, status, notes, count_report=False)
        for t, v, cat, amt, cur, text in REPORTS:
            eid = self.upsert_entity(t, v, "SUSPECT")
            self.add_report(eid, "seed", cat, amt, cur, text, embedder.embed([text])[0])

    def ping(self):
        return True

    def upsert_entity(self, etype, value, status="SUSPECT", notes="", count_report=True):
        key = (etype, value.lower())
        e = self.entities.get(key)
        inc = 1 if count_report else 0
        if e is None:
            e = {"id": len(self.entities) + 1, "entity_type": etype, "entity_value": value.lower(), "status": status,
                 "report_count": inc, "notes": notes}
            self.entities[key] = e
        else:
            e["report_count"] += inc
            if status == "BLOCKED":
                e["status"] = "BLOCKED"
            elif e["status"] != "TRUSTED" and e["report_count"] >= 3:
                e["status"] = "BLOCKED"
        return e["id"]

    def lookup_entities(self, entities):
        out = []
        for t, v in entities:
            e = self.entities.get((t, v.lower()))
            if e:
                loss = sum(r["amount"] for r in self.reports if r["entity_id"] == e["id"])
                out.append({**e, "reported_loss": loss, "last_report_at": None})
        return out

    def add_report(self, entity_id, reporter, category, amount, currency, narrative, vec):
        self.reports.append({"id": len(self.reports) + 1, "entity_id": entity_id, "category": category,
                             "amount": amount, "currency": currency, "narrative": narrative, "vec": vec})
        return len(self.reports)

    def search_patterns(self, vec, region="GLOBAL", k=5):
        rows = [p for p in self.patterns if p["region"] in ("GLOBAL", region.upper())]
        rows = sorted(({**{x: p[x] for x in p if x != "vec"}, "similarity": round(_cos(vec, p["vec"]), 4)} for p in rows),
                      key=lambda r: -r["similarity"])
        return rows[:k]

    def search_reports(self, vec, k=3):
        ents = {e["id"]: e for e in self.entities.values()}
        rows = []
        for r in self.reports:
            e = ents[r["entity_id"]]
            rows.append({**{x: r[x] for x in r if x != "vec"}, "entity_type": e["entity_type"],
                         "entity_value": e["entity_value"], "status": e["status"], "similarity": round(_cos(vec, r["vec"]), 4)})
        return sorted(rows, key=lambda r: -r["similarity"])[:k]

    def init_examples(self, dim):
        pass

    def get_meta(self, key):
        return getattr(self, "_meta", {}).get(key)

    def set_meta(self, key, value):
        if not hasattr(self, "_meta"):
            self._meta = {}
        self._meta[key] = value

    def example_ids(self):
        return set(self.examples)

    def insert_example(self, row_id, row, vec):
        self.examples.setdefault(row_id, {**row, "id": row_id, "vec": vec})

    def search_examples(self, vec, k=3):
        rows = [{**{key: value for key, value in row.items() if key != "vec"},
                 "similarity": round(_cos(vec, row["vec"]), 4)} for row in self.examples.values()]
        return sorted(rows, key=lambda row: -row["similarity"])[:k]

    def payee_velocity(self, payee_email, hours=24):
        rows = [s for s in self.screenings if s["payee_email"] == payee_email.lower()]
        return {"attempts": len(rows), "blocked": sum(1 for s in rows if s["verdict"] == "BLOCK"),
                "total_amount": sum(s["amount"] for s in rows)}

    def insert_screening(self, s):
        row = {**s, "id": len(self.screenings) + 1, "payee_email": (s.get("payee_email") or "").lower(),
               "paypal_order_id": None, "paypal_status": None, "reasons_json": json.dumps(s.get("reasons", []))}
        self.screenings.append(row)
        return row["id"]

    def update_screening_ai(self, sid, summary, score, verdict):
        self.screenings[sid - 1].update(ai_summary=summary, risk_score=score, verdict=verdict)

    def update_screening_paypal(self, sid, order_id, status):
        self.screenings[sid - 1].update(paypal_order_id=order_id, paypal_status=status)

    def get_screening(self, sid):
        if sid < 1 or sid > len(self.screenings):
            return None
        s = dict(self.screenings[sid - 1])
        s["reasons"] = json.loads(s.pop("reasons_json"))
        return s

    def recent_screenings(self, n=15):
        return self.screenings[-n:]

    def stats(self):
        return {"totals": {"screenings": len(self.screenings), "blocked": 0, "reviewed": 0, "allowed": 0,
                           "money_protected": 0}, "categories": [], "top_entities": [], "daily": [],
                "knowledge_base": {"patterns": len(self.patterns), "entities": len(self.entities), "reports": len(self.reports)}}

    def schema_description(self):
        return "PG_SCREENINGS(ID INTEGER, VERDICT VARCHAR, AMOUNT DECIMAL)"

    def run_readonly(self, sql):
        return {"columns": ["sql"], "rows": [[sql]]}


@pytest.fixture(scope="session")
def embedder():
    return LocalHashEmbedder(768)


@pytest.fixture()
def repo(embedder):
    return FakeRepo(embedder)
