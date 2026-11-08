"""Deterministic synthetic retail dataset.

Same seed => byte-identical dataset on every machine (pure `random.Random`, Decimal money,
no wall-clock input). The dataset deliberately contains traps that expose wrong analytical SQL:

* multi-line orders + multiple refund rows per line  -> refund x items join fan-out
* CANCELLED orders that still carry PROCESSED refunds (payment reversals)
* PENDING and REJECTED refunds that must not count
* PENDING orders (mostly late June) that are not yet revenue
* refunds processed in a later month than the order (cohort vs cash attribution)
* orders at 23:59:59 on month end / 00:00:00 on month start (date boundary bugs)
* 100%-discounted lines and a zero-price product (zero-revenue, still an order)
* order-level SHIPPING_AMOUNT that is not revenue (and multiplies after a line join)
* nullable PROMO_CODE / REASON_CODE columns
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

SEED = 20260107
CENT = Decimal("0.01")

MONTHLY_ORDER_TARGETS = {1: 430, 2: 410, 3: 480, 4: 500, 5: 540, 6: 560}
YEAR = 2026

REGION_WEIGHTS = {"NA": 40, "EMEA": 30, "APAC": 20, "LATAM": 10}
CHANNEL_WEIGHTS = {"WEB": 45, "MOBILE": 30, "STORE": 15, "MARKETPLACE": 10}
PROMOS = {"SPRING10": Decimal("0.10"), "WELCOME15": Decimal("0.15"), "VIP20": Decimal("0.20")}
REFUND_REASONS = ["DAMAGED", "NOT_AS_DESCRIBED", "LATE_DELIVERY", "CHANGED_MIND", None]

_CATALOG = {
    "ELECTRONICS": (["Wireless Earbuds", "USB-C Hub", "Smart Speaker", "Action Camera", "Mechanical Keyboard",
                     "Portable SSD 1TB", "Noise-Cancelling Headphones", "Fitness Tracker"], (29, 249)),
    "HOME": (["Ceramic Pour-Over Set", "Linen Throw", "Cast Iron Skillet", "LED Desk Lamp", "Glass Storage Set",
              "Bamboo Cutting Board", "Aroma Diffuser", "Wool Rug Small"], (14, 129)),
    "APPAREL": (["Merino Crew Sweater", "Rain Shell Jacket", "Organic Tee", "Chino Pants", "Running Socks 3-Pack",
                 "Leather Belt", "Canvas Sneakers", "Packable Down Vest"], (12, 159)),
    "BEAUTY": (["Vitamin C Serum", "Mineral Sunscreen", "Clay Mask", "Hydrating Cleanser", "Lip Balm Trio",
                "Hair Repair Oil", "Night Cream", "Sample Kit"], (8, 69)),
    "SPORTS": (["Yoga Mat Pro", "Adjustable Dumbbell", "Trail Water Bottle", "Resistance Bands", "Cycling Gloves",
                "Foam Roller", "Jump Rope Speed", "Hiking Daypack"], (9, 189)),
}


@dataclass(frozen=True)
class Product:
    product_id: int
    sku: str
    product_name: str
    category: str
    list_price: Decimal
    is_active: int


@dataclass(frozen=True)
class Order:
    order_id: int
    order_number: str
    customer_id: int
    order_ts: datetime
    status: str
    region_code: str
    channel_code: str
    shipping_amount: Decimal
    promo_code: str | None
    cancelled_ts: datetime | None


@dataclass(frozen=True)
class OrderItem:
    order_item_id: int
    order_id: int
    line_number: int
    product_id: int
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal

    @property
    def line_revenue(self) -> Decimal:
        return self.quantity * self.unit_price - self.discount_amount


@dataclass(frozen=True)
class Refund:
    refund_id: int
    order_id: int
    order_item_id: int
    refund_ts: datetime
    refund_amount: Decimal
    status: str
    reason_code: str | None


@dataclass
class Dataset:
    seed: int
    products: list[Product] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    items: list[OrderItem] = field(default_factory=list)
    refunds: list[Refund] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "products": len(self.products),
            "orders": len(self.orders),
            "order_items": len(self.items),
            "refunds": len(self.refunds),
        }


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _pick(rng: random.Random, weights: dict) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def _month_end(month: int) -> datetime:
    nxt = datetime(YEAR + (month == 12), month % 12 + 1, 1)
    return nxt - timedelta(seconds=1)


def _products(rng: random.Random) -> list[Product]:
    out: list[Product] = []
    pid = 101
    for category, (names, (lo, hi)) in _CATALOG.items():
        for idx, name in enumerate(names):
            price = Decimal("0.00") if name == "Sample Kit" else Decimal(rng.randint(lo, hi)) + Decimal("0.99")
            out.append(Product(pid, f"{category[:3]}-{idx + 1:03d}", name, category, price, 1))
            pid += 1
    return out


def generate(seed: int = SEED) -> Dataset:
    rng = random.Random(seed)
    ds = Dataset(seed=seed, products=_products(rng))
    sellable = [p for p in ds.products if p.list_price > 0]
    sample_kit = next(p for p in ds.products if p.product_name == "Sample Kit")

    # ---- order headers ---------------------------------------------------------------
    raw: list[tuple[datetime, str, str]] = []
    for month, target in MONTHLY_ORDER_TARGETS.items():
        start = datetime(YEAR, month, 1)
        span = int((_month_end(month) - start).total_seconds())
        for _ in range(target):
            raw.append((start + timedelta(seconds=rng.randint(0, span)), _pick(rng, REGION_WEIGHTS),
                        _pick(rng, CHANNEL_WEIGHTS)))
    raw.sort(key=lambda r: r[0])

    item_id = 1
    refund_id = 1
    for order_id, (ts, region, channel) in enumerate(raw, start=1):
        late_june = ts.month == 6 and ts.day >= 25
        roll = rng.random()
        if roll < (0.30 if late_june else 0.03):
            status = "PENDING"
        elif roll < (0.38 if late_june else 0.11):
            status = "CANCELLED"
        else:
            status = "COMPLETED"
        promo = rng.choice(list(PROMOS)) if rng.random() < 0.20 else None

        n_lines = rng.choices([1, 2, 3, 4, 5], weights=[35, 30, 20, 10, 5], k=1)[0]
        chosen = rng.sample(sellable, n_lines)
        if rng.random() < 0.03:  # free sample added to the basket
            chosen.append(sample_kit)
        lines: list[OrderItem] = []
        for ln, product in enumerate(chosen, start=1):
            qty = rng.choices([1, 2, 3], weights=[70, 22, 8], k=1)[0]
            gross = qty * product.list_price
            if promo:
                discount = _q(gross * PROMOS[promo])
            elif product.list_price > 0 and rng.random() < 0.01:
                discount = gross  # 100% discount (goodwill / free gift)
            elif rng.random() < 0.10:
                discount = _q(gross * Decimal(rng.randint(5, 30)) / Decimal(100))
            else:
                discount = Decimal("0.00")
            lines.append(OrderItem(item_id, order_id, ln, product.product_id, qty, product.list_price, discount))
            item_id += 1

        merch = sum((li.line_revenue for li in lines), Decimal("0"))
        shipping = Decimal("0.00") if channel == "STORE" or merch >= 100 else Decimal("7.99")
        cancelled_ts = ts + timedelta(hours=rng.randint(1, 48)) if status == "CANCELLED" else None
        ds.orders.append(Order(order_id, f"MG-{YEAR}-{order_id:06d}", rng.randint(1, 900), ts, status, region,
                               channel, shipping, promo, cancelled_ts))
        ds.items.extend(lines)

        # ---- refunds -----------------------------------------------------------------
        def add_refund(line: OrderItem, amount: Decimal, when: datetime, rstatus: str, reason: str | None) -> None:
            nonlocal refund_id
            ds.refunds.append(Refund(refund_id, order_id, line.order_item_id, when, amount, rstatus, reason))
            refund_id += 1

        paid_lines = [li for li in lines if li.line_revenue > 0]
        if not paid_lines:
            continue
        if status == "CANCELLED":
            assert cancelled_ts is not None
            if rng.random() < 0.5:  # payment captured then reversed
                for li in paid_lines:
                    add_refund(li, li.line_revenue, cancelled_ts, "PROCESSED", "ORDER_CANCELLED")
            continue
        if status != "COMPLETED":
            continue
        roll = rng.random()
        if roll < 0.06:  # full refund of every line
            when = ts + timedelta(days=rng.randint(3, 40), hours=rng.randint(0, 23))
            reason = rng.choice(REFUND_REASONS)
            for li in paid_lines:
                add_refund(li, li.line_revenue, when, "PROCESSED", reason)
        elif roll < 0.15:  # partial refund on one line, sometimes in two installments
            li = rng.choice(paid_lines)
            total = _q(li.line_revenue * Decimal(rng.randint(20, 70)) / Decimal(100))
            if total <= 0:
                continue
            when = ts + timedelta(days=rng.randint(2, 35), hours=rng.randint(0, 23))
            reason = rng.choice(REFUND_REASONS)
            if rng.random() < 0.35 and total >= Decimal("2.00"):
                first = _q(total * Decimal("0.6"))
                add_refund(li, first, when, "PROCESSED", reason)
                add_refund(li, total - first, when + timedelta(days=rng.randint(1, 10)), "PROCESSED", reason)
            else:
                add_refund(li, total, when, "PROCESSED", reason)
            extra = rng.random()
            if extra < 0.15:  # a rejected claim on top of the processed one
                add_refund(li, _q(li.line_revenue * Decimal("0.5")), when + timedelta(days=3), "REJECTED", "CHANGED_MIND")
            elif extra < 0.25:  # still pending review
                add_refund(li, _q(li.line_revenue * Decimal("0.3")), when + timedelta(days=5), "PENDING", None)

    _add_canaries(ds)
    return ds


# Hand-checkable canary orders (expected values are documented in docs/METRIC_SEMANTICS.md §6).
CANARY_ORDER_IDS = (90001, 90002, 90003, 90004)


def _add_canaries(ds: Dataset) -> None:
    p = {prod.sku: prod for prod in ds.products}
    earbuds, hub, lamp, mat = p["ELE-001"], p["ELE-002"], p["HOM-004"], p["SPO-001"]
    D = Decimal

    # C1: last second of January, two lines, two processed installments + one rejected refund.
    ds.orders.append(Order(90001, "MG-CANARY-0001", 999, datetime(2026, 1, 31, 23, 59, 59), "COMPLETED",
                           "EMEA", "WEB", D("7.99"), None, None))
    ds.items += [OrderItem(900011, 90001, 1, earbuds.product_id, 2, D("50.00"), D("10.00")),
                 OrderItem(900012, 90001, 2, hub.product_id, 1, D("20.00"), D("0.00"))]
    ds.refunds += [Refund(900001, 90001, 900011, datetime(2026, 2, 3, 10, 0), D("15.00"), "PROCESSED", "DAMAGED"),
                   Refund(900002, 90001, 900011, datetime(2026, 2, 9, 10, 0), D("5.00"), "PROCESSED", "DAMAGED"),
                   Refund(900003, 90001, 900011, datetime(2026, 2, 10, 10, 0), D("30.00"), "REJECTED", None)]
    # C2: first second of February, fully refunded in March (cohort attribution -> February).
    ds.orders.append(Order(90002, "MG-CANARY-0002", 999, datetime(2026, 2, 1, 0, 0, 0), "COMPLETED",
                           "EMEA", "WEB", D("7.99"), None, None))
    ds.items.append(OrderItem(900021, 90002, 1, lamp.product_id, 1, D("40.00"), D("0.00")))
    ds.refunds.append(Refund(900004, 90002, 900021, datetime(2026, 3, 5, 12, 0), D("40.00"), "PROCESSED",
                             "NOT_AS_DESCRIBED"))
    # C3: cancelled order with a processed payment reversal -> excluded from every metric.
    ds.orders.append(Order(90003, "MG-CANARY-0003", 999, datetime(2026, 2, 14, 9, 30), "CANCELLED",
                           "NA", "MOBILE", D("0.00"), None, datetime(2026, 2, 14, 11, 0)))
    ds.items.append(OrderItem(900031, 90003, 1, mat.product_id, 1, D("100.00"), D("0.00")))
    ds.refunds.append(Refund(900005, 90003, 900031, datetime(2026, 2, 14, 11, 0), D("100.00"), "PROCESSED",
                             "ORDER_CANCELLED"))
    # C4: 100%-discounted single line -> zero revenue, still one completed order.
    ds.orders.append(Order(90004, "MG-CANARY-0004", 999, datetime(2026, 3, 10, 15, 0), "COMPLETED",
                           "APAC", "STORE", D("0.00"), None, None))
    ds.items.append(OrderItem(900041, 90004, 1, mat.product_id, 1, D("25.00"), D("25.00")))
