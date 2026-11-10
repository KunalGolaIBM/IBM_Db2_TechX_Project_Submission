"""Idempotent Db2 schema and seed data creation."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from src.database.connection import connection
from src.database.schema import DDL, TABLES

CUSTOMERS = [
    (1,"Aarav Mehta","aarav.mehta@example.in","Mumbai","Maharashtra"),(2,"Ananya Iyer","ananya.iyer@example.in","Bengaluru","Karnataka"),
    (3,"Vivaan Sharma","vivaan.sharma@example.in","Delhi","Delhi"),(4,"Diya Nair","diya.nair@example.in","Kochi","Kerala"),
    (5,"Aditya Rao","aditya.rao@example.in","Hyderabad","Telangana"),(6,"Meera Patel","meera.patel@example.in","Ahmedabad","Gujarat"),
    (7,"Arjun Singh","arjun.singh@example.in","Jaipur","Rajasthan"),(8,"Ishita Das","ishita.das@example.in","Kolkata","West Bengal"),
    (9,"Kabir Shah","kabir.shah@example.in","Pune","Maharashtra"),(10,"Saanvi Reddy","saanvi.reddy@example.in","Chennai","Tamil Nadu"),
    (11,"Reyansh Joshi","reyansh.joshi@example.in","Indore","Madhya Pradesh"),(12,"Aditi Kulkarni","aditi.kulkarni@example.in","Nagpur","Maharashtra"),
    (13,"Krishna Menon","krishna.menon@example.in","Thiruvananthapuram","Kerala"),(14,"Myra Kapoor","myra.kapoor@example.in","Noida","Uttar Pradesh"),
    (15,"Atharv Gupta","atharv.gupta@example.in","Lucknow","Uttar Pradesh"),(16,"Sara Fernandes","sara.fernandes@example.in","Panaji","Goa"),
    (17,"Ishaan Chatterjee","ishaan.chatterjee@example.in","Bhubaneswar","Odisha"),(18,"Avni Bansal","avni.bansal@example.in","Chandigarh","Chandigarh"),
    (19,"Dhruv Desai","dhruv.desai@example.in","Surat","Gujarat"),(20,"Kiara Paul","kiara.paul@example.in","Guwahati","Assam"),
    (21,"Rohan Verma","rohan.verma@example.in","Kanpur","Uttar Pradesh"),(22,"Tara Sethi","tara.sethi@example.in","Gurugram","Haryana"),
    (23,"Neil Thomas","neil.thomas@example.in","Coimbatore","Tamil Nadu"),(24,"Pihu Jain","pihu.jain@example.in","Jodhpur","Rajasthan"),
]
PRODUCTS = [
    (1,"Aster X Smartphone","Electronics",Decimal("42999"),38),(2,"AsterBook Pro 14","Electronics",Decimal("89999"),16),
    (3,"SoundWave Headphones","Electronics",Decimal("7999"),64),(4,"Pulse Smartwatch","Electronics",Decimal("12499"),42),
    (5,"Monsoon Cotton Shirt","Fashion",Decimal("1899"),110),(6,"Indigo Kurta Set","Fashion",Decimal("2799"),72),
    (7,"Trailblazer Backpack","Fashion",Decimal("3499"),55),(8,"Nila Ceramic Dinner Set","Home",Decimal("4599"),33),
    (9,"Saffron Table Lamp","Home",Decimal("2299"),48),(10,"Breeze Air Purifier","Home",Decimal("15999"),19),
    (11,"Neem Care Gift Box","Beauty",Decimal("1499"),87),(12,"Lotus Skin Essentials","Beauty",Decimal("2199"),62),
    (13,"Pro Cricket Bat","Sports",Decimal("5499"),28),(14,"Yoga Mat Premium","Sports",Decimal("1799"),96),
    (15,"Chai & Coffee Hamper","Grocery",Decimal("1299"),74),
]
STATUSES = ("DELIVERED","DELIVERED","SHIPPED","PROCESSING","PLACED","CANCELLED")
METHODS = ("UPI","CARD","NET_BANKING","WALLET","COD")


def _merge_rows(conn, table: str, columns: tuple[str, ...], rows: Iterable[tuple]):
    import ibm_db
    names = ",".join(columns)
    expressions = []
    for column in columns:
        if column in {"ORDER_DATE", "PAYMENT_DATE"}:
            expressions.append("DATE(?)")
        elif column in {"UNIT_PRICE", "TOTAL_AMOUNT", "SUBTOTAL", "AMOUNT"}:
            expressions.append("CAST(? AS DECIMAL(12,2))")
        else:
            expressions.append("?")
    placeholders = ",".join(expressions)
    sql = (f"MERGE INTO {table} AS T USING (VALUES ({placeholders})) AS S ({names}) "
           f"ON T.{columns[0]} = S.{columns[0]} "
           f"WHEN NOT MATCHED THEN INSERT ({names}) VALUES ({', '.join('S.' + c for c in columns)})")
    stmt = ibm_db.prepare(conn, sql)
    for row in rows:
        ibm_db.execute(stmt, tuple(str(value) if isinstance(value, Decimal) else value for value in row))


def _table_exists(conn, name: str) -> bool:
    import ibm_db
    stmt = ibm_db.prepare(conn, "SELECT 1 FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA AND TABNAME = ?")
    ibm_db.execute(stmt, (name,))
    return ibm_db.fetch_tuple(stmt) is not False


def initialize_database() -> dict[str, int]:
    import ibm_db
    with connection() as conn:
        for ddl in DDL:
            # CREATE TABLE/INDEX is applied only if its target is missing.
            target = ddl.split("(")[0].split()[-1]
            exists = _table_exists(conn, target) if target in TABLES else _index_exists(conn, target)
            if not exists:
                ibm_db.exec_immediate(conn, ddl)

        today = date.today()
        orders, items, payments = [], [], []
        for order_id in range(1, 61):
            customer_id = (order_id * 7 % len(CUSTOMERS)) + 1
            order_date = today - timedelta(days=(order_id * 11) % 540)
            product_a = (order_id * 3 % len(PRODUCTS)) + 1
            product_b = ((order_id * 5 + 4) % len(PRODUCTS)) + 1
            qty_a, qty_b = (order_id % 3) + 1, (order_id % 2) + 1
            p_a, p_b = PRODUCTS[product_a - 1][3], PRODUCTS[product_b - 1][3]
            total = p_a * qty_a + p_b * qty_b
            status = STATUSES[order_id % len(STATUSES)]
            orders.append((order_id, customer_id, order_date.isoformat(), status, total))
            items.extend([(order_id * 2 - 1, order_id, product_a, qty_a, p_a, p_a * qty_a),
                          (order_id * 2, order_id, product_b, qty_b, p_b, p_b * qty_b)])
            pay_status = "PENDING" if status in ("PLACED", "PROCESSING") and order_id % 2 else ("FAILED" if status == "CANCELLED" else "PAID")
            payments.append((order_id, order_id, METHODS[order_id % len(METHODS)], pay_status, order_date.isoformat(), total))

        _merge_rows(conn, "CUSTOMERS", ("CUSTOMER_ID","CUSTOMER_NAME","EMAIL","CITY","STATE","COUNTRY"),
                    [r + ("India",) for r in CUSTOMERS])
        _merge_rows(conn, "PRODUCTS", ("PRODUCT_ID","PRODUCT_NAME","CATEGORY","UNIT_PRICE","STOCK_QUANTITY"), PRODUCTS)
        _merge_rows(conn, "ORDERS", ("ORDER_ID","CUSTOMER_ID","ORDER_DATE","ORDER_STATUS","TOTAL_AMOUNT"), orders)
        _merge_rows(conn, "ORDER_ITEMS", ("ITEM_ID","ORDER_ID","PRODUCT_ID","QUANTITY","UNIT_PRICE","SUBTOTAL"), items)
        _merge_rows(conn, "PAYMENTS", ("PAYMENT_ID","ORDER_ID","PAYMENT_METHOD","PAYMENT_STATUS","PAYMENT_DATE","AMOUNT"), payments)
        counts = {}
        for table in TABLES:
            stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) AS N FROM {table}")
            counts[table] = int(ibm_db.fetch_assoc(stmt)["N"])
        return counts


def _index_exists(conn, name: str) -> bool:
    import ibm_db
    stmt = ibm_db.prepare(conn, "SELECT 1 FROM SYSCAT.INDEXES WHERE INDSCHEMA = CURRENT SCHEMA AND INDNAME = ?")
    ibm_db.execute(stmt, (name,))
    return ibm_db.fetch_tuple(stmt) is not False
