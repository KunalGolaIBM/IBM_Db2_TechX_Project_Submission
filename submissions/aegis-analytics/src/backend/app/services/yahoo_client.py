from __future__ import annotations

import importlib

import pandas as pd


def _import_yfinance() -> object:
    try:
        return importlib.import_module("yfinance")
    except ModuleNotFoundError:
        return None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance download() MultiIndex columns to flat lowercase names."""
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    flat = []
    for col in df.columns:
        if isinstance(col, tuple):
            found = None
            for item in col:
                s = str(item).lower()
                if s in {"open", "high", "low", "close", "volume", "adj close"}:
                    found = s
                    break
            flat.append(found if found else str(col[0]).lower())
        else:
            flat.append(str(col).lower())
    out = df.copy()
    out.columns = flat
    return out


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = _flatten_columns(df)

    rename = {}
    for c in df.columns:
        key = str(c).lower()
        if key in {"open", "high", "low", "close", "volume"}:
            rename[c] = key
    df = df.rename(columns=rename)

    expected = ["open", "high", "low", "close", "volume"]
    for c in expected:
        if c not in df.columns:
            df[c] = None

    df = df[expected].copy()
    df.index = pd.to_datetime(df.index)
    return df


def fetch_ohlcv(
    symbol: str,
    *,
    interval: str,
    period: str,
    auto_adjust: bool = False,
) -> pd.DataFrame:
    """
    Fetch OHLCV from Yahoo Finance via yfinance.
    Returns a DataFrame indexed by timestamp (may be tz-aware).
    """
    yf = _import_yfinance()
    if yf is None:
        raise RuntimeError("The 'yfinance' package is required to fetch OHLCV data. Install it using 'pip install yfinance'.")

    df = pd.DataFrame()

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period, auto_adjust=auto_adjust)
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        try:
            df = yf.download(
                symbol,
                interval=interval,
                period=period,
                auto_adjust=auto_adjust,
                progress=False,
                threads=False,
            )
        except Exception:
            return pd.DataFrame()

    return _normalize_ohlcv(df)
