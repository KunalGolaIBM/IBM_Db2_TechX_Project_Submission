"""Chain-head anchors: the ledger's head kept outside Db2, so a rebuilt ledger is caught without receipts.

VERIFY_CHAIN proves that the ledger rows agree with each other. An owner who drops the triggers can rebuild
the whole chain so that it agrees again. A receipt (the row hash the caller kept) catches that for its own
row only. An anchor catches it for every row up to it: after each append, AsOf writes the new chain head
(ledger ID and row hash) to an append-only file outside the database, with an HMAC-SHA256 under
ASOF_ANCHOR_KEY, a key Db2 never holds. Each row hash covers every row before it, so if the ledger still has
the anchored hash at the anchored ID, rows 1 to that ID are what they were when it was anchored.

Each record also carries the previous record's MAC, so removing, editing or reordering records breaks the
log, and nobody without the key can write a valid record. Cutting records off the end of the log cannot be
seen from the log alone: the rows after the last anchor are reported as unanchored, and since every append
is anchored that number should be 0. Keep the log where the database owner cannot write (another host, a
write-once bucket); the default directory, var/anchors, suits a demo on one machine.

    python -m asof.anchor verify            # exit 0 only if every anchor matches the ledger
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import db

if TYPE_CHECKING:
    import ibm_db_dbi

    from .config import Settings

try:  # one writer at a time across processes; the thread lock covers platforms without fcntl
    import fcntl
except ImportError:  # pragma: no cover - not on the platforms AsOf supports
    fcntl = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

FORMAT = 1
SQL_HASHES = "SELECT LEDGER_ID, ROW_HASH FROM ANSWER_LEDGER ORDER BY LEDGER_ID"
_LOCK = threading.Lock()


class AnchorError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnchorStatus:
    status: str                     # OK, NO_ANCHORS, LOG_TAMPERED, MISMATCH, MISSING_ROW, CHAIN_BROKEN
    anchors: int
    covered_through: int | None     # rows 1..this ID are anchored and match
    unanchored_rows: int            # rows after the last anchor
    first_bad_anchor: int | None    # 1-based record number in the log
    detail: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "anchors": self.anchors, "covered_through": self.covered_through,
                "unanchored_rows": self.unanchored_rows, "first_bad_anchor": self.first_bad_anchor, "detail": self.detail}


class AnchorLog:
    """The anchor log of one schema's ledger: one JSON record per line, appended under a file lock."""

    def __init__(self, directory: Path, key: bytes, schema: str = db.SCHEMA):
        db.validate_schema(schema)
        if len(key) < 32:
            raise AnchorError("the anchor key must be at least 32 bytes")
        self.directory, self.schema, self._key = Path(directory), schema, key
        self.path = self.directory / f"anchors-{schema}.jsonl"

    @classmethod
    def from_settings(cls, settings: Settings, schema: str = db.SCHEMA) -> AnchorLog | None:
        """None when no ASOF_ANCHOR_KEY is set: anchoring is then off, and /healthz says so."""
        key = settings.anchor_key
        return cls(settings.anchor_dir, key, schema) if key else None

    def _mac(self, record: dict[str, Any]) -> str:
        body = json.dumps({k: v for k, v in record.items() if k != "mac"}, sort_keys=True, separators=(",", ":"))
        return hmac.new(self._key, body.encode("utf-8"), hashlib.sha256).hexdigest()

    def records(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"_unreadable": n})
        return out

    def append(self, ledger_id: int, row_hash: str) -> dict[str, Any] | None:
        """Anchor the head after an append. A head at or below the last anchor is already covered (two
        checks finishing out of order): nothing is written and None is returned."""
        if ledger_id < 1 or len(row_hash) != 64:
            raise AnchorError("not a ledger head")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with _LOCK, open(self.path, "a+", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0)
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
            last = json.loads(lines[-1]) if lines else None
            if last and ledger_id <= int(last["ledger_id"]):
                return None
            record = {"v": FORMAT, "schema": self.schema, "ledger_id": int(ledger_id), "row_hash": row_hash.lower(),
                      "anchored_at": datetime.now(UTC).isoformat(timespec="seconds"),
                      "prev_mac": last["mac"] if last else ""}
            record["mac"] = self._mac(record)
            fh.write(json.dumps(record, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(self.path, 0o600)
        return record

    def rotate(self) -> Path | None:
        """After a deliberate ledger reset (setup --reset or --reset-ledger) the old anchors no longer apply:
        keep them, renamed, as the record of the ledger that was thrown away."""
        if not self.path.is_file():
            return None
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archived = self.path.with_name(f"anchors-{self.schema}-reset-{stamp}.jsonl")
        self.path.rename(archived)
        return archived

    def check_log(self) -> tuple[int | None, str | None]:
        """(first bad record number, why) if the log was edited, reordered or forged; (None, None) if not."""
        prev_mac, prev_id = "", 0
        for n, r in enumerate(self.records(), start=1):
            if "_unreadable" in r:
                return n, "unreadable record"
            if r.get("v") != FORMAT or r.get("schema") != self.schema:
                return n, "unknown format or another schema's record"
            if not hmac.compare_digest(str(r.get("mac", "")), self._mac(r)):
                return n, "MAC does not match: the record was edited or written without the key"
            if r.get("prev_mac") != prev_mac:
                return n, "does not follow the previous record: records were removed or reordered"
            if int(r["ledger_id"]) <= prev_id:
                return n, "ledger IDs must increase"
            prev_mac, prev_id = r["mac"], int(r["ledger_id"])
        return None, None


def verify(anchors: AnchorLog, conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA,
           through: int | None = None) -> AnchorStatus:
    """The log itself, then every anchor against the ledger's row hashes, then VERIFY_CHAIN.

    `through` is for a restored backup, a copy of the ledger as of a past moment: anchors written for rows after
    its head are left out (the whole log is still checked for tampering first)."""
    from .ledger import verify_chain

    records = anchors.records()
    db.use_schema(conn, schema)
    hashes = {int(i): h.strip() for i, h in db.query(conn, SQL_HASHES)}
    head = max(hashes, default=0)
    if not records:
        return AnchorStatus("NO_ANCHORS", 0, None, len(hashes), None, "no anchors written yet")
    bad, why = anchors.check_log()
    if bad is not None:
        return AnchorStatus("LOG_TAMPERED", len(records), None, 0, bad, why)
    if through is not None:
        records = [r for r in records if int(r["ledger_id"]) <= through]
        if not records:
            return AnchorStatus("NO_ANCHORS", 0, None, len(hashes), None, f"no anchors up to row {through}")
    for n, r in enumerate(records, start=1):
        stored = hashes.get(int(r["ledger_id"]))
        if stored is None:
            return AnchorStatus("MISSING_ROW", len(records), None, 0, n,
                                f"ledger row {r['ledger_id']} is gone: the ledger was truncated or reset")
        if not hmac.compare_digest(stored, r["row_hash"]):
            return AnchorStatus("MISMATCH", len(records), None, 0, n,
                                f"ledger row {r['ledger_id']} no longer has the anchored hash: the ledger was "
                                "rewritten up to that row")
    last = int(records[-1]["ledger_id"])
    unanchored = sum(1 for i in hashes if i > last)
    chain = verify_chain(conn, schema)
    if chain.status != "OK":
        return AnchorStatus("CHAIN_BROKEN", len(records), last, unanchored, None,
                            f"anchors match, but VERIFY_CHAIN reports {chain.status} at row {chain.first_bad}")
    note = None if unanchored == 0 else (f"rows {last + 1} to {head} were appended without an anchor (an anchor "
                                          "write failed, or the end of the log was cut off)")
    return AnchorStatus("OK", len(records), last, unanchored, None, note)


def main(argv: list[str] | None = None) -> int:
    from .config import get_settings

    p = argparse.ArgumentParser(prog="python -m asof.anchor", description=__doc__.split("\n\n")[0])
    p.add_argument("command", choices=["verify"])
    p.add_argument("--schema", default=db.SCHEMA)
    args = p.parse_args(argv)
    settings = get_settings()
    anchors = AnchorLog.from_settings(settings, args.schema)
    if anchors is None:
        print("Anchoring is off: set ASOF_ANCHOR_KEY in .env (python -m asof.setup generates one).")
        return 2
    with db.connection(settings, "app") as conn:
        s = verify(anchors, conn, args.schema)
    print(json.dumps(s.as_dict(), indent=1))
    return 0 if s.status == "OK" and s.unanchored_rows == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
