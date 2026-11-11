from __future__ import annotations

from typing import Any, Callable

from .models import Difficulty
from .repositories import Repository

ARCADE_MEDIUM_SCORE = 500
ARCADE_HARD_SCORE = 1500


def build_tools(repo: Repository) -> list[Callable[..., Any]]:
    """Expose only read profile/score tools and the controlled challenge writer."""
    def profile_tool(player_id: str) -> dict[str, Any] | None:
        return repo.get_profile(player_id)
    def score_tool(player_id: str) -> list[dict[str, Any]]:
        return repo.list_scores(player_id)
    def challenge_tool(player_id: str, objective: str, challenge: str, difficulty: Difficulty, source: str = "assistant") -> dict[str, Any]:
        return repo.save_assistant_output(player_id, objective, challenge, difficulty, source)
    functions = [
        ("get_player_profile", "Read the player's profile.", profile_tool),
        ("get_recent_scores", "Read recent game scores.", score_tool),
        ("save_adaptive_challenge", "Save one generated challenge for the player.", challenge_tool),
    ]
    try:
        from langchain_core.tools import StructuredTool
        return [StructuredTool.from_function(func=f, name=n, description=d) for n, d, f in functions]
    except ImportError:
        return [f for _, _, f in functions]


def choose_difficulty(scores: list[dict[str, Any]]) -> str:
    if not scores:
        return "easy"
    average = sum(float(item.get("score", 0)) for item in scores) / len(scores)
    return "hard" if average >= ARCADE_HARD_SCORE else "medium" if average >= ARCADE_MEDIUM_SCORE else "easy"


class GameAssistant:
    def __init__(self, repo: Repository, llm: Any = None) -> None:
        self.repo, self.llm = repo, llm

    @property
    def mode(self) -> str:
        return "watsonx" if self.llm is not None else "deterministic-offline"

    def run(self, request: Any) -> dict[str, Any]:
        difficulty = request.requested_difficulty
        scores = self.repo.list_scores(request.player_id)
        if difficulty is None:
            difficulty = choose_difficulty(scores)
        if self.llm is not None:
            return self._run_langchain(request, difficulty)
        challenge = f"Complete a {difficulty} CEO mission focused on: {request.objective}."
        saved = self.repo.save_assistant_output(request.player_id, request.objective, challenge, difficulty, self.mode)
        return {"challenge": saved, "mode": self.mode}

    def _run_langchain(self, request: Any, difficulty: str) -> dict[str, Any]:
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain_core.prompts import PromptTemplate
        tools = build_tools(self.repo)
        prompt = PromptTemplate.from_template(
            "You are the Bootcamp Runner AI CEO assistant. Use only the supplied tools. "
            "Create and save one actionable challenge. Player: {player_id}; objective: {objective}; "
            "difficulty: {difficulty}.\n{tools}\nTool names: {tool_names}\n"
            "Question: {input}\nThought: ...\nAction: ...\nAction Input: ...\nObservation: ...\n"
            "Final: concise challenge\n{agent_scratchpad}")
        executor = AgentExecutor(agent=create_react_agent(self.llm, tools, prompt), tools=tools, verbose=False, max_iterations=8)
        result = executor.invoke({"input": "Create and save the challenge.", "player_id": request.player_id,
                                  "objective": request.objective, "difficulty": difficulty})
        output = str(result.get("output", "")).strip()
        if not output:
            raise RuntimeError("Watsonx agent returned no challenge")
        return {"challenge": {"player_id": request.player_id, "objective": request.objective,
                              "challenge": output, "difficulty": difficulty, "source": "watsonx"}, "mode": "watsonx"}
