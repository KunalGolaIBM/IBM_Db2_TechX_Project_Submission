"""POST /api/analyze workflow.

question -> policy screens -> planner (LLM or labelled demo rules) -> Pydantic QueryPlan
-> registry validation -> registry hash check against Db2 -> deterministic compiler -> SQL guard
-> parameterization check -> read-only execution (MGREADER) -> reconciliation / completeness /
null checks -> status precedence -> deterministic answer + chart -> audit record.

Status precedence: BLOCKED > AMBIGUOUS > EXECUTION_FAILED > EXECUTED_WITH_WARNINGS > VERIFIED.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

from pydantic import ValidationError

from metricguard import API_CONTRACT_VERSION
from metricguard.config import Settings
from metricguard.core.compiler import CompiledQuery, CompileError, compile_plan
from metricguard.core.plan import DateRange, FilterClause, MetricRef, OrderBy, QueryPlan
from metricguard.core.registry import DATA_COVERAGE_END, DATA_COVERAGE_START, DIMENSIONS, METRICS
from metricguard.core.sql_guard import check_sql
from metricguard.core.validator import validate_plan
from metricguard.db import Db2Client, Db2Error
from metricguard.planner import DEMO_DISCLOSURE, Planner, PlannerOutput, PlannerOutputError, PlannerResult
from metricguard.planner.policy import screen_question

from . import present

CHECKS: list[tuple[str, str]] = [
    ("V01", "plan_schema"), ("V02", "metric_approval"), ("V03", "registry_integrity"),
    ("V04", "dimension_filter_policy"), ("V05", "deterministic_sql"), ("V06", "sql_guard"),
    ("V07", "parameterized"), ("V08", "execution"), ("V09", "reconciliation"), ("V10", "completeness"),
    ("V11", "null_semantics"),
]
_V02_CODES = {"UNKNOWN_METRIC", "METRIC_NOT_APPROVED", "METRIC_VERSION_MISMATCH", "DUPLICATE_METRIC"}
_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}
_COMPONENTS = {  # non-additive metric -> (numerator, denominator) additive components
    "average_order_value": ("gross_revenue", "order_count"),
    "refund_rate": ("refund_amount", "gross_revenue"),
}
_RECON_MAX_GROUPS = 1000
ReaderFactory = Callable[[], Db2Client]


class Checks:
    def __init__(self) -> None:
        self._state = {cid: ("SKIPPED", "Not reached.") for cid, _ in CHECKS}

    def set(self, cid: str, status: str, detail: str) -> None:
        self._state[cid] = (status, detail)

    def status(self, cid: str) -> str:
        return self._state[cid][0]

    def skip_rest(self, after: str, detail: str) -> None:
        reached = False
        for cid, _ in CHECKS:
            if reached and self._state[cid][1] == "Not reached.":
                self._state[cid] = ("SKIPPED", detail)
            reached = reached or cid == after

    def as_list(self) -> list[dict[str, str]]:
        return [{"id": cid, "name": name, "status": self._state[cid][0], "detail": self._state[cid][1]}
                for cid, name in CHECKS]


@dataclass
class Outcome:
    """Everything needed to render the API response and the audit record."""

    request_id: str
    created_at: datetime
    question: str
    planner: dict[str, Any]
    status: str = "PENDING"  # always set to one of the five contract statuses before rendering
    plan: QueryPlan | None = None
    assumptions: list[dict[str, str]] = field(default_factory=list)
    reasons: list[dict[str, str]] = field(default_factory=list)
    checks: Checks = field(default_factory=Checks)
    compiled: CompiledQuery | None = None
    sql_hash: str | None = None
    result: dict[str, Any] | None = None
    raw_rows: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, Any] | None = None
    clarification: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    registry_rows: dict[str, str] = field(default_factory=dict)
    timing: dict[str, float | None] = field(default_factory=lambda: {
        "total_ms": 0.0, "planning_ms": 0.0, "validation_ms": 0.0, "execution_ms": None, "verification_ms": None})

    def reason(self, code: str, severity: str, message: str) -> None:
        if not any(r["code"] == code and r["message"] == message for r in self.reasons):
            self.reasons.append({"code": code, "severity": severity, "message": message})


# --------------------------------------------------------------------------------------
# Plan construction
# --------------------------------------------------------------------------------------
def _snake(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_") or "unnamed"


def build_plan(out: PlannerOutput) -> tuple[QueryPlan, list[dict[str, str]]]:
    """PlannerOutput -> QueryPlan. Versions are pinned from the registry, never from the model."""
    assumptions: list[dict[str, str]] = []
    if out.start_date is None and out.end_date is None:
        date_range = DateRange.default()
        assumptions.append({"code": "DEFAULT_DATE_RANGE", "message": (
            f"No period given; using data coverage {DATA_COVERAGE_START.isoformat()}.."
            f"{DATA_COVERAGE_END.isoformat()}.")})
    else:
        start = out.start_date or DATA_COVERAGE_START
        end = out.end_date or DATA_COVERAGE_END
        date_range = DateRange(start_date=start, end_date=end, source="explicit")
    metrics = [_snake(m) if m not in METRICS else m for m in out.metrics]
    plan = QueryPlan(
        metrics=[MetricRef(name=n, version=METRICS[n].version if n in METRICS else "unregistered") for n in metrics],
        dimensions=[d if d in DIMENSIONS else _snake(d) for d in out.dimensions],
        filters=[FilterClause(field=f.field, values=f.values) for f in out.filters],
        date_range=date_range,
        order_by=[OrderBy(field=o.field, direction=o.direction) for o in out.order_by],
        limit=out.limit,
    )
    return plan, assumptions


def _clarification(question: str, metric_terms: list[tuple[str, list[str]]], time_phrase: str | None
                   ) -> dict[str, Any] | None:
    latest_q = "Q2 2026"

    def rewrite(metric_display: str | None, term: str | None, period: str | None) -> str:
        q = question.strip()
        if metric_display and term:
            q = re.sub(rf"\b{re.escape(term)}\b", metric_display.lower(), q, count=1, flags=re.IGNORECASE)
        if time_phrase:
            q = re.sub(rf"\b(?:in\s+|during\s+|for\s+|over\s+)?(?:the\s+)?{re.escape(time_phrase)}\b",
                       f"in {period or latest_q}", q, count=1, flags=re.IGNORECASE)
        elif period:
            q = q.rstrip("?. ") + f" in {period}?"
        return q

    for term, candidates in metric_terms:
        known = [c for c in candidates if c in METRICS]
        if len(known) >= 2:
            return {
                "prompt": f"Which {term.lower()} do you mean?",
                "options": [{
                    "id": c, "label": METRICS[c].display_name, "description": METRICS[c].description,
                    "suggested_question": rewrite(METRICS[c].display_name, term, latest_q if time_phrase else None),
                } for c in known],
            }
    if time_phrase:
        return {
            "prompt": f"Which period do you mean by \"{time_phrase}\"?",
            "options": [
                {"id": "q2_2026", "label": "Q2 2026", "description": "Latest full quarter in the data (Apr–Jun 2026).",
                 "suggested_question": rewrite(None, None, "Q2 2026")},
                {"id": "h1_2026", "label": "H1 2026", "description": "All available data (Jan–Jun 2026).",
                 "suggested_question": rewrite(None, None, "H1 2026")},
            ],
        }
    return None


# --------------------------------------------------------------------------------------
# Verification helpers
# --------------------------------------------------------------------------------------
_LITERAL_RE = re.compile(r"'((?:[^']|'')*)'")


def parameterization_issues(compiled: CompiledQuery, plan: QueryPlan) -> list[str]:
    body = re.sub(r"--[^\n]*", "", compiled.sql)
    markers = len(re.findall(r"\?", _LITERAL_RE.sub("''", body)))
    issues = []
    if markers != len(compiled.parameters):
        issues.append(f"{markers} markers but {len(compiled.parameters)} parameters")
    literals = {m.group(1) for m in _LITERAL_RE.finditer(body)}
    values = {v for f in plan.filters for v in f.values}
    values |= {plan.date_range.start_date.isoformat(), plan.date_range.end_date.isoformat()}
    leaked = sorted(v for v in values if v in literals or (len(v) >= 6 and v in body))
    if leaked:
        issues.append(f"plan values appear in SQL text: {leaked}")
    return issues


def _q(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _recompute(metric: str, row: dict[str, Any]) -> Decimal | None:
    num_name, den_name = _COMPONENTS[metric]
    num, den = row.get(num_name), row.get(den_name)
    if num is None or den is None or Decimal(str(den)) == 0:
        return None
    return _q(Decimal(str(num)) / Decimal(str(den)), METRICS[metric].scale)


def _aux_plan(plan: QueryPlan, metrics: list[str], dimensions: list[str]) -> QueryPlan:
    # model_construct: auxiliary control queries may carry >4 metrics; values come from the validated plan.
    return QueryPlan.model_construct(
        metrics=[MetricRef(name=m, version=METRICS[m].version) for m in metrics], dimensions=dimensions,
        filters=plan.filters, date_range=plan.date_range, order_by=[], limit=None)


def _rows(compiled: CompiledQuery, res) -> list[dict[str, Any]]:
    return [{c.name: row[i] for i, c in enumerate(compiled.columns)} for row in res.rows]


def _key(row: dict[str, Any], dims: list[str]) -> tuple:
    return tuple(row[d] for d in dims)


# --------------------------------------------------------------------------------------
class AnalysisService:
    def __init__(self, settings: Settings, planner: Planner, *, reader_factory: ReaderFactory | None = None):
        self.settings = settings
        self.planner = planner
        self.reader_factory = reader_factory or (lambda: Db2Client(settings, role="reader"))

    # ---- public -----------------------------------------------------------------------
    def analyze(self, question: str, *, max_rows: int = 100) -> Outcome:
        started = time.perf_counter()
        planner_info = {"name": self.planner.name, "model": self.planner.model,
                        "execution_mode": self.planner.execution_mode, "provider": self.planner.provider,
                        "disclosure": DEMO_DISCLOSURE if self.planner.execution_mode == "DEMO_RULE_BASED" else None}
        o = Outcome(request_id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), question=question,
                    planner=planner_info)
        try:
            self._run(o, question, max_rows)
        finally:
            o.timing["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return o

    # ---- stages -----------------------------------------------------------------------
    def _run(self, o: Outcome, question: str, max_rows: int) -> None:
        screens = screen_question(question)
        t0 = time.perf_counter()
        try:
            result: PlannerResult = self.planner.plan(question)  # PlannerUnavailableError propagates (503)
        except PlannerOutputError as exc:
            o.timing["planning_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            o.checks.set("V01", "FAIL", str(exc))
            o.reason("PLAN_SCHEMA_INVALID", "error", f"{exc} Nothing was executed.")
            for s in screens:
                if s.code in ("WRITE_INTENT", "OUT_OF_SCOPE"):
                    o.reason(s.code, "error", s.message)
            o.checks.skip_rest("V01", "No valid plan.")
            o.status = "BLOCKED"
            return
        o.timing["planning_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        out = result.output
        v0 = time.perf_counter()

        # 1. Write intent / out of scope: never planned, never executed.
        blockers = [s for s in screens if s.code in ("WRITE_INTENT", "OUT_OF_SCOPE")]
        if out.intent == "write_request" and not any(s.code == "WRITE_INTENT" for s in blockers):
            o.reason("WRITE_INTENT", "error", "The planner classified this as a request to change data. "
                     "MetricGuard only runs read-only, governed queries.")
        if out.intent == "out_of_scope" and not blockers:
            o.reason("OUT_OF_SCOPE", "error", "The question does not map to an approved metric. "
                     "See GET /api/metrics for what can be answered.")
        for s in blockers:
            o.reason(s.code, "error", s.message)
        if o.reasons:
            o.checks.set("V01", "SKIPPED", "Not planned: request is outside the governed read-only scope.")
            o.checks.skip_rest("V01", "Not executed.")
            o.status = "BLOCKED"
            o.timing["validation_ms"] = round((time.perf_counter() - v0) * 1000, 1)
            return

        # 2. Ambiguity signals (from the deterministic screens and the planner).
        metric_terms: list[tuple[str, list[str]]] = []
        time_phrase: str | None = None
        for s in screens:
            if s.code == "AMBIGUOUS_METRIC":
                metric_terms.append((s.term or "revenue", ["net_revenue", "gross_revenue"]))
                o.reason("AMBIGUOUS_METRIC", "warning", s.message)
            elif s.code == "AMBIGUOUS_TIME_RANGE":
                time_phrase = s.term
                o.reason("AMBIGUOUS_TIME_RANGE", "warning", s.message)
        if out.ambiguous_metric and out.ambiguous_metric.candidate_metrics:
            am = out.ambiguous_metric
            if not any(t.lower() == am.term.lower() for t, _ in metric_terms):
                metric_terms.append((am.term, am.candidate_metrics))
                o.reason("AMBIGUOUS_METRIC", "warning", f"\"{am.term}\" could mean "
                         f"{' or '.join(c for c in am.candidate_metrics)}.")
        if out.relative_time_phrase and time_phrase is None:
            time_phrase = out.relative_time_phrase
            o.reason("AMBIGUOUS_TIME_RANGE", "warning", f"\"{time_phrase}\" is relative and has no anchor date; "
                     "data covers 2026-01-01..2026-06-30.")
        ambiguous = bool(metric_terms or time_phrase or out.intent == "ambiguous")

        # 3. Plan schema (V01). A plan is still built when ambiguous so policy blocks take precedence.
        plan: QueryPlan | None = None
        assumptions: list[dict[str, str]] = []
        if out.metrics:
            try:
                plan, assumptions = build_plan(out)
            except ValidationError as exc:
                first = exc.errors()[0]
                where = ".".join(str(p) for p in first.get("loc", ()))
                o.checks.set("V01", "FAIL", f"{where}: {first.get('msg')}")
                o.reason("PLAN_SCHEMA_INVALID", "error", f"The planner output is not a valid plan ({where}: "
                         f"{first.get('msg')}). Nothing was executed.")
                o.checks.skip_rest("V01", "No valid plan.")
                o.status = "BLOCKED"
                return
        elif not ambiguous:
            o.checks.set("V01", "FAIL", "No metric in plan.")
            o.reason("OUT_OF_SCOPE", "error", "The question does not name an approved metric. "
                     "See GET /api/metrics for what can be answered.")
            o.checks.skip_rest("V01", "No valid plan.")
            o.status = "BLOCKED"
            return

        if plan is not None:
            o.checks.set("V01", "PASS", "Plan parsed.")
            issues = validate_plan(plan)
            v02 = [i for i in issues if i.code in _V02_CODES]
            v04 = [i for i in issues if i.code not in _V02_CODES]
            refs = ", ".join(f"{m.name}@{m.version}" for m in plan.metrics)
            o.checks.set("V02", "FAIL" if v02 else "PASS",
                         "; ".join(i.message for i in v02) if v02 else f"{refs} approved.")
            o.checks.set("V04", "FAIL" if v04 else "PASS",
                         "; ".join(i.message for i in v04) if v04 else "Dimensions, filters and sort allowed.")
            if issues:
                o.plan = plan
                o.assumptions = assumptions
                o.reasons = [r for r in o.reasons if r["severity"] == "error"]
                for i in issues:
                    o.reason(i.code, "error", i.message)
                o.checks.skip_rest("V04", "Blocked by policy; not executed.")
                o.status = "BLOCKED"
                o.timing["validation_ms"] = round((time.perf_counter() - v0) * 1000, 1)
                return

        if ambiguous:
            clar = _clarification(o.question, metric_terms, time_phrase)
            if clar is None:
                o.reasons = []
                o.checks.set("V01", "SKIPPED", "No single plan.")
                o.reason("OUT_OF_SCOPE", "error", "The question is ambiguous and no approved interpretation could "
                         "be offered. Name a metric from GET /api/metrics and an explicit period.")
                o.checks.skip_rest("V01", "Not executed.")
                o.status = "BLOCKED"
                return
            o.plan = None
            o.clarification = clar
            o.checks = Checks()
            o.checks.set("V01", "SKIPPED", "No single plan.")
            o.checks.skip_rest("V01", "Awaiting clarification.")
            o.status = "AMBIGUOUS"
            o.timing["validation_ms"] = round((time.perf_counter() - v0) * 1000, 1)
            return

        assert plan is not None
        o.plan, o.assumptions = plan, assumptions
        for a in assumptions:
            o.reason(a["code"], "info", a["message"])
        self._execute(o, plan, max_rows, v0)

    def _execute(self, o: Outcome, plan: QueryPlan, max_rows: int, v0: float) -> None:
        try:
            db = self.reader_factory().connect()
        except Db2Error as exc:
            self._registry_unreadable(o)
            ok = self._compile_and_guard(o, plan, max_rows)
            o.timing["validation_ms"] = round((time.perf_counter() - v0) * 1000, 1)
            if not ok:
                return
            o.timing["validation_ms"] = round((time.perf_counter() - v0) * 1000, 1)
            self._fail(o, exc, connecting=True)
            return
        try:
            # V03 registry integrity, read through the least-privilege connection.
            try:
                rows = db.query(
                    "SELECT METRIC_NAME, METRIC_VERSION, DEFINITION_HASH, LIFECYCLE_STATUS "
                    "FROM METRICGUARD.METRIC_DEFINITIONS", ()).rows
                stored = {(r[0].strip(), r[1].strip()): (r[2].strip(), r[3].strip()) for r in rows}
                drift = []
                for ref in plan.metrics:
                    m = METRICS[ref.name]
                    got = stored.get((m.name, m.version))
                    o.registry_rows[m.ref] = got[0] if got else ""
                    if got is None:
                        drift.append(f"{m.ref} is not registered in Db2")
                    elif got[1] != "APPROVED":
                        drift.append(f"{m.ref} is {got[1]} in Db2")
                    elif got[0] != m.definition_hash():
                        drift.append(f"{m.ref} hash differs from the approved Db2 row")
                if drift:
                    o.checks.set("V03", "FAIL", "; ".join(drift))
                    o.reason("REGISTRY_DRIFT", "error", "Runtime metric definitions differ from the approved rows in "
                             "METRICGUARD.METRIC_DEFINITIONS: " + "; ".join(drift) + ".")
                    o.checks.skip_rest("V04", "Blocked by registry drift; not executed.")
                    o.status = "BLOCKED"
                    return
                o.checks.set("V03", "PASS", "Definition hashes match METRICGUARD.METRIC_DEFINITIONS.")
            except Db2Error:
                self._registry_unreadable(o)

            ok = self._compile_and_guard(o, plan, max_rows)
            o.timing["validation_ms"] = round((time.perf_counter() - v0) * 1000, 1)
            if not ok:
                return
            compiled = o.compiled
            assert compiled is not None

            # V08 execution as MGREADER.
            e0 = time.perf_counter()
            try:
                res = db.query(compiled.sql, compiled.param_values, max_rows=max_rows)
            except Db2Error as exc:
                o.timing["execution_ms"] = round((time.perf_counter() - e0) * 1000, 1)
                self._fail(o, exc, connecting=False)
                return
            o.timing["execution_ms"] = round((time.perf_counter() - e0) * 1000, 1)
            rows = _rows(compiled, res)
            o.raw_rows = rows
            principal = (self.settings.db2_reader_user or self.settings.db2_user).upper()
            o.checks.set("V08", "PASS", f"Db2 returned {len(rows)} row{'s' if len(rows) != 1 else ''} "
                         f"as {principal}.")
            if db.role != "reader" or not self.settings.reader_configured:
                o.reason("PRIVILEGED_CONNECTION", "warning", "No read-only Db2 account is configured; the query ran "
                         "with the administrative connection.")

            r0 = time.perf_counter()
            components = self._reconcile(o, db, plan, rows, truncated=res.truncated)
            self._completeness(o, plan, rows, res.truncated)
            self._nulls(o, plan, rows, components)
            o.timing["verification_ms"] = round((time.perf_counter() - r0) * 1000, 1)
        finally:
            db.close()

        json_rows = [{k: (present.to_json_number(v, k) if k in METRICS else (None if v is None else str(v)))
                      for k, v in r.items()} for r in rows]
        o.result = {"columns": present.result_columns(plan), "rows": json_rows, "row_count": len(json_rows),
                    "truncated": res.truncated}
        warnings = [r for r in o.reasons if r["severity"] == "warning"]
        o.status = "EXECUTED_WITH_WARNINGS" if warnings or o.checks.status("V03") != "PASS" else "VERIFIED"

    def _registry_unreadable(self, o: Outcome) -> None:
        o.checks.set("V03", "WARN", "METRICGUARD.METRIC_DEFINITIONS could not be read.")
        o.reason("REGISTRY_UNVERIFIED", "warning", "The approved metric definitions in Db2 could not be read, so "
                 "registry integrity is unverified.")

    def _compile_and_guard(self, o: Outcome, plan: QueryPlan, max_rows: int) -> bool:
        try:
            compiled = compile_plan(plan, max_rows=max_rows)
        except CompileError as exc:
            o.checks.set("V05", "FAIL", str(exc))
            o.reason("COMPILER_REJECTED", "error", f"The deterministic compiler rejected the plan: {exc}")
            o.checks.skip_rest("V05", "Not executed.")
            o.status = "BLOCKED"
            return False
        o.compiled = compiled
        o.sql_hash = hashlib.sha256(compiled.sql.encode("utf-8")).hexdigest()
        o.checks.set("V05", "PASS", "Generated by metricguard-compiler.")
        findings = check_sql(compiled.sql)
        if findings:
            o.checks.set("V06", "FAIL", "; ".join(f.message for f in findings))
            for f in findings:
                o.reason(f.code, "error", f.message)
            o.checks.skip_rest("V06", "Not executed.")
            o.status = "BLOCKED"
            return False
        o.checks.set("V06", "PASS", f"Single SELECT on {len(compiled.tables)} allow-listed tables.")
        issues = parameterization_issues(compiled, plan)
        if issues:
            o.checks.set("V07", "FAIL", "; ".join(issues))
            o.reason("SQL_NOT_PARAMETERIZED", "error", "Compiled SQL is not fully parameterized: " + "; ".join(issues))
            o.checks.skip_rest("V07", "Not executed.")
            o.status = "BLOCKED"
            return False
        n = len(compiled.parameters)
        o.checks.set("V07", "PASS", f"{n} markers, {n} parameters.")
        return True

    def _fail(self, o: Outcome, exc: Db2Error, *, connecting: bool) -> None:
        state = exc.sqlstate
        if state == "57014":
            code, message = "QUERY_TIMEOUT", f"Db2 did not finish within {self.settings.query_timeout_seconds} s."
        elif connecting or (state or "").startswith("08"):
            code, message = "DATABASE_UNAVAILABLE", "IBM Db2 is unavailable."
        else:
            code, message = "DB2_ERROR", "Db2 rejected the governed query."
        o.checks.set("V08", "FAIL", f"SQLSTATE {state}" if state else message)
        o.checks.skip_rest("V08", "Not executed.")
        o.reason(code, "error", message)
        o.error = {"code": code, "message": message, "details": [], "sqlstate": state}
        o.status = "EXECUTION_FAILED"

    # ---- post-execution checks --------------------------------------------------------
    def _reconcile(self, o: Outcome, db: Db2Client, plan: QueryPlan, rows: list[dict[str, Any]], *,
                   truncated: bool) -> dict[tuple, dict[str, Any]] | None:
        names = plan.metric_names
        ratio = [m for m in names if m in _COMPONENTS]
        additive = [m for m in names if METRICS[m].additive]
        comp_names: list[str] = []
        for m in additive + [c for r in ratio for c in _COMPONENTS[r]]:
            if m not in comp_names:
                comp_names.append(m)
        dims = plan.dimensions
        if not dims and not ratio:
            o.checks.set("V09", "SKIPPED", "Single total; no groups to reconcile.")
            return None
        try:
            totals_plan = _aux_plan(plan, list(dict.fromkeys(names + comp_names)), [])
            tq = compile_plan(totals_plan, max_rows=1)
            if check_sql(tq.sql):
                raise CompileError("control query failed the guard")
            totals = _rows(tq, db.query(tq.sql, tq.param_values, max_rows=1))[0]
            o.totals = totals
            groups: dict[tuple, dict[str, Any]] = {}
            if dims:
                gq = compile_plan(_aux_plan(plan, comp_names, dims), max_rows=_RECON_MAX_GROUPS)
                if check_sql(gq.sql):
                    raise CompileError("control query failed the guard")
                for g in _rows(gq, db.query(gq.sql, gq.param_values, max_rows=_RECON_MAX_GROUPS)):
                    groups[_key(g, dims)] = g
        except (Db2Error, CompileError, IndexError):
            o.checks.set("V09", "WARN", "Control-total query could not be completed.")
            o.reason("RECONCILIATION_UNAVAILABLE", "warning", "The independent control-total query could not be "
                     "completed, so the result is not reconciled.")
            return None

        problems: list[str] = []
        detail: list[str] = []
        if dims:
            for m in additive:
                total = sum((Decimal(str(g[m])) for g in groups.values()), Decimal(0))
                if total != Decimal(str(totals[m])):
                    problems.append(f"sum of {m} groups {total} != control total {totals[m]}")
            for r in rows:
                g = groups.get(_key(r, dims))
                if g is None:
                    problems.append(f"group {_key(r, dims)} missing from the control grouping")
                    continue
                for m in additive:
                    if Decimal(str(r[m])) != Decimal(str(g[m])):
                        problems.append(f"{m} for {_key(r, dims)} differs from the control grouping")
                for m in ratio:
                    expect = _recompute(m, g)
                    got = r[m] if r[m] is None else Decimal(str(r[m]))
                    if expect != got:
                        problems.append(f"{m} for {_key(r, dims)} is {got}; components give {expect}")
            if not plan.limit and not truncated and len(rows) != len(groups):
                problems.append(f"{len(rows)} result groups vs {len(groups)} control groups")
        else:
            for m in additive:
                if Decimal(str(rows[0][m])) != Decimal(str(totals[m])):
                    problems.append(f"{m} differs from the control query")
            for m in ratio:
                got = rows[0][m] if rows[0][m] is None else Decimal(str(rows[0][m]))
                if _recompute(m, totals) != got:
                    problems.append(f"{m} is {got}; components give {_recompute(m, totals)}")
        for m in ratio:
            got = totals[m] if totals[m] is None else Decimal(str(totals[m]))
            if _recompute(m, totals) != got:
                problems.append(f"overall {m} does not match its components")

        if problems:
            o.checks.set("V09", "WARN", "; ".join(problems)[:500])
            o.reason("RECONCILIATION_MISMATCH", "warning", "Result does not reconcile with the control query: "
                     + "; ".join(problems[:3]) + ".")
            return groups or {(): totals}
        if dims and additive:
            detail.append("group sums equal control totals ("
                          + "; ".join(f"{m} {present.fmt(totals[m], m)}" for m in additive) + ")")
        if ratio:
            detail.append(f"{', '.join(ratio)} recomputed from reconciled components")
        text = "; ".join(detail)
        o.checks.set("V09", "PASS", text[0].upper() + text[1:] + ".")
        o.reason("RECONCILED", "info", text[0].upper() + text[1:] + ".")
        return groups or {(): totals}

    def _completeness(self, o: Outcome, plan: QueryPlan, rows: list[dict[str, Any]], truncated: bool) -> None:
        notes: list[str] = []
        warn = False
        if truncated:
            warn = True
            notes.append(f"truncated to {len(rows)} rows")
            o.reason("RESULT_TRUNCATED", "warning", f"Only the first {len(rows)} rows are returned; raise "
                     "options.max_rows or narrow the question.")
        empty = not rows or (not plan.dimensions and all(
            rows[0].get(m) in (None, 0) for m in plan.metric_names if METRICS[m].additive) and any(
            METRICS[m].additive for m in plan.metric_names))
        if empty:
            warn = True
            notes.append("no matching orders")
            o.reason("EMPTY_RESULT", "warning", "No completed orders match the requested scope.")
        start, end = plan.date_range.start_date, plan.date_range.end_date
        if start < DATA_COVERAGE_START or end > DATA_COVERAGE_END:
            warn = True
            outside = max(0, (DATA_COVERAGE_START - start).days) + max(0, (end - DATA_COVERAGE_END).days)
            notes.append(f"range extends {outside} days beyond coverage")
            o.reason("RANGE_OUTSIDE_COVERAGE", "warning", f"Data covers {DATA_COVERAGE_START.isoformat()}.."
                     f"{DATA_COVERAGE_END.isoformat()}; {outside} requested days have no data.")
        if warn:
            o.checks.set("V10", "WARN", "; ".join(notes).capitalize() + ".")
        else:
            o.checks.set("V10", "PASS", f"{len(rows)} row{'s' if len(rows) != 1 else ''}, not truncated, "
                         "range within coverage.")

    def _nulls(self, o: Outcome, plan: QueryPlan, rows: list[dict[str, Any]],
               components: dict[tuple, dict[str, Any]] | None) -> None:
        unexpected: list[str] = []
        allowed = 0
        for r in rows:
            for m in plan.metric_names:
                if r.get(m) is not None:
                    continue
                if m in _COMPONENTS:
                    comp = (components or {}).get(_key(r, plan.dimensions)) if components else None
                    den = comp.get(_COMPONENTS[m][1]) if comp else None
                    if comp is None or den in (None, 0) or Decimal(str(den)) == 0:
                        allowed += 1
                        continue
                unexpected.append(f"{m} for {_key(r, plan.dimensions) or 'total'}")
        if unexpected:
            o.checks.set("V11", "WARN", f"Unexpected NULL: {', '.join(unexpected[:5])}.")
            o.reason("UNEXPECTED_NULL", "warning", f"NULL where the registry does not allow it: {', '.join(unexpected[:5])}.")
        elif allowed:
            o.checks.set("V11", "PASS", f"{allowed} NULL value(s), each with a zero denominator as the registry allows.")
        else:
            o.checks.set("V11", "PASS", "No NULL metric values.")


# --------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------
_SUMMARIES = {
    "VERIFIED": "Approved metrics, governed SQL, executed on IBM Db2 and checked against independent control "
                "queries.",
    "EXECUTED_WITH_WARNINGS": "Executed with governed SQL on IBM Db2; read the warnings before relying on these "
                              "numbers.",
    "EXECUTION_FAILED": "The governed query could not be executed on IBM Db2.",
}


def _verification_summary(o: Outcome) -> str:
    if o.status == "VERIFIED" and o.checks.status("V09") == "SKIPPED":
        return "Approved metric, governed SQL, executed on IBM Db2; complete result within data coverage."
    if o.status in _SUMMARIES:
        return _SUMMARIES[o.status]
    sev = "error" if o.status == "BLOCKED" else "warning"
    msgs = [r["message"] for r in o.reasons if r["severity"] == sev]
    return msgs[0] if len(msgs) == 1 else (" ".join(msgs[:2]) if msgs else o.status.title())


def render_response(o: Outcome) -> dict[str, Any]:
    plan = o.plan
    executed = o.status in ("VERIFIED", "EXECUTED_WITH_WARNINGS")
    metrics = []
    if plan is not None:
        for ref in plan.metrics:
            m = METRICS.get(ref.name)
            if m is not None:
                metrics.append({"name": m.name, "version": m.version, "display_name": m.display_name,
                                "unit": m.unit.value, "scale": m.scale, "definition_hash": m.definition_hash()})
    sql = None
    if o.compiled is not None and o.status in ("VERIFIED", "EXECUTED_WITH_WARNINGS", "EXECUTION_FAILED"):
        sql = {"text": o.compiled.sql, "dialect": "db2",
               "parameters": [p.as_dict() for p in o.compiled.parameters], "generated_by": "metricguard-compiler",
               "sql_hash": o.sql_hash, "tables": o.compiled.tables}
    answer = chart = None
    if executed and plan is not None and o.result is not None:
        answer = {"summary": present.summary(plan, o.raw_rows, o.totals, truncated=o.result["truncated"]),
                  "headline": present.headline(plan, o.raw_rows, o.totals)}
        chart = present.chart_spec(plan, o.result["rows"])
    reasons = sorted(o.reasons, key=lambda r: _SEVERITY_RANK[r["severity"]])
    return {
        "request_id": o.request_id,
        "created_at": o.created_at.isoformat().replace("+00:00", "Z"),
        "api_version": API_CONTRACT_VERSION,
        "status": o.status,
        "question": o.question,
        "answer": answer,
        "plan": plan.model_dump(mode="json") if plan is not None and o.status != "AMBIGUOUS" else None,
        "assumptions": o.assumptions if o.status != "AMBIGUOUS" else [],
        "metrics": metrics if o.status != "AMBIGUOUS" else [],
        "sql": sql,
        "result": o.result if executed else None,
        "chart": chart,
        "verification": {"status": o.status, "summary": _verification_summary(o), "reasons": reasons,
                         "checks": o.checks.as_list()},
        "clarification": o.clarification if o.status == "AMBIGUOUS" else None,
        "timing": o.timing,
        "planner": o.planner,
        "audit": {"persisted": False, "url": None},
        "error": o.error if o.status == "EXECUTION_FAILED" else None,
    }


def audit_record(o: Outcome, response: dict[str, Any]) -> dict[str, Any]:
    """Row for METRICGUARD.QUERY_AUDIT_LOG. Contains no credentials and no raw driver/provider messages."""
    def ms(v: float | None) -> int | None:
        return None if v is None else int(round(v))

    reasons = response["verification"]["reasons"]
    top = reasons[0]["code"] if reasons else None
    plan = response["plan"]
    result = response["result"]
    preview = None
    if result is not None:
        preview = {**result, "rows": result["rows"][:20]}
    metric_defs = [{"ref": f"{m['name']}@{m['version']}", "definition_hash": m["definition_hash"],
                    "db2_hash_match": (o.registry_rows.get(f"{m['name']}@{m['version']}") == m["definition_hash"])
                    if o.registry_rows else None} for m in response["metrics"]]
    sql = response["sql"]
    err = response["error"]
    answer = response["answer"]
    return {
        "request_id": o.request_id,
        "created_at": o.created_at.astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ",
                                                                                           timespec="microseconds"),
        "question": o.question[:2000],
        "status": o.status,
        "status_reason": top,
        "metric_refs": ",".join(f"{m.name}@{m.version}" for m in o.plan.metrics) if o.plan is not None
        and o.status != "AMBIGUOUS" else None,
        "planner": o.planner["name"],
        "planner_model": o.planner["model"],
        "execution_mode": o.planner["execution_mode"],
        "plan_json": json.dumps(plan) if plan else None,
        "sql_text": sql["text"] if sql else None,
        "sql_params_json": json.dumps(sql["parameters"]) if sql else None,
        "sql_hash": sql["sql_hash"] if sql else None,
        "verification_json": json.dumps(response["verification"]),
        "result_row_count": result["row_count"] if result else None,
        "result_preview_json": json.dumps(preview) if preview else None,
        "answer_summary": answer["summary"][:2000] if answer else None,
        "metric_defs_json": json.dumps(metric_defs) if metric_defs else None,
        "total_ms": ms(o.timing["total_ms"]),
        "planning_ms": ms(o.timing["planning_ms"]),
        "validation_ms": ms(o.timing["validation_ms"]),
        "execution_ms": ms(o.timing["execution_ms"]),
        "verification_ms": ms(o.timing["verification_ms"]),
        "error_code": err["code"] if err else None,
        "error_message": err["message"][:1000] if err else None,
        "api_version": API_CONTRACT_VERSION,
    }

