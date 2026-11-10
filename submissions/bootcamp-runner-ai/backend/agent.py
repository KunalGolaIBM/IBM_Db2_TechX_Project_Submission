from __future__ import annotations

from typing import Any, Callable

from .models import RecommendationIn
from .repositories import Repository


def get_learning_history(repo: Repository, learner_id: str) -> list[dict[str, Any]]:
    return repo.get_learning_history(learner_id)


def analyze_topic_performance(history: list[dict[str, Any]], topic: str) -> dict[str, Any]:
    scores = [float(item["score"]) for item in history if str(item.get("topic", "")).lower() == topic.lower()]
    return {"topic": topic, "attempts": len(scores), "average_score": round(sum(scores) / len(scores), 2) if scores else None}


def recommend_difficulty(average_score: float | None) -> str:
    if average_score is None or average_score < 60:
        return "easy"
    if average_score < 80:
        return "medium"
    return "hard"


def generate_practice_recommendation(topic: str, difficulty: str, average_score: float | None) -> str:
    score_text = "no prior score" if average_score is None else f"an average score of {average_score:.1f}%"
    return f"Practice {topic} at {difficulty} difficulty, focusing on retrieval and worked examples ({score_text})."


def save_learning_recommendation(repo: Repository, learner_id: str, topic: str, text: str, difficulty: str, source: str) -> dict[str, Any]:
    return repo.save_recommendation(RecommendationIn(
        learner_id=learner_id, topic=topic, recommendation=text, difficulty=difficulty, source=source
    ))


def build_tools(repo: Repository) -> list[Callable[..., Any]]:
    """Return named LangChain tools (or compatible callables when LangChain is absent)."""
    def history_tool(learner_id: str) -> list[dict[str, Any]]:
        return get_learning_history(repo, learner_id)

    def analysis_tool(history: list[dict[str, Any]], topic: str) -> dict[str, Any]:
        return analyze_topic_performance(history, topic)

    def difficulty_tool(average_score: float | None) -> str:
        return recommend_difficulty(average_score)

    def practice_tool(topic: str, difficulty: str, average_score: float | None) -> str:
        return generate_practice_recommendation(topic, difficulty, average_score)

    def save_tool(learner_id: str, topic: str, text: str, difficulty: str, source: str = "agent") -> dict[str, Any]:
        return save_learning_recommendation(repo, learner_id, topic, text, difficulty, source)

    functions: list[tuple[str, str, Callable[..., Any]]] = [
        ("get_learning_history", "Get recent quiz attempts for a learner.",
         history_tool),
        ("analyze_topic_performance", "Calculate topic attempts and average score.", analysis_tool),
        ("recommend_difficulty", "Choose easy, medium, or hard from an average score.", difficulty_tool),
        ("generate_practice_recommendation", "Write a focused practice recommendation.",
         practice_tool),
        ("save_learning_recommendation", "Persist an AI learning recommendation.", save_tool),
    ]
    try:
        from langchain_core.tools import StructuredTool
        return [StructuredTool.from_function(func, name=name, description=description)
                for name, description, func in functions]
    except ImportError:
        return [func for _, _, func in functions]


class AdaptiveAgent:
    """Tool-using adaptive agent with an explicit deterministic offline fallback."""

    def __init__(self, repo: Repository, llm: Any = None) -> None:
        self.repo = repo
        self.llm = llm

    @property
    def mode(self) -> str:
        return "watsonx" if self.llm is not None else "deterministic-fallback"

    def run(self, learner_id: str, topic: str, requested_difficulty: str | None = None) -> dict[str, Any]:
        if self.llm is not None:
            return self._run_langchain(learner_id, topic, requested_difficulty)
        history = get_learning_history(self.repo, learner_id)
        analysis = analyze_topic_performance(history, topic)
        difficulty = requested_difficulty or recommend_difficulty(analysis["average_score"])
        text = generate_practice_recommendation(topic, difficulty, analysis["average_score"])
        saved = save_learning_recommendation(self.repo, learner_id, topic, text, difficulty, self.mode)
        return {"analysis": analysis, "difficulty": difficulty, "recommendation": saved, "mode": self.mode}

    def _run_langchain(self, learner_id: str, topic: str, requested_difficulty: str | None) -> dict[str, Any]:
        """Run a real LangChain agent; configured LLM failures are never disguised as fallback mode."""
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain_core.prompts import PromptTemplate

        tools = build_tools(self.repo)
        prompt = PromptTemplate.from_template(
            "You are Bootcamp Runner AI. Use the available tools to inspect learner history, "
            "analyze the requested topic, choose difficulty, generate practice advice, and save it. "
            "Learner ID: {learner_id}; topic: {topic}; requested difficulty: {requested_difficulty}.\n"
            "You have access to:\n{tools}\nTool names: {tool_names}\n"
            "Use this format:\nQuestion: {input}\nThought: ...\nAction: one tool name\nAction Input: ...\n"
            "Observation: ...\nFinal: concise recommendation\n{agent_scratchpad}"
        )
        agent = create_react_agent(self.llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=8)
        result = executor.invoke({
            "input": "Create and save an adaptive practice recommendation.",
            "learner_id": learner_id,
            "topic": topic,
            "requested_difficulty": requested_difficulty or "automatic",
        })
        output = str(result.get("output", "")).strip()
        if not output:
            raise RuntimeError("Watsonx agent returned no recommendation")
        return {
            "recommendation": {
                "learner_id": learner_id,
                "topic": topic,
                "recommendation": output,
                "difficulty": requested_difficulty or "medium",
                "source": "watsonx",
            },
            "mode": "watsonx",
            "agent_output": output,
        }


def build_watsonx_llm(settings: Any) -> Any:
    if not settings.llm_configured:
        return None
    try:
        from langchain_ibm import WatsonxLLM
    except ImportError as exc:
        raise RuntimeError("Watsonx is configured but langchain-ibm is not installed") from exc
    return WatsonxLLM(
        model_id=settings.watsonx_model,
        url=settings.watsonx_url,
        project_id=settings.watsonx_project_id,
        apikey=settings.watsonx_apikey,
    )
