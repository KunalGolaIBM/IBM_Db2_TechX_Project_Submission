"""Tests for the fix loop controller and CrewAI adapter."""

import sys
import types

import pytest

from parity.agents.controller import FixLoopController, GatewayRunner
from parity.agents.types import AgentOutput, AgentRole, LoopResult
from parity.engine.result import ComparisonResult, ComparisonStatus


class FakeRunner:
    """Runner that returns preset text per role."""

    def __init__(self, fix_texts):
        self.fix_texts = list(fix_texts)
        self.calls = []

    def run(self, role, user):
        self.calls.append((role, user))
        if role is AgentRole.DIAGNOSTICIAN:
            return AgentOutput(role=role, text="trailing space handling differs")
        text = self.fix_texts.pop(0) if self.fix_texts else "SELECT 1"
        return AgentOutput(role=role, text=text)


def match_result(sql):
    return ComparisonResult(status=ComparisonStatus.MATCH)


def mismatch_result(sql):
    return ComparisonResult(status=ComparisonStatus.MISMATCH, note="still differs")


def test_fix_accepted_on_first_try():
    runner = FakeRunner(["SELECT fixed"])
    controller = FixLoopController(runner, rerun=match_result)
    result = controller.run("SELECT 1", "SELECT 1", "row 0 differs")
    assert result.status == "FIXED"
    assert result.final_sql == "SELECT fixed"
    assert len(result.attempts) == 1
    assert result.needs_human is False


def test_fix_accepted_on_second_try():
    outputs = iter([mismatch_result("x"), match_result("y")])
    runner = FakeRunner(["SELECT a", "SELECT b"])
    controller = FixLoopController(runner, rerun=lambda sql: next(outputs))
    result = controller.run("SELECT 1", "SELECT 1", "diff")
    assert result.status == "FIXED"
    assert result.final_sql == "SELECT b"
    assert len(result.attempts) == 2


def test_loop_escalates_after_max_attempts():
    runner = FakeRunner(["SELECT a", "SELECT b", "SELECT c"])
    controller = FixLoopController(runner, rerun=mismatch_result, max_attempts=3)
    result = controller.run("SELECT 1", "SELECT 1", "diff")
    assert result.status == "NEEDS_HUMAN"
    assert result.needs_human is True
    assert len(result.attempts) == 3
    assert result.hypothesis == "trailing space handling differs"


def test_controller_rejects_bad_attempt_limit():
    with pytest.raises(ValueError):
        FixLoopController(FakeRunner([]), rerun=match_result, max_attempts=0)


def test_gateway_runner_uses_gateway():
    class FakeGateway:
        def complete(self, agent, system, user):
            from parity.gateway.types import GatewayResponse

            return GatewayResponse(text="  SELECT 1  ", provider="p1", model="m")

    output = GatewayRunner(FakeGateway()).run(AgentRole.FIXER, "fix this")
    assert output.text == "SELECT 1"
    assert output.provider == "p1"


def test_crewai_adapter_missing_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "crewai", None)
    from parity.agents.crewai_adapter import build_crewai_agent

    with pytest.raises(ImportError, match="crewai is not installed"):
        build_crewai_agent(AgentRole.FIXER)


def test_crewai_adapter_with_fake_module(monkeypatch):
    fake = types.ModuleType("crewai")

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake.Agent = FakeAgent
    monkeypatch.setitem(sys.modules, "crewai", fake)
    from parity.agents.crewai_adapter import build_crewai_agent

    agent = build_crewai_agent(AgentRole.TRANSLATOR, model="test-model")
    assert agent.kwargs["role"] == "SQL Translator"
    assert agent.kwargs["model"] == "test-model"
    assert agent.kwargs["allow_delegation"] is False


def test_loop_result_defaults():
    result = LoopResult(status="FIXED")
    assert result.attempts == ()
    assert result.needs_human is False
