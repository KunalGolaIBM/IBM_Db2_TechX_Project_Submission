#!/usr/bin/env python3
"""Generate db/seed/seed_data.sql — logically consistent RecallGuard AI demo data.

All names are fictional. The generator is deterministic (no randomness), so the
acceptance tests can assert exact traceability results.

Scenarios
  1. TOM-2026-041  tomato puree, Salmonella — MAIN LIVE DEMO (incident created
     live by the demo button; only supply-chain records are seeded here).
     Near-miss lots TOM-2026-042 / TOM-2026-038 feed the SAME product SKUs and
     even the SAME retailers, but must never enter the recall scope.
  2. CHI-2026-017  chili powder, Salmonella — historical incident (completed
     recall is generated at bootstrap by running the real pipeline).
  3. MLK-2026-233  milk powder, suspected Cronobacter — open investigation.

Run:  python db/seed/generate_seed.py   (writes seed_data.sql next to this file)
"""
from __future__ import annotations

import datetime as dt
from collections import OrderedDict
from pathlib import Path

OUT = Path(__file__).with_name("seed_data.sql")


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (dt.date,)):
        return f"'{v.isoformat()}'"
    return "'" + str(v).replace("'", "''") + "'"


def insert(table: str, cols: list[str], rows: list[tuple]) -> list[str]:
    return [f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(q(v) for v in r)})" for r in rows]


# ---------------------------------------------------------------- master data
SUPPLIERS = [
    ("SUP-001", "Valle Rosso Tomato Cooperative", "India", "Maharashtra", "qa@vallerosso.example", "+91-20-5550-0101", "FSSC 22000", "STANDARD"),
    ("SUP-002", "Deccan Spice Traders", "India", "Telangana", "quality@deccanspice.example", "+91-40-5550-0202", "ISO 22000", "ELEVATED"),
    ("SUP-003", "Sahyadri Dairy Farms", "India", "Maharashtra", "qc@sahyadridairy.example", "+91-20-5550-0303", "FSSC 22000", "STANDARD"),
    ("SUP-004", "Malwa Wheat Millers", "India", "Madhya Pradesh", "mill@malwawheat.example", "+91-731-555-0404", "BRCGS", "LOW"),
    ("SUP-005", "Konkan Edible Oils", "India", "Goa", "qa@konkanoils.example", "+91-832-555-0505", "ISO 22000", "LOW"),
    ("SUP-006", "Narmada Onion Growers", "India", "Madhya Pradesh", "ops@narmadaonion.example", "+91-755-555-0606", "GLOBALG.A.P.", "STANDARD"),
    ("SUP-007", "Kaveri Salt & Sugar Co", "India", "Karnataka", "qa@kaverisalt.example", "+91-80-5550-0707", "FSSC 22000", "LOW"),
    ("SUP-008", "Nilgiri Herb Estates", "India", "Tamil Nadu", "herbs@nilgiri.example", "+91-423-555-0808", "Organic India", "STANDARD"),
    ("SUP-009", "Ganga Fresh Paneer Co", "India", "Uttar Pradesh", "qa@gangapaneer.example", "+91-522-555-0909", "FSSC 22000", "STANDARD"),
    ("SUP-010", "Western Ghats Garlic Collective", "India", "Karnataka", "garlic@wghats.example", "+91-824-555-1010", "GLOBALG.A.P.", "STANDARD"),
    ("SUP-011", "Thar Pulses & Grains", "India", "Rajasthan", "trade@tharpulses.example", "+91-291-555-1111", "ISO 22000", "LOW"),
    ("SUP-012", "Coastal Potato Farms", "India", "Gujarat", "qa@coastalpotato.example", "+91-79-5550-1212", "BRCGS", "STANDARD"),
]

INGREDIENTS = [
    ("ING-TOM", "Tomato puree (28 Brix)", "Vegetable puree", 0),
    ("ING-CHI", "Red chili powder", "Spice", 0),
    ("ING-TUR", "Turmeric powder", "Spice", 0),
    ("ING-MLK", "Skimmed milk powder", "Dairy", 1),
    ("ING-CRM", "Fresh cream 35%", "Dairy", 1),
    ("ING-FLR", "Wheat flour (maida)", "Cereal", 1),
    ("ING-OIL", "Refined sunflower oil", "Oil", 0),
    ("ING-ONI", "Onion paste", "Vegetable puree", 0),
    ("ING-SLT", "Iodised salt", "Mineral", 0),
    ("ING-SUG", "Refined sugar", "Sweetener", 0),
    ("ING-HRB", "Dried oregano & basil", "Herb", 0),
    ("ING-PNR", "Paneer cubes", "Dairy", 1),
    ("ING-GAR", "Garlic paste", "Vegetable puree", 0),
    ("ING-LEN", "Red lentils (masoor)", "Pulse", 0),
    ("ING-POT", "Potato flakes", "Vegetable", 0),
]

FACILITIES = [
    ("FAC-PUN", "Pune Sauce Works", "Pune", "Maharashtra", "LIC-MH-PUN-0041"),
    ("FAC-NSK", "Nashik Ready Meals Plant", "Nashik", "Maharashtra", "LIC-MH-NSK-0112"),
    ("FAC-IND", "Indore Snacks Unit", "Indore", "Madhya Pradesh", "LIC-MP-IND-0077"),
    ("FAC-HSR", "Hosur Dairy & Bakery", "Hosur", "Tamil Nadu", "LIC-TN-HSR-0203"),
]

# lot_id, ingredient, supplier, facility, kg, received, expiry, coa_ref
LOTS = [
    ("TOM-2026-038", "ING-TOM", "SUP-001", "FAC-PUN", 2000, "2026-09-15", "2027-03-15", "COA-VR-2026-0915"),
    ("TOM-2026-041", "ING-TOM", "SUP-001", "FAC-PUN", 2400, "2026-10-02", "2027-04-02", "COA-VR-2026-1001"),
    ("TOM-2026-042", "ING-TOM", "SUP-001", "FAC-PUN", 2200, "2026-10-09", "2027-04-09", "COA-VR-2026-1008"),
    ("CHI-2026-017", "ING-CHI", "SUP-002", "FAC-IND", 600, "2026-08-28", "2027-08-28", "COA-DS-2026-0827"),
    ("CHI-2026-018", "ING-CHI", "SUP-002", "FAC-IND", 650, "2026-09-30", "2027-09-30", "COA-DS-2026-0929"),
    ("TUR-2026-009", "ING-TUR", "SUP-002", "FAC-IND", 300, "2026-08-20", "2027-08-20", "COA-DS-2026-0819"),
    ("MLK-2026-233", "ING-MLK", "SUP-003", "FAC-HSR", 1500, "2026-10-14", "2027-04-14", "COA-SD-2026-1013"),
    ("MLK-2026-234", "ING-MLK", "SUP-003", "FAC-HSR", 1500, "2026-10-19", "2027-04-19", "COA-SD-2026-1018"),
    ("CRM-2026-051", "ING-CRM", "SUP-003", "FAC-NSK", 800, "2026-10-05", "2026-11-05", "COA-SD-2026-1004"),
    ("CRM-2026-052", "ING-CRM", "SUP-003", "FAC-PUN", 600, "2026-10-22", "2026-11-22", "COA-SD-2026-1021"),
    ("FLR-2026-120", "ING-FLR", "SUP-004", "FAC-HSR", 5000, "2026-10-10", "2027-01-10", "COA-MW-2026-1009"),
    ("FLR-2026-121", "ING-FLR", "SUP-004", "FAC-HSR", 5000, "2026-10-17", "2027-01-17", "COA-MW-2026-1016"),
    ("OIL-2026-077", "ING-OIL", "SUP-005", "FAC-PUN", 3000, "2026-09-25", "2027-09-25", "COA-KO-2026-0924"),
    ("OIL-2026-078", "ING-OIL", "SUP-005", "FAC-IND", 3000, "2026-08-25", "2027-08-25", "COA-KO-2026-0824"),
    ("ONI-2026-064", "ING-ONI", "SUP-006", "FAC-PUN", 900, "2026-10-01", "2027-01-01", "COA-NO-2026-0930"),
    ("ONI-2026-065", "ING-ONI", "SUP-006", "FAC-NSK", 900, "2026-10-15", "2027-01-15", "COA-NO-2026-1014"),
    ("SLT-2026-030", "ING-SLT", "SUP-007", "FAC-PUN", 1000, "2026-08-10", "2028-08-10", "COA-KS-2026-0809"),
    ("SUG-2026-028", "ING-SUG", "SUP-007", "FAC-HSR", 2000, "2026-08-12", "2028-08-12", "COA-KS-2026-0811"),
    ("HRB-2026-012", "ING-HRB", "SUP-008", "FAC-PUN", 150, "2026-09-20", "2027-09-20", "COA-NH-2026-0919"),
    ("HRB-2026-013", "ING-HRB", "SUP-008", "FAC-IND", 150, "2026-10-12", "2027-10-12", "COA-NH-2026-1011"),
    ("PNR-2026-090", "ING-PNR", "SUP-009", "FAC-NSK", 700, "2026-10-07", "2026-10-21", "COA-GP-2026-1006"),
    ("PNR-2026-091", "ING-PNR", "SUP-009", "FAC-NSK", 700, "2026-10-21", "2026-11-04", "COA-GP-2026-1020"),
    ("GAR-2026-044", "ING-GAR", "SUP-010", "FAC-PUN", 400, "2026-09-28", "2026-12-28", "COA-WG-2026-0927"),
    ("GAR-2026-045", "ING-GAR", "SUP-010", "FAC-NSK", 400, "2026-10-16", "2027-01-16", "COA-WG-2026-1015"),
    ("LEN-2026-019", "ING-LEN", "SUP-011", "FAC-NSK", 2500, "2026-09-18", "2027-09-18", "COA-TP-2026-0917"),
    ("POT-2026-055", "ING-POT", "SUP-012", "FAC-IND", 2000, "2026-08-26", "2027-02-26", "COA-CP-2026-0825"),
    ("POT-2026-056", "ING-POT", "SUP-012", "FAC-IND", 2000, "2026-10-08", "2027-04-08", "COA-CP-2026-1007"),
]

PRODUCTS = [
    ("P-PSC", "Classic Pasta Sauce", "Rossa Kitchen", "Sauces", "500 g jar", "8901000000017"),
    ("P-MAR", "Marinara Sauce", "Rossa Kitchen", "Sauces", "400 g jar", "8901000000024"),
    ("P-PZS", "Pizza Sauce", "Rossa Kitchen", "Sauces", "300 g pouch", "8901000000031"),
    ("P-KET", "Tomato Ketchup", "Rossa Kitchen", "Condiments", "1 kg bottle", "8901000000048"),
    ("P-TSP", "Creamy Tomato Soup", "Rossa Kitchen", "Soups", "450 ml carton", "8901000000055"),
    ("P-PTM", "Paneer Tikka Masala Ready Meal", "Ghar Ka Swad", "Ready meals", "300 g tray", "8901000000062"),
    ("P-DAL", "Dal Tadka Ready Meal", "Ghar Ka Swad", "Ready meals", "300 g tray", "8901000000079"),
    ("P-PNB", "Paneer Butter Masala Ready Meal", "Ghar Ka Swad", "Ready meals", "300 g tray", "8901000000086"),
    ("P-ALO", "Aloo Masala Chips", "CrunchKart", "Snacks", "150 g pack", "8901000000093"),
    ("P-MSN", "Masala Lentil Namkeen", "CrunchKart", "Snacks", "200 g pack", "8901000000109"),
    ("P-PER", "Peri Peri Potato Wedges", "CrunchKart", "Frozen snacks", "500 g bag", "8901000000116"),
    ("P-CHT", "Chili Garlic Chutney", "Rossa Kitchen", "Condiments", "200 g jar", "8901000000123"),
    ("P-HSB", "Italian Herb Seasoning", "Rossa Kitchen", "Seasonings", "50 g shaker", "8901000000130"),
    ("P-MLB", "Milk Bread", "Hosur Bake House", "Bakery", "400 g loaf", "8901000000147"),
    ("P-CRK", "Cream Crackers", "Hosur Bake House", "Bakery", "250 g pack", "8901000000154"),
    ("P-BIS", "Butter Biscuits", "Hosur Bake House", "Bakery", "200 g pack", "8901000000161"),
    ("P-GNA", "Garlic Naan (frozen)", "Ghar Ka Swad", "Frozen bakery", "4 pc pack", "8901000000178"),
]

WAREHOUSES = [
    ("WH-PUN1", "Pune Central DC", "Pune", "Maharashtra", "AMBIENT"),
    ("WH-MUM1", "Bhiwandi Mega DC", "Mumbai", "Maharashtra", "AMBIENT"),
    ("WH-NSK1", "Nashik Chilled Hub", "Nashik", "Maharashtra", "CHILLED"),
    ("WH-DEL1", "Gurugram North DC", "Gurugram", "Haryana", "CHILLED"),
    ("WH-KOL1", "Kolkata East Hub", "Kolkata", "West Bengal", "CHILLED"),
    ("WH-HYD1", "Hyderabad South DC", "Hyderabad", "Telangana", "AMBIENT"),
    ("WH-BLR1", "Hoskote Bengaluru DC", "Bengaluru", "Karnataka", "AMBIENT"),
    ("WH-CHN1", "Chennai Cold Chain Hub", "Chennai", "Tamil Nadu", "FROZEN"),
    ("WH-IND1", "Indore Central DC", "Indore", "Madhya Pradesh", "AMBIENT"),
    ("WH-AHM1", "Ahmedabad West DC", "Ahmedabad", "Gujarat", "AMBIENT"),
]

DISTRIBUTORS = [
    ("DST-01", "WestFresh Distribution", "Mumbai", "dispatch@westfresh.example"),
    ("DST-02", "Sahyadri FMCG Logistics", "Pune", "ops@sahyadrifmcg.example"),
    ("DST-03", "NorthStar Foods Distribution", "Delhi", "recalls@northstarfoods.example"),
    ("DST-04", "Southern Cart Distributors", "Bengaluru", "ops@southerncart.example"),
    ("DST-05", "Deccan Retail Supply", "Hyderabad", "supply@deccanretail.example"),
    ("DST-06", "Malwa Trade Links", "Indore", "trade@malwalinks.example"),
]

RETAILERS = [
    ("RTL-PUN-01", "FreshMart Koregaon Park", "SUPERMARKET", "Pune", "Maharashtra"),
    ("RTL-PUN-02", "DailyBasket Baner", "SUPERMARKET", "Pune", "Maharashtra"),
    ("RTL-PUN-03", "QuickStop Kothrud", "CONVENIENCE", "Pune", "Maharashtra"),
    ("RTL-PUN-04", "GreenLeaf Hypermarket Hadapsar", "HYPERMARKET", "Pune", "Maharashtra"),
    ("RTL-PUN-05", "CartNow Online (Pune FC)", "ONLINE", "Pune", "Maharashtra"),
    ("RTL-MUM-01", "FreshMart Andheri", "SUPERMARKET", "Mumbai", "Maharashtra"),
    ("RTL-MUM-02", "Bayview Grocers Bandra", "SUPERMARKET", "Mumbai", "Maharashtra"),
    ("RTL-MUM-03", "MetroMart Thane", "HYPERMARKET", "Thane", "Maharashtra"),
    ("RTL-MUM-04", "Slice Street Pizzeria Group", "FOODSERVICE", "Mumbai", "Maharashtra"),
    ("RTL-NSK-01", "Godavari Supermart Nashik", "SUPERMARKET", "Nashik", "Maharashtra"),
    ("RTL-HYD-01", "Charminar Fresh Hyderabad", "SUPERMARKET", "Hyderabad", "Telangana"),
    ("RTL-HYD-02", "HiTech City Grocers", "SUPERMARKET", "Hyderabad", "Telangana"),
    ("RTL-HYD-03", "QuickStop Secunderabad", "CONVENIENCE", "Secunderabad", "Telangana"),
    ("RTL-HYD-04", "MegaValue Hypermarket Kukatpally", "HYPERMARKET", "Hyderabad", "Telangana"),
    ("RTL-HYD-05", "Banjara Daily Needs", "CONVENIENCE", "Hyderabad", "Telangana"),
    ("RTL-DEL-01", "Capital Fresh Saket", "SUPERMARKET", "New Delhi", "Delhi"),
    ("RTL-DEL-02", "NCR Value Mart Noida", "HYPERMARKET", "Noida", "Uttar Pradesh"),
    ("RTL-DEL-03", "QuickStop Gurugram", "CONVENIENCE", "Gurugram", "Haryana"),
    ("RTL-DEL-04", "Lodhi Gourmet Store", "SUPERMARKET", "New Delhi", "Delhi"),
    ("RTL-KOL-01", "Hooghly Fresh Park Street", "SUPERMARKET", "Kolkata", "West Bengal"),
    ("RTL-KOL-02", "Salt Lake Daily Mart", "SUPERMARKET", "Kolkata", "West Bengal"),
    ("RTL-BLR-01", "Namma Fresh Indiranagar", "SUPERMARKET", "Bengaluru", "Karnataka"),
    ("RTL-BLR-02", "Silicon Basket Whitefield", "HYPERMARKET", "Bengaluru", "Karnataka"),
    ("RTL-BLR-03", "CartNow Online (Bengaluru FC)", "ONLINE", "Bengaluru", "Karnataka"),
    ("RTL-CHN-01", "Marina Fresh Adyar", "SUPERMARKET", "Chennai", "Tamil Nadu"),
    ("RTL-CHN-02", "Coromandel Hypermart", "HYPERMARKET", "Chennai", "Tamil Nadu"),
    ("RTL-IND-01", "Rajwada Supermart", "SUPERMARKET", "Indore", "Madhya Pradesh"),
    ("RTL-IND-02", "Malwa Daily Basket", "CONVENIENCE", "Indore", "Madhya Pradesh"),
    ("RTL-AHM-01", "Sabarmati Fresh", "SUPERMARKET", "Ahmedabad", "Gujarat"),
    ("RTL-AHM-02", "Navrang Hypermarket", "HYPERMARKET", "Ahmedabad", "Gujarat"),
]

# batch_id, facility, type, product, description, qty, unit, production_date, best_before_days
BATCHES = [
    # ---- Scenario 1: TOM-2026-041 (contaminated) ----
    ("PB-2026-1001", "FAC-PUN", "INTERMEDIATE", None, "Tomato base concentrate (from TOM-2026-041)", 1500, "KG", "2026-10-04", 60),
    ("PB-2026-1002", "FAC-PUN", "FINISHED", "P-PSC", "Classic Pasta Sauce 500 g", 9000, "UNITS", "2026-10-05", 365),
    ("PB-2026-1003", "FAC-PUN", "INTERMEDIATE", None, "Masala gravy base", 800, "KG", "2026-10-06", 30),
    ("PB-2026-1004", "FAC-PUN", "FINISHED", "P-MAR", "Marinara Sauce 400 g", 6000, "UNITS", "2026-10-07", 365),
    ("PB-2026-1005", "FAC-PUN", "FINISHED", "P-PZS", "Pizza Sauce 300 g", 8000, "UNITS", "2026-10-07", 270),
    ("PB-2026-1006", "FAC-PUN", "FINISHED", "P-PZS", "Pizza Sauce 300 g (second run)", 5000, "UNITS", "2026-10-12", 270),
    ("PB-2026-1007", "FAC-NSK", "FINISHED", "P-PTM", "Paneer Tikka Masala Ready Meal 300 g", 7000, "UNITS", "2026-10-09", 120),
    ("PB-2026-1008", "FAC-PUN", "FINISHED", "P-TSP", "Creamy Tomato Soup 450 ml", 4000, "UNITS", "2026-10-10", 180),
    ("PB-2026-1009", "FAC-NSK", "FINISHED", "P-DAL", "Dal Tadka Ready Meal 300 g", 3000, "UNITS", "2026-10-11", 120),
    # ---- Near-miss: same supplier / same SKUs, clean lots ----
    ("PB-2026-0950", "FAC-PUN", "FINISHED", "P-PSC", "Classic Pasta Sauce 500 g", 8500, "UNITS", "2026-09-20", 365),
    ("PB-2026-0951", "FAC-PUN", "FINISHED", "P-TSP", "Creamy Tomato Soup 450 ml", 3500, "UNITS", "2026-09-21", 180),
    ("PB-2026-1010", "FAC-PUN", "INTERMEDIATE", None, "Tomato base concentrate (from TOM-2026-042)", 1400, "KG", "2026-10-11", 60),
    ("PB-2026-1011", "FAC-PUN", "FINISHED", "P-MAR", "Marinara Sauce 400 g", 6000, "UNITS", "2026-10-13", 365),
    ("PB-2026-1012", "FAC-PUN", "FINISHED", "P-KET", "Tomato Ketchup 1 kg", 10000, "UNITS", "2026-10-14", 365),
    ("PB-2026-1013", "FAC-PUN", "FINISHED", "P-PSC", "Classic Pasta Sauce 500 g", 8000, "UNITS", "2026-10-15", 365),
    # ---- Scenario 2: CHI-2026-017 ----
    ("PB-2026-0960", "FAC-IND", "INTERMEDIATE", None, "Masala seasoning mix (from CHI-2026-017)", 500, "KG", "2026-09-02", 180),
    ("PB-2026-0961", "FAC-IND", "FINISHED", "P-ALO", "Aloo Masala Chips 150 g", 12000, "UNITS", "2026-09-04", 150),
    ("PB-2026-0962", "FAC-IND", "FINISHED", "P-MSN", "Masala Lentil Namkeen 200 g", 9000, "UNITS", "2026-09-05", 150),
    ("PB-2026-0963", "FAC-PUN", "FINISHED", "P-CHT", "Chili Garlic Chutney 200 g", 4000, "UNITS", "2026-09-06", 270),
    # ---- Scenario 3: MLK-2026-233 ----
    ("PB-2026-1020", "FAC-HSR", "FINISHED", "P-MLB", "Milk Bread 400 g", 6000, "UNITS", "2026-10-20", 7),
    ("PB-2026-1021", "FAC-HSR", "FINISHED", "P-CRK", "Cream Crackers 250 g", 8000, "UNITS", "2026-10-21", 240),
    ("PB-2026-1022", "FAC-HSR", "FINISHED", "P-BIS", "Butter Biscuits 200 g", 9000, "UNITS", "2026-10-22", 240),
    # ---- Background production ----
    ("PB-2026-1030", "FAC-HSR", "FINISHED", "P-BIS", "Butter Biscuits 200 g", 9500, "UNITS", "2026-10-25", 240),
    ("PB-2026-1031", "FAC-IND", "FINISHED", "P-PER", "Peri Peri Potato Wedges 500 g", 6000, "UNITS", "2026-10-14", 300),
    ("PB-2026-1032", "FAC-IND", "FINISHED", "P-HSB", "Italian Herb Seasoning 50 g", 7000, "UNITS", "2026-10-16", 540),
    ("PB-2026-1033", "FAC-NSK", "FINISHED", "P-PNB", "Paneer Butter Masala Ready Meal 300 g", 5000, "UNITS", "2026-10-23", 120),
    ("PB-2026-1034", "FAC-HSR", "FINISHED", "P-GNA", "Garlic Naan (frozen) 4 pc", 6000, "UNITS", "2026-10-24", 180),
    ("PB-2026-1035", "FAC-HSR", "FINISHED", "P-MLB", "Milk Bread 400 g", 6000, "UNITS", "2026-10-28", 7),
    ("PB-2026-1037", "FAC-IND", "INTERMEDIATE", None, "Masala seasoning mix (from CHI-2026-018)", 500, "KG", "2026-10-18", 180),
    ("PB-2026-1036", "FAC-IND", "FINISHED", "P-ALO", "Aloo Masala Chips 150 g", 12000, "UNITS", "2026-10-20", 150),
    ("PB-2026-1038", "FAC-IND", "FINISHED", "P-MSN", "Masala Lentil Namkeen 200 g", 9000, "UNITS", "2026-10-21", 150),
    ("PB-2026-1039", "FAC-NSK", "FINISHED", "P-DAL", "Dal Tadka Ready Meal 300 g", 4000, "UNITS", "2026-10-24", 120),
    ("PB-2026-1040", "FAC-PUN", "FINISHED", "P-TSP", "Creamy Tomato Soup 450 ml", 4000, "UNITS", "2026-10-26", 180),
]

# (input_ref, output_batch, qty, unit, step, record_status)
TRANSFORMS = [
    ("TOM-2026-041", "PB-2026-1001", 1400, "KG", "Concentration & pasteurisation", "VERIFIED"),
    ("SLT-2026-030", "PB-2026-1001", 20, "KG", "Concentration & pasteurisation", "VERIFIED"),
    ("HRB-2026-012", "PB-2026-1001", 10, "KG", "Concentration & pasteurisation", "VERIFIED"),
    ("TOM-2026-041", "PB-2026-1002", 900, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("OIL-2026-077", "PB-2026-1002", 150, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("GAR-2026-044", "PB-2026-1002", 40, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("HRB-2026-012", "PB-2026-1002", 12, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("PB-2026-1001", "PB-2026-1003", 400, "KG", "Gravy base blending", "VERIFIED"),
    ("ONI-2026-064", "PB-2026-1003", 250, "KG", "Gravy base blending", "VERIFIED"),
    ("GAR-2026-044", "PB-2026-1003", 40, "KG", "Gravy base blending", "VERIFIED"),
    ("CHI-2026-018", "PB-2026-1003", 15, "KG", "Gravy base blending", "VERIFIED"),
    ("TUR-2026-009", "PB-2026-1003", 8, "KG", "Gravy base blending", "VERIFIED"),
    ("OIL-2026-077", "PB-2026-1003", 90, "KG", "Gravy base blending", "VERIFIED"),
    ("PB-2026-1001", "PB-2026-1004", 350, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("HRB-2026-012", "PB-2026-1004", 8, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("OIL-2026-077", "PB-2026-1004", 60, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("PB-2026-1001", "PB-2026-1005", 300, "KG", "Sauce cooking & pouch fill", "VERIFIED"),
    ("SLT-2026-030", "PB-2026-1005", 6, "KG", "Sauce cooking & pouch fill", "VERIFIED"),
    # manual reconciliation entry — the uncertainty the verification agent must surface
    ("PB-2026-1001", "PB-2026-1006", 250, "KG", "Sauce cooking & pouch fill (manual log)", "UNVERIFIED"),
    ("PB-2026-1003", "PB-2026-1007", 500, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("PNR-2026-090", "PB-2026-1007", 420, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("CRM-2026-051", "PB-2026-1007", 140, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("PB-2026-1001", "PB-2026-1008", 200, "KG", "Soup cooking & aseptic fill", "VERIFIED"),
    ("CRM-2026-051", "PB-2026-1008", 120, "KG", "Soup cooking & aseptic fill", "VERIFIED"),
    ("SUG-2026-028", "PB-2026-1008", 20, "KG", "Soup cooking & aseptic fill", "VERIFIED"),
    ("PB-2026-1003", "PB-2026-1009", 150, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("LEN-2026-019", "PB-2026-1009", 450, "KG", "Ready meal assembly & retort", "VERIFIED"),
    # near-miss
    ("TOM-2026-038", "PB-2026-0950", 1000, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("OIL-2026-077", "PB-2026-0950", 140, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("TOM-2026-038", "PB-2026-0951", 600, "KG", "Soup cooking & aseptic fill", "VERIFIED"),
    ("TOM-2026-042", "PB-2026-1010", 1300, "KG", "Concentration & pasteurisation", "VERIFIED"),
    ("SLT-2026-030", "PB-2026-1010", 18, "KG", "Concentration & pasteurisation", "VERIFIED"),
    ("PB-2026-1010", "PB-2026-1011", 350, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("HRB-2026-012", "PB-2026-1011", 8, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("TOM-2026-042", "PB-2026-1012", 800, "KG", "Ketchup cooking & bottling", "VERIFIED"),
    ("SUG-2026-028", "PB-2026-1012", 180, "KG", "Ketchup cooking & bottling", "VERIFIED"),
    ("PB-2026-1010", "PB-2026-1013", 600, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    ("GAR-2026-044", "PB-2026-1013", 35, "KG", "Sauce cooking & hot-fill", "VERIFIED"),
    # scenario 2
    ("CHI-2026-017", "PB-2026-0960", 300, "KG", "Seasoning blending", "VERIFIED"),
    ("TUR-2026-009", "PB-2026-0960", 40, "KG", "Seasoning blending", "VERIFIED"),
    ("SLT-2026-030", "PB-2026-0960", 120, "KG", "Seasoning blending", "VERIFIED"),
    ("PB-2026-0960", "PB-2026-0961", 260, "KG", "Frying & seasoning", "VERIFIED"),
    ("POT-2026-055", "PB-2026-0961", 1500, "KG", "Frying & seasoning", "VERIFIED"),
    ("OIL-2026-078", "PB-2026-0961", 600, "KG", "Frying & seasoning", "VERIFIED"),
    ("PB-2026-0960", "PB-2026-0962", 220, "KG", "Frying & seasoning", "VERIFIED"),
    ("LEN-2026-019", "PB-2026-0962", 1200, "KG", "Frying & seasoning", "VERIFIED"),
    ("CHI-2026-017", "PB-2026-0963", 120, "KG", "Chutney cooking & hot-fill", "VERIFIED"),
    ("GAR-2026-044", "PB-2026-0963", 80, "KG", "Chutney cooking & hot-fill", "VERIFIED"),
    # scenario 3
    ("FLR-2026-120", "PB-2026-1020", 2200, "KG", "Mixing, proofing & baking", "VERIFIED"),
    ("MLK-2026-233", "PB-2026-1020", 90, "KG", "Mixing, proofing & baking", "VERIFIED"),
    ("SUG-2026-028", "PB-2026-1020", 80, "KG", "Mixing, proofing & baking", "VERIFIED"),
    ("FLR-2026-120", "PB-2026-1021", 1800, "KG", "Sheeting & baking", "VERIFIED"),
    ("MLK-2026-233", "PB-2026-1021", 70, "KG", "Sheeting & baking", "VERIFIED"),
    ("FLR-2026-121", "PB-2026-1022", 1600, "KG", "Mixing & baking", "VERIFIED"),
    ("MLK-2026-234", "PB-2026-1022", 80, "KG", "Mixing & baking", "VERIFIED"),
    # background
    ("FLR-2026-121", "PB-2026-1030", 1700, "KG", "Mixing & baking", "VERIFIED"),
    ("MLK-2026-234", "PB-2026-1030", 85, "KG", "Mixing & baking", "VERIFIED"),
    ("SUG-2026-028", "PB-2026-1030", 300, "KG", "Mixing & baking", "VERIFIED"),
    ("POT-2026-056", "PB-2026-1031", 2000, "KG", "Cutting, seasoning & freezing", "VERIFIED"),
    ("CHI-2026-018", "PB-2026-1031", 30, "KG", "Cutting, seasoning & freezing", "VERIFIED"),
    ("HRB-2026-013", "PB-2026-1032", 120, "KG", "Herb blending & packing", "VERIFIED"),
    ("PNR-2026-091", "PB-2026-1033", 380, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("ONI-2026-065", "PB-2026-1033", 200, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("FLR-2026-121", "PB-2026-1034", 900, "KG", "Dough, baking & freezing", "VERIFIED"),
    ("GAR-2026-045", "PB-2026-1034", 60, "KG", "Dough, baking & freezing", "VERIFIED"),
    ("FLR-2026-121", "PB-2026-1035", 2200, "KG", "Mixing, proofing & baking", "VERIFIED"),
    ("MLK-2026-234", "PB-2026-1035", 90, "KG", "Mixing, proofing & baking", "VERIFIED"),
    ("CHI-2026-018", "PB-2026-1037", 280, "KG", "Seasoning blending", "VERIFIED"),
    ("TUR-2026-009", "PB-2026-1037", 40, "KG", "Seasoning blending", "VERIFIED"),
    ("PB-2026-1037", "PB-2026-1036", 260, "KG", "Frying & seasoning", "VERIFIED"),
    ("POT-2026-056", "PB-2026-1036", 1500, "KG", "Frying & seasoning", "VERIFIED"),
    ("OIL-2026-078", "PB-2026-1036", 600, "KG", "Frying & seasoning", "VERIFIED"),
    ("PB-2026-1037", "PB-2026-1038", 220, "KG", "Frying & seasoning", "VERIFIED"),
    ("LEN-2026-019", "PB-2026-1038", 1100, "KG", "Frying & seasoning", "VERIFIED"),
    ("LEN-2026-019", "PB-2026-1039", 500, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("ONI-2026-065", "PB-2026-1039", 120, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("GAR-2026-045", "PB-2026-1039", 30, "KG", "Ready meal assembly & retort", "VERIFIED"),
    ("PB-2026-1010", "PB-2026-1040", 220, "KG", "Soup cooking & aseptic fill", "VERIFIED"),
    ("CRM-2026-052", "PB-2026-1040", 120, "KG", "Soup cooking & aseptic fill", "VERIFIED"),
]

# Explicit distribution hops: (batch, origin, dest, ship_date, units, delivered?)
# Location prefixes: FAC- facility, WH- warehouse, DST- distributor, RTL- retailer
HOPS = [
    # PB-2026-1002 Classic Pasta Sauce (affected)
    ("PB-2026-1002", "FAC-PUN", "WH-PUN1", "2026-10-06", 5000, True),
    ("PB-2026-1002", "FAC-PUN", "WH-MUM1", "2026-10-06", 4000, True),
    ("PB-2026-1002", "WH-PUN1", "DST-02", "2026-10-09", 4000, True),
    ("PB-2026-1002", "DST-02", "RTL-PUN-01", "2026-10-11", 1500, True),
    ("PB-2026-1002", "DST-02", "RTL-PUN-02", "2026-10-11", 1300, True),
    ("PB-2026-1002", "DST-02", "RTL-PUN-03", "2026-10-11", 1200, True),
    ("PB-2026-1002", "WH-MUM1", "DST-01", "2026-10-10", 3500, True),
    ("PB-2026-1002", "DST-01", "RTL-MUM-01", "2026-10-12", 1300, True),
    ("PB-2026-1002", "DST-01", "RTL-MUM-02", "2026-10-12", 1200, True),
    ("PB-2026-1002", "DST-01", "RTL-MUM-03", "2026-10-12", 1000, True),
    # PB-2026-1004 Marinara (affected)
    ("PB-2026-1004", "FAC-PUN", "WH-PUN1", "2026-10-08", 3000, True),
    ("PB-2026-1004", "FAC-PUN", "WH-HYD1", "2026-10-09", 3000, True),
    ("PB-2026-1004", "WH-PUN1", "DST-02", "2026-10-12", 2500, True),
    ("PB-2026-1004", "DST-02", "RTL-PUN-01", "2026-10-14", 1300, True),
    ("PB-2026-1004", "DST-02", "RTL-PUN-04", "2026-10-14", 1200, True),
    ("PB-2026-1004", "WH-HYD1", "DST-05", "2026-10-13", 2800, True),
    ("PB-2026-1004", "DST-05", "RTL-HYD-01", "2026-10-15", 1000, True),
    ("PB-2026-1004", "DST-05", "RTL-HYD-02", "2026-10-15", 1000, True),
    ("PB-2026-1004", "DST-05", "RTL-HYD-03", "2026-10-15", 800, True),
    # PB-2026-1005 Pizza sauce (affected)
    ("PB-2026-1005", "FAC-PUN", "WH-MUM1", "2026-10-08", 4000, True),
    ("PB-2026-1005", "FAC-PUN", "WH-HYD1", "2026-10-09", 2000, True),
    ("PB-2026-1005", "WH-MUM1", "DST-01", "2026-10-11", 3500, True),
    ("PB-2026-1005", "DST-01", "RTL-MUM-01", "2026-10-13", 1000, True),
    ("PB-2026-1005", "DST-01", "RTL-MUM-04", "2026-10-13", 1500, True),
    ("PB-2026-1005", "DST-01", "RTL-MUM-02", "2026-10-13", 1000, True),
    ("PB-2026-1005", "WH-HYD1", "RTL-HYD-04", "2026-10-12", 1800, True),
    # PB-2026-1006 Pizza sauce second run (affected via UNVERIFIED edge)
    ("PB-2026-1006", "FAC-PUN", "WH-MUM1", "2026-10-13", 5000, True),
    ("PB-2026-1006", "WH-MUM1", "DST-01", "2026-10-16", 2000, True),
    ("PB-2026-1006", "DST-01", "RTL-MUM-04", "2026-10-17", 2000, True),
    # PB-2026-1007 Paneer tikka masala (affected, depth 3, multi-hop to Kolkata)
    ("PB-2026-1007", "FAC-NSK", "WH-NSK1", "2026-10-10", 3000, True),
    ("PB-2026-1007", "FAC-NSK", "WH-DEL1", "2026-10-11", 4000, True),
    ("PB-2026-1007", "WH-NSK1", "DST-01", "2026-10-13", 2500, True),
    ("PB-2026-1007", "DST-01", "RTL-MUM-03", "2026-10-15", 1300, True),
    ("PB-2026-1007", "DST-01", "RTL-NSK-01", "2026-10-15", 1200, True),
    ("PB-2026-1007", "WH-DEL1", "DST-03", "2026-10-15", 2500, True),
    ("PB-2026-1007", "DST-03", "RTL-DEL-01", "2026-10-17", 1000, True),
    ("PB-2026-1007", "DST-03", "RTL-DEL-02", "2026-10-17", 800, True),
    ("PB-2026-1007", "DST-03", "RTL-DEL-03", "2026-10-17", 700, True),
    ("PB-2026-1007", "WH-DEL1", "WH-KOL1", "2026-10-16", 1400, True),
    ("PB-2026-1007", "WH-KOL1", "RTL-KOL-01", "2026-10-20", 700, True),
    ("PB-2026-1007", "WH-KOL1", "RTL-KOL-02", "2026-10-20", 600, True),
    # PB-2026-1008 Tomato soup (affected) — DST-05 has NO onward records (records gap)
    ("PB-2026-1008", "FAC-PUN", "WH-PUN1", "2026-10-11", 2000, True),
    ("PB-2026-1008", "FAC-PUN", "WH-HYD1", "2026-10-12", 2000, True),
    ("PB-2026-1008", "WH-PUN1", "DST-02", "2026-10-14", 1800, True),
    ("PB-2026-1008", "DST-02", "RTL-PUN-02", "2026-10-15", 900, True),
    ("PB-2026-1008", "DST-02", "RTL-PUN-05", "2026-10-15", 900, True),
    ("PB-2026-1008", "WH-HYD1", "DST-05", "2026-10-14", 2000, True),
    # PB-2026-1009 Dal tadka (affected) — one shipment still IN TRANSIT
    ("PB-2026-1009", "FAC-NSK", "WH-NSK1", "2026-10-12", 3000, True),
    ("PB-2026-1009", "WH-NSK1", "DST-01", "2026-11-09", 1500, False),
    # ---- near-miss: overlapping locations, different batches ----
    ("PB-2026-1011", "FAC-PUN", "WH-PUN1", "2026-10-14", 3000, True),
    ("PB-2026-1011", "WH-PUN1", "DST-02", "2026-10-16", 2800, True),
    ("PB-2026-1011", "DST-02", "RTL-PUN-01", "2026-10-18", 1500, True),
    ("PB-2026-1011", "DST-02", "RTL-PUN-02", "2026-10-18", 1300, True),
    ("PB-2026-1012", "FAC-PUN", "WH-BLR1", "2026-10-16", 6000, True),
    ("PB-2026-1012", "WH-BLR1", "DST-04", "2026-10-19", 5500, True),
    ("PB-2026-1012", "DST-04", "RTL-BLR-01", "2026-10-21", 2500, True),
    ("PB-2026-1012", "DST-04", "RTL-BLR-02", "2026-10-21", 3000, True),
    ("PB-2026-1013", "FAC-PUN", "WH-MUM1", "2026-10-16", 8000, True),
    ("PB-2026-1013", "WH-MUM1", "DST-01", "2026-10-19", 6000, True),
    ("PB-2026-1013", "DST-01", "RTL-MUM-01", "2026-10-21", 3000, True),
    ("PB-2026-1013", "DST-01", "RTL-MUM-02", "2026-10-21", 3000, True),
]

# Rule-based distribution for remaining finished batches (deterministic).
FACILITY_WAREHOUSES = {
    "FAC-PUN": ["WH-PUN1", "WH-HYD1"],
    "FAC-NSK": ["WH-NSK1", "WH-DEL1"],
    "FAC-IND": ["WH-IND1", "WH-AHM1"],
    "FAC-HSR": ["WH-BLR1", "WH-CHN1"],
}
WAREHOUSE_ROUTE = {  # warehouse -> (distributor or None, retailers)
    "WH-PUN1": ("DST-02", ["RTL-PUN-03", "RTL-PUN-04"]),
    "WH-HYD1": ("DST-05", ["RTL-HYD-02", "RTL-HYD-05"]),
    "WH-NSK1": ("DST-01", ["RTL-NSK-01", "RTL-MUM-03"]),
    "WH-DEL1": ("DST-03", ["RTL-DEL-01", "RTL-DEL-04"]),
    "WH-IND1": ("DST-06", ["RTL-IND-01", "RTL-IND-02"]),
    "WH-AHM1": (None, ["RTL-AHM-01", "RTL-AHM-02"]),
    "WH-BLR1": ("DST-04", ["RTL-BLR-02", "RTL-BLR-03"]),
    "WH-CHN1": (None, ["RTL-CHN-01", "RTL-CHN-02"]),
}
EXPLICIT = {h[0] for h in HOPS}


def rule_hops(batch):
    bid, fac, btype, prod, _desc, qty, _u, pdate, _bb = batch
    if btype != "FINISHED" or bid in EXPLICIT:
        return []
    p = d(pdate)
    hops = []
    w1, w2 = FACILITY_WAREHOUSES[fac]
    first = int(qty * 0.6) // 100 * 100
    second = int(qty * 0.3) // 100 * 100
    for wh, units, lag in ((w1, first, 1), (w2, second, 2)):
        ship = p + dt.timedelta(days=lag)
        hops.append((bid, fac, wh, ship.isoformat(), units, True))
        dst, rts = WAREHOUSE_ROUTE[wh]
        fwd = units // 100 * 90  # 90% forwarded, rest held as warehouse stock
        if dst:
            ship2 = ship + dt.timedelta(days=3)
            hops.append((bid, wh, dst, ship2.isoformat(), fwd, True))
            half = fwd // 2
            for i, r in enumerate(rts):
                hops.append((bid, dst, r, (ship2 + dt.timedelta(days=2)).isoformat(), half if i == 0 else fwd - half, True))
        else:
            half = fwd // 2
            for i, r in enumerate(rts):
                hops.append((bid, wh, r, (ship + dt.timedelta(days=3)).isoformat(), half if i == 0 else fwd - half, True))
    return hops


def kind(ref: str) -> str:
    return {"FAC": "FACILITY", "WH": "WAREHOUSE", "DST": "DISTRIBUTOR", "RTL": "RETAILER"}[ref.split("-")[0]]


CARRIERS = ["BlueLine Logistics", "Sahyadri Roadways", "ColdTrail Reefer Lines", "NorthStar Fleet"]


def build_shipments():
    hops = list(HOPS)
    for b in BATCHES:
        hops.extend(rule_hops(b))
    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for bid, o, de, sd, units, delivered in sorted(hops, key=lambda h: (h[3], h[1], h[2], h[0])):
        groups.setdefault((o, de, sd, delivered), []).append((bid, units))
    ship_rows, item_rows = [], []
    for n, ((o, de, sd, delivered), items) in enumerate(groups.items(), start=1):
        sid = f"SHP-2026-{n:04d}"
        ok, dk = kind(o), kind(de)
        sdate = d(sd)
        dlv = (sdate + dt.timedelta(days=1)) if delivered else None
        row = (
            sid, ok, o,
            o if ok == "FACILITY" else None, o if ok == "WAREHOUSE" else None, o if ok == "DISTRIBUTOR" else None,
            dk, de,
            de if dk == "WAREHOUSE" else None, de if dk == "DISTRIBUTOR" else None, de if dk == "RETAILER" else None,
            sdate, dlv, "DELIVERED" if delivered else "IN_TRANSIT", CARRIERS[n % len(CARRIERS)],
        )
        ship_rows.append(row)
        for bid, units in items:
            item_rows.append((sid, bid, units))
    return ship_rows, item_rows


QUALITY_REPORTS = [
    # supplier COA says PASS for the lot the lab later finds contaminated -> conflicting evidence
    ("QR-2026-0101", "LOT", "TOM-2026-041", "SUPPLIER_COA", "Valle Rosso Tomato Cooperative QA", "2026-10-01",
     "Certificate of Analysis: Salmonella spp. not detected in 25 g (n=1); Brix 28.2; pH 4.3", "PASS", "DOC-SEED-0001"),
    ("QR-2026-0102", "BATCH", "PB-2026-1001", "PROCESS_QC", "Pune Sauce Works QA", "2026-10-04",
     "Pasteurisation log: hold temperature dipped to 84.1 C for 6 min (target >= 90 C) between 14:10 and 14:16", "INCONCLUSIVE", "DOC-SEED-0002"),
    ("QR-2026-0103", "LOT", "TOM-2026-042", "SUPPLIER_COA", "Valle Rosso Tomato Cooperative QA", "2026-10-08",
     "Certificate of Analysis: Salmonella spp. not detected in 25 g (n=5); Brix 28.0; pH 4.2", "PASS", None),
    ("QR-2026-0104", "LOT", "CHI-2026-017", "THIRD_PARTY_LAB", "Deccan Analytical Services", "2026-09-12",
     "Salmonella spp. detected in 2 of 5 x 25 g samples", "FAIL", "DOC-SEED-0003"),
    ("QR-2026-0105", "LOT", "MLK-2026-233", "CUSTOMER_COMPLAINT", "Hosur Dairy & Bakery QA", "2026-11-02",
     "Presumptive Cronobacter spp. on enrichment; confirmation pending", "INCONCLUSIVE", "DOC-SEED-0004"),
    ("QR-2026-0106", "BATCH", "PB-2026-1011", "PROCESS_QC", "Pune Sauce Works QA", "2026-10-13",
     "Pasteurisation log within limits (>= 90 C for 10 min)", "PASS", None),
]


def main() -> None:
    lines = ["-- AUTO-GENERATED by db/seed/generate_seed.py — do not edit by hand.",
             "-- Fictional demonstration data for RecallGuard AI. Not real companies or products."]
    lines += insert("suppliers", ["supplier_id", "supplier_name", "country", "region", "contact_email", "contact_phone", "certification", "risk_tier"], SUPPLIERS)
    lines += insert("ingredients", ["ingredient_id", "ingredient_name", "category", "allergen_flag"], INGREDIENTS)
    lines += insert("manufacturing_facilities", ["facility_id", "facility_name", "city", "state_region", "license_no"], FACILITIES)
    lines += insert("ingredient_lots", ["lot_id", "ingredient_id", "supplier_id", "facility_id", "quantity_kg", "received_date", "expiry_date", "coa_reference"],
                    [(l[0], l[1], l[2], l[3], l[4], d(l[5]), d(l[6]), l[7]) for l in LOTS])
    lines += insert("finished_products", ["product_id", "product_name", "brand", "category", "unit_size", "gtin"], PRODUCTS)
    lines += insert("production_batches", ["batch_id", "facility_id", "batch_type", "product_id", "description", "quantity", "quantity_unit", "production_date", "best_before"],
                    [(b[0], b[1], b[2], b[3], b[4], b[5], b[6], d(b[7]), d(b[7]) + dt.timedelta(days=b[8])) for b in BATCHES])
    lot_ids = {l[0] for l in LOTS}
    batch_dates = {b[0]: d(b[7]) for b in BATCHES}
    tr_rows = []
    for i, (inp, out, qty, unit, step, rs) in enumerate(TRANSFORMS, start=1):
        is_lot = inp in lot_ids
        if not is_lot:
            assert batch_dates[inp] <= batch_dates[out], f"{inp} produced after {out}"
        ts = f"{batch_dates[out].isoformat()} 08:{i % 60:02d}:00"
        tr_rows.append((f"TR-2026-{i:04d}", "LOT" if is_lot else "BATCH", inp, inp if is_lot else None, None if is_lot else inp, out, qty, unit, step, ts, rs))
    lines += insert("batch_transformations", ["transformation_id", "input_kind", "input_ref", "input_lot_id", "input_batch_id", "output_batch_id", "quantity_used", "quantity_unit", "process_step", "transformed_at", "record_status"], tr_rows)
    lines += insert("warehouses", ["warehouse_id", "warehouse_name", "city", "state_region", "temperature_class"], WAREHOUSES)
    lines += insert("distributors", ["distributor_id", "distributor_name", "city", "contact_email"], DISTRIBUTORS)
    lines += insert("retailers", ["retailer_id", "retailer_name", "retailer_type", "city", "state_region", "contact_email"],
                    [r + (f"store-ops+{r[0].lower()}@retail.example",) for r in RETAILERS])
    ships, items = build_shipments()
    lines += insert("shipments", ["shipment_id", "origin_kind", "origin_ref", "origin_facility_id", "origin_warehouse_id", "origin_distributor_id",
                                  "dest_kind", "dest_ref", "dest_warehouse_id", "dest_distributor_id", "dest_retailer_id",
                                  "ship_date", "delivered_date", "shipment_status", "carrier"], ships)
    lines += insert("shipment_items", ["shipment_id", "batch_id", "quantity_units"], items)
    lines += insert("quality_reports", ["report_id", "subject_kind", "subject_ref", "report_type", "issued_by", "issued_date", "result_summary", "outcome", "document_id"],
                    [r[:5] + (d(r[5]),) + r[6:] for r in QUALITY_REPORTS])
    OUT.write_text(";\n".join(lines) + ";\n", encoding="utf-8")
    print(f"wrote {OUT} — suppliers={len(SUPPLIERS)} lots={len(LOTS)} batches={len(BATCHES)} products={len(PRODUCTS)} "
          f"warehouses={len(WAREHOUSES)} retailers={len(RETAILERS)} shipments={len(ships)} shipment_items={len(items)} transformations={len(tr_rows)}")


if __name__ == "__main__":
    main()
