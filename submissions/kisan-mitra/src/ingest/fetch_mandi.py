"""
Mandi Price Ingestion Pipeline - Kisan Mitra (किसान मित्र)
Connects to data.gov.in Agmarknet API to fetch real daily market arrival prices.
Gracefully falls back to local authenticated snapshot in data/mandi_prices_snapshot.csv.
"""

import sys
import os
import argparse
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config
from app.db_client import get_db_client

AGMARKNET_API_URL = "https://api.data.gov.in/resource/"

def clean_date(val: Any) -> str:
    """Normalize various date formats (DD/MM/YYYY or YYYY-MM-DD) to YYYY-MM-DD."""
    if not val or pd.isna(val):
        return datetime.date.today().isoformat()
    val_str = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(val_str, fmt).date().isoformat()
        except ValueError:
            pass
    return datetime.date.today().isoformat()

def clean_price(val: Any) -> Optional[float]:
    """Clean and cast price values to float."""
    if val is None or pd.isna(val):
        return None
    try:
        val_cleaned = str(val).replace(",", "").strip()
        f = float(val_cleaned)
        return round(f, 2)
    except (ValueError, TypeError):
        return None

def fetch_from_api(api_key: str, resource_id: str, state: str = "Uttar Pradesh", limit: int = 500) -> List[Dict[str, Any]]:
    """Fetch live data from data.gov.in API with pagination."""
    headers = {"User-Agent": "KisanMitra-AgmarknetIngest/1.0"}
    all_records: List[Dict[str, Any]] = []
    offset = 0
    batch_size = min(limit, 200)

    print(f"📡 Querying data.gov.in Agmarknet API for state: '{state}'...")
    
    while len(all_records) < limit:
        params = {
            "api-key": api_key,
            "format": "json",
            "offset": offset,
            "limit": batch_size,
        }
        if state:
            params["filters[state]"] = state
            
        endpoint = f"{AGMARKNET_API_URL}{resource_id}"
        try:
            resp = requests.get(endpoint, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️ API returned status {resp.status_code}: {resp.text[:200]}")
                break
                
            data = resp.json()
            records = data.get("records", [])
            if not records:
                break
                
            for rec in records:
                all_records.append({
                    "state": rec.get("state", "Uttar Pradesh").strip(),
                    "district": rec.get("district", "Unknown").strip(),
                    "market": rec.get("market", "Mandi").strip(),
                    "commodity": rec.get("commodity", "General").strip(),
                    "variety": rec.get("variety", "FAQ").strip(),
                    "arrival_date": clean_date(rec.get("arrival_date")),
                    "min_price": clean_price(rec.get("min_price")),
                    "max_price": clean_price(rec.get("max_price")),
                    "modal_price": clean_price(rec.get("modal_price")) or 0.0,
                })
            
            offset += len(records)
            if len(records) < batch_size:
                break
        except Exception as e:
            print(f"⚠️ Error while querying Agmarknet API: {e}")
            break

    return all_records

def load_from_fallback_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Load verified Agmarknet daily price data from local snapshot CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Fallback CSV not found at {csv_path}")
    
    print(f"📂 Loading verified Agmarknet mandi prices from fallback snapshot: {csv_path}")
    df = pd.read_csv(csv_path)
    records: List[Dict[str, Any]] = []
    
    for _, row in df.iterrows():
        modal = clean_price(row.get("modal_price"))
        if modal is None:
            continue
        records.append({
            "state": str(row.get("state", "Uttar Pradesh")).strip(),
            "district": str(row.get("district", "Unknown")).strip(),
            "market": str(row.get("market", "Mandi")).strip(),
            "commodity": str(row.get("commodity", "Produce")).strip(),
            "variety": str(row.get("variety", "FAQ")).strip(),
            "arrival_date": clean_date(row.get("arrival_date")),
            "min_price": clean_price(row.get("min_price")),
            "max_price": clean_price(row.get("max_price")),
            "modal_price": modal,
        })
    return records

def ingest_mandi_data(force_csv: bool = False, state: str = "Uttar Pradesh", dry_run: bool = False):
    """Main ingestion coordinator."""
    records: List[Dict[str, Any]] = []
    
    api_key = config.DATA_GOV_API_KEY.strip()
    resource_id = config.DATA_GOV_RESOURCE_ID.strip()
    
    if not force_csv and api_key and api_key != "your_data_gov_in_api_key_here":
        try:
            records = fetch_from_api(api_key, resource_id, state=state)
        except Exception as err:
            print(f"⚠️ API fetch encountered an issue ({err}). Falling back to snapshot CSV.")
    
    if not records:
        print("ℹ️ Using local verified Agmarknet snapshot dataset.")
        records = load_from_fallback_csv(config.MANDI_CSV_PATH)
        
    print(f"✅ Prepared {len(records)} mandi price records for ingestion.")
    
    if dry_run:
        print("🔍 Dry run enabled. Sample 3 records:")
        for r in records[:3]:
            print(f"   {r}")
        return

    # Ingest into IBM Db2 / client
    db = get_db_client(read_only=False)
    inserted = db.insert_mandi_prices(records)
    print(f"🌾 Successfully stored {inserted} mandi price records into IBM Db2 table MANDI_PRICES.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Agmarknet Mandi Prices into Db2")
    parser.add_argument("--force-csv", action="store_true", help="Force fallback CSV loading")
    parser.add_argument("--state", type=str, default="Uttar Pradesh", help="State to filter (default: Uttar Pradesh)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and inspect records without inserting")
    args = parser.parse_args()
    
    ingest_mandi_data(force_csv=args.force_csv, state=args.state, dry_run=args.dry_run)
