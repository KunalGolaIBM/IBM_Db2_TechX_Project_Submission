"""SPR's fare tables as time bands (RULE_JSON "time_bands", read by rules.band_check), copied from the policy text.

Written after the first unseen-domain run, whose two false allows (R05, R10) and two of its holds (R06, R07) turned on
which row of the fare table a cancellation time falls in. P-03 is the table for confirmed non-premium tickets; P-05 is
the Premium QuickBook rule. Bands of T in hours: from_h inclusive (P-02: "'At least' includes the threshold
exactly"), to_h exclusive. "For any flat charge, deduct no more than the passenger's base fare" is applied by the check.
"""

from __future__ import annotations

from typing import Any

P03: dict[int, list[dict[str, Any]]] = {
    1: [{"from_h": 48, "charge_inr": {"1A": 240, "2A": 200, "SL": 120, "2S": 60}},
        {"from_h": 12, "to_h": 48, "charge_inr": {"1A": 120, "2A": 100, "SL": 60, "2S": 30}},
        {"from_h": 4, "to_h": 12, "charge_pct": 50},
        {"to_h": 4, "refund": False}],
    2: [{"from_h": 36, "charge_inr": {"1A": 260, "2A": 220, "SL": 140, "2S": 70}},
        {"from_h": 10, "to_h": 36, "charge_inr": {"1A": 130, "2A": 110, "SL": 70, "2S": 35}},
        {"from_h": 3, "to_h": 10, "charge_pct": 50},
        {"to_h": 3, "refund": False}],
    3: [{"from_h": 24, "charge_inr": {"1A": 280, "2A": 240, "SL": 160, "2S": 80}},
        {"from_h": 8, "to_h": 24, "charge_inr": {"1A": 140, "2A": 120, "SL": 80, "2S": 40}},
        {"from_h": 2, "to_h": 8, "charge_pct": 60},
        {"to_h": 2, "refund": False}],
}
# P-05: v1 "No voluntary refund is available for a confirmed Premium QuickBook ticket at any time"; v2 and v3 a
# percentage charge at or beyond the threshold, non-refundable below it.
P05: dict[int, list[dict[str, Any]]] = {
    1: [{"refund": False}],
    2: [{"from_h": 36, "charge_pct": 30}, {"to_h": 36, "refund": False}],
    3: [{"from_h": 24, "charge_pct": 35}, {"to_h": 24, "refund": False}],
}
SECTIONS = {"P-03": P03, "P-05": P05}
