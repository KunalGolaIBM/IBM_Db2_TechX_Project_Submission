"""
GitMind — History Agent

Investigates the commit history of a repository, reconstructs
the story of how the project evolved, explains specific commits,
traces feature evolution, and generates narratives.

Responsible for: git log, git show, git blame
Tasks: commit explanation, feature evolution, timeline generation,
       repository storytelling
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langgraph.func import entrypoint, task

from config import get_llm
from tools.git_tools import HISTORY_TOOLS
from embeddings.vector_store import EMBEDDING_TOOLS

_PROMPT_PATH = Path(__file__).parent / "sys_prompt.yaml"

with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _sys_prompt_data = yaml.safe_load(f)

SYSTEM_PROMPT = _sys_prompt_data.get("SYSTEM_PROMPT", "You are a helpful Git history agent.")

tools = HISTORY_TOOLS + EMBEDDING_TOOLS
tools_by_name = {t.name: t for t in tools}


def _create_model():
    """Create the LLM with tools bound."""
    model = get_llm(temperature=0)
    return model.bind_tools(tools)


@task
def call_llm(messages: list[BaseMessage], model_with_tools: Any):
    """LLM decides whether to call a tool or respond directly."""
    return model_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)] + messages
    )


@task
def call_tool(tool_call: dict):
    """Execute a tool call."""
    tool_fn = tools_by_name.get(tool_call["name"])
    if not tool_fn:
        return f"Unknown tool: {tool_call['name']}"
    return tool_fn.invoke(tool_call)


@entrypoint()
def history_agent(messages: list[BaseMessage]) -> str:
    """
    Main entrypoint for the History Agent.

    Takes a list of messages (user query), iterates through
    tool calls until the LLM produces a final text response.
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

        from langchain_core.messages import ToolMessage

        messages = list(messages) + [response]
        for tc, result in zip(response.tool_calls, tool_results):
            messages.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )

        response = call_llm(messages, model_with_tools).result()

    return getattr(response, "text", None) or str(getattr(response, "content", ""))