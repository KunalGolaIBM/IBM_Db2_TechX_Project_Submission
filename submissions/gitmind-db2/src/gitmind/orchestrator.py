"""
GitMind 2.0 — Orchestrator

Main LangGraph multi-agent workflow:
    User Query -> Router -> [Specialist Agents] -> Evidence Verification -> Synthesizer -> Persistent Db2 Finding
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.messages import HumanMessage

import config
from utils.repo_utils import get_repo_id
from workflows.router import AgentType, route_query
from workflows.synthesizer import synthesize

logger = logging.getLogger("gitmind.orchestrator")


# ---------------------------------------------------------------------------
# Agent Invocation Registry
# ---------------------------------------------------------------------------

def _invoke_agent(agent_type: AgentType, query: str) -> str:
    """Invoke a specific specialist agent and return its response."""
    messages = [HumanMessage(content=query)]

    try:
        if agent_type == AgentType.HISTORY:
            from agents.history.history_agent import history_agent
            return history_agent.invoke(messages)

        elif agent_type == AgentType.RECOVERY:
            from agents.recovery.recovery_agent import recovery_agent
            return recovery_agent.invoke(messages)

        elif agent_type == AgentType.CODE:
            from agents.code.code_agent import code_agent
            return code_agent.invoke(messages)

        elif agent_type == AgentType.GITHUB:
            from agents.github.github_agent import github_agent
            return github_agent.invoke(messages)

        elif agent_type == AgentType.SUGGEST:
            from agents.suggest.suggest_agent import suggest_agent
            return suggest_agent.invoke(messages)

        elif agent_type == AgentType.DOCS:
            from agents.docs.docs_agent import docs_agent
            return docs_agent.invoke(messages)

        elif agent_type == AgentType.PROJECT:
            from agents.project.project_agent import project_agent
            return project_agent.invoke(messages)

        else:
            return f"Unknown agent type: {agent_type}"

    except Exception as e:
        logger.error(f"Error from {agent_type.value} agent: {e}")
        return f"Error from {agent_type.value} agent: {e}"


# ---------------------------------------------------------------------------
# Main Orchestration Pipelines
# ---------------------------------------------------------------------------

def run_query(query: str, command: Optional[str] = None, repo_path: str = ".") -> str:
    """
    Main orchestration function.
    Routes query, collects agent findings, executes Db2 evidence verification,
    and returns a synthesized, grounded response.
    """
    repo_id = get_repo_id(repo_path)
    run_id = None

    # Track multi-agent investigation in Db2
    if config.STORAGE_BACKEND == "db2":
        try:
            from data.repository_memory import get_repository_memory
            memory = get_repository_memory()
            run_id = memory.start_agent_run(
                repo_id=repo_id,
                query=query,
                workflow_name=command or "ask",
                agents_invoked=[],
            )
        except Exception:
            pass

    # 1. Routing Decision
    routing = route_query(query, command=command)
    agents_invoked = [routing.primary_agent.value] + [s.value for s in routing.secondary_agents]

    # 2. Invoke Specialist Agents
    agent_outputs: dict[str, str] = {}

    primary_result = _invoke_agent(routing.primary_agent, routing.rewritten_query or query)
    agent_outputs[routing.primary_agent.value] = primary_result

    for secondary in routing.secondary_agents:
        try:
            sec_result = _invoke_agent(secondary, routing.rewritten_query or query)
            agent_outputs[secondary.value] = sec_result
        except Exception as e:
            logger.debug(f"Secondary agent {secondary.value} skipped: {e}")

    # 3. Grounded Synthesis with Db2 Evidence Verification
    final_response = synthesize(agent_outputs, query, repo_path=repo_path)

    # 4. Mark agent run complete in Db2
    if config.STORAGE_BACKEND == "db2" and run_id:
        try:
            memory.complete_agent_run(run_id, status="SUCCESS")
        except Exception:
            pass

    return final_response


def run_review(base_ref: str = "main", repo_path: str = ".") -> str:
    """
    Executes the signature GitMind 2.0 Change-Risk and Regression Review.
    """
    from workflows.review import ChangeRiskAnalyzer
    analyzer = ChangeRiskAnalyzer(repo_path=repo_path)
    result = analyzer.analyze_change_risk(base_ref=base_ref)
    return result.review_markdown


def run_suggest() -> str:
    """Run the suggest agent directly for proactive repo health."""
    return _invoke_agent(
        AgentType.SUGGEST,
        "Analyze the current state of this repository and provide proactive suggestions. "
        "Check for unpushed commits, uncommitted changes, rebase/merge state, "
        "force push risks, stale branches, and any potential issues.",
    )


def run_recover() -> str:
    """Run the recovery agent for reflog and dangling object analysis."""
    return _invoke_agent(
        AgentType.RECOVERY,
        "Analyze the reflog and git fsck output to find any recoverable work. "
        "Look for dangling commits, deleted branches, lost stashes, and recent "
        "destructive operations. Provide a complete recovery plan if anything is found.",
    )


def run_story(days: int = 7, detailed: bool = False) -> str:
    """Run the history agent for storytelling."""
    detail_note = "Include file-level changes for each commit." if detailed else ""
    return _invoke_agent(
        AgentType.HISTORY,
        f"Generate a narrative story of this repository's evolution over the last {days} days. "
        f"Group commits by feature/theme, identify major changes, and tell the story of "
        f"what was built and why. {detail_note}",
    )


def run_explain(target: str, repo_path: str = ".") -> str:
    """Explain a specific commit, file, or feature with Db2 context."""
    query = (
        f"Explain '{target}' in the context of this repository. "
        f"If it's a commit hash, explain what the commit did and why. "
        f"If it's a file path, explain its history and evolution. "
        f"If it's a feature name, trace its development through commits. "
        f"Provide context from PRs and issues if available."
    )
    return run_query(query, command="explain", repo_path=repo_path)


def run_project(query: str = "", repo_path: str = ".") -> str:
    """Run the project agent for architectural and setup overview."""
    if not query:
        query = (
            "Analyze this repository and provide a comprehensive overview. "
            "Explain what the project is, the problem it solves, the technologies "
            "used, the architecture, key components, and how to set it up."
        )
    return _invoke_agent(AgentType.PROJECT, query)
