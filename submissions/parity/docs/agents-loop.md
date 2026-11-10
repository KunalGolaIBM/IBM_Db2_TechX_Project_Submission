# Agent loop

## What it does

Agents propose fixes. The Parity Engine decides if a fix works. The controller in `src/parity/agents/controller.py` is plain Python. It owns every limit.

## Roles

- **Translator:** Postgres SQL to Db2 SQL.
- **Fuzzer:** edge case values per column.
- **Diagnostician:** one sentence hypothesis for a mismatch.
- **Fixer:** rewritten Db2 SQL.

Prompts live in `src/parity/agents/prompts.py`. They hold only SQL and synthetic values. Production rows are never sent to a model.

## Fix loop

1. Diagnostician writes a hypothesis from the first diff.
2. Fixer proposes rewritten SQL.
3. The controller runs the candidate through the injected re-run function. In production that is the full compare runner on both databases.
4. MATCH accepts the fix. Anything else counts as a failed attempt.
5. After 3 failed attempts the query is marked NEEDS_HUMAN with full context.

The controller never trusts an agent verdict. A fix is accepted only when execution returns MATCH.

## CrewAI

`src/parity/agents/crewai_adapter.py` maps the four roles to CrewAI Agent objects. CrewAI is optional. Install it with:

```bash
pip install -e ".[agents]"
```

Without CrewAI, the controller and the gateway runner still work. Tests use a fake CrewAI module.

## Safety

- Max attempts is enforced in code, not in a prompt.
- Token budgets are enforced at the gateway.
- Every agent input and output can be logged for audit in later branches.
