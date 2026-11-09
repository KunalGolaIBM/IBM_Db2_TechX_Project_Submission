"""
GitMind - Project Agent

Develops a high-level understanding of the repository by analyzing its
documentation, metadata, structure, and supporting files.

Responsible for:
- Explaining the project's purpose and the problem it solves
- Identifying the project type (CLI, library, web app, API, etc.)
- Analyzing repository architecture and major components
- Understanding the project structure and organization
- Identifying technologies, frameworks, and build systems
- Explaining the development workflow and setup process
- Summarizing key features and design decisions
- Using repository documentation as the primary source of truth
- Falling back to repository history when documentation is incomplete
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.func import entrypoint, task

from config import get_llm
from tools.git_tools import PROJECT_TOOLS, HISTORY_TOOLS
from embeddings.vector_store import EMBEDDING_TOOLS

_PROMPT_PATH = Path(__file__).parent / "sys_prompt.yaml"

with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _sys_prompt_data = yaml.safe_load(f)

SYSTEM_PROMPT = _sys_prompt_data.get("SYSTEM_PROMPT", "You are a helpful CURRENT REPO/PROJECT agent")

tools = HISTORY_TOOLS + EMBEDDING_TOOLS + PROJECT_TOOLS
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
def project_agent(messages: list[BaseMessage]) -> str:
    """
    Main entry point for the project agent.

    Args:
        messages: List of messages (user query)

    Iterates through tool calls until the LLM produces a final
    text response.

    Returns:
        Final response from the project agent
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