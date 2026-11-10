"""Unit tests for StockSage LangGraph agent workflow."""

import pytest
from src.agent import (
    agent_app,
    ask_stocksage,
    classify_intent_node,
    fetch_verified_data_node,
    synthesize_explanation_node,
)
from src.database_setup import initialize_database
from src.db_connection import db_manager


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_database(db_manager, force_recreate=True)
    yield


def test_intent_classification():
    """Verify that intent classification routes retail queries accurately."""
    assert classify_intent_node({"question": "Which products are running low?"})["intent"] == "low_stock"
    assert classify_intent_node({"question": "Which items will run out in the next 3 days?"})["intent"] == "stockout_risk"
    assert classify_intent_node({"question": "Which products are at risk of expiry?"})["intent"] == "expiry_risk"
    assert classify_intent_node({"question": "What should I reorder today?"})["intent"] == "reorder_advice"
    assert classify_intent_node({"question": "What sold the most this week?"})["intent"] == "fast_slow_moving"


def test_verified_tool_execution():
    """Verify that the tool node fetches correct data for each intent."""
    state_low = fetch_verified_data_node({"intent": "low_stock", "question": ""})
    assert "alerts" in state_low["verified_data"]

    state_exp = fetch_verified_data_node({"intent": "expiry_risk", "question": ""})
    assert "expiry" in state_exp["verified_data"]

    state_reorder = fetch_verified_data_node({"intent": "reorder_advice", "question": ""})
    assert "reorder" in state_reorder["verified_data"]


def test_agent_graph_execution():
    """Test full LangGraph end-to-end question answering pipeline."""
    response = ask_stocksage("What should I reorder today?")
    assert isinstance(response, str)
    assert len(response) > 20
    assert ("Reorder" in response or "Smart Reorder" in response or "healthy" in response)


def test_agent_expiry_question():
    """Test full agent flow for expiry question."""
    response = ask_stocksage("Which products are approaching expiry?")
    assert isinstance(response, str)
    assert ("Expiry" in response or "Batch" in response or "batch" in response)

