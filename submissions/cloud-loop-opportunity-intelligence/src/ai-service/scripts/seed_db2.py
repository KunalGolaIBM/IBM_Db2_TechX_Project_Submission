#!/usr/bin/env python3
"""
Seed Script for IBM Db2 & Haystack Vector Store
Cloud-Loop (IBM Db2 TechX Summit 2026 Submission)

Usage:
    python src/ai-service/scripts/seed_db2.py
    python src/ai-service/scripts/seed_db2.py --synthetic 50
    python src/ai-service/scripts/seed_db2.py --drop-expired
"""
import sys
import os
import json
import argparse
import logging
from datetime import datetime, date, timezone

# Ensure src/ai-service root is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
ai_service_root = os.path.abspath(os.path.join(script_dir, ".."))
if ai_service_root not in sys.path:
    sys.path.insert(0, ai_service_root)

from app.core.config import settings
from app.database.migrations import run_migrations
from app.repositories.opportunity_repository import opportunity_repo
from app.services.haystack_service import haystack_db2_service
from app.ai.embeddings import generate_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_db2")

def generate_synthetic_rows(count: int) -> list:
    """Generates synthetic rows for stress/load testing, explicitly labeled source='synthetic-demo'."""
    kinds = ["job", "internship", "event", "program", "certification"]
    domains = ["Cloud Computing", "AI/ML", "DevOps", "Database Engineering", "Full Stack"]
    synthetic_list = []
    for i in range(1, count + 1):
        kind = kinds[i % len(kinds)]
        domain = domains[i % len(domains)]
        opp_id = f"synthetic-{kind}-{i}"
        synthetic_list.append({
            "id": opp_id,
            "kind": kind,
            "slug": opp_id,
            "title": f"Synthetic Demo {domain} {kind.capitalize()} #{i}",
            "org": f"Demo Org {((i - 1) % 10) + 1}",
            "location": "Virtual / Remote",
            "mode": "remote",
            "deadline": "2026-12-31",
            "posted": "2026-08-01",
            "apply_url": "https://cloudloop.dev/demo",
            "source": "synthetic-demo",
            "skills": [domain, "Python", "SQL", "Cloud-Loop Demo"],
            "description": f"Automated synthetic benchmark opportunity for IBM Db2 scale testing #{i}.",
        })
    return synthetic_list

def run_seed(drop_expired: bool = True, synthetic_count: int = 0):
    logger.info("================================================================")
    logger.info("Cloud-Loop: IBM Db2 & Haystack Vector Store Seeding Pipeline")
    logger.info("================================================================")

    # 1. Apply Idempotent DDL Migrations
    logger.info("[Step 1/4] Applying idempotent DDL schema migrations...")
    run_migrations()

    # 2. Load Seed Data from Curated JSON
    seed_file = os.path.join(ai_service_root, "data", "seed", "opportunities.json")
    if not os.path.exists(seed_file):
        logger.error(f"Seed file not found at: {seed_file}")
        sys.exit(1)

    with open(seed_file, "r", encoding="utf-8") as f:
        opportunities = json.load(f)

    logger.info(f"[Step 2/4] Loaded {len(opportunities)} curated records from seed catalog.")

    # Drop or filter expired opportunities
    today_str = date.today().isoformat()
    active_curated = []
    expired_dropped = 0
    for opp in opportunities:
        deadline = opp.get("deadline")
        if drop_expired and deadline and deadline < today_str:
            expired_dropped += 1
            continue
        active_curated.append(opp)

    logger.info(f"Retained {len(active_curated)} active opportunities (dropped {expired_dropped} expired).")

    # Add synthetic demo records if requested
    all_to_load = list(active_curated)
    if synthetic_count > 0:
        syn_rows = generate_synthetic_rows(synthetic_count)
        all_to_load.extend(syn_rows)
        logger.info(f"Generated {len(syn_rows)} load-testing rows with source='synthetic-demo'.")

    # 3. Synchronize Relational Storage (CLOUDLOOP.OPPORTUNITIES)
    logger.info("[Step 3/4] Synchronizing relational database (CLOUDLOOP.OPPORTUNITIES)...")
    inserted = 0
    updated = 0
    for opp in all_to_load:
        existing = opportunity_repo.get_by_id(opp["id"])
        if existing:
            opportunity_repo.update(opp["id"], opp)
            updated += 1
        else:
            opportunity_repo.create(opp)
            inserted += 1

    logger.info(f"Relational storage synchronized: {inserted} inserted, {updated} updated.")

    # 4. Embed & Index into Vector Store (CLOUDLOOP.OPPORTUNITY_KB)
    logger.info("[Step 4/4] Generating 384-dim dense embeddings and indexing into OPPORTUNITY_KB...")
    store = haystack_db2_service.get_document_store()

    haystack_docs = []
    for opp in all_to_load:
        skills_str = ", ".join(opp.get("skills") or [])
        content = (
            f"{opp.get('title')} at {opp.get('org')}. "
            f"Kind: {opp.get('kind')}. Location: {opp.get('location')} ({opp.get('mode')}). "
            f"{opp.get('description', '')} "
            f"Required Skills: {skills_str}."
        )

        doc_meta = {
            "id": opp.get("id"),
            "slug": opp.get("slug"),
            "kind": opp.get("kind"),
            "title": opp.get("title"),
            "org": opp.get("org"),
            "location": opp.get("location"),
            "mode": opp.get("mode"),
            "deadline": opp.get("deadline"),
            "source": opp.get("source"),
            "apply_url": opp.get("apply_url"),
        }

        emb = generate_embedding(content)

        # Build Document object
        try:
            from haystack import Document
            doc = Document(id=opp.get("id"), content=content, meta=doc_meta, embedding=emb)
        except ImportError:
            doc = {"id": opp.get("id"), "content": content, "meta": doc_meta, "embedding": emb}

        haystack_docs.append(doc)

    indexed = haystack_db2_service.write_documents(haystack_docs, policy="OVERWRITE")
    logger.info(f"Vector store indexed: {indexed} documents written to OPPORTUNITY_KB.")

    # 5. Print Verification Counts
    counts = {}
    for opp in all_to_load:
        k = opp.get("kind", "unknown")
        counts[k] = counts.get(k, 0) + 1

    logger.info("================================================================")
    logger.info("IBM Db2 & Haystack Seeding Summary:")
    for kind, cnt in sorted(counts.items()):
        logger.info(f"  - {kind.capitalize():<15}: {cnt:>4} records")
    logger.info(f"Total Active Opportunities: {len(all_to_load)}")
    logger.info("Db2 & Vector Store status: READY FOR EVALUATION")
    logger.info("================================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed IBM Db2 and Haystack for Cloud-Loop")
    parser.add_argument("--synthetic", type=int, default=0, help="Generate N synthetic-demo benchmark rows")
    parser.add_argument("--keep-expired", action="store_true", help="Do not drop expired opportunities")
    args = parser.parse_args()

    run_seed(drop_expired=not args.keep_expired, synthetic_count=args.synthetic)
