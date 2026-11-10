"""The LangGraph nodes: Detective, Historian, Diff Engine, Verifier, Reporter.

LLM use is deliberately narrow and always validated:
  Detective  - reads the question, ranks hypotheses, revises them from evidence
  Historian  - proposes a structured query plan (never SQL text)
  Reporter   - writes the plain-language summary from verified facts
The Diff Engine and the Verifier's checks are deterministic code.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Optional, TypedDict

from . import diff_engine as de
from .config import Settings
from .llm import LLM, LLMError
from .models import PATTERN_TITLES, PATTERNS, fmt_ts, money, parse_ts
from .scope import (default_hypotheses, detect_direction, find_product, heuristic_time_spec,
                    resolve_window, valid_hypotheses)

AGENTS = ["detective", "historian", "diff", "verifier", "reporter"]


class State(TypedDict, total=False):
    run_id: str
    question: str
    since: Optional[str]
    until: Optional[str]
    hours: Optional[float]
    now: Any
    scope: dict
    hypotheses: list
    tested: list
    current: str
    iteration: int
    rows: list
    delete_rows: list
    events: list
    groups: list
    metric_start: Any
    metric_end: Any
    all_scores: dict
    recon: dict
    rerun: dict
    verdict: str
    evidence_sql: list
    report: dict


@dataclass
class Context:
    repo: Any
    llm: LLM
    settings: Settings
    emit: Callable[[dict], None] = lambda event: None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    _seq: int = 0

    def audit(self, agent: str, action: str, *, sql: str = None, rows: int = None, ms: float = None,
              outcome: str = "ok", detail: Any = None) -> None:
        self._seq += 1
        entry = {"run_id": self.run_id, "seq": self._seq, "agent": agent, "action": action, "sql": sql,
                 "rows": rows, "ms": round(ms, 1) if ms is not None else None, "outcome": outcome,
                 "detail": detail if isinstance(detail, str) or detail is None else json.dumps(detail, default=str)}
        try:
            self.repo.write_audit(entry)
        except Exception as exc:  # auditing must never break an investigation
            entry["outcome"] = f"audit-write-failed: {str(exc)[:80]}"
        self.emit({"type": "audit", **{k: entry[k] for k in ("seq", "agent", "action", "rows", "ms", "outcome")}})

    def timed(self, fn, *args):
        t0 = time.perf_counter()
        result = fn(*args)
        return result, (time.perf_counter() - t0) * 1000


def _ctx(config) -> Context:
    return config["configurable"]["ctx"]


def _start(ctx: Context, agent: str, message: str) -> None:
    ctx.emit({"type": "agent", "agent": agent, "status": "running", "message": message})


def _done(ctx: Context, agent: str, summary: str, **extra) -> None:
    ctx.emit({"type": "agent", "agent": agent, "status": "done", "message": summary, **extra})


def _llm_call(ctx: Context, agent: str, action: str, system: str, user: str, max_tokens: int = 700) -> Optional[dict]:
    """Ask the LLM for JSON. Returns None on any failure (the caller then uses its heuristic)."""
    if not ctx.llm.enabled:
        return None
    try:
        result = ctx.llm.json(system, user, max_tokens)
        ctx.audit(agent, f"llm:{action}", ms=ctx.llm.last_latency_ms, detail=f"model={ctx.llm.label}")
        return result
    except LLMError as exc:
        ctx.audit(agent, f"llm:{action}", ms=ctx.llm.last_latency_ms, outcome="fallback", detail=str(exc)[:200])
        return None


# --------------------------------------------------------------------------------------
# Detective
# --------------------------------------------------------------------------------------
DETECTIVE_SYSTEM = (
    "You are the Detective in a data-incident investigation over an orders database. "
    "Given a business question, identify the product (by exact name from the list, or null), whether the metric "
    "went up/down/unknown, the time window, and rank these hypotheses by likelihood: "
    f"{', '.join(PATTERNS)}. Time window kinds: since_snapshot, last_hours (with 'hours'), today, yesterday."
)


def detective(state: State, config) -> dict:
    ctx = _ctx(config)
    if state.get("scope") is None:
        return _detective_first_pass(state, ctx)
    return _detective_revise(state, ctx)


def _detective_first_pass(state: State, ctx: Context) -> dict:
    _start(ctx, "detective", "Reading the question and scoping the investigation")
    question = state["question"]
    now = state.get("now") or ctx.repo.now()
    products, ms = ctx.timed(ctx.repo.products)
    ctx.audit("detective", "read product catalogue", rows=len(products), ms=ms)

    product = find_product(question, products)
    direction = detect_direction(question)
    spec = heuristic_time_spec(question)
    hypotheses = default_hypotheses(direction)
    reasoning = "Heuristic parse of the question."

    answer = _llm_call(ctx, "detective", "scope the question", DETECTIVE_SYSTEM, json.dumps({
        "question": question, "products": [p["name"] for p in products], "now": fmt_ts(now),
        "reply_schema": {"product": "name or null", "direction": "up|down|unknown",
                         "time": {"kind": "...", "hours": "number, optional"}, "hypotheses": ["..."],
                         "reasoning": "one sentence"}}))
    if answer:
        by_name = {p["name"].lower(): p for p in products}
        named = by_name.get(str(answer.get("product") or "").lower())
        product = named or product
        if answer.get("direction") in ("up", "down", "unknown"):
            direction = answer["direction"]
        t = answer.get("time")
        if isinstance(t, dict) and t.get("kind") in ("since_snapshot", "last_hours", "today", "yesterday"):
            spec = t
        ranked = valid_hypotheses(answer.get("hypotheses"))
        if ranked:  # keep any hypothesis the model forgot, at the end
            hypotheses = ranked + [h for h in default_hypotheses(direction) if h not in ranked]
        reasoning = str(answer.get("reasoning") or "LLM-assisted scoping.")[:300]

    pid = product["product_id"] if product else None
    snap = ctx.repo.last_snapshot(pid)
    since = parse_ts(state["since"]) if state.get("since") else None
    until = parse_ts(state["until"]) if state.get("until") else None
    if state.get("hours"):
        spec = {"kind": "last_hours", "hours": float(state["hours"])}
    start, end, label = resolve_window(spec, now, snap["ts"] if snap else None, since, until)
    scope = {"product_id": pid, "product_name": product["name"] if product else None, "direction": direction,
             "start": start, "end": end, "window_label": label, "reasoning": reasoning}
    ctx.audit("detective", "scope", detail={"product": scope["product_name"], "direction": direction,
                                             "window": label, "hypotheses": hypotheses})
    first = hypotheses[0]
    _done(ctx, "detective",
          f"Investigating {scope['product_name'] or 'all products'} ({direction}), {label}. "
          f"First hypothesis: {PATTERN_TITLES[first].lower()}.",
          scope={**scope, "start": fmt_ts(start), "end": fmt_ts(end)}, hypotheses=hypotheses)
    return {"now": now, "scope": scope, "hypotheses": hypotheses, "current": first, "tested": [], "iteration": 0,
            "evidence_sql": []}


def _detective_revise(state: State, ctx: Context) -> dict:
    _start(ctx, "detective", "Revising the hypothesis from the evidence so far")
    tested = {t["pattern"] for t in state["tested"]}
    remaining = [h for h in state["hypotheses"] if h not in tested]
    scores = state.get("all_scores", {})
    # evidence-driven order: the pattern that moved the metric most goes first
    remaining.sort(key=lambda h: -abs(Decimal(scores.get(h, {}).get("explained", "0"))))
    reasoning = "Reordered by how much each remaining pattern moved the metric in the history."
    answer = _llm_call(ctx, "detective", "revise hypotheses", DETECTIVE_SYSTEM, json.dumps({
        "tested_and_rejected": [{"pattern": t["pattern"], "reason": t["reason"]} for t in state["tested"]],
        "remaining": remaining,
        "evidence": {h: scores.get(h, {}).get("explained") for h in remaining},
        "reply_schema": {"hypotheses": "the remaining hypotheses, most likely first", "reasoning": "one sentence"}}))
    if answer:
        ranked = [h for h in valid_hypotheses(answer.get("hypotheses")) if h in remaining]
        if ranked:
            remaining = ranked + [h for h in remaining if h not in ranked]
            reasoning = str(answer.get("reasoning") or reasoning)[:300]
    nxt = remaining[0]
    ctx.audit("detective", "revise", detail={"next": nxt, "rejected": sorted(tested)})
    _done(ctx, "detective", f"Next hypothesis: {PATTERN_TITLES[nxt].lower()}. {reasoning}", hypotheses=remaining)
    return {"current": nxt, "iteration": state.get("iteration", 0) + 1,
            "hypotheses": [t["pattern"] for t in state["tested"]] + remaining}


# --------------------------------------------------------------------------------------
# Historian
# --------------------------------------------------------------------------------------
HISTORIAN_SYSTEM = (
    "You are the Historian. Propose a query plan to fetch the row history needed to test a hypothesis about "
    "an orders table. Do NOT write SQL. Allowed plan fields: include_delete_log (boolean)."
)


def historian(state: State, config) -> dict:
    ctx = _ctx(config)
    sc = state["scope"]
    if state.get("rows") is not None:  # history already fetched: reuse it for the new hypothesis
        _start(ctx, "historian", "Re-using the row history already fetched")
        ctx.audit("historian", "reuse cached history", rows=len(state["rows"]),
                  detail=f"hypothesis={state['current']}")
        _done(ctx, "historian", f"Re-used {len(state['rows'])} row versions already in memory (no new Db2 query).")
        return {}
    _start(ctx, "historian", "Reading the table's history with FOR SYSTEM_TIME")
    plan = _llm_call(ctx, "historian", "plan queries", HISTORIAN_SYSTEM, json.dumps({
        "hypothesis": state["current"], "table": ctx.repo.table.name, "window": [fmt_ts(sc["start"]), fmt_ts(sc["end"])],
        "reply_schema": {"include_delete_log": True}})) or {}
    include_deletes = bool(plan.get("include_delete_log", True))

    (rows, sql), ms = ctx.timed(ctx.repo.versions, sc["product_id"], sc["start"], sc["end"])
    ctx.audit("historian", "FOR SYSTEM_TIME FROM .. TO .. (row versions)", sql=sql, rows=len(rows), ms=ms)
    evidence = [{"label": "Row versions in the window (temporal query)", "sql": sql}]
    delete_rows: list = []
    if include_deletes:
        (delete_rows, dsql), ms = ctx.timed(ctx.repo.delete_log, sc["start"], sc["end"])
        ctx.audit("historian", "delete log (who deleted rows)", sql=dsql, rows=len(delete_rows), ms=ms)
        evidence.append({"label": "Who deleted rows (AFTER DELETE trigger log)", "sql": dsql})
    _done(ctx, "historian", f"Fetched {len(rows)} row versions from the temporal table's history.")
    return {"rows": rows, "delete_rows": delete_rows, "evidence_sql": state.get("evidence_sql", []) + evidence}


# --------------------------------------------------------------------------------------
# Diff Engine (deterministic)
# --------------------------------------------------------------------------------------
def diff(state: State, config) -> dict:
    ctx = _ctx(config)
    _start(ctx, "diff", "Comparing row versions and grouping changes by transaction")
    if state.get("events") is not None:
        _done(ctx, "diff", f"{len(state['events'])} change events already computed.")
        return {}
    sc = state["scope"]
    t0 = time.perf_counter()
    versions = de.versions_from_rows(state["rows"])
    events = de.build_events(versions, sc["start"], sc["end"], state.get("delete_rows"))
    groups = de.group_events(events)
    ctx.audit("diff", "build change events", rows=len(events), ms=(time.perf_counter() - t0) * 1000,
              detail={"groups": len(groups)})
    top = groups[0] if groups else None
    msg = (f"{len(events)} change events in {len(groups)} transaction groups." +
           (f" Largest: {top.n_rows} rows, {PATTERN_TITLES.get(top.pattern, top.pattern).lower()}, "
            f"impact {top.impact:+}." if top else ""))
    _done(ctx, "diff", msg, groups=[g.to_dict() for g in groups[:6]])
    return {"events": events, "groups": groups}


# --------------------------------------------------------------------------------------
# Verifier
# --------------------------------------------------------------------------------------
def verifier(state: State, config) -> dict:
    ctx = _ctx(config)
    sc = state["scope"]
    _start(ctx, "verifier", f"Testing hypothesis: {PATTERN_TITLES[state['current']].lower()}")
    update: dict = {}
    evidence = list(state.get("evidence_sql", []))

    if state.get("metric_start") is None:
        m0, ms0 = ctx.timed(ctx.repo.metric_as_of, sc["product_id"], sc["start"])
        m1, ms1 = ctx.timed(ctx.repo.metric_as_of, sc["product_id"], sc["end"])
        ctx.audit("verifier", "FOR SYSTEM_TIME AS OF start", sql=m0.sql, rows=m0.row_count, ms=ms0)
        ctx.audit("verifier", "FOR SYSTEM_TIME AS OF end", sql=m1.sql, rows=m1.row_count, ms=ms1)
        evidence = [{"label": "Revenue at the start of the window (AS OF)", "sql": m0.sql},
                    {"label": "Revenue at the end of the window (AS OF)", "sql": m1.sql}] + evidence
        update.update(metric_start=m0, metric_end=m1, evidence_sql=evidence)
    m0, m1 = update.get("metric_start", state.get("metric_start")), update.get("metric_end", state.get("metric_end"))

    events = state["events"]
    scores = {p: de.score_hypothesis(p, events, m0.revenue, m1.revenue, ctx.settings.confirm_share) for p in PATTERNS}
    recon = de.reconcile(events, m0.revenue, m1.revenue)
    current = scores[state["current"]]
    ctx.audit("verifier", f"score hypothesis {state['current']}", detail={
        "share": round(current["share"], 3), "confirmed": current["confirmed"], "reconciled": recon["ok"]})

    tested = list(state.get("tested", []))
    tested.append({"pattern": state["current"], "title": current["title"], "share": current["share"],
                   "explained": current["explained"], "confirmed": current["confirmed"], "reason": current["reason"]})
    ctx.emit({"type": "hypothesis", **tested[-1]})
    update.update(all_scores=scores, recon=recon, tested=tested)

    observed = money(m1.revenue) - money(m0.revenue)
    if current["confirmed"]:
        # Re-run both AS OF queries: results at fixed timestamps must be identical (history is immutable).
        r0, ms0 = ctx.timed(ctx.repo.metric_as_of, sc["product_id"], sc["start"])
        r1, ms1 = ctx.timed(ctx.repo.metric_as_of, sc["product_id"], sc["end"])
        stable = (r0.revenue == m0.revenue) and (r1.revenue == m1.revenue)
        ctx.audit("verifier", "re-run AS OF queries (stability check)", rows=2, ms=ms0 + ms1,
                  outcome="ok" if stable else "MISMATCH", detail={"stable": stable})
        update["rerun"] = {"stable": stable}
        update["verdict"] = "confirmed"
        _done(ctx, "verifier", f"Confirmed. {current['reason']}" + ("" if stable else " (re-run mismatch!)"),
              result="confirmed", pattern=state["current"], share=current["share"])
        return update

    remaining = [h for h in state["hypotheses"] if h not in {t["pattern"] for t in tested}]
    if observed == 0 and not events:
        update["verdict"] = "no_change"
        _done(ctx, "verifier", "The metric did not change in this window.", result="no_change")
    elif remaining and state.get("iteration", 0) + 1 < ctx.settings.max_iterations:
        update["verdict"] = "retry"
        _done(ctx, "verifier", f"Rejected. {current['reason']} Sending the graph back to the Detective.",
              result="rejected", pattern=state["current"], share=current["share"])
    else:
        update["verdict"] = "exhausted"
        _done(ctx, "verifier", f"Rejected. {current['reason']} No hypotheses left.", result="rejected",
              pattern=state["current"], share=current["share"])
    return update


def route_after_verifier(state: State) -> str:
    return "detective" if state.get("verdict") == "retry" else "reporter"


# --------------------------------------------------------------------------------------
# Reporter
# --------------------------------------------------------------------------------------
REPORTER_SYSTEM = (
    "You are the Reporter. Write a 3-4 sentence plain-language incident summary for a business reader using ONLY "
    "the facts in the JSON. Do not invent numbers, names or causes. Mention what changed, when, who/what made the "
    "change, how many rows, and the revenue effect."
)


def reporter(state: State, config) -> dict:
    ctx = _ctx(config)
    _start(ctx, "reporter", "Writing the incident report")
    sc, events, groups = state["scope"], state["events"], state["groups"]
    m0, m1 = state["metric_start"], state["metric_end"]
    observed = money(m1.revenue) - money(m0.revenue)
    pct = float(observed / m0.revenue * 100) if m0.revenue else None
    verdict = state["verdict"]
    tested = state["tested"]

    confirmed = next((t for t in tested if t["confirmed"]), None)
    pattern = confirmed["pattern"] if confirmed else None
    if not pattern and tested:  # inconclusive: best partial explanation in the right direction
        same = [t for t in tested if t["share"] > 0]
        pattern = max(same, key=lambda t: t["share"])["pattern"] if same else None

    root = None
    if pattern:
        pgroups = [g for g in groups if g.pattern == pattern]
        pevents = [e for e in events if e.pattern == pattern]
        main = pgroups[0] if pgroups else None
        actors = sorted({a for g in pgroups for a in g.actors})
        root = {
            "pattern": pattern, "title": PATTERN_TITLES[pattern],
            "when": fmt_ts(main.first_at) if main else None, "transaction": main.txn if main else None,
            "actor": ", ".join(actors) if actors else None, "rows_affected": len(pevents),
            "impact": str(sum((e.impact for e in pevents), Decimal("0"))),
            "groups": [g.to_dict() for g in pgroups[:5]],
        }
    status = "confirmed" if verdict == "confirmed" else ("no_change" if verdict == "no_change" else "inconclusive")
    recon_ok = state["recon"]["ok"]
    stable = state.get("rerun", {}).get("stable", False)
    confidence = "high" if status == "confirmed" and recon_ok and stable else (
        "medium" if status == "confirmed" else "low")

    affected = []
    if pattern:
        for e in [e for e in events if e.pattern == pattern][:25]:
            affected.append({"item_id": e.item_id, "at": fmt_ts(e.at), "kind": e.kind, "actor": e.actor,
                             "before": e.before, "after": e.after, "impact": str(e.impact)})

    timeline = []
    snap = ctx.repo.last_snapshot(sc["product_id"])
    if snap and sc["start"] == snap["ts"]:
        timeline.append({"at": fmt_ts(snap["ts"]), "label": "KPI snapshot taken (last known-good value)",
                         "detail": f"revenue {snap['revenue']}", "kind": "snapshot"})
    for g in sorted(groups, key=lambda g: g.first_at):
        title = PATTERN_TITLES.get(g.pattern, g.pattern)
        who = f" by {', '.join(g.actors)}" if g.actors else ""
        timeline.append({"at": fmt_ts(g.first_at), "label": f"{title}: {g.n_rows} row(s){who}",
                         "detail": f"revenue impact {g.impact:+}; transaction {g.txn}",
                         "kind": "root" if g.pattern == pattern and status == "confirmed" else "change"})
    timeline.append({"at": fmt_ts(sc["end"]), "label": "Investigation point (now)", "detail":
                     f"revenue {money(m1.revenue)}", "kind": "now"})

    warnings = []
    if m0.row_count == 0:
        warnings.append("The table had no rows for this scope at the start of the window, so the comparison "
                        "baseline is empty. Try a window that starts after the data was loaded.")
    if not recon_ok:
        warnings.append(f"The sum of detected changes differs from the measured change by {state['recon']['difference']}; "
                        "some versions may be missing (for example rows moved between products).")
    if not state.get("rerun", {}).get("stable", True):
        warnings.append("Re-running the AS OF queries returned different values: the history may have been altered.")

    facts = {"product": sc["product_name"], "window": sc["window_label"], "revenue_before": str(m0.revenue),
             "revenue_after": str(m1.revenue), "change": str(observed), "status": status, "root_cause": root}
    narrative = _template_narrative(facts)
    llm_text = _llm_summary(ctx, facts)
    if llm_text:
        narrative = llm_text

    report = {
        "run_id": ctx.run_id, "question": state["question"], "generated_at": fmt_ts(ctx.repo.now()),
        "product_name": sc["product_name"], "product_id": sc["product_id"], "window": {"start": fmt_ts(sc["start"]), "end": fmt_ts(sc["end"]),
                                                       "label": sc["window_label"]},
        "metric": {"name": "Revenue (quantity x unit price)", "start": str(m0.revenue), "end": str(m1.revenue),
                   "delta": str(observed), "pct": round(pct, 1) if pct is not None else None},
        "verdict": {"status": status, "pattern": pattern if status == "confirmed" else None,
                    "confidence": confidence, "share": next((t["share"] for t in tested if t["pattern"] == pattern), None),
                    "best_guess": pattern if status != "confirmed" else None},
        "root_cause": root, "affected_rows": affected, "timeline": timeline,
        "hypotheses_tested": tested, "reconciliation": state["recon"],
        "evidence_sql": state.get("evidence_sql", []), "narrative": narrative, "warnings": warnings,
        "llm": ctx.llm.label, "iterations": state.get("iteration", 0) + 1,
    }
    try:
        ctx.repo.save_report(report)
        ctx.audit("reporter", "save incident report", detail=f"status={status}")
    except Exception as exc:
        ctx.audit("reporter", "save incident report", outcome="failed", detail=str(exc)[:200])
    _done(ctx, "reporter", narrative)
    ctx.emit({"type": "report", "report": report})
    return {"report": report}


def _llm_summary(ctx: Context, facts: dict) -> Optional[str]:
    if not ctx.llm.enabled:
        return None
    try:
        text = ctx.llm.complete(REPORTER_SYSTEM, json.dumps(facts, default=str), 400).strip()
        ctx.audit("reporter", "llm:write summary", ms=ctx.llm.last_latency_ms, detail=f"model={ctx.llm.label}")
        return text[:1200] or None
    except LLMError as exc:
        ctx.audit("reporter", "llm:write summary", ms=ctx.llm.last_latency_ms, outcome="fallback",
                  detail=str(exc)[:200])
        return None


def _template_narrative(f: dict) -> str:
    name = f["product"] or "Revenue"
    w = f["window"]
    when_ = w if w.startswith(("since", "yesterday", "today")) else f"in the {w}" if w.startswith("last") else w
    head = (f"{name} revenue moved from {f['revenue_before']} to {f['revenue_after']} "
            f"({f['change']}) {when_}. ")
    r = f["root_cause"]
    if f["status"] == "no_change":
        return head + "No change was detected, so there is nothing to explain."
    if not r:
        return head + "No hypothesis could be confirmed from the recorded history."
    who = f" by {r['actor']}" if r["actor"] else ""
    when = f" at {r['when'][:19]}" if r["when"] else ""
    body = (f"Cause: {r['title'].lower()}{who}{when}, touching {r['rows_affected']} row(s) with a revenue effect of "
            f"{r['impact']}.")
    return head + (body if f["status"] == "confirmed" else "Best partial explanation (not confirmed): " + body)
