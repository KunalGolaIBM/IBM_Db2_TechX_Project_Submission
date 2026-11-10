"""Question understanding helpers: heuristic parsing and time-window resolution."""
from __future__ import annotations

import difflib
import re
from datetime import datetime, timedelta
from typing import Optional

from .models import PATTERNS

DOWN_WORDS = ("drop", "fell", "fall", "decreas", "declin", "lower", "less", "down", "dip", "shrank", "missing", "too low")
UP_WORDS = ("increas", "rise", "rose", "spike", "jump", "higher", "more", "up", "inflat", "surge", "too high", "double")


def find_product(question: str, products: list[dict]) -> Optional[dict]:
    q = question.lower()
    for p in sorted(products, key=lambda p: -len(p["name"])):
        if p["name"].lower() in q:
            return p
    # token-level fuzzy match, e.g. "aurora" -> "Aurora Laptop"
    words = re.findall(r"[a-z0-9]+", q)
    best, best_score = None, 0.0
    for p in products:
        for tok in re.findall(r"[a-z0-9]+", p["name"].lower()):
            if len(tok) < 4:
                continue
            for w in words:
                score = difflib.SequenceMatcher(None, tok, w).ratio()
                if score > best_score:
                    best, best_score = p, score
    return best if best_score >= 0.84 else None


def detect_direction(question: str) -> str:
    q = question.lower()
    down = any(w in q for w in DOWN_WORDS)
    up = any(w in q for w in UP_WORDS)
    if down and not up:
        return "down"
    if up and not down:
        return "up"
    return "unknown"


def default_hypotheses(direction: str) -> list[str]:
    """Prior ordering of hypotheses (the Detective revises it with evidence on retries)."""
    if direction == "down":
        return ["rows_deleted", "quantity_change", "price_change", "duplicate_load"]
    if direction == "up":
        return ["duplicate_load", "price_change", "quantity_change", "rows_deleted"]
    return ["price_change", "quantity_change", "duplicate_load", "rows_deleted"]


def heuristic_time_spec(question: str) -> dict:
    q = question.lower()
    m = re.search(r"(?:last|past)\s+(\d+(?:\.\d+)?)\s*(minute|min|hour|hr|day)s?", q)
    if m:
        n, unit = float(m.group(1)), m.group(2)
        hours = n / 60 if unit.startswith("min") else n * 24 if unit == "day" else n
        return {"kind": "last_hours", "hours": hours}
    if "yesterday" in q:
        return {"kind": "yesterday"}
    if "today" in q:
        return {"kind": "today"}
    return {"kind": "since_snapshot"}


def resolve_window(spec: dict, now: datetime, snapshot_ts: Optional[datetime],
                   since: Optional[datetime] = None, until: Optional[datetime] = None) -> tuple[datetime, datetime, str]:
    """Turn a time spec into (start, end, label). Explicit since/until always win."""
    end = until or now
    if since:
        return since, end, f"{since:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M}"
    kind = spec.get("kind", "since_snapshot")
    if kind == "last_hours":
        hours = max(float(spec.get("hours", 24)), 0.05)
        return end - timedelta(hours=hours), end, f"last {hours:g} h"
    if kind == "yesterday":
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight - timedelta(days=1), midnight, "yesterday"
    if kind == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), end, "today"
    if snapshot_ts and snapshot_ts < end:
        return snapshot_ts, end, f"since the last KPI snapshot ({snapshot_ts:%H:%M})"
    return end - timedelta(hours=24), end, "last 24 h"


def valid_hypotheses(candidate) -> list[str]:
    seen, out = set(), []
    for h in candidate or []:
        if h in PATTERNS and h not in seen:
            seen.add(h)
            out.append(h)
    return out
