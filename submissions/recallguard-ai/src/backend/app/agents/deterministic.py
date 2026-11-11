"""Deterministic agent implementations.

These functions are used in two ways:
  1. As the clearly-labelled DETERMINISTIC_FALLBACK when no LLM is configured.
  2. As the fact-producing tools behind the CrewAI agents (crew.py): LLM agents
     receive these Db2-derived structured facts and may only add narrative.

Nothing here fabricates data: every ID, quantity and location comes from a Db2
query result or an uploaded document's verbatim text.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable

from app.database import Database
from app.database.queries import sql
from app.services import evidence as ev
from app.services.risk import compute_risk, recall_class_for
from app.services.traceability import impact_analysis, lineage_path

from .schemas import (
    Conflict,
    DataGap,
    EvidenceRef,
    ExcludedBatch,
    InvestigationFindings,
    LocationExposure,
    Notification,
    RecallItem,
    RecallPlan,
    RiskAssessment,
    SupplyChainFindings,
    VerificationCheck,
    VerificationReport,
)

Log = Callable[[str], None]
ID_RE = re.compile(r"\b(?:PB-20\d{2}-\d{4}|[A-Z]{3}-20\d{2}-\d{3})\b")


# ============================================================== 1. Investigation
def investigation_agent(db: Database, ctx: dict[str, Any], log: Log) -> InvestigationFindings:
    inc = ctx["incident"]
    src = inc["source_ref"]
    log(f"Reading incident {inc['incident_id']}: {inc['contaminant']} ({inc['severity']}) reported on {src}.")
    docs = ev.list_documents(db, incident_id=inc["incident_id"])
    log(f"Loaded {len(docs)} evidence document(s) linked to the incident from Db2 table EVIDENCE_DOCUMENTS.")
    lab_findings, lots, dates = [], set(), set()
    for d in docs:
        for c in d["extracted"].get("claims", []):
            ref = EvidenceRef(document_id=d["document_id"], filename=d["filename"], page=c.get("page"), section=c.get("section"),
                              snippet=c.get("snippet", ""), claim_type=c["type"], value=c["value"], positive=c.get("positive"))
            if c["type"] == "test_result":
                lab_findings.append(ref)
            elif c["type"] == "lot_id":
                lots.add(c["value"])
            elif c["type"] == "date":
                dates.add(c["value"])
    positives = [f for f in lab_findings if f.positive]
    log(f"Grounded extraction: {len(lab_findings)} test-result lines, {len(positives)} positive; lot ids mentioned: {sorted(lots) or 'none'}.")

    # Quality records stored in Db2 for the source and its first-level outputs
    qrs = db.query("SELECT report_id, subject_ref, report_type, issued_by, issued_date, result_summary, outcome, document_id "
                   "FROM quality_reports WHERE subject_ref = ? OR subject_ref IN "
                   "(SELECT output_batch_id FROM batch_transformations WHERE input_ref = ?) ORDER BY issued_date", (src, src))
    supporting = [EvidenceRef(document_id=q["document_id"], filename=q["report_id"], snippet=q["result_summary"],
                              claim_type=q["report_type"], value=q["outcome"], positive=q["outcome"] == "FAIL")
                  for q in qrs]
    log(f"Found {len(qrs)} QUALITY_REPORTS record(s) for {src} and its direct outputs.")

    conflicts: list[Conflict] = []
    for q in qrs:
        if q["subject_ref"] == src and q["outcome"] == "PASS" and positives:
            conflicts.append(Conflict(
                topic=f"Microbiological status of {src}",
                statement_a=f"{q['report_type']} {q['report_id']} ({q['issued_by']}, {q['issued_date']}): {q['result_summary']}",
                statement_b=f"{positives[0].filename} p.{positives[0].page}: {positives[0].snippet}",
                sources=[q["report_id"], positives[0].document_id or ""],
                resolution="Independent laboratory result takes precedence for safety decisions; supplier COA sampling (n=1) may have missed "
                           "heterogeneous contamination. Human reviewer must confirm."))
        if q["outcome"] == "INCONCLUSIVE":
            log(f"Process QC record {q['report_id']} on {q['subject_ref']} is INCONCLUSIVE: {q['result_summary']}")

    missing = []
    if not docs:
        missing.append("No laboratory report uploaded for this incident.")
    if docs and not positives:
        missing.append("Uploaded documents contain no positive/confirmed test result — contamination not laboratory-confirmed.")
    if lots and src not in lots and inc["source_kind"] == "LOT":
        missing.append(f"Lab report references {sorted(lots)} but the incident source is {src}; confirm the lot identity.")

    supplier = db.query_one("SELECT s.supplier_id, s.supplier_name FROM suppliers s WHERE s.supplier_id = ?", (inc.get("supplier_id"),)) if inc.get("supplier_id") else None
    qc_inconclusive = [q for q in qrs if q["outcome"] == "INCONCLUSIVE"]
    hypothesis = ""
    if qc_inconclusive:
        hypothesis = (f"Possible contributing process deviation: {qc_inconclusive[0]['report_id']} on {qc_inconclusive[0]['subject_ref']} — "
                      f"{qc_inconclusive[0]['result_summary']}. Supplier-origin contamination remains the primary hypothesis.")
    summary = (f"{inc['contaminant']} reported on {inc['source_kind'].lower()} {src}"
               + (f" supplied by {supplier['supplier_name']} ({supplier['supplier_id']})" if supplier else "")
               + (f". Laboratory evidence confirms {len(positives)} positive result(s)." if positives else ". No positive laboratory result on file yet.")
               + (f" {len(conflicts)} conflicting record(s) identified." if conflicts else ""))
    log("Investigation findings assembled.")
    return InvestigationFindings(
        incident_id=inc["incident_id"], suspected_source_ref=src, source_kind=inc["source_kind"],
        supplier_id=supplier["supplier_id"] if supplier else None, supplier_name=supplier["supplier_name"] if supplier else None,
        contaminant=inc["contaminant"], lab_confirmed=bool(positives), lab_findings=lab_findings, supporting_records=supporting,
        extracted_lot_ids=sorted(lots), extracted_dates=sorted(dates), conflicts=conflicts, missing_evidence=missing,
        summary=summary, hypothesis=hypothesis)


# ============================================================== 2. Supply chain
def supply_chain_agent(db: Database, ctx: dict[str, Any], log: Log) -> SupplyChainFindings:
    src = ctx["investigation"].suspected_source_ref
    log(f"Executing Db2 recursive genealogy + distribution trace for {src}.")
    imp = impact_analysis(db, src)
    ctx["impact"] = imp
    for q in imp["queries"]:
        log(f"  Db2 query {q['query']}: {q['rows']} rows in {q['ms']} ms")
    s = imp["summary"]
    log(f"Affected: {s['batches_total']} batches ({s['batches_direct']} direct, {s['batches_indirect']} indirect), {s['products']} products, "
        f"{s['warehouses']} warehouses, {s['distributors']} distributors, {s['retailers']} retailers.")
    for g in imp["data_gaps"]:
        log(f"  GAP [{g['severity']}] {g['code']}: {g['message']}")
    batches = imp["batches"]
    return SupplyChainFindings(
        source_ref=src,
        affected_batch_ids=[b["batch_id"] for b in batches],
        direct_batch_ids=[b["batch_id"] for b in batches if b["relation"] == "DIRECT"],
        indirect_batch_ids=[b["batch_id"] for b in batches if b["relation"] == "INDIRECT"],
        finished_batch_ids=[b["batch_id"] for b in batches if b["batch_type"] == "FINISHED"],
        product_ids=[p["product_id"] for p in imp["products"]],
        locations=[LocationExposure(loc_kind=l["loc_kind"], loc_ref=l["loc_ref"], loc_name=l["loc_name"], city=l["city"],
                                    units_received=l["units_received"], units_held=l["units_held"], units_in_transit=l["units_in_transit"],
                                    batches=[x["batch_id"] for x in l["batches"]], products=l["products"]) for l in imp["locations"]],
        data_gaps=[DataGap(**g) for g in imp["data_gaps"]],
        summary_counts={k: int(v) for k, v in s.items()},
        queries_executed=imp["queries"], engine=imp["engine"],
        summary=(f"Db2 traced {src} through {s['max_depth']} transformation level(s) to {s['finished_batches']} finished batches of "
                 f"{s['products']} products ({s['units_produced']:,} units), shipped via {s['shipments']} shipments to "
                 f"{s['retailers']} retailers in {s['cities']} cities. {s['data_gaps']} traceability gap(s) flagged."))


# ============================================================== 3. Risk
def risk_agent(db: Database, ctx: dict[str, Any], log: Log) -> RiskAssessment:
    inc, sc, inv = ctx["incident"], ctx["supply_chain"], ctx["investigation"]
    r = compute_risk(severity=inc["severity"], category=inc["contamination_category"], impact_summary=sc.summary_counts,
                     data_gaps=[g.model_dump() for g in sc.data_gaps], discovered_at=inc["discovered_at"],
                     evidence_confirmed=inv.lab_confirmed)
    for f in r["factors"]:
        log(f"  {f['factor']:<12} w={f['weight']:>2}  norm={f['normalized']:.2f}  +{f['contribution']:.1f}  {f['reason']}")
    rc = recall_class_for(r["score"], inc["contamination_category"], inc["severity"])
    log(f"Risk score {r['score']}/100 -> {r['classification']} ({rc}); completeness {r['data_completeness_pct']}%, confidence {r['confidence']}.")
    return RiskAssessment(**r, recall_class=rc)


# ============================================================== 4. Recall planning
def _priority(loc_kind: str, units: int, in_transit: int, critical: bool) -> str:
    if loc_kind == "RETAILER" and units > 0:
        return "P1"
    if in_transit > 0 or (critical and loc_kind in ("WAREHOUSE", "DISTRIBUTOR")):
        return "P1" if in_transit > 0 else "P2"
    return "P2" if loc_kind in ("WAREHOUSE", "DISTRIBUTOR") else "P3"


def recall_planning_agent(db: Database, ctx: dict[str, Any], log: Log) -> RecallPlan:
    inc, inv, risk = ctx["incident"], ctx["investigation"], ctx["risk"]
    imp = ctx["impact"]
    src = imp["source"]["ref"]
    batch_info = {b["batch_id"]: b for b in imp["batches"]}
    gap_refs = {r for g in imp["data_gaps"] for r in g["refs"]}
    lab_refs = [f"{f.document_id} p.{f.page}" for f in inv.lab_findings if f.positive][:2]
    shipments_by = defaultdict(list)
    for h in imp["hops"]:
        shipments_by[(h["batch_id"], h["dest_ref"])].append(h["shipment_id"])
    critical = risk.classification in ("CRITICAL", "HIGH")
    items: list[RecallItem] = []
    for loc in imp["locations"]:
        for x in loc["batches"]:
            b = batch_info.get(x["batch_id"])
            if not b or b["batch_type"] != "FINISHED":
                continue
            units = x["units_held"]
            if units <= 0:
                continue
            path = lineage_path(imp["edges"], src, b["batch_id"])
            uncertain = b.get("uncertain_link") or loc["loc_ref"] in gap_refs and (
                any(g["code"] == "DISTRIBUTION_DEAD_END" and loc["loc_ref"] in g["refs"] for g in imp["data_gaps"]))
            basis = "PRECAUTIONARY" if uncertain else b["relation"] if b["relation"] in ("DIRECT", "INDIRECT") else "DIRECT"
            state = ("in transit to" if x["in_transit_units"] else "held at" if loc["loc_kind"] != "RETAILER" else "delivered to")
            reason = (f"{b['batch_id']} ({b['product_name']}) derives from {src} (lineage {' -> '.join(path)}) "
                      f"[{b['relation'].lower()}, Db2 genealogy depth {b['depth']}]; {units:,} units {state} {loc['loc_name']}.")
            if b.get("uncertain_link"):
                reason += " Genealogy link is UNVERIFIED — included conservatively."
            if basis == "PRECAUTIONARY" and loc["loc_kind"] == "DISTRIBUTOR":
                reason += " Onward distribution unknown (no shipment records) — distributor must disclose recipients."
            refs = shipments_by.get((b["batch_id"], loc["loc_ref"]), []) + lab_refs
            items.append(RecallItem(
                batch_id=b["batch_id"], product_id=b["product_id"], product_name=b["product_name"], location_kind=loc["loc_kind"],
                location_ref=loc["loc_ref"], location_name=loc["loc_name"], city=loc["city"], quantity_units=units,
                priority=_priority(loc["loc_kind"], units, x["in_transit_units"], critical), inclusion_basis=basis,
                reason=reason[:600], evidence_refs=refs[:6], lineage_path=path))
    log(f"Built {len(items)} batch-location recall items from Db2 impact rows (only locations holding stock).")

    # Notifications: every location that ever handled an affected finished batch (incl. pass-through nodes)
    notif: dict[str, dict[str, Any]] = {}
    for loc in imp["locations"]:
        fb = [x for x in loc["batches"] if batch_info.get(x["batch_id"], {}).get("batch_type") == "FINISHED"]
        if not fb:
            continue
        held = sum(x["units_held"] for x in fb)
        acts = ["NOTIFY"]
        if held > 0:
            acts.append("RECOVER" if loc["loc_kind"] == "RETAILER" else "QUARANTINE")
        prods = sorted({batch_info[x["batch_id"]]["product_name"] for x in fb})
        bl = sorted({x["batch_id"] for x in fb})
        instr = (f"[SIMULATED NOTICE — {risk.recall_class.replace('_', ' ')}] {loc['loc_name']} ({loc['loc_ref']}): "
                 f"Immediately stop sale/dispatch of {', '.join(prods)} — batch(es) {', '.join(bl)}. ")
        if loc["loc_kind"] == "RETAILER":
            instr += f"Remove {held:,} units from shelves and back-store, segregate and tag 'RECALL — DO NOT SELL', confirm counts within 24 h."
        elif held > 0:
            instr += f"Place {held:,} units on QUARANTINE hold in WMS, block outbound picks, report on-hand counts within 12 h."
        else:
            instr += "Your records show all units were forwarded; confirm onward recipients and quantities within 12 h."
        notif[loc["loc_ref"]] = dict(location_kind=loc["loc_kind"], location_ref=loc["loc_ref"], location_name=loc["loc_name"],
                                     action_types=acts, units_expected=held, batches=bl, instruction=instr)
    log(f"Prepared {len(notif)} location notifications (simulated channel; nothing is sent before human approval).")

    # Near-miss exclusions: other batches of the same products that Db2 shows are NOT linked to the source
    product_ids = sorted({i.product_id for i in items} | {p["product_id"] for p in imp["products"]})
    excluded: list[ExcludedBatch] = []
    if product_ids:
        marks = ",".join("?" for _ in product_ids)
        others = db.query(f"SELECT batch_id, product_id FROM production_batches WHERE product_id IN ({marks}) ORDER BY batch_id", product_ids)
        for o in others:
            if o["batch_id"] not in batch_info:
                excluded.append(ExcludedBatch(batch_id=o["batch_id"], product_id=o["product_id"],
                                              reason=f"Same product, but Db2 genealogy shows no path from {src} to {o['batch_id']} — not recalled."))
    log(f"{len(excluded)} same-SKU batch(es) explicitly excluded (targeted recall instead of whole-product recall).")

    total = sum(i.quantity_units for i in items)
    title = f"{risk.recall_class.replace('_', ' ')} recall — {inc['contaminant']} in {src}"
    summary = (f"Recall {len({i.batch_id for i in items})} batches of {len({i.product_id for i in items})} products "
               f"({total:,} units) at {len({i.location_ref for i in items})} locations; "
               f"{sum(1 for i in items if i.priority == 'P1')} P1 actions. {len(excluded)} same-product batches excluded by genealogy.")
    plan = RecallPlan(recall_class=risk.recall_class, title=title, items=items,
                      notifications=[Notification(**n) for n in notif.values()], excluded_batches=excluded, total_units=total,
                      summary=summary, consumer_notice_recommended=risk.recall_class == "CLASS_I" and any(i.location_kind == "RETAILER" for i in items))
    plan.report_markdown = render_report(inc, inv, imp, risk, plan)
    return plan


def render_report(inc, inv, imp, risk, plan: RecallPlan) -> str:
    s = imp["summary"]
    lines = [
        f"# {plan.title}", "",
        f"**Incident:** {inc['incident_id']} — {inc['title']}  ",
        f"**Source:** {imp['source']['kind']} {imp['source']['ref']} · Supplier: {inv.supplier_name or 'n/a'}  ",
        f"**Risk:** {risk.score}/100 ({risk.classification}, confidence {risk.confidence}) · {plan.recall_class.replace('_', ' ')}  ",
        f"**Data engine:** {imp['engine']}", "",
        "## Findings", inv.summary, "",
        "## Scope (from Db2 recursive trace)",
        f"- {s['finished_batches']} finished batches / {s['products']} products / {s['units_produced']:,} units produced",
        f"- {s['warehouses']} warehouses, {s['distributors']} distributors, {s['retailers']} retailers, {s['cities']} cities",
        f"- {plan.total_units:,} units to recover or quarantine", "",
        "## Recall items",
        "| Pri | Batch | Product | Location | Units | Basis |", "|---|---|---|---|---:|---|",
    ]
    for i in sorted(plan.items, key=lambda x: (x.priority, x.location_ref)):
        lines.append(f"| {i.priority} | {i.batch_id} | {i.product_name} | {i.location_name} ({i.location_ref}) | {i.quantity_units:,} | {i.inclusion_basis} |")
    lines += ["", "## Traceability gaps (handled conservatively)"] + [f"- **{g['code']}** — {g['message']}" for g in imp["data_gaps"]]
    lines += ["", "## Excluded batches (same product, no genealogy link)"] + [f"- {e.batch_id} ({e.product_id})" for e in plan.excluded_batches]
    lines += ["", f"_{risk.disclaimer}_", "", "_AI-generated recommendation. Requires approval by an authorised recall manager. "
              "No notices are issued automatically; notifications in this system are simulated._"]
    return "\n".join(lines)


# ============================================================== 5. Verification
def verification_agent(db: Database, ctx: dict[str, Any], log: Log, plan: RecallPlan | None = None) -> VerificationReport:
    plan = plan or ctx["recall_plan"]
    inv, imp = ctx["investigation"], ctx["impact"]
    src = imp["source"]["ref"]
    checks: list[VerificationCheck] = []

    # 1. independent reverse-direction completeness check
    reverse = {r["batch_id"] for r in db.query(sql("verify_finished_descendants"), (src,))}
    if imp["source"]["kind"] == "BATCH" and imp["source"].get("batch_type") == "FINISHED":
        reverse.add(src)
    planned_batches = {i.batch_id for i in plan.items}
    finished_with_stock = {b["batch_id"] for b in imp["batches"] if b["batch_type"] == "FINISHED"}
    missing = sorted(reverse - finished_with_stock)
    missing_from_plan = sorted(reverse - planned_batches)
    log(f"Reverse (upstream-from-every-finished-batch) Db2 query found {len(reverse)} descendants of {src}.")
    checks.append(VerificationCheck(check="Forward trace == independent reverse trace", passed=not missing,
                                    severity="BLOCKER" if missing else "INFO",
                                    detail=f"Reverse query: {sorted(reverse)}" + (f"; MISSING from forward trace: {missing}" if missing else "")))
    checks.append(VerificationCheck(check="Every descendant finished batch has a recall item", passed=not missing_from_plan,
                                    severity="BLOCKER" if missing_from_plan else "INFO",
                                    detail="All covered" if not missing_from_plan else f"No recall item for {missing_from_plan} (no stock located — confirm disposition)"))

    # 2. every item's batch must descend from the source (per-item lineage query)
    extraneous = []
    for b in sorted(planned_batches):
        hits = 1 if b == src else int(db.query_one(sql("verify_batch_lineage"), (b, src))["hits"])
        if hits == 0:
            extraneous.append(b)
    checks.append(VerificationCheck(check="Every planned batch descends from the source (per-batch Db2 lineage query)",
                                    passed=not extraneous, severity="BLOCKER" if extraneous else "INFO",
                                    detail="All planned batches verified" if not extraneous else f"Unrelated batches in plan: {extraneous}"))

    # 3. every (batch, location) is backed by a shipment record or is the producing facility
    unsupported_items = []
    recip_cache: dict[str, set[str]] = {}
    for i in plan.items:
        if i.batch_id not in recip_cache:
            recip_cache[i.batch_id] = {r["dest_ref"] for r in db.query(sql("verify_direct_recipients"), (i.batch_id,))}
        fac = db.scalar("SELECT facility_id FROM production_batches WHERE batch_id = ?", (i.batch_id,))
        if i.location_ref not in recip_cache[i.batch_id] and i.location_ref != fac:
            unsupported_items.append(f"{i.batch_id}@{i.location_ref}")
    checks.append(VerificationCheck(check="Every batch-location item backed by a Db2 shipment record", passed=not unsupported_items,
                                    severity="BLOCKER" if unsupported_items else "INFO",
                                    detail=f"{len(plan.items)} items checked" + (f"; unsupported: {unsupported_items}" if unsupported_items else "")))

    # 4. non-recursive cross-check: any recipient of an affected batch missing from notifications?
    notified = {n.location_ref for n in plan.notifications}
    missed = []
    for b in sorted(reverse):
        for r in db.query(sql("verify_direct_recipients"), (b,)):
            if r["dest_ref"] not in notified:
                missed.append(f"{r['dest_ref']} ({b})")
    checks.append(VerificationCheck(check="All shipment recipients of affected batches are notified", passed=not missed,
                                    severity="BLOCKER" if missed else "INFO",
                                    detail="All recipients covered" if not missed else f"Not notified: {missed}"))

    # 5. quantity reconciliation per batch
    recon_issues = []
    for b in imp["batches"]:
        if b["batch_type"] != "FINISHED":
            continue
        located = sum(i.quantity_units for i in plan.items if i.batch_id == b["batch_id"])
        if located != int(b["quantity"]):
            recon_issues.append(f"{b['batch_id']}: produced {int(b['quantity']):,}, located {located:,}")
    checks.append(VerificationCheck(check="Units located reconcile to units produced", passed=not recon_issues,
                                    severity="WARNING" if recon_issues else "INFO",
                                    detail="All units accounted for" if not recon_issues else "; ".join(recon_issues)))

    # 6. unsupported claims: any ID in narrative text that does not exist in Db2
    narrative = " ".join([inv.summary, inv.hypothesis, plan.summary, plan.title] + [n.instruction for n in plan.notifications]
                         + [i.reason for i in plan.items] + [ctx.get("risk").narrative if ctx.get("risk") else ""])
    ids = set(ID_RE.findall(narrative))
    known = set()
    if ids:
        marks = ",".join("?" for _ in ids)
        known |= {r["lot_id"] for r in db.query(f"SELECT lot_id FROM ingredient_lots WHERE lot_id IN ({marks})", list(ids))}
        known |= {r["batch_id"] for r in db.query(f"SELECT batch_id FROM production_batches WHERE batch_id IN ({marks})", list(ids))}
    unsupported = sorted(ids - known)
    checks.append(VerificationCheck(check="No identifiers in narrative absent from Db2", passed=not unsupported,
                                    severity="BLOCKER" if unsupported else "INFO",
                                    detail=f"{len(ids)} identifiers checked" + (f"; unknown: {unsupported}" if unsupported else "")))

    # 7. evidence sufficiency & conflicts
    checks.append(VerificationCheck(check="Contamination confirmed by laboratory evidence", passed=inv.lab_confirmed,
                                    severity="INFO" if inv.lab_confirmed else "WARNING",
                                    detail="Positive result cited from uploaded report" if inv.lab_confirmed else "No positive lab result on file — recall would be precautionary"))
    checks.append(VerificationCheck(check="No conflicting evidence", passed=not inv.conflicts,
                                    severity="WARNING" if inv.conflicts else "INFO",
                                    detail="; ".join(c.topic for c in inv.conflicts) or "None"))
    gaps = imp["data_gaps"]
    checks.append(VerificationCheck(check="Traceability records complete", passed=not gaps,
                                    severity="WARNING" if gaps else "INFO",
                                    detail=f"{len(gaps)} gap(s): " + ", ".join(sorted({g['code'] for g in gaps})) if gaps else "Complete"))

    blockers = [c for c in checks if not c.passed and c.severity == "BLOCKER"]
    warnings = [c for c in checks if not c.passed and c.severity == "WARNING"]
    verdict = "FAIL" if blockers else "PASS_WITH_WARNINGS" if warnings else "PASS"
    reasons = ["Policy: every AI-generated recall plan requires approval by an authorised recall manager."]
    reasons += [f"{c.check}: {c.detail}" for c in blockers + warnings]
    for c in checks:
        log(f"  [{'PASS' if c.passed else c.severity}] {c.check} — {c.detail[:160]}")
    log(f"Verification verdict: {verdict}.")
    return VerificationReport(verdict=verdict, checks=checks, unsupported_claims=unsupported + unsupported_items,
                              missing_from_plan=missing_from_plan, extraneous_in_plan=extraneous, conflicts=inv.conflicts,
                              human_review_reasons=reasons, requires_human_review=True,
                              summary=f"{verdict}: {sum(c.passed for c in checks)}/{len(checks)} checks passed; "
                                      f"{len(blockers)} blocker(s), {len(warnings)} warning(s). Human approval required.")
