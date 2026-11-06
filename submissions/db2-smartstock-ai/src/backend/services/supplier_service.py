"""
Supplier Directory & Vendor Management Service for IBM Db2.
"""

import uuid
from typing import List, Dict, Any, Optional
from db.db2_client import db_client

class SupplierService:
    @staticmethod
    def get_all_suppliers() -> List[Dict[str, Any]]:
        sql = "SELECT supplier_id, supplier_name, contact, lead_time_days, rating, min_order_qty FROM SUPPLIERS ORDER BY supplier_name"
        rows = db_client.query(sql)
        for r in rows:
            r['lead_time_days'] = int(r.get('lead_time_days', 2) or 2)
            r['rating'] = float(r.get('rating', 4.5) or 4.5)
            r['min_order_qty'] = float(r.get('min_order_qty', 5.0) or 5.0)
        return rows

    @staticmethod
    def add_supplier(data: Dict[str, Any]) -> bool:
        sid = data.get("supplier_id") or f"SUP_{uuid.uuid4().hex[:6].upper()}"
        sql = """
        INSERT INTO SUPPLIERS (supplier_id, supplier_name, contact, lead_time_days, rating, min_order_qty)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        return db_client.execute(sql, [
            sid,
            data['supplier_name'],
            data.get('contact', ''),
            int(data.get('lead_time_days', 2)),
            float(data.get('rating', 4.5)),
            float(data.get('min_order_qty', 5.0))
        ])

    @staticmethod
    def delete_supplier(supplier_id: str) -> bool:
        sql = "DELETE FROM SUPPLIERS WHERE supplier_id = ?"
        return db_client.execute(sql, [supplier_id])

