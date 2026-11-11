# Db2 trusted context: each API request runs as its API user

With `ASOF_AUTH=users`, every `/api/` request carries a personal token ([users.py](../src/asof/users.py)). Without a trusted context, Db2 still sees one account for all of them: the runtime user `asofapp`. With `ASOF_TRUSTED_CONTEXT=true` (off by default), the API's runtime connections are Db2 trusted connections, and each request switches its connection's session user to the API user's own Db2 ID, without a password. Then:

- `SESSION_USER`, and so `STORED_BY` in the ledger ([13_trusted_context.sql](../src/asof/sql/13_trusted_context.sql)), is the person who asked, with `STORED_CONTEXT = ASOF_API_CONTEXT`.
- Db2 checks that person's privileges, not the service account's: an auditor's session that tries to append to the ledger is refused by Db2 (`42501`), whatever the application does.

## Where the requester is recorded

[13_trusted_context.sql](../src/asof/sql/13_trusted_context.sql) adds three `ANSWER_LEDGER` columns and a `BEFORE INSERT` trigger (`SECURED`, as the column masks require) that fills them on every insert, whatever the `INSERT` named, so no caller can supply them:

- `STORED_BY`: `SESSION_USER`. With the setting on, the API user's ID; off, the runtime user (or the reviewer user for a specialist's reply). `CURRENT USER` would not do: inside `APPEND_LEDGER` it is the procedure's owner.
- `STORED_ROLES`: the roles `VERIFY_ROLE_FOR_USER` finds for `SESSION_USER`, plus the trusted context's role, read from `MON_GET_CONNECTION` (`TRUSTED_CTX_ROLE`).
- `STORED_CONTEXT`: the trusted context the connection matched, or `NULL`.

They are recorded, not hashed: `APPEND_LEDGER_ROW` and the row hash are unchanged, so `VERIFY_CHAIN` does not cover them; the append-only triggers and the grants protect them. The columns come from an `ALTER`, so an existing ledger gets them with its rows and hashes untouched (older rows read `NULL`). Adding a column marks the table's column masks and row permissions invalid (`SQL5188N` on any later statement that reads them, `CREATE PROCEDURE` included), so `schema.install()` recreates every invalid mask and permission right after such a statement. The trigger costs about 0.06 ms per insert (5,000 inserts: 0.39 s without it, 0.68 s with it). The ledger detail (`GET /api/ledger/{id}` and its page) shows them as `stored_by`.

Code: [trusted.py](../src/asof/trusted.py) (context, roles, user list), [db.py](../src/asof/db.py) (`ConnectionPool(trusted=True)`, `switch_user`), [api.py](../src/asof/api.py) (the middleware hands each authenticated request's ID to the pool through a context variable). Tests: [test_trusted.py](../tests/test_trusted.py) (no database) and [test_db2_trusted.py](../tests/test_db2_trusted.py) (Db2).

## Turning it on

```bash
# .env
ASOF_AUTH=users
ASOF_TRUSTED_CONTEXT=true
ASOF_TRUSTED_CONTEXT_ADDRESS=      # empty: the address Db2 sees for setup's own connection
python -m asof.setup               # creates ASOF_API_CONTEXT and its roles; prints the address and the users
python -m asof.users add maria --roles checker,auditor   # also adds API_MARIA to the context's list
```

`python -m asof.users add` and `disable` keep the context's list and each ID's roles in step with `ASOF.API_USER`; setup does the same on every run, and drops the context when the setting is false.

## What Db2 holds

| Object | What it is |
|---|---|
| `ASOF_API_CONTEXT` | `BASED UPON CONNECTION USING SYSTEM AUTHID ASOFAPP ATTRIBUTES (ADDRESS '<address>') DEFAULT ROLE ASOF_API_SESSION ENABLE`, then one `ADD USE FOR API_<NAME> WITHOUT AUTHENTICATION` per active API user. Never `WITH USE FOR PUBLIC`: that would let the runtime user's connections switch to any ID without a password, the owner's included. |
| `API_<NAME>` | An API user's Db2 ID: `API_`, the name upper case, `.` and `-` as `_` (`maria.lopez` is `API_MARIA_LOPEZ`). The prefix keeps an API user named `db2inst1` from mapping to the owner. Two names that map to one ID are refused. The IDs need no password and no operating-system account: they exist only as grantees and as names on the context's list. |
| `ASOF_API_SESSION` | The context's default role, in force only inside a connection that matched the context. `CONNECT`, plus what the runtime user holds in the AsOf schema, mirrored from the catalog at every sync (so it follows `90_grants.sql`), minus the three procedures that write the ledger, suggestions and notices: `APPEND_LEDGER`, `ADD_SUGGESTION`, `ADD_NOTICE`. The runtime user's other procedures (the demo's spend counter and the backtest's) stay in this role. |
| `ASOF_API_CHECKER`, `ASOF_API_EDITOR`, `ASOF_API_REVIEWER` | Granted to an ID by its API roles: `EXECUTE` on `APPEND_LEDGER`; plus `ADD_SUGGESTION` for editors; plus `ADD_NOTICE` for reviewers. Auditors get none. |
| `ASOF_TEXT_READER`, `ASOF_ALL_DOMAINS` | Granted to every API user's ID directly, as setup grants them to the runtime user. The column masks, `VERIFY_CHAIN` and the domain row permissions ([06_domain_permissions.sql](../src/asof/sql/06_domain_permissions.sql)) ask `VERIFY_ROLE_FOR_USER(SESSION_USER, ...)`, which does not see a trusted context's role. Those permissions are evaluated for the switched ID: one holding only `ASOF_DOMAIN_BANK` sees only the bank's decisions and is refused an airline append (tested). Setup does not yet scope API users to a domain: each gets all domains, as the runtime user has. |

The policy editor, reviewer, analyst and dbt users keep their own service accounts: only the runtime user's pooled connections switch. One AsOf schema per database uses the context (it is database-wide; the last sync's schema decides the list).

## What the spike found (Db2 12.1.5.0, IBM's stock image)

Run against IBM's unmodified `icr.io/db2_community/db2:12.1.5.0` on x86 Linux, reached through an SSH tunnel and then Docker's port mapping.

- **The DDL works as written.** `CREATE TRUSTED CONTEXT ... BASED UPON CONNECTION USING SYSTEM AUTHID ASOFAPP ATTRIBUTES (ADDRESS '172.17.0.1') DEFAULT ROLE ... ENABLE WITH USE FOR ... WITHOUT AUTHENTICATION`, `ALTER TRUSTED CONTEXT ... ADD USE FOR` / `DROP USE FOR`, all as the owner (who holds SECADM).
- **ibm_db does it.** `ibm_db_dbi.connect(dsn, user, password, conn_options={SQL_ATTR_USE_TRUSTED_CONTEXT: SQL_TRUE})`, then `ibm_db.set_option(conn.conn_handler, {SQL_ATTR_TRUSTED_CONTEXT_USERID: "API_MARIA"}, 1)` between transactions. Db2 performs the switch at the next statement. After it, `SESSION_USER`, `SYSTEM_USER` and `CURRENT USER` all read `API_MARIA`.
- **The address Db2 sees.** Through Docker's port mapping, the client address is the bridge gateway (`172.17.0.1` here, read from `MON_GET_CONNECTION`'s `CLIENT_IPADDR`), not `127.0.0.1`. That is why setup takes the address Db2 reports for its own connection. It also means the `ADDRESS` attribute only narrows things to "something on the Docker host": the runtime user's password is still what authenticates the connection.
- **Switched IDs need no operating-system user.** `MARIA`, `MARIA.LOPEZ` and `API_MARIA-L` (delimited) all switched without existing on the OS. Without `CONNECT` they are refused: `SQL1060N User "MARIA" does not have the CONNECT privilege`. The context's role supplies it.
- **IDs not on the list are refused,** the owner included: `SQL20361N The switch user request using authorization ID "DB2INST1" within trusted context "ASOF_SPIKE_CTX" failed with reason code "1"` (SQLSTATE `42517`). The connection is unusable afterwards (`SQL0900N`, `08003`), so the pool closes it.
- **A switch resets the session.** `CURRENT SCHEMA` and `CURRENT PATH` become the new user's, and `CURRENT LOCK TIMEOUT` goes back to `-1` (wait forever). `switch_user` sets the lock timeout again and makes `use_schema` set the schema again.
- **The context's role is invisible to `VERIFY_ROLE_FOR_USER`.** For a switched user holding `ASOF_SPIKE_ROLE` only through the context, `VERIFY_ROLE_FOR_USER(SESSION_USER, 'ASOF_SPIKE_ROLE')` is `0`, although the role's privileges apply (its `SELECT` and `EXECUTE` worked). Hence `ASOF_TEXT_READER` granted to the IDs directly, and `STORED_ROLES` reading the context's role from `MON_GET_CONNECTION` (`TRUSTED_CTX_ROLE`).
- **Implicit trusted connections.** Once the context exists, every plain connection as `asofapp` from that address is an implicit trusted connection with the context's default role (`TRUSTED_CONN_TYPE = IMPLICIT`). That is why `ASOF_API_SESSION` holds nothing the runtime user does not already hold.
- **Cost.** `switch_user` (the switch, the `SESSION_USER` check, the lock timeout) took 274 ms median against 70 ms for a plain query over this tunnel: about four round trips. The pool switches on every checkout made for a user, even to the ID the connection already runs as, so Db2 checks the context's list on every request (a disabled user is refused at once), and a check makes two to six checkouts. That cost, which a local Db2 makes much smaller but which was not measured here, is one reason the setting is off by default.

## The pool

`ConnectionPool(trusted=True)` opens trusted connections and remembers which ID each one runs as. A checkout reads the request's ID from `db.SESSION_USER` (a context variable the API sets after authenticating the token, and resets when the request ends). With an ID, it switches; without one (the token lookup itself, `/healthz`), it switches back to the runtime user only if the connection runs as someone else. A refused switch closes that connection and fails the request (`503`), and its pool slot is freed. Sync routes run in a worker thread; the context variable reaches them (tested through the real middleware).

## Limits

- Only the runtime user's connections switch; editor, reviewer, analyst and dbt work still runs as those service accounts.
- `STORED_BY` is outside `ROW_HASH`; see [schema.md](schema.md).
- With `WITHOUT AUTHENTICATION`, Db2 trusts the application to have authenticated the person: the token check in [api.py](../src/asof/api.py) is what proves who it is. Db2 adds that only listed IDs can be used, only from the context's address and only on a connection authenticated as the runtime user, and that each ID gets only its own privileges.
- Not tested under Rosetta on Apple Silicon.
