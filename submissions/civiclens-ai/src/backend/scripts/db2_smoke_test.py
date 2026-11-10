"""End-to-end IBM Db2 smoke test that produces *real* integration evidence.

Steps (all against the configured Db2 server, no mocks):
  1. connect with ibm_db and read server info
  2. run the idempotent migration and list CivicLens tables from SYSCAT.TABLES
  3. insert a SYNTHETIC complaint, read it back, run duplicate + hotspot queries
  4. write an AUDIT_LOG row, then delete the smoke-test rows inside a transaction

Writes a JSON evidence file to docs/evidence/ (no credentials included).

Usage:  python scripts/db2_smoke_test.py [--keep]
"""

import json
import sys
import time
from datetime import timedelta

import _bootstrap
from civiclens.config import get_settings
from civiclens.db import repository as repo
from civiclens.db.connection import session
from civiclens.db.migrate import migrate
from civiclens.domain.models import Category, ComplaintCreate

EVIDENCE_DIR = _bootstrap.SUBMISSION_DIR / "docs" / "evidence"


def main() -> int:
    keep = "--keep" in sys.argv
    settings = get_settings()
    evidence: dict = {
        "target_host": settings.db2_host,
        "database": settings.db2_database,
        "schema": settings.db2_schema,
        "tls": settings.db2_ssl_enabled,
        "steps": [],
    }

    def step(name: str, **data) -> None:
        evidence["steps"].append({"step": name, **data})
        print(f"[ok] {name}: {json.dumps(data, default=str)[:200]}")

    t0 = time.perf_counter()
    with session(settings) as db:
        step("connect", server=db.server_info())
        step("migrate", **migrate(db))
        tables = [
            r["tabname"]
            for r in db.fetch_all(
                "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TYPE = 'T' ORDER BY TABNAME",
                (db.schema,),
            )
        ]
        step("catalog_tables", tables=tables)

        payload = ComplaintCreate(
            category=Category.POTHOLE,
            title="[SMOKE TEST] Synthetic pothole",
            description="[SYNTHETIC] Smoke-test record created by db2_smoke_test.py",
            latitude=27.4964,
            longitude=77.6767,
            ward="Smoke Ward",
            severity=4,
            source="SMOKE_TEST",
            is_synthetic=True,
        )
        cid = repo.insert_complaint(db, payload)
        back = repo.get_complaint(db, cid)
        assert back is not None and back.title == payload.title and back.is_synthetic
        step("insert_and_read_back", complaint_id=cid, geo_cell=back.geo_cell, reported_at=back.reported_at)

        cid2 = repo.insert_complaint(db, payload)  # identical re-submission
        dups = repo.find_duplicate_candidates(
            db,
            category=back.category,
            title=back.title,
            description=back.description,
            latitude=back.latitude,
            longitude=back.longitude,
            reported_at=back.reported_at,
            exclude_id=cid2,
        )
        assert any(d.complaint_id == cid for d in dups), "duplicate query did not find the twin"
        step("duplicate_detection", query_id=cid2, candidates=[d.model_dump() for d in dups][:3])

        spots = repo.hotspots(
            db, since=repo.utcnow() - timedelta(days=1), min_count=2, category=Category.POTHOLE
        )
        assert any(s.geo_cell == back.geo_cell for s in spots)
        step("hotspot_aggregation", hotspots=[s.model_dump(mode="json") for s in spots][:3])

        aid = repo.write_audit(
            db,
            actor_type="SYSTEM",
            actor_id="smoke_test",
            action="SMOKE_TEST",
            input_payload={"complaint_ids": [cid, cid2]},
            output_summary="ok",
        )
        step("audit_write", audit_id=aid)

        if not keep:
            with db.transaction():
                n = db.execute("DELETE FROM {schema}.COMPLAINTS WHERE COMPLAINT_ID IN (?, ?)", (cid, cid2))
            step("cleanup_transaction", deleted_rows=n)

    evidence["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
    evidence["result"] = "PASS"
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE_DIR / "db2_smoke_test_result.json"
    out.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"PASS - evidence written to {out.relative_to(_bootstrap.SUBMISSION_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
