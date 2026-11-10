-- ============================================================================
-- CatalogLens Synthetic Seed Data
-- Target Platform: IBM Db2 LUW
-- Schema: ENTERPRISE
-- ============================================================================

-- Customers
INSERT INTO ENTERPRISE.CUSTOMER_MST (CUST_NAME, CUST_TYPE_CD, CUST_EMAIL, TAX_ID, STATUS_CD) VALUES
('Acme Industrial Corp', 'B2B', 'procurement@acme-industrial.com', 'US-94-2819021', 'AC'),
('Nexus Logistics LLC', 'B2B', 'finance@nexuslogistics.com', 'US-82-1092837', 'AC'),
('Sarah Jenkins', 'RET', 'sarah.jenkins@example.com', NULL, 'AC'),
('David Vance', 'RET', 'dvance@quantummail.org', NULL, 'AC'),
('Global Retail Partners', 'B2B', 'accounts@globalretail.de', 'DE-198273641', 'AC'),
('Elena Rostova', 'RET', 'elena.rostova@techmail.io', NULL, 'SU');

-- Warehouses
INSERT INTO ENTERPRISE.WAREHOUSE_MST (WH_CODE, WH_NAME, REGION_CD, MAX_CAPACITY, OPERATIONAL_STS) VALUES
('WH-EAST-01', 'Jersey City Distribution Hub', 'US-EAST', 85000, 'ONLINE'),
('WH-WEST-02', 'Reno Logistics Facility', 'US-WEST', 120000, 'ONLINE'),
('WH-CENTRAL-03', 'Dallas Fulfillment Center', 'US-CENTRAL', 95000, 'ONLINE'),
('WH-EU-01', 'Rotterdam Euro Hub', 'EU-WEST', 60000, 'ONLINE');

-- Suppliers
INSERT INTO ENTERPRISE.SUPPLIER_MST (SUPP_NAME, CONTACT_EMAIL, COUNTRY_CD, RATING_SCORE, ACTIVE_IND) VALUES
('Apex Semiconductor Ltd', 'sales@apex-semi.tw', 'TWN', 4.85, 'Y'),
('Nordic Precision Machining', 'orders@nordicprecision.se', 'SWE', 4.92, 'Y'),
('Shenzhen Optical Components', 'b2b@szoptical.cn', 'CHN', 4.40, 'Y'),
('American Alloy Fabricators', 'supply@amalloyfab.com', 'USA', 4.70, 'Y');

-- Products
INSERT INTO ENTERPRISE.PRODUCT_MST (SKU_CODE, PROD_NAME, CATEGORY_ID, BASE_PRICE, WEIGHT_KG, IS_ACTIVE) VALUES
('SKU-SRV-2001', 'Enterprise Rackmount Server 2U Xeon', 101, 3499.00, 18.500, 'Y'),
('SKU-MEM-8042', '64GB ECC Registered DDR5 Module', 102, 289.50, 0.120, 'Y'),
('SKU-SSD-9901', '3.84TB Enterprise NVMe U.3 SSD', 103, 549.00, 0.180, 'Y'),
('SKU-CAB-0012', '10GbE SFP+ Direct Attach Copper Cable 3m', 104, 45.00, 0.250, 'Y'),
('SKU-RACK-42U', '42U Standard Equipment Enclosure', 105, 1150.00, 125.000, 'Y'),
('SKU-PWR-1600', '1600W Titanium Redundant Power Supply', 106, 320.00, 2.100, 'Y');

-- Inventory
INSERT INTO ENTERPRISE.INVENTORY (PROD_ID, WH_ID, ON_HAND_QTY, REORDER_POINT, LAST_COUNT_DT) VALUES
(5001, 1, 45, 10, '2026-10-15'),
(5001, 2, 80, 15, '2026-10-14'),
(5002, 1, 620, 100, '2026-10-20'),
(5002, 2, 850, 150, '2026-10-21'),
(5003, 1, 310, 50, '2026-10-18'),
(5003, 3, 215, 40, '2026-10-19'),
(5004, 1, 1200, 200, '2026-10-01'),
(5005, 1, 14, 5, '2026-10-05'),
(5006, 2, 95, 20, '2026-10-12');

-- Payment Methods
INSERT INTO ENTERPRISE.PAYMENT_METHOD (CUST_ID, PM_TYPE_CD, TOKENIZED_ACCT, EXPIRY_MON_YR, IS_DEFAULT) VALUES
(10001, 'ACH', 'tok_ach_corp_991827461928', '12/2028', 'Y'),
(10002, 'CC', 'tok_visa_bus_4111222233334444', '09/2027', 'Y'),
(10003, 'CC', 'tok_mc_ret_5500123456789012', '04/2026', 'Y'),
(10004, 'PAYPAL', 'tok_pp_dvance_wallet_8829', NULL, 'Y');

-- Orders Header
INSERT INTO ENTERPRISE.ORD_HDR (CUST_ID, ORDER_DT, ORDER_STATUS_CD, TOTAL_AMT, CURRENCY_CD, CHANNEL_CD) VALUES
(10001, '2026-11-01', 'PAID', 8145.50, 'USD', 'B2B_EDI'),
(10002, '2026-11-03', 'SHIP', 4298.00, 'USD', 'WEB'),
(10003, '2026-11-05', 'NEW', 634.50, 'USD', 'WEB'),
(10004, '2026-11-06', 'DELV', 1150.00, 'USD', 'WEB');

-- Order Lines
INSERT INTO ENTERPRISE.ORD_LINE (ORDER_ID, PROD_ID, LINE_NUM, ORDER_QTY, UNIT_PRICE, DISCOUNT_AMT, NET_AMT) VALUES
(90001, 5001, 1, 2, 3499.00, 200.00, 6798.00),
(90001, 5002, 2, 4, 289.50, 0.00, 1158.00),
(90001, 5004, 3, 4, 45.00, 0.00, 180.00),
(90002, 5001, 1, 1, 3499.00, 0.00, 3499.00),
(90002, 5003, 2, 1, 549.00, 0.00, 549.00),
(90003, 5002, 1, 2, 289.50, 0.00, 579.00),
(90004, 5005, 1, 1, 1150.00, 0.00, 1150.00);

-- Inventory Reservations
INSERT INTO ENTERPRISE.INVENTORY_RESERVATION (ORDER_ID, PROD_ID, WH_ID, RESV_QTY, RESV_STATUS, EXPIRE_TS) VALUES
(90001, 5001, 1, 2, 'FULFILLED', '2026-11-02 12:00:00'),
(90002, 5001, 2, 1, 'FULFILLED', '2026-11-04 18:00:00'),
(90003, 5002, 1, 2, 'ACTIVE', '2026-11-08 23:59:59');

-- Payment Transactions
INSERT INTO ENTERPRISE.PAYMENT_TXN (ORDER_ID, PM_ID, TXN_AMT, TXN_STATUS_CD, GATEWAY_REF_NO, AUTH_CODE) VALUES
(90001, 1, 8145.50, 'CAPT', 'gw_ref_ach_9928172645', 'AUTH-89102'),
(90002, 2, 4298.00, 'CAPT', 'gw_ref_cc_1827364510', 'AUTH-44192'),
(90004, 4, 1150.00, 'CAPT', 'gw_ref_pp_7726152438', 'AUTH-99182');

-- Shipments Header
INSERT INTO ENTERPRISE.SHIPMENT_HDR (ORDER_ID, WH_ID, CARRIER_CD, TRACKING_NO, SHIP_DT, DELIVERY_STS) VALUES
(90001, 1, 'FEDEX', 'TRK-FX-992817263541', '2026-11-02', 'DELIVERED'),
(90002, 2, 'UPS', 'TRK-UPS-1Z9999999999', '2026-11-04', 'IN_TRANSIT'),
(90004, 1, 'FREIGHT', 'TRK-FRT-8819201928', '2026-11-07', 'DELIVERED');

-- Shipment Items
INSERT INTO ENTERPRISE.SHIPMENT_ITEM (SHIPMENT_ID, LINE_ID, PACKED_QTY, INSPECTION_STS) VALUES
(30001, 1, 2, 'PASSED'),
(30001, 2, 4, 'PASSED'),
(30001, 3, 4, 'PASSED'),
(30002, 4, 1, 'PASSED'),
(30002, 5, 1, 'PASSED'),
(30003, 7, 1, 'PASSED');

-- Returns Header (Notice CUST_REF_NO references CUSTOMER_MST.CUST_ID, and ORDER_ID references ORD_HDR.ORDER_ID without foreign key constraint!)
INSERT INTO ENTERPRISE.RETURN_HDR (ORDER_ID, CUST_REF_NO, RET_REASON_CD, RET_STATUS_CD, REFUND_AMT, REQUEST_DT) VALUES
(90001, 10001, 'DEFECTIVE', 'RECV', 579.00, '2026-11-08'),
(90004, 10004, 'BUYER_REMORSE', 'APRV', 1150.00, '2026-11-09');
