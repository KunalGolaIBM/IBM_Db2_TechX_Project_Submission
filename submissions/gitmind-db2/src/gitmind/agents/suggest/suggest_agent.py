"""
GitMind — Suggest Agent

Proactively analyzes the current repository state and provides
actionable suggestions without the user asking a specific question.

Detects: unpushed commits, rebase state, force push risks,
stale branches, merge conflicts, uncommitted changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.func import entrypoint, task

from config import get_llm
from tools.git_tools import SUGGEST_TOOLS


_PROMPT_PATH = Path(__file__).parent / "sys_prompt.yaml"

with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _sys_prompt_data = yaml.safe_load(f)

SYSTEM_PROMPT = _sys_prompt_data.get("SYSTEM_PROMPT", "You are a proactive Git advisor.")

tools = SUGGEST_TOOLS
tools_by_name = {t.name: t for t in tools}


def _create_model():
    model = get_llm(temperature=0)
    return model.bind_tools(tools)


@task
def call_llm(messages: list[BaseMessage], model_with_tools: Any):
    return model_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)] + messages
    )


@task
def call_tool(tool_call: dict):
    tool_fn = tools_by_name.get(tool_call["name"])
    if not tool_fn:
        return f"Unknown tool: {tool_call['name']}"
    return tool_fn.invoke(tool_call)


@entrypoint()
def suggest_agent(messages: list[BaseMessage]) -> str:
    """
    Main entrypoint for the Suggest Agent.

    Proactively analyzes the repo state and generates suggestions.
    """
    model_with_tools = _create_model()
    response = call_llm(messages, model_with_tools).result()

    iterations = 0
    max_iterations = 5
    while response.tool_calls and iterations < max_iterations:
        iterations += 1
        tool_result_futures = [
            call_tool(tc) for tc in response.tool_calls
        ]
        tool_results = [f.result() for f in tool_result_futures]

        messages = list(messages) + [response]
        for tc, result in zip(response.tool_calls, tool_results):
            messages.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )

        response = call_llm(messages, model_with_tools).result()

    return getattr(response, "text", None) or str(getattr(response, "content", ""))
