"""Supply-chain genealogy & impact analysis.

The relationship tracing is executed by IBM Db2 recursive SQL (db/queries/traceability.sql).
This module only executes those statements, records which queries ran (for
transparency in the UI), and shapes the rows into an impact report / graph.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from app.database import Database
from app.database.queries import sql

from .common import NotFound


class QueryLog:
    """Captures every Db2 statement executed for an analysis (name, rows, ms)."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.entries: list[dict[str, Any]] = []

    def run(self, name: str, params: tuple) -> list[dict[str, Any]]:
        t0 = time.perf_counter()
        rows = self.db.query(sql(name), params)
        self.entries.append({"query": name, "rows": len(rows), "ms": round((time.perf_counter() - t0) * 1000, 2),
                             "params": list(params)})
        return rows


def resolve_node(db: Database, ref: str) -> dict[str, Any]:
    ref = ref.strip().upper()
    lot = db.query_one(
        "SELECT l.lot_id, l.ingredient_id, i.ingredient_name, l.supplier_id, s.supplier_name, s.country, s.certification, "
        "l.facility_id, l.quantity_kg, l.received_date, l.expiry_date, l.coa_reference, l.lot_status "
        "FROM ingredient_lots l JOIN ingredients i ON i.ingredient_id = l.ingredient_id "
        "JOIN suppliers s ON s.supplier_id = l.supplier_id WHERE l.lot_id = ?", (ref,))
    if lot:
        return {"kind": "LOT", "ref": ref, **lot}
    batch = db.query_one(
        "SELECT b.batch_id, b.batch_type, b.product_id, p.product_name, b.description, b.quantity, b.quantity_unit, "
        "b.production_date, b.facility_id, f.facility_name, b.batch_status "
        "FROM production_batches b JOIN manufacturing_facilities f ON f.facility_id = b.facility_id "
        "LEFT JOIN finished_products p ON p.product_id = b.product_id WHERE b.batch_id = ?", (ref,))
    if batch:
        return {"kind": "BATCH", "ref": ref, **batch}
    raise NotFound(f"No ingredient lot or production batch with id '{ref}'")


def impact_analysis(db: Database, source_ref: str) -> dict[str, Any]:
    source = resolve_node(db, source_ref)
    ref = source["ref"]
    ql = QueryLog(db)
    batches = ql.run("impact_batches", (ref, ref))
    hops = ql.run("impact_hops", (ref, ref))
    balance = ql.run("impact_location_balance", (ref, ref))
    unverified = ql.run("impact_unverified_edges", (ref, ref, ref))
    intermediates = ql.run("impact_intermediate_balance", (ref, ref))
    lot_use = ql.run("lot_consumption", (ref,)) if source["kind"] == "LOT" else []
    edges = ql.run("downstream_genealogy", (ref,))

    for b in batches:
        if b["batch_id"] == ref:
            b["relation"] = "SOURCE"
        else:
            b["relation"] = "DIRECT" if b["depth"] == 1 else "INDIRECT"
    unverified_outputs = {e["output_batch_id"] for e in unverified}
    # a batch is "uncertain" if every path to it relies on an unverified record; here we flag any batch fed by one
    for b in batches:
        b["uncertain_link"] = b["batch_id"] in unverified_outputs

    finished = [b for b in batches if b["batch_type"] == "FINISHED"]
    products: dict[str, dict[str, Any]] = {}
    for b in finished:
        p = products.setdefault(b["product_id"], {
            "product_id": b["product_id"], "product_name": b["product_name"], "brand": b["brand"],
            "unit_size": b["unit_size"], "gtin": b["gtin"], "batches": [], "units_produced": 0})
        p["batches"].append(b["batch_id"])
        p["units_produced"] += int(b["quantity"])

    # --- aggregate per location ------------------------------------------------
    locs: dict[str, dict[str, Any]] = {}
    for r in balance:
        loc = locs.setdefault(r["loc_ref"], {"loc_kind": r["loc_kind"], "loc_ref": r["loc_ref"], "loc_name": r["loc_name"],
                                              "city": r["city"], "batches": [], "units_received": 0, "units_held": 0,
                                              "units_in_transit": 0})
        loc["batches"].append({"batch_id": r["batch_id"], "units_in": r["units_in"], "units_out": r["units_out"],
                               "units_held": r["units_held"], "in_transit_units": r["in_transit_units"]})
        loc["units_received"] += r["units_in"]
        loc["units_held"] += r["units_held"]
        loc["units_in_transit"] += r["in_transit_units"]
    batch_product = {b["batch_id"]: b["product_id"] for b in finished}
    for loc in locs.values():
        loc["products"] = sorted({batch_product.get(x["batch_id"]) for x in loc["batches"] if batch_product.get(x["batch_id"])})

    # --- data gaps (never treated as "safe") ------------------------------------
    gaps: list[dict[str, Any]] = []
    for e in unverified:
        gaps.append({"code": "UNVERIFIED_TRANSFORMATION", "severity": "HIGH", "refs": [e["transformation_id"], e["input_ref"], e["output_batch_id"]],
                     "message": f"Genealogy link {e['input_ref']} -> {e['output_batch_id']} ({e['quantity_used']} {e['quantity_unit']}) is "
                                f"{e['record_status']} ('{e['process_step']}'). Batch kept IN scope conservatively until the record is verified."})
    for r in intermediates:
        diff = float(r["quantity"]) - float(r["consumed"])
        if diff > 0.5:
            gaps.append({"code": "INTERMEDIATE_UNACCOUNTED", "severity": "HIGH", "refs": [r["batch_id"]],
                         "message": f"{r['batch_id']} ({r['description']}) produced {r['quantity']} {r['quantity_unit']} but only "
                                    f"{r['consumed']} {r['quantity_unit']} is recorded as consumed — {round(diff, 2)} {r['quantity_unit']} unaccounted "
                                    f"(possible unrecorded use or remaining stock). Quarantine remaining stock and reconcile."})
    for r in lot_use:
        diff = float(r["quantity_kg"]) - float(r["consumed_kg"])
        if diff > 0.5:
            gaps.append({"code": "SOURCE_LOT_REMAINDER", "severity": "MEDIUM", "refs": [r["lot_id"]],
                         "message": f"{r['lot_id']}: {r['quantity_kg']} kg received, {r['consumed_kg']} kg recorded in production — "
                                    f"{round(diff, 2)} kg not linked to any batch. Treat as potentially still in inventory at {r['facility_id']}."})
    for loc in locs.values():
        for x in loc["batches"]:
            if loc["loc_kind"] == "DISTRIBUTOR" and x["units_held"] > 0 and x["in_transit_units"] == 0:
                gaps.append({"code": "DISTRIBUTION_DEAD_END", "severity": "HIGH", "refs": [loc["loc_ref"], x["batch_id"]],
                             "message": f"{loc['loc_name']} ({loc['loc_ref']}) received {x['units_in']} units of {x['batch_id']} with no onward "
                                        f"shipment records. Downstream retailers are UNKNOWN — escalate for distributor records."})
            if x["in_transit_units"] > 0:
                gaps.append({"code": "IN_TRANSIT", "severity": "MEDIUM", "refs": [loc["loc_ref"], x["batch_id"]],
                             "message": f"{x['in_transit_units']} units of {x['batch_id']} are in transit to {loc['loc_name']} ({loc['loc_ref']}). "
                                        f"Intercept shipment before delivery."})
    shipped = {h["batch_id"] for h in hops}
    for b in finished:
        if b["batch_id"] not in shipped:
            gaps.append({"code": "NO_DISTRIBUTION_RECORDS", "severity": "MEDIUM", "refs": [b["batch_id"]],
                         "message": f"No shipment records found for finished batch {b['batch_id']}; location of stock must be confirmed."})

    by_kind = defaultdict(list)
    for loc in locs.values():
        by_kind[loc["loc_kind"]].append(loc)

    summary = {
        "batches_total": len(batches),
        "batches_direct": sum(1 for b in batches if b["relation"] == "DIRECT"),
        "batches_indirect": sum(1 for b in batches if b["relation"] == "INDIRECT"),
        "finished_batches": len(finished),
        "intermediate_batches": sum(1 for b in batches if b["batch_type"] == "INTERMEDIATE"),
        "products": len(products),
        "units_produced": sum(int(b["quantity"]) for b in finished),
        "units_at_retail": sum(l["units_held"] for l in by_kind["RETAILER"]),
        "units_in_supply_chain": sum(l["units_held"] for k in ("FACILITY", "WAREHOUSE", "DISTRIBUTOR") for l in by_kind[k]),
        "units_in_transit": sum(l["units_in_transit"] for l in locs.values()),
        "shipments": len({h["shipment_id"] for h in hops}),
        "facilities": len(by_kind["FACILITY"]),
        "warehouses": len(by_kind["WAREHOUSE"]),
        "distributors": len(by_kind["DISTRIBUTOR"]),
        "retailers": len(by_kind["RETAILER"]),
        "cities": len({l["city"] for l in locs.values() if l["city"]}),
        "data_gaps": len(gaps),
        "max_depth": max((b["depth"] for b in batches), default=0),
    }
    return {
        "source": source,
        "batches": batches,
        "products": sorted(products.values(), key=lambda p: p["product_id"]),
        "hops": hops,
        "edges": [{"parent_ref": e["parent_ref"], "node_ref": e["node_ref"], "depth": e["depth"],
                   "record_status": e["record_status"], "quantity_used": e["quantity_used"],
                   "quantity_unit": e["quantity_unit"], "process_step": e["process_step"]} for e in edges],
        "locations": sorted(locs.values(), key=lambda l: (["FACILITY", "WAREHOUSE", "DISTRIBUTOR", "RETAILER"].index(l["loc_kind"]), l["loc_ref"])),
        "data_gaps": gaps,
        "summary": summary,
        "queries": ql.entries,
        "engine": db.label,
    }


# ------------------------------------------------------------------ graph view
def trace_graph(db: Database, ref: str, affected_refs: set[str] | None = None) -> dict[str, Any]:
    """Nodes/edges for the React Flow explorer: upstream + downstream + distribution."""
    node = resolve_node(db, ref)
    ref = node["ref"]
    ql = QueryLog(db)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}

    def add_node(nid: str, ntype: str, label: str, layer: int, **data: Any) -> None:
        cur = nodes.get(nid)
        if cur is None or layer > cur["layer"]:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, "layer": layer, **data}

    def add_edge(src: str, dst: str, kind: str, label: str = "", **data: Any) -> None:
        key = (src, dst)
        if key in edges:
            e = edges[key]
            if data.get("units"):
                e["units"] = e.get("units", 0) + data["units"]
                e["label"] = f"{e['units']:,} u"
            for bid in data.get("batches", []):
                if bid not in e.setdefault("batches", []):
                    e["batches"].append(bid)
            return
        edges[key] = {"id": f"{src}->{dst}", "source": src, "target": dst, "kind": kind, "label": label, **data}

    # upstream (only meaningful for a batch)
    if node["kind"] == "BATCH":
        up = ql.run("upstream_genealogy", (ref,))
        max_d = max((r["depth"] for r in up), default=0)
        for r in up:
            layer = 1 + (max_d - r["depth"])
            if r["node_kind"] == "LOT":
                add_node(r["node_ref"], "lot", r["node_ref"], layer, subtitle=r["ingredient_name"], supplier=r["supplier_name"])
                if r["supplier_id"]:
                    add_node(r["supplier_id"], "supplier", r["supplier_name"], layer - 1, subtitle=r["supplier_id"])
                    add_edge(r["supplier_id"], r["node_ref"], "supplies")
            else:
                add_node(r["node_ref"], "intermediate", r["node_ref"], layer, subtitle=r["batch_description"])
            add_edge(r["node_ref"], r["child_ref"], "transform", f"{r['quantity_used']:g} {r['quantity_unit']}",
                     record_status=r["record_status"], process_step=r["process_step"])
        base = max_d + 1
        add_node(ref, "finished" if node["batch_type"] == "FINISHED" else "intermediate", ref, base,
                 subtitle=node.get("product_name") or node.get("description"), focus=True)
    else:
        add_node(node["supplier_id"], "supplier", node["supplier_name"], 0, subtitle=node["supplier_id"])
        add_node(ref, "lot", ref, 1, subtitle=node["ingredient_name"], supplier=node["supplier_name"], focus=True)
        add_edge(node["supplier_id"], ref, "supplies")
        base = 1

    down = ql.run("downstream_genealogy", (ref,))
    for r in down:
        ntype = "finished" if r["batch_type"] == "FINISHED" else "intermediate"
        add_node(r["node_ref"], ntype, r["node_ref"], base + r["depth"],
                 subtitle=r["product_name"] or r["description"], product_id=r["product_id"])
        add_edge(r["parent_ref"], r["node_ref"], "transform", f"{r['quantity_used']:g} {r['quantity_unit']}",
                 record_status=r["record_status"], process_step=r["process_step"])

    batch_layer = max((n["layer"] for n in nodes.values()), default=1)
    hops = ql.run("impact_hops", (ref, ref))
    for h in hops:
        src = h["batch_id"] if h["origin_kind"] == "FACILITY" else h["origin_ref"]
        ltype = h["dest_kind"].lower()
        add_node(h["dest_ref"], ltype, h["dest_name"] or h["dest_ref"], batch_layer + h["hop"], subtitle=h["dest_city"])
        add_edge(src, h["dest_ref"], "ship", f"{h['units']:,} u", units=h["units"], batches=[h["batch_id"]],
                 status=h["shipment_status"])

    affected_refs = affected_refs or set()
    for n in nodes.values():
        n["affected"] = n["id"] in affected_refs
    for e in edges.values():
        e["affected"] = e["source"] in affected_refs and e["target"] in affected_refs
    return {"root": node, "nodes": list(nodes.values()), "edges": list(edges.values()), "queries": ql.entries,
            "engine": db.label}


def affected_set(db: Database, source_ref: str) -> set[str]:
    """Every node id (lot, batches, locations, supplier) in the impact of a source."""
    ref = source_ref.upper()
    out = {ref}
    for r in db.query(sql("impact_batches"), (ref, ref)):
        out.add(r["batch_id"])
    for h in db.query(sql("impact_hops"), (ref, ref)):
        out.add(h["dest_ref"])
    return out


def lineage_path(edges: list[dict[str, Any]], source_ref: str, batch_id: str) -> list[str]:
    """Shortest source -> batch path through the Db2-returned genealogy edges."""
    if batch_id == source_ref:
        return [source_ref]
    parents: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        parents[e["node_ref"]].append(e["parent_ref"])
    frontier, seen = [[batch_id]], {batch_id}
    while frontier:
        nxt = []
        for path in frontier:
            for p in parents.get(path[0], []):
                if p == source_ref:
                    return [p] + path
                if p not in seen:
                    seen.add(p)
                    nxt.append([p] + path)
        frontier = nxt
    return [batch_id]
