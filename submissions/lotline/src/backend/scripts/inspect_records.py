import sys
sys.path.insert(0, 'backend')
from app.database import query_all

print("--- INCIDENTS ---")
for r in query_all("SELECT * FROM LOTLINE_APP.INCIDENTS WHERE INCIDENT_ID = 'INC-2026-001'"):
    print(r)

print("\n--- LOT RAW-204 ---")
for r in query_all("SELECT * FROM LOTLINE_APP.LOTS WHERE LOT_ID = 'RAW-204'"):
    print(r)

print("\n--- LOT_LINEAGE for RAW-204 ---")
for r in query_all("SELECT * FROM LOTLINE_APP.LOT_LINEAGE WHERE PARENT_LOT_ID = 'RAW-204'"):
    print(r)

print("\n--- INVENTORY for RAW-204 ---")
for r in query_all("SELECT * FROM LOTLINE_APP.INVENTORY WHERE LOT_ID = 'RAW-204'"):
    print(r)

print("\n--- ALL LOT_LINEAGE ---")
for r in query_all("SELECT * FROM LOTLINE_APP.LOT_LINEAGE"):
    print(r)

print("\n--- ALL RECALL_ACTIONS ---")
for r in query_all("SELECT * FROM LOTLINE_APP.RECALL_ACTIONS"):
    print(r)

print("\n--- ALL SHIPMENTS ---")
for r in query_all("SELECT * FROM LOTLINE_APP.SHIPMENTS"):
    print(r)
