"""SplitSync AI Assistant agent orchestrating LangChain tools and deterministic fallbacks."""

import logging
from typing import Optional

from config import settings
from ai.tools import (
    ALL_TOOLS,
    get_group_financial_summary,
    get_member_balances,
    get_recent_transactions,
    get_pending_approvals,
    get_latest_settlement_transfers,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the SplitSync AI financial assistant. You provide accurate, grounded answers about group "
    "expenses, contributions, and settlements based strictly on data retrieved through your tools. "
    "NEVER guess or invent numbers. State amounts clearly in INR (e.g. ₹1,250.00). If information is "
    "unavailable, explain clearly."
)


class AIAssistantService:
    """Manages AI agent execution with tool calling and deterministic fallback."""

    def __init__(self) -> None:
        self.provider = settings.ai_provider
        self.model = settings.ai_model
        self.is_live = False
        self._llm = None
        self._initialize_llm()

    def _initialize_llm(self) -> None:
        """Attempt to configure live LangChain LLM if credentials are provided."""
        try:
            if settings.openai_api_key:
                from langchain_openai import ChatOpenAI  # type: ignore

                self._llm = ChatOpenAI(
                    model=settings.ai_model,
                    api_key=settings.openai_api_key,
                    temperature=0.0,
                )
                self.is_live = True
                self.provider = "openai"
                logger.info("Configured OpenAI Chat LLM: %s", settings.ai_model)
            elif settings.google_api_key:
                from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore

                self._llm = ChatGoogleGenerativeAI(
                    model=settings.ai_model,
                    google_api_key=settings.google_api_key,
                    temperature=0.0,
                )
                self.is_live = True
                self.provider = "google"
                logger.info("Configured Google Generative AI: %s", settings.ai_model)
        except Exception as exc:
            logger.debug("Live LLM initialization deferred to fallback: %s", exc)
            self.is_live = False

    def ask(self, message: str, group_id: Optional[str] = None) -> dict:
        """Answer user questions using tools or deterministic engine."""
        if self.is_live and self._llm is not None:
            try:
                return self._ask_llm(message, group_id)
            except Exception as exc:
                logger.warning("Live LLM query failed, using deterministic fallback: %s", exc)

        return self._deterministic_answer(message, group_id)

    def _ask_llm(self, message: str, group_id: Optional[str]) -> dict:
        """Execute query via LangChain tool-calling model."""
        prompt_text = message
        if group_id:
            prompt_text += f"\n(Context group_id: {group_id})"

        llm_with_tools = self._llm.bind_tools(ALL_TOOLS)  # type: ignore
        ai_msg = llm_with_tools.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ]
        )

        tools_used: list[str] = []
        tool_outputs = []

        if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
            tool_map = {t.__name__: t for t in ALL_TOOLS}
            for tool_call in ai_msg.tool_calls:
                name = tool_call["name"]
                args = tool_call["args"]
                if "group_id" not in args and group_id:
                    args["group_id"] = group_id
                tools_used.append(name)
                func = tool_map.get(name)
                if func:
                    out = func.invoke(args) if hasattr(func, "invoke") else func(**args)
                    tool_outputs.append(str(out))

            # Final grounded synthesis
            synthesis_prompt = (
                f"User asked: {message}\n"
                f"Retrieved database facts:\n" + "\n\n".join(tool_outputs) + "\n"
                "Provide a friendly, concise financial answer formatted in INR."
            )
            final_msg = self._llm.invoke(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": synthesis_prompt},
                ]
            )
            return {
                "response": final_msg.content,
                "group_id": group_id,
                "tools_used": tools_used,
            }

        return {
            "response": str(ai_msg.content),
            "group_id": group_id,
            "tools_used": tools_used,
        }

    def _deterministic_answer(self, message: str, group_id: Optional[str]) -> dict:
        """Deterministic fallback answering common queries strictly through tools."""
        if not group_id:
            return {
                "response": (
                    "Please specify or select a group context so I can look up the accurate financial records for you."
                ),
                "group_id": None,
                "tools_used": [],
            }

        msg_lower = message.lower()
        tools_used: list[str] = []
        parts: list[str] = []

        if any(w in msg_lower for w in ("summary", "total", "spent", "contributed", "how much")):
            parts.append(get_group_financial_summary(group_id))
            tools_used.append("get_group_financial_summary")

        if any(w in msg_lower for w in ("balance", "owe", "who owes", "net")):
            parts.append(get_member_balances(group_id))
            tools_used.append("get_member_balances")

        if any(w in msg_lower for w in ("settle", "transfer", "pay back", "clear")):
            parts.append(get_latest_settlement_transfers(group_id))
            tools_used.append("get_latest_settlement_transfers")

        if any(w in msg_lower for w in ("pending", "approval", "cash", "verify")):
            parts.append(get_pending_approvals(group_id))
            tools_used.append("get_pending_approvals")

        if any(w in msg_lower for w in ("recent", "transaction", "activity", "history")):
            parts.append(get_recent_transactions(group_id))
            tools_used.append("get_recent_transactions")

        if not parts:
            # Default to summary and balances
            parts.append(get_group_financial_summary(group_id))
            parts.append(get_member_balances(group_id))
            tools_used.extend(["get_group_financial_summary", "get_member_balances"])

        response = "\n\n".join(parts)
        return {
            "response": response,
            "group_id": group_id,
            "tools_used": tools_used,
        }

    def get_status(self) -> dict:
        """Return assistant operational status and available analytical tools."""
        return {
            "provider": self.provider,
            "model": self.model,
            "is_live_llm": self.is_live,
            "tools_available": [t.__name__ for t in ALL_TOOLS],
        }


ai_assistant = AIAssistantService()
