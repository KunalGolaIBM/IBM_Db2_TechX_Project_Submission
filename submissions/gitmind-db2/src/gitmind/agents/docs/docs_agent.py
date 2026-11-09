"""
GitMind — Docs Agent (Context7 MCP Integration)

A helper agent that retrieves up-to-date documentation for git,
GitHub, and related tools. Uses the Context7 MCP server when
available, or falls back to built-in knowledge.

This agent is invoked by other agents when they need accurate,
current documentation for commands or APIs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain.tools import tool
from langgraph.func import entrypoint, task

from config import get_llm

_PROMPT_PATH = Path(__file__).parent / "sys_prompt.yaml"

with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _sys_prompt_data = yaml.safe_load(f)

SYSTEM_PROMPT = _sys_prompt_data.get("SYSTEM_PROMPT", "You are a documentation helper.")


@tool
def get_git_command_help(command: str) -> str:
    """
    Get help/documentation for a git command. Runs 'git <command> --help'
    and returns a summary of the command's usage and options.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", command, "-h"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or result.stderr
        # Truncated for LLM context
        if len(output) > 4000:
            output = output[:4000] + "\n... (truncated)"
        return output
    except Exception as e:
        return f"Error getting help for 'git {command}': {e}"


@tool
def get_git_config_docs(section: str = "") -> str:
    """
    Get documentation about git configuration options.
    If section is provided (e.g., 'core', 'remote', 'branch'),
    returns config entries for that section.
    """
    import subprocess

    try:
        if section:
            result = subprocess.run(
                ["git", "config", "--list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = [
                line for line in result.stdout.splitlines()
                if line.startswith(f"{section}.")
            ]
            return "\n".join(lines) if lines else f"No config entries found for section '{section}'"
        else:
            result = subprocess.run(
                ["git", "config", "--list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout[:4000] if result.stdout else "No git config found."
    except Exception as e:
        return f"Error reading git config: {e}"


@tool
def lookup_git_concept(concept: str) -> str:
    """
    Look up a git concept, workflow, or best practice from the built-in
    knowledge base. Covers: rebasing, cherry-picking, bisecting, worktrees,
    submodules, hooks, LFS, sparse checkout, and more.
    """
    concepts = {
        "rebase": (
            "git rebase replays commits from one branch onto another. "
            "Interactive rebase (git rebase -i) allows reordering, squashing, "
            "editing, or dropping commits. Use 'git rebase --onto' for advanced "
            "rebasing. Always use --force-with-lease when pushing after rebase."
        ),
        "cherry-pick": (
            "git cherry-pick applies the changes from a specific commit onto "
            "the current branch. Useful for applying hotfixes across branches. "
            "Use -x flag to record the source commit hash in the message."
        ),
        "bisect": (
            "git bisect performs a binary search through commit history to find "
            "which commit introduced a bug. Start with 'git bisect start', then "
            "mark commits as 'good' or 'bad'. Git narrows down the culprit commit."
        ),
        "worktree": (
            "git worktree allows checking out multiple branches simultaneously "
            "in separate directories. Useful for reviewing PRs while keeping "
            "your current work untouched. 'git worktree add <path> <branch>'."
        ),
        "submodule": (
            "git submodules embed one repository inside another. "
            "'git submodule update --init --recursive' initializes all submodules. "
            "Use 'git submodule foreach' for batch operations."
        ),
        "hook": (
            "Git hooks are scripts that run at specific points: pre-commit, "
            "post-commit, pre-push, etc. Stored in .git/hooks/. "
            "Use tools like husky or pre-commit framework for team-wide hooks."
        ),
        "lfs": (
            "Git LFS (Large File Storage) stores large files outside the repo. "
            "Track files with 'git lfs track \"*.psd\"'. "
            "Requires the git-lfs extension installed."
        ),
        "stash": (
            "git stash temporarily saves uncommitted changes. "
            "'git stash push -m \"description\"' for named stashes. "
            "'git stash pop' restores the most recent stash. "
            "'git stash apply stash@{N}' for specific stashes."
        ),
        "reflog": (
            "git reflog records all changes to HEAD — commits, rebases, resets, "
            "checkouts. It's your safety net for recovering lost work. "
            "Entries expire after 90 days by default (30 for unreachable)."
        ),
        "force-push": (
            "git push --force overwrites remote history (DANGEROUS). "
            "Prefer --force-with-lease which fails if someone else pushed. "
            "Always fetch before force pushing to check for remote changes."
        ),
        "sparse-checkout": (
            "Sparse checkout allows cloning only specific directories. "
            "'git sparse-checkout init --cone' then "
            "'git sparse-checkout set <dir1> <dir2>'. "
            "Useful for large monorepos."
        ),
    }

    # Find matching concept
    query = concept.lower().replace("-", "").replace("_", "").replace(" ", "")
    for key, value in concepts.items():
        if query in key.replace("-", "").replace("_", ""):
            return value

    return (
        f"No built-in documentation for '{concept}'. "
        "Try get_git_command_help for specific git commands."
    )


tools = [get_git_command_help, get_git_config_docs, lookup_git_concept]
tools_by_name = {t.name: t for t in tools}

DOCS_TOOLS = tools


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
def docs_agent(messages: list[BaseMessage]) -> str:
    """
    Main entrypoint for the Docs Agent.

    Provides accurate documentation for git commands, concepts,
    and workflows. Uses built-in knowledge and git --help.

    NOTE: When Context7 MCP is configured, this agent can be
    extended to query Context7 for up-to-date documentation
    for any library/tool.
    """
    model = get_llm(temperature=0)
    model_with_tools = model.bind_tools(tools)

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

        response = call_llm(messages, model_with_tools).result() # Check this one
        # print(f"The response from the agents/docs/docs_agent.py: {response}")

    return getattr(response, "text", None) or str(getattr(response, "content", ""))
