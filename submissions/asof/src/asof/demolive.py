"""Live checks on the public demo: what a visitor types gets a real model, inside limits that Db2 and the app enforce.

    ASOF_PUBLIC_DEMO=true  LLM_PROVIDER=replay  ASOF_DEMO_LIVE=true   # and OPENROUTER_API_KEY in the environment

Routing, per request to POST /api/gate or POST /api/assistant/ask:
- an input the shipped recording holds exactly (a built-in scenario, asof/replay.py) replays: instant and free;
- anything else is a live check, if one can start;
- if it cannot, the request is refused with the reason (HTTP 429 or 503) and nothing is checked, recorded or sent.

A live check meets these in order, and the first that says no refuses it:
1. input limits (LiveGateIn, LiveAskIn: Pydantic, before anything runs);
2. a pause: the provider failed PAUSE_AFTER live checks in a row (for PAUSE_S), or today's cap is known to be spent;
3. the visitor's limits, per minute (sliding) and per UTC day, keyed on the address the API derives from the proxy's
   X-Forwarded-For entry (an IPv6 address by its /64, so rotating addresses inside one network does not help);
4. at most LIVE_SLOTS live checks at once;
5. Db2's daily cap for the whole demo: ASOF.CLAIM_DEMO_CHECK admits the check atomically or SIGNALs 75097.
Only then does the check run, against its own budget (LIVE_CHECK_DEADLINE_S), with no local fallback model. A check
that fails after it started is held by the gate, as every failed check is (decision ESCALATED, reason
ERROR_FAIL_CLOSED, the holding reply), so the draft is never released unchecked. Afterwards ASOF.RECORD_DEMO_SPEND adds
the check's model calls and the tokens the provider reported to the day's row.
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, TypeVar

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .llm import LLMError, LLMResult

T = TypeVar("T", bound=BaseModel)

log = logging.getLogger(__name__)

CAP_REACHED = "75097"  # CLAIM_DEMO_CHECK: the day's cap is spent
LIVE_QUESTION_MAX = 500  # characters; the chat page's input allows 500 too
LIVE_DRAFT_MAX = 1500
LIVE_SLOTS = 3
LIVE_CHECK_DEADLINE_S = 120.0
PAUSE_AFTER = 3  # failed live checks in a row
PAUSE_S = 300.0
STATUS_CACHE_S = 5.0  # /healthz reads the day's row at most this often
MAX_VISITORS = 50_000  # entries kept by the per-minute window before old ones are swept

SQL_TODAY = ("SELECT SPEND_DAY, CHECKS_USED, LLM_CALLS, INPUT_TOKENS, OUTPUT_TOKENS FROM DEMO_SPEND "
             "WHERE SPEND_DAY = DATE(CURRENT TIMESTAMP - CURRENT TIMEZONE)")

STILL_REPLAY = "The built-in scenarios still replay recorded model outputs, with Db2 live."


def utc_today() -> date:
    return datetime.now(UTC).date()


class _Live(BaseModel):
    model_config = ConfigDict(extra="ignore")


class LiveGateIn(_Live):
    """What a live check of a draft may hold: tighter than the API's own limits, so one request stays cheap."""
    question: str = Field(max_length=LIVE_QUESTION_MAX)
    draft_answer: str = Field(max_length=LIVE_DRAFT_MAX)


class LiveAskIn(_Live):
    question: str = Field(max_length=LIVE_QUESTION_MAX)


class LiveRefused(Exception):
    """A live check that did not start. Nothing was checked, recorded or sent; `message` says why, for the visitor."""

    def __init__(self, status: int, reason: str, message: str, retry_after_s: float | None = None):
        super().__init__(message)
        self.status, self.reason, self.message = status, reason, message
        self.retry_after_s = None if retry_after_s is None else max(1, int(retry_after_s + 0.999))


class RecordedInputs:
    """The check inputs the shipped recording answers exactly: (doc_id, question, as_of, draft) for a draft sent to
    /api/gate (a built-in draft, or the demo assistant's recorded one), and (doc_id, question, as_of) for the demo
    assistant. Compared exactly, as the replay keys are: one changed character makes it a new input."""

    def __init__(self, checks: Iterable[dict[str, Any]]):
        self._gate: set[tuple[str, str, str, str]] = set()
        self._ask: set[tuple[str, str, str]] = set()
        for c in checks:
            self._gate.add((c["doc_id"], c["question"], c["as_of"], c["draft_checked"]))
            if c.get("draft") is None:
                self._ask.add((c["doc_id"], c["question"], c["as_of"]))

    @classmethod
    def shipped(cls) -> RecordedInputs:
        from .replay import Recording

        return cls(Recording.load().scenarios.get("checks", []))

    def gate(self, doc_id: str, question: str, draft: str, as_of: date) -> bool:
        return (doc_id, question, as_of.isoformat(), draft) in self._gate

    def ask(self, doc_id: str, question: str, as_of: date) -> bool:
        return (doc_id, question, as_of.isoformat()) in self._ask

    def __len__(self) -> int:
        return len(self._gate)


class Meter:
    """One live check's model client: passes each call to the live client and counts calls, the tokens the provider
    reported, and failed calls (for the pause). One per check, so concurrent checks never share counts."""

    def __init__(self, inner: Any):
        self.inner = inner
        self.calls = self.input_tokens = self.output_tokens = self.failures = 0

    @property
    def provider(self) -> str:
        return str(self.inner.provider)

    @property
    def model_name(self) -> str:
        return str(self.inner.model_name)

    @property
    def info(self) -> str:
        return str(self.inner.info)

    def begin_check(self) -> None:
        getattr(self.inner, "begin_check", lambda: None)()

    def _usage(self, usage: Any) -> None:
        usage = usage or {}
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)

    def structured(self, schema: type[T], messages: list[tuple[str, str]], choices: dict[str, list[str]] | None = None,
                   max_chars: int | None = None) -> LLMResult[T]:
        self.calls += 1
        try:
            result: LLMResult[T] = (self.inner.structured(schema, messages, choices) if max_chars is None else
                                    self.inner.structured(schema, messages, choices, max_chars=max_chars))
        except LLMError:
            self.failures += 1
            raise
        self.input_tokens += result.input_tokens or 0
        self.output_tokens += result.output_tokens or 0
        return result

    def tool_round(self, messages: list[Any], tools: list[Any]) -> AIMessage:
        self.calls += 1
        try:
            msg: AIMessage = self.inner.tool_round(messages, tools)
        except LLMError:
            self.failures += 1
            raise
        self._usage(getattr(msg, "usage_metadata", None))
        return msg

    @property
    def chat_model(self) -> Any:
        """The live chat model for the demo assistant's chain, counting its calls and tokens."""
        inner = self.inner.chat_model

        def call(prompt: Any) -> Any:
            self.calls += 1
            msg = inner.invoke(prompt)
            self._usage(getattr(msg, "usage_metadata", None))
            return msg

        return RunnableLambda(call)

    def run(self, fn: Callable[[], Any]) -> Any:
        try:
            return self.inner.run(fn)
        except LLMError:
            self.failures += 1
            raise


class SpendCounter:
    """The day's row in ASOF.DEMO_SPEND, through the two procedures (the runtime user holds no write on the table)."""

    def __init__(self, connect: Callable[[], Any], schema: str = db.SCHEMA):
        self.connect, self.schema = connect, schema

    def claim(self, cap: int) -> tuple[date, int]:
        """Admit one live check: (the UTC day Db2 counted it on, checks used that day). DatabaseError with SQLSTATE
        75097 when the cap is spent."""
        conn = self.connect()
        try:
            db.use_schema(conn, self.schema)
            cur = conn.cursor()
            try:
                out = cur.callproc("CLAIM_DEMO_CHECK", (int(cap), date(1970, 1, 1), 0))
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                raise db.wrap_error(exc, "CLAIM_DEMO_CHECK refused") from None
            finally:
                cur.close()
        finally:
            conn.close()
        return out[1], int(out[2])

    def record(self, day: date, calls: int, input_tokens: int, output_tokens: int) -> None:
        conn = self.connect()
        try:
            db.use_schema(conn, self.schema)
            cur = conn.cursor()
            try:
                cur.callproc("RECORD_DEMO_SPEND", (day, int(calls), int(input_tokens), int(output_tokens)))
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                raise db.wrap_error(exc, "RECORD_DEMO_SPEND refused") from None
            finally:
                cur.close()
        finally:
            conn.close()

    def today(self) -> dict[str, Any] | None:
        conn = self.connect()
        try:
            db.use_schema(conn, self.schema)
            rows = db.query(conn, SQL_TODAY)
        finally:
            conn.close()
        if not rows:
            return None
        day, used, calls, tin, tout = rows[0]
        return {"day": day, "checks": int(used), "llm_calls": int(calls), "input_tokens": int(tin),
                "output_tokens": int(tout)}


def visitor_key(address: str) -> str:
    """The key a visitor's limits are counted under: an IPv4 address as it is, an IPv6 address by its /64."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address[:64] or "unknown"
    if ip.version == 6 and not getattr(ip, "ipv4_mapped", None):
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    mapped = getattr(ip, "ipv4_mapped", None)
    return str(mapped or ip)


class VisitorLimits:
    """Live checks per visitor: a sliding minute and a UTC day. A slot is reserved under one lock, and given back when
    a later layer refuses the check, so a visitor's count is only what was admitted."""

    def __init__(self, per_minute: int, per_day: int, clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = utc_today):
        self.per_minute, self.per_day = per_minute, per_day
        self.clock, self.today = clock, today
        self.minute: dict[str, deque[float]] = {}
        self.day: dict[str, int] = {}
        self.day_of: date | None = None
        self.lock = threading.Lock()

    def _roll(self, now: float) -> None:
        today = self.today()
        if today != self.day_of:
            self.day.clear()
            self.day_of = today
        if len(self.minute) > MAX_VISITORS:
            for k in [k for k, q in self.minute.items() if not q or now - q[-1] > 60.0]:
                del self.minute[k]

    def reserve(self, key: str) -> str | None:
        """None if a slot was reserved, else which limit refused it ("visitor_minute" or "visitor_day")."""
        with self.lock:
            now = self.clock()
            self._roll(now)
            q = self.minute.setdefault(key, deque())
            while q and now - q[0] > 60.0:
                q.popleft()
            if self.day.get(key, 0) >= self.per_day:
                return "visitor_day"
            if len(q) >= self.per_minute:
                return "visitor_minute"
            q.append(now)
            self.day[key] = self.day.get(key, 0) + 1
            return None

    def give_back(self, key: str) -> None:
        with self.lock:
            q = self.minute.get(key)
            if q:
                q.pop()
            if self.day.get(key):
                self.day[key] -= 1

    def used_today(self, key: str) -> int:
        with self.lock:
            return self.day.get(key, 0) if self.day_of == self.today() else 0


class Pause:
    """Live checks stop for PAUSE_S after PAUSE_AFTER checks in a row saw the provider fail."""

    def __init__(self, after: int = PAUSE_AFTER, seconds: float = PAUSE_S, clock: Callable[[], float] = time.monotonic):
        self.after, self.seconds, self.clock = after, seconds, clock
        self.failed_in_a_row = 0
        self.until = 0.0
        self.lock = threading.Lock()

    def note(self, failed: bool) -> None:
        with self.lock:
            if not failed:
                self.failed_in_a_row = 0
                return
            self.failed_in_a_row += 1
            if self.failed_in_a_row >= self.after:
                self.until = self.clock() + self.seconds
                self.failed_in_a_row = 0
                log.error("live checks paused for %.0f s: the provider failed %d live checks in a row", self.seconds,
                          self.after)

    def remaining_s(self) -> float:
        with self.lock:
            return max(0.0, self.until - self.clock())


@dataclass
class Session:
    """One admitted live check: the UTC day Db2 counted it on, its metered client, and the gate and demo assistant
    built on that client (set by LiveChecks.check)."""
    day: date
    used: int
    key: str
    meter: Meter | None = None
    gate: Any = None
    assistant: Any = None


class LiveChecks:
    """The public demo's live checks: routing, the five layers above, and the banner text."""

    def __init__(self, *, model: str, cap: int, per_minute: int, per_day: int, available: bool,
                 client: Callable[[], Any], spend: Any, gate: Callable[[Meter], Any], assistant: Callable[[Meter], Any],
                 recorded: RecordedInputs | None = None, clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = utc_today):
        self.model, self.cap, self.per_minute, self.per_day, self.available = model, cap, per_minute, per_day, available
        self._client_factory, self._client, self._client_lock = client, None, threading.Lock()
        self.spend, self._make_gate, self._make_assistant = spend, gate, assistant
        self.recorded = recorded if recorded is not None else RecordedInputs.shipped()
        self.visitors = VisitorLimits(per_minute, per_day, clock, today)
        self.pause = Pause(clock=clock)
        self.slots = threading.BoundedSemaphore(LIVE_SLOTS)
        self.clock, self.today = clock, today
        self.spent_on: date | None = None  # the day Db2 said its cap was spent
        self._status: tuple[float, dict[str, Any] | None] | None = None

    @classmethod
    def from_settings(cls, settings: Any, connect: Callable[[], Any], schema: str, gate: Callable[[Meter], Any],
                      assistant: Callable[[Meter], Any], **kwargs: Any) -> LiveChecks:
        from .config import _is_set
        from .llm import build_llm

        return cls(model=f"openrouter:{settings.openrouter_model}", cap=settings.asof_demo_live_daily_cap,
                   per_minute=settings.asof_demo_live_per_minute, per_day=settings.asof_demo_live_per_day,
                   available=_is_set(settings.openrouter_api_key),
                   client=lambda: build_llm(settings, provider="openrouter", fallback=False),
                   spend=SpendCounter(connect, schema), gate=gate, assistant=assistant, **kwargs)

    # ---- routing -----------------------------------------------------------------------------
    def recorded_gate(self, doc_id: str, question: str, draft: str, as_of: date) -> bool:
        return self.recorded.gate(doc_id, question, draft, as_of)

    def recorded_ask(self, doc_id: str, question: str, as_of: date) -> bool:
        return self.recorded.ask(doc_id, question, as_of)

    # ---- why a live check would not start ------------------------------------------------------
    def _blocked(self, key: str | None = None) -> tuple[str, float | None] | None:
        """(reason, seconds until it may change) for the layers that need no reservation, else None."""
        if not self.available:
            return "unavailable", None
        left = self.pause.remaining_s()
        if left > 0:
            return "provider", left
        if self.spent_on == self.today():
            return "cap", _to_midnight()
        if key is not None and self.visitors.used_today(key) >= self.per_day:
            return "visitor_day", _to_midnight()
        return None

    def _why(self, reason: str, retry_after_s: float | None) -> str:
        """Plain words for the banner and the refusal: what is paused and why."""
        if reason == "unavailable":
            return "live checks are not available on this server right now, so only the built-in scenarios work."
        if reason == "spend_counter":
            return "live checks are paused: the demo could not reach its spend counter in Db2, so no live check starts."
        if reason == "provider":
            minutes = max(1, round((retry_after_s or 0) / 60))
            return (f"live checks are paused for about {minutes} minute{'s' if minutes > 1 else ''}: the model provider "
                    f"failed {PAUSE_AFTER} live checks in a row.")
        if reason == "cap":
            return (f"live checks are paused: today's limit of {self.cap} live checks for the whole demo is used up. "
                    "They resume at 00:00 UTC.")
        if reason == "visitor_day":
            return f"you have used your {self.per_day} live checks for today. They reset at 00:00 UTC."
        if reason == "visitor_minute":
            return f"live checks are limited to {self.per_minute} a minute per visitor. Try again in a minute."
        return f"{LIVE_SLOTS} live checks are already running. Try again in a few seconds."  # busy

    def _refused(self, reason: str, retry_after_s: float | None) -> LiveRefused:
        status = 429 if reason.startswith("visitor_") else 503
        why = self._why(reason, retry_after_s)
        return LiveRefused(status, reason, f"{why[0].upper()}{why[1:]} Nothing was checked or sent. {STILL_REPLAY}",
                           retry_after_s)

    # ---- admission ---------------------------------------------------------------------------
    def client(self) -> Any:
        with self._client_lock:
            if self._client is None:
                self._client = self._client_factory()
            return self._client

    def admit(self, address: str) -> Session:
        """Reserve everything one live check needs, or raise LiveRefused. Db2 is asked last."""
        blocked = self._blocked()
        if blocked:
            raise self._refused(*blocked)
        key = visitor_key(address)
        which = self.visitors.reserve(key)
        if which is not None:
            raise self._refused(which, _to_midnight() if which == "visitor_day" else 60.0)
        if not self.slots.acquire(blocking=False):
            self.visitors.give_back(key)
            raise self._refused("busy", 10.0)
        try:
            day, used = self.spend.claim(self.cap)
        except db.DatabaseError as exc:
            self.slots.release()
            self.visitors.give_back(key)
            self._status = None
            if exc.sqlstate == CAP_REACHED:
                self.spent_on = self.today()
                raise self._refused("cap", _to_midnight()) from None
            log.error("live check refused: the spend counter in Db2 failed: %s", exc)
            raise self._refused("spend_counter", 30.0) from None
        except BaseException:
            self.slots.release()
            self.visitors.give_back(key)
            raise
        if used >= self.cap:
            self.spent_on = self.today()  # this was the day's last one
        self._status = None
        return Session(day, used, key)

    def finish(self, session: Session) -> None:
        """Give the slot back, note whether the provider failed, and add the check's usage to the day's row."""
        self.slots.release()
        m = session.meter
        if m is None:
            return
        if m.calls or m.failures:
            self.pause.note(failed=m.failures > 0)
        try:
            self.spend.record(session.day, m.calls, m.input_tokens, m.output_tokens)
        except Exception as exc:  # noqa: BLE001 - the check is done; its usage stays uncounted, loudly
            log.error("live check usage not recorded (%d calls, %d+%d tokens): %s", m.calls, m.input_tokens,
                      m.output_tokens, exc)
        log.info("live check %d/%d on %s: %d model calls, %d input and %d output tokens", session.used, self.cap,
                 session.day, m.calls, m.input_tokens, m.output_tokens)

    @contextmanager
    def check(self, address: str) -> Iterator[Session]:
        """with live.check(address) as s: s.gate.check(...): admitted (or LiveRefused raised), then accounted for."""
        session = self.admit(address)
        try:
            session.meter = Meter(self.client())
            session.gate = self._make_gate(session.meter)
            session.assistant = self._make_assistant(session.meter)
            yield session
        finally:
            self.finish(session)

    # ---- the banner -------------------------------------------------------------------------------
    def _today_row(self) -> dict[str, Any] | None:
        now = self.clock()
        if self._status is not None and now - self._status[0] < STATUS_CACHE_S:
            return self._status[1]
        row: dict[str, Any] | None
        try:
            row = self.spend.today()
        except Exception as exc:  # noqa: BLE001 - the banner falls back to what the app knows
            log.warning("could not read today's live-check count: %s", exc)
            row = None
        self._status = (now, row)
        return row

    def status(self, address: str) -> dict[str, Any]:
        """For /healthz: whether live checks run now ("on", "paused" or "unavailable"), why not, and the banner."""
        blocked = self._blocked(visitor_key(address))
        row = None if blocked else self._today_row()
        if blocked is None and row is not None and row["checks"] >= self.cap:
            blocked = ("cap", None)
        if blocked is not None:
            reason = blocked[0]
            return {"state": "unavailable" if reason == "unavailable" else "paused", "reason": reason,
                    "notice": f"Public demo: {self._why(*blocked)} {STILL_REPLAY}"}
        used = row["checks"] if row else 0
        return {"state": "on", "reason": None,
                "notice": f"Public demo: the built-in scenarios replay recorded model outputs, and anything else is "
                          f"checked live by {self.model.split(':', 1)[1]}, with Db2 live throughout. Live checks today: "
                          f"{used} of {self.cap} for the whole demo, {self.per_day} per visitor. Nothing here changes "
                          f"policy or sends anything."}


def _to_midnight() -> float:
    """Seconds until 00:00 UTC, when the daily limits reset."""
    now = datetime.now(UTC)
    return float(86400 - (now.hour * 3600 + now.minute * 60 + now.second))
