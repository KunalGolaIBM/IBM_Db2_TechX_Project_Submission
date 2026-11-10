"""Tests for the agent fix loop."""


from parity.agents.loop import FIXED, NEEDS_HUMAN, SKIPPED, build_diff_text, run_fix_loop
from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonResult, ComparisonStatus, DiffKind, ResultSet
from parity.gateway.cache import InMemoryCache
from parity.gateway.client import Gateway
from parity.gateway.types import GatewayResponse, ProviderConfig


def mismatch() -> ComparisonResult:
    return ComparisonResult(
        status=ComparisonStatus.MISMATCH,
        diffs=(
            RowDiffFactory(),
        ),
    )


def RowDiffFactory():
    from parity.engine.result import RowDiff

    return RowDiff(
        kind=DiffKind.VALUE,
        detail="row 0 column country differs",
        source_value=2,
        target_value=3,
    )


def stub_gateway(responses: list[str]) -> Gateway:
    """A gateway that answers with the given texts in order."""
    provider = ProviderConfig(name="stub", base_url="http://localhost", model="stub-model")
    calls = list(responses)

    def transport(prov, system, user):
        text = calls.pop(0) if calls else ""
        return GatewayResponse(text=text, provider="stub", model="stub-model")

    gateway = Gateway(providers=[provider], cache=InMemoryCache(), transport=transport)
    return gateway


def source_executor() -> InMemoryExecutor:
    return InMemoryExecutor(
        {"SELECT id FROM t": ResultSet(columns=("id",), rows=((1,),))}
    )


def target_executor(correct: bool) -> InMemoryExecutor:
    if correct:
        sql = 'SELECT id FROM "T"'
    else:
        sql = "SELECT id FROM wrong"
    return InMemoryExecutor({sql: ResultSet(columns=("id",), rows=((1,),))})


def test_build_diff_text():
    text = build_diff_text(mismatch())
    assert "VALUE" in text
    assert "row 0 column country differs" in text


def test_loop_is_skipped_without_a_gateway():
    outcome = run_fix_loop(
        "SELECT id FROM t",
        "SELECT id FROM t",
        mismatch(),
        source_executor(),
        target_executor(True),
        None,
    )
    assert outcome.status == SKIPPED
    assert "no agent gateway" in outcome.note
    assert not outcome.is_fixed


def test_loop_is_skipped_for_a_matching_query():
    outcome = run_fix_loop(
        "SELECT id FROM t",
        "SELECT id FROM t",
        ComparisonResult(status=ComparisonStatus.MATCH),
        source_executor(),
        target_executor(True),
        stub_gateway(["hyp", "SELECT id FROM t"]),
    )
    assert outcome.status == SKIPPED
    assert "nothing to fix" in outcome.note


def test_a_proved_fix_is_accepted():
    gateway = stub_gateway(
        [
            "the count differs because of blank values",
            'SELECT id FROM "T"',
        ]
    )
    outcome = run_fix_loop(
        "SELECT id FROM t",
        "SELECT id FROM wrong",
        mismatch(),
        source_executor(),
        target_executor(True),
        gateway,
        table="t",
    )
    assert outcome.status == FIXED
    assert outcome.is_fixed
    assert outcome.hypothesis == "the count differs because of blank values"
    assert outcome.attempts == 1
    assert not outcome.needs_human


def test_a_fix_that_still_fails_goes_to_a_human():
    gateway = stub_gateway(
        [
            "the count differs",
            "SELECT id FROM still_wrong",
            "SELECT id FROM still_wrong",
            "SELECT id FROM still_wrong",
        ]
    )
    outcome = run_fix_loop(
        "SELECT id FROM t",
        "SELECT id FROM wrong",
        mismatch(),
        source_executor(),
        target_executor(False),
        gateway,
        table="t",
    )
    assert outcome.status == NEEDS_HUMAN
    assert outcome.needs_human
    assert outcome.attempts == 3


def test_an_agent_failure_keeps_the_mismatch():
    class BrokenRunner:
        pass

    gateway = Gateway(
        providers=[ProviderConfig(name="p", base_url="http://localhost", model="m")],
        cache=InMemoryCache(),
    )

    def broken(prov, system, user):
        raise RuntimeError("model is down")

    gateway._transport = broken
    outcome = run_fix_loop(
        "SELECT id FROM t",
        "SELECT id FROM wrong",
        mismatch(),
        source_executor(),
        target_executor(False),
        gateway,
        table="t",
    )
    assert outcome.status == NEEDS_HUMAN
    assert "model is down" in outcome.note
