"""Replay mode: recorded model outputs for the built-in scenarios, so AsOf runs with no model at all.

    LLM_PROVIDER=replay            # in .env: no API key, no Ollama
    python -m asof.replay record   # maintainers: re-record with the configured live model

Only the model is replaced. Retrieval (FOR BUSINESS_TIME AS OF with VECTOR_DISTANCE), the verbatim-quote
rule, the rule check on RULE_JSON, the coverage check, the decision, the re-check of a rewrite and the
hash-chained ledger all run live in Db2, as they do with a live model.

Each model call is looked up by a SHA-256 of everything the model would have been sent: the output schema
or the tools, and every message. A recording therefore answers only the exact input it was made for.
Anything else raises ReplayMiss, which is an LLMError, so the check fails closed and the answer is held
for a specialist. Recorded outputs are validated by the same Pydantic schemas as live ones, and every
decision made this way says "replay:" in the ledger's MODEL_INFO.

The built-in scenarios are the playground chips, change-impact presets, Ask-the-ledger examples and the
specialist inbox's suggested replies in ui/scenarios.json (the UI loads the same file), plus the decisions
`python -m asof.demo` records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, ValidationError

from .config import REPLAY_FILE, ConfigError
from .llm import LLMError, LLMResult, structured_call

T = TypeVar("T", bound=BaseModel)

log = logging.getLogger(__name__)

RECORDING_PATH = REPLAY_FILE
SCENARIOS_PATH = Path(__file__).with_name("ui") / "scenarios.json"
REPLAY_SCHEMA = "ASOF_REPLAY"  # where `record` runs the scenarios (a scratch copy of the seed data)
FORMAT = 2  # 2: keys cover the output schema and the tools' argument schemas, not just their names

MISS = ("replay mode has no recorded model output for this input (only the built-in scenarios are recorded). "
        "To check other answers, set OPENROUTER_API_KEY and LLM_PROVIDER=openrouter in .env, or "
        "LLM_PROVIDER=ollama with Ollama running, then restart.")


class ReplayMiss(LLMError):
    """No recording matches this exact model input, so the caller fails closed."""


# LangChain's view descriptions (Ask the ledger) end with two sample rows, which change as the ledger
# grows. They are left out of the key, so a recorded query replays on any ledger; the query then runs
# live, through the same SQLGlot check, as the read-only analyst.
_SAMPLE_ROWS = re.compile(r"/\*\n\d+ rows from [^\n]* table:\n.*?\*/", re.S)


def _text(content: Any) -> str:
    text = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
    return _SAMPLE_ROWS.sub("/* sample rows */", text)


def _messages(messages) -> list[list[Any]]:
    out: list[list[Any]] = []
    for m in messages:
        if isinstance(m, tuple):
            out.append([m[0], _text(m[1])])
            continue
        item: list[Any] = [m.type, _text(m.content)]
        calls = getattr(m, "tool_calls", None)
        if calls:
            item.append([[c.get("name"), c.get("args") or {}, c.get("id")] for c in calls])
        if getattr(m, "tool_call_id", None):
            item.append(m.tool_call_id)
        out.append(item)
    return out


def _key(kind: str, name: str, messages, extra: Any = None) -> str:
    payload = json.dumps([FORMAT, kind, name, _messages(messages), extra], sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _shape(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def structured_key(schema: type[BaseModel], messages, choices: dict[str, list[str]] | None = None) -> str:
    # The schema's shape is part of the key: if a schema changes, its old outputs stop replaying.
    return _key("structured", schema.__name__, messages,
                {"choices": {k: list(v) for k, v in sorted((choices or {}).items())},
                 "schema": _shape(schema.model_json_schema())})


def tools_key(messages, tools) -> str:
    shapes = sorted((t.name, _shape(getattr(t, "args", {}))) for t in tools)
    return _key("tools", ",".join(name for name, _ in shapes), messages, shapes)


def chat_key(messages) -> str:
    return _key("chat", "", messages)


class Recording:
    """Recorded model outputs, keyed by the SHA-256 of their input."""

    def __init__(self, model: str, recorded_on: str, entries: dict[str, dict] | None = None,
                 scenarios: dict[str, Any] | None = None):
        self.model, self.recorded_on = model, recorded_on
        self.entries: dict[str, dict] = entries if entries is not None else {}
        self.scenarios: dict[str, Any] = scenarios if scenarios is not None else {}

    @classmethod
    def load(cls, path: Path = RECORDING_PATH) -> Recording:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"LLM_PROVIDER=replay, but the recording {path.name} could not be read "
                              f"({type(exc).__name__})") from None
        if data.get("format") != FORMAT or not isinstance(data.get("entries"), dict):
            raise ConfigError(f"{path.name} is not a format-{FORMAT} AsOf recording")
        return cls(str(data["model"]), str(data["recorded_on"]), data["entries"], data.get("scenarios") or {})

    def save(self, path: Path = RECORDING_PATH) -> None:
        data = {"format": FORMAT, "model": self.model, "recorded_on": self.recorded_on,
                "note": "Model outputs recorded by `python -m asof.replay record`; read by LLM_PROVIDER=replay.",
                "scenarios": self.scenarios, "entries": self.entries}
        path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    def get(self, key: str, kind: str) -> Any:
        entry = self.entries.get(key)
        if entry is None or entry.get("kind") != kind:
            raise ReplayMiss(MISS)
        return entry["output"]

    def has(self, key: str) -> bool:
        return key in self.entries

    def put(self, key: str, kind: str, name: str, output: Any) -> None:
        self.entries[key] = {"kind": kind, "name": name, "output": output}


class _StoreChatModel(BaseChatModel):
    """A LangChain chat model over a Recording, for chains that call the model directly (the demo
    assistant). Replays; or, given `inner`, calls the live model and records what it said."""

    recording: Any
    inner: Any = None

    @property
    def _llm_type(self) -> str:
        return "asof-replay" if self.inner is None else "asof-record"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        key = chat_key(messages)
        if self.inner is None or self.recording.has(key):
            text = self.recording.get(key, "chat")
        else:
            text = self.inner.invoke(messages).content
            self.recording.put(key, "chat", "chat", text)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def _validated(schema: type[T], output: Any) -> T:
    try:
        return schema.model_validate(output)
    except ValidationError as exc:
        raise LLMError(f"the recorded {schema.__name__} does not fit the schema") from exc


class ReplayLLM:
    """Same interface as llm.LLMClient, answering from a Recording. It never calls a model."""

    provider = "replay"

    def __init__(self, recording: Recording):
        self.recording = recording
        self.model_name = recording.model
        self.chat_model = _StoreChatModel(recording=recording)

    @property
    def info(self) -> str:
        return f"replay:{self.recording.model} (recorded {self.recording.recorded_on})"

    def structured(self, schema: type[T], messages: list[tuple[str, str]], choices: dict[str, list[str]] | None = None,
                   max_chars: int | None = None) -> LLMResult[T]:
        value = _validated(schema, self.recording.get(structured_key(schema, messages, choices), "structured"))
        return LLMResult(value=value, latency_ms=0, input_tokens=None, output_tokens=None, attempts=1)

    def tool_round(self, messages: list, tools: list) -> AIMessage:
        out = self.recording.get(tools_key(messages, tools), "tools")
        return AIMessage(content=out["content"], tool_calls=[
            {"name": c["name"], "args": c["args"], "id": c["id"], "type": "tool_call"} for c in out["tool_calls"]])

    def run(self, fn):
        try:
            return fn()
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - same contract as LLMClient.run
            raise LLMError(f"{self.info} call failed: {type(exc).__name__}") from exc


class Recorder:
    """Wraps a live client and records every output. An input already recorded is answered from the
    recording, so one input always has one output and every recorded scenario replays as it ran."""

    def __init__(self, inner, recording: Recording):
        self.inner, self.recording = inner, recording
        self.provider, self.model_name = inner.provider, inner.model_name
        self.chat_model = _StoreChatModel(recording=recording, inner=inner.chat_model)
        self.live_calls = 0

    @property
    def info(self) -> str:
        return self.inner.info

    def begin_check(self) -> None:
        getattr(self.inner, "begin_check", lambda: None)()

    def structured(self, schema: type[T], messages: list[tuple[str, str]], choices: dict[str, list[str]] | None = None,
                   max_chars: int | None = None) -> LLMResult[T]:
        key = structured_key(schema, messages, choices)
        if self.recording.has(key):
            return ReplayLLM(self.recording).structured(schema, messages, choices)
        result = structured_call(self.inner, schema, messages, choices, max_chars)
        self.live_calls += 1
        self.recording.put(key, "structured", schema.__name__, result.value.model_dump(mode="json"))
        return result

    def tool_round(self, messages: list, tools: list) -> AIMessage:
        key = tools_key(messages, tools)
        if self.recording.has(key):
            return ReplayLLM(self.recording).tool_round(messages, tools)
        msg = self.inner.tool_round(messages, tools)
        self.live_calls += 1
        self.recording.put(key, "tools", "tools", {
            "content": msg.content,
            "tool_calls": [{"name": c["name"], "args": c.get("args") or {}, "id": c.get("id")} for c in msg.tool_calls or []]})
        return msg

    def run(self, fn):
        return self.inner.run(fn)


@lru_cache(maxsize=1)
def shipped_model() -> str | None:
    """The model the shipped recording was made with, for /healthz and the UI banner."""
    try:
        r = Recording.load()
    except ConfigError:
        return None
    return f"{r.model} on {r.recorded_on}"


def load_scenarios(path: Path = SCENARIOS_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_scenarios() -> list[dict[str, Any]]:
    """Every built-in check: the playground chips, then the demo's decisions not already among them."""
    from .demo import BANK_DRAFTS, HELD_DRAFTS, SCENARIOS
    from .domains import AIRLINE, BANK

    items = [{"label": s["label"], "doc_id": s["doc"], "question": s["question"], "as_of": s["as_of"],
              "draft": s.get("draft") if s["mode"] == "draft" else None} for s in load_scenarios()["playground"]]
    items += [{"label": f"demo: {q}", "doc_id": AIRLINE.doc_id, "question": q, "as_of": d.isoformat(), "draft": None}
              for q, d in SCENARIOS]
    items += [{"label": f"demo: {q}", "doc_id": BANK.doc_id, "question": q, "as_of": d.isoformat(), "draft": t}
              for q, t, d in BANK_DRAFTS]
    items += [{"label": f"chat {b['ref']}: {q}", "doc_id": AIRLINE.doc_id, "question": q, "as_of": b["booked"], "draft": None}
              for b in load_scenarios().get("chat", {}).get("bookings", []) for q in b["questions"]]
    items += [{"label": f"held: {q}", "doc_id": doc, "question": q, "as_of": d.isoformat(), "draft": t}
              for doc, q, t, d in HELD_DRAFTS]
    seen, unique = set(), []
    for it in items:
        k = (it["doc_id"], it["question"], it["as_of"], it["draft"])
        if k not in seen:
            seen.add(k)
            unique.append(it)
    return unique


def review_scenarios() -> list[dict[str, Any]]:
    """The specialist inbox's built-in replies (scenarios.json "reviews"), each with the held draft it answers."""
    from .demo import HELD_DRAFTS

    held = {q: (doc, t, d) for doc, q, t, d in HELD_DRAFTS}
    out = []
    for r in load_scenarios().get("reviews", []):
        doc, draft, on = held[r["question"]]
        out.append({"doc_id": doc, "question": r["question"], "draft": draft, "as_of": on.isoformat(),
                    "reply": r["reply"], "note": r.get("note")})
    return out


def run_reviews(gate, connect=None) -> list[dict[str, Any]]:
    """Hold each built-in draft, then send the built-in reply through the inbox (the reply's check is what records)."""
    from . import review
    from .gate import GateRequest

    out = []
    for sc in review_scenarios():
        held = gate.check(GateRequest(sc["question"], sc["draft"], date.fromisoformat(sc["as_of"]), sc["doc_id"], "chat"))
        rec = {"question": sc["question"], "held": held.reason_code, "outcome": None, "refused": None}
        try:
            rec["outcome"] = review.resolve(gate, held.ledger_id, sc["reply"], sc["note"], connect=connect).outcome
        except review.ReviewError as exc:
            rec["refused"] = str(exc)
        out.append(rec)
        print(f"  review {rec['outcome'] or 'REFUSED':<20} {sc['question']}", flush=True)
    return out


def next_version(timeline: list[dict[str, Any]], clause_id: str) -> str:
    """The version label the UI proposes for a change (one more than the highest)."""
    clause = next(c for c in timeline if c["clause_id"] == clause_id)
    return f"v{max(int(v['version'][1:]) for v in clause['versions']) + 1}"


def record(settings) -> int:
    """Run every built-in scenario against the live model in a scratch schema and save the outputs."""
    from . import db, impactagent, policy
    from .askledger import LedgerAsker
    from .assistant import DemoAssistant
    from .embeddings import get_embeddings
    from .gate import Gate, GateRequest
    from .llm import build_llm

    live = build_llm(settings, fallback=False)  # one provider, so the recording names one model
    if live.provider == "replay":
        print("Set a live LLM_PROVIDER (with its key) to record; replay cannot record itself.")
        return 2
    recording = Recording(live.info, date.today().isoformat())
    rec = Recorder(live, recording)
    emb = get_embeddings(settings.embedding_model)
    started = time.monotonic()
    print(f"Recording with {live.info} in schema {REPLAY_SCHEMA}", flush=True)
    _fresh_schema(settings, emb)
    time.sleep(1.1)  # the policy changes below must get a later system time than the seed rows

    app = db.ConnectionPool(settings, "app").connect
    gate, bot = Gate(rec, emb, app, REPLAY_SCHEMA), DemoAssistant(rec, emb, app, REPLAY_SCHEMA)
    checks, failed = [], 0
    for sc in check_scenarios():
        draft = sc["draft"] or bot.answer(sc["question"]).text
        r = gate.check(GateRequest(sc["question"], draft, date.fromisoformat(sc["as_of"]), sc["doc_id"], "demo"))
        failed += r.reason_code == "ERROR_FAIL_CLOSED"
        checks.append(sc | {"draft_checked": draft, "decision": r.decision, "reason_code": r.reason_code})
        print(f"  {r.decision:<9} {r.reason_code:<24} {sc['label']}", flush=True)

    reviews = run_reviews(gate, lambda: db.connect(settings, "review"))
    failed += sum(1 for r in reviews if r["refused"])

    asks = []
    asker = LedgerAsker(rec, settings, REPLAY_SCHEMA)
    for q in load_scenarios()["ask_examples"]:
        res = asker.ask(q)
        asks.append({"question": q, "status": res.status, "sql": res.sql})
        print(f"  ask {res.status:<9} {q}", flush=True)

    impacts = []
    for p in load_scenarios()["presets"]:
        with db.connection(settings, "app") as reader:  # the timeline view, read as the API reads it
            label = next_version(policy.timeline(reader, REPLAY_SCHEMA), p["clause"])
        with db.connection(settings, "editor") as ed:
            policy.apply_change(ed, policy.PolicyChange(
                clause_id=p["clause"], effective_from=p["from"], version_label=label, clause_text=p["text"],
                rule=p["rule"], change_note=p["note"]), emb, REPLAY_SCHEMA)
        drafted = impactagent.draft_fixes(gate, p["clause"])
        failed += sum(1 for d in drafted if d.get("error") or d.get("check_reason") == "ERROR_FAIL_CLOSED")
        impacts.append({"preset": p["label"], "clause_id": p["clause"], "version_label": label,
                        "drafts": [{"answer_id": d["answer_id"], "check_decision": d.get("check_decision"),
                                    "check_reason": d.get("check_reason"), "error": d.get("error")} for d in drafted]})
        print(f"  impact {p['label']}: {[(d['answer_id'], d.get('check_decision')) for d in drafted]}", flush=True)

    intake_summary = record_intake(settings, recording)
    print(f"  intake {intake_summary['document']}: {[(i['clause_id'], i['kind']) for i in intake_summary['items']]}",
          flush=True)

    if failed:
        print(f"{failed} scenario(s) failed closed on a live-model error; nothing saved. Run it again.")
        return 1
    recording.scenarios = {"checks": checks, "ask": asks, "impact": impacts, "intake": intake_summary, "reviews": reviews}
    recording.save()
    print(f"Saved {len(recording.entries)} outputs ({rec.live_calls} live calls) to {RECORDING_PATH.name} "
          f"in {time.monotonic() - started:.0f} s")
    return 0


def _fresh_schema(settings, emb) -> None:
    """REPLAY_SCHEMA rebuilt from the seed data, so recordings never depend on the dev database's state."""
    from . import db, schema, seed

    with db.connection(settings, "admin") as conn:
        schema.drop(conn, REPLAY_SCHEMA)
        schema.install(conn, REPLAY_SCHEMA)
        seed.seed_policy(conn, emb, REPLAY_SCHEMA)
        seed.seed_chain_head(conn, REPLAY_SCHEMA)
        seed.seed_published_answers(conn, REPLAY_SCHEMA)
        seed.seed_faq(conn, emb, REPLAY_SCHEMA)
        schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, REPLAY_SCHEMA,
                            analyst_user=settings.asof_analyst_user, review_user=settings.asof_review_user)


def record_intake(settings, recording: Recording) -> dict[str, Any]:
    """Record the extraction of the sample policy revision (the policy intake demo) into `recording`.

    The intake prompt lists the policy's clause IDs, titles and rule keys, not their current text, so the
    recording replays on any database whose clauses keep those (a policy change through APPLY_POLICY_CHANGE does).
    """
    from . import db, intake
    from .domains import AIRLINE
    from .llm import build_llm

    live = build_llm(settings, fallback=False, max_output_tokens=settings.asof_intake_max_output_tokens,
                     deadline_s=settings.asof_intake_timeout_s)
    rec = Recorder(live, recording)
    source = intake.read_pdf(intake.SAMPLE_PDF.read_bytes(), intake.SAMPLE_PDF.name)
    with db.connection(settings, "app") as reader:
        proposals, discarded, _ = intake.propose(rec, source, AIRLINE.doc_id, reader, REPLAY_SCHEMA)
    return {"document": source.name, "sha256": source.sha256, "live_calls": rec.live_calls,
            "items": [{"item_no": p.item_no, "kind": p.kind, "clause_id": p.clause_id, "blocked": p.blocked}
                      for p in proposals], "discarded": [d.title for d in discarded]}


def _run_checks(settings, recorder, items) -> list[dict[str, Any]]:
    from . import db
    from .assistant import DemoAssistant
    from .embeddings import get_embeddings
    from .gate import Gate, GateRequest

    emb = get_embeddings(settings.embedding_model)
    app = db.ConnectionPool(settings, "app").connect
    gate, bot = Gate(recorder, emb, app, REPLAY_SCHEMA), DemoAssistant(recorder, emb, app, REPLAY_SCHEMA)
    out = []
    for sc in items:
        draft = sc["draft"] or bot.answer(sc["question"]).text
        r = gate.check(GateRequest(sc["question"], draft, date.fromisoformat(sc["as_of"]), sc["doc_id"], "demo"))
        out.append(sc | {"draft_checked": draft, "decision": r.decision, "reason_code": r.reason_code})
        print(f"  {r.decision:<9} {r.reason_code:<24} {sc['label']}", flush=True)
    return out


def record_only_chat(settings) -> int:
    """Record the customer chat's questions that the shipped recording lacks, leaving every other output as it is."""
    from .embeddings import get_embeddings
    from .llm import build_llm

    recording = Recording.load()
    live = build_llm(settings, fallback=False)
    if live.info != recording.model:
        print(f"The shipped recording is from {recording.model}; set that model to add to it (now: {live.info}).")
        return 2
    have = {(c["doc_id"], c["question"], c["as_of"], c["draft"]) for c in recording.scenarios.get("checks", [])}
    todo = [c for c in check_scenarios() if c["label"].startswith("chat ")
            and (c["doc_id"], c["question"], c["as_of"], c["draft"]) not in have]
    if not todo:
        print("Every chat question is already recorded.")
        return 0
    _fresh_schema(settings, get_embeddings(settings.embedding_model))
    done = _run_checks(settings, Recorder(live, recording), todo)
    if any(c["reason_code"] == "ERROR_FAIL_CLOSED" for c in done):
        print("A check failed closed on a live-model error; nothing saved. Run it again.")
        return 1
    recording.scenarios.setdefault("checks", []).extend(done)
    recording.save()
    return 0


def record_only_ask(settings) -> int:
    """Re-record the Ask-the-ledger examples (after a change to the views they describe), leaving every other output as
    it is. The built-in checks replay first, from the recording, so the ledger the questions read is not empty."""
    from .askledger import LedgerAsker
    from .embeddings import get_embeddings
    from .llm import build_llm

    recording = Recording.load()
    live = build_llm(settings, fallback=False)
    if live.info != recording.model:
        print(f"The shipped recording is from {recording.model}; set that model to add to it (now: {live.info}).")
        return 2
    emb = get_embeddings(settings.embedding_model)
    _fresh_schema(settings, emb)
    recorder = Recorder(live, recording)
    _run_checks(settings, recorder, check_scenarios())
    if recorder.live_calls:
        print(f"{recorder.live_calls} check output(s) were not in the recording; nothing saved.")
        return 1
    asks = []
    asker = LedgerAsker(recorder, settings, REPLAY_SCHEMA)
    for q in load_scenarios()["ask_examples"]:
        res = asker.ask(q)
        asks.append({"question": q, "status": res.status, "sql": res.sql})
        print(f"  ask {res.status:<9} {q}", flush=True)
    if any(a["status"] != "ANSWERED" for a in asks):
        print("An example did not get a checked query; nothing saved. Run it again.")
        return 1
    recording.scenarios["ask"] = asks
    recording.save()
    print(f"Saved {recorder.live_calls} new outputs to {RECORDING_PATH.name}")
    return 0


def record_only_reviews(settings) -> int:
    """Add the held drafts and the inbox's replies to the shipped recording, leaving every other output as it is."""
    from . import db
    from .embeddings import get_embeddings
    from .gate import Gate
    from .llm import build_llm

    recording = Recording.load()
    live = build_llm(settings, fallback=False)
    if live.info != recording.model:
        print(f"The shipped recording is from {recording.model}; set that model to add to it (now: {live.info}).")
        return 2
    emb = get_embeddings(settings.embedding_model)
    _fresh_schema(settings, emb)
    recorder = Recorder(live, recording)
    have = {(c["doc_id"], c["question"], c["as_of"], c["draft"]) for c in recording.scenarios.get("checks", [])}
    todo = [c for c in check_scenarios() if c["label"].startswith("held: ")
            and (c["doc_id"], c["question"], c["as_of"], c["draft"]) not in have]
    done = _run_checks(settings, recorder, todo)
    reviews = run_reviews(Gate(recorder, emb, db.ConnectionPool(settings, "app").connect, REPLAY_SCHEMA),
                          lambda: db.connect(settings, "review"))
    if any(c["reason_code"] == "ERROR_FAIL_CLOSED" for c in done) or any(r["refused"] for r in reviews):
        print("A check failed closed or a reply was refused; nothing saved. Run it again.")
        return 1
    recording.scenarios.setdefault("checks", []).extend(done)
    recording.scenarios["reviews"] = reviews
    recording.save()
    return 0


def record_only_intake(settings) -> int:
    """Add the intake recording to the shipped one without re-recording (and so changing) any other scenario."""
    from .embeddings import get_embeddings
    from .llm import build_llm

    recording = Recording.load()
    live = build_llm(settings, fallback=False)
    if live.info != recording.model:
        print(f"The shipped recording is from {recording.model}; set that model to add to it (now: {live.info}).")
        return 2
    _fresh_schema(settings, get_embeddings(settings.embedding_model))
    summary = record_intake(settings, recording)
    recording.scenarios["intake"] = summary
    recording.save()
    print(f"Recorded the intake of {summary['document']}: {[(i['clause_id'], i['kind']) for i in summary['items']]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m asof.replay", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["record", "show"], help="record: re-record with the live model; "
                        "show: list what the shipped recording covers")
    parser.add_argument("--only", choices=["intake", "chat", "reviews", "ask"],
                        help="record only these scenarios and add them to the "
                        "shipped recording, leaving every other recorded output as it is")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    from . import db
    from .config import get_settings

    if args.command == "show":
        r = Recording.load()
        print(f"{len(r.entries)} recorded outputs from {r.model}, recorded {r.recorded_on}")
        for c in r.scenarios.get("checks", []):
            print(f"  {c['decision']:<9} {c['as_of']}  {c['label']}")
        return 0
    try:
        if args.only == "intake":
            return record_only_intake(get_settings())
        if args.only == "chat":
            return record_only_chat(get_settings())
        if args.only == "reviews":
            return record_only_reviews(get_settings())
        if args.only == "ask":
            return record_only_ask(get_settings())
        return record(get_settings())
    except (ConfigError, LLMError, db.DatabaseError) as exc:
        print(f"Recording failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
