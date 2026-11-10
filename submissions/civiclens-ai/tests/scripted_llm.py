"""A scripted chat model used as a TEST DOUBLE for the agent loop. It is not an LLM and any
recommendation it produces is labelled ``test-double:scripted`` in Db2, never ``LLM`` evidence
for a real provider."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

Responder = Callable[[list[BaseMessage], int], AIMessage]


class ScriptedChatModel(BaseChatModel):
    responder: Any
    calls: int = 0
    bound_tool_names: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "scripted-test-double"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        self.bound_tool_names = [getattr(t, "name", str(t)) for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        self.calls += 1
        msg = self.responder(messages, self.calls)
        return ChatResult(generations=[ChatGeneration(message=msg)])


def tool_call(name: str, args: dict, call_id: str = "c1") -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def ai_calls(*calls: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=list(calls))
