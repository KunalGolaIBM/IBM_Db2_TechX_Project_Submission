"""
GitMind — GitHub Agent

Provides human intent context from GitHub: PRs, issues, reviews,
comments, and discussions. Traces the chain from commit → PR → issue
to understand why changes were made.

Responsible for: GitHub API queries
Tasks: PR context, issue tracking, review summaries, intent tracing
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.func import entrypoint, task

from config import get_llm, has_github_token
from tools.git_tools import HISTORY_TOOLS

_PROMPT_PATH = Path(__file__).parent / "sys_prompt.yaml"

with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _sys_prompt_data = yaml.safe_load(f)

SYSTEM_PROMPT = _sys_prompt_data.get("SYSTEM_PROMPT", "You are a GitHub context agent.")


def _get_tools():
    """Get tools, including GitHub tools only if token is available."""
    all_tools = list(HISTORY_TOOLS)

    if has_github_token():
        from github_integration.github_tools import GITHUB_TOOLS
        all_tools.extend(GITHUB_TOOLS)

    return all_tools


@task
def call_llm(messages: list[BaseMessage], model_with_tools: Any):
    return model_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)] + messages
    )


@task
def call_tool(tool_call: dict, tools_by_name: dict):
    tool_fn = tools_by_name.get(tool_call["name"])
    if not tool_fn:
        return f"Unknown tool: {tool_call['name']}"
    return tool_fn.invoke(tool_call)


@entrypoint()
def github_agent(messages: list[BaseMessage]) -> str:
    """
    Main entrypoint for the GitHub Agent.

    Queries GitHub for PRs, issues, reviews, and discussions to
    provide human intent context for code changes.
    """
    tools = _get_tools()
    tools_by_name = {t.name: t for t in tools}

    model = get_llm(temperature=0)
    model_with_tools = model.bind_tools(tools)

    response = call_llm(messages, model_with_tools).result()

    iterations = 0
    max_iterations = 5
    while response.tool_calls and iterations < max_iterations:
        iterations += 1
        tool_result_futures = [
            call_tool(tc, tools_by_name) for tc in response.tool_calls
        ]
        tool_results = [f.result() for f in tool_result_futures]

        messages = list(messages) + [response]
        for tc, result in zip(response.tool_calls, tool_results):
            messages.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )

        response = call_llm(messages, model_with_tools).result()
        
    return getattr(response, "text", None) or str(getattr(response, "content", ""))
