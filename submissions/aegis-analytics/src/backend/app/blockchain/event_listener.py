"""
event_listener.py — Blockchain event listener for Aegis Analytics AI.

Polls for new block events and triggers oracle price refreshes.
Designed to run as a background thread alongside FastAPI.

Usage:
    from backend.app.blockchain.event_listener import start_event_listener
    start_event_listener()   # starts a daemon thread
"""
from __future__ import annotations

import logging
import os
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_listener_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _listener_loop(poll_interval_seconds: int = 30) -> None:
    """
    Background polling loop.
    Every `poll_interval_seconds`, fetches the current block number and
    triggers oracle price refreshes for configured crypto pairs.
    """
    from backend.app.blockchain.chain_client import ChainClient
    from backend.app.blockchain.oracle_service import fetch_all_oracle_prices

    logger.info("Blockchain event listener started (poll every %ds).", poll_interval_seconds)
    last_block = -1

    while not _stop_event.is_set():
        try:
            client       = ChainClient.from_env()
            current_block = client.get_block_number()

            if current_block > last_block:
                logger.debug("New block: %d (prev: %d)", current_block, last_block)
                last_block = current_block

                # Refresh oracle prices on every new block batch
                crypto_pairs = os.getenv("ORACLE_PAIRS", "ETH/USD,BTC/USD").split(",")
                fetch_all_oracle_prices([p.strip() for p in crypto_pairs if p.strip()])

        except Exception as exc:
            logger.warning("Event listener poll error: %s", exc)

        _stop_event.wait(timeout=poll_interval_seconds)

    logger.info("Blockchain event listener stopped.")


def start_event_listener(poll_interval_seconds: int = 30) -> None:
    """
    Start the blockchain event listener as a background daemon thread.
    No-op if BLOCKCHAIN_ENABLED is not true.
    """
    global _listener_thread

    if os.getenv("BLOCKCHAIN_ENABLED", "false").lower() != "true":
        logger.info("BLOCKCHAIN_ENABLED=false — event listener not started.")
        return

    if _listener_thread is not None and _listener_thread.is_alive():
        logger.warning("Event listener is already running.")
        return

    _stop_event.clear()
    _listener_thread = threading.Thread(
        target=_listener_loop,
        args=(poll_interval_seconds,),
        daemon=True,
        name="aegis-blockchain-listener",
    )
    _listener_thread.start()
    logger.info("Blockchain event listener daemon thread started.")


def stop_event_listener() -> None:
    """Signal the event listener thread to stop gracefully."""
    _stop_event.set()
    if _listener_thread is not None:
        _listener_thread.join(timeout=10)
    logger.info("Blockchain event listener stopped.")
