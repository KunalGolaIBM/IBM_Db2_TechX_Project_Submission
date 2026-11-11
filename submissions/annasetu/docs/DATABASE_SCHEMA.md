# Db2 schema and integrity rules

The application owns its operational data in IBM Db2. FastAPI connects directly through `ibm_db_dbi`; SQL uses positional parameter markers (`?`). `initialize_schema()` creates missing objects and tolerates existing Db2 objects; it does not drop tables or clear data. LangChain `DB2VS` maintains the `ANNA_POLICY_VECTOR` vector table in the same database.

## Tables

| Table | Key fields and purpose |
|---|---|
| `USERS` | `USER_ID` primary key; unique `EMAIL`; `DISPLAY_NAME`, role (`donor`, `ngo`, `volunteer`, `admin`), salted password hash and creation time. |
| `NGOS` | `NGO_ID`; owning user; name; verification and active flags; non-negative available kg; accepted categories; storage capabilities; coordinates and receiving hours. |
| `VOLUNTEERS` | `VOLUNTEER_ID`; unique user assignment; service area and active flag. |
| `FOOD_BATCHES` | `BATCH_ID`; donor; title/category/quantity; preparation and use-by timestamps; storage mode and temperature; allergen declaration/confirmation; ingredients; pickup address/coordinates; human review and workflow status. Use-by must be later than preparation; quantity must be positive. |
| `SAFETY_OBSERVATIONS` | Immutable `OBSERVATION_ID`; batch, recording user, optional temperature, storage note and observed timestamp. New measurements are new rows. |
| `HUMAN_VERIFICATIONS` | Immutable `VERIFICATION_ID`; batch, verifier, decision (`verified`, `hold`, `rejected`), notes and timestamp. |
| `RESCUES` | `RESCUE_ID`; batch, NGO, volunteer, positive allocated kg, workflow status, three OTP hashes and pickup/delivery/distribution timestamps. |
| `AUDIT_HEAD` | Single locked row identifying the latest audit event and chain hash. Serializes audit append operations. |
| `AUDIT_EVENTS` | Identity event ID, entity/actor, event type/data, previous hash, event hash and timestamp. Unique event hash. Actual distributed kg is recorded in the distribution event payload; the existing table schema is unchanged. |
| `POLICY_DOCUMENTS` | `DOCUMENT_ID`, title, official source URL, passage content, active flag and creation time; source corpus for retrieval. |
| `ANNA_POLICY_VECTOR` | LangChain Db2 vector index populated from active policy documents. Uses Db2 vector search; not a separate operational database. |

## Relationships and constraints

- NGO and volunteer profiles reference their owner/user. Food references a donor and optional verifier. Observations and verifications reference food and actor. Rescues reference food, NGO and volunteer. Audit events reference actors.
- Db2 check constraints restrict roles, storage types, lifecycle states, positive food/rescue quantities, non-negative capacity, boolean flags, and preparation/use-by ordering.
- Indexes support food status/use-by lookup, NGO rescue status, and entity audit history.
- Db2 triggers reject both `UPDATE` and `DELETE` on `AUDIT_EVENTS`, `SAFETY_OBSERVATIONS`, and `HUMAN_VERIFICATIONS` with SQLSTATE `75001`. Corrections are recorded by appending a new event or observation.

## Transaction boundaries

1. Food creation inserts the batch, first safety observation and audit event together.
2. Evidence changes append a safety observation, reset the batch's review state, append audit history and commit together.
3. Human review inserts an immutable verification record, updates the current batch review pointer/status, and appends its event in one transaction.
4. Allocation conditionally decrements receiver capacity (`AVAILABLE_KG >= requested`), inserts rescue rows and audit events, updates batch state, then commits. Exceptions roll back the reservation and rescue rows.
5. OTP checkpoints update rescue state/timestamp, recalculate batch status, append an audit event, and commit together. The NGO distribution checkpoint requires a positive actual quantity no greater than allocated kg; that amount is hashed into the append-only event and used in dashboard aggregates.
6. Rescue failure marks it failed, restores its reserved capacity, records the failure event, recalculates batch state, and commits together.

The hash chain detects audit tampering; the triggers enforce append-only behavior at the database layer. OTP plaintext is not persisted. The database stores salted PBKDF2 password hashes, never plaintext passwords.
