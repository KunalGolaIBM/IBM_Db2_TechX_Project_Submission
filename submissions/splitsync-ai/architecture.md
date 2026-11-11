# System Architecture

## Overview

SplitSync AI is built on a multi-tier, modular architecture designed for financial correctness, horizontal scalability, and low-latency interaction. The system bridges enterprise-grade transactional persistence via **IBM Db2** with a modern full-stack web application powered by **FastAPI** (Python 3.11+) and **Next.js 14** (TypeScript). Financial integrity is guaranteed through an integer-paise double-entry ledger service, graph-based debt simplification, and an immutable audit trail. An integrated **LangChain** conversational engine enables natural language querying over financial records via strictly allow-listed, read-only Db2 analytical tools.

---

## Architecture Diagram

```mermaid
graph TD
    User([Browser / Mobile Client]) -->|HTTPS / React 18| Frontend[Next.js 14 Frontend Application]
    Frontend -->|REST API / JSON| Backend[FastAPI Backend Application]

    subgraph "Application Backend Layer (FastAPI)"
        Backend --> AuthMiddleware[Auth Middleware & JWT Validation]
        
        AuthMiddleware --> GroupService[Group Services]
        AuthMiddleware --> ExpenseService[Expense Services]
        AuthMiddleware --> PaymentService[Payment Services]
        
        GroupService --> FinancialServices[Financial Services]
        ExpenseService --> FinancialServices
        PaymentService --> FinancialServices
        
        subgraph "Financial Services Layer"
            FinancialServices --> SettlementEngine[Settlement Engine (Min Cash-Flow)]
            FinancialServices --> AuditService[Audit Service]
            FinancialServices --> LedgerService[Double-Entry Ledger Service]
        end
        
        Backend --> AIAssistant[LangChain Assistant Engine]
        AIAssistant -->|Safe Analytical Tool Calls| FinancialServices
        AIAssistant -->|Allow-Listed Queries| DB2Repo[Db2 Repository Layer]
        
        FinancialServices --> DB2Repo
    end

    subgraph "Data Persistence Layer"
        DB2Repo -->|ibm_db Native Driver / Parameterized SQL| Db2[(IBM Db2 Database)]
    end
```

---

## Component Breakdown

### 1. User Interface / Client Layer (Next.js 14)
- **Framework**: Next.js 14 with App Router, React 18, TypeScript, and Tailwind CSS.
- **State & Data Fetching**: Client and server components utilizing asynchronous REST requests against the FastAPI backend.
- **Component Architecture**: Modular UI components for group dashboards, dynamic split inputs (Equal, Exact, Percentage, Shares), real-time net balance visualizers, interactive UPI QR settlement modals, and a slide-over AI conversational chat interface.
- **Security**: Stateless JWT storage with automatic request header injection and route protection middleware.

### 2. Application Backend Layer (FastAPI)
- **Framework**: FastAPI (Python 3.11+) with Pydantic v2 data models for rigorous request and response validation.
- **Authentication & Security**: PyJWT for issuing and verifying HMAC-SHA256 signed access tokens; Passlib with bcrypt for salted password hashing.
- **Middleware**: Centralized exception handling (`AppError`, validation handlers), structured logging, and configurable CORS middleware.
- **API Surface**: Clean RESTful endpoints organized under `/api/auth`, `/api/groups`, `/api/expenses`, `/api/payments`, `/api/ledger`, and `/api/ai`.

### 3. Domain & Application Services Layer
- **Group Services**: Handles group lifecycle, member role permissions (`admin`, `member`), group settings, and invitation token generation.
- **Expense Services**: Validates expense creation, enforces that split allocations sum exactly to the total expense amount in paise, and coordinates ledger journal postings.
- **Payment Services**: Manages UPI payment intent lifecycles, formats standard UPI deep-link URLs (`upi://pay`), generates dynamic QR code images, and manages settlement confirmation states.

### 4. Financial Services Layer
- **Double-Entry Ledger Service**: Implements standard double-entry bookkeeping principles. Every expense and settlement records balancing debit and credit entries in Db2. Balances are derived directly from the ledger to prevent state desynchronization.
- **Settlement Engine (Minimum Cash-Flow Algorithm)**: Constructs a directed graph of all inter-member net obligations within a group and applies an optimized debt simplification algorithm. It reduces complex multi-party debt webs to the minimum possible number of direct peer-to-peer settlement transactions.
- **Audit Service**: Produces an immutable, append-only log of every state change, recording entity type, entity ID, action, user ID, payload snapshot, and timestamp.

### 5. AI / Model Orchestration Layer (LangChain)
- **Framework**: LangChain 0.2 ReAct agent workflow with model adapters for OpenAI (`gpt-4o-mini`), Google Gemini, and local Ollama models.
- **Tool-Calling Pattern**: The agent interacts with the database exclusively through safe, pre-compiled, allow-listed read-only tools:
  - `get_group_balances`: Fetches real-time net balances for group members.
  - `get_spending_summary`: Aggregates category-level expenditure and contributor breakdowns.
  - `get_settlement_recommendations`: Invokes the settlement engine to produce optimal payment plans.
  - `get_audit_trail`: Fetches transaction histories and changes for verification.
- **Guardrails**: No dynamic or arbitrary SQL generation. All queries are pre-written, parameterized, and enforced with tenant isolation checks. Query metrics and prompts are persisted in `ai_query_logs`.

### 6. Persistence & Repository Layer (IBM Db2)
- **Driver**: Official native `ibm_db` Python connector.
- **Connection Management**: Connection pooling, prepared statements, and explicit transaction demarcation (`commit` / `rollback`).
- **Data Integrity**: Enforced primary keys, foreign keys with referential constraints, unique constraints on tokens and handles, and indexes on frequent lookup paths.

---

## Data Flow

### 1. Expense Ingestion & Double-Entry Ledger Posting
1. **User Request**: The user enters an expense with total amount, category, payer, and member split definitions (Equal, Exact, Percentage, or Shares) via the Next.js UI.
2. **Validation**: FastAPI validates the payload with Pydantic v2. The system verifies that `sum(splits) == total_amount` in integer paise.
3. **Transaction Demarcation**: The Db2 repository opens an explicit transaction (`autocommit = False`).
4. **Expense Record**: The master expense is inserted into `expenses`.
5. **Split Breakdown**: Individual member allocations are batch-inserted into `expense_splits`.
6. **Ledger Posting**: The Double-Entry Ledger Service writes balancing debit and credit rows to `ledger_entries` (crediting the payer account, debiting each split participant account).
7. **Audit Record**: The Audit Service logs the mutation into `audit_logs`.
8. **Commit**: The transaction is committed to Db2. If any step fails, the entire transaction rolls back cleanly.

### 2. Debt Simplification & UPI Settlement Flow
1. **Balance Aggregation**: The system calculates the net financial balance of each member from `ledger_entries`.
2. **Graph Simplification**: The Settlement Engine runs the minimum cash-flow algorithm to compute the minimal list of direct payments needed to achieve zero balances.
3. **Intent Creation**: When a debtor chooses to pay, a payment intent is created in `payment_intents` with a unique transaction reference and amount in paise.
4. **QR Generation**: The backend constructs a standard UPI payload (`upi://pay?pa=...&pn=...&am=...&tr=...`) and renders a high-contrast QR code.
5. **Confirmation & Ledger Settlement**: Upon payment confirmation (simulated demo flow or live callback), a record is inserted into `settlements`, reciprocal balancing entries are posted to `ledger_entries`, and the intent is marked completed.

### 3. Conversational AI Financial Query Flow
1. **User Prompt**: The user submits a conversational question (e.g., *"Who paid the most for food during our road trip?"*).
2. **Agent Reasoning**: The LangChain agent parses the user's intent, inspects the available tool definitions, and selects the matching analytical tool (e.g., `get_spending_summary`).
3. **Tool Execution**: The tool invokes the Db2 repository with validated group and filter parameters.
4. **Db2 Parameterized Query**: The repository runs an aggregate SQL query via `ibm_db` and returns structured records.
5. **Response Synthesis**: LangChain formats the database output into a friendly, context-aware explanation.
6. **Audit & Logging**: The user prompt, tool invoked, execution duration, and token usage are logged to `ai_query_logs`.

---

## IBM Db2 Schema & Storage Design

All monetary amounts are stored strictly as `BIGINT` representing integer paise (1 INR = 100 paise). The schema consists of 12 normalized relational tables:

```
+-----------------------------------------------------------------------------------------+
|                                     IBM Db2 Schema                                      |
+-----------------------------------------------------------------------------------------+
| 1.  APP_USERS          : User accounts, display names, emails, bcrypt password hashes   |
| 2.  GROUPS             : Shared expense groups, currency (INR), accounting mode, creator |
| 3.  GROUP_MEMBERS      : Membership mappings, permissions (ADMIN, MEMBER), join dates   |
| 4.  PAYMENT_EVENTS     : Digital payment events (DEMO/LIVE), amounts in paise, status   |
| 5.  CASH_CONTRIBUTIONS : Manually reported cash contributions (PENDING_APPROVAL status) |
| 6.  EXPENSES           : Master expense records, paid-by member, category, total paise  |
| 7.  EXPENSE_SPLITS     : Granular per-member share in paise with exact remainder preservation|
| 8.  CASH_APPROVALS     : Dual-control peer approvals/rejections with self-approval block|
| 9.  LEDGER_ENTRIES     : Double-entry balanced journal lines (CREDIT/DEBIT) in paise    |
| 10. SETTLEMENT_RUNS    : Settlement calculation snapshots, total settled amount in paise|
| 11. SETTLEMENT_ITEMS   : Min-cash-flow transfer instructions (from, to, amount in paise)|
| 12. AUDIT_EVENTS       : Immutable system audit log of all financial mutations & actors |
+-----------------------------------------------------------------------------------------+
```

### Table Definitions

1. **`APP_USERS`**
   - **Purpose**: Stores registered user identity, bcrypt salted password hashes, and account status.
   - **Key Columns**: `USER_ID` (VARCHAR(36) PK), `DISPLAY_NAME` (VARCHAR(255)), `EMAIL` (VARCHAR(255) UNIQUE), `PASSWORD_HASH` (VARCHAR(255)), `STATUS` (VARCHAR(20)), `CREATED_AT` (TIMESTAMP).

2. **`GROUPS`**
   - **Purpose**: Represents shared expense groups for trips, roommates, or events.
   - **Key Columns**: `GROUP_ID` (VARCHAR(36) PK), `NAME` (VARCHAR(255)), `DESCRIPTION` (VARCHAR(2000)), `CURRENCY` (VARCHAR(10)), `SPLIT_METHOD` (VARCHAR(20)), `ACCOUNTING_MODE` (VARCHAR(20)), `STATUS` (VARCHAR(20)), `CREATED_BY` (VARCHAR(36) FK -> APP_USERS.USER_ID), `CREATED_AT` (TIMESTAMP).

3. **`GROUP_MEMBERS`**
   - **Purpose**: Associative entity mapping users to groups with permission roles.
   - **Key Columns**: `GROUP_MEMBER_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36) FK -> GROUPS.GROUP_ID), `USER_ID` (VARCHAR(36) FK -> APP_USERS.USER_ID), `ROLE` (VARCHAR(20): `ADMIN` / `MEMBER`), `STATUS` (VARCHAR(20)), `JOINED_AT` (TIMESTAMP).

4. **`PAYMENT_EVENTS`**
   - **Purpose**: Records verified digital payments and sandbox demonstration payments.
   - **Key Columns**: `PAYMENT_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36) FK), `MEMBER_ID` (VARCHAR(36) FK), `PROVIDER` (VARCHAR(50)), `PROVIDER_TXN_ID` (VARCHAR(255)), `AMOUNT_MINOR` (BIGINT in paise), `CURRENCY` (VARCHAR(10)), `STATUS` (VARCHAR(20)), `SOURCE` (VARCHAR(10): `DEMO` / `LIVE`), `IDEMPOTENCY_KEY` (VARCHAR(255) UNIQUE), `PAID_AT` (TIMESTAMP), `CREATED_AT` (TIMESTAMP).

5. **`CASH_CONTRIBUTIONS`**
   - **Purpose**: Tracks manual cash payments awaiting independent peer approval.
   - **Key Columns**: `CASH_CONTRIBUTION_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36) FK), `MEMBER_ID` (VARCHAR(36) FK), `AMOUNT_MINOR` (BIGINT in paise), `DESCRIPTION` (VARCHAR(500)), `STATUS` (VARCHAR(20): `PENDING_APPROVAL`, `APPROVED`, `REJECTED`), `CREATED_AT` (TIMESTAMP).

6. **`EXPENSES`**
   - **Purpose**: Master table for all recorded group expenditures.
   - **Key Columns**: `EXPENSE_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36) FK), `PAID_BY_MEMBER_ID` (VARCHAR(36) FK), `AMOUNT_MINOR` (BIGINT in paise), `DESCRIPTION` (VARCHAR(500)), `CATEGORY` (VARCHAR(50)), `PAYMENT_METHOD` (VARCHAR(20): `DIGITAL` / `CASH`), `STATUS` (VARCHAR(20)), `EXPENSE_DATE` (DATE), `CREATED_AT` (TIMESTAMP).

7. **`EXPENSE_SPLITS`**
   - **Purpose**: Granular per-member share allocation for each expense with exact zero-loss math.
   - **Key Columns**: `SPLIT_ID` (VARCHAR(36) PK), `EXPENSE_ID` (VARCHAR(36) FK -> EXPENSES.EXPENSE_ID), `MEMBER_ID` (VARCHAR(36) FK -> GROUP_MEMBERS.GROUP_MEMBER_ID), `SHARE_MINOR` (BIGINT in paise).

8. **`CASH_APPROVALS`**
   - **Purpose**: Records dual-control verification decisions preventing self-approval.
   - **Key Columns**: `APPROVAL_ID` (VARCHAR(36) PK), `ENTITY_TYPE` (VARCHAR(30)), `ENTITY_ID` (VARCHAR(36)), `APPROVER_MEMBER_ID` (VARCHAR(36) FK), `DECISION` (VARCHAR(20): `APPROVED` / `REJECTED`), `COMMENT` (VARCHAR(500)), `DECIDED_AT` (TIMESTAMP).

9. **`LEDGER_ENTRIES`**
   - **Purpose**: Double-entry journal entries ensuring mathematical reconcilability across all financial operations.
   - **Key Columns**: `LEDGER_ENTRY_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36) FK), `MEMBER_ID` (VARCHAR(36) FK), `ENTITY_TYPE` (VARCHAR(30)), `ENTITY_ID` (VARCHAR(36)), `ENTRY_TYPE` (VARCHAR(10): `CREDIT` / `DEBIT`), `AMOUNT_MINOR` (BIGINT in paise), `CURRENCY` (VARCHAR(10)), `STATUS` (VARCHAR(20)), `CREATED_AT` (TIMESTAMP).

10. **`SETTLEMENT_RUNS`**
    - **Purpose**: Snapshot records of deterministic debt simplification calculations.
    - **Key Columns**: `RUN_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36) FK), `TOTAL_MINOR` (BIGINT in paise), `CURRENCY` (VARCHAR(10)), `STATUS` (VARCHAR(20)), `CALCULATED_AT` (TIMESTAMP), `CALCULATED_BY` (VARCHAR(36) FK).

11. **`SETTLEMENT_ITEMS`**
    - **Purpose**: Individual recommended peer-to-peer settlement transfers.
    - **Key Columns**: `ITEM_ID` (VARCHAR(36) PK), `RUN_ID` (VARCHAR(36) FK -> SETTLEMENT_RUNS.RUN_ID), `FROM_MEMBER_ID` (VARCHAR(36) FK), `TO_MEMBER_ID` (VARCHAR(36) FK), `AMOUNT_MINOR` (BIGINT in paise), `STATUS` (VARCHAR(20): `RECOMMENDED` / `SETTLED`).

12. **`AUDIT_EVENTS`**
    - **Purpose**: Immutable append-only audit trail capturing all domain state mutations.
    - **Key Columns**: `EVENT_ID` (VARCHAR(36) PK), `GROUP_ID` (VARCHAR(36)), `ACTOR_ID` (VARCHAR(36)), `EVENT_TYPE` (VARCHAR(50)), `ENTITY_TYPE` (VARCHAR(50)), `ENTITY_ID` (VARCHAR(36)), `DETAILS_JSON` (VARCHAR(4000)), `CREATED_AT` (TIMESTAMP).

---

## Security & Secrets Management

- **Environment Isolation**: All database passwords, JWT signing keys, and external AI provider keys are loaded at runtime from environment variables using `pydantic-settings`. No plaintext secrets exist in source code or configuration files.
- **Git Protection**: Strict `.gitignore` rules prevent `.env`, local certificates, and credential files from being tracked in version control.
- **SQL Injection Prevention**: All queries to IBM Db2 are strictly executed using parameterized prepared statements via `ibm_db.prepare()` and `ibm_db.execute()`. No string interpolation is permitted in SQL strings.
- **Cryptographic Standards**: User passwords are encrypted with bcrypt (12 salt rounds). Authentication tokens are signed with HMAC-SHA256 (`HS256`) and enforced with configurable expiration windows.
- **AI Sandboxing**: The LangChain assistant operates within a closed execution sandbox. It possesses no direct DDL/DML capabilities and can only invoke pre-defined, read-only analytical functions that enforce user session tenancy.
- **Financial Precision Integrity**: The application mandates integer arithmetic for all currency operations, preventing rounding exploitation, precision leakage, or truncation errors common in floating-point accounting systems.
