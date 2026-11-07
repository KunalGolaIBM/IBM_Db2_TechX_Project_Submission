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

The built-in scenarios are the playground chips, change-impact presets and Ask-the-ledger examples in
ui/scenarios.json (the UI loads the same file), plus the decisions `python -m asof.demo` records.
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
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import ValidationError

from .config import REPLAY_FILE, ConfigError
from .llm import LLMError, LLMResult

log = logging.getLogger(__name__)

RECORDING_PATH = REPLAY_FILE
SCENARIOS_PATH = Path(__file__).with_name("ui") / "scenarios.json"
REPLAY_SCHEMA = "ASOF_REPLAY"  # where `record` runs the scenarios (a scratch copy of the seed data)
FORMAT = 1

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


def structured_key(schema: type, messages, choices: dict[str, list[str]] | None = None) -> str:
    return _key("structured", schema.__name__, messages, {k: list(v) for k, v in sorted((choices or {}).items())})


def tools_key(messages, tools) -> str:
    return _key("tools", ",".join(sorted(t.name for t in tools)), messages)


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


def _validated(schema: type, output: Any):
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

    def structured(self, schema: type, messages, choices: dict[str, list[str]] | None = None) -> LLMResult:
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

    def structured(self, schema: type, messages, choices: dict[str, list[str]] | None = None) -> LLMResult:
        key = structured_key(schema, messages, choices)
        if self.recording.has(key):
            return ReplayLLM(self.recording).structured(schema, messages, choices)
        result = self.inner.structured(schema, messages, choices)
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
    from .demo import BANK_DRAFTS, SCENARIOS
    from .domains import AIRLINE, BANK

    items = [{"label": s["label"], "doc_id": s["doc"], "question": s["question"], "as_of": s["as_of"],
              "draft": s.get("draft") if s["mode"] == "draft" else None} for s in load_scenarios()["playground"]]
    items += [{"label": f"demo: {q}", "doc_id": AIRLINE.doc_id, "question": q, "as_of": d.isoformat(), "draft": None}
              for q, d in SCENARIOS]
    items += [{"label": f"demo: {q}", "doc_id": BANK.doc_id, "question": q, "as_of": d.isoformat(), "draft": t}
              for q, t, d in BANK_DRAFTS]
    seen, unique = set(), []
    for it in items:
        k = (it["doc_id"], it["question"], it["as_of"], it["draft"])
        if k not in seen:
            seen.add(k)
            unique.append(it)
    return unique


def next_version(timeline: list[dict[str, Any]], clause_id: str) -> str:
    """The version label the UI proposes for a change (one more than the highest)."""
    clause = next(c for c in timeline if c["clause_id"] == clause_id)
    return f"v{max(int(v['version'][1:]) for v in clause['versions']) + 1}"


def record(settings) -> int:
    """Run every built-in scenario against the live model in a scratch schema and save the outputs."""
    from . import db, impactagent, policy, schema, seed
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
    with db.connection(settings, "admin") as conn:
        schema.drop(conn, REPLAY_SCHEMA)
        schema.install(conn, REPLAY_SCHEMA)
        seed.seed_policy(conn, emb, REPLAY_SCHEMA)
        seed.seed_chain_head(conn, REPLAY_SCHEMA)
        seed.seed_published_answers(conn, REPLAY_SCHEMA)
        seed.seed_faq(conn, emb, REPLAY_SCHEMA)
        schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, REPLAY_SCHEMA,
                            analyst_user=settings.asof_analyst_user)
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

    if failed:
        print(f"{failed} scenario(s) failed closed on a live-model error; nothing saved. Run it again.")
        return 1
    recording.scenarios = {"checks": checks, "ask": asks, "impact": impacts}
    recording.save()
    print(f"Saved {len(recording.entries)} outputs ({rec.live_calls} live calls) to {RECORDING_PATH.name} "
          f"in {time.monotonic() - started:.0f} s")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m asof.replay", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["record", "show"], help="record: re-record with the live model; "
                        "show: list what the shipped recording covers")
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
        return record(get_settings())
    except (ConfigError, LLMError, db.DatabaseError) as exc:
        print(f"Recording failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
