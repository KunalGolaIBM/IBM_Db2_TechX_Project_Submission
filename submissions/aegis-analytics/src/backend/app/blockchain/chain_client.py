"""
chain_client.py — Web3 client wrapper for EVM blockchain networks (Sepolia, Polygon, Ethereum).
Handles RPC connection, block inspection, contract interaction, and signed transactions.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    from web3 import Web3
    try:
        from web3.middleware import ExtraDataToPOAMiddleware as geth_poa_middleware
    except ImportError:
        try:
            from web3.middleware import geth_poa_middleware
        except ImportError:
            geth_poa_middleware = None
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None
    geth_poa_middleware = None

logger = logging.getLogger(__name__)


class ChainClient:
    """Wrapper around Web3 instance with safe connection handling and transaction helpers."""

    def __init__(self, rpc_url: str, chain_id: int = 11155111):
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self._w3: Optional[Any] = None

        if WEB3_AVAILABLE and rpc_url and not rpc_url.startswith("http://localhost:0"):
            try:
                self._w3 = Web3(Web3.HTTPProvider(rpc_url))
                # Inject PoA middleware for Polygon / Sepolia testnets
                if geth_poa_middleware is not None:
                    try:
                        self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    except Exception:
                        pass
            except Exception as err:
                logger.warning(f"ChainClient failed to initialize Web3 provider: {err}")
                self._w3 = None

    @property
    def is_connected(self) -> bool:
        """Return True if Web3 connection to RPC node is active."""
        if not self._w3:
            return False
        try:
            return bool(self._w3.is_connected())
        except Exception:
            return False

    def get_block_number(self) -> int:
        """Fetch current block height on target chain."""
        if not self.is_connected:
            return 0
        return self._w3.eth.block_number

    def get_gas_price(self) -> int:
        """Fetch current gas price in wei."""
        if not self.is_connected:
            return 2_000_000_000  # Default 2 gwei
        return self._w3.eth.gas_price

    def get_balance(self, address: str) -> float:
        """Get ETH/MATIC balance for an address."""
        if not self.is_connected or not self._w3.is_address(address):
            return 0.0
        wei = self._w3.eth.get_balance(self._w3.to_checksum_address(address))
        return float(self._w3.from_wei(wei, "ether"))

    def send_raw_transaction(self, signed_tx_hex: str) -> str:
        """Broadcast a pre-signed raw transaction to the network."""
        if not self.is_connected:
            raise RuntimeError("Cannot send transaction: RPC client is not connected.")
        tx_hash = self._w3.eth.send_raw_transaction(bytes.fromhex(signed_tx_hex.replace("0x", "")))
        return tx_hash.hex()

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Fetch receipt for a transaction hash."""
        if not self.is_connected:
            return None
        try:
            receipt = self._w3.eth.get_transaction_receipt(tx_hash)
            return dict(receipt) if receipt else None
        except Exception as err:
            logger.error(f"Failed to fetch receipt for {tx_hash}: {err}")
            return None
