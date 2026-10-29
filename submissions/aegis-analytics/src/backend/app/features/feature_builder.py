from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple

import numpy as np
import pandas as pd

Timeframe = Literal["1m", "1d"]


@dataclass(frozen=True)
class HorizonSpec:
    horizon: str  # e.g. "5m", "1d"
    steps: int   # number of bars to look ahead


def _cyclical_features(series: pd.Series, period: float, prefix: str) -> pd.DataFrame:
    angle = 2.0 * np.pi * (series.astype(float) / period)
    return pd.DataFrame({f"{prefix}_sin": np.sin(angle), f"{prefix}_cos": np.cos(angle)}, index=series.index)


def add_time_features(df: pd.DataFrame, *, tz: str = "US/Eastern") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=df.index)

    idx = df.index
    if getattr(idx, "tzinfo", None) is not None or hasattr(idx, "tz"):
        try:
            local = idx.tz_convert(tz)
        except Exception:
            local = idx
    else:
        local = idx

    # DatetimeIndex exposes `.hour`, `.minute`, `.dayofweek` as vectorized arrays.
    # Wrap them as Series with index=df.index to preserve exact index and timezone when building cyclical features.
    if hasattr(local, "hour") and hasattr(local, "minute") and hasattr(local, "dayofweek"):
        hour_s = pd.Series(local.hour, index=df.index)
        minute_s = pd.Series(local.minute, index=df.index)
        dow_s = pd.Series(local.dayofweek, index=df.index)
    else:
        # Fallback for non-DatetimeIndex inputs.
        tmp_idx = pd.DatetimeIndex(pd.to_datetime(local))
        hour_s = pd.Series(tmp_idx.hour, index=df.index)
        minute_s = pd.Series(tmp_idx.minute, index=df.index)
        dow_s = pd.Series(tmp_idx.dayofweek, index=df.index)

    # intraday uses hour/min, daily mostly uses day-of-week
    out = []
    out.append(_cyclical_features(hour_s, 24.0, "hour"))
    out.append(_cyclical_features(minute_s, 60.0, "minute"))
    out.append(_cyclical_features(dow_s, 7.0, "dow"))
    return pd.concat(out, axis=1)


def _base_price_features(df: pd.DataFrame, *, windows_close: List[int], windows_ret: List[int]) -> pd.DataFrame:
    close = df["close"].astype(float)
    ret_1 = close.pct_change(1)

    feat = pd.DataFrame(index=df.index)
    feat["ret_1"] = ret_1
    feat["ret_2"] = close.pct_change(2)
    feat["ret_3"] = close.pct_change(3)
    feat["ret_5"] = close.pct_change(5)

    # rolling statistics on returns
    for w in windows_ret:
        feat[f"roll_mean_ret_{w}"] = ret_1.rolling(w).mean()
        feat[f"roll_std_ret_{w}"] = ret_1.rolling(w).std()

    # trend features using rolling mean of close
    for w in windows_close:
        ma = close.rolling(w).mean()
        feat[f"trend_ma_{w}"] = (close / ma) - 1.0

    feat = feat.replace([np.inf, -np.inf], np.nan)
    return feat


def horizons_from_config(timeframe: Timeframe, horizon_specs: List[str]) -> List[HorizonSpec]:
    out: List[HorizonSpec] = []
    for h in horizon_specs:
        h = h.lower().strip()
        if timeframe == "1m":
            if not h.endswith("m"):
                raise ValueError(f"Intraday timeframe expects horizons like '5m', got {h}")
            steps = int(h[:-1])
        elif timeframe == "1d":
            if not h.endswith("d"):
                raise ValueError(f"Daily timeframe expects horizons like '1d', got {h}")
            steps = int(h[:-1])
        else:
            raise ValueError(f"Unsupported timeframe {timeframe}")
        out.append(HorizonSpec(horizon=h, steps=steps))
    return out


def build_features_and_targets(
    df_bars: pd.DataFrame,
    *,
    timeframe: Timeframe,
    horizon: str,
    tz: str = "US/Eastern",
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Returns (X, y_return, y_up) for the requested horizon.
    y_return is future_return = close[t+steps]/close[t] - 1.
    y_up is classification label for direction (return > 0).
    """
    if df_bars.empty:
        return pd.DataFrame(), pd.Series(dtype=float), pd.Series(dtype=int)

    horizon = horizon.lower().strip()
    if timeframe == "1m":
        if not horizon.endswith("m"):
            raise ValueError("Expected intraday horizon like '5m'")
        steps = int(horizon[:-1])
        windows_close = [20, 60, 120]  # expressed in bars (minutes) for 1m
        windows_ret = [5, 15, 30]
    elif timeframe == "1d":
        if not horizon.endswith("d"):
            raise ValueError("Expected daily horizon like '1d'")
        steps = int(horizon[:-1])
        windows_close = [5, 10, 20]
        windows_ret = [5, 10, 20]
    else:
        raise ValueError("Unsupported timeframe")

    close = df_bars["close"].astype(float)
    future_close = close.shift(-steps)
    y_return = (future_close / close) - 1.0
    y_up = (y_return > 0).astype(int)

    # features at time t
    feat = _base_price_features(df_bars, windows_close=windows_close, windows_ret=windows_ret)
    feat = pd.concat([feat, add_time_features(df_bars, tz=tz)], axis=1)

    # drop rows with NaN features/targets
    dataset = feat.join(pd.DataFrame({"y_return": y_return, "y_up": y_up}))
    dataset = dataset.dropna()

    X = dataset.drop(columns=["y_return", "y_up"])
    y_ret = dataset["y_return"].astype(float)
    y_up = dataset["y_up"].astype(int)
    return X, y_ret, y_up


def build_latest_features(
    df_bars: pd.DataFrame,
    *,
    timeframe: Timeframe,
) -> pd.DataFrame:
    """
    Build only features (no targets) for the latest timestamp row.
    """
    if df_bars.empty:
        return pd.DataFrame()

    if timeframe == "1m":
        windows_close = [20, 60, 120]
        windows_ret = [5, 15, 30]
    elif timeframe == "1d":
        windows_close = [5, 10, 20]
        windows_ret = [5, 10, 20]
    else:
        raise ValueError("Unsupported timeframe")

    feat = _base_price_features(df_bars, windows_close=windows_close, windows_ret=windows_ret)
    feat = pd.concat([feat, add_time_features(df_bars)], axis=1)
    feat = feat.replace([np.inf, -np.inf], np.nan).dropna()
    return feat

