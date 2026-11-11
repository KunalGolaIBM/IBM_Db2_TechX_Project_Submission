import os
import json
import sys
from pathlib import Path

# Add project root to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from app.services.ingestion_service import ingestion_service
from app.database.migrations import run_migrations

def run_full_ingestion():
    print("=" * 60)
    print("Cloud Loop — IBM Db2 Ingestion Pipeline")
    print("=" * 60)

    # 1. Ensure migrations are applied
    run_migrations()

    features_dir = backend_dir.parent / "src" / "features"

    datasets = [
        ("Google & LinkedIn Fresher Jobs", features_dir / "jobs" / "data" / "scraped-jobs.json"),
        ("Tech & Summer Internships", features_dir / "internships" / "data" / "scraped-internships.json"),
        ("Hackathons & Developer Events", features_dir / "events" / "data" / "scraped-events.json"),
        ("Global Student Programs", features_dir / "programs" / "data" / "scraped-programs.json"),
    ]

    total_processed = 0
    total_inserted = 0
    total_updated = 0
    total_rejected = 0

    for source_name, file_path in datasets:
        print(f"\nProcessing: {source_name}...")
        if not file_path.exists():
            print(f"  ⚠️ Warning: File not found: {file_path}")
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)

            print(f"  Loaded {len(raw_items)} records from disk.")
            # Ingest through the validation & normalization service
            result = ingestion_service.ingest_records(source=source_name, raw_items=raw_items)

            print(f"  ✅ Result: Inserted: {result['inserted']}, Updated: {result['updated']}, Rejected: {result['rejected']}")
            total_processed += result["processed"]
            total_inserted += result["inserted"]
            total_updated += result["updated"]
            total_rejected += result["rejected"]

        except Exception as e:
            print(f"  ❌ Error reading or ingesting {file_path}: {e}")

    print("\n" + "=" * 60)
    print(f"INGESTION COMPLETED: {total_processed} processed ({total_inserted} inserted, {total_updated} updated, {total_rejected} rejected)")
    print("=" * 60)

if __name__ == "__main__":
    run_full_ingestion()

