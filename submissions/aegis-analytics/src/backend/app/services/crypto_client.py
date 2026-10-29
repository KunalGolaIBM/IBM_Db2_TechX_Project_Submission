"""
crypto_client.py — Binance & CoinGecko OHLCV data fetcher for Aegis Analytics AI.

Fetches cryptocurrency OHLCV price bars from Binance REST API (public klines endpoint)
with graceful fallback to CoinGecko REST API.
Does not require third-party SDK dependencies (uses standard requests).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
COINGECKO_COINS_URL = "https://api.coingecko.com/api/v3/coins"

BINANCE_INTERVAL_MAP = {
    "1m":  "1m",
    "3m":  "3m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1h",
    "2h":  "2h",
    "4h":  "4h",
    "1d":  "1d",
    "1w":  "1w",
}

CRYPTO_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "ADAUSDT", "XRPUSDT", "DOGEUSDT", "MATICUSDT",
    "LINKUSDT", "UNIUSDT", "AVAXUSDT",
]


def fetch_crypto_ohlcv(
    symbol: str = "BTCUSDT",
    *,
    interval: str = "1m",
    limit: int = 300,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Fetch OHLCV candlestick data directly from Binance public REST API.
    Does not require API keys or third-party wrappers.
    """
    clean_sym = symbol.upper().replace("/", "").replace("-", "").strip()
    if not clean_sym.endswith("USDT") and not clean_sym.endswith("BTC") and not clean_sym.endswith("USD"):
        clean_sym += "USDT"

    b_interval = BINANCE_INTERVAL_MAP.get(interval, "1m")
    params = {
        "symbol": clean_sym,
        "interval": b_interval,
        "limit": min(limit, 1000),
    }
    if start_time:
        params["startTime"] = int(start_time.timestamp() * 1000)
    if end_time:
        params["endTime"] = int(end_time.timestamp() * 1000)

    try:
        resp = requests.get(BINANCE_KLINES_URL, params=params, timeout=10)
        resp.raise_for_status()
        raw_klines = resp.json()

        records = []
        timestamps = []
        for k in raw_klines:
            open_ms = int(k[0])
            ts = datetime.fromtimestamp(open_ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)
            records.append({
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
            timestamps.append(ts)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records, index=pd.to_datetime(timestamps))
        df.index.name = "ts_utc"
        logger.info("Binance REST: fetched %d bars for %s (%s)", len(df), clean_sym, interval)
        return df

    except Exception as exc:
        logger.warning("Binance REST fetch failed for %s: %s — trying CoinGecko.", clean_sym, exc)
        return _fetch_coingecko_ohlcv(clean_sym)


# Alias function for routes/tests
fetch_crypto_ohlcv_binance = fetch_crypto_ohlcv


def _fetch_coingecko_ohlcv(symbol: str, days: int = 30) -> pd.DataFrame:
    """Fallback: fetch daily OHLCV from CoinGecko public REST API."""
    COINGECKO_IDS = {
        "BTCUSDT":   "bitcoin",
        "ETHUSDT":   "ethereum",
        "BNBUSDT":   "binancecoin",
        "SOLUSDT":   "solana",
        "ADAUSDT":   "cardano",
        "XRPUSDT":   "ripple",
        "DOGEUSDT":  "dogecoin",
        "MATICUSDT": "matic-network",
        "LINKUSDT":  "chainlink",
        "UNIUSDT":   "uniswap",
        "AVAXUSDT":  "avalanche-2",
    }

    clean_sym = symbol.upper().replace("/", "").replace("-", "").strip()
    coin_id = COINGECKO_IDS.get(clean_sym, "bitcoin")

    try:
        url = f"{COINGECKO_COINS_URL}/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": str(days)}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        ohlc = resp.json()

        records = []
        timestamps = []
        for row in ohlc:
            ts = datetime.fromtimestamp(row[0] / 1000.0, tz=timezone.utc).replace(tzinfo=None)
            records.append({
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": 0.0,
            })
            timestamps.append(ts)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records, index=pd.to_datetime(timestamps))
        df.index.name = "ts_utc"
        logger.info("CoinGecko REST: fetched %d bars for %s", len(df), clean_sym)
        return df

    except Exception as exc:
        logger.error("CoinGecko REST fetch failed for %s: %s", symbol, exc)
        return pd.DataFrame()


def list_crypto_symbols() -> list[str]:
    """Return the list of supported cryptocurrency trading pairs."""
    return list(CRYPTO_SYMBOLS)
