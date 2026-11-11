"""Prompt-injection defenses for the natural-language surface.

Heuristic rule set applied to every inbound chat message BEFORE it reaches an
LLM or orchestrator. Modes:

- ``off``   — detection disabled (never the default).
- ``flag``  — detect, attach warnings, still process (demo/observability).
- ``block`` — detect and reject with HTTP 400 (secure default).

Rules target known instruction-override patterns (role markers, "ignore
previous instructions", system-prompt extraction, jailbreak phrasing).
This is a layer, not a moat: prompts are still template-delimited downstream
and the SQL gate validates all generated SQL independently of what the model
"was told".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.errors import PromptInjectionBlockedError

# (rule_id, compiled pattern) — patterns are case-insensitive.
INJECTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous_instructions",
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|earlier)\b"
            r".{0,40}\b(instructions?|prompts?|rules?|directives?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "system_prompt_extraction",
        re.compile(
            r"\b(reveal|show|print|repeat|output)\b.{0,40}\b(system prompt|hidden prompt"
            r"|initial instructions|developer message)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(you are now|act as|pretend to be|role[\s-]?play as)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_phrasing",
        re.compile(
            r"\b(danjailbreak|developer mode|opposite mode|do anything now)\b"
            r"|\bDAN\b.{0,20}\bmode\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_marker_smuggling",
        re.compile(
            r"(###\s*(system|assistant|user)\b|<\|im_start\|>|<\|im_end\|>"
            r"|\[SYSTEM\]|\[ASSISTANT\])",
            re.IGNORECASE,
        ),
    ),
    (
        "instruction_fence_breakout",
        re.compile(r"```(?:system|assistant)|end of (the )?prompt\b", re.IGNORECASE),
    ),
)

MAX_FLAGS = 8


@dataclass(frozen=True, slots=True)
class InjectionVerdict:
    flagged: bool
    rule_ids: tuple[str, ...]
    mode: str

    @property
    def warnings(self) -> list[str]:
        return [f"prompt-injection rule matched: {rid}" for rid in self.rule_ids]


def detect_prompt_injection(text: str) -> tuple[str, ...]:
    """Return the ids of all rules that match ``text``."""
    if not text:
        return ()
    matched: list[str] = []
    for rule_id, pattern in INJECTION_RULES:
        if pattern.search(text):
            matched.append(rule_id)
        if len(matched) >= MAX_FLAGS:
            break
    return tuple(matched)


def screen_message(text: str, mode: str = "block") -> InjectionVerdict:
    """Screen a message according to ``mode``; raise when blocking.

    ``off`` disables detection entirely (documented contract); ``flag``
    detects but processes; ``block`` detects and rejects with HTTP 400.
    """
    if mode == "off":
        return InjectionVerdict(flagged=False, rule_ids=(), mode=mode)
    rule_ids = detect_prompt_injection(text)
    verdict = InjectionVerdict(flagged=bool(rule_ids), rule_ids=rule_ids, mode=mode)
    if verdict.flagged and mode == "block":
        raise PromptInjectionBlockedError(
            "Message blocked by prompt-injection defense.",
            detail={"matched_rules": list(rule_ids)},
        )
    return verdict
