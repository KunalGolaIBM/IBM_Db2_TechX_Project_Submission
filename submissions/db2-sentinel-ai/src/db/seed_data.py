"""
Seed data generator and loader for Db2 Sentinel AI.
Populates realistic accounts, transactions, sanctions watchlists, and FATF AML typologies
with precomputed dense vector embeddings for semantic search.
"""

import json
from datetime import datetime, timedelta
from src.db.connection import get_db_manager
from src.utils.embeddings import get_embedding_service

# FATF & International AML Typologies Catalog
AML_TYPOLOGIES_SEED = [
    {
        "typology_id": "TYP-001",
        "code": "STRUCTURING_SMURFING",
        "title": "Structuring / Smurfing Cash & Wires Below Threshold",
        "category": "Placement & Layering",
        "description": "Deliberate fragmentation of large transaction amounts into multiple sub-threshold sums (typically just below $10,000 or local CTR limits) within a short window across multiple accounts or branches to evade mandatory regulatory currency reporting.",
        "red_flags": "Multiple transactions between $9,000 and $9,950; same-day or 48-hour consolidation; repetitive transaction notes like 'split fee' or 'tranche'; funds quickly consolidated into a single beneficiary account.",
    },
    {
        "typology_id": "TYP-002",
        "code": "OFFSHORE_SHELL_LAYERING",
        "title": "Offshore Shell Company & Passthrough Invoicing",
        "category": "Layering",
        "description": "Circulation of high-value funds through multiple corporate shell entities registered in high-secrecy jurisdictions, supported by fabricated invoices for intangible services like 'marketing consultation', 'software IP licenses', or 'management retainer'.",
        "red_flags": "Entities incorporated in secrecy havens with no physical office or employees; generic invoice descriptions for advisory services; rapid in-and-out pass-through within 24 hours with negligible retained balance.",
    },
    {
        "typology_id": "TYP-003",
        "code": "CIRCULAR_FUNDS_ROUTING",
        "title": "Circular Round-Trip Wire Routing (U-Turn Transactions)",
        "category": "Layering & Obfuscation",
        "description": "Movement of capital in a loop across multiple jurisdictions (Entity A -> Entity B -> Entity C -> Entity A) with minimal margin deducted, solely designed to create false transaction volume and sever the audit trail of illicit origin.",
        "red_flags": "Identical or near-identical principal sum transferred in a closed ring; counterparties share beneficial ownership or common directors; transactions lack commercial justification or legitimate economic rationale.",
    },
    {
        "typology_id": "TYP-004",
        "code": "RAPID_VELOCITY_MULE_RING",
        "title": "High-Velocity Money Mule Network Exploitation",
        "category": "Integration & Extraction",
        "description": "Recruitment of retail individual accounts (mules) that have historically exhibited low transactional activity, suddenly receiving bursts of third-party domestic or international wires followed by instantaneous withdrawal, ATM cash extraction, or crypto exchange deposit.",
        "red_flags": "Dormant account activated with high-value incoming transfers; funds drained within 15 minutes of receipt; account balance returns immediately to near zero; disparate sender locations.",
    },
    {
        "typology_id": "TYP-005",
        "code": "SANCTIONS_EVASION_FRONT",
        "title": "Sanctioned Entity Evasion via Front Proxies",
        "category": "Sanctions & Terrorist Financing",
        "description": "Execution of cross-border transfers involving sanctioned state entities, designated individuals, or embargoed industries through intermediary logistics firms, trading front companies, or altered shipping manifests.",
        "red_flags": "Beneficiary name matches alias or phonetically similar variation of Specially Designated Nationals (SDN); transshipment points near embargoed borders; vague memo references to maritime logistics or dual-use goods.",
    },
    {
        "typology_id": "TYP-006",
        "code": "TRADE_BASED_MONEY_LAUNDERING",
        "title": "Trade-Based Money Laundering (TBML) Over/Under Invoicing",
        "category": "Trade Misinvoicing",
        "description": "Disguising illicit capital movement as legitimate international commerce by significantly misrepresenting the price, quantity, or quality of imported/exported commodities or software goods.",
        "red_flags": "Unit price grossly deviates from fair market commodity value; shipping documentation lacks freight inspection certificates; payment sent to third party unconnected to maritime bill of lading.",
    },
]

# Sanctions & Watchlist Entities
SANCTIONS_WATCHLIST_SEED = [
    {
        "entity_id": "SANCT-001",
        "name": "Titan Petrochemical Trading LLC",
        "aliases": "Titan Oil Trading, Titan Global FZE, TPT Marine",
        "country": "United Arab Emirates / Iran",
        "category": "SDN - OFAC Sanctioned Entity",
        "risk_level": "CRITICAL",
    },
    {
        "entity_id": "SANCT-002",
        "name": "Volkov Strategic Capital Management",
        "aliases": "VSCM Holding, Volkov Investments Moscow",
        "country": "Russia",
        "category": "Sanctioned Financial Institution",
        "risk_level": "CRITICAL",
    },
    {
        "entity_id": "SANCT-003",
        "name": "Al-Bahar Logistics Services",
        "aliases": "Al Bahar Express, Ocean Freight Gulf",
        "country": "Yemen / Syria",
        "category": "Designated Terrorist Financing Front",
        "risk_level": "CRITICAL",
    },
]

# Bank Accounts Seed
ACCOUNTS_SEED = [
    {
        "account_id": "ACC-1001",
        "customer_name": "Apex Global Innovations Corp",
        "account_type": "Corporate",
        "jurisdiction": "United States",
        "balance": 2450000.00,
        "risk_rating": "LOW",
        "status": "ACTIVE",
        "kyc_verified": 1,
    },
    {
        "account_id": "ACC-1002",
        "customer_name": "Nordic Clean Energy Solutions AB",
        "account_type": "Corporate",
        "jurisdiction": "Sweden",
        "balance": 890000.00,
        "risk_rating": "LOW",
        "status": "ACTIVE",
        "kyc_verified": 1,
    },
    {
        "account_id": "ACC-1003",
        "customer_name": "Pan-Asia Invoicing FZE",
        "account_type": "Offshore",
        "jurisdiction": "UAE - Free Zone",
        "balance": 18500.00,
        "risk_rating": "HIGH",
        "status": "ACTIVE",
        "kyc_verified": 1,
    },
    {
        "account_id": "ACC-1004",
        "customer_name": "Starlight Global Holdings BVI",
        "account_type": "Offshore",
        "jurisdiction": "British Virgin Islands",
        "balance": 412000.00,
        "risk_rating": "HIGH",
        "status": "ACTIVE",
        "kyc_verified": 0,
    },
    {
        "account_id": "ACC-1005",
        "customer_name": "Aegis Maritime Consultancy Ltd",
        "account_type": "Corporate",
        "jurisdiction": "Cyprus",
        "balance": 125000.00,
        "risk_rating": "MEDIUM",
        "status": "ACTIVE",
        "kyc_verified": 1,
    },
    {
        "account_id": "ACC-1006",
        "customer_name": "Blue Horizon Intermediaries SA",
        "account_type": "Corporate",
        "jurisdiction": "Seychelles",
        "balance": 67000.00,
        "risk_rating": "HIGH",
        "status": "ACTIVE",
        "kyc_verified": 0,
    },
    {
        "account_id": "ACC-1007",
        "customer_name": "Rahul Verma (Retail Student)",
        "account_type": "Retail",
        "jurisdiction": "India",
        "balance": 350.00,
        "risk_rating": "HIGH",
        "status": "ACTIVE",
        "kyc_verified": 1,
    },
    {
        "account_id": "ACC-1008",
        "customer_name": "Elena Rostova",
        "account_type": "Retail",
        "jurisdiction": "Cyprus",
        "balance": 45000.00,
        "risk_rating": "MEDIUM",
        "status": "ACTIVE",
        "kyc_verified": 1,
    },
]


def generate_seed_transactions():
    """Generates realistic transactions including 3 iconic financial crime scenarios."""
    now = datetime.now()
    txs = []

    # Scenario 1: Structuring / Smurfing Pattern (Sub-threshold wires within 2 hours)
    t1 = now - timedelta(hours=3, minutes=45)
    txs.append({
        "tx_id": "TX-STRUCT-01",
        "sender_id": "ACC-1008",
        "receiver_id": "ACC-1003",
        "amount": 9850.00,
        "currency": "USD",
        "channel": "WIRE",
        "timestamp": t1.strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Consultancy invoice installment 1 split payment",
        "flag_anomaly": 1,
    })
    txs.append({
        "tx_id": "TX-STRUCT-02",
        "sender_id": "ACC-1008",
        "receiver_id": "ACC-1003",
        "amount": 9900.00,
        "currency": "USD",
        "channel": "WIRE",
        "timestamp": (t1 + timedelta(minutes=22)).strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Consultancy invoice installment 2 tranche retainers",
        "flag_anomaly": 1,
    })
    txs.append({
        "tx_id": "TX-STRUCT-03",
        "sender_id": "ACC-1005",
        "receiver_id": "ACC-1003",
        "amount": 9750.00,
        "currency": "USD",
        "channel": "WIRE",
        "timestamp": (t1 + timedelta(minutes=48)).strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Urgent advisory settlement fee tranche 3",
        "flag_anomaly": 1,
    })

    # Scenario 2: Circular Routing Loop (ACC-1004 -> ACC-1005 -> ACC-1006 -> ACC-1004)
    t2 = now - timedelta(days=2)
    txs.append({
        "tx_id": "TX-LOOP-01",
        "sender_id": "ACC-1004",
        "receiver_id": "ACC-1005",
        "amount": 250000.00,
        "currency": "USD",
        "channel": "SWIFT",
        "timestamp": t2.strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Intercompany loan funding tranche A",
        "flag_anomaly": 1,
    })
    txs.append({
        "tx_id": "TX-LOOP-02",
        "sender_id": "ACC-1005",
        "receiver_id": "ACC-1006",
        "amount": 245000.00,
        "currency": "USD",
        "channel": "SWIFT",
        "timestamp": (t2 + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Consultancy subcontracting pass-through disbursement",
        "flag_anomaly": 1,
    })
    txs.append({
        "tx_id": "TX-LOOP-03",
        "sender_id": "ACC-1006",
        "receiver_id": "ACC-1004",
        "amount": 240000.00,
        "currency": "USD",
        "channel": "SWIFT",
        "timestamp": (t2 + timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Return of surplus treasury liquidity collateral",
        "flag_anomaly": 1,
    })

    # Scenario 3: Sanctions Front Evasion (Direct reference to sanctioned Titan Petrochem)
    t3 = now - timedelta(hours=5)
    txs.append({
        "tx_id": "TX-SANCT-01",
        "sender_id": "ACC-1003",
        "receiver_id": "ACC-1005",
        "amount": 185000.00,
        "currency": "USD",
        "channel": "WIRE",
        "timestamp": t3.strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Settlement of bunkering fuel for Titan Petrochemical Trading LLC cargo #901",
        "flag_anomaly": 1,
    })

    # Legitimate Normal Transactions for Baseline Contrast
    t4 = now - timedelta(days=1)
    txs.append({
        "tx_id": "TX-NORM-01",
        "sender_id": "ACC-1001",
        "receiver_id": "ACC-1002",
        "amount": 42000.00,
        "currency": "USD",
        "channel": "ACH",
        "timestamp": t4.strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Q4 Enterprise software license renewal and support",
        "flag_anomaly": 0,
    })
    txs.append({
        "tx_id": "TX-NORM-02",
        "sender_id": "ACC-1002",
        "receiver_id": "ACC-1001",
        "amount": 15400.00,
        "currency": "USD",
        "channel": "ACH",
        "timestamp": (t4 + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
        "memo": "Quarterly solar farm monitoring telemetry hardware",
        "flag_anomaly": 0,
    })

    return txs


def seed_database(force: bool = False):
    """Inserts all seed data and computes vector embeddings."""
    db = get_db_manager()
    emb_service = get_embedding_service()

    # Check if already seeded
    try:
        existing = db.execute_query("SELECT COUNT(*) AS CNT FROM AML_TYPOLOGIES")
        cnt = existing[0]["CNT"] if existing else 0
        if cnt > 0 and not force:
            return  # Already seeded
    except Exception:
        pass

    # 1. Insert AML Typologies with Vector Embeddings
    for typ in AML_TYPOLOGIES_SEED:
        text_for_embedding = f"{typ['title']}. {typ['description']} {typ['red_flags']}"
        vector = emb_service.embed_text(text_for_embedding)
        vec_repr = json.dumps(vector)

        sql = """
        INSERT OR REPLACE INTO AML_TYPOLOGIES (TYPOLOGY_ID, CODE, TITLE, DESCRIPTION, CATEGORY, RED_FLAGS, EMBEDDING)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        if db.active_mode == "live":
            sql = """
            INSERT INTO AML_TYPOLOGIES (TYPOLOGY_ID, CODE, TITLE, DESCRIPTION, CATEGORY, RED_FLAGS, EMBEDDING)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        db.execute_update(
            sql,
            (
                typ["typology_id"],
                typ["code"],
                typ["title"],
                typ["description"],
                typ["category"],
                typ["red_flags"],
                vec_repr,
            ),
        )

    # 2. Insert Sanctions Watchlist
    for sanct in SANCTIONS_WATCHLIST_SEED:
        sql = """
        INSERT OR REPLACE INTO SANCTIONS_WATCHLIST (ENTITY_ID, NAME, ALIASES, COUNTRY, CATEGORY, RISK_LEVEL)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        if db.active_mode == "live":
            sql = """
            INSERT INTO SANCTIONS_WATCHLIST (ENTITY_ID, NAME, ALIASES, COUNTRY, CATEGORY, RISK_LEVEL)
            VALUES (?, ?, ?, ?, ?, ?)
            """
        db.execute_update(
            sql,
            (
                sanct["entity_id"],
                sanct["name"],
                sanct["aliases"],
                sanct["country"],
                sanct["category"],
                sanct["risk_level"],
            ),
        )

    # 3. Insert Accounts
    for acc in ACCOUNTS_SEED:
        sql = """
        INSERT OR REPLACE INTO ACCOUNTS (ACCOUNT_ID, CUSTOMER_NAME, ACCOUNT_TYPE, JURISDICTION, BALANCE, RISK_RATING, STATUS, KYC_VERIFIED)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        if db.active_mode == "live":
            sql = """
            INSERT INTO ACCOUNTS (ACCOUNT_ID, CUSTOMER_NAME, ACCOUNT_TYPE, JURISDICTION, BALANCE, RISK_RATING, STATUS, KYC_VERIFIED)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
        db.execute_update(
            sql,
            (
                acc["account_id"],
                acc["customer_name"],
                acc["account_type"],
                acc["jurisdiction"],
                acc["balance"],
                acc["risk_rating"],
                acc["status"],
                acc["kyc_verified"],
            ),
        )

    # 4. Insert Transactions with Embeddings
    transactions = generate_seed_transactions()
    for tx in transactions:
        memo_vector = emb_service.embed_text(tx["memo"])
        vec_repr = json.dumps(memo_vector)

        sql = """
        INSERT OR REPLACE INTO TRANSACTIONS (TX_ID, SENDER_ID, RECEIVER_ID, AMOUNT, CURRENCY, CHANNEL, TX_TIMESTAMP, MEMO, FLAG_ANOMALY, EMBEDDING)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if db.active_mode == "live":
            sql = """
            INSERT INTO TRANSACTIONS (TX_ID, SENDER_ID, RECEIVER_ID, AMOUNT, CURRENCY, CHANNEL, TX_TIMESTAMP, MEMO, FLAG_ANOMALY, EMBEDDING)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        db.execute_update(
            sql,
            (
                tx["tx_id"],
                tx["sender_id"],
                tx["receiver_id"],
                tx["amount"],
                tx["currency"],
                tx["channel"],
                tx["timestamp"],
                tx["memo"],
                tx["flag_anomaly"],
                vec_repr,
            ),
        )

    # 5. Insert initial Pending Investigation Alerts for the anomalous transactions
    initial_alerts = [
        ("ALT-001", "TX-STRUCT-01", 88, "Structuring & Rapid Smurfing Cluster Detected"),
        ("ALT-002", "TX-LOOP-01", 94, "High-Value Multi-Hop Circular Fund Routing (U-Turn)"),
        ("ALT-003", "TX-SANCT-01", 98, "Critical Sanctions Evasion & SDN Watchlist Hit"),
    ]
    for alt_id, tx_id, score, rule in initial_alerts:
        sql = """
        INSERT OR REPLACE INTO INVESTIGATION_ALERTS (ALERT_ID, TX_ID, RISK_SCORE, RULE_TRIGGERED, STATUS)
        VALUES (?, ?, ?, ?, 'PENDING_INVESTIGATION')
        """
        if db.active_mode == "live":
            sql = """
            INSERT INTO INVESTIGATION_ALERTS (ALERT_ID, TX_ID, RISK_SCORE, RULE_TRIGGERED, STATUS)
            VALUES (?, ?, ?, ?, 'PENDING_INVESTIGATION')
            """
        db.execute_update(sql, (alt_id, tx_id, score, rule))
