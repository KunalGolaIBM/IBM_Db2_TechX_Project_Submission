import sys
sys.path.insert(0, 'backend')
from app.database import query_all

tables = query_all("SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = 'LOTLINE_APP' ORDER BY TABNAME")
print("Tables in LOTLINE_APP:")
for t in tables:
    tname = t['tabname']
    cols = query_all(f"SELECT COLNAME, TYPENAME, LENGTH, NULLS FROM SYSCAT.COLUMNS WHERE TABSCHEMA = 'LOTLINE_APP' AND TABNAME = '{tname}' ORDER BY COLNO")
    print(f"\n--- {tname} ---")
    for c in cols:
        print(f"  {c['colname']} ({c['typename']}) Nullable: {c['nulls']}")
