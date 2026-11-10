# Bridge admin

## What it does

The Windows ibm_db driver cannot reach a Db2 server. That blocked every write from the host, so the knowledge base review command could not run on Windows.

`Db2BridgeAdmin` sends the statement and its parameters to the bridge container. The container binds the parameters with the driver and runs the statement. The values never become part of the SQL text, so the same rule holds as for the direct client: user data is never SQL.

## What it unlocks

- `parity kb-review --store db2` now works on the host.
- The knowledge base can be written from a host run.
- The run history and the gateway cache can use the same client.

## The two clients

Both clients give the same three methods: `execute`, `execute_ddl`, and `insert_rows`.

- `Db2Admin` connects with the driver. It works on Linux and inside the bridge container.
- `Db2BridgeAdmin` sends the work to the bridge container. It works on any machine with Docker.

The bridge protocol accepts two forms on standard input. Plain SQL text runs a statement without parameters. A JSON envelope with `sql` and `params` runs a statement with bound parameters.

## Known limits

Every statement starts a new container, so a batch of statements is slower than a direct connection. The bridge is for the write path, not for a hot loop.
