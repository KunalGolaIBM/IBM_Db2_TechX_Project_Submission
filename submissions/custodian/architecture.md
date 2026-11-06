# System Architecture

## Overview
Custodian puts IBM Db2 between an AI agent and production data, and makes the **database engine** the agent's guardrail.
The demo app is the support desk of *NovaPay*, a fictional fintech. Its LangGraph agent has two tools, ticket search and SQL, and both go through
the Custodian gateway (`src/gateway.py`). The gateway never trusts the prompt. Each statement is classified, its blast radius is measured,
it is checked against a policy table held in Db2, and if needed it is parked for a human. Then it runs **on the end user's own Db2
connection**, so Db2's GRANTs and Row and Column Access Control (RCAC) decide what the agent can see or change. Every attempt is written to a
ledger in Db2. System-period temporal tables make each agent write reversible (Rewind) and each AI answer reproducible (Replay).

---

## Architecture Diagram

```mermaid
graph TD
    U[Streamlit UI<br/>persona: Priya SUPPORT / Arjun ADMINS] -->|prompt| A[LangGraph agent<br/>plan → act → approval → finish]
    A -->|llm()| L[Groq gpt-oss-120b → Ollama qwen2.5 → offline script]
    A -->|search_tickets| V[DB2VS langchain-db2<br/>on the user's connection]
    A -->|sql| G{Custodian gateway}
    G -->|1. classify| C[sqlglot + IBM db2-sqlglot dialect<br/>1 stmt · SELECT/INSERT/UPDATE/DELETE · BANK tables only]
    G -->|2. blast radius| B[COUNT* rewrite run AS USER<br/>+ EXPLAIN PLAN cost<br/>+ CUSTODIAN.POLICY]
    G -->|3. approve?| P[(CUSTODIAN.APPROVALS)]
    P -.LangGraph interrupt / resume.-> A
    G -->|4. execute as PRIYA / ARJUN| D[(IBM Db2 12.1.5<br/>BANK schema)]
    G -->|every attempt| LG[(CUSTODIAN.LEDGER)]
    D --- R[RCAC: row permission + 3 column masks]
    D --- T[System-period temporal<br/>CUSTOMERS_HIST · ACCOUNTS_HIST]
    D --- X[VECTOR 384 FLOAT32<br/>TICKET_EMBEDDINGS]
    U -->|Rewind| T
    U -->|Replay: SET CURRENT TEMPORAL SYSTEM_TIME| T
```

---

## Component Breakdown

1. **User interface (`src/app.py`, Streamlit)**
   - Persona switcher (support agent Priya, admin Arjun). Each persona is a real Db2 authorization ID.
   - Chat, plus a live panel showing every statement, its decision, the deciding layer, the exact row count, the share of the table, and the EXPLAIN cost.
   - An approvals queue read from Db2, and a ledger view with **Rewind** and **Replay** buttons.
2. **Agent (`src/agent.py`, LangGraph)**
   - `plan` calls `llm()`: Groq first, then local Ollama, both through their OpenAI-compatible APIs. With `--no-llm` / `CUSTODIAN_LLM=none` it replays scripted plans, and it falls back to those plans automatically if every provider fails.
   - `act` runs a tool. `approval` pauses the graph with `interrupt()`; an admin's decision resumes it with `Command(resume=...)`. `finish` stores the answer in the ledger.
3. **Gateway (`src/gateway.py`)**: the only code that talks to Db2 for the agent. Its layers are listed under Data Flow below.
4. **Database layer (IBM Db2 12.1.5 Community Edition, Docker)**: business data, the security model, history, vectors and the control-plane tables all live in Db2.
5. **Retrieval (`src/retrieval.py`)**: the official `langchain-db2` `DB2VS` store with local `ibm-granite/granite-embedding-30m-english` embeddings (384 dimensions, cosine).

---

## Data Flow

1. **Input**: Priya types a request. LangGraph starts a thread whose state records her Db2 identity.
2. **Context retrieval**: `search_tickets` runs `VECTOR_DISTANCE(embedding, VECTOR(?,384,FLOAT32), COSINE)` through DB2VS on **Priya's** connection. This is also where the demo's prompt-injection arrives, inside ticket #7100.
3. **Inference**: the model proposes one SQL statement as JSON.
4. **Gateway layers**:
   1. **classifier**: parses the SQL with sqlglot using IBM's Db2 dialect. It must be exactly one statement, of type SELECT, INSERT, UPDATE or DELETE, touching only BANK tables (no `CUSTODIAN.*`, `*_HIST`, `SYS*` or routine calls). DDL, GRANT, SET, CALL, MERGE and TRUNCATE are refused.
   2. **blast radius**: the DML is rewritten to `SELECT COUNT(*) FROM <same table> WHERE <same predicate>` and run **as the user**, so RCAC row permissions shape the count. `EXPLAIN PLAN FOR <dml>` adds the optimizer's cost. `CUSTODIAN.POLICY` (role × table × operation) returns ALLOW, APPROVE or DENY.
   3. **approval**: an APPROVE decision inserts a row into `CUSTODIAN.APPROVALS`, and the LangGraph run pauses. An admin approves; the four-eyes rule forbids approving your own request. The gateway re-measures and refuses if the statement would now touch more rows than were approved.
   4. **execute as the human**: the statement runs on Priya's own connection in one transaction, wrapped as `SELECT pk, SYS_START FROM FINAL TABLE (UPDATE ...)` or `SELECT pk FROM OLD TABLE (DELETE ...)`. This captures the exact transaction timestamp Db2 stamped on the rows. If the touched row count differs from the preflight count, it rolls back.
5. **State persistence**: every attempt is written to `CUSTODIAN.LEDGER` with its decision, layer, reason, row counts, cost, `AS_OF` (for reads) and `TX_TS` (for writes). The final answer is stored with them.
6. **Rewind** (admin only): undoes one agent transaction from Db2's own history. It updates rows back to the version whose `SYS_END` equals the transaction timestamp, re-inserts deleted rows, and deletes inserted rows, all in one transaction run **as the admin**. History is read through `BANK.T FOR SYSTEM_TIME FROM … TO …`, not `*_HIST`: once RCAC is active, Db2 guards the history table with a default deny-all permission (`SYS_DEFAULT_ROW_PERMISSION__CUSTOMERS_HIST`, `1 = 0`), so history is only visible through the base table under the same masks. Rewind refuses if a row was edited again later.
7. **Replay** (auditor): re-runs a ledgered read as the same identity, with `SET CURRENT TEMPORAL SYSTEM_TIME = <AS_OF>`, and then again for now, and shows both side by side. The agent's SQL is not modified.

---

## IBM Db2 Schema & Storage Design

Full DDL: [`src/schema.sql`](src/schema.sql) and [`src/rcac.sql`](src/rcac.sql). The key parts:

```sql
-- Temporal business table: Db2 archives every prior version automatically
CREATE TABLE BANK.ACCOUNTS (
  ACCOUNT_ID INTEGER NOT NULL PRIMARY KEY, CUSTOMER_ID INTEGER NOT NULL, PRODUCT VARCHAR(20) NOT NULL,
  BALANCE DECIMAL(12,2) NOT NULL, LATE_FEE DECIMAL(8,2) NOT NULL, INTEREST_RATE DECIMAL(5,2) NOT NULL,
  SYS_START TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN IMPLICITLY HIDDEN,
  SYS_END   TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END IMPLICITLY HIDDEN,
  TRANS_ID  TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID IMPLICITLY HIDDEN,  -- required (SQL20490N rc 2)
  PERIOD SYSTEM_TIME (SYS_START, SYS_END));
CREATE TABLE BANK.ACCOUNTS_HIST LIKE BANK.ACCOUNTS;
ALTER TABLE BANK.ACCOUNTS ADD VERSIONING USE HISTORY TABLE BANK.ACCOUNTS_HIST;

-- RCAC: enforced by the engine for every access path
CREATE PERMISSION BANK.CUSTOMERS_ROWS ON BANK.CUSTOMERS
  FOR ROWS WHERE VERIFY_ROLE_FOR_USER(SESSION_USER, 'ADMINS') = 1
              OR (VERIFY_ROLE_FOR_USER(SESSION_USER, 'SUPPORT') = 1 AND SEGMENT = 'RETAIL')
  ENFORCED FOR ALL ACCESS ENABLE;
CREATE MASK BANK.CUSTOMERS_CARD_MASK ON BANK.CUSTOMERS FOR COLUMN CARD_NUMBER RETURN
  CASE WHEN VERIFY_ROLE_FOR_USER(SESSION_USER, 'ADMINS') = 1 THEN CARD_NUMBER
       ELSE CAST('XXXX-XXXX-XXXX-' || SUBSTR(CARD_NUMBER, 16, 4) AS CHAR(19)) END ENABLE;

-- Vector store created by langchain-db2 DB2VS
-- BANK.TICKET_EMBEDDINGS(id CHAR(16) PK, text CLOB, metadata BLOB, embedding VECTOR(384, FLOAT32))

-- Control plane: end users hold no privileges on these
CREATE TABLE CUSTODIAN.POLICY    (ROLE_NAME, TABLE_NAME, OPERATION, AUTO_ALLOW_MAX, APPROVAL_MAX, PK(...));
CREATE TABLE CUSTODIAN.APPROVALS (APPROVAL_ID IDENTITY, LEDGER_ID, REQUESTED_BY, SQL_TEXT, ROWS_AFFECTED, THREAD_ID, STATUS, DECIDED_BY, DECIDED_AT);
CREATE TABLE CUSTODIAN.LEDGER    (ENTRY_ID IDENTITY, CREATED_AT, DB_USER, PROMPT, SQL_TEXT, DECISION, LAYER, REASON,
                                  ROWS_AFFECTED, TABLE_ROWS, EST_COST, AS_OF, TX_TS, ANSWER, REWOUND_BY);
```

| Table | Rows (seed) | Notes |
|---|---|---|
| BANK.CUSTOMERS (+ `_HIST`) | 3,200 | 320 PRIVATE (hidden from SUPPORT), 1,206 INACTIVE. PAN, card and e-mail are masked for non-admins. |
| BANK.ACCOUNTS (+ `_HIST`) | 4,810 | Customer 1042 has a 59.00 late fee and a 36.00% rate (demo). |
| BANK.TICKETS | 61 | Ticket #7100 carries the prompt-injection payload. |
| BANK.TICKET_EMBEDDINGS | 61 | `VECTOR(384, FLOAT32)`. Brute-force cosine search is fine at this size. |

Identities: `PRIYA` (role `SUPPORT`) and `ARJUN` (role `ADMINS`) are OS users baked into the Db2 image (`Dockerfile`). Db2 authenticates
OS users, so they are real Db2 authorization IDs, and `SESSION_USER` inside RCAC rules is the human, not a shared service account.
`db2inst1` is the gateway's own identity. It owns the control-plane tables and holds no role, so RCAC shows it **zero** customer rows.

---

## Security & Secrets Management
- All credentials are read at runtime from `.env` (gitignored). `.env.example` holds placeholders only. The Groq key is optional.
- The demo users' passwords are passed to `docker compose` as build arguments from `.env`. In production, use a Db2 **trusted context** so the gateway can switch the connection's user without holding their passwords (see Known Limitations in README).
- The agent can never issue `SET`, `GRANT`, DDL, or touch `CUSTODIAN.*`. That is enforced twice, by the classifier and by Db2 GRANTs.
