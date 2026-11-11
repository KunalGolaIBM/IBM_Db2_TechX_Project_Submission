"""`metricguard db verify`: prove the Db2 database matches the documented semantics.

Sections
1. connectivity  - server identity and version from Db2 itself
2. schema        - all required tables present, row counts match the deterministic generator
3. data quality  - invariants the metric semantics depend on
4. registry      - METRIC_DEFINITIONS hashes match the runtime registry
5. golden        - compiled analytical queries executed on Db2 == independent Python oracle
6. canaries      - hand-computed edge-case orders
7. traps         - naive SQL vs governed SQL (shows why governance matters)
8. reconciliation- grouped totals add up to the ungrouped control total
"""

from __future__ import annotations

import json
import platform
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from metricguard import API_CONTRACT_VERSION, __version__
from metricguard.config import REPO_ROOT, Settings
from metricguard.core.compiler import compile_plan
from metricguard.core.examples import EXAMPLES
from metricguard.core.plan import DateRange, MetricRef, QueryPlan
from metricguard.core.registry import METRICS, registry_fingerprint
from metricguard.core.sql_guard import check_sql
from metricguard.core.validator import validate_plan
from metricguard.db import Db2Client, Db2Error
from metricguard.seed import oracle
from metricguard.seed.generator import generate

S = "METRICGUARD"
REQUIRED_TABLES = ["ORDERS", "ORDER_ITEMS", "PRODUCTS", "REFUNDS", "METRIC_DEFINITIONS", "QUERY_AUDIT_LOG"]

DQ_CHECKS: list[tuple[str, str, str]] = [
    ("DQ-01", "Every order has at least one line (order_count is derived from lines)",
     f"SELECT COUNT(*) FROM {S}.ORDERS o WHERE NOT EXISTS (SELECT 1 FROM {S}.ORDER_ITEMS i WHERE i.ORDER_ID = o.ORDER_ID)"),
    ("DQ-02", "Processed refunds never exceed the refunded line's revenue",
     f"SELECT COUNT(*) FROM (SELECT r.ORDER_ITEM_ID, SUM(r.REFUND_AMOUNT) AS AMT FROM {S}.REFUNDS r "
     f"WHERE r.STATUS = 'PROCESSED' GROUP BY r.ORDER_ITEM_ID) x JOIN {S}.ORDER_ITEMS i ON i.ORDER_ITEM_ID = x.ORDER_ITEM_ID "
     "WHERE x.AMT > i.QUANTITY * i.UNIT_PRICE - i.DISCOUNT_AMOUNT"),
    ("DQ-03", "No refund is dated before its order",
     f"SELECT COUNT(*) FROM {S}.REFUNDS r JOIN {S}.ORDERS o ON o.ORDER_ID = r.ORDER_ID WHERE r.REFUND_TS < o.ORDER_TS"),
    ("DQ-04", "No order falls outside the documented coverage window 2026-01-01..2026-06-30",
     f"SELECT COUNT(*) FROM {S}.ORDERS WHERE ORDER_TS < '2026-01-01 00:00:00' OR ORDER_TS >= '2026-07-01 00:00:00'"),
    ("DQ-05", "Refund rows always reference a line of the same order (composite FK)",
     f"SELECT COUNT(*) FROM {S}.REFUNDS r JOIN {S}.ORDER_ITEMS i ON i.ORDER_ITEM_ID = r.ORDER_ITEM_ID WHERE i.ORDER_ID <> r.ORDER_ID"),
]

# Naive SQL a text-to-SQL model commonly writes, vs the governed metric value.
TRAPS: list[dict[str, Any]] = [
    {
        "id": "TRAP-01",
        "title": "Refunds joined to items at order grain (fan-out)",
        "metric": "gross_revenue",
        "naive_sql": f"SELECT CAST(SUM(i.QUANTITY * i.UNIT_PRICE - i.DISCOUNT_AMOUNT) AS DECIMAL(18,2)) FROM {S}.ORDERS o "
                     f"JOIN {S}.ORDER_ITEMS i ON i.ORDER_ID = o.ORDER_ID LEFT JOIN {S}.REFUNDS r ON r.ORDER_ID = o.ORDER_ID "
                     "WHERE o.STATUS = 'COMPLETED'",
    },
    {
        "id": "TRAP-02",
        "title": "Net revenue ignoring order status and refund status",
        "metric": "net_revenue",
        "naive_sql": f"SELECT CAST((SELECT SUM(QUANTITY * UNIT_PRICE - DISCOUNT_AMOUNT) FROM {S}.ORDER_ITEMS) - "
                     f"(SELECT SUM(REFUND_AMOUNT) FROM {S}.REFUNDS) AS DECIMAL(18,2)) FROM SYSIBM.SYSDUMMY1",
    },
    {
        "id": "TRAP-03",
        "title": "Revenue including shipping summed after a line join",
        "metric": "gross_revenue",
        "naive_sql": f"SELECT CAST(SUM(i.QUANTITY * i.UNIT_PRICE - i.DISCOUNT_AMOUNT + o.SHIPPING_AMOUNT) AS DECIMAL(18,2)) "
                     f"FROM {S}.ORDERS o JOIN {S}.ORDER_ITEMS i ON i.ORDER_ID = o.ORDER_ID WHERE o.STATUS = 'COMPLETED'",
    },
    {
        "id": "TRAP-04",
        "title": "January order count with BETWEEN '2026-01-01' AND '2026-01-31' (drops Jan 31 after midnight)",
        "metric": "order_count",
        "range": (date(2026, 1, 1), date(2026, 1, 31)),
        "naive_sql": f"SELECT COUNT(*) FROM {S}.ORDERS WHERE STATUS = 'COMPLETED' "
                     "AND ORDER_TS BETWEEN '2026-01-01' AND '2026-01-31'",
    },
]

CANARY_SQL = (
    f"SELECT o.ORDER_ID, o.STATUS, VARCHAR_FORMAT(o.ORDER_TS, 'YYYY-MM') AS ORDER_MONTH, "
    f"CAST(SUM(i.QUANTITY * i.UNIT_PRICE - i.DISCOUNT_AMOUNT) AS DECIMAL(18,2)) AS LINE_REVENUE, "
    f"CAST(COALESCE((SELECT SUM(r.REFUND_AMOUNT) FROM {S}.REFUNDS r WHERE r.ORDER_ID = o.ORDER_ID "
    f"AND r.STATUS = 'PROCESSED'), 0) AS DECIMAL(18,2)) AS PROCESSED_REFUNDS "
    f"FROM {S}.ORDERS o JOIN {S}.ORDER_ITEMS i ON i.ORDER_ID = o.ORDER_ID "
    f"WHERE o.ORDER_ID IN (90001, 90002, 90003, 90004) GROUP BY o.ORDER_ID, o.STATUS, o.ORDER_TS ORDER BY o.ORDER_ID"
)
# Hand-computed (docs/METRIC_SEMANTICS.md section 6).
CANARY_EXPECTED = {
    90001: ("COMPLETED", "2026-01", Decimal("110.00"), Decimal("20.00")),
    90002: ("COMPLETED", "2026-02", Decimal("40.00"), Decimal("40.00")),
    90003: ("CANCELLED", "2026-02", Decimal("100.00"), Decimal("100.00")),
    90004: ("COMPLETED", "2026-03", Decimal("0.00"), Decimal("0.00")),
}


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _all_metrics_plan(start: date, end: date, dims: list[str] | None = None) -> QueryPlan:
    names = [m.name for m in METRICS.values() if m.additive]  # reconciliation applies to additive metrics
    if dims and "product_category" in dims:
        names = [n for n in names if "product_category" in METRICS[n].allowed_dimensions]
    return QueryPlan(
        metrics=[MetricRef(name=n, version=METRICS[n].version) for n in names],
        dimensions=dims or [],
        date_range=DateRange(start_date=start, end_date=end),
    )


def _apply_order_limit(rows: list[dict[str, Any]], plan: QueryPlan) -> list[dict[str, Any]]:
    out = list(rows)
    for ob in reversed(plan.order_by):
        out.sort(key=lambda r: (r[ob.field] is None, r[ob.field]), reverse=ob.direction == "desc")
    return out[: plan.limit] if plan.limit else out


def run_plan(db: Db2Client, plan: QueryPlan, max_rows: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compiled = compile_plan(plan, max_rows=max_rows)
    findings = check_sql(compiled.sql)
    if findings:
        raise RuntimeError(f"SQL guard rejected compiled SQL: {findings}")
    res = db.query(compiled.sql, compiled.param_values, max_rows=max_rows)
    rows = [{c.name: row[i] for i, c in enumerate(compiled.columns)} for row in res.rows]
    meta = {"sql": compiled.sql, "parameters": [p.as_dict() for p in compiled.parameters],
            "execution_ms": res.elapsed_ms, "row_count": len(rows)}
    return rows, meta


def verify(settings: Settings, *, log=print) -> dict[str, Any]:
    ds = generate()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metricguard_version": __version__,
        "api_contract_version": API_CONTRACT_VERSION,
        "client": {"python": platform.python_version(), "machine": platform.machine(), "os": platform.system()},
        "target": settings.redacted_target(),
    }
    failures = 0

    admin = Db2Client(settings).connect()
    reader_enabled = bool(settings.db2_reader_user and settings.db2_reader_password)
    try:
        reader = Db2Client(settings, reader=True).connect() if reader_enabled else admin
    except Db2Error as exc:
        log(f"WARNING: reader connection failed ({exc.sqlstate}); using admin connection")
        reader, reader_enabled = admin, False
    report["analytical_connection"] = settings.db2_reader_user if reader_enabled else settings.db2_user

    try:
        # 1. connectivity ----------------------------------------------------------
        ident = admin.server_identity()
        report["connectivity"] = {
            "status": "PASS",
            **{k: _jsonable(v) for k, v in ident.items()},
            "codeset": admin.scalar("SELECT VALUE FROM SYSIBMADM.DBCFG WHERE NAME = 'codeset'"),
        }
        log(f"[connectivity] {report['connectivity']['service_level']} as {report['connectivity']['current_user']}")

        # 2. schema ----------------------------------------------------------------
        present = {r[0] for r in admin.query(
            "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T'", (S,)).rows}
        expected_counts = {"ORDERS": len(ds.orders), "ORDER_ITEMS": len(ds.items), "PRODUCTS": len(ds.products),
                           "REFUNDS": len(ds.refunds), "METRIC_DEFINITIONS": len(METRICS)}
        tables = []
        for t in REQUIRED_TABLES:
            count = admin.scalar(f"SELECT COUNT(*) FROM {S}.{t}") if t in present else None
            exp = expected_counts.get(t)
            ok = t in present and (exp is None or count == exp)
            failures += not ok
            tables.append({"table": t, "present": t in present, "rows": count, "expected_rows": exp,
                           "status": "PASS" if ok else "FAIL"})
        idx = admin.query("SELECT TABNAME, COUNT(*) FROM SYSCAT.INDEXES WHERE TABSCHEMA = ? GROUP BY TABNAME "
                          "ORDER BY TABNAME", (S,)).rows
        report["schema"] = {"tables": tables, "indexes_per_table": {r[0]: r[1] for r in idx}}
        log(f"[schema] {sum(t['status'] == 'PASS' for t in tables)}/{len(tables)} tables OK")

        # 3. data quality ----------------------------------------------------------
        dq = []
        for cid, title, sql in DQ_CHECKS:
            bad = admin.scalar(sql)
            failures += bad != 0
            dq.append({"id": cid, "check": title, "violations": bad, "status": "PASS" if bad == 0 else "FAIL"})
        report["data_quality"] = dq
        log(f"[data quality] {sum(d['status'] == 'PASS' for d in dq)}/{len(dq)} checks pass")

        # 4. registry ----------------------------------------------------------------
        stored = {(r[0], r[1]): r[2].strip() for r in admin.query(
            f"SELECT METRIC_NAME, METRIC_VERSION, DEFINITION_HASH FROM {S}.METRIC_DEFINITIONS "
            "WHERE LIFECYCLE_STATUS = 'APPROVED'").rows}
        reg = []
        for m in METRICS.values():
            ok = stored.get((m.name, m.version)) == m.definition_hash()
            failures += not ok
            reg.append({"metric": m.ref, "hash": m.definition_hash()[:16], "status": "PASS" if ok else "FAIL"})
        report["registry"] = {"fingerprint": registry_fingerprint(), "metrics": reg}
        log(f"[registry] {sum(r['status'] == 'PASS' for r in reg)}/{len(reg)} definitions match Db2")

        # 5. golden analytical queries ---------------------------------------------
        golden = []
        for ex in EXAMPLES:
            if ex.reference_plan is None:
                continue
            plan = ex.reference_plan
            issues = validate_plan(plan)
            rows, meta = run_plan(reader, plan, settings.max_result_rows)
            expected = oracle.compute(
                ds, metrics=plan.metric_names, dimensions=plan.dimensions,
                start=plan.date_range.start_date, end=plan.date_range.end_date,
                filters={f.field: f.values for f in plan.filters},
            )
            expected = _apply_order_limit(expected, plan)
            match = rows == expected and not issues
            failures += not match
            golden.append({
                "id": ex.id, "question": ex.question, "status": "PASS" if match else "FAIL",
                "plan_issues": [i.code for i in issues], "row_count": meta["row_count"],
                "execution_ms": meta["execution_ms"],
                "db2_rows": [{k: _jsonable(v) for k, v in r.items()} for r in rows],
                "oracle_rows": [{k: _jsonable(v) for k, v in r.items()} for r in expected],
                "sql": meta["sql"], "parameters": meta["parameters"],
            })
            log(f"[golden] {ex.id}: {'PASS' if match else 'FAIL'} ({meta['row_count']} rows, {meta['execution_ms']} ms)")
        report["golden_queries"] = golden

        # 6. canaries ----------------------------------------------------------------
        can = []
        for row in admin.query(CANARY_SQL).rows:
            oid = row[0]
            got = (row[1].strip(), row[2], row[3], row[4])
            ok = got == CANARY_EXPECTED[oid]
            failures += not ok
            can.append({"order_id": oid, "status": "PASS" if ok else "FAIL", "db2": [_jsonable(v) for v in got],
                        "hand_computed": [_jsonable(v) for v in CANARY_EXPECTED[oid]]})
        failures += len(can) != len(CANARY_EXPECTED)
        report["canaries"] = can
        log(f"[canaries] {sum(c['status'] == 'PASS' for c in can)}/{len(CANARY_EXPECTED)} hand-computed orders match")

        # 7. traps --------------------------------------------------------------------
        traps = []
        for trap in TRAPS:
            start, end = trap.get("range", (date(2026, 1, 1), date(2026, 6, 30)))
            plan = QueryPlan(metrics=[MetricRef(name=trap["metric"], version=METRICS[trap["metric"]].version)],
                             date_range=DateRange(start_date=start, end_date=end))
            governed_rows, _ = run_plan(reader, plan, settings.max_result_rows)
            governed = governed_rows[0][trap["metric"]]
            naive = admin.scalar(trap["naive_sql"])
            traps.append({"id": trap["id"], "title": trap["title"], "metric": trap["metric"],
                          "governed_value": _jsonable(governed), "naive_value": _jsonable(naive),
                          "difference": _jsonable(naive - governed), "naive_sql": trap["naive_sql"]})
            log(f"[trap] {trap['id']}: governed={governed} naive={naive}")
        report["traps"] = traps

        # 8. reconciliation ----------------------------------------------------------
        totals_rows, _ = run_plan(reader, _all_metrics_plan(date(2026, 1, 1), date(2026, 6, 30)), 10)
        totals = totals_rows[0]
        recon = []
        for dim in ["order_month", "region", "channel", "product_category"]:
            rows, _ = run_plan(reader, _all_metrics_plan(date(2026, 1, 1), date(2026, 6, 30), [dim]), 100)
            for metric in ["gross_revenue", "net_revenue", "refund_amount", "order_count"]:
                if metric not in rows[0]:
                    continue
                total = sum(r[metric] for r in rows)
                ok = total == totals[metric]
                failures += not ok
                recon.append({"dimension": dim, "metric": metric, "sum_of_groups": _jsonable(total),
                              "control_total": _jsonable(totals[metric]), "status": "PASS" if ok else "FAIL"})
        report["h1_totals"] = {k: _jsonable(v) for k, v in totals.items()}
        report["reconciliation"] = recon
        log(f"[reconciliation] {sum(r['status'] == 'PASS' for r in recon)}/{len(recon)} grouped sums equal the control total")

        # 9. least privilege -------------------------------------------------------
        if reader_enabled:
            try:
                reader.execute(f"DELETE FROM {S}.REFUNDS WHERE REFUND_ID = -1")
                priv = {"status": "FAIL", "detail": "reader was able to run DELETE"}
                failures += 1
            except Db2Error as exc:
                priv = {"status": "PASS", "detail": f"DELETE rejected by Db2 (SQLSTATE {exc.sqlstate}, SQLCODE {exc.sqlcode})"}
            report["least_privilege"] = priv
            log(f"[least privilege] {priv['status']}: {priv['detail']}")

        # 10. audit writer: append-only, no business data --------------------
        if settings.audit_configured:
            audit_checks = []
            try:
                with Db2Client(settings, role="audit") as aud:
                    for label, sql in [
                        ("SELECT business data", f"SELECT COUNT(*) FROM {S}.ORDERS"),
                        ("UPDATE audit rows", f"UPDATE {S}.QUERY_AUDIT_LOG SET STATUS = 'VERIFIED' WHERE REQUEST_ID = 'x'"),
                        ("DELETE audit rows", f"DELETE FROM {S}.QUERY_AUDIT_LOG WHERE REQUEST_ID = 'x'"),
                    ]:
                        try:
                            aud.query(sql) if sql.startswith("SELECT") else aud.execute(sql)
                            audit_checks.append(f"{label}: ALLOWED")
                            failures += 1
                        except Db2Error as exc:
                            audit_checks.append(f"{label}: rejected (SQLSTATE {exc.sqlstate})")
                    aud.scalar(f"SELECT COUNT(*) FROM {S}.QUERY_AUDIT_LOG")
                ok = all("rejected" in c for c in audit_checks)
                report["audit_writer"] = {"status": "PASS" if ok else "FAIL", "user": settings.db2_audit_user.upper(),
                                          "detail": "; ".join(audit_checks)}
            except Db2Error as exc:
                failures += 1
                report["audit_writer"] = {"status": "FAIL", "user": settings.db2_audit_user,
                                          "detail": f"audit connection failed (SQLSTATE {exc.sqlstate})"}
            log(f"[audit writer] {report['audit_writer']['status']}: {report['audit_writer']['detail']}")
    finally:
        if reader is not admin:
            reader.close()
        admin.close()

    report["failures"] = failures
    report["result"] = "PASS" if failures == 0 else "FAIL"
    return report


def write_evidence(report: dict[str, Any]) -> list[str]:
    out_dir = REPO_ROOT / "evidence"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "db2_verification.json"
    json_path.write_text(json.dumps(report, indent=2, default=_jsonable) + "\n")

    c = report["connectivity"]
    lines = [
        "# Db2 Verification Evidence",
        "",
        f"Generated by `make db-verify` at {report['generated_at']} — overall result: **{report['result']}** "
        f"({report['failures']} failures). Credentials are never written to this file.",
        "",
        "## Connectivity",
        "",
        "| Field | Value |", "|---|---|",
        f"| Server | {c['dbms_name']} {c['dbms_version']} |",
        f"| Service level | {c['service_level']} (SYSIBM.SYSVERSIONS {c['version_number']}) |",
        f"| Code set | {c['codeset']} |",
        f"| Database | {c['current_server']} |",
        f"| Connected as | {c['current_user']} (analytical queries as `{report['analytical_connection']}`) |",
        f"| Server timestamp | {c['server_timestamp']} |",
        f"| Client | Python {report['client']['python']} on {report['client']['os']} {report['client']['machine']} |",
        "",
        "## Tables",
        "",
        "| Table | Rows | Expected | Status |", "|---|---:|---:|---|",
        *[f"| {t['table']} | {t['rows']} | {t['expected_rows'] if t['expected_rows'] is not None else '—'} | {t['status']} |"
          for t in report["schema"]["tables"]],
        "",
        "## Data quality",
        "",
        "| Check | Violations | Status |", "|---|---:|---|",
        *[f"| {d['id']} {d['check']} | {d['violations']} | {d['status']} |" for d in report["data_quality"]],
        "",
        "## Golden analytical queries (Db2 result == independent oracle)",
        "",
        "| Example | Rows | Db2 ms | Status |", "|---|---:|---:|---|",
        *[f"| {g['id']} — {g['question']} | {g['row_count']} | {g['execution_ms']} | {g['status']} |"
          for g in report["golden_queries"]],
        "",
        "## H1 2026 control totals",
        "",
        "| Metric | Value |", "|---|---:|",
        *[f"| {k} | {v} |" for k, v in report["h1_totals"].items()],
        "",
        "## Naive SQL vs governed metric",
        "",
        "| Trap | Governed | Naive | Naive − governed |", "|---|---:|---:|---:|",
        *[f"| {t['id']} {t['title']} | {t['governed_value']} | {t['naive_value']} | {t['difference']} |"
          for t in report["traps"]],
        "",
        "## Canary orders (hand-computed)",
        "",
        "| Order | Db2 [status, month, line revenue, processed refunds] | Status |", "|---|---|---|",
        *[f"| {x['order_id']} | {', '.join(map(str, x['db2']))} | {x['status']} |" for x in report["canaries"]],
        "",
        "## Reconciliation",
        "",
        f"{sum(r['status'] == 'PASS' for r in report['reconciliation'])}/{len(report['reconciliation'])} "
        "grouped sums equal the ungrouped control total.",
        "",
    ]
    if "least_privilege" in report:
        lp = report["least_privilege"]
        lines += ["## Least privilege", "", f"{lp['status']}: {lp['detail']}", ""]
    if "audit_writer" in report:
        aw = report["audit_writer"]
        lines += ["## Audit writer (append-only)", "",
                  f"{aw['status']}: `{aw['user']}` may INSERT and SELECT QUERY_AUDIT_LOG only. {aw['detail']}", ""]
    md_path = out_dir / "DB2_VERIFICATION.md"
    md_path.write_text("\n".join(lines))
    return [str(json_path.relative_to(REPO_ROOT)), str(md_path.relative_to(REPO_ROOT))]
