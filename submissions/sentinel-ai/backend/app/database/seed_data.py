import uuid
import datetime
from app.database.db2_connector import db_connector

def seed_database():
    """Seeds synthetic defence network data if tables are empty."""
    users_count = db_connector.execute_query("SELECT COUNT(*) as cnt FROM USER_ACCOUNTS")
    if users_count and users_count[0].get("cnt", 0) > 0:
        return  # already seeded

    print("Seeding synthetic defence cybersecurity records...")

    # 1. USER_ACCOUNTS
    users = [
        ("USR-101", "sconnor", "Col. Sarah Connor", "col.sarah.connor@stratcom.mil", "Operations Commander", "Strategic Command", "TOP_SECRET", "ACTIVE"),
        ("USR-102", "avance", "Maj. Alex Vance", "maj.alex.vance@cybercommand.def", "Cyber Operations Officer", "Joint Cyber Command", "SECRET", "ACTIVE"),
        ("USR-103", "erostova", "Dr. Elena Rostova", "dr.elena.rostova@defencelab.mil", "Chief Cryptography Scientist", "Defence Science Lab", "TOP_SECRET", "ACTIVE"),
        ("USR-104", "mreed", "Lt. Marcus Reed", "lt.marcus.reed@jointops.mil", "Logistics Officer", "Joint Logistics Fleet", "CONFIDENTIAL", "ACTIVE"),
        ("USR-105", "dking", "David King", "david.king@dia.mil", "Senior Intelligence Analyst", "Defence Intelligence Agency", "SECRET", "ACTIVE"),
    ]

    for u in users:
        db_connector.execute_update(
            "INSERT INTO USER_ACCOUNTS (user_id, username, full_name, email, role, department, security_clearance, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            u
        )

    now = datetime.datetime.now()

    # 2. LOGIN_EVENTS (Baseline history)
    login_events = [
        (str(uuid.uuid4()), "USR-101", (now - datetime.timedelta(days=2)).isoformat(), "10.240.12.15", "DEF-SEC-LAPTOP-101", "Workstation", "Offutt AFB, Omaha", "SUCCESS", None, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StratCom-Sec/4.2"),
        (str(uuid.uuid4()), "USR-101", (now - datetime.timedelta(days=1)).isoformat(), "10.240.12.15", "DEF-SEC-LAPTOP-101", "Workstation", "Offutt AFB, Omaha", "SUCCESS", None, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StratCom-Sec/4.2"),
        (str(uuid.uuid4()), "USR-102", (now - datetime.timedelta(hours=14)).isoformat(), "10.110.4.88", "CYBER-TERMINAL-09", "Secure Desktop", "Fort Meade, MD", "SUCCESS", None, "Mozilla/5.0 (X11; Linux x86_64) CyberSec-Auth/1.1"),
        (str(uuid.uuid4()), "USR-103", (now - datetime.timedelta(hours=8)).isoformat(), "10.150.8.22", "LAB-SEC-WORKSTATION", "Workstation", "Porton Down Facility", "SUCCESS", None, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DefenceLab/2.0"),
        (str(uuid.uuid4()), "USR-104", (now - datetime.timedelta(hours=5)).isoformat(), "10.200.1.44", "LOG-DESK-04", "Workstation", "Norfolk Naval Base", "SUCCESS", None, "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
        (str(uuid.uuid4()), "USR-105", (now - datetime.timedelta(hours=3)).isoformat(), "10.180.7.19", "DIA-INTEL-MAC-01", "Laptop", "Pentagon Corridor 4", "SUCCESS", None, "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1)"),
    ]

    for le in login_events:
        db_connector.execute_update(
            "INSERT INTO LOGIN_EVENTS (event_id, user_id, timestamp, ip_address, device_name, device_type, location, status, failure_reason, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            le
        )

    # 3. ACCESS_LOGS (Routine access)
    access_logs = [
        (str(uuid.uuid4()), "USR-101", (now - datetime.timedelta(days=1, hours=2)).isoformat(), "RES-OP-901", "Joint Daily Operations Briefing", "Document", "READ", "ALLOWED", "SECRET"),
        (str(uuid.uuid4()), "USR-101", (now - datetime.timedelta(days=1, hours=1)).isoformat(), "RES-SAT-402", "Strategic Satellite Telemetry Portal", "Dashboard", "READ", "ALLOWED", "TOP_SECRET"),
        (str(uuid.uuid4()), "USR-102", (now - datetime.timedelta(hours=12)).isoformat(), "RES-NET-118", "Firewall Anomaly Correlation Logs", "Log Repository", "READ", "ALLOWED", "SECRET"),
        (str(uuid.uuid4()), "USR-103", (now - datetime.timedelta(hours=6)).isoformat(), "RES-CRYPTO-55", "Quantum Resistant Cipher Protocols", "Research DB", "READ", "ALLOWED", "TOP_SECRET"),
        (str(uuid.uuid4()), "USR-104", (now - datetime.timedelta(hours=4)).isoformat(), "RES-LOG-88", "Naval Supply Convoy Schedules", "Database", "WRITE", "ALLOWED", "CONFIDENTIAL"),
    ]

    for al in access_logs:
        db_connector.execute_update(
            "INSERT INTO ACCESS_LOGS (log_id, user_id, timestamp, resource_id, resource_name, resource_type, access_type, status, classification_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            al
        )

    print("Initial synthetic database records populated.")

