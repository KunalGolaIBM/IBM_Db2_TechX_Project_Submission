#!/usr/bin/env python3
"""
Seed Controlled Demonstration Events into Db2Sentinel AI.
Populates standard baseline events, brute-force probes, and off-hours exfiltration telemetry.
"""
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.backend.app.database import db_manager

def main():
    print("=" * 60)
    print("Seeding Controlled Demonstration Telemetry")
    print("=" * 60)
    db_manager.seed_demo_data()
    metrics = db_manager.get_metrics()
    print("✅ Controlled test events inserted into database:")
    print(f"   Total Events: {metrics.get('total_events')}")
    print(f"   Database Mode: {db_manager.active_mode}")
    print("=" * 60)

if __name__ == "__main__":
    main()
