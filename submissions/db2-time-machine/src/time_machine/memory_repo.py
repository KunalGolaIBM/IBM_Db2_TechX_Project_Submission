"""In-memory test double that mimics Db2 system-period temporal semantics.

It exists so the agents, the graph and the API can be unit-tested without a Db2 server.
It is NOT used by the application: the real app always talks to Db2 (see ``repository.py``).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from .models import MetricPoint, Version, fmt_ts, money, parse_ts
from .temporal_sql import ORDER_ITEMS


class MemoryRepository:
    table = ORDER_ITEMS

    def __init__(self, now: datetime):
        self._now = now
        self.versions_store: list[Version] = []
        self._products = []
        self._snapshots: list[dict] = []
        self._deletes: list[dict] = []
        self.audit: list[dict] = []
        self.reports: dict[str, dict] = {}
        self.queries: list[str] = []
        self._txn = 0

    # -- scenario builders -------------------------------------------------
    def add_product(self, product_id: int, name: str, category: str = "General") -> None:
        self._products.append({"product_id": product_id, "name": name, "category": category})

    def _next_txn(self, at: datetime) -> str:
        self._txn += 1
        return f"{fmt_ts(at)}{self._txn:06d}"[:32]

    def insert(self, at: datetime, item_id, order_id, product_id, qty, price, actor="erp_loader", txn=None) -> None:
        txn = txn or self._next_txn(at)
        self.versions_store.append(Version(item_id, order_id, product_id, qty, money(price), actor, at, None, txn))

    def update(self, at: datetime, item_id, *, qty=None, price=None, actor="erp_loader", txn=None) -> None:
        cur = next(v for v in self.versions_store if v.item_id == item_id and v.sys_end is None)
        cur.sys_end = at
        self.versions_store.append(replace(
            cur, quantity=cur.quantity if qty is None else qty,
            unit_price=cur.unit_price if price is None else money(price),
            changed_by=actor, sys_start=at, sys_end=None, trans_id=txn or self._next_txn(at)))

    def delete(self, at: datetime, item_id, actor="cleanup_job") -> None:
        cur = next(v for v in self.versions_store if v.item_id == item_id and v.sys_end is None)
        cur.sys_end = at
        self._deletes.append({"item_id": item_id, "deleted_by": actor, "deleted_at": fmt_ts(at)})

    def snapshot(self, at: datetime, product_id: int) -> None:
        rev = sum((v.revenue for v in self._as_of(at) if v.product_id == product_id), Decimal("0"))
        self._snapshots.append({"product_id": product_id, "revenue": rev, "snapshot_ts": at})

    def set_now(self, now: datetime) -> None:
        self._now = now

    # -- temporal reads ----------------------------------------------------
    def _as_of(self, ts):
        return [v for v in self.versions_store if v.sys_start <= ts and (v.sys_end is None or v.sys_end > ts)]

    def now(self):
        return self._now

    def products(self):
        return list(self._products)

    def last_snapshot(self, product_id):
        rows = [s for s in self._snapshots if product_id is None or s["product_id"] == product_id]
        if not rows:
            return None
        s = max(rows, key=lambda r: r["snapshot_ts"])
        return {"ts": s["snapshot_ts"], "revenue": s["revenue"], "product_id": s["product_id"]}

    def metric_as_of(self, product_id, ts):
        from . import temporal_sql as q
        sql = q.metric_as_of_sql(self.table, product_id, ts)
        self.queries.append(sql)
        rows = [v for v in self._as_of(ts) if product_id is None or v.product_id == product_id]
        return MetricPoint(ts, sum((v.revenue for v in rows), Decimal("0")), len(rows), sql)

    def versions(self, product_id, start, end):
        from . import temporal_sql as q
        sql = q.versions_sql(self.table, product_id, start, end)
        self.queries.append(sql)
        rows = []
        for v in self.versions_store:
            if product_id is not None and v.product_id != product_id:
                continue
            if v.sys_start < end and (v.sys_end is None or v.sys_end > start):
                rows.append({
                    "item_id": v.item_id, "order_id": v.order_id, "product_id": v.product_id,
                    "quantity": v.quantity, "unit_price": v.unit_price, "changed_by": v.changed_by,
                    "sys_start": fmt_ts(v.sys_start),
                    "sys_end": fmt_ts(v.sys_end) if v.sys_end else "9999-12-30 00:00:00.000000",
                    "trans_id": v.trans_id})
        rows.sort(key=lambda r: (r["item_id"], r["sys_start"]))
        return rows, sql

    def delete_log(self, start, end):
        from . import temporal_sql as q
        sql = q.delete_log_sql(start, end)
        rows = [d for d in self._deletes if start <= parse_ts(d["deleted_at"]) <= end]
        return rows, sql

    def temporal_tables(self):
        return [{"tabname": "ORDER_ITEMS", "temporaltype": "S"}]

    # -- fixed writers -----------------------------------------------------
    def write_audit(self, entry):
        self.audit.append(dict(entry))

    def list_audit(self, run_id):
        return [a for a in self.audit if a["run_id"] == run_id]

    def save_report(self, report):
        self.reports[report["run_id"]] = report

    def list_reports(self, limit=20):
        return [{"run_id": r["run_id"], "question": r["question"], "status": r["verdict"]["status"]}
                for r in list(self.reports.values())[-limit:]]

    def get_report(self, run_id):
        return self.reports.get(run_id)

    def curve(self, product_id, start, end, points=20):
        step = (end - start) / max(points - 1, 1)
        return [{"ts": fmt_ts(start + step * i),
                 "revenue": str(self.metric_as_of(product_id, start + step * i).revenue)} for i in range(points)]


def demo_scenario(fault: str = "price") -> tuple["MemoryRepository", datetime]:
    """Build a small deterministic dataset with one injected fault. Returns (repo, snapshot_ts)."""
    t0 = datetime(2026, 11, 9, 8, 0, 0)
    repo = MemoryRepository(now=t0 + timedelta(hours=3))
    repo.add_product(1, "Aurora Laptop", "Computers")
    repo.add_product(2, "Pulse Headphones", "Audio")
    item = 0
    for order in range(1, 41):  # baseline load, 40 orders
        for pid, price in ((1, 500), (2, 120)):
            if (order + pid) % 2 == 0 or order % 3 == 0:
                item += 1
                repo.insert(t0, item, order, pid, 1 + order % 3, price, "erp_loader", txn="T-LOAD-0001")
    snap = t0 + timedelta(minutes=30)
    repo.snapshot(snap, 1)
    repo.snapshot(snap, 2)
    # normal business activity after the snapshot: three new orders
    for k in range(3):
        item += 1
        repo.insert(t0 + timedelta(minutes=45 + k), item, 100 + k, 1, 1, 500, "web_checkout")
    if fault == "price":
        for it in [v.item_id for v in repo.versions_store if v.product_id == 1 and v.sys_end is None][:12]:
            repo.update(t0 + timedelta(hours=2), it, price=50, actor="nightly_batch", txn="T-NIGHTLY-0042")
    elif fault == "duplicate":
        for v in [v for v in repo.versions_store if v.product_id == 1 and v.sys_start == t0][:10]:
            item += 1
            repo.insert(t0 + timedelta(hours=2), item, v.order_id, 1, v.quantity, v.unit_price, "etl_rerun",
                        txn="T-ETL-0099")
    elif fault == "quantity":
        for it in [v.item_id for v in repo.versions_store if v.product_id == 1 and v.sys_end is None][:9]:
            repo.update(t0 + timedelta(hours=2), it, qty=0, actor="bulk_import", txn="T-BULK-0007")
    elif fault == "deleted":
        for it in [v.item_id for v in repo.versions_store if v.product_id == 1 and v.sys_end is None][:8]:
            repo.delete(t0 + timedelta(hours=2), it, actor="cleanup_job")
    return repo, snap
