"""AsOf policy check as a Langflow component.

Put it between an assistant and the customer: it sends the draft, the question, the date that decides
which policy applies and the policy document to AsOf's /api/gate, and passes on only what AsOf releases.
It talks to AsOf over HTTP, so a Langflow install needs none of AsOf's own dependencies.

Load it in the Langflow UI by pointing LANGFLOW_COMPONENTS_PATH at the folder that holds `asof_policy/`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

DOCS = ["AURELIA-CSP", "FERNHOLLOW-FEES"]
URL = re.compile(r"^https?://[A-Za-z0-9.\-]+(:[0-9]{1,5})?/?$")


class AsOfCheckComponent(Component):
    display_name = "AsOf policy check"
    description = ("Checks a draft answer against the policy version in force on the customer's date (IBM Db2) "
                   "and passes on only what AsOf releases.")
    icon = "shield-check"
    name = "AsOfCheck"

    inputs = [
        MultilineInput(name="draft_answer", display_name="Draft answer", required=True,
                       info="What the assistant wants to send."),
        MessageTextInput(name="question", display_name="Customer question", required=True),
        StrInput(name="as_of_date", display_name="As-of date", required=True,
                 info="YYYY-MM-DD: the booking or account date from your system, never the model's guess."),
        DropdownInput(name="doc_id", display_name="Policy document", options=DOCS, value=DOCS[0]),
        StrInput(name="api_url", display_name="AsOf URL", value="http://127.0.0.1:8000", advanced=True),
        SecretStrInput(name="api_token", display_name="AsOf API token", required=False, advanced=True,
                       info="Only if the server sets ASOF_API_TOKEN."),
        IntInput(name="timeout_s", display_name="Timeout (s)", value=120, advanced=True),
    ]
    outputs = [
        Output(display_name="Answer to send", name="answer", method="checked_answer"),
        Output(display_name="Verdicts", name="verdicts", method="verdicts"),
    ]

    def _check(self) -> dict[str, Any]:
        cached = getattr(self, "_asof_result", None)
        if cached is not None:
            return cached
        try:
            on = date.fromisoformat(str(self.as_of_date).strip())
        except ValueError:
            raise ValueError("as_of_date must be an ISO date (YYYY-MM-DD)") from None
        url = str(self.api_url).strip().rstrip("/")
        if not URL.match(url + "/"):
            raise ValueError("api_url must be an http(s) URL with no path")
        if self.doc_id not in DOCS:
            raise ValueError(f"doc_id must be one of {DOCS}")
        headers = {"content-type": "application/json"}
        if self.api_token:
            headers["authorization"] = f"Bearer {self.api_token}"
        body = {"question": str(self.question), "draft_answer": str(self.draft_answer), "as_of_date": on.isoformat(),
                "doc_id": self.doc_id, "channel": "api"}
        resp = httpx.post(f"{url}/api/gate", json=body, headers=headers, timeout=max(5, int(self.timeout_s)))
        if resp.status_code not in (200, 503):  # 503 = checked but not released (a holding reply instead)
            raise ValueError(f"AsOf returned HTTP {resp.status_code}: {resp.text[:200]}")
        result = resp.json()
        if "decision" not in result:
            raise ValueError(f"AsOf could not check the draft: {result.get('error', 'unknown error')}")
        self._asof_result = result
        self.status = f"{result['decision']} ({result['reason_code']}), ledger #{result.get('ledger_id')}"
        return result

    def checked_answer(self) -> Message:
        """The released answer (as written, or corrected), or AsOf's holding reply."""
        return Message(text=self._check()["final_answer"])

    def verdicts(self) -> Data:
        r = self._check()
        return Data(data={k: r.get(k) for k in ("decision", "reason_code", "released", "ledger_id", "claims")})
