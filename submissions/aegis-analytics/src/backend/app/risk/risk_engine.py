from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLatestOut:
    p_return_below_minus_1pct: float
    p_return_below_minus_2pct: float


def risk_from_interval(*, interval_low: float, interval_high: float, low_tail_thresholds=( -0.01, -0.02)) -> RiskLatestOut:
    """
    MVP risk proxy using a simple uniform-in-interval assumption:
    p(return < t) = clamp((t - low)/(high - low), 0..1).
    """
    low = float(interval_low)
    high = float(interval_high)
    if high <= low:
        # degenerate interval: treat as deterministic at mid
        p1 = 1.0 if low < low_tail_thresholds[0] else 0.0
        p2 = 1.0 if low < low_tail_thresholds[1] else 0.0
        return RiskLatestOut(p_return_below_minus_1pct=p1, p_return_below_minus_2pct=p2)

    def p_below(t: float) -> float:
        p = (t - low) / (high - low)
        if p < 0.0:
            return 0.0
        if p > 1.0:
            return 1.0
        return float(p)

    p1 = p_below(float(low_tail_thresholds[0]))
    p2 = p_below(float(low_tail_thresholds[1]))
    return RiskLatestOut(p_return_below_minus_1pct=p1, p_return_below_minus_2pct=p2)

