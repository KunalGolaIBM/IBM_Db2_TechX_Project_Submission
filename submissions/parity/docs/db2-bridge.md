# Db2 bridge

## Why

The Windows `ibm_db` driver fails with `SQL1042C` against a healthy Db2 server. See `docs/db-executors.md`. Parity already needs Docker for the databases, so the Db2 driver runs in a Linux container instead.

## How it works

- `Dockerfile.bridge` builds a Linux image named `parity-bridge` with Python, `ibm_db`, `psycopg`, and Parity source.
- `src/parity/bridge_client.py` runs inside that container. It reads one SQL statement from stdin, runs it on Db2, and writes JSON to stdout.
- `src/parity/engine/db2_bridge.py` is `Db2BridgeExecutor`. It runs `docker run` with the bridge image, sends SQL on stdin, and reads the JSON result.

The bridge executor uses the same safety guard and row limit as the direct executor. It adds `--add-host=host.docker.internal:host-gateway` so the container can reach Db2 on the host.

## Build

```bash
docker build -f Dockerfile.bridge -t parity-bridge .
```

## Usage

```python
from parity.config import load_settings
from parity.engine.db2_bridge import Db2BridgeExecutor

_, db2_settings = load_settings()
executor = Db2BridgeExecutor(db2_settings)
result = executor.execute('SELECT "ID" FROM "DEMO_USERS"')
```

Set `PARITY_DB2_HOST=host.docker.internal` when Db2 runs on the host and the driver runs in the bridge container.

## Note on admin operations

Schema sync DDL and inserts use `Db2Admin` with the direct driver. On Windows those also need a Linux environment. The live sync test runs the whole sync script inside the bridge container, where the driver works natively. A remote admin bridge is planned if needed.
