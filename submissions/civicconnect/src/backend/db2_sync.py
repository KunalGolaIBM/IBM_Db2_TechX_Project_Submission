"""
CivicConnect – IBM Db2 Sync Utility
Mirrors existing Firebase Firestore complaint documents into IBM Db2.
Run once to back-fill historical data or on a schedule for live sync.

Usage:
    python src/backend/db2_sync.py
"""

import json
import os
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Firebase Admin SDK (optional – only needed for back-fill sync)
# ---------------------------------------------------------------------------

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as fs_admin
    _FIREBASE_AVAILABLE = True
except ImportError:
    _FIREBASE_AVAILABLE = False
    print("[Sync] firebase-admin not installed; skipping Firestore import mode.")

# Ensure parent directories are on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.db2_repository import insert_complaint
from db.db2_setup import setup_schema, get_ibm_db_connection
import ibm_db


def sync_from_firestore():
    """
    Fetch all complaints from Firebase Firestore and upsert them into IBM Db2.
    Requires GOOGLE_APPLICATION_CREDENTIALS env var pointing to service account JSON.
    """
    if not _FIREBASE_AVAILABLE:
        print("[Sync] firebase-admin not available. Skipping Firestore sync.")
        return

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        print("[Sync] GOOGLE_APPLICATION_CREDENTIALS not set. Skipping.")
        return

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))

    db_ref = fs_admin.client()
    docs = db_ref.collection("complaints").stream()

    synced = 0
    skipped = 0
    for doc in docs:
        data = doc.to_dict()
        try:
            # Map Firestore field names to Db2 column naming convention
            mapped = {
                "id": data.get("id", doc.id),
                "complaint_id": data.get("complaintId", f"CCMS-SYNC-{doc.id[:8]}"),
                "user_id": data.get("userId", ""),
                "citizen_name": data.get("citizenName", ""),
                "citizen_email": data.get("citizenEmail", ""),
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "category": data.get("category", "Other Civic Issues"),
                "department_id": data.get("departmentId", ""),
                "department_name": data.get("departmentName", ""),
                "location": data.get("location", ""),
                "landmark": data.get("landmark", ""),
                "image_url": data.get("imageUrl", ""),
                "priority": data.get("priority", "medium"),
                "status": data.get("status", "Submitted"),
                "ai_summary": data.get("aiSummary", ""),
                "ai_keywords": data.get("aiKeywords", []),
            }
            insert_complaint(mapped)
            synced += 1
        except Exception as e:
            # Skip rows that already exist (duplicate complaint_id)
            if "duplicate" in str(e).lower() or "-803" in str(e):
                skipped += 1
            else:
                print(f"[Sync] Error syncing {doc.id}: {e}")

    print(f"[Sync] Complete. Synced={synced}, Skipped(duplicates)={skipped}")


def verify_sync():
    """Quick row-count verification against Db2."""
    conn = get_ibm_db_connection()
    try:
        stmt = ibm_db.exec_immediate(
            conn, "SELECT COUNT(*) AS CNT FROM CIVICCONNECT.COMPLAINTS"
        )
        row = ibm_db.fetch_assoc(stmt)
        print(f"[Verify] IBM Db2 COMPLAINTS table row count: {row['CNT']}")
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    print("[Sync] Setting up IBM Db2 schema...")
    setup_schema()
    print("[Sync] Starting Firestore → IBM Db2 sync...")
    sync_from_firestore()
    verify_sync()
