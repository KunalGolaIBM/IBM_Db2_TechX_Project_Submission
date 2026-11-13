# AsOf as a Langflow component

[components/asof_policy/asof_check.py](components/asof_policy/asof_check.py) is a Langflow component,
**AsOf policy check**, that sits between an assistant and the customer. It sends the draft, the question,
the date that decides which policy applies and the policy document to AsOf's `/api/gate`, and its
**Answer to send** output is only what AsOf releases: the draft as written, a corrected version, or the
holding reply. A second output, **Verdicts**, carries the decision, the ledger entry and the per-claim
verdicts. It talks to AsOf over HTTP, so a Langflow install needs none of AsOf's dependencies.

[asof_check_flow.py](asof_check_flow.py) is a complete flow (Chat Input, AsOf policy check, Chat Output)
that `lfx`, Langflow's executor, runs headless.

## Run it

Langflow gets its own virtualenv: it pins its own LangChain.

```bash
python3.12 -m venv .venv-langflow && .venv-langflow/bin/pip install -r langflow/requirements-langflow.txt
python src/main.py &                                   # AsOf on http://127.0.0.1:8000
.venv-langflow/bin/lfx run langflow/asof_check_flow.py "The overdraft fee is \$35 for each item we pay." --format text
```

The flow reads `ASOF_QUESTION`, `ASOF_AS_OF`, `ASOF_DOC_ID`, `ASOF_URL` and `ASOF_API_TOKEN` from the
environment (defaults: the bank's overdraft question for 3 August 2026). In the Langflow UI, set
`LANGFLOW_COMPONENTS_PATH` to `langflow/components` and the component appears under **asof_policy**.

## Verified

On 6 Nov 2026 with `lfx` 1.13.1 (and IBM's `lfx-ibm` 0.3.2 bundle installed alongside), against AsOf with
OpenRouter: the draft "The overdraft fee is $35 for each item we pay." for 3 August 2026 came out of the
flow as "An overdraft fee of $25 is charged for each item we pay ... Policy references: OVD-001 v2 (in effect
from 2026-07-01)." The component tests (no server) cover the request it sends, that both outputs share one
check, the holding reply on a held answer, the bearer token, and that bad dates, URLs and documents are
refused before any request. CI runs them.
