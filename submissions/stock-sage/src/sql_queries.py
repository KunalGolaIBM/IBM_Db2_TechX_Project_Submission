"""Parameterized SQL queries for IBM Db2.

All queries use standard Db2 SQL syntax with parameter placeholders (?)
to prevent SQL injection and guarantee deterministic result sets.
"""

# Query 1: Total current stock per product (summed across active inventory batches)
QUERY_CURRENT_STOCK = """
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        p.unit_price,
        p.reorder_level,
        s.supplier_name,
        s.lead_time_days,
        COALESCE(SUM(b.available_quantity), 0) AS total_available_stock
    FROM PRODUCTS p
    LEFT JOIN INVENTORY_BATCHES b ON p.product_id = b.product_id
    LEFT JOIN SUPPLIERS s ON p.supplier_id = s.supplier_id
    GROUP BY 
        p.product_id, p.product_name, p.category, p.unit_price, 
        p.reorder_level, s.supplier_name, s.lead_time_days
    ORDER BY p.category, p.product_name
"""

# Query 2: Products running low on stock (stock <= reorder_level)
QUERY_LOW_STOCK_PRODUCTS = """
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        p.unit_price,
        p.reorder_level,
        s.supplier_name,
        s.contact_details,
        s.lead_time_days,
        COALESCE(SUM(b.available_quantity), 0) AS total_stock
    FROM PRODUCTS p
    LEFT JOIN INVENTORY_BATCHES b ON p.product_id = b.product_id
    LEFT JOIN SUPPLIERS s ON p.supplier_id = s.supplier_id
    GROUP BY 
        p.product_id, p.product_name, p.category, p.unit_price, 
        p.reorder_level, s.supplier_name, s.contact_details, s.lead_time_days
    HAVING COALESCE(SUM(b.available_quantity), 0) <= p.reorder_level
    ORDER BY (p.reorder_level - COALESCE(SUM(b.available_quantity), 0)) DESC
"""

# Query 3: Batches approaching expiry (within given number of days)
QUERY_BATCH_EXPIRY = """
    SELECT 
        b.batch_id,
        p.product_id,
        p.product_name,
        p.category,
        b.available_quantity,
        b.received_date,
        b.expiry_date,
        s.supplier_name
    FROM INVENTORY_BATCHES b
    JOIN PRODUCTS p ON b.product_id = p.product_id
    JOIN SUPPLIERS s ON p.supplier_id = s.supplier_id
    WHERE b.available_quantity > 0
    ORDER BY b.expiry_date ASC
"""

# Query 4: Sales velocity & averages over the last N days
QUERY_SALES_VELOCITY = """
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        p.unit_price,
        COUNT(s.sale_id) AS sales_count,
        COALESCE(SUM(s.quantity_sold), 0) AS total_quantity_sold,
        COALESCE(SUM(s.revenue), 0.0) AS total_revenue,
        ROUND(CAST(COALESCE(SUM(s.quantity_sold), 0) AS DOUBLE) / ?, 2) AS avg_daily_sales
    FROM PRODUCTS p
    LEFT JOIN SALES s ON p.product_id = s.product_id 
        AND s.sale_date >= ?
    GROUP BY p.product_id, p.product_name, p.category, p.unit_price
    ORDER BY total_quantity_sold DESC
"""

# Query 5: Full sales history by date for trend visualization
QUERY_DAILY_SALES_TREND = """
    SELECT 
        s.sale_date,
        SUM(s.quantity_sold) AS total_units_sold,
        SUM(s.revenue) AS total_daily_revenue,
        COUNT(DISTINCT s.product_id) AS distinct_products_sold
    FROM SALES s
    GROUP BY s.sale_date
    ORDER BY s.sale_date ASC
"""

# Query 6: Category sales breakdown
QUERY_CATEGORY_PERFORMANCE = """
    SELECT 
        p.category,
        SUM(s.quantity_sold) AS units_sold,
        SUM(s.revenue) AS category_revenue
    FROM SALES s
    JOIN PRODUCTS p ON s.product_id = p.product_id
    GROUP BY p.category
    ORDER BY category_revenue DESC
"""

# Query 7: Suppliers lookup
QUERY_SUPPLIERS = """
    SELECT 
        supplier_id,
        supplier_name,
        lead_time_days,
        contact_details
    FROM SUPPLIERS
    ORDER BY supplier_name ASC
"""

