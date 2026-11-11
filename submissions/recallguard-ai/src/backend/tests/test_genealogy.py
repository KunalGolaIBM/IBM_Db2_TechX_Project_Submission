"""Critical acceptance tests for Db2 recursive genealogy & impact analysis.

Expected values are written by hand from the seed design (db/seed/generate_seed.py),
independent of the code under test.
"""
from app.database.queries import sql
from app.services.traceability import impact_analysis, lineage_path, trace_graph

TOM_BATCHES = {"PB-2026-1001", "PB-2026-1002", "PB-2026-1003", "PB-2026-1004", "PB-2026-1005", "PB-2026-1006",
               "PB-2026-1007", "PB-2026-1008", "PB-2026-1009"}
TOM_FINISHED = TOM_BATCHES - {"PB-2026-1001", "PB-2026-1003"}
TOM_PRODUCTS = {"P-PSC", "P-MAR", "P-PZS", "P-PTM", "P-TSP", "P-DAL"}
TOM_RETAILERS = {"RTL-PUN-01", "RTL-PUN-02", "RTL-PUN-03", "RTL-PUN-04", "RTL-PUN-05", "RTL-MUM-01", "RTL-MUM-02", "RTL-MUM-03",
                 "RTL-MUM-04", "RTL-NSK-01", "RTL-HYD-01", "RTL-HYD-02", "RTL-HYD-03", "RTL-HYD-04", "RTL-DEL-01", "RTL-DEL-02",
                 "RTL-DEL-03", "RTL-KOL-01", "RTL-KOL-02"}
TOM_WAREHOUSES = {"WH-PUN1", "WH-MUM1", "WH-HYD1", "WH-NSK1", "WH-DEL1", "WH-KOL1"}
TOM_DISTRIBUTORS = {"DST-01", "DST-02", "DST-03", "DST-05"}
NEAR_MISS = {"PB-2026-0950", "PB-2026-0951", "PB-2026-1010", "PB-2026-1011", "PB-2026-1012", "PB-2026-1013", "PB-2026-1040"}


def _locs(imp, kind):
    return {l["loc_ref"] for l in imp["locations"] if l["loc_kind"] == kind}


def test_tom_2026_041_full_downstream_impact(db):
    imp = impact_analysis(db, "TOM-2026-041")
    assert {b["batch_id"] for b in imp["batches"]} == TOM_BATCHES
    assert {b["batch_id"] for b in imp["batches"] if b["batch_type"] == "FINISHED"} == TOM_FINISHED
    assert {p["product_id"] for p in imp["products"]} == TOM_PRODUCTS
    assert _locs(imp, "RETAILER") == TOM_RETAILERS
    assert _locs(imp, "WAREHOUSE") == TOM_WAREHOUSES
    assert _locs(imp, "DISTRIBUTOR") == TOM_DISTRIBUTORS
    assert imp["source"]["supplier_id"] == "SUP-001"
    assert imp["summary"]["max_depth"] == 3


def test_direct_vs_indirect_classification(db):
    imp = impact_analysis(db, "TOM-2026-041")
    rel = {b["batch_id"]: b["relation"] for b in imp["batches"]}
    assert rel["PB-2026-1001"] == "DIRECT" and rel["PB-2026-1002"] == "DIRECT"
    assert rel["PB-2026-1007"] == "INDIRECT" and rel["PB-2026-1009"] == "INDIRECT"


def test_near_miss_batches_never_included(db):
    imp = impact_analysis(db, "TOM-2026-041")
    ids = {b["batch_id"] for b in imp["batches"]}
    assert ids.isdisjoint(NEAR_MISS)
    assert all(h["batch_id"] in TOM_BATCHES for h in imp["hops"])


def test_unrelated_batch_has_no_tomato_products(db):
    imp = impact_analysis(db, "PB-2026-1030")  # butter biscuits
    assert {b["batch_id"] for b in imp["batches"]} == {"PB-2026-1030"}
    assert {p["product_id"] for p in imp["products"]} == {"P-BIS"}
    assert _locs(imp, "RETAILER").isdisjoint(TOM_RETAILERS)


def test_data_gaps_are_flagged_conservatively(db):
    imp = impact_analysis(db, "TOM-2026-041")
    codes = {g["code"] for g in imp["data_gaps"]}
    assert {"UNVERIFIED_TRANSFORMATION", "INTERMEDIATE_UNACCOUNTED", "DISTRIBUTION_DEAD_END", "IN_TRANSIT", "SOURCE_LOT_REMAINDER"} <= codes
    # the batch reached only through an UNVERIFIED record is still in scope
    assert "PB-2026-1006" in {b["batch_id"] for b in imp["batches"]}


def test_units_conserved_per_batch(db):
    imp = impact_analysis(db, "TOM-2026-041")
    for b in imp["batches"]:
        if b["batch_type"] != "FINISHED":
            continue
        held = sum(x["units_held"] for l in imp["locations"] for x in l["batches"] if x["batch_id"] == b["batch_id"])
        assert held == b["quantity"], b["batch_id"]


def test_upstream_trace_reaches_contaminated_lot_and_supplier(db):
    rows = db.query(sql("upstream_genealogy"), ("PB-2026-1007",))
    refs = {r["node_ref"] for r in rows}
    assert {"PB-2026-1003", "PB-2026-1001", "TOM-2026-041"} <= refs
    assert "SUP-001" in {r["supplier_id"] for r in rows if r["supplier_id"]}


def test_reverse_query_matches_forward_trace(db):
    rev = {r["batch_id"] for r in db.query(sql("verify_finished_descendants"), ("TOM-2026-041",))}
    assert rev == TOM_FINISHED


def test_lineage_path(db):
    imp = impact_analysis(db, "TOM-2026-041")
    assert lineage_path(imp["edges"], "TOM-2026-041", "PB-2026-1007") == ["TOM-2026-041", "PB-2026-1001", "PB-2026-1003", "PB-2026-1007"]


def test_trace_graph_highlights_affected_nodes(db):
    g = trace_graph(db, "PB-2026-1004", {"PB-2026-1004", "RTL-PUN-01"})
    ids = {n["id"] for n in g["nodes"]}
    assert {"TOM-2026-041", "SUP-001", "PB-2026-1001", "RTL-HYD-01"} <= ids
    assert next(n for n in g["nodes"] if n["id"] == "PB-2026-1004")["affected"] is True
    assert any(e["kind"] == "ship" for e in g["edges"])
