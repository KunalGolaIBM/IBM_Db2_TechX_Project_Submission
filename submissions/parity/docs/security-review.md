# Security review

## SQL injection

Every insert, update, and delete uses bound parameters (`ibm_db.bind_param`). User data never sits inside SQL text. The only formatted SQL in the codebase is DDL with quoted identifiers that come from schema introspection, plus the vetted vector literals in the knowledge base store (built from validated floats only).

## Credentials

No secret has a default value in the config loader. Missing values fail with a clear error. The dev passwords in `docker-compose.yml` are disposable test credentials for local containers only. `.env` files are blocked by `.gitignore`.

## Source safety

Only SELECT statements run against the source database. The safety guard rejects write statements before they reach the database. Postgres is used as read only. All mutation happens on the disposable Db2 test schema.

## Prompt data

Prompts hold only SQL text, schema names, and synthetic fuzz values. Production rows are never sent to a model. This is enforced by construction: the gateway only ever receives system and user text built from SQL, never from result rows.

## Container isolation

Parity runs against disposable Docker containers. Db2 needs privileged mode for its startup script, which is a documented requirement of the image. Teardown leaves no containers behind.

## Verdict

No critical or high findings open. The sign-off covers the V1 surface: engine, executors, sync, gateway, knowledge base, and CLI.
