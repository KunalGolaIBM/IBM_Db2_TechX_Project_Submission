"""
oracle_service.py — Chainlink price feed reader for Aegis Analytics AI.

Reads verified on-chain price data from Chainlink Data Feeds.
Falls back gracefully when blockchain is not enabled.

Chainlink feed registry (Sepolia & Polygon):
  https://docs.chain.link/data-feeds/price-feeds/addresses
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from backend.app.blockchain.chain_client import ChainClient
from backend.app.services.storage import fetch_latest_oracle_price, upsert_oracle_price

logger = logging.getLogger(__name__)


# ── Chainlink AggregatorV3Interface ABI (minimal) ────────────────────────────

AGGREGATOR_ABI = [
    {
        "name": "latestRoundData",
        "type": "function",
        "inputs": [],
        "outputs": [
            {"name": "roundId",         "type": "uint80"},
            {"name": "answer",          "type": "int256"},
            {"name": "startedAt",       "type": "uint256"},
            {"name": "updatedAt",       "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
        "stateMutability": "view",
    },
    {
        "name": "decimals",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
    },
    {
        "name": "description",
        "type": "function",
        "inputs": [],
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
    },
]


# ── Well-known Chainlink Feed Addresses ───────────────────────────────────────
CHAINLINK_FEEDS: Dict[str, Dict[int, str]] = {
    "ETH/USD":  {137: "0xF9680D99D6C9589e2a93a78A04A279e509205945", 11155111: "0x694AA1769357215DE4FAC081bf1f309aDC325306"},
    "BTC/USD":  {137: "0xc907E116054Ad103354f2D350FD2514433D57F6f", 11155111: "0x1b44F3514812d835EB1BDB0acB33d3fA3351Ee43"},
    "MATIC/USD":{137: "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"},
    "LINK/USD": {137: "0xd9FFdb71EbE7496cC440152d43986Aae0AB76665", 11155111: "0xc59E3633BAAC79493d908e63626716e204A45EdF"},
}


def _is_blockchain_enabled() -> bool:
    return os.getenv("BLOCKCHAIN_ENABLED", "false").lower() == "true"


def get_feed_address(pair: str, chain_id: Optional[int] = None) -> Optional[str]:
    """Look up the Chainlink feed address for a trading pair and chain."""
    cid = chain_id or int(os.getenv("CHAIN_ID", "11155111"))
    feeds = CHAINLINK_FEEDS.get(pair.upper(), {})
    return feeds.get(cid)


class OracleService:
    """Service to query on-chain Chainlink feeds and persist price snapshots."""

    def __init__(self, chain_client: ChainClient):
        self.client = chain_client

    def fetch_oracle_price(self, symbol: str, feed_address: Optional[str] = None) -> Optional[Tuple[float, int, datetime]]:
        """
        Query Chainlink aggregator contract for latest price answer.
        Returns tuple of (price_usd, round_id, block_timestamp).
        """
        pair = f"{symbol.upper()}/USD" if not symbol.endswith("/USD") else symbol.upper()
        addr = feed_address or get_feed_address(pair, self.client.chain_id)
        if not addr or not self.client.is_connected:
            return None

        try:
            w3 = self.client._w3
            contract = w3.eth.contract(address=w3.to_checksum_address(addr), abi=AGGREGATOR_ABI)
            decimals = contract.functions.decimals().call()
            round_data = contract.functions.latestRoundData().call()
            round_id, answer, _started_at, updated_at, _answered_in_round = round_data

            price_usd = float(answer) / (10 ** decimals)
            block_ts = datetime.fromtimestamp(updated_at, tz=timezone.utc).replace(tzinfo=None)

            # Persist to database
            upsert_oracle_price(
                symbol=symbol.upper(),
                oracle_addr=addr,
                price_usd=price_usd,
                round_id=round_id,
                block_ts=block_ts,
            )
            return (price_usd, round_id, block_ts)
        except Exception as err:
            logger.error(f"Error fetching Chainlink price for {symbol}: {err}")
            return None

    def get_latest_price(self, symbol: str) -> Dict[str, Any]:
        """Fetch latest price from on-chain oracle or return cached DB price."""
        result = self.fetch_oracle_price(symbol)
        if result:
            price_usd, round_id, block_ts = result
            return {
                "symbol": symbol.upper(),
                "price_usd": price_usd,
                "round_id": round_id,
                "block_ts": block_ts.isoformat(),
                "source": "chainlink_onchain",
            }

        # Fallback to local DB
        db_record = fetch_latest_oracle_price(symbol.upper())
        if db_record:
            return {
                "symbol": db_record.symbol,
                "price_usd": float(db_record.price_usd),
                "round_id": db_record.round_id,
                "block_ts": db_record.block_ts.isoformat(),
                "source": "database_cached",
            }

        # Fallback to latest market bar for stocks / symbols without direct Chainlink feed
        try:
            from backend.app.services.storage import fetch_bars
            from backend.app.services.yahoo_client import fetch_ohlcv
            df = fetch_bars("data/app.db", symbol.upper(), "1m")
            if df.empty:
                df = fetch_ohlcv(symbol.upper(), interval="1d", period="5d")
            if not df.empty:
                last_price = float(df.iloc[-1]["close"])
                last_ts = df.index[-1]
                block_ts = last_ts.to_pydatetime() if hasattr(last_ts, "to_pydatetime") else datetime.now(timezone.utc)
                return {
                    "symbol": symbol.upper(),
                    "price_usd": last_price,
                    "round_id": 100001,
                    "block_ts": block_ts.isoformat(),
                    "source": "market_reference",
                }
        except Exception as err:
            logger.warning(f"Market reference fallback failed for {symbol}: {err}")

        return {
            "symbol": symbol.upper(),
            "price_usd": 0.0,
            "round_id": None,
            "block_ts": datetime.now(timezone.utc).isoformat(),
            "source": "unavailable",
        }


def fetch_chainlink_price(
    pair: str,
    feed_address: Optional[str] = None,
    chain_id: Optional[int] = None,
) -> Optional[dict]:
    """Fetch latest price from a Chainlink price feed."""
    if not _is_blockchain_enabled():
        return None

    try:
        cid = chain_id or int(os.getenv("CHAIN_ID", "11155111"))
        rpc_url = os.getenv("CHAIN_RPC_URL", "")
        client = ChainClient(rpc_url, cid)
        service = OracleService(client)
        return service.get_latest_price(pair)
    except Exception as exc:
        logger.error("Chainlink oracle fetch failed for %s: %s", pair, exc)
        return None


def fetch_all_oracle_prices(pairs: Optional[list[str]] = None) -> dict[str, Optional[dict]]:
    """Fetch current Chainlink prices for a list of trading pairs."""
    default_pairs = ["ETH/USD", "BTC/USD", "MATIC/USD", "LINK/USD"]
    targets = pairs or default_pairs
    return {pair: fetch_chainlink_price(pair) for pair in targets}
