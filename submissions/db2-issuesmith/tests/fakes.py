"""In-memory stand-ins so the agent graph can be unit-tested without a Db2 server.
The real implementation is issuesmith.db.Db2Repository (exercised by `cli.py demo`)."""
import math


class FakeRepo:
    def __init__(self):
        self.incidents, self.evidence, self.drafts, self.runs = {}, [], [], []
        self._next = 1001

    def create_incident(self, source_name, sanitized_log, redactions):
        iid = self._next
        self._next += 1
        self.incidents[iid] = {"INCIDENT_ID": iid, "LOG": sanitized_log, "STATUS": "NEW", "CATEGORY": None, "VEC": None}
        return iid

    def update_classification(self, iid, category, confidence, env, signature, embedding):
        self.incidents[iid].update(CATEGORY=category, VEC=embedding)

    def add_evidence(self, iid, evidence):
        self.evidence.extend((iid, e) for e in evidence)

    def find_similar(self, iid):
        me = self.incidents[iid]["VEC"]
        out = []
        for oid, inc in self.incidents.items():
            if oid == iid or inc["VEC"] is None:
                continue
            dot = sum(a * b for a, b in zip(me, inc["VEC"]))
            na = math.sqrt(sum(a * a for a in me)) or 1
            nb = math.sqrt(sum(b * b for b in inc["VEC"])) or 1
            out.append({"INCIDENT_ID": oid, "CATEGORY": inc["CATEGORY"], "STATUS": inc["STATUS"],
                        "CREATED_AT": None, "DISTANCE": 1 - dot / (na * nb), "VIA": "fake"})
        return sorted(out, key=lambda r: r["DISTANCE"])[:5]

    def set_status(self, iid, status, duplicate_of=None):
        self.incidents[iid]["STATUS"] = status

    def save_draft(self, iid, round_no, title, body, score, notes, generated_by, is_final):
        self.drafts.append({"iid": iid, "round": round_no, "title": title, "final": is_final, "score": score})
        return len(self.drafts)

    def log_agent_run(self, iid, agent, status, detail, latency_ms):
        self.runs.append((iid, agent, status))


class FakeKB:
    def search(self, query, k=3):
        return [{"title": "Readiness-message timeout", "category": "RESTART", "source": "kb.md",
                 "url": "", "text": "Readiness wait can time out while Db2 later becomes accessible.", "distance": 0.2}]


class ScriptedLLM:
    """Returns canned replies in order, to test the critic -> writer retry loop."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.name = "scripted"
        self.calls = []

    @property
    def available(self):
        return True

    def chat(self, system, user, temperature=0.1):
        self.calls.append(user)
        return self.replies.pop(0)
