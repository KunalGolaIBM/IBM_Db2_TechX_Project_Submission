"""
Db2 Environment and Schema Health Check.
Connects to IBM Db2 LUW, prints server version, schema statistics, and seed status.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import (
    get_db2_server_info,
    execute_query,
    table_exists,
    view_exists
)

TABLES = [
    "students",
    "concepts",
    "concept_prereqs",
    "documents",
    "chunks",
    "lessons",
    "questions",
    "attempts",
    "mastery",
    "mastery_history",
    "loop_events",
    "llm_cache",
    "lesson_images"
]


def check_db_health():
    print("=" * 65)
    print("IBM Db2 LUW Health & Environment Verification")
    print("=" * 65)
    
    info = get_db2_server_info()
    print(f"DBMS Engine : {info.get('dbms_name')}")
    print(f"Db2 Version : {info.get('dbms_ver')}")
    print(f"Database    : {info.get('db_name')}")
    print("-" * 65)

    print("Table Verification & Record Counts:")
    for tbl in TABLES:
        exists = table_exists(tbl)
        if exists:
            count_res = execute_query(f"SELECT COUNT(*) AS cnt FROM {tbl}")
            count = count_res[0]["cnt"] if count_res else 0
            print(f"  [OK] Table '{tbl:<16}' exists. Rows: {count}")
        else:
            print(f"  [FAIL] Table '{tbl:<16}' DOES NOT EXIST!")

    print("-" * 65)
    print("View Verification:")
    v_exists = view_exists("v_student_progress")
    print(f"  [{'OK' if v_exists else 'FAIL'}] View 'v_student_progress': {'Exists and active' if v_exists else 'NOT FOUND'}")

    print("-" * 65)
    # Check concept count and prerequisite count
    try:
        concepts = execute_query("SELECT concept_id, name, seq_order FROM concepts ORDER BY seq_order ASC")
        print(f"Total Concepts Registered: {len(concepts)}")
        for c in concepts:
            prereqs = execute_query(
                "SELECT c2.name FROM concept_prereqs cp JOIN concepts c2 ON cp.prereq_id = c2.concept_id WHERE cp.concept_id = ?",
                (c["concept_id"],)
            )
            p_names = [p["name"] for p in prereqs]
            prereq_str = ", ".join(p_names) if p_names else "(None - Root)"
            print(f"  {c['seq_order']}. {c['name']:<20} -> Needs: {prereq_str}")
    except Exception as e:
        print(f"Could not inspect concepts: {e}")

    print("=" * 65)
    print("Db2 check complete.")


if __name__ == "__main__":
    check_db_health()

