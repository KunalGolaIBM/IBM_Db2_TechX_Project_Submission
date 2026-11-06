"""A Langflow flow, runnable headless with `lfx run`: the assistant's draft comes in as the chat message,
AsOf checks it for the question, date and policy document given below, and only what AsOf releases goes out.

    lfx run langflow/asof_check_flow.py "The overdraft fee is $35 for each item we pay." --format text
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "components"))

from asof_policy.asof_check import AsOfCheckComponent  # noqa: E402
from lfx.components.input_output import ChatInput, ChatOutput  # noqa: E402
from lfx.graph import Graph  # noqa: E402


def get_graph() -> Graph:
    chat_input = ChatInput()
    check = AsOfCheckComponent()
    check.set(
        draft_answer=chat_input.message_response,
        question=os.environ.get("ASOF_QUESTION", "How much is the overdraft fee?"),
        as_of_date=os.environ.get("ASOF_AS_OF", "2026-08-03"),
        doc_id=os.environ.get("ASOF_DOC_ID", "FERNHOLLOW-FEES"),
        api_url=os.environ.get("ASOF_URL", "http://127.0.0.1:8000"),
        api_token=os.environ.get("ASOF_API_TOKEN", ""),
    )
    chat_output = ChatOutput()
    chat_output.set(input_value=check.checked_answer)
    return Graph(chat_input, chat_output)
