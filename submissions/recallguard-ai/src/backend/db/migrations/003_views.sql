-- =====================================================================
-- RecallGuard AI — directory view (migration 003)
-- One row per physical location in the supply chain, so trace queries can
-- resolve a (kind, ref) pair to a human-readable name with a single join.
-- =====================================================================

CREATE VIEW v_locations (loc_kind, loc_ref, loc_name, city) AS
    SELECT CAST('FACILITY' AS VARCHAR(12)), facility_id, facility_name, city FROM manufacturing_facilities
    UNION ALL
    SELECT CAST('WAREHOUSE' AS VARCHAR(12)), warehouse_id, warehouse_name, city FROM warehouses
    UNION ALL
    SELECT CAST('DISTRIBUTOR' AS VARCHAR(12)), distributor_id, distributor_name, city FROM distributors
    UNION ALL
    SELECT CAST('RETAILER' AS VARCHAR(12)), retailer_id, retailer_name, city FROM retailers
