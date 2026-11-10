"""Read-only queries used by application pages."""
from src.database.connection import query_dataframe
from src.database.schema import TABLES

def table_counts():
    return {t: int(query_dataframe(f"SELECT COUNT(*) AS N FROM {t}")[0].iloc[0, 0]) for t in TABLES}

def table_preview(table: str, limit: int = 50):
    if table not in TABLES:
        raise ValueError("Unknown application table")
    limit = max(1, min(int(limit), 500))
    return query_dataframe(f"SELECT * FROM {table} FETCH FIRST {limit} ROWS ONLY")[0]

def live_schema_context():
    names = ",".join(f"'{name}'" for name in TABLES)
    df, _ = query_dataframe(
        "SELECT TABNAME, COLNAME, TYPENAME FROM SYSCAT.COLUMNS "
        f"WHERE TABSCHEMA=CURRENT SCHEMA AND TABNAME IN ({names}) ORDER BY TABNAME, COLNO"
    )
    grouped = {}
    for row in df.itertuples(index=False):
        grouped.setdefault(str(row[0]), []).append(f"{row[1]} {row[2]}")
    if not grouped:
        raise RuntimeError("The configured Db2 schema does not contain the Db2Ops AI application tables.")
    return "Live Db2 application schema (catalog metadata):\n" + "\n".join(
        f"{table}({', '.join(columns)})" for table, columns in grouped.items()
    ) + "\n" + SCHEMA_CONTEXT_RELATIONSHIPS

SCHEMA_CONTEXT_RELATIONSHIPS = (
    "Relationships: ORDERS.CUSTOMER_ID -> CUSTOMERS; ORDER_ITEMS.ORDER_ID -> ORDERS; "
    "ORDER_ITEMS.PRODUCT_ID -> PRODUCTS; PAYMENTS.ORDER_ID -> ORDERS. "
    "Revenue means sum of ORDER_ITEMS.SUBTOTAL or ORDERS.TOTAL_AMOUNT. "
    "Use Db2 syntax, FETCH FIRST n ROWS ONLY, and CURRENT DATE. Reference only the five app tables."
)

def analytics_frames(start_date=None, end_date=None):
    from datetime import date, timedelta
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=540))
    sql = {
        "monthly": "SELECT YEAR(ORDER_DATE) AS SALES_YEAR, MONTH(ORDER_DATE) AS SALES_MONTH, SUM(TOTAL_AMOUNT) AS REVENUE, COUNT(*) AS ORDERS FROM ORDERS WHERE ORDER_STATUS <> 'CANCELLED' AND ORDER_DATE BETWEEN ? AND ? GROUP BY YEAR(ORDER_DATE), MONTH(ORDER_DATE) ORDER BY SALES_YEAR, SALES_MONTH",
        "products": "SELECT P.PRODUCT_NAME, SUM(I.QUANTITY) AS UNITS, SUM(I.SUBTOTAL) AS REVENUE FROM ORDER_ITEMS I JOIN PRODUCTS P ON P.PRODUCT_ID=I.PRODUCT_ID JOIN ORDERS O ON O.ORDER_ID=I.ORDER_ID WHERE O.ORDER_STATUS <> 'CANCELLED' AND O.ORDER_DATE BETWEEN ? AND ? GROUP BY P.PRODUCT_NAME ORDER BY REVENUE DESC FETCH FIRST 10 ROWS ONLY",
        "customers": "SELECT C.CUSTOMER_NAME, SUM(O.TOTAL_AMOUNT) AS SPEND FROM CUSTOMERS C JOIN ORDERS O ON O.CUSTOMER_ID=C.CUSTOMER_ID WHERE O.ORDER_STATUS <> 'CANCELLED' AND O.ORDER_DATE BETWEEN ? AND ? GROUP BY C.CUSTOMER_NAME ORDER BY SPEND DESC FETCH FIRST 10 ROWS ONLY",
        "cities": "SELECT C.CITY, SUM(O.TOTAL_AMOUNT) AS REVENUE FROM CUSTOMERS C JOIN ORDERS O ON O.CUSTOMER_ID=C.CUSTOMER_ID WHERE O.ORDER_STATUS <> 'CANCELLED' AND O.ORDER_DATE BETWEEN ? AND ? GROUP BY C.CITY ORDER BY REVENUE DESC FETCH FIRST 10 ROWS ONLY",
        "payments": "SELECT PAYMENT_STATUS, COUNT(*) AS PAYMENT_COUNT, SUM(AMOUNT) AS AMOUNT FROM PAYMENTS WHERE PAYMENT_DATE BETWEEN ? AND ? GROUP BY PAYMENT_STATUS ORDER BY PAYMENT_STATUS",
        "categories": "SELECT P.CATEGORY, SUM(I.SUBTOTAL) AS REVENUE, SUM(I.QUANTITY) AS UNITS FROM ORDER_ITEMS I JOIN PRODUCTS P ON P.PRODUCT_ID=I.PRODUCT_ID JOIN ORDERS O ON O.ORDER_ID=I.ORDER_ID WHERE O.ORDER_STATUS <> 'CANCELLED' AND O.ORDER_DATE BETWEEN ? AND ? GROUP BY P.CATEGORY ORDER BY REVENUE DESC",
    }
    dates = (start_date.isoformat(), end_date.isoformat())
    return {name: query_dataframe(statement, dates)[0] for name, statement in sql.items()}
