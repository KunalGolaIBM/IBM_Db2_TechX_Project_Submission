from __future__ import annotations

import json
from typing import Any

from .config import Settings
from .errors import CoachingDisabledError, CoachingUnavailableError, LlmNotConfiguredError
from .models import AnalyticsSummary, CoachingResponse, GameDetail


class LangChainCoach:
    """Optional outer adapter; provider packages are imported only on use."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _model(self) -> Any:
        provider = self.settings.coach_provider
        try:
            if provider == "ollama":
                from langchain_ollama import ChatOllama

                return ChatOllama(model=self.settings.coach_model, base_url=self.settings.ollama_base_url, temperature=0.2)
            if provider == "openai":
                if not self.settings.openai_api_key:
                    raise LlmNotConfiguredError("OpenAI coaching needs OPENAI_API_KEY")
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(model=self.settings.coach_model, api_key=self.settings.openai_api_key, temperature=0.2)
        except CoachingUnavailableError:
            raise
        except ModuleNotFoundError as exc:
            raise LlmNotConfiguredError("Install backend/requirements-llm.txt to enable coaching") from exc
        raise CoachingDisabledError("AI coaching is disabled")

    @staticmethod
    def _context(summary: AnalyticsSummary, game: GameDetail | None) -> str:
        facts: dict[str, Any] = {
            "career_summary": summary.model_dump(mode="json"),
            "selected_game": None,
        }
        if game is not None:
            facts["selected_game"] = {
                "game_id": str(game.game_id),
                "result": game.result,
                "termination": game.termination,
                "player_color": game.player_color,
                "opening": {"eco": game.opening_eco, "name": game.opening_name},
                "moves": [move.model_dump() for move in game.moves],
                "analysis": [item.model_dump() for item in game.analysis if item.status == "evaluated"],
            }
        return json.dumps(facts, ensure_ascii=False, default=str)

    def generate(self, summary: AnalyticsSummary, game: GameDetail | None) -> CoachingResponse:
        model = self._model()
        prompt = (
            "You are a concise chess coach. Use only the supplied IBM Db2 facts. "
            "Do not invent moves, evaluations, or statistics. Give 3 actionable observations, "
            "and explicitly say when evidence is insufficient.\n\nFACTS:\n"
            + self._context(summary, game)
        )
        try:
            response = model.invoke(prompt)
        except Exception as exc:
            raise CoachingUnavailableError("The configured coaching provider is unavailable") from exc
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)
        advice = str(content).strip()
        if not advice:
            raise CoachingUnavailableError("The coaching provider returned an empty response")
        return CoachingResponse(provider=self.settings.coach_provider, model=self.settings.coach_model, advice=advice)

