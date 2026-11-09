"""
GitMind — Router

Classifies user queries and determines which agent(s) to invoke.
Uses the LLM to understand query intent and route to the appropriate
specialist agent(s).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from config import get_llm


class AgentType(str, Enum):
    HISTORY = "history"
    RECOVERY = "recovery"
    CODE = "code"
    GITHUB = "github"
    SUGGEST = "suggest"
    DOCS = "docs"
    PROJECT = "project"


class RoutingDecision(BaseModel):
    """Structured routing decision from the LLM."""

    primary_agent: AgentType = Field(
        ...,
        description="The main agent to handle this query."
    )
    secondary_agents: list[AgentType] = Field(
        default_factory=list,
        description="Additional agents that may provide useful context."
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of why this routing was chosen."
    )
    rewritten_query: str = Field(
        default="",
        description="The query rewritten for the target agent, if needed."
    )


ROUTING_PROMPT = """You are a query router for GitMind, a Git repository analysis tool.

Given a user query, determine which specialist agent(s) should handle it.

Available agents:

1. HISTORY — Handles: commit history, repository timeline, "what changed?", 
   "who changed this?", feature evolution, blame analysis, contributor activity.
   Commands: gitmind story, gitmind explain (for commits/files/features)

2. RECOVERY — Handles: lost commits, deleted branches, reflog analysis,
   "I accidentally...", "how do I undo?", detached HEAD, recovering work.
   Command: gitmind recover

3. CODE — Handles: function-level changes, AST analysis, "what functions changed?",
   dependency analysis, code structure questions, module evolution.
   Uses Tree-sitter for semantic code understanding.
   Explains files, folders, and functions when asked specifically using command `gitmind explain`.
   Command: gitmind explain (for files/folder/functions)

4. GITHUB — Handles: pull requests, issues, reviews, discussions,
   "why was this PR created?", "what issue is this related to?",
   commit → PR → issue tracing.

5. SUGGEST — Handles: proactive analysis without a specific question,
   "what should I do next?", safety checks, push risk assessment.
   Command: gitmind suggest

6. DOCS — Handles: git command documentation, "how do I use git rebase?",
   concept explanations, workflow guidance, best practices.

7. PROJECT — Handles: high-level project understanding, "what is this project?",
   project purpose, architecture overview, technologies used, repository
   structure, build/run instructions, design decisions, project metadata.
   Uses README, docs/, pyproject.toml, package.json, and other project files
   as the primary source of truth.

------------------------------------------------------------------------  
EXAMPLES:
------------------------------------------------------------------------

User:
What is git rebase?

→ DOCS

------------------

User:
How does cherry-pick work?

→ DOCS

------------------

User:
Explain this repository.

→ PROJECT

------------------

User:
What is the idea behind this project?

→ PROJECT

------------------

User:
What problem is this project solving?

→ PROJECT

------------------

User:
What technologies does this project use?

→ PROJECT

------------------

User:
How do I set up this project?

→ PROJECT

------------------

User:
Explain the use of workflows/orchestrator.py

→ PROJECT + CODE + HISTORY

------------------

User:
Walk me through this codebase.

→ PROJECT + CODE

------------------

User:
Explain the architecture.

→ PROJECT + CODE

------------------

User:
How does authentication work?

→ CODE

------------------

User:
Why was authentication added?

→ HISTORY + CODE

------------------

User:
Why was this PR created?

→ GITHUB + HISTORY

Routing rules:
- Questions about the project itself ("what is this?", "what does it do?") → PROJECT
- Questions about project architecture, setup, technologies → PROJECT
- Most questions about "what happened" → HISTORY
- Questions about "what code changed" at function level → CODE (with HISTORY as secondary)
- Questions about "why" that mention PRs/issues → GITHUB (with HISTORY as secondary)
- Questions about recovering lost work → RECOVERY
- "What should I do?" with no specific question → SUGGEST
- "How do I use X?" → DOCS
- Complex questions may need multiple agents

Respond with a JSON object matching this schema:
{
  "primary_agent": "history|recovery|code|github|suggest|docs|project",
  "secondary_agents": ["agent1", "agent2"],
  "reasoning": "Brief explanation",
  "rewritten_query": "Query optimized for the target agent"
}"""


def route_query(query: str, command: Optional[str] = None) -> RoutingDecision:
    """
    Route a user query to the appropriate agent(s).

    Args:
        query: The user's natural language query
        command: Optional CLI command context (e.g., "story", "recover")

    Returns:
        RoutingDecision with primary and secondary agents
    """
    # Fast-path for known commands
    if command:
        # this is the fast path where the command is already known and the agent is decided
        command_map = {
            "story": AgentType.HISTORY,
            "recover": AgentType.RECOVERY,
            "suggest": AgentType.SUGGEST,
            "explain": AgentType.HISTORY,
            "project": AgentType.PROJECT,
        }
        
        secondary_map = { # separate map for secondary agents, modify as per the need
        "story": [AgentType.GITHUB],
        "explain": [AgentType.CODE, AgentType.PROJECT, AgentType.GITHUB],
        "recover": [AgentType.GITHUB, AgentType.HISTORY],
        "suggest": [AgentType.GITHUB, AgentType.PROJECT],
        "project": [AgentType.GITHUB],
        }
        
        if command in command_map:
            return RoutingDecision(
                primary_agent=command_map[command],
                secondary_agents=secondary_map.get(command, []),
                reasoning=f"Direct routing from '{command}' command.",
                rewritten_query=query,
            )

    # Fast-path heuristics for high-confidence intents
    q_lower = query.lower().strip()
    if any(p in q_lower for p in ("what is gitmind", "what is the gitmind", "what is this project", "project overview", "about this project", "what does this project do")):
        return RoutingDecision(
            primary_agent=AgentType.PROJECT,
            secondary_agents=[],
            reasoning="Direct intent match: project overview and architecture.",
            rewritten_query=query,
        )
    if any(p in q_lower for p in ("how do i undo", "i accidentally", "recover lost", "find deleted branch", "how to recover")):
        return RoutingDecision(
            primary_agent=AgentType.RECOVERY,
            secondary_agents=[],
            reasoning="Direct intent match: git recovery and reflog.",
            rewritten_query=query,
        )

    # LLM-based routing for `ask` command and ambiguous queries
    # this is the slow path where the command is not known and the agent is decided by the LLM
    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(RoutingDecision)

    try:
        decision = structured_llm.invoke(
            f"{ROUTING_PROMPT}\n\nUser query: {query}"
        )
        if not decision.rewritten_query:
            decision.rewritten_query = query
        return decision
    except Exception:
        # Fallback: route to history agent
        return RoutingDecision(
            primary_agent=AgentType.HISTORY,
            secondary_agents=[],
            reasoning="Fallback routing — could not determine intent.",
            rewritten_query=query,
        )
