"""Load the SYNTHETIC demo dataset into IBM Db2 (skips refs that already exist).

Usage:  python scripts/seed_synthetic.py [--reset]
  --reset  delete previously seeded SYNTHETIC rows (SOURCE='SYNTHETIC') first
"""

import json
import sys
from datetime import datetime, timedelta

import _bootstrap
from civiclens.db import repository as repo
from civiclens.db.connection import session
from civiclens.domain.models import ComplaintCreate

DATA = _bootstrap.SUBMISSION_DIR / "data" / "synthetic" / "complaints_demo.json"


def reported_time(now: datetime, days_ago: int, hour: int) -> datetime:
    """Place a record ``days_ago`` days back at ``hour`` o'clock, never in the future."""
    reported = (now - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0, microsecond=0)
    while reported > now:
        reported -= timedelta(days=1)
    return reported


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    now = repo.utcnow()
    inserted = skipped = 0
    with session() as db:
        if "--reset" in sys.argv:
            removed = db.execute(
                "DELETE FROM {schema}.COMPLAINTS WHERE IS_SYNTHETIC = 1 AND SOURCE = 'SYNTHETIC'"
            )
            print(f"Removed {removed} previously seeded synthetic rows")
        existing = {
            r["external_ref"]
            for r in db.fetch_all(
                "SELECT EXTERNAL_REF FROM {schema}.COMPLAINTS "
                "WHERE IS_SYNTHETIC = 1 AND EXTERNAL_REF IS NOT NULL"
            )
        }
        with db.transaction():
            for rec in payload["records"]:
                if rec["external_ref"] in existing:
                    skipped += 1
                    continue
                rec = dict(rec)
                reported = reported_time(now, rec.pop("days_ago"), rec.pop("hour"))
                repo.insert_complaint(db, ComplaintCreate(**rec, reported_at=reported))
                inserted += 1
            repo.write_audit(
                db,
                actor_type="SYSTEM",
                actor_id="seed_synthetic",
                action="SEED_SYNTHETIC",
                output_summary=f"inserted={inserted} skipped={skipped}",
            )
    print(f"Synthetic seed complete: inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    main()
