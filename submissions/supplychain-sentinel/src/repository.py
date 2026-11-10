import os
import sqlite3
from pathlib import Path
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

DEMO_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS supplier (supplier_id TEXT PRIMARY KEY, supplier_name TEXT, on_time_rate REAL, status TEXT);
CREATE TABLE IF NOT EXISTS component (component_id TEXT PRIMARY KEY, component_name TEXT, criticality TEXT, daily_demand INTEGER);
CREATE TABLE IF NOT EXISTS inventory (component_id TEXT PRIMARY KEY, on_hand_qty INTEGER, reserved_qty INTEGER);
CREATE TABLE IF NOT EXISTS purchase_order (po_id TEXT PRIMARY KEY, supplier_id TEXT, component_id TEXT, order_qty INTEGER, expected_date TEXT, status TEXT);
CREATE TABLE IF NOT EXISTS shipment_event (shipment_id TEXT PRIMARY KEY, po_id TEXT, event_status TEXT, original_eta TEXT, revised_eta TEXT, event_note TEXT);
CREATE TABLE IF NOT EXISTS quality_inspection (inspection_id TEXT PRIMARY KEY, component_id TEXT, quality_status TEXT, inspection_date TEXT);
CREATE TABLE IF NOT EXISTS production_order (production_order_id TEXT PRIMARY KEY, component_id TEXT, required_qty INTEGER, required_date TEXT, order_status TEXT);
CREATE TABLE IF NOT EXISTS risk_case (case_id TEXT PRIMARY KEY, shipment_id TEXT, component_id TEXT, severity TEXT, summary TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS recommendation (recommendation_id TEXT PRIMARY KEY, case_id TEXT, option_name TEXT, rationale TEXT, status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approval_audit (audit_id TEXT PRIMARY KEY, case_id TEXT, recommendation_id TEXT, decision TEXT, approver TEXT, rationale TEXT, created_at TEXT);
"""

def _db2_configured():
    return all(os.getenv(k) for k in ["DB2_HOST", "DB2_DATABASE", "DB2_USERNAME", "DB2_PASSWORD"])

class Repository:
    """Narrow, allow-listed data access layer. Db2 is the judging path; SQLite is local demo fallback."""
    def __init__(self):
        self.mode = "IBM Db2" if _db2_configured() and os.getenv("DEMO_MODE","0") != "1" else "SQLite demo"
        self.conn = None
        self.ibm = None
        if self.mode == "IBM Db2":
            try:
                import ibm_db
                self.ibm = ibm_db
                conn_str = (
                    f"DATABASE={os.getenv('DB2_DATABASE')};"
                    f"HOSTNAME={os.getenv('DB2_HOST')};"
                    f"PORT={os.getenv('DB2_PORT','50000')};"
                    f"PROTOCOL={os.getenv('DB2_PROTOCOL','TCPIP')};"
                    f"UID={os.getenv('DB2_USERNAME')};"
                    f"PWD={os.getenv('DB2_PASSWORD')};"
                )
                self.conn = ibm_db.connect(conn_str, "", "")
            except Exception as exc:
                raise RuntimeError(f"Could not connect to configured IBM Db2 instance: {exc}") from exc
        else:
            db_path = Path(os.getenv("SQLITE_PATH", "./data/sentinel_demo.db"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_demo()

    def _init_demo(self):
        self.conn.executescript(DEMO_DB_SCHEMA)
        count = self.conn.execute("SELECT COUNT(*) FROM supplier").fetchone()[0]
        if count == 0:
            self.conn.executemany("INSERT INTO supplier VALUES (?,?,?,?)", [
                ("SUP-01","Northstar Components",82.0,"ACTIVE"),
                ("SUP-02","Apex Industrial Supply",96.0,"ACTIVE")])
            self.conn.executemany("INSERT INTO component VALUES (?,?,?,?)", [
                ("CMP-CTRL-01","Motor Controller Unit","CRITICAL",30),
                ("CMP-BOLT-02","Mounting Bolt Set","MEDIUM",12)])
            self.conn.executemany("INSERT INTO inventory VALUES (?,?,?)", [
                ("CMP-CTRL-01",180,90),("CMP-BOLT-02",500,100)])
            self.conn.executemany("INSERT INTO purchase_order VALUES (?,?,?,?,?,?)", [
                ("PO-4401","SUP-01","CMP-CTRL-01",300,"2026-11-12","IN_TRANSIT"),
                ("PO-4402","SUP-02","CMP-BOLT-02",600,"2026-11-13","IN_TRANSIT")])
            self.conn.executemany("INSERT INTO shipment_event VALUES (?,?,?,?,?,?)", [
                ("SHIP-1008","PO-4401","DELAYED","2026-11-08","2026-11-16","Carrier update: revised ETA is eight days later."),
                ("SHIP-1009","PO-4402","ON_TIME","2026-11-13","2026-11-13","Shipment tracking normal.")])
            self.conn.executemany("INSERT INTO quality_inspection VALUES (?,?,?,?)", [
                ("QI-7001","CMP-CTRL-01","PASSED","2026-11-01"),
                ("QI-7002","CMP-BOLT-02","PASSED","2026-11-02")])
            self.conn.executemany("INSERT INTO production_order VALUES (?,?,?,?,?)", [
                ("PROD-2101","CMP-CTRL-01",120,"2026-11-12","PLANNED"),
                ("PROD-2102","CMP-CTRL-01",100,"2026-11-14","PLANNED"),
                ("PROD-2103","CMP-CTRL-01",80,"2026-11-18","PLANNED"),
                ("PROD-2201","CMP-BOLT-02",100,"2026-11-15","PLANNED")])
            self.conn.commit()

    def _query(self, sql, params=()):
        if self.mode == "SQLite demo":
            cur = self.conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
        stmt = self.ibm.prepare(self.conn, sql)
        self.ibm.execute(stmt, params)
        rows=[]
        result=self.ibm.fetch_assoc(stmt)
        while result:
            rows.append({k.lower():v for k,v in result.items()})
            result=self.ibm.fetch_assoc(stmt)
        return rows

    def get_disruption_context(self, shipment_id):
        # All values supplied by the user are bound parameters, never interpolated into SQL.
        if self.mode == "IBM Db2":
            sql = """
            SELECT s.SHIPMENT_ID AS shipment_id, s.EVENT_STATUS AS event_status,
                   s.ORIGINAL_ETA AS original_eta, s.REVISED_ETA AS revised_eta,
                   s.EVENT_NOTE AS event_note, p.PO_ID AS po_id, p.ORDER_QTY AS order_qty,
                   p.COMPONENT_ID AS component_id, p.SUPPLIER_ID AS supplier_id,
                   sup.SUPPLIER_NAME AS supplier_name, sup.ON_TIME_RATE AS on_time_rate,
                   c.COMPONENT_NAME AS component_name, c.CRITICALITY AS criticality,
                   c.DAILY_DEMAND AS daily_demand, i.ON_HAND_QTY AS on_hand_qty,
                   i.RESERVED_QTY AS reserved_qty, q.QUALITY_STATUS AS quality_status
            FROM SHIPMENT_EVENT s
            JOIN PURCHASE_ORDER p ON p.PO_ID=s.PO_ID
            JOIN SUPPLIER sup ON sup.SUPPLIER_ID=p.SUPPLIER_ID
            JOIN COMPONENT c ON c.COMPONENT_ID=p.COMPONENT_ID
            JOIN INVENTORY i ON i.COMPONENT_ID=c.COMPONENT_ID
            LEFT JOIN QUALITY_INSPECTION q ON q.COMPONENT_ID=c.COMPONENT_ID
            WHERE s.SHIPMENT_ID = ?
            """
        else:
            sql = """
            SELECT s.shipment_id, s.event_status, s.original_eta, s.revised_eta,
                   s.event_note, p.po_id, p.order_qty, p.component_id, p.supplier_id,
                   sup.supplier_name, sup.on_time_rate, c.component_name, c.criticality,
                   c.daily_demand, i.on_hand_qty, i.reserved_qty, q.quality_status
            FROM shipment_event s
            JOIN purchase_order p ON p.po_id=s.po_id
            JOIN supplier sup ON sup.supplier_id=p.supplier_id
            JOIN component c ON c.component_id=p.component_id
            JOIN inventory i ON i.component_id=c.component_id
            LEFT JOIN quality_inspection q ON q.component_id=c.component_id
            WHERE s.shipment_id = ?
            """
        rows=self._query(sql,(shipment_id,))
        if not rows:
            raise ValueError(f"No shipment found for ID {shipment_id}")
        context=rows[0]
        context["production_orders"]=self._query(
            "SELECT production_order_id, required_qty, required_date, order_status FROM production_order WHERE component_id = ? AND order_status <> ? ORDER BY required_date",
            (context["component_id"],"COMPLETED"))
        return context

    def create_risk_case(self, case_id, shipment_id, component_id, severity, summary):
        now=datetime.utcnow().isoformat()
        if self.mode == "IBM Db2":
            sql="INSERT INTO RISK_CASE (CASE_ID, SHIPMENT_ID, COMPONENT_ID, SEVERITY, SUMMARY) VALUES (?,?,?,?,?)"
            stmt=self.ibm.prepare(self.conn,sql); self.ibm.execute(stmt,(case_id,shipment_id,component_id,severity,summary))
            self.ibm.commit(self.conn)
        else:
            self.conn.execute("INSERT OR REPLACE INTO risk_case VALUES (?,?,?,?,?,?)",
                              (case_id,shipment_id,component_id,severity,summary,now))
            self.conn.commit()

    def record_recommendations(self, case_id, options):
        for idx,opt in enumerate(options,1):
            rid=f"{case_id}-R{idx}"
            if self.mode == "IBM Db2":
                stmt=self.ibm.prepare(self.conn,
                    "INSERT INTO RECOMMENDATION (RECOMMENDATION_ID, CASE_ID, OPTION_NAME, RATIONALE, STATUS) VALUES (?,?,?,?,?)")
                self.ibm.execute(stmt,(rid,case_id,opt["name"],opt["rationale"],"PROPOSED"))
            else:
                self.conn.execute("INSERT OR REPLACE INTO recommendation VALUES (?,?,?,?,?,?,?)",
                    (rid,case_id,opt["name"],opt["rationale"],"PROPOSED",datetime.utcnow().isoformat()))
        if self.mode == "IBM Db2": self.ibm.commit(self.conn)
        else: self.conn.commit()

    def record_approval(self, case_id, recommendation_id, decision, approver, rationale):
        audit_id=f"AUD-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        if self.mode == "IBM Db2":
            stmt=self.ibm.prepare(self.conn,
                "INSERT INTO APPROVAL_AUDIT (AUDIT_ID, CASE_ID, RECOMMENDATION_ID, DECISION, APPROVER, RATIONALE) VALUES (?,?,?,?,?,?)")
            self.ibm.execute(stmt,(audit_id,case_id,recommendation_id,decision,approver,rationale))
            self.ibm.commit(self.conn)
        else:
            self.conn.execute("INSERT INTO approval_audit VALUES (?,?,?,?,?,?,?)",
                (audit_id,case_id,recommendation_id,decision,approver,rationale,datetime.utcnow().isoformat()))
            self.conn.commit()
        return audit_id

    def list_recent_cases(self):
        if self.mode == "IBM Db2":
            return self._query("SELECT CASE_ID AS case_id, SHIPMENT_ID AS shipment_id, COMPONENT_ID AS component_id, SEVERITY AS severity, SUMMARY AS summary, CREATED_AT AS created_at FROM RISK_CASE ORDER BY CREATED_AT DESC FETCH FIRST 20 ROWS ONLY")
        return self._query("SELECT case_id, shipment_id, component_id, severity, summary, created_at FROM risk_case ORDER BY created_at DESC LIMIT 20")

    def close(self):
        if self.conn:
            if self.mode == "IBM Db2": self.ibm.close(self.conn)
            else: self.conn.close()
