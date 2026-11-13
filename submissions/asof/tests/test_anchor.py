"""Chain-head anchors: an HMAC-chained log outside Db2 that catches a ledger rebuilt without receipts."""

from __future__ import annotations

import json

import pytest

from asof import anchor
from asof.anchor import AnchorError, AnchorLog
from asof.config import Settings
from asof.ledger import ChainStatus

KEY = b"k" * 40
H1, H2, H3 = "1" * 64, "2" * 64, "3" * 64


@pytest.fixture
def log(tmp_path) -> AnchorLog:
    return AnchorLog(tmp_path, KEY, "ASOF_X")


def lines(log: AnchorLog) -> list[dict]:
    return [json.loads(x) for x in log.path.read_text().splitlines()]


def rewrite(log: AnchorLog, records: list[dict]) -> None:
    log.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))


def test_each_record_is_maced_and_chained_to_the_previous(log):
    log.append(1, H1)
    log.append(2, H2)
    a, b = lines(log)
    assert (a["ledger_id"], a["row_hash"], a["prev_mac"]) == (1, H1, "") and b["prev_mac"] == a["mac"]
    assert log.check_log() == (None, None)
    assert oct(log.path.stat().st_mode & 0o777) == "0o600"


def test_a_head_already_covered_is_not_written_again(log):
    log.append(5, H2)
    assert log.append(4, H1) is None and log.append(5, H2) is None  # checks that finished out of order
    assert len(lines(log)) == 1


@pytest.mark.parametrize("tamper, why", [
    (lambda rs: [{**rs[0], "row_hash": H3}, *rs[1:]], "MAC does not match"),          # an edited record
    (lambda rs: [rs[0], rs[2]], "does not follow"),                                     # a record removed
    (lambda rs: [rs[1], rs[0], rs[2]], "does not follow"),                              # reordered
])
def test_any_edit_to_the_log_is_caught(log, tamper, why):
    for i, h in enumerate((H1, H2, H3), start=1):
        log.append(i, h)
    rewrite(log, tamper(lines(log)))
    bad, reason = log.check_log()
    assert bad is not None and why in reason


def test_a_record_written_without_the_key_is_caught(log, tmp_path):
    log.append(1, H1)
    forger = AnchorLog(tmp_path, b"f" * 40, "ASOF_X")  # same file, another key
    forger.append(2, H2)
    assert log.check_log() == (2, "MAC does not match: the record was edited or written without the key")


def test_short_keys_and_bad_heads_are_refused(tmp_path):
    with pytest.raises(AnchorError):
        AnchorLog(tmp_path, b"short", "ASOF")
    with pytest.raises(AnchorError):
        AnchorLog(tmp_path, KEY, "ASOF").append(1, "abc")
    with pytest.raises(ValueError):
        Settings(asof_anchor_key="too-short")


def test_rotation_keeps_the_old_log_aside(log):
    log.append(1, H1)
    archived = log.rotate()
    assert archived.exists() and archived.name.startswith("anchors-ASOF_X-reset-") and not log.path.exists()
    assert log.rotate() is None


@pytest.fixture
def ledger_now(monkeypatch):
    """The ledger's row hashes and VERIFY_CHAIN, as Db2 would answer them."""
    state = {"hashes": {}, "chain": "OK"}
    monkeypatch.setattr(anchor.db, "use_schema", lambda conn, schema: None)
    monkeypatch.setattr(anchor.db, "query", lambda conn, sql, params=(): sorted(state["hashes"].items()))
    monkeypatch.setattr("asof.ledger.verify_chain",
                        lambda conn, schema: ChainStatus(state["chain"], len(state["hashes"]), None, None))
    return state


def test_verify_ok_and_counts_unanchored_rows(log, ledger_now):
    ledger_now["hashes"] = {1: H1, 2: H2, 3: H3}
    assert anchor.verify(log, None, "ASOF_X").status == "NO_ANCHORS"
    log.append(1, H1)
    log.append(2, H2)
    s = anchor.verify(log, None, "ASOF_X")
    assert (s.status, s.covered_through, s.unanchored_rows) == ("OK", 2, 1) and "3 to 3" in s.detail


@pytest.mark.parametrize("hashes, status", [({1: H1, 2: H3}, "MISMATCH"), ({1: H1}, "MISSING_ROW")])
def test_verify_catches_a_rewritten_or_truncated_ledger(log, ledger_now, hashes, status):
    log.append(1, H1)
    log.append(2, H2)
    ledger_now["hashes"] = hashes
    s = anchor.verify(log, None, "ASOF_X")
    assert s.status == status and s.first_bad_anchor == 2


def test_a_restored_backup_is_judged_by_the_anchors_up_to_its_head(log, ledger_now):
    """A backup restored as of row 2 lacks row 3: with through=2 that is expected, and rows 1 to 2 must still
    match their anchors; a tampered log is refused whatever `through` says."""
    for i, h in ((1, H1), (2, H2), (3, H3)):
        log.append(i, h)
    ledger_now["hashes"] = {1: H1, 2: H2}
    assert anchor.verify(log, None, "ASOF_X").status == "MISSING_ROW"
    s = anchor.verify(log, None, "ASOF_X", through=2)
    assert (s.status, s.anchors, s.covered_through, s.unanchored_rows) == ("OK", 2, 2, 0)
    ledger_now["hashes"] = {1: H1, 2: H3}
    assert anchor.verify(log, None, "ASOF_X", through=2).status == "MISMATCH"
    assert anchor.verify(log, None, "ASOF_X", through=0).status == "NO_ANCHORS"
    records = lines(log)
    records[0]["row_hash"] = H3
    rewrite(log, records)
    assert anchor.verify(log, None, "ASOF_X", through=2).status == "LOG_TAMPERED"


def test_verify_reports_a_broken_chain_even_when_anchors_match(log, ledger_now):
    log.append(1, H1)
    ledger_now["hashes"], ledger_now["chain"] = {1: H1}, "BROKEN"
    assert anchor.verify(log, None, "ASOF_X").status == "CHAIN_BROKEN"


def test_every_gate_that_writes_the_real_ledger_anchors_it(tmp_path, monkeypatch):
    """The API, the demo and the LangChain runnable write to schema ASOF, so they anchor; the eval, replay
    recording and benchmark write to scratch schemas that are wiped on every run, so they do not."""
    import inspect

    from asof import demo, integration

    monkeypatch.setenv("ASOF_ANCHOR_KEY_FILE", str(tmp_path / "anchor.key"))
    (tmp_path / "anchor.key").write_text("k" * 43)
    (tmp_path / "anchor.key").chmod(0o600)
    monkeypatch.setattr(integration, "build_llm", lambda settings: None)
    monkeypatch.setattr(integration, "get_embeddings", lambda name: None)
    s = Settings(_env_file=None, asof_app_password="x" * 20, asof_anchor_key_file=str(tmp_path / "anchor.key"))
    gate = integration.build_gate(s)
    assert gate.anchors is not None and gate.anchors.path.name == "anchors-ASOF.jsonl"
    assert "anchors=AnchorLog.from_settings(settings)" in inspect.getsource(demo.main)
