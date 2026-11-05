"""
Text-to-SQL Agent Test Suite - Kisan Mitra (किसान मित्र)
Tests natural language question parsing, SQL generation, and relational data retrieval.
"""

import pytest
from app.agents.sql_agent import get_sql_agent

@pytest.fixture
def sql_agent():
    return get_sql_agent()

def test_mathura_potato_price_hinglish(sql_agent):
    """Q1: Mathura mandi me aaj aloo ka bhav kya hai?"""
    res = sql_agent.run("Mathura mandi me aaj aloo ka bhav kya hai?")
    assert res["error"] is None
    assert "MANDI_PRICES" in res["generated_sql"]
    assert "Mathura" in res["generated_sql"] or "mathura" in res["generated_sql"].lower()
    assert res["row_count"] > 0
    assert any("Potato" in str(r.values()) or "potato" in str(r.values()).lower() for r in res["rows"])

def test_weekly_highest_grain_hindi(sql_agent):
    """Q2: UP me pichhle hafte sabse mehnga kaunsa anaaj tha?"""
    res = sql_agent.run("UP me pichhle hafte sabse mehnga kaunsa anaaj tha?")
    assert res["error"] is None
    assert "MANDI_PRICES" in res["generated_sql"]
    assert "ORDER BY" in res["generated_sql"]
    assert res["row_count"] > 0

def test_agra_mustard_english(sql_agent):
    """Q3: What is the current price of mustard in Agra market?"""
    res = sql_agent.run("What is the current price of mustard in Agra market?")
    assert res["error"] is None
    assert res["row_count"] > 0
    assert any("Mustard" in str(r.values()) for r in res["rows"])

def test_lucknow_wheat_hindi(sql_agent):
    """Q4: लखनऊ मंडी में गेहूं का क्या भाव चल रहा है?"""
    res = sql_agent.run("लखनऊ मंडी में गेहूं का क्या भाव चल रहा है?")
    assert res["error"] is None
    assert res["row_count"] > 0
    assert any("Wheat" in str(r.values()) for r in res["rows"])
