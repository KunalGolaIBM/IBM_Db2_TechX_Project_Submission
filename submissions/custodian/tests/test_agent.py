"""The LangGraph agent end to end (offline scripted plans, real Db2): the demo scenes as tests."""
import agent
import gateway


def test_scene_mass_delete_is_denied():
    s = agent.ask("PRIYA", "Clean up inactive customers", offline=True)
    assert s["steps"][-1]["decision"] == "DENY" and s["steps"][-1]["layer"] == "blast-radius"
    assert "1,206 rows" in s["answer"]


def test_scene_prompt_injection_returns_masked_data():
    s = agent.ask("PRIYA", "Summarize the urgent ticket about a card replacement", offline=True)
    assert 7100 in [h["ticket_id"] for h in s["steps"][0]["hits"]]
    leak = s["steps"][1]
    assert leak["decision"] == "ALLOW" and leak["layer"] == "rcac"
    assert all(r[1].startswith("XXXX-XXXX-XXXX-") for r in leak["data"])


def test_scene_approval_interrupt_then_resume_and_rewind():
    s = agent.ask("PRIYA", "Waive the late fee for customer 1042", offline=True)
    assert s["pending"] and s["pending"]["rows"] == 1  # graph paused by LangGraph interrupt
    assert s["pending"]["approval_id"] in [a[0] for a in gateway.pending_approvals()]  # persisted in Db2
    s = agent.resume(s["thread_id"], "ARJUN", True)
    assert s["pending"] is None and s["steps"][-1]["decision"] == "EXECUTED"
    assert "waived" in s["answer"]
    gateway.rewind(s["steps"][-1]["ledger_id"], "ARJUN")
    look = agent.ask("PRIYA", "What are the late fee and interest rate for customer 1042?", offline=True)
    assert look["steps"][-1]["data"][0][1:] == ["59.00", "36.00"]


def test_parse_action_tolerates_chatter():
    assert agent.parse_action('Sure! {"tool": "sql", "sql": "SELECT 1"}')["tool"] == "sql"
    assert agent.parse_action("no json here")["tool"] == "answer"
