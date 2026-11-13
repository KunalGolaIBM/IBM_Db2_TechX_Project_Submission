# Architecture — Khata AI

## Overview

```
 Shopkeeper (types Hinglish sentence)
          │
          ▼
 ┌──────────────────┐    structured output     ┌──────────────────────┐
 │  app.py / ui.py  │ ───────────────────────► │  llm.py              │
 │  (CLI / Streamlit)│ ◄─────────────────────── │  LangChain + Gemini  │
 └──────────────────┘   {name, amount, type,   │  (offline fallback)  │
          │              note}                  └──────────────────────┘
          │ add_entry / get_pending / get_history
          ▼
 ┌──────────────────┐        ibm_db_dbi        ┌──────────────────────┐
 │      db.py       │ ───────────────────────► │  IBM Db2 (Docker)    │
 └──────────────────┘                          │  customers, entries  │
                                               └──────────────────────┘
```

## Components

| Component | Responsibility |
|---|---|
| `llm.py` | Turns a Hinglish sentence into a validated `LedgerEntry` (Pydantic) using LangChain `with_structured_output`; writes reminder messages. Falls back to a regex/keyword parser when no API key is available or the call fails. |
| `db.py` | All Db2 access: connection from environment variables, idempotent schema creation, inserts, reports. |
| `app.py` | Menu-driven CLI with a confirmation step before saving an entry. |
| `ui.py` | Optional Streamlit UI with the same functions. |

## Db2 schema

```sql
CREATE TABLE customers (
  id   INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
  name VARCHAR(60) NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE entries (
  id          INTEGER NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
  customer_id INTEGER NOT NULL,
  amount      DECIMAL(10,2) NOT NULL,
  entry_type  VARCHAR(10) NOT NULL,      -- 'UDHAAR' or 'PAYMENT'
  note        VARCHAR(200),
  entry_date  DATE NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (customer_id) REFERENCES customers (id)
);
```

The tables are created on start-up only if they do not already exist (checked via `SYSCAT.TABLES`).

## Key query — pending dues, oldest first

```sql
SELECT c.name,
       SUM(CASE WHEN e.entry_type = 'UDHAAR' THEN e.amount ELSE -e.amount END) AS balance,
       DAYS(CURRENT DATE) - DAYS(MIN(e.entry_date)) AS days_old
FROM customers c
JOIN entries e ON e.customer_id = c.id
GROUP BY c.name
HAVING SUM(CASE WHEN e.entry_type = 'UDHAAR' THEN e.amount ELSE -e.amount END) > 0
ORDER BY days_old DESC, balance DESC;
```

## AI flow

1. The user's sentence goes into a prompt that describes the shopkeeper context (Hindi/Hinglish, UDHAAR vs PAYMENT).
2. `ChatGoogleGenerativeAI(...).with_structured_output(LedgerEntry)` returns a validated object.
3. The CLI shows what was understood and asks for confirmation before anything is written to Db2.
4. If the API key is missing or the call fails, `_fallback_parse` extracts the same fields with rules (name before "ne/ko", first number, payment keywords such as *wapas*, *chukaya*, *jama*).
5. Reminders: the LLM writes a short polite Hinglish message from `(name, balance, days_old)`; a fixed template is used if the LLM is unavailable.

## Design decisions

- **The LLM never does arithmetic.** It only converts text to fields; balances and ageing are computed by Db2, so numbers are exact and auditable.
- **Human in the loop.** Every parsed entry is shown for confirmation before saving.
- **Graceful degradation.** The app works fully offline of the LLM.
- **Secrets.** Credentials and API keys are read from environment variables (`.env`, git-ignored); `.env.example` contains placeholders only.
