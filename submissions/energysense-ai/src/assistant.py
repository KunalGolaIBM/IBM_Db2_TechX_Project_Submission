"""Optional LangChain tool-calling assistant with read-only data tools."""
from __future__ import annotations

import json
from typing import Any

from .analysis import analyse_window, diagnose, recommend
from .config import get_settings


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def build_assistant(store):
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("Set OPENAI_API_KEY in .env to enable the optional LangChain assistant.")
    try:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("Install the optional LangChain packages from requirements.txt.") from exc

    def get_recent_readings(appliance_id: str) -> str:
        """Read the latest telemetry rows for an appliance from the configured database."""
        if not appliance_id.strip() or len(appliance_id) > 64:
            return "Invalid appliance identifier."
        rows = store.recent_telemetry(appliance_id.strip(), 30)
        return _json(rows[-10:]) if rows else "No stored readings found for this appliance."

    def analyse_appliance(appliance_id: str) -> str:
        """Run the explainable baseline and outlier analysis on the latest stored reading."""
        if not appliance_id.strip() or len(appliance_id) > 64:
            return "Invalid appliance identifier."
        rows = store.recent_telemetry(appliance_id.strip(), 120)
        if not rows:
            return "No stored readings found for this appliance."
        latest = rows[-1]
        report = analyse_window(latest, rows)
        return _json({
            "latest_reading": latest,
            "analysis": report,
            "diagnosis": diagnose(report, latest),
            "recommended_action": recommend(report, latest),
        })

    def retrieve_maintenance_notes(query: str) -> str:
        """Retrieve relevant maintenance guidance from the IBM Db2 vector knowledge base."""
        if not query.strip() or len(query) > 1000:
            return "Please provide a maintenance search phrase up to 1000 characters."
        from .langchain_db2 import search_maintenance_knowledge
        notes = search_maintenance_knowledge(query, k=3)
        return "\n".join(notes) if notes else "No matching maintenance notes were found."

    def get_recent_events(appliance_id: str) -> str:
        """Read the latest saved anomaly events for an appliance."""
        if not appliance_id.strip() or len(appliance_id) > 64:
            return "Invalid appliance identifier."
        return _json(store.list_events(appliance_id=appliance_id.strip(), limit=10))

    model = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
    return create_agent(
        model=model,
        tools=[get_recent_readings, analyse_appliance, retrieve_maintenance_notes, get_recent_events],
        system_prompt=(
            "You are EnergySense AI's equipment-monitoring assistant. Use the database tools "
            "before answering questions about an appliance. Quote measured values with units and "
            "identify their source (synthetic, Wokwi simulation or ESP32). Explain baseline and "
            "anomaly outputs, and use Db2 maintenance notes when available. Distinguish evidence "
            "from hypotheses; one reading never proves a component has failed. Never issue relay "
            "commands, bypass protection or claim AI controls the device. The deterministic local "
            "ESP32 protection path is independent of network, Db2 and this assistant. Any action "
            "must be verified by a qualified technician."
        ),
    )


def ask_assistant(store, question: str) -> str:
    if not question or not question.strip() or len(question) > 2000:
        raise ValueError("Question must contain 1 to 2000 non-whitespace characters.")
    agent = build_assistant(store)
    response = agent.invoke({"messages": [{"role": "user", "content": question.strip()}]})
    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        raise RuntimeError("The LangChain agent returned no messages.")
    content = getattr(messages[-1], "content", None)
    if content is None:
        raise RuntimeError("The LangChain agent returned an empty final response.")
    return content if isinstance(content, str) else _json(content)
