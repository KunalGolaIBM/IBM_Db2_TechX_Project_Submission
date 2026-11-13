"""
src/ai/mood_interpreter.py
--------------------------
Converts a free-text mood description into one of the app's
known mood codes using LangChain + a local Ollama LLM.

This is OPTIONAL — the app works without it. It is only called
when the user types a free-text mood instead of clicking a button.

Usage:
    from src.ai.mood_interpreter import MoodInterpreter
    interpreter = MoodInterpreter()
    code = interpreter.interpret("I feel nostalgic and a bit low")
    # → "sad"
"""

from __future__ import annotations
import os
from dotenv import load_dotenv
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

KNOWN_MOODS = ["sad", "happy", "romantic", "wholesome", "ghazal"]

_PROMPT = PromptTemplate.from_template(
    """You are a music mood classifier for an Indian music app.
The user has described their mood in their own words.
Your only job is to pick the single best matching mood code from this list:
{mood_list}

Rules:
- Reply with ONLY the mood code, nothing else.
- Do not explain or add punctuation.
- If nothing fits, reply with "happy" as a safe default.

User mood description: {user_input}
Mood code:"""
)


class MoodInterpreter:
    """
    Interprets a free-text mood description and returns a mood code.
    Falls back to 'happy' if the LLM is unavailable or returns junk.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        llm = OllamaLLM(model=model, base_url=base_url, temperature=0)
        self._chain = _PROMPT | llm | StrOutputParser()

    def interpret(self, user_input: str) -> str:
        """
        Return a valid mood code for the given free-text input.
        Never raises — falls back to 'happy' on any error.
        """
        if not user_input or not user_input.strip():
            return "happy"
        try:
            raw = self._chain.invoke(
                {
                    "mood_list": ", ".join(KNOWN_MOODS),
                    "user_input": user_input.strip(),
                }
            )
            code = raw.strip().lower().split()[0].strip(".,;:")
            return code if code in KNOWN_MOODS else "happy"
        except Exception as exc:
            print(f"[MoodInterpreter] LLM unavailable, defaulting to 'happy': {exc}")
            return "happy"

