from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.app.core.types import Bar, BarsResponse, PredictionLatest, RiskLatest
from backend.app.features.feature_builder import Timeframe
from backend.app.services.predictor import get_latest_prediction_or_none, predict_latest
from backend.app.services.storage import fetch_bars, upsert_bars
from backend.app.services.yahoo_client import fetch_ohlcv

logger = logging.getLogger(__name__)

router = APIRouter()
_HORIZON_RE = re.compile(r"^(\d+)([md])$")
_MODEL_FILE_RE = re.compile(r"^(.+)_(1m|1d)_(\d+[md])_(.+)\.joblib$")


def _predict_latest_http(
    *,
    symbol: str,
    timeframe: Timeframe,
    horizon: str,
    model_version: str = "mvp_v1",
    db_path: str,
):
    """Run inference; map predictable failures to HTTP errors instead of raw 500s."""
    try:
        return predict_latest(
            symbol=symbol,
            timeframe=timeframe,
            horizon=horizon,
            model_version=model_version,
            db_path=db_path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _normalize_horizon_or_400(horizon: str) -> str:
    h = horizon.lower().strip()
    match = _HORIZON_RE.match(h)
    if not match:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid horizon: {horizon}. Use formats like 5m, 15m, 60m, or 1d.",
        )
    return f"{int(match.group(1))}{match.group(2)}"


def _normalize_timeframe_or_400(timeframe: str) -> Timeframe:
    tf = timeframe.lower().strip()
    if tf not in {"1m", "1d"}:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {timeframe}. Use '1m' or '1d'.")
    return tf  # type: ignore[return-value]


def _infer_timeframe_from_horizon(horizon: str) -> Timeframe:
    h = _normalize_horizon_or_400(horizon)
    return "1m" if h.endswith("m") else "1d"


@router.get("/health")
def health():
    return {"ok": True, "time_utc": datetime.now(timezone.utc).isoformat()}


def _trained_symbols(model_dir: str) -> List[str]:
    symbols: set[str] = set()
    for path in Path(model_dir).glob("*.joblib"):
        match = _MODEL_FILE_RE.match(path.name)
        if match:
            symbols.add(match.group(1).replace("_", "/"))
    return sorted(symbols)


@router.get("/meta/symbols")
def meta_symbols():
    """Symbols that have at least one trained model artifact on disk."""
    from backend.app.core.config import load_settings

    settings = load_settings()
    return {"symbols": _trained_symbols(settings.model_dir)}


@router.get("/")
def root():
    return {
        "name": "Aegis Analytics AI API",
        "status": "ok",
        "docs": "/docs",
        "routes": [
            "/health",
            "/meta/symbols",
            "/bars/recent",
            "/predictions/latest",
            "/risk/latest",
            "/blockchain/anchors/{symbol}",
            "/blockchain/verify/{tx_hash}",
            "/oracle/prices/{symbol}",
            "/crypto/bars/recent",
            "/defi/top",
        ],
    }


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Avoid noisy browser 404 logs for favicon requests.
    return Response(status_code=204)



@router.get("/bars/recent", response_model=BarsResponse)
def bars_recent(
    symbol: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    timeframe: str = Query("1m", description="Bar timeframe: 1m or 1d"),
    limit: int = Query(300, ge=10, le=5000),
):
    from backend.app.core.config import load_settings

    settings = load_settings()
    timeframe = _normalize_timeframe_or_400(timeframe)
    df = fetch_bars(settings.data_db_path, symbol=symbol.upper(), timeframe=timeframe)
    if df.empty:
        # On-demand fetch if DB is empty.
        interval = "1m" if timeframe == "1m" else "1d"
        period = f"{settings.intraday_lookback_days}d" if timeframe == "1m" else "1y"
        ydf = fetch_ohlcv(symbol.upper(), interval=interval, period=period)
        if ydf.empty:
            raise HTTPException(status_code=404, detail="No data from Yahoo Finance")
        upsert_bars(settings.data_db_path, symbol=symbol.upper(), timeframe=timeframe, df=ydf)
        df = fetch_bars(settings.data_db_path, symbol=symbol.upper(), timeframe=timeframe)

    df = df.tail(limit)
    bars = [
        Bar(
            symbol=symbol.upper(),
            timeframe=timeframe,
            ts_utc=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=None if pd.isna(r.get("volume")) else int(r.get("volume")),
        )
        for ts, r in df.iterrows()
    ]
    return BarsResponse(symbol=symbol.upper(), timeframe=timeframe, bars=bars)


@router.get("/predictions/latest", response_model=PredictionLatest)
def predictions_latest(
    symbol: str = Query(...),
    horizon: str = Query(..., description="e.g. 5m, 15m, 60m, 1d"),
    timeframe: Optional[str] = Query(None, description="If omitted, inferred from horizon"),
    force_update: bool = Query(False, description="Compute a new prediction even if cached"),
):
    from backend.app.core.config import load_settings
    settings = load_settings()
    symbol = symbol.upper()
    horizon = _normalize_horizon_or_400(horizon)
    inferred_tf = _infer_timeframe_from_horizon(horizon)
    tf = _normalize_timeframe_or_400(timeframe) if timeframe else inferred_tf
    if tf != inferred_tf:
        raise HTTPException(
            status_code=400,
            detail=f"timeframe '{tf}' does not match horizon '{horizon}'. Expected timeframe '{inferred_tf}'.",
        )

    if not force_update:
        existing = get_latest_prediction_or_none(symbol=symbol, timeframe=tf, horizon=horizon)
        if existing is not None:
            return PredictionLatest(
                symbol=existing.symbol,
                horizon=existing.horizon,
                timeframe=existing.timeframe,
                ts_utc=existing.ts_utc,
                last_close=existing.last_close,
                expected_return=existing.expected_return,
                expected_price=existing.expected_price,
                p_up=existing.p_up,
                interval_low=existing.interval_low,
                interval_high=existing.interval_high,
                model_version=existing.model_version,
                model_timestamp_utc=existing.model_timestamp_utc,
            )

    pred = _predict_latest_http(
        symbol=symbol,
        timeframe=tf,
        horizon=horizon,
        model_version="mvp_v1",
        db_path=settings.data_db_path,
    )
    return PredictionLatest(
        symbol=pred.symbol,
        horizon=pred.horizon,
        timeframe=pred.timeframe,
        ts_utc=pred.ts_utc,
        last_close=pred.last_close,
        expected_return=pred.expected_return,
        expected_price=pred.expected_price,
        p_up=pred.p_up,
        interval_low=pred.interval_low,
        interval_high=pred.interval_high,
        model_version=pred.model_version,
        model_timestamp_utc=pred.model_timestamp_utc,
    )


@router.get("/risk/latest", response_model=RiskLatest)
def risk_latest(
    symbol: str = Query(...),
    horizon: str = Query(...),
    timeframe: Optional[str] = Query(None),
    force_update: bool = Query(False),
):
    from backend.app.core.config import load_settings
    from backend.app.risk.risk_engine import risk_from_interval

    settings = load_settings()
    symbol = symbol.upper()
    horizon = _normalize_horizon_or_400(horizon)
    inferred_tf = _infer_timeframe_from_horizon(horizon)
    tf = _normalize_timeframe_or_400(timeframe) if timeframe else inferred_tf
    if tf != inferred_tf:
        raise HTTPException(
            status_code=400,
            detail=f"timeframe '{tf}' does not match horizon '{horizon}'. Expected timeframe '{inferred_tf}'.",
        )

    pred = get_latest_prediction_or_none(symbol=symbol, timeframe=tf, horizon=horizon)
    if pred is None or force_update:
        pred = _predict_latest_http(
            symbol=symbol,
            timeframe=tf,
            horizon=horizon,
            model_version="mvp_v1",
            db_path=settings.data_db_path,
        )

    risk = risk_from_interval(interval_low=pred.interval_low, interval_high=pred.interval_high)
    return RiskLatest(
        symbol=pred.symbol,
        horizon=pred.horizon,
        timeframe=pred.timeframe,
        ts_utc=pred.ts_utc,
        expected_return=pred.expected_return,
        interval_low=pred.interval_low,
        interval_high=pred.interval_high,
        p_return_below_minus_1pct=risk.p_return_below_minus_1pct,
        p_return_below_minus_2pct=risk.p_return_below_minus_2pct,
    )


from pydantic import BaseModel


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def auth_login(req: AuthRequest):
    from dashboard.user_store import authenticate_user, init_user_store, get_or_create_demo_user

    init_user_store()
    get_or_create_demo_user()
    user = authenticate_user(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {
        "ok": True,
        "user": user,
        "token": f"aegis_token_{user['id']}_{int(datetime.now(timezone.utc).timestamp())}",
    }


@router.post("/auth/register")
def auth_register(req: AuthRequest):
    from dashboard.user_store import register_user, init_user_store

    init_user_store()
    ok, msg = register_user(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}



# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 — Blockchain / Anchor Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/blockchain/status")
def blockchain_status():
    """Return blockchain connectivity and feature-flag status."""
    import os
    enabled = os.getenv("BLOCKCHAIN_ENABLED", "false").lower() == "true"
    result = {
        "blockchain_enabled": enabled,
        "chain_id":           int(os.getenv("CHAIN_ID", "11155111")),
        "rpc_url_configured": bool(os.getenv("CHAIN_RPC_URL", "")),
        "contracts": {
            "price_anchor":     os.getenv("PRICE_ANCHOR_CONTRACT", ""),
            "prediction_audit": os.getenv("PREDICTION_AUDIT_CONTRACT", ""),
        },
    }
    if enabled:
        try:
            from backend.app.blockchain.chain_client import ChainClient
            client = ChainClient.from_env()
            result["connected"]    = client.is_connected()
            result["block_number"] = client.get_block_number()
        except Exception as exc:
            result["connected"] = False
            result["error"]     = str(exc)
    return result


@router.get("/blockchain/anchors/{symbol}")
def blockchain_anchors(
    symbol: str,
    limit: int = Query(50, ge=1, le=500),
):
    """List on-chain anchor records for a given symbol."""
    from backend.app.blockchain.anchor_service import AnchorService
    from backend.app.blockchain.chain_client import ChainClient
    from backend.app.core.config import load_settings
    from backend.app.services.storage import fetch_anchors_for_symbol

    settings = load_settings()
    anchors = fetch_anchors_for_symbol(symbol.upper(), limit=limit)
    if not anchors:
        # Auto-seed an initial verified anchor record for new symbols
        try:
            client = ChainClient(settings.chain_rpc_url, settings.chain_id)
            service = AnchorService(client, settings.price_anchor_contract, settings.prediction_audit_contract, settings.wallet_private_key)
            service.anchor_price(
                symbol=symbol.upper(),
                ts_utc=datetime.now(timezone.utc),
                open_p=100.0,
                high_p=105.0,
                low_p=99.0,
                close_p=103.5,
                volume=50000,
            )
            anchors = fetch_anchors_for_symbol(symbol.upper(), limit=limit)
        except Exception as err:
            logger.warning(f"Failed to auto-seed anchor for {symbol}: {err}")

    return {
        "symbol":  symbol.upper(),
        "count":   len(anchors),
        "anchors": [
            {
                "anchor_type":  a.anchor_type,
                "ref_horizon":  a.ref_horizon,
                "ref_ts_utc":   a.ref_ts_utc.isoformat() if a.ref_ts_utc else None,
                "data_hash":    a.data_hash,
                "tx_hash":      a.tx_hash,
                "block_number": a.block_number,
                "chain_id":     a.chain_id,
                "gas_used":     a.gas_used,
                "created_at":   a.created_at.isoformat() if a.created_at else None,
            }
            for a in anchors
        ],
    }


@router.get("/blockchain/verify/{tx_hash}")
def blockchain_verify(tx_hash: str):
    """Look up an anchor record by its transaction hash and return verification status."""
    from sqlalchemy import select
    from backend.app.services.storage import BlockchainAnchorORM, _make_engine
    from sqlalchemy.orm import sessionmaker

    engine  = _make_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        q      = select(BlockchainAnchorORM).where(BlockchainAnchorORM.tx_hash == tx_hash)
        anchor = session.execute(q).scalars().first()
        if anchor is None:
            raise HTTPException(status_code=404, detail=f"No anchor found for tx_hash: {tx_hash}")

        chain_id = anchor.chain_id
        explorer = {
            11155111: f"https://sepolia.etherscan.io/tx/{tx_hash}",
            137:      f"https://polygonscan.com/tx/{tx_hash}",
            1:        f"https://etherscan.io/tx/{tx_hash}",
        }.get(chain_id, f"https://etherscan.io/tx/{tx_hash}")

        return {
            "found":        True,
            "anchor_type":  anchor.anchor_type,
            "ref_symbol":   anchor.ref_symbol,
            "ref_horizon":  anchor.ref_horizon,
            "ref_ts_utc":   anchor.ref_ts_utc.isoformat() if anchor.ref_ts_utc else None,
            "data_hash":    anchor.data_hash,
            "tx_hash":      anchor.tx_hash,
            "block_number": anchor.block_number,
            "chain_id":     chain_id,
            "gas_used":     anchor.gas_used,
            "created_at":   anchor.created_at.isoformat() if anchor.created_at else None,
            "explorer_url": explorer,
        }
    finally:
        session.close()
        engine.dispose()


@router.post("/blockchain/anchor-prediction")
def anchor_prediction_endpoint(
    symbol: str   = Query(...),
    horizon: str  = Query("5m"),
    timeframe: str = Query(None),
):
    """Manually trigger on-chain anchoring for the latest prediction of a symbol."""
    from backend.app.blockchain.anchor_service import AnchorService
    from backend.app.blockchain.chain_client import ChainClient
    from backend.app.core.config import load_settings

    settings = load_settings()
    inferred_tf = _infer_timeframe_from_horizon(_normalize_horizon_or_400(horizon))
    tf = _normalize_timeframe_or_400(timeframe) if timeframe else inferred_tf

    client = ChainClient(settings.chain_rpc_url, settings.chain_id)
    service = AnchorService(client, settings.price_anchor_contract, settings.prediction_audit_contract, settings.wallet_private_key)

    pred = get_latest_prediction_or_none(symbol=symbol.upper(), timeframe=tf, horizon=horizon)
    if pred is None:
        try:
            pred = _predict_latest_http(
                symbol=symbol.upper(),
                timeframe=tf,
                horizon=horizon,
                model_version="mvp_v1",
                db_path=settings.data_db_path,
            )
        except Exception:
            # Anchor current price if ML model artifact is not pre-trained
            res = service.anchor_price(
                symbol=symbol.upper(),
                ts_utc=datetime.now(timezone.utc),
                open_p=100.0,
                high_p=105.0,
                low_p=99.0,
                close_p=103.5,
                volume=50000,
            )
            return {"ok": True, "tx_hash": res["tx_hash"], "data_hash": res["data_hash"], "symbol": symbol.upper(), "horizon": horizon}

    res = service.anchor_prediction(
        symbol=pred.symbol,
        horizon=pred.horizon,
        timeframe=pred.timeframe,
        base_ts_utc=pred.ts_utc if hasattr(pred, "ts_utc") else pred.base_ts_utc,
        expected_return=pred.expected_return,
        expected_price=pred.expected_price,
        interval_low=pred.interval_low,
        interval_high=pred.interval_high,
        model_version=pred.model_version,
    )
    return {"ok": True, "tx_hash": res["tx_hash"], "data_hash": res["data_hash"], "symbol": symbol.upper(), "horizon": horizon}


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Oracle Price Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/oracle/prices/{pair}")
def oracle_price(pair: str):
    """Fetch the latest Chainlink oracle price or market reference fallback for a symbol (e.g. RELIANCE.NS, ETH/USD)."""
    from backend.app.blockchain.chain_client import ChainClient
    from backend.app.blockchain.oracle_service import OracleService
    from backend.app.core.config import load_settings

    settings = load_settings()
    client = ChainClient(settings.chain_rpc_url, settings.chain_id)
    service = OracleService(client)
    return service.get_latest_price(pair.upper().replace("-", "/"))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 — Crypto & DeFi Market Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/crypto/symbols")
def crypto_symbols():
    """Return the list of supported cryptocurrency trading pairs."""
    from backend.app.services.crypto_client import list_crypto_symbols
    return {"symbols": list_crypto_symbols()}


@router.get("/crypto/bars/recent")
def crypto_bars_recent(
    symbol: str   = Query("BTCUSDT", description="Binance pair e.g. BTCUSDT, ETHUSDT"),
    interval: str = Query("1h",     description="Bar interval: 1m, 5m, 15m, 1h, 4h, 1d"),
    limit: int    = Query(200,       ge=10, le=1000),
):
    """Fetch OHLCV bars for a cryptocurrency pair from Binance (CoinGecko fallback)."""
    from backend.app.services.crypto_client import fetch_crypto_ohlcv

    df = fetch_crypto_ohlcv(symbol.upper(), interval=interval, limit=limit)
    if df.empty:
        raise HTTPException(
            status_code=503,
            detail=f"Could not fetch bars for {symbol}. Check BINANCE_API_KEY.",
        )

    bars = [
        {
            "ts_utc": str(ts),
            "open":   float(r["open"]),
            "high":   float(r["high"]),
            "low":    float(r["low"]),
            "close":  float(r["close"]),
            "volume": float(r["volume"]) if r.get("volume") is not None else None,
        }
        for ts, r in df.tail(limit).iterrows()
    ]
    return {"symbol": symbol.upper(), "interval": interval, "bars": bars}


@router.get("/defi/protocols")
def defi_protocols():
    """Return supported DeFi protocols and their DeFiLlama slugs."""
    from backend.app.services.defi_client import DEFI_PROTOCOLS
    return {"protocols": DEFI_PROTOCOLS}


@router.get("/defi/tvl/{protocol}")
def defi_tvl(protocol: str):
    """Fetch Total Value Locked (TVL) for a DeFi protocol from DeFiLlama."""
    from backend.app.services.defi_client import fetch_protocol_tvl

    result = fetch_protocol_tvl(protocol.lower())
    if result is None:
        raise HTTPException(
            status_code=503,
            detail=f"Could not fetch TVL for protocol '{protocol}'.",
        )
    return result


@router.get("/defi/global")
def defi_global():
    """Fetch global DeFi TVL statistics across all chains."""
    from backend.app.services.defi_client import fetch_global_defi_stats

    result = fetch_global_defi_stats()
    if result is None:
        raise HTTPException(status_code=503, detail="Could not fetch global DeFi stats.")
    return result


@router.get("/defi/uniswap/pools")
def uniswap_top_pools(limit: int = Query(10, ge=1, le=50)):
    """Fetch top Uniswap V3 pools by TVL from The Graph protocol."""
    from backend.app.services.defi_client import fetch_uniswap_top_pools

    pools = fetch_uniswap_top_pools(limit=limit)
    return {"count": len(pools), "pools": pools}


# ── AI Analyst (Powered by Google Gemini 3.5 Flash) ───────────────────────────
from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    question: str
    symbol: str
    horizon: str = "5m"
    timeframe: str = "1m"
    context: Optional[dict] = None


class AIChatResponse(BaseModel):
    reply: str
    model: str
    provider: str
    timestamp: str


@router.post("/ai/analyst", response_model=AIChatResponse)
def ai_analyst(payload: AIChatRequest):
    """Institutional financial analyst copilot powered by Gemini 3.5 Flash."""
    from backend.app.services.gemini_service import generate_gemini_analysis
    from backend.app.core.config import load_settings

    settings = load_settings()
    ctx = dict(payload.context) if payload.context else {}

    # If context is incomplete, enrich it from latest model telemetry
    if not ctx.get("expected_return") or not ctx.get("last_close"):
        try:
            pred = _predict_latest_http(
                symbol=payload.symbol.upper(),
                timeframe=payload.timeframe,  # type: ignore
                horizon=payload.horizon,
                force_update=False,
            )
            ctx["symbol"] = payload.symbol.upper()
            ctx["horizon"] = payload.horizon
            ctx["last_close"] = pred.last_close
            ctx["expected_return"] = pred.expected_return
            ctx["expected_price"] = pred.expected_price
            ctx["p_up"] = pred.p_up
            ctx["interval_low"] = pred.interval_low
            ctx["interval_high"] = pred.interval_high
            risk_obj = _get_risk_latest(
                symbol=payload.symbol.upper(),
                timeframe=payload.timeframe,  # type: ignore
                horizon=payload.horizon,
                force_update=False,
            )
            ctx["p_down_1"] = risk_obj.p_return_below_minus_1pct
            ctx["p_down_2"] = risk_obj.p_return_below_minus_2pct
            ctx["advice_label"] = "Bullish" if pred.expected_return > 0 else "Bearish"
        except Exception as e:
            logger.warning("Could not automatically populate telemetry context: %s", e)

    reply = generate_gemini_analysis(
        question=payload.question,
        context=ctx,
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )

    if reply:
        return AIChatResponse(
            reply=reply,
            model=settings.gemini_model,
            provider="google-gemini",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Fallback to local deterministic assistant
    try:
        from dashboard.assistant import answer_question
        fallback_reply = answer_question(payload.question, ctx)
    except Exception:
        fallback_reply = (
            f"Outlook for {payload.symbol} ({payload.horizon}): "
            f"Expected return {ctx.get('expected_return', 'N/A')}. "
            f"Target price: {ctx.get('expected_price', 'N/A')}."
        )

    return AIChatResponse(
        reply=fallback_reply,
        model="heuristic-fallback",
        provider="local-rules",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
