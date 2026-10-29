from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from backend.app.core.config import load_settings
from backend.app.features.feature_builder import Timeframe, build_latest_features
from backend.app.services.storage import fetch_bars, init_db, upsert_bars, upsert_prediction
from backend.app.services.yahoo_client import fetch_ohlcv


@dataclass(frozen=True)
class PredictionOut:
    symbol: str
    horizon: str
    timeframe: str

    ts_utc: datetime
    last_close: float

    expected_return: float
    expected_price: float

    p_up: Optional[float]
    interval_low: float
    interval_high: float

    model_version: str
    model_timestamp_utc: datetime


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_")


@lru_cache(maxsize=128)
def _load_artifact(artifact_path: str) -> dict:
    return joblib.load(artifact_path)


def _artifact_path(symbol: str, timeframe: str, horizon: str, model_dir: str, model_version: str) -> str:
    safe = _safe_symbol(symbol)
    return str(Path(model_dir) / f"{safe}_{timeframe}_{horizon}_{model_version}.joblib")


def _ensure_minimum_bars(df_bars: pd.DataFrame, *, timeframe: Timeframe, horizon: str) -> int:
    # Must be >= max rolling window + max lookahead + some margin.
    if timeframe == "1m":
        steps = int(horizon[:-1])
        return 120 + max(30, steps) + 10
    if timeframe == "1d":
        return 20 + 1 + 5
    raise ValueError("Unsupported timeframe")


def predict_latest(
    *,
    symbol: str,
    timeframe: Timeframe,
    horizon: str,
    model_version: str = "mvp_v1",
    db_path: Optional[str] = None,
) -> PredictionOut:
    settings = load_settings()
    if db_path is None:
        db_path = settings.data_db_path

    init_db(db_path)
    model_dir = settings.model_dir

    # Load most recent bars from DB; if insufficient, fetch from Yahoo and upsert.
    df_bars = fetch_bars(db_path, symbol=symbol, timeframe=timeframe)
    needed = _ensure_minimum_bars(df_bars, timeframe=timeframe, horizon=horizon)

    if len(df_bars) < needed:
        if timeframe == "1m":
            intraday_period = f"{settings.intraday_lookback_days}d"
            ydf = fetch_ohlcv(
                symbol,
                interval=settings.intraday_interval,
                period=intraday_period,
            )
        else:
            ydf = fetch_ohlcv(symbol, interval="1d", period="1y")

        if ydf.empty:
            raise RuntimeError(f"Yahoo returned no data for {symbol} {timeframe}")
        upsert_bars(db_path, symbol=symbol, timeframe=timeframe, df=ydf)
        df_bars = fetch_bars(db_path, symbol=symbol, timeframe=timeframe)

    if df_bars.empty:
        raise RuntimeError(f"No bars available for {symbol} {timeframe}")

    # Take only the tail required for feature calculations.
    df_tail = df_bars.tail(needed).copy()
    features_latest = build_latest_features(df_tail, timeframe=timeframe)
    if features_latest.empty:
        raise RuntimeError(f"Could not build features for {symbol} {timeframe} {horizon}")

    X_latest = features_latest.iloc[[-1]]  # keep 2D
    last_ts = features_latest.index[-1].to_pydatetime().replace(tzinfo=None)
    last_close = float(df_tail["close"].iloc[-1])

    artifact_path = _artifact_path(symbol, timeframe, horizon, model_dir, model_version=model_version)
    if not Path(artifact_path).exists():
        raise FileNotFoundError(f"Missing model artifact: {artifact_path}. Run `python ml/train.py` first.")
    artifact = _load_artifact(artifact_path)

    feature_columns = artifact["feature_columns"]
    # Align columns order to training time.
    X_latest = X_latest.reindex(columns=feature_columns)

    reg = artifact["regress"]
    expected_return = float(reg.predict(X_latest)[0])

    conformal = artifact["conformal"]
    interval_low_arr, interval_high_arr = conformal.predict_interval(np.array([expected_return]))
    interval_low = float(interval_low_arr[0])
    interval_high = float(interval_high_arr[0])

    # Calibrated directional probability
    direction = artifact["direction"]
    calibrator = artifact["calibrator"]
    p_raw = float(direction.predict_proba(X_latest)[:, 1][0])
    p_up = float(calibrator.predict_proba(np.array([p_raw]))[0])

    expected_price = last_close * (1.0 + expected_return)
    created_ts = datetime.now(timezone.utc).replace(tzinfo=None)
    model_timestamp_utc = artifact["trained_at_utc"]

    out = PredictionOut(
        symbol=symbol,
        horizon=horizon,
        timeframe=timeframe,
        ts_utc=last_ts,
        last_close=last_close,
        expected_return=expected_return,
        expected_price=expected_price,
        p_up=p_up,
        interval_low=interval_low,
        interval_high=interval_high,
        model_version=artifact["model_version"],
        model_timestamp_utc=model_timestamp_utc,
    )

    # Persist prediction snapshot for dashboard/API.
    upsert_prediction(
        db_path,
        symbol=symbol,
        timeframe=timeframe,
        horizon=horizon,
        base_ts_utc=out.ts_utc,
        created_ts_utc=created_ts,
        last_close=out.last_close,
        expected_return=out.expected_return,
        expected_price=out.expected_price,
        p_up=out.p_up,
        interval_low=out.interval_low,
        interval_high=out.interval_high,
        model_version=out.model_version,
        model_timestamp_utc=out.model_timestamp_utc,
    )

    return out


def get_latest_prediction_or_none(
    *,
    symbol: str,
    timeframe: Timeframe,
    horizon: str,
    model_version: str = "mvp_v1",
) -> Optional[PredictionOut]:
    settings = load_settings()
    from backend.app.services.storage import fetch_latest_prediction

    row = fetch_latest_prediction(settings.data_db_path, symbol=symbol, timeframe=timeframe, horizon=horizon)
    if row is None:
        return None

    return PredictionOut(
        symbol=row.symbol,
        horizon=row.horizon,
        timeframe=row.timeframe,
        ts_utc=row.base_ts_utc,
        last_close=row.last_close,
        expected_return=row.expected_return,
        expected_price=row.expected_price,
        p_up=row.p_up,
        interval_low=row.interval_low,
        interval_high=row.interval_high,
        model_version=row.model_version,
        model_timestamp_utc=row.model_timestamp_utc,
    )

