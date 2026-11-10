"""Plain data structures shared by the agents, the diff engine and the API."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

PATTERNS = ("price_change", "quantity_change", "duplicate_load", "rows_deleted")

PATTERN_TITLES = {
    "price_change": "Silent price change",
    "quantity_change": "Bulk quantity update",
    "duplicate_load": "Duplicate load",
    "rows_deleted": "Rows deleted",
    "new_rows": "New orders (normal activity)",
}

TS_FMT = "%Y-%m-%d %H:%M:%S.%f"


def parse_ts(value: Any) -> Optional[datetime]:
    """Parse a Db2 timestamp string (or datetime). The 'end of time' marker returns None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return None if value.year >= 9999 else value
    text = str(value).strip().replace("T", " ")
    if text.startswith("9999"):
        return None
    if "." in text:
        head, frac = text.split(".", 1)
        text = f"{head}.{(frac + '000000')[:6]}"
    else:
        text += ".000000"
    return datetime.strptime(text, TS_FMT)


def fmt_ts(value: Optional[datetime]) -> Optional[str]:
    return value.strftime(TS_FMT) if value else None


def money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


@dataclass
class Version:
    """One row version returned by a FOR SYSTEM_TIME query."""
    item_id: int
    order_id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    changed_by: Optional[str]
    sys_start: datetime
    sys_end: Optional[datetime]  # None = still current
    trans_id: Optional[str] = None

    @property
    def revenue(self) -> Decimal:
        return money(self.quantity * self.unit_price)

    def natural_key(self) -> tuple:
        return (self.order_id, self.product_id, self.quantity, str(self.unit_price))


@dataclass
class ChangeEvent:
    kind: str  # insert | update | delete
    item_id: int
    at: datetime
    txn: str
    actor: Optional[str]
    pattern: str
    impact: Decimal
    before: Optional[dict] = None
    after: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["at"] = fmt_ts(self.at)
        d["impact"] = str(self.impact)
        return d


@dataclass
class ChangeGroup:
    """Events that happened in one transaction with the same pattern."""
    txn: str
    pattern: str
    n_rows: int
    impact: Decimal
    actors: list
    first_at: datetime
    last_at: datetime
    sample: list = field(default_factory=list)

    @property
    def bulk(self) -> bool:
        return self.n_rows >= 5

    def to_dict(self) -> dict:
        return {
            "txn": self.txn, "pattern": self.pattern, "title": PATTERN_TITLES.get(self.pattern, self.pattern),
            "n_rows": self.n_rows, "impact": str(self.impact), "actors": self.actors, "bulk": self.bulk,
            "first_at": fmt_ts(self.first_at), "last_at": fmt_ts(self.last_at), "sample": self.sample,
        }


@dataclass
class MetricPoint:
    ts: datetime
    revenue: Decimal
    row_count: int
    sql: str


@dataclass
class Scope:
    """What the Detective decided to investigate."""
    product_id: Optional[int]
    product_name: Optional[str]
    direction: str  # up | down | unknown
    start: datetime
    end: datetime
    window_label: str
    hypotheses: list
    reasoning: str = ""
