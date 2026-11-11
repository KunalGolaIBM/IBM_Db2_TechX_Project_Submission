-- =====================================================================
-- RecallGuard AI — authoritative traceability queries (IBM Db2 SQL)
--
-- These recursive common table expressions ARE the genealogy engine: the
-- Python layer never walks the graph itself, it only executes these
-- statements and shapes the result sets. All values arrive through '?'
-- parameter markers (no string interpolation of user input).
--
-- Db2 notes
--  * Db2 has no RECURSIVE keyword: a CTE that references itself is recursive.
--  * Every column of a recursive CTE is CAST in BOTH the initialisation and
--    the recursive fullselect so the data types/lengths match exactly
--    (avoids SQL0344N / SQL0373N).
--  * Each recursive leg carries a depth counter with an explicit bound, which
--    terminates recursion and suppresses SQL0347W.
--
-- Files are parsed by app/database/queries.py: each block starts with
-- "-- name: <query_name>" and may include the shared fragment {{IMPACT_CTES}}.
-- =====================================================================

-- name: IMPACT_CTES
-- Shared fragment. Params: (start_ref, start_ref)
--   seeds            -> the start batch itself (if the start is a batch) and
--                       every batch that directly consumed the start node
--   genealogy        -> recursive downstream walk over batch_transformations
--   affected_batches -> distinct set of every batch derived from the source
--   flow             -> recursive walk of the physical distribution network:
--                       first leg leaves the producing facility, each
--                       further leg leaves the previous destination on or
--                       after the arrival date, for the SAME batch
--   hops             -> de-duplicated shipment legs
WITH seeds (node_ref) AS (
    SELECT batch_id FROM production_batches WHERE batch_id = ?
    UNION ALL
    SELECT output_batch_id FROM batch_transformations WHERE input_ref = ?
),
genealogy (node_ref, depth) AS (
    SELECT CAST(node_ref AS VARCHAR(30)), 1 FROM seeds
    UNION ALL
    SELECT CAST(t.output_batch_id AS VARCHAR(30)), g.depth + 1
    FROM genealogy g
    JOIN batch_transformations t ON t.input_ref = g.node_ref
    WHERE g.depth < 12
),
affected_batches (batch_id) AS (
    SELECT DISTINCT node_ref FROM genealogy
),
flow (batch_id, shipment_id, origin_kind, origin_ref, dest_kind, dest_ref, ship_date, shipment_status, units, hop) AS (
    SELECT CAST(si.batch_id AS VARCHAR(30)), CAST(s.shipment_id AS VARCHAR(30)),
           CAST(s.origin_kind AS VARCHAR(12)), CAST(s.origin_ref AS VARCHAR(20)),
           CAST(s.dest_kind AS VARCHAR(12)), CAST(s.dest_ref AS VARCHAR(20)),
           s.ship_date, CAST(s.shipment_status AS VARCHAR(12)), si.quantity_units, 1
    FROM affected_batches a
    JOIN shipment_items si ON si.batch_id = a.batch_id
    JOIN shipments s ON s.shipment_id = si.shipment_id
    WHERE s.origin_kind = 'FACILITY'
    UNION ALL
    SELECT CAST(si.batch_id AS VARCHAR(30)), CAST(s.shipment_id AS VARCHAR(30)),
           CAST(s.origin_kind AS VARCHAR(12)), CAST(s.origin_ref AS VARCHAR(20)),
           CAST(s.dest_kind AS VARCHAR(12)), CAST(s.dest_ref AS VARCHAR(20)),
           s.ship_date, CAST(s.shipment_status AS VARCHAR(12)), si.quantity_units, f.hop + 1
    FROM flow f
    JOIN shipments s ON s.origin_ref = f.dest_ref AND s.ship_date >= f.ship_date
    JOIN shipment_items si ON si.shipment_id = s.shipment_id AND si.batch_id = f.batch_id
    WHERE f.hop < 8
),
hops (batch_id, shipment_id, origin_kind, origin_ref, dest_kind, dest_ref, ship_date, shipment_status, units, hop) AS (
    SELECT batch_id, shipment_id, origin_kind, origin_ref, dest_kind, dest_ref, ship_date, shipment_status, units, MIN(hop)
    FROM flow
    GROUP BY batch_id, shipment_id, origin_kind, origin_ref, dest_kind, dest_ref, ship_date, shipment_status, units
)

-- name: downstream_genealogy
-- Every genealogy EDGE below a lot or batch (used for the graph view).
-- Params: (start_ref)
WITH genealogy (node_ref, parent_ref, depth, process_step, record_status, quantity_used, quantity_unit) AS (
    SELECT CAST(t.output_batch_id AS VARCHAR(30)), CAST(t.input_ref AS VARCHAR(30)), 1,
           CAST(t.process_step AS VARCHAR(80)), CAST(t.record_status AS VARCHAR(12)),
           t.quantity_used, CAST(t.quantity_unit AS VARCHAR(10))
    FROM batch_transformations t
    WHERE t.input_ref = ?
    UNION ALL
    SELECT CAST(t.output_batch_id AS VARCHAR(30)), CAST(t.input_ref AS VARCHAR(30)), g.depth + 1,
           CAST(t.process_step AS VARCHAR(80)), CAST(t.record_status AS VARCHAR(12)),
           t.quantity_used, CAST(t.quantity_unit AS VARCHAR(10))
    FROM genealogy g
    JOIN batch_transformations t ON t.input_ref = g.node_ref
    WHERE g.depth < 12
)
SELECT DISTINCT g.node_ref, g.parent_ref, g.depth, g.process_step, g.record_status,
       g.quantity_used, g.quantity_unit,
       b.batch_type, b.product_id, b.description, b.quantity, b.quantity_unit AS batch_unit,
       b.production_date, b.batch_status, b.facility_id, p.product_name
FROM genealogy g
JOIN production_batches b ON b.batch_id = g.node_ref
LEFT JOIN finished_products p ON p.product_id = b.product_id
ORDER BY g.depth, g.node_ref

-- name: upstream_genealogy
-- Every ancestor of a batch: intermediate batches and the ingredient lots and
-- suppliers at the root. Params: (batch_id)
WITH ancestry (node_ref, node_kind, child_ref, depth, process_step, record_status, quantity_used, quantity_unit) AS (
    SELECT CAST(t.input_ref AS VARCHAR(30)), CAST(t.input_kind AS VARCHAR(5)), CAST(t.output_batch_id AS VARCHAR(30)), 1,
           CAST(t.process_step AS VARCHAR(80)), CAST(t.record_status AS VARCHAR(12)),
           t.quantity_used, CAST(t.quantity_unit AS VARCHAR(10))
    FROM batch_transformations t
    WHERE t.output_batch_id = ?
    UNION ALL
    SELECT CAST(t.input_ref AS VARCHAR(30)), CAST(t.input_kind AS VARCHAR(5)), CAST(t.output_batch_id AS VARCHAR(30)), a.depth + 1,
           CAST(t.process_step AS VARCHAR(80)), CAST(t.record_status AS VARCHAR(12)),
           t.quantity_used, CAST(t.quantity_unit AS VARCHAR(10))
    FROM ancestry a
    JOIN batch_transformations t ON t.output_batch_id = a.node_ref
    WHERE a.node_kind = 'BATCH' AND a.depth < 12
)
SELECT DISTINCT a.node_ref, a.node_kind, a.child_ref, a.depth, a.process_step, a.record_status,
       a.quantity_used, a.quantity_unit,
       l.supplier_id, s.supplier_name, l.ingredient_id, i.ingredient_name, l.received_date,
       b.description AS batch_description, b.batch_type
FROM ancestry a
LEFT JOIN ingredient_lots l ON a.node_kind = 'LOT' AND l.lot_id = a.node_ref
LEFT JOIN suppliers s ON s.supplier_id = l.supplier_id
LEFT JOIN ingredients i ON i.ingredient_id = l.ingredient_id
LEFT JOIN production_batches b ON a.node_kind = 'BATCH' AND b.batch_id = a.node_ref
ORDER BY a.depth, a.node_ref

-- name: impact_batches
-- All batches derived from the source, with minimum genealogy depth.
-- Params: (start_ref, start_ref)
{{IMPACT_CTES}}
SELECT b.batch_id, b.batch_type, b.product_id, b.description, b.quantity, b.quantity_unit,
       b.production_date, b.best_before, b.batch_status, b.facility_id,
       p.product_name, p.brand, p.unit_size, p.gtin,
       (SELECT MIN(g.depth) FROM genealogy g WHERE g.node_ref = b.batch_id) AS depth
FROM affected_batches a
JOIN production_batches b ON b.batch_id = a.batch_id
LEFT JOIN finished_products p ON p.product_id = b.product_id
ORDER BY depth, b.batch_id

-- name: impact_hops
-- Every shipment leg that carried an affected batch. Params: (start_ref, start_ref)
{{IMPACT_CTES}}
SELECT h.batch_id, h.shipment_id, h.origin_kind, h.origin_ref, h.dest_kind, h.dest_ref,
       h.ship_date, h.shipment_status, h.units, h.hop,
       vo.loc_name AS origin_name, vd.loc_name AS dest_name, vd.city AS dest_city
FROM hops h
LEFT JOIN v_locations vo ON vo.loc_ref = h.origin_ref
LEFT JOIN v_locations vd ON vd.loc_ref = h.dest_ref
ORDER BY h.ship_date, h.shipment_id, h.batch_id

-- name: impact_location_balance
-- Net units of each affected batch at each location (received - forwarded).
-- Facility rows: produced quantity of FINISHED batches - units shipped out.
-- Params: (start_ref, start_ref)
{{IMPACT_CTES}},
inbound (batch_id, loc_kind, loc_ref, units_in, delivered_units, in_transit_units) AS (
    SELECT batch_id, dest_kind, dest_ref, SUM(units),
           SUM(CASE WHEN shipment_status = 'DELIVERED' THEN units ELSE 0 END),
           SUM(CASE WHEN shipment_status = 'IN_TRANSIT' THEN units ELSE 0 END)
    FROM hops GROUP BY batch_id, dest_kind, dest_ref
),
outbound (batch_id, loc_ref, units_out) AS (
    SELECT batch_id, origin_ref, SUM(units) FROM hops GROUP BY batch_id, origin_ref
)
SELECT i.batch_id, i.loc_kind, i.loc_ref, v.loc_name, v.city,
       i.units_in, i.delivered_units, i.in_transit_units,
       COALESCE(o.units_out, 0) AS units_out,
       i.units_in - COALESCE(o.units_out, 0) AS units_held
FROM inbound i
LEFT JOIN outbound o ON o.batch_id = i.batch_id AND o.loc_ref = i.loc_ref
LEFT JOIN v_locations v ON v.loc_ref = i.loc_ref
UNION ALL
SELECT b.batch_id, CAST('FACILITY' AS VARCHAR(12)), b.facility_id, v.loc_name, v.city,
       CAST(b.quantity AS INTEGER), CAST(b.quantity AS INTEGER), 0,
       COALESCE(o.units_out, 0),
       CAST(b.quantity AS INTEGER) - COALESCE(o.units_out, 0)
FROM affected_batches a
JOIN production_batches b ON b.batch_id = a.batch_id AND b.batch_type = 'FINISHED'
LEFT JOIN outbound o ON o.batch_id = b.batch_id AND o.loc_ref = b.facility_id
LEFT JOIN v_locations v ON v.loc_ref = b.facility_id

-- name: impact_unverified_edges
-- Transformation records on the contamination path that are not VERIFIED.
-- Params: (start_ref, start_ref, start_ref)
{{IMPACT_CTES}}
SELECT t.transformation_id, t.input_ref, t.output_batch_id, t.quantity_used, t.quantity_unit,
       t.process_step, t.record_status
FROM batch_transformations t
WHERE t.record_status <> 'VERIFIED'
  AND (t.input_ref = ? OR t.input_ref IN (SELECT batch_id FROM affected_batches))
ORDER BY t.transformation_id

-- name: impact_intermediate_balance
-- Intermediate batches on the path whose produced quantity is not fully
-- accounted for by downstream consumption records. Params: (start_ref, start_ref)
{{IMPACT_CTES}}
SELECT b.batch_id, b.description, b.quantity, b.quantity_unit,
       COALESCE(SUM(t.quantity_used), 0) AS consumed
FROM affected_batches a
JOIN production_batches b ON b.batch_id = a.batch_id AND b.batch_type = 'INTERMEDIATE'
LEFT JOIN batch_transformations t ON t.input_ref = b.batch_id
GROUP BY b.batch_id, b.description, b.quantity, b.quantity_unit
ORDER BY b.batch_id

-- name: lot_consumption
-- How much of an ingredient lot is accounted for by production records.
-- Params: (lot_id)
SELECT l.lot_id, l.quantity_kg, l.lot_status, l.received_date, l.supplier_id, s.supplier_name,
       l.ingredient_id, i.ingredient_name, l.facility_id, l.coa_reference,
       COALESCE(SUM(t.quantity_used), 0) AS consumed_kg
FROM ingredient_lots l
JOIN suppliers s ON s.supplier_id = l.supplier_id
JOIN ingredients i ON i.ingredient_id = l.ingredient_id
LEFT JOIN batch_transformations t ON t.input_lot_id = l.lot_id
WHERE l.lot_id = ?
GROUP BY l.lot_id, l.quantity_kg, l.lot_status, l.received_date, l.supplier_id, s.supplier_name,
         l.ingredient_id, i.ingredient_name, l.facility_id, l.coa_reference

-- name: verify_finished_descendants
-- INDEPENDENT reverse-direction check used by the Verification Agent:
-- start from EVERY finished batch, walk UPSTREAM, keep those whose ancestry
-- contains the source. Must equal the forward-trace result.
-- Params: (source_ref)
WITH ancestry (batch_id, node_ref, depth) AS (
    SELECT CAST(b.batch_id AS VARCHAR(30)), CAST(t.input_ref AS VARCHAR(30)), 1
    FROM production_batches b
    JOIN batch_transformations t ON t.output_batch_id = b.batch_id
    WHERE b.batch_type = 'FINISHED'
    UNION ALL
    SELECT CAST(a.batch_id AS VARCHAR(30)), CAST(t.input_ref AS VARCHAR(30)), a.depth + 1
    FROM ancestry a
    JOIN batch_transformations t ON t.output_batch_id = a.node_ref
    WHERE a.depth < 12
)
SELECT DISTINCT batch_id FROM ancestry WHERE node_ref = ?
ORDER BY batch_id

-- name: verify_batch_lineage
-- Does batch X descend from source S? (upstream walk from X). Params: (batch_id, source_ref)
WITH ancestry (node_ref, depth) AS (
    SELECT CAST(input_ref AS VARCHAR(30)), 1 FROM batch_transformations WHERE output_batch_id = ?
    UNION ALL
    SELECT CAST(t.input_ref AS VARCHAR(30)), a.depth + 1
    FROM ancestry a
    JOIN batch_transformations t ON t.output_batch_id = a.node_ref
    WHERE a.depth < 12
)
SELECT COUNT(*) AS hits FROM ancestry WHERE node_ref = ?

-- name: verify_direct_recipients
-- Non-recursive cross-check: every location that a shipment record says
-- RECEIVED a given batch, regardless of hop ordering. Params: (batch_id)
SELECT DISTINCT s.dest_kind, s.dest_ref, s.shipment_status
FROM shipments s
JOIN shipment_items si ON si.shipment_id = s.shipment_id
WHERE si.batch_id = ?
ORDER BY s.dest_ref
