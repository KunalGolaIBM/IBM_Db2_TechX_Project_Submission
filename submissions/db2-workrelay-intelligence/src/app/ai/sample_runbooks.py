from __future__ import annotations
from typing import Any

SAMPLE_RUNBOOKS: list[dict[str, Any]] = [
    {
        "doc_id": "RUNBOOK-DB2-001",
        "title": "IBM Db2 Connection Pool Exhaustion Mitigation",
        "category": "database",
        "service": "database",
        "content": (
            "Symptoms: Application threads block when attempting to borrow connection from pool. "
            "Exceptions show Db2 connection timeout or SQL30081N communication failure. "
            "Root causes: Connection leaks in legacy batch jobs, sudden spike in API traffic without pool scaling."
        ),
        "resolution_steps": (
            "1. Run snapshot monitor: db2 get snapshot for database on testdb to inspect current connections. "
            "2. Identify idle locked threads with db2 list applications. "
            "3. Gracefully force hanging connections or recycle connection pool. "
            "4. Tune maxPoolSize from default 20 to 50 in application environment."
        ),
        "metadata": {"severity_level": "HIGH", "author": "SRE Team"},
    },
    {
        "doc_id": "RUNBOOK-DB2-002",
        "title": "IBM Db2 Transaction Log Full (SQL0964C)",
        "category": "database",
        "service": "database",
        "content": (
            "Symptoms: DML queries fail with SQL0964C: The transaction log for the database is full. "
            "Root causes: Long-running uncommitted transactions, mass DELETE/UPDATE operations without intermediate commits."
        ),
        "resolution_steps": (
            "1. Inspect active transactions using db2pd -db testdb -trans. "
            "2. Identify application holding oldest transaction and commit or rollback. "
            "3. If needed, temporarily increase log file size: db2 update db cfg for testdb using LOGFILSIZ 8192. "
            "4. Enable archive logging or add secondary logs with LOGSECOND."
        ),
        "metadata": {"severity_level": "CRITICAL", "author": "Database Engineering"},
    },
    {
        "doc_id": "RUNBOOK-SVC-001",
        "title": "High 5xx Error Rate in Payment & Checkout Service",
        "category": "microservice",
        "service": "payment-api",
        "content": (
            "Symptoms: Ingress controller reports > 5% HTTP 502/504 errors on /checkout endpoint. "
            "Root causes: Upstream gateway timeout, database locking on order state transitions."
        ),
        "resolution_steps": (
            "1. Check pod CPU/memory utilization and restart crash-looping replicas. "
            "2. Inspect Db2 lock waits with db2pd -locks. "
            "3. Activate circuit breaker on third-party payment gateways. "
            "4. Roll back recent canary deployment if regression observed."
        ),
        "metadata": {"severity_level": "CRITICAL", "author": "Payment Pod"},
    },
    {
        "doc_id": "RUNBOOK-AUTH-001",
        "title": "Authentication Service JWT Verification Failures",
        "category": "security",
        "service": "auth-service",
        "content": (
            "Symptoms: Valid user tokens rejected with 401 Unauthorized. "
            "Root causes: Public key rotation desynchronization, JWKS endpoint caching timeout."
        ),
        "resolution_steps": (
            "1. Flush local JWKS cache in auth-service container. "
            "2. Verify NTP clock synchronization across cluster nodes. "
            "3. Force refresh of public signing keys from identity provider."
        ),
        "metadata": {"severity_level": "HIGH", "author": "Security Engineering"},
    },
]
