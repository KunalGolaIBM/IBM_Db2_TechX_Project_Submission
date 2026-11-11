"""The LangChain chain (src/chain.py) that drives the question box. A fake LLM stands in for Granite, so these run
without a model; the SQL checks and Db2 privileges behind the chain are the real ones."""
import pytest
from langchain_core.language_models import FakeListLLM
from conftest import needs_db2
import ask, chain

Q = "How many suspect days were there at ITO in October 2025?"

def test_prompt_template_matches_the_evaluated_prompt():
    """The 20-question score was measured on ask.prompt(); the chain must send Granite the same text."""
    assert chain.PROMPT.format(question=Q) == ask.prompt(Q)

def test_granite_is_called_through_langchain_ollama():
    from langchain_ollama import OllamaLLM
    m = chain.granite()
    assert isinstance(m.bound, OllamaLLM) and m.bound.temperature == 0 and m.kwargs["system"] == ask.SYSTEM

@pytest.mark.parametrize("raw", ["DELETE FROM AQ.VERDICT", "SELECT * FROM AQ.READING", "SELECT * FROM SYSCAT.TABLES"])
def test_chain_output_still_passes_the_sql_checks(raw):
    out = chain.answer_chain(model=FakeListLLM(responses=[raw])).invoke({"question": Q})
    assert out["refused"] and out["outcome"] == "BLOCKED"

def test_guard_refuses_before_the_chain_runs():
    llm = FakeListLLM(responses=["SELECT 1 FROM AQ.V_DAY"])
    assert ask.ask("Will ITO be severe tomorrow?", model=llm)["refused"] is True

@needs_db2
def test_chain_answers_from_db2_as_the_reader(reader_conn):
    raw = "```sql\nSELECT COUNT(*) AS N FROM AQ.V_DAY WHERE STATUS = 'SUSPECT'\n```"
    out = ask.ask(Q, conn=reader_conn, model=FakeListLLM(responses=[raw]))
    assert out["outcome"] == "ANSWERED" and out["columns"] == ["N"] and out["rows"][0][0] >= 0
