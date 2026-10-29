from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PredictionLatest(BaseModel):
    symbol: str
    horizon: str
    timeframe: str
    ts_utc: datetime

    last_close: float
    expected_return: float
    expected_price: float

    p_up: Optional[float] = None

    interval_low: float
    interval_high: float

    model_version: str
    model_timestamp_utc: datetime


class RiskLatest(BaseModel):
    symbol: str
    horizon: str
    timeframe: str
    ts_utc: datetime

    expected_return: float
    interval_low: float
    interval_high: float

    # simple threshold-based risk measures (MVP)
    p_return_below_minus_1pct: float
    p_return_below_minus_2pct: float


class Bar(BaseModel):
    symbol: str
    timeframe: str
    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None


class BarsResponse(BaseModel):
    symbol: str
    timeframe: str
    bars: List[Bar]

