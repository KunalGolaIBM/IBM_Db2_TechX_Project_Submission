"""Shared deterministic LLM doubles.

These fakes exist only in tests. They never ship in the application path; the
production client is LangChain + a configured hosted model.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

_PASSAGE_HEADER = re.compile(r"\[PASSAGE ID (\d+)\][^\n]*")


class ScriptedLLM:
    provider_name = "scripted-test-llm"

    def __init__(self, handler: Callable[[str, str], str]) -> None:
        self.handler = handler
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.handler(system_prompt, user_prompt)


def extraction_response(claims: list[dict]) -> str:
    return json.dumps({"claims": claims})


def verification_response(
    classification: str,
    passage_ids: list[int] | None = None,
    explanation: str = "The cited passage explicitly states the measured result described by the claim.",
    limitations: str = "The evidence is synthetic and covers only a controlled setting.",
) -> str:
    evidence = [{"passage_id": pid, "quote": "quoted evidence"} for pid in (passage_ids or [])]
    return json.dumps(
        {
            "classification": classification,
            "explanation": explanation,
            "limitations": limitations,
            "evidence": evidence,
        }
    )


def passages_in_prompt(user_prompt: str) -> list[tuple[int, str]]:
    """Return (passage_id, header) pairs present in a verification prompt."""
    results = []
    for match in _PASSAGE_HEADER.finditer(user_prompt):
        results.append((int(match.group(1)), match.group(0)))
    return results


def passage_id_containing(user_prompt: str, needle: str) -> int | None:
    """Find the id of the passage block containing a distinctive string."""
    blocks = user_prompt.split("[PASSAGE ID ")
    for block in blocks[1:]:
        if needle in block:
            return int(block.split("]", 1)[0])
    return None
