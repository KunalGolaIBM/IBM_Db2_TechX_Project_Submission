from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Search for .env in aegis root, parent dirs, or user home
for candidate in [
    Path.cwd() / ".env",
    Path(__file__).resolve().parents[3] / ".env",
    Path.home() / ".env",
]:
    if candidate.is_file():
        load_dotenv(candidate, override=False)


def _split_symbols(value: str) -> List[str]:
    return [s.strip().upper() for s in value.split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    # ── Core ML / Data settings ───────────────────────────────────────────────
    symbols: List[str]
    data_db_path: str          # Legacy SQLite path (kept for dev/fallback)
    model_dir: str

    intraday_interval: str
    intraday_lookback_days: int
    intraday_horizons_minutes: List[int]

    daily_horizon_days: int
    prediction_refresh_minutes: int
    conformal_alpha: float

    # ── Phase 0: PostgreSQL ───────────────────────────────────────────────────
    database_url: str           # PostgreSQL connection string (or SQLite fallback)

    # ── Phase 1: Blockchain ───────────────────────────────────────────────────
    chain_rpc_url: str          # RPC node URL (Infura, Alchemy, or local)
    chain_id: int               # 11155111=Sepolia, 137=Polygon, 1=Mainnet
    wallet_private_key: str     # Signing wallet private key (NEVER commit to git)
    price_anchor_contract: str  # Deployed PriceAnchor.sol address
    prediction_audit_contract: str  # Deployed PredictionAudit.sol address
    blockchain_enabled: bool    # Feature flag — disable for dev without a node

    # ── Phase 3: Crypto & DeFi data ───────────────────────────────────────────
    binance_api_key: str
    binance_api_secret: str
    coingecko_api_key: str
    asset_classes: List[str]    # e.g. ["stocks", "crypto", "defi"]

    # ── Google Gemini AI ──────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"


def load_settings() -> Settings:
    # Determine database URL: prefer DATABASE_URL env var, fall back to SQLite
    _db_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.getenv('DATA_DB_PATH', 'data/app.db')}",
    )
    return Settings(
        # ── Core ML / Data ────────────────────────────────────────────────────
        symbols=_split_symbols(os.getenv("SYMBOLS", "RELIANCE.NS,INFY.NS,TCS.NS")),
        data_db_path=os.getenv("DATA_DB_PATH", "data/app.db"),
        model_dir=os.getenv("MODEL_DIR", "models"),
        intraday_interval=os.getenv("INTRADAY_INTERVAL", "1m"),
        intraday_lookback_days=int(os.getenv("INTRADAY_LOOKBACK_DAYS", "7")),
        intraday_horizons_minutes=[5, 15, 60],
        daily_horizon_days=int(os.getenv("DAILY_HORIZON_DAYS", "1")),
        prediction_refresh_minutes=int(os.getenv("PREDICTION_REFRESH_MINUTES", "5")),
        conformal_alpha=float(os.getenv("CONFORMAL_ALPHA", "0.1")),
        # ── Phase 0: PostgreSQL ───────────────────────────────────────────────
        database_url=_db_url,
        # ── Phase 1: Blockchain ───────────────────────────────────────────────
        chain_rpc_url=os.getenv("CHAIN_RPC_URL", ""),
        chain_id=int(os.getenv("CHAIN_ID", "11155111")),  # Default: Sepolia testnet
        wallet_private_key=os.getenv("WALLET_PRIVATE_KEY", ""),
        price_anchor_contract=os.getenv("PRICE_ANCHOR_CONTRACT", ""),
        prediction_audit_contract=os.getenv("PREDICTION_AUDIT_CONTRACT", ""),
        blockchain_enabled=os.getenv("BLOCKCHAIN_ENABLED", "false").lower() == "true",
        # ── Phase 3: Crypto & DeFi ────────────────────────────────────────────
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        coingecko_api_key=os.getenv("COINGECKO_API_KEY", ""),
        asset_classes=_split_symbols(os.getenv("ASSET_CLASSES", "stocks")),
        # ── Google Gemini AI ──────────────────────────────────────────────────
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    )
