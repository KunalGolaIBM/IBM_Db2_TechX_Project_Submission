from datetime import date, timedelta
from src.models import InventoryItem, Recommendation
from src.config import DATA_BACKEND

class DemoRepository:
    """Synthetic in-memory data for local demonstration only."""
    def __init__(self):
        self.items = [
            InventoryItem(medicine_id="MED-001", medicine_name="Amoxicillin 500 mg", on_hand=500, reorder_level=250, avg_daily_use=65, supplier_lead_days=10, nearest_expiry=date.today()+timedelta(days=48), expiring_quantity=40),
            InventoryItem(medicine_id="MED-002", medicine_name="Paracetamol 500 mg", on_hand=1800, reorder_level=600, avg_daily_use=90, supplier_lead_days=5, nearest_expiry=date.today()+timedelta(days=130), expiring_quantity=0),
            InventoryItem(medicine_id="MED-003", medicine_name="ORS Sachet", on_hand=120, reorder_level=200, avg_daily_use=28, supplier_lead_days=8, nearest_expiry=date.today()+timedelta(days=12), expiring_quantity=70),
        ]
        self.recommendations = {}
        self.events = []

    def list_inventory(self):
        return list(self.items)

    def save_recommendation(self, rec):
        self.recommendations[rec.recommendation_id] = rec

    def review_recommendation(self, recommendation_id, status, reviewer, quantity):
        rec = self.recommendations.get(recommendation_id)
        if not rec:
            raise KeyError("Recommendation not found")
        updated = rec.model_copy(update={"status": status, "suggested_quantity": quantity})
        self.recommendations[recommendation_id] = updated
        self.events.append({"recommendation_id": recommendation_id, "status": status, "reviewer": reviewer, "quantity": quantity})
        return updated

class Db2Repository:
    """IBM Db2 implementation using ibm_db and bound SQL parameters."""
    def __init__(self):
        import ibm_db
        from src.config import DB2_HOST, DB2_PORT, DB2_DATABASE, DB2_USER, DB2_PASSWORD, DB2_SECURITY
        if not DB2_PASSWORD:
            raise RuntimeError("DB2_PASSWORD is missing.")
        security = "Security=SSL;" if DB2_SECURITY else ""
        dsn = f"DATABASE={DB2_DATABASE};HOSTNAME={DB2_HOST};PORT={DB2_PORT};PROTOCOL=TCPIP;UID={DB2_USER};PWD={DB2_PASSWORD};{security}"
        self.ibm_db = ibm_db
        self.conn = ibm_db.connect(dsn, "", "")

    def _query(self, sql, params=()):
        stmt = self.ibm_db.prepare(self.conn, sql)
        for index, value in enumerate(params, start=1):
            self.ibm_db.bind_param(stmt, index, value)
        self.ibm_db.execute(stmt)
        rows, row = [], self.ibm_db.fetch_assoc(stmt)
        while row:
            rows.append({key.lower(): value for key, value in row.items()})
            row = self.ibm_db.fetch_assoc(stmt)
        return rows

    def list_inventory(self):
        sql = """SELECT m.medicine_id, m.medicine_name, i.on_hand, m.reorder_level,
        m.avg_daily_use, s.lead_days AS supplier_lead_days,
        MIN(b.expiry_date) AS nearest_expiry,
        COALESCE(SUM(CASE WHEN b.expiry_date <= CURRENT DATE + 30 DAYS THEN b.quantity ELSE 0 END), 0) AS expiring_quantity
        FROM medicines m JOIN inventory i ON i.medicine_id=m.medicine_id
        LEFT JOIN batches b ON b.medicine_id=m.medicine_id
        LEFT JOIN suppliers s ON s.supplier_id=m.supplier_id
        GROUP BY m.medicine_id,m.medicine_name,i.on_hand,m.reorder_level,m.avg_daily_use,s.lead_days"""
        result = []
        for row in self._query(sql):
            expiry = row.get("nearest_expiry")
            if expiry and not isinstance(expiry, date):
                expiry = date.fromisoformat(str(expiry)[:10])
            result.append(InventoryItem(medicine_id=str(row["medicine_id"]), medicine_name=row["medicine_name"],
                on_hand=int(row["on_hand"]), reorder_level=int(row["reorder_level"]),
                avg_daily_use=float(row["avg_daily_use"]), supplier_lead_days=int(row.get("supplier_lead_days") or 0),
                nearest_expiry=expiry, expiring_quantity=int(row.get("expiring_quantity") or 0)))
        return result

    def save_recommendation(self, rec):
        sql = "INSERT INTO recommendations (recommendation_id,medicine_id,suggested_quantity,days_of_cover,rationale,status,created_at) VALUES (?,?,?,?,?,?,CURRENT TIMESTAMP)"
        stmt = self.ibm_db.prepare(self.conn, sql)
        values = [rec.recommendation_id, rec.medicine_id, rec.suggested_quantity, rec.days_of_cover, "; ".join(rec.rationale), rec.status]
        for index, value in enumerate(values, start=1):
            self.ibm_db.bind_param(stmt, index, value)
        self.ibm_db.execute(stmt)
        self.ibm_db.commit(self.conn)

    def review_recommendation(self, recommendation_id, status, reviewer, quantity):
        # Fetch the recommendation first so the API returns the actual medicine context.
        lookup = """SELECT r.recommendation_id, r.medicine_id, m.medicine_name,
        r.suggested_quantity, r.days_of_cover, r.rationale
        FROM recommendations r JOIN medicines m ON m.medicine_id=r.medicine_id
        WHERE r.recommendation_id=?"""
        rows = self._query(lookup, (recommendation_id,))
        if not rows:
            raise KeyError("Recommendation not found")
        row = rows[0]
        update_sql = "UPDATE recommendations SET status=?, suggested_quantity=? WHERE recommendation_id=?"
        stmt = self.ibm_db.prepare(self.conn, update_sql)
        for index, value in enumerate([status, quantity, recommendation_id], start=1):
            self.ibm_db.bind_param(stmt, index, value)
        self.ibm_db.execute(stmt)
        audit_sql = "INSERT INTO approval_events (recommendation_id,reviewer,action,approved_quantity,created_at) VALUES (?,?,?,?,CURRENT TIMESTAMP)"
        audit = self.ibm_db.prepare(self.conn, audit_sql)
        for index, value in enumerate([recommendation_id, reviewer, status, quantity], start=1):
            self.ibm_db.bind_param(audit, index, value)
        self.ibm_db.execute(audit)
        self.ibm_db.commit(self.conn)
        rationale = row.get("rationale") or "Review recorded in IBM Db2"
        return Recommendation(recommendation_id=recommendation_id,
            medicine_id=str(row["medicine_id"]), medicine_name=row["medicine_name"],
            suggested_quantity=quantity, days_of_cover=float(row["days_of_cover"]),
            rationale=str(rationale).split("; "), status=status)

def get_repository():
    return Db2Repository() if DATA_BACKEND == "db2" else DemoRepository()
