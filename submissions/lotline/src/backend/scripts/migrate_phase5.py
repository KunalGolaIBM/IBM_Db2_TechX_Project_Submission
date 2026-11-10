import sys
sys.path.insert(0, 'backend')
from app.database import query_all, execute_transaction, get_db_connection
import ibm_db

def table_exists(table_name: str) -> bool:
    rows = query_all(
        "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = 'LOTLINE_APP' AND TABNAME = ?",
        (table_name.upper(),)
    )
    return len(rows) > 0

def run_migration():
    print("Checking / applying Phase 5 Db2 migrations for LOTLINE_APP...")

    tables_ddl = [
        ("RECALL_COMMUNICATIONS", """
        CREATE TABLE LOTLINE_APP.RECALL_COMMUNICATIONS (
            COMM_ID VARCHAR(32) NOT NULL PRIMARY KEY,
            INCIDENT_ID VARCHAR(32) NOT NULL,
            SHIPMENT_ID VARCHAR(32),
            BATCH_ID VARCHAR(32) NOT NULL,
            RECIPIENT_ORG VARCHAR(128) NOT NULL,
            CONTACT_NAME VARCHAR(128),
            CONTACT_DESIGNATION VARCHAR(64),
            CONTACT_PHONE VARCHAR(32),
            CONTACT_EMAIL VARCHAR(128),
            COMM_TYPE VARCHAR(32) NOT NULL,
            MESSAGE_DRAFT VARCHAR(2000),
            STATUS VARCHAR(32) NOT NULL,
            DISPATCH_TIMESTAMP TIMESTAMP,
            DELIVERY_CONFIRMATION VARCHAR(255),
            ACKNOWLEDGEMENT_NOTES VARCHAR(1000),
            ACKNOWLEDGEMENT_AT TIMESTAMP,
            OPERATOR_NAME VARCHAR(128),
            APPROVED_BY VARCHAR(128),
            APPROVED_AT TIMESTAMP,
            CREATED_AT TIMESTAMP NOT NULL,
            UPDATED_AT TIMESTAMP NOT NULL
        )
        """),
        ("LOGISTICS_INTERVENTIONS", """
        CREATE TABLE LOTLINE_APP.LOGISTICS_INTERVENTIONS (
            INTERVENTION_ID VARCHAR(32) NOT NULL PRIMARY KEY,
            INCIDENT_ID VARCHAR(32) NOT NULL,
            SHIPMENT_ID VARCHAR(32) NOT NULL,
            LOT_ID VARCHAR(32) NOT NULL,
            QUANTITY DECIMAL(12,3) NOT NULL,
            DESTINATION_NAME VARCHAR(128) NOT NULL,
            CARRIER_IDENTITY VARCHAR(128) NOT NULL,
            TRACKING_REF VARCHAR(64),
            DISPATCH_CONTACT VARCHAR(128),
            STATUS VARCHAR(32) NOT NULL,
            CARRIER_ACK_AT TIMESTAMP,
            CARGO_LOCATION VARCHAR(255),
            INTERCEPTION_NOTES VARCHAR(1000),
            RETURNED_FACILITY_ID VARCHAR(32),
            RECOVERED_QUANTITY DECIMAL(12,3),
            RETURN_VERIFIED_AT TIMESTAMP,
            REQUESTED_BY VARCHAR(128),
            APPROVED_BY VARCHAR(128),
            APPROVED_AT TIMESTAMP,
            CREATED_AT TIMESTAMP NOT NULL,
            UPDATED_AT TIMESTAMP NOT NULL
        )
        """),
        ("PRODUCT_RECOVERIES", """
        CREATE TABLE LOTLINE_APP.PRODUCT_RECOVERIES (
            RECOVERY_ID VARCHAR(32) NOT NULL PRIMARY KEY,
            INCIDENT_ID VARCHAR(32) NOT NULL,
            LOT_ID VARCHAR(32) NOT NULL,
            SOURCE_LOCATION_TYPE VARCHAR(32) NOT NULL,
            SOURCE_ENTITY_NAME VARCHAR(128) NOT NULL,
            QUANTITY_CONFIRMED DECIMAL(12,3) NOT NULL,
            QUANTITY_RECOVERED DECIMAL(12,3) NOT NULL,
            QUANTITY_AWAITING_COLLECTION DECIMAL(12,3) NOT NULL,
            UNIT_OF_MEASURE VARCHAR(16) NOT NULL,
            STORAGE_FACILITY_ID VARCHAR(32),
            VERIFICATION_METHOD VARCHAR(64),
            RECORDED_BY VARCHAR(128) NOT NULL,
            RECORDED_AT TIMESTAMP NOT NULL,
            NOTES VARCHAR(1000)
        )
        """),
        ("PRODUCT_DISPOSITIONS", """
        CREATE TABLE LOTLINE_APP.PRODUCT_DISPOSITIONS (
            DISPOSITION_ID VARCHAR(32) NOT NULL PRIMARY KEY,
            INCIDENT_ID VARCHAR(32) NOT NULL,
            LOT_ID VARCHAR(32) NOT NULL,
            LOT_TYPE VARCHAR(16) NOT NULL,
            QUANTITY DECIMAL(12,3) NOT NULL,
            UNIT_OF_MEASURE VARCHAR(16) NOT NULL,
            DISPOSITION_TYPE VARCHAR(64) NOT NULL,
            REASON VARCHAR(1000) NOT NULL,
            PROPOSED_METHOD VARCHAR(255),
            AUTHORITY_PERMISSION_REF VARCHAR(128),
            STATUS VARCHAR(32) NOT NULL,
            OPERATOR_NAME VARCHAR(128) NOT NULL,
            APPROVED_BY VARCHAR(128),
            APPROVED_AT TIMESTAMP,
            EXECUTED_AT TIMESTAMP,
            EVIDENCE_ATTACHMENT VARCHAR(255),
            CREATED_AT TIMESTAMP NOT NULL
        )
        """),
        ("REGULATORY_SUBMISSIONS", """
        CREATE TABLE LOTLINE_APP.REGULATORY_SUBMISSIONS (
            SUBMISSION_ID VARCHAR(32) NOT NULL PRIMARY KEY,
            INCIDENT_ID VARCHAR(32) NOT NULL,
            REGULATORY_BODY VARCHAR(64) NOT NULL,
            FOSCOS_RECALL_REF VARCHAR(64),
            SUBMISSION_STAGE VARCHAR(64) NOT NULL,
            SUBMITTED_BY VARCHAR(128),
            SUBMISSION_TIMESTAMP TIMESTAMP,
            AUTHORITY_FEEDBACK VARCHAR(2000),
            SUPPORTING_EVIDENCE_REF VARCHAR(255),
            PENDING_CORRECTIONS VARCHAR(1000),
            AWARENESS_TIMESTAMP TIMESTAMP NOT NULL,
            STATUTORY_DEADLINE TIMESTAMP NOT NULL,
            CREATED_AT TIMESTAMP NOT NULL,
            UPDATED_AT TIMESTAMP NOT NULL
        )
        """),
        ("EFFECTIVENESS_REPORTS", """
        CREATE TABLE LOTLINE_APP.EFFECTIVENESS_REPORTS (
            REPORT_ID VARCHAR(32) NOT NULL PRIMARY KEY,
            INCIDENT_ID VARCHAR(32) NOT NULL,
            REPORT_TYPE VARCHAR(32) NOT NULL,
            TOTAL_AFFECTED_UNITS DECIMAL(12,3) NOT NULL,
            TOTAL_DISTRIBUTED_UNITS DECIMAL(12,3) NOT NULL,
            ORGS_IDENTIFIED INTEGER NOT NULL,
            ORGS_NOTIFIED INTEGER NOT NULL,
            ORGS_ACKNOWLEDGED INTEGER NOT NULL,
            QUANTITY_RECOVERED DECIMAL(12,3) NOT NULL,
            QUANTITY_DESTROYED DECIMAL(12,3) NOT NULL,
            QUANTITY_OUTSTANDING DECIMAL(12,3) NOT NULL,
            RECALL_EFFECTIVENESS_PCT DECIMAL(5,2) NOT NULL,
            CONSIGNEE_RESPONSE_PCT DECIMAL(5,2) NOT NULL,
            RECOVERY_PCT DECIMAL(5,2) NOT NULL,
            UNRESOLVED_ACTIONS_COUNT INTEGER NOT NULL,
            CAN_CLOSE_RECALL VARCHAR(1) NOT NULL,
            STATUS VARCHAR(32) NOT NULL,
            EVALUATED_BY VARCHAR(128) NOT NULL,
            CREATED_AT TIMESTAMP NOT NULL
        )
        """)
    ]

    for tname, ddl in tables_ddl:
        if not table_exists(tname):
            print(f"Creating table LOTLINE_APP.{tname}...")
            with get_db_connection() as conn:
                stmt = ibm_db.exec_immediate(conn, ddl)
            print(f"  Created {tname} successfully.")
        else:
            print(f"Table LOTLINE_APP.{tname} already exists.")

    # Seed baseline data for INC-2026-001 if empty
    seed_baseline_data()

def seed_baseline_data():
    incident_id = "INC-2026-001"

    # 1. Communications
    existing_comms = query_all("SELECT COUNT(*) AS CNT FROM LOTLINE_APP.RECALL_COMMUNICATIONS WHERE INCIDENT_ID = ?", (incident_id,))
    if existing_comms[0]['cnt'] == 0:
        print("Seeding baseline communications...")
        comms_data = [
            ("COMM-001", incident_id, "SHP-001", "FIN-401", "FreshMart Nagpur Central", "Rajesh Sharma", "Store General Manager", "+91 712 255 1011", "r.sharma@freshmart.example.in", "FORMAL_NOTICE", "URGENT FOOD RECALL: Batch FIN-401 Green Spinach Wrap (300 units). Potential Salmonella contamination in source lot RAW-204. Quarantine inventory immediately and halt all retail shelf sales.", "PENDING_APPROVAL", None, None, None, None, "Chief Safety Officer", None, None),
            ("COMM-002", incident_id, "SHP-002", "FIN-401", "FreshMart Pune West", "Kavita Deshmukh", "Inbound Logistics Manager", "+91 20 2567 8901", "k.deshmukh@freshmart.example.in", "FORMAL_NOTICE", "URGENT FOOD RECALL: Shipment SHP-002 (200 units FIN-401). Active transit interception requested. Do not accept consignment into receiving bay.", "PENDING_APPROVAL", None, None, None, None, "Chief Safety Officer", None, None),
            ("COMM-003", incident_id, "SHP-003", "FIN-402", "QuickCart Mumbai", "Amitabh Varma", "Fulfillment Director", "+91 22 6123 4567", "a.varma@quickcart.example.in", "FORMAL_NOTICE", "URGENT FOOD RECALL: Batch FIN-402 Spinach Green Smoothie (400 units). Potential Salmonella contamination. Immediate withdrawal from dark stores required.", "PENDING_APPROVAL", None, None, None, None, "Chief Safety Officer", None, None),
            ("COMM-004", incident_id, "SHP-004", "FIN-403", "CityGrocer Nashik", "Sunita Patil", "Quality Assurance Lead", "+91 253 234 5678", "s.patil@citygrocer.example.in", "FORMAL_NOTICE", "URGENT FOOD RECALL: Batch FIN-403 Garden Veggie Bowl (150 units). Potential Salmonella contamination. Hold in segregated returns area.", "PENDING_APPROVAL", None, None, None, None, "Chief Safety Officer", None, None),
        ]
        ops = []
        for c in comms_data:
            ops.append((
                """
                INSERT INTO LOTLINE_APP.RECALL_COMMUNICATIONS
                (COMM_ID, INCIDENT_ID, SHIPMENT_ID, BATCH_ID, RECIPIENT_ORG, CONTACT_NAME, CONTACT_DESIGNATION,
                 CONTACT_PHONE, CONTACT_EMAIL, COMM_TYPE, MESSAGE_DRAFT, STATUS, DISPATCH_TIMESTAMP,
                 DELIVERY_CONFIRMATION, ACKNOWLEDGEMENT_NOTES, ACKNOWLEDGEMENT_AT, OPERATOR_NAME, APPROVED_BY, APPROVED_AT,
                 CREATED_AT, UPDATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP, CURRENT TIMESTAMP)
                """,
                c
            ))
        execute_transaction(ops)
        print("  Seeded 4 baseline communications.")

    # 2. Logistics Interventions
    existing_interventions = query_all("SELECT COUNT(*) AS CNT FROM LOTLINE_APP.LOGISTICS_INTERVENTIONS WHERE INCIDENT_ID = ?", (incident_id,))
    if existing_interventions[0]['cnt'] == 0:
        print("Seeding baseline logistics intervention...")
        ops = [(
            """
            INSERT INTO LOTLINE_APP.LOGISTICS_INTERVENTIONS
            (INTERVENTION_ID, INCIDENT_ID, SHIPMENT_ID, LOT_ID, QUANTITY, DESTINATION_NAME,
             CARRIER_IDENTITY, TRACKING_REF, DISPATCH_CONTACT, STATUS, CARRIER_ACK_AT,
             CARGO_LOCATION, INTERCEPTION_NOTES, RETURNED_FACILITY_ID, RECOVERED_QUANTITY,
             RETURN_VERIFIED_AT, REQUESTED_BY, APPROVED_BY, APPROVED_AT, CREATED_AT, UPDATED_AT)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, CURRENT TIMESTAMP, CURRENT TIMESTAMP)
            """,
            (
                "INT-001",
                incident_id,
                "SHP-002",
                "FIN-401",
                200.0,
                "FreshMart Pune West",
                "ColdChain Logistics Express",
                "CC-TRK-98442",
                "Manoj Gaikwad (Fleet Dispatcher +91 98220 11223)",
                "PENDING_APPROVAL",
                "En route NH-48 Pune Expressway KM-114",
                "Vehicle carrying 200 units FIN-401. Human operator approval required before issuing carrier re-route instructions back to FAC-NGP.",
                "Logistics Control Officer"
            )
        )]
        execute_transaction(ops)
        print("  Seeded baseline logistics intervention INT-001.")

    # 3. Product Recoveries (Warehouse quarantined stock verified)
    existing_recoveries = query_all("SELECT COUNT(*) AS CNT FROM LOTLINE_APP.PRODUCT_RECOVERIES WHERE INCIDENT_ID = ?", (incident_id,))
    if existing_recoveries[0]['cnt'] == 0:
        print("Seeding baseline product recoveries...")
        recoveries_data = [
            ("REC-001", incident_id, "FIN-401", "WAREHOUSE_HOLD", "Facility FAC-PUN Cold Bay 1", 500.0, 500.0, 0.0, "UNIT", "FAC-PUN", "PHYSICAL_AUDIT", "Plant QA Officer", "Secure quarantine hold completed inside FAC-PUN."),
            ("REC-002", incident_id, "FIN-402", "WAREHOUSE_HOLD", "Facility FAC-MUM Storage Bay 2", 400.0, 400.0, 0.0, "UNIT", "FAC-MUM", "PHYSICAL_AUDIT", "Plant QA Officer", "Physical lock applied to pallet positions P-12 through P-14."),
            ("REC-003", incident_id, "FIN-403", "WAREHOUSE_HOLD", "Facility FAC-PUN Vault 3", 450.0, 450.0, 0.0, "UNIT", "FAC-PUN", "PHYSICAL_AUDIT", "Plant QA Officer", "Quarantine tape and ERP hold flag verified."),
        ]
        ops = []
        for r in recoveries_data:
            ops.append((
                """
                INSERT INTO LOTLINE_APP.PRODUCT_RECOVERIES
                (RECOVERY_ID, INCIDENT_ID, LOT_ID, SOURCE_LOCATION_TYPE, SOURCE_ENTITY_NAME,
                 QUANTITY_CONFIRMED, QUANTITY_RECOVERED, QUANTITY_AWAITING_COLLECTION,
                 UNIT_OF_MEASURE, STORAGE_FACILITY_ID, VERIFICATION_METHOD, RECORDED_BY, RECORDED_AT, NOTES)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP, ?)
                """,
                r
            ))
        execute_transaction(ops)
        print("  Seeded 3 baseline product recoveries.")

    # 4. Product Dispositions
    existing_dispositions = query_all("SELECT COUNT(*) AS CNT FROM LOTLINE_APP.PRODUCT_DISPOSITIONS WHERE INCIDENT_ID = ?", (incident_id,))
    if existing_dispositions[0]['cnt'] == 0:
        print("Seeding baseline product dispositions...")
        ops = [
            (
                """
                INSERT INTO LOTLINE_APP.PRODUCT_DISPOSITIONS
                (DISPOSITION_ID, INCIDENT_ID, LOT_ID, LOT_TYPE, QUANTITY, UNIT_OF_MEASURE,
                 DISPOSITION_TYPE, REASON, PROPOSED_METHOD, AUTHORITY_PERMISSION_REF,
                 STATUS, OPERATOR_NAME, APPROVED_BY, APPROVED_AT, EXECUTED_AT, EVIDENCE_ATTACHMENT, CREATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP, NULL, ?, CURRENT TIMESTAMP)
                """,
                (
                    "DISP-001",
                    incident_id,
                    "RAW-204",
                    "RAW",
                    50.0,
                    "KG",
                    "CONTINUED_QUARANTINE",
                    "Quarantine remaining raw organic spinach pending regulatory microbiological confirmatory testing.",
                    "Isolated bio-hazard cold storage at -2°C",
                    None,
                    "APPROVED",
                    "Response Planning Agent",
                    "Lead Product Safety Officer",
                    "FAC-NGP-QUARANTINE-BAY-04"
                )
            ),
            (
                """
                INSERT INTO LOTLINE_APP.PRODUCT_DISPOSITIONS
                (DISPOSITION_ID, INCIDENT_ID, LOT_ID, LOT_TYPE, QUANTITY, UNIT_OF_MEASURE,
                 DISPOSITION_TYPE, REASON, PROPOSED_METHOD, AUTHORITY_PERMISSION_REF,
                 STATUS, OPERATOR_NAME, APPROVED_BY, APPROVED_AT, EXECUTED_AT, EVIDENCE_ATTACHMENT, CREATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, CURRENT TIMESTAMP)
                """,
                (
                    "DISP-002",
                    incident_id,
                    "WIP-301",
                    "WIP",
                    200.0,
                    "KG",
                    "AWAITING_AUTHORITY_INSTRUCTIONS",
                    "Intermediate spinach wrap base containing raw material RAW-204. Awaiting FSSAI designated officer instructions on authorized industrial disposal.",
                    "High-temperature bio-thermal rendering under municipal oversight",
                    "REQ-AUTH-2026-FSSAI-01",
                    "PROPOSED",
                    "Response Planning Agent",
                    "FAC-PUN-WIP-HOLD"
                )
            )
        ]
        execute_transaction(ops)
        print("  Seeded 2 baseline product dispositions.")

    # 5. Regulatory Submissions (FoSCoS Tracker)
    existing_reg = query_all("SELECT COUNT(*) AS CNT FROM LOTLINE_APP.REGULATORY_SUBMISSIONS WHERE INCIDENT_ID = ?", (incident_id,))
    if existing_reg[0]['cnt'] == 0:
        print("Seeding baseline regulatory submission...")
        ops = [(
            """
            INSERT INTO LOTLINE_APP.REGULATORY_SUBMISSIONS
            (SUBMISSION_ID, INCIDENT_ID, REGULATORY_BODY, FOSCOS_RECALL_REF, SUBMISSION_STAGE,
             SUBMITTED_BY, SUBMISSION_TIMESTAMP, AUTHORITY_FEEDBACK, SUPPORTING_EVIDENCE_REF,
             PENDING_CORRECTIONS, AWARENESS_TIMESTAMP, STATUTORY_DEADLINE, CREATED_AT, UPDATED_AT)
            VALUES (?, ?, ?, NULL, ?, NULL, NULL, NULL, ?, ?, TIMESTAMP('2026-11-09-15.36.48.636226'), TIMESTAMP('2026-11-10-15.36.48.636226'), CURRENT TIMESTAMP, CURRENT TIMESTAMP)
            """,
            (
                "REG-001",
                incident_id,
                "FSSAI_FOSCOS",
                "MISSING_INFO_REVIEW",
                "DOC-FSSAI-SCHED1-DRAFT",
                "Requires FBO 14-digit FSSAI License Number and 24/7 Coordinator Phone before authorized portal submission."
            )
        )]
        execute_transaction(ops)
        print("  Seeded baseline regulatory submission REG-001.")

    print("Phase 5 database migrations and baseline seeding complete!")

if __name__ == "__main__":
    run_migration()
