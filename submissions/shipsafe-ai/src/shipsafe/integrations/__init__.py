"""Connect ShipSafe to AI IDEs (IBM Bob, Claude Code, Cursor, VS Code)."""

from .connect import TARGETS, connect, merge_config, server_command

__all__ = ["TARGETS", "connect", "merge_config", "server_command"]
