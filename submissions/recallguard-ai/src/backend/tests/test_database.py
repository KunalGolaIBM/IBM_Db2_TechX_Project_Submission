"""Schema, seed and referential-integrity tests."""
import pytest

from app.database import IntegrityViolation, db_status

TABLES = ["suppliers", "ingredients", "ingredient_lots", "manufacturing_facilities", "production_batches", "batch_transformations",
          "finished_products", "warehouses", "distributors", "retailers", "shipments", "shipment_items", "quality_reports",
          "contamination_incidents", "incident_affected_lots", "recall_campaigns", "recall_affected_items", "recall_actions",
          "agent_investigations", "audit_logs", "evidence_documents", "evidence_chunks", "incident_comments"]


def test_connection_status_is_honestly_labelled(db):
    st = db_status()
    assert st["connected"] is True
    if st["mode"] == "dev":
        assert st["is_ibm_db2"] is False
        assert "NOT IBM Db2" in st["warning"]


def test_all_tables_and_migrations_exist(db):
    for t in TABLES:
        assert db.table_exists(t), t
    applied = {r["version"] for r in db.query("SELECT version FROM schema_migrations")}
    assert {"001_core_schema.sql", "002_indexes.sql", "003_views.sql"} <= applied


@pytest.mark.parametrize("table,minimum", [("suppliers", 10), ("ingredient_lots", 20), ("production_batches", 30),
                                           ("finished_products", 15), ("warehouses", 8), ("retailers", 20), ("shipments", 50)])
def test_seed_volume_requirements(db, table, minimum):
    assert db.scalar(f"SELECT COUNT(*) AS n FROM {table}") >= minimum


def test_seed_has_no_orphans(db):
    orphans = db.scalar("SELECT COUNT(*) AS n FROM shipment_items si LEFT JOIN production_batches b ON b.batch_id = si.batch_id WHERE b.batch_id IS NULL")
    assert orphans == 0
    assert db.scalar("SELECT COUNT(*) AS n FROM batch_transformations WHERE input_ref = output_batch_id") == 0


def test_duplicate_genealogy_edge_rejected(db):
    with pytest.raises(IntegrityViolation):
        db.execute("INSERT INTO batch_transformations (transformation_id, input_kind, input_ref, input_lot_id, input_batch_id, output_batch_id, "
                   "quantity_used, quantity_unit, process_step, transformed_at) VALUES ('TR-DUP','LOT','TOM-2026-041','TOM-2026-041',NULL,"
                   "'PB-2026-1001',1,'KG','dup','2026-10-04 08:00:00')")


def test_self_loop_and_inconsistent_input_rejected(db):
    with pytest.raises(IntegrityViolation):
        db.execute("INSERT INTO batch_transformations (transformation_id, input_kind, input_ref, input_lot_id, input_batch_id, output_batch_id, "
                   "quantity_used, quantity_unit, process_step, transformed_at) VALUES ('TR-LOOP','BATCH','PB-2026-1001',NULL,'PB-2026-1001',"
                   "'PB-2026-1001',1,'KG','loop','2026-10-04 08:00:00')")
    with pytest.raises(IntegrityViolation):  # input_ref must mirror the populated FK
        db.execute("INSERT INTO batch_transformations (transformation_id, input_kind, input_ref, input_lot_id, input_batch_id, output_batch_id, "
                   "quantity_used, quantity_unit, process_step, transformed_at) VALUES ('TR-BAD','LOT','TOM-2026-042','TOM-2026-041',NULL,"
                   "'PB-2026-1030',1,'KG','bad','2026-10-04 08:00:00')")


def test_orphan_shipment_item_rejected(db):
    with pytest.raises(IntegrityViolation):
        db.execute("INSERT INTO shipment_items (shipment_id, batch_id, quantity_units) VALUES ('SHP-2026-0001','PB-DOES-NOT-EXIST',5)")


def test_shipment_polymorphic_check(db):
    with pytest.raises(IntegrityViolation):  # dest_kind RETAILER but retailer FK missing
        db.execute("INSERT INTO shipments (shipment_id, origin_kind, origin_ref, origin_facility_id, dest_kind, dest_ref, ship_date, "
                   "shipment_status) VALUES ('SHP-BAD','FACILITY','FAC-PUN','FAC-PUN','RETAILER','RTL-PUN-01','2026-10-10','DELIVERED')")


def test_parameterised_queries_are_injection_safe(db):
    rows = db.query("SELECT lot_id FROM ingredient_lots WHERE lot_id = ?", ("TOM-2026-041' OR '1'='1",))
    assert rows == []
