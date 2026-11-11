"""CLI behaviour (mocked runtime; no Db2)."""

from locklens import cli
from locklens.services.runtime import ConnectionStatus


class SeqRuntime:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), 0

    def test_connection(self):
        self.calls += 1
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]


def no_sleep(_):
    pass


def test_wait_retries_until_database_is_ready():
    rt = SeqRuntime([ConnectionStatus(False, "x", "unreachable"), ConnectionStatus(False, "x", "database_not_found"),
                     ConnectionStatus(True, "ok")])
    lines = []
    status = cli.wait_for_db2(rt, timeout=1000, interval=1, sleep=no_sleep, out=lines.append)
    assert status.ok and rt.calls == 3 and len(lines) == 2


def test_wait_stops_immediately_on_invalid_credentials():
    rt = SeqRuntime([ConnectionStatus(False, "bad", "invalid_credentials")])
    status = cli.wait_for_db2(rt, timeout=1000, interval=1, sleep=no_sleep, out=lambda _: None)
    assert not status.ok and rt.calls == 1


def test_wait_gives_up_after_timeout():
    ticks = iter(range(0, 1000, 5))
    rt = SeqRuntime([ConnectionStatus(False, "x", "unreachable")])
    status = cli.wait_for_db2(rt, timeout=20, interval=1, sleep=no_sleep,
                              clock=lambda: next(ticks), out=lambda _: None)
    assert not status.ok and 1 < rt.calls < 10


def test_missing_configuration_exits_with_code_2_and_lists_problems(capsys=None):
    import os
    saved = os.environ.pop("DB2_PASSWORD", None)
    cwd = os.getcwd()
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))     # no .env here
        assert cli.main(["test-connection"]) == 2
    finally:
        os.chdir(cwd)
        if saved is not None:
            os.environ["DB2_PASSWORD"] = saved
