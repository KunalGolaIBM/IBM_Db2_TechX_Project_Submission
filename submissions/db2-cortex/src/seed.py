"""Creates the BANKING demo schema + Cortex control-plane tables in Db2 and fills the VECTOR semantic layer."""
import random
import datetime as dt
from db import execute, executemany, query, vlit, conn
from embeddings import embed, EMB
from config import EMBED_DIM

random.seed(7)
TABLES = ["CORTEX.AUDIT_LOG", "CORTEX.SESSION_MEMORY", "CORTEX.QUERY_CACHE", "CORTEX.SEMANTIC_LAYER",
          "BANKING.TRANSACTIONS", "BANKING.LOANS", "BANKING.ACCOUNTS", "BANKING.CUSTOMERS", "BANKING.BRANCHES"]

DDL = [
    "CREATE TABLE BANKING.BRANCHES (BRANCH_ID INT NOT NULL PRIMARY KEY, NAME VARCHAR(60), CITY VARCHAR(40), REGION VARCHAR(20))",
    "CREATE TABLE BANKING.CUSTOMERS (CUSTOMER_ID INT NOT NULL PRIMARY KEY, FULL_NAME VARCHAR(80), EMAIL VARCHAR(100), CITY VARCHAR(40), SEGMENT VARCHAR(20), JOINED_ON DATE)",
    "CREATE TABLE BANKING.ACCOUNTS (ACCOUNT_ID INT NOT NULL PRIMARY KEY, CUSTOMER_ID INT, BRANCH_ID INT, TYPE VARCHAR(12), BALANCE DECIMAL(14,2), OPENED_ON DATE)",
    "CREATE TABLE BANKING.TRANSACTIONS (TXN_ID BIGINT NOT NULL PRIMARY KEY, ACCOUNT_ID INT, TXN_DATE DATE, AMOUNT DECIMAL(12,2), CHANNEL VARCHAR(10), MERCHANT_CAT VARCHAR(20), IS_FLAGGED SMALLINT)",
    "CREATE TABLE BANKING.LOANS (LOAN_ID INT NOT NULL PRIMARY KEY, CUSTOMER_ID INT, BRANCH_ID INT, PRINCIPAL DECIMAL(14,2), STATUS VARCHAR(10), ISSUED_ON DATE)",
    f"CREATE TABLE CORTEX.SEMANTIC_LAYER (ID INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, KIND VARCHAR(12), NAME VARCHAR(100), DESCRIPTION VARCHAR(2000), EMB VECTOR({EMBED_DIM}, FLOAT32))",
    f"CREATE TABLE CORTEX.QUERY_CACHE (ID INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, QUESTION VARCHAR(500), SQL_TEXT VARCHAR(4000), ROLE VARCHAR(12), HITS INT DEFAULT 0, EMB VECTOR({EMBED_DIM}, FLOAT32))",
    "CREATE TABLE CORTEX.SESSION_MEMORY (ID BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, SESSION_ID VARCHAR(40), TS VARCHAR(32), QUESTION VARCHAR(500), SQL_TEXT VARCHAR(4000))",
    "CREATE TABLE CORTEX.AUDIT_LOG (ID BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, TS VARCHAR(32), ROLE VARCHAR(12), QUESTION VARCHAR(500), SQL_TEXT VARCHAR(4000), STATUS VARCHAR(12), ROWS_RETURNED INT, LATENCY_MS INT, PREV_HASH CHAR(64), HASH CHAR(64))",
]

SEMANTIC = [
    ("table", "BANKING.CUSTOMERS", "Customers. Columns: CUSTOMER_ID, FULL_NAME (PII), EMAIL (PII), CITY, SEGMENT (RETAIL/SME/PREMIUM), JOINED_ON."),
    ("table", "BANKING.ACCOUNTS", "Accounts held by customers. Columns: ACCOUNT_ID, CUSTOMER_ID, BRANCH_ID, TYPE (SAVINGS/CURRENT/SALARY), BALANCE, OPENED_ON."),
    ("table", "BANKING.TRANSACTIONS", "Card, UPI and net-banking transactions. Columns: TXN_ID, ACCOUNT_ID, TXN_DATE, AMOUNT, CHANNEL (UPI/CARD/NETBANK/ATM), MERCHANT_CAT, IS_FLAGGED (1 = suspected fraud)."),
    ("table", "BANKING.LOANS", "Loans issued. Columns: LOAN_ID, CUSTOMER_ID, BRANCH_ID, PRINCIPAL, STATUS (ACTIVE/CLOSED/DEFAULTED), ISSUED_ON."),
    ("table", "BANKING.BRANCHES", "Bank branches. Columns: BRANCH_ID, NAME, CITY, REGION (NORTH/SOUTH/EAST/WEST)."),
    ("metric", "default_rate", "Loan default rate = loans with STATUS='DEFAULTED' divided by all loans, usually grouped by branch or region."),
    ("metric", "fraud_rate", "Fraud rate = transactions with IS_FLAGGED=1 divided by all transactions, by channel or merchant category."),
    ("metric", "monthly_volume", "Monthly transaction volume = SUM(AMOUNT) grouped by TO_CHAR(TXN_DATE,'YYYY-MM')."),
    ("metric", "top_customers", "Top customers by total account BALANCE: join CUSTOMERS to ACCOUNTS and SUM(BALANCE)."),
    ("join", "joins", "TRANSACTIONS.ACCOUNT_ID=ACCOUNTS.ACCOUNT_ID; ACCOUNTS.CUSTOMER_ID=CUSTOMERS.CUSTOMER_ID; ACCOUNTS.BRANCH_ID=BRANCHES.BRANCH_ID; LOANS.BRANCH_ID=BRANCHES.BRANCH_ID."),
]
GLOSSARY = [
    "Governance: FULL_NAME and EMAIL are personal data and must be masked for the analyst role.",
    "Fiscal year runs from 1 April to 31 March.",
    "Amounts are in Indian Rupees (INR).",
    "Only SELECT statements are permitted; results are capped at 200 rows.",
]


def d(a, b):
    return a + dt.timedelta(days=random.randint(0, (b - a).days))


def run():
    for s in ("BANKING", "CORTEX"):
        try:
            execute(f"CREATE SCHEMA {s}")
        except Exception:
            pass
    for t in TABLES:
        try:
            execute(f"DROP TABLE {t}")
        except Exception:
            pass
    for q in DDL:
        execute(q)
    cities = ["Hyderabad", "Mumbai", "Delhi", "Chennai", "Kolkata", "Pune", "Bengaluru", "Jaipur"]
    reg = ["SOUTH", "WEST", "NORTH", "SOUTH", "EAST", "WEST", "SOUTH", "NORTH"]
    executemany("INSERT INTO BANKING.BRANCHES VALUES (?,?,?,?)", [(i + 1, f"{c} Main", c, reg[i]) for i, c in enumerate(cities)])
    first = ["Aarav", "Diya", "Rohan", "Ananya", "Vikram", "Meera", "Karan", "Isha", "Arjun", "Sneha", "Rahul", "Priya"]
    last = ["Reddy", "Sharma", "Iyer", "Gupta", "Khan", "Nair", "Das", "Mehta", "Patel", "Rao"]
    cust = [(i, f"{random.choice(first)} {random.choice(last)}", f"user{i}@example.com", random.choice(cities),
             random.choices(["RETAIL", "SME", "PREMIUM"], [70, 20, 10])[0], str(d(dt.date(2018, 1, 1), dt.date(2025, 6, 1)))) for i in range(1, 401)]
    executemany("INSERT INTO BANKING.CUSTOMERS VALUES (?,?,?,?,?,?)", cust)
    accts = [(i, random.randint(1, 400), random.randint(1, 8), random.choice(["SAVINGS", "CURRENT", "SALARY"]),
              round(random.lognormvariate(10.5, 1.1), 2), str(d(dt.date(2018, 1, 1), dt.date(2026, 1, 1)))) for i in range(1, 701)]
    executemany("INSERT INTO BANKING.ACCOUNTS VALUES (?,?,?,?,?,?)", accts)
    ch = ["UPI", "CARD", "NETBANK", "ATM"]
    mc = ["GROCERY", "TRAVEL", "ELECTRONICS", "DINING", "FUEL", "UTILITIES", "CRYPTO"]
    tx = []
    for i in range(1, 15001):
        fl = 1 if random.random() < 0.015 else 0
        amt = round(random.lognormvariate(7.2, 1.0) * (4 if fl else 1), 2)
        tx.append((i, random.randint(1, 700), str(d(dt.date(2025, 1, 1), dt.date(2026, 10, 31))), amt,
                   random.choices(ch, [50, 30, 12, 8])[0], random.choice(mc), fl))
    for i in range(0, len(tx), 2000):
        executemany("INSERT INTO BANKING.TRANSACTIONS VALUES (?,?,?,?,?,?,?)", tx[i:i + 2000])
    loans = [(i, random.randint(1, 400), random.randint(1, 8), round(random.uniform(50000, 2500000), 2),
              random.choices(["ACTIVE", "CLOSED", "DEFAULTED"], [70, 20, 10])[0], str(d(dt.date(2021, 1, 1), dt.date(2026, 9, 1)))) for i in range(1, 301)]
    executemany("INSERT INTO BANKING.LOANS VALUES (?,?,?,?,?,?)", loans)
    for kind, name, desc in SEMANTIC:
        execute(f"INSERT INTO CORTEX.SEMANTIC_LAYER (KIND,NAME,DESCRIPTION,EMB) VALUES (?,?,?,{vlit(embed(f'{name} {desc}'))})",
                (kind, name, desc))
    try:  # LangChain Db2 vector store holds governance glossary
        from langchain_db2 import DB2VS
        from langchain_community.vectorstores.utils import DistanceStrategy
        DB2VS.from_texts(GLOSSARY, EMB, client=conn(), table_name="CORTEX_GLOSSARY", distance_strategy=DistanceStrategy.COSINE)
    except Exception as e:
        print("glossary store skipped:", e)
    print("Seed complete.")


if __name__ == "__main__":
    run()
