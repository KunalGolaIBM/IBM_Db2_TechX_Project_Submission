-- =============================================================================
-- Kisan Mitra (किसान मित्र) - IBM Db2 Initial Bootstrap Seed Data
-- Connects to IBM Db2 12.1+ database KISANMIT
-- =============================================================================

CONNECT TO KISANMIT USER db2inst1 USING KisanMitra2026!;

-- 1. Insert Sample Mandi Daily Price Records
INSERT INTO MANDI_PRICES (state, district, market, commodity, variety, arrival_date, min_price, max_price, modal_price)
VALUES 
('Uttar Pradesh', 'Mathura', 'Mathura', 'Potato', 'Desi', CURRENT DATE, 1420.00, 1580.00, 1520.00),
('Uttar Pradesh', 'Mathura', 'Kosi Kalan', 'Potato', 'Desi', CURRENT DATE, 1400.00, 1540.00, 1480.00),
('Uttar Pradesh', 'Mathura', 'Mathura', 'Wheat', 'Dara', CURRENT DATE, 2420.00, 2560.00, 2500.00),
('Uttar Pradesh', 'Mathura', 'Kosi Kalan', 'Wheat', 'Dara', CURRENT DATE, 2410.00, 2530.00, 2475.00),
('Uttar Pradesh', 'Agra', 'Agra', 'Potato', 'Desi', CURRENT DATE, 1450.00, 1620.00, 1550.00),
('Uttar Pradesh', 'Agra', 'Agra', 'Wheat', 'Dara', CURRENT DATE, 2440.00, 2580.00, 2520.00),
('Uttar Pradesh', 'Agra', 'Agra', 'Mustard', 'Sarson', CURRENT DATE, 5250.00, 5600.00, 5450.00),
('Uttar Pradesh', 'Aligarh', 'Aligarh', 'Potato', 'Desi', CURRENT DATE, 1390.00, 1520.00, 1460.00),
('Uttar Pradesh', 'Aligarh', 'Aligarh', 'Wheat', 'Dara', CURRENT DATE, 2430.00, 2570.00, 2510.00),
('Uttar Pradesh', 'Lucknow', 'Lucknow', 'Potato', 'Desi', CURRENT DATE, 1500.00, 1680.00, 1600.00),
('Uttar Pradesh', 'Lucknow', 'Lucknow', 'Wheat', 'Dara', CURRENT DATE, 2460.00, 2600.00, 2550.00),
('Uttar Pradesh', 'Lucknow', 'Lucknow', 'Gram', 'Desi', CURRENT DATE, 6100.00, 6600.00, 6400.00),
('Uttar Pradesh', 'Kanpur Nagar', 'Kanpur', 'Wheat', 'Dara', CURRENT DATE, 2450.00, 2590.00, 2540.00),
('Uttar Pradesh', 'Kanpur Nagar', 'Kanpur', 'Gram', 'Desi', CURRENT DATE, 6150.00, 6650.00, 6420.00),
('Uttar Pradesh', 'Varanasi', 'Varanasi', 'Gram', 'Desi', CURRENT DATE, 6200.00, 6700.00, 6480.00),
('Uttar Pradesh', 'Bareilly', 'Bareilly', 'Wheat', 'Dara', CURRENT DATE, 2430.00, 2560.00, 2510.00);

COMMIT;

TERMINATE;
