-- PACT — Procurement Audit & Counterfactual Triage
-- Schema Migration 001: 8 Procurement Source Tables
-- Target Database: IBM Db2 Community Edition (12.1.5.0)

-- 1. Buyers
CREATE TABLE buyers (
    id INTEGER NOT NULL PRIMARY KEY,
    first_name VARCHAR(64) NOT NULL,
    last_name VARCHAR(64) NOT NULL,
    email VARCHAR(128) NOT NULL UNIQUE,
    team VARCHAR(64) NOT NULL
);

-- 2. Suppliers
CREATE TABLE suppliers (
    id INTEGER NOT NULL PRIMARY KEY,
    supplier_name VARCHAR(128) NOT NULL,
    country VARCHAR(64) NOT NULL,
    payment_terms VARCHAR(32) NOT NULL
);

-- 3. Items
CREATE TABLE items (
    id INTEGER NOT NULL PRIMARY KEY,
    sku VARCHAR(32) NOT NULL UNIQUE,
    catalogue VARCHAR(64) NOT NULL,
    item_label VARCHAR(128) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    list_price DECIMAL(12, 2) NOT NULL
);

-- 4. Requisitions
CREATE TABLE requisitions (
    id INTEGER NOT NULL PRIMARY KEY,
    requester_dept VARCHAR(64) NOT NULL,
    item_id INTEGER NOT NULL,
    quantity_requested INTEGER NOT NULL,
    list_price DECIMAL(12, 2) NOT NULL,
    requested_on DATE NOT NULL,
    CONSTRAINT fk_req_item FOREIGN KEY (item_id) REFERENCES items(id)
);

-- 5. Purchase Orders
CREATE TABLE purchase_orders (
    id INTEGER NOT NULL PRIMARY KEY,
    po_number VARCHAR(32) NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL,
    buyer_id INTEGER NOT NULL,
    ordered_on DATE NOT NULL,
    payment_terms VARCHAR(32) NOT NULL,
    CONSTRAINT fk_po_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    CONSTRAINT fk_po_buyer FOREIGN KEY (buyer_id) REFERENCES buyers(id)
);

-- 6. Purchase Order Lines
CREATE TABLE po_lines (
    id INTEGER NOT NULL PRIMARY KEY,
    purchase_order_id INTEGER NOT NULL,
    requisition_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    ordered_on DATE NOT NULL,
    negotiated_factor DECIMAL(8, 4) NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    CONSTRAINT fk_pol_po FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id),
    CONSTRAINT fk_pol_req FOREIGN KEY (requisition_id) REFERENCES requisitions(id),
    CONSTRAINT fk_pol_item FOREIGN KEY (item_id) REFERENCES items(id)
);

-- 7. Goods Receipts
CREATE TABLE goods_receipts (
    id INTEGER NOT NULL PRIMARY KEY,
    po_line_id INTEGER NOT NULL,
    received_on DATE NOT NULL,
    received_share DECIMAL(8, 4) NOT NULL,
    received_qty INTEGER NOT NULL,
    condition VARCHAR(32) NOT NULL,
    CONSTRAINT fk_rec_poline FOREIGN KEY (po_line_id) REFERENCES po_lines(id)
);

-- 8. Supplier Invoices
CREATE TABLE supplier_invoices (
    id INTEGER NOT NULL PRIMARY KEY,
    po_line_id INTEGER NOT NULL,
    invoice_no VARCHAR(32) NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    qty_ratio DECIMAL(8, 4) NOT NULL,
    invoiced_qty INTEGER NOT NULL,
    billing_drift DECIMAL(8, 4) NOT NULL,
    billed_unit_price DECIMAL(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    paid_on DATE,
    CONSTRAINT fk_inv_poline FOREIGN KEY (po_line_id) REFERENCES po_lines(id)
);

-- Performance Indexes on Reconciliation Join Keys
CREATE INDEX idx_gr_poline ON goods_receipts(po_line_id);
CREATE INDEX idx_inv_poline ON supplier_invoices(po_line_id);
CREATE INDEX idx_pol_po ON po_lines(purchase_order_id);
CREATE INDEX idx_pol_item ON po_lines(item_id);
CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_req_item ON requisitions(item_id);

