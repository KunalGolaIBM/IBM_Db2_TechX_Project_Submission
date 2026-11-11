"""Demo workload: fixed literals so each query is a single package-cache entry."""
from __future__ import annotations

import time

WORKLOAD = {
    "W1": "SELECT ORDER_ID, ORDER_DATE, STATUS, TOTAL_AMOUNT FROM RETAIL.ORDERS WHERE CUSTOMER_ID = 4242 "
          "ORDER BY ORDER_DATE DESC FETCH FIRST 20 ROWS ONLY",
    "W2": "SELECT P.PRODUCT_NAME, SUM(I.QUANTITY) AS UNITS, SUM(I.QUANTITY * I.UNIT_PRICE) AS REVENUE "
          "FROM RETAIL.ORDER_ITEMS I JOIN RETAIL.PRODUCTS P ON P.PRODUCT_ID = I.PRODUCT_ID "
          "WHERE I.PRODUCT_ID = 77 GROUP BY P.PRODUCT_NAME",
    "W3": "SELECT CHANNEL, COUNT(*) AS ORDERS, SUM(TOTAL_AMOUNT) AS REVENUE FROM RETAIL.ORDERS "
          "WHERE YEAR(ORDER_DATE) = 2024 AND MONTH(ORDER_DATE) = 3 GROUP BY CHANNEL",
    "W4": "SELECT O.ORDER_ID, O.ORDER_DATE, O.TOTAL_AMOUNT, C.FULL_NAME, C.EMAIL FROM RETAIL.ORDERS O "
          "JOIN RETAIL.CUSTOMERS C ON C.CUSTOMER_ID = O.CUSTOMER_ID WHERE O.STATUS = 'PENDING' "
          "AND O.ORDER_DATE BETWEEN '2025-06-01' AND '2025-06-30' ORDER BY O.TOTAL_AMOUNT DESC FETCH FIRST 50 ROWS ONLY",
    "W5": "SELECT COUNT(*) FROM RETAIL.CUSTOMERS C WHERE C.SEGMENT = 'ENTERPRISE' AND C.CUSTOMER_ID NOT IN "
          "(SELECT O.CUSTOMER_ID FROM RETAIL.ORDERS O WHERE O.ORDER_DATE >= '2025-01-01')",
    "W6": "SELECT FULL_NAME, EMAIL, COUNTRY FROM RETAIL.CUSTOMERS WHERE CUSTOMER_ID = 1234",
    "W7": "SELECT CUSTOMER_ID, ORDER_DATE, TOTAL_AMOUNT FROM RETAIL.ORDERS WHERE STATUS = 'PENDING' "
          "AND TOTAL_AMOUNT > 900 UNION SELECT CUSTOMER_ID, ORDER_DATE, TOTAL_AMOUNT FROM RETAIL.ORDERS "
          "WHERE STATUS = 'CANCELLED' AND TOTAL_AMOUNT > 900",
}


def label_for(sql: str) -> str:
    norm = " ".join(sql.split()).upper()
    return next((k for k, v in WORKLOAD.items() if " ".join(v.split()).upper() == norm), "")


def run(db, repeat: int = 5, flush: bool = True) -> dict[str, float]:
    if flush:
        db.exec_immediate("FLUSH PACKAGE CACHE DYNAMIC")
    out = {}
    for name, sql in WORKLOAD.items():
        t0 = time.perf_counter()
        for _ in range(repeat):
            db.run_untagged(sql)
        out[name] = (time.perf_counter() - t0) * 1000 / repeat
    return out
