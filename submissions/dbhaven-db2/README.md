# dbhaven for IBM Db2: Enterprise Encrypted Backups & Disaster Recovery

[![Go Version](https://img.shields.io/badge/go-1.24%2B-blue.svg)](https://golang.org)
[![IBM Db2](https://img.shields.io/badge/IBM%20Db2-12.1%2B%20LUW-052FAD.svg)](https://www.ibm.com/products/db2)
[![AES-256-GCM](https://img.shields.io/badge/Security-AES--256--GCM-green.svg)](https://en.wikipedia.org/wiki/Galois/Counter_Mode)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**dbhaven** is a production-grade, scheduled, encrypted database backup and disaster recovery engine. It provides automated online hot backups for **IBM Db2**, streaming end-to-end authenticated **AES-256-GCM** encryption, multi-cloud and local storage replication, and automated **Grandfather-Father-Son (GFS)** archival lifecycle management.

---

## Key Features for IBM Db2

- 🚀 **Online Hot Backups:** Non-blocking backups (`db2 backup database ... online`) that allow active transactions without downtime or performance degradation.
- 🔐 **Military-Grade Encryption:** Streams database images through chunked AES-256-GCM authenticated encryption with independent nonces and 16-byte HMAC verification tags per 64KB block.
- ☁️ **Direct Cloud Streaming:** Zero intermediate disk footprint — streams compressed and encrypted archives directly to AWS S3, Cloudflare R2, MinIO, or local disk.
- 🗓️ **Automated Scheduling Daemon:** Built-in standard 5-field cron daemon with structured `slog` logging and dry-run preview capabilities.
- 🗑️ **Grandfather-Father-Son (GFS) Retention:** Automatically prunes daily, weekly, and monthly snapshots to enforce compliance and optimize storage costs.
- ♻️ **Single-Command Disaster Recovery:** Decrypts, verifies cryptographic checksums, and restores database state with one command: `dbhaven restore`.

---

## Directory Structure

```text
submissions/dbhaven-db2/
├── .env.example              # Sample environment configuration
├── README.md                 # Complete project documentation and guide
├── architecture.md           # System architecture, sequence diagrams, and threat model
├── submission.json           # Summit project metadata and participant info
├── src/                      # Complete source code implementation
│   ├── cmd/dbhaven/          # CLI entry points (backup, restore, schedule, keygen)
│   ├── internal/config/      # YAML configuration loader & validator (with Db2 support)
│   ├── internal/crypto/      # Chunked AES-256-GCM streaming encryption engine
│   ├── internal/dump/        # Native database connectors (IBM Db2, Postgres, MySQL, Mongo)
│   ├── internal/retention/   # GFS and keep-last retention pruning engine
│   ├── internal/runner/      # Backup execution orchestrator
│   ├── internal/scheduler/   # Cron scheduling daemon
│   ├── internal/store/       # Local and S3 cloud storage drivers
│   ├── python_client/        # Python ibm_db backup & integrity verification CLI
│   └── docker-compose.yml    # Rapid Db2 Community Edition sandbox
└── tests/                    # Comprehensive unit and integration test suite
    ├── config_test.py        # Python configuration validation test
    └── verify_db2_test.py    # Db2 DSN and backup command verification test
```

---

## Quickstart Guide

### 1. Generate an AES-256 Master Key
```bash
dbhaven keygen --out ~/.dbhaven-key
```

### 2. Configure `dbhaven.yaml` for IBM Db2
Create your configuration file with your IBM Db2 connection string:
```yaml
encryption:
  key_file: /etc/dbhaven/key

jobs:
  - name: enterprise-db2
    type: db2
    dsn: "db2://db2inst1:db2pwd123@127.0.0.1:50000/SAMPLE"
    schedule: "0 2 * * *"          # Runs nightly at 02:00
    destinations:
      - type: local
        path: /var/backups/dbhaven/db2
      - type: s3
        endpoint: s3.amazonaws.com
        bucket: dbhaven-db2-archives
        prefix: enterprise/
        region: us-east-1
        access_key: YOUR_AWS_KEY
        secret_key: YOUR_AWS_SECRET
        use_ssl: true
    retention:
      daily: 7
      weekly: 4
      monthly: 12
    extra_args: ["online"]
```

### 3. Dry-Run Verification
Preview what commands `dbhaven` will execute against IBM Db2 without modifying data:
```bash
dbhaven backup --config dbhaven.yaml --job enterprise-db2 --dry-run
```

### 4. Execute Backup Once
```bash
dbhaven backup --config dbhaven.yaml --job enterprise-db2
```

### 5. Launch Automated Backup Daemon
```bash
dbhaven schedule --config dbhaven.yaml
```

### 6. One-Command Disaster Recovery
```bash
dbhaven restore --config dbhaven.yaml --job enterprise-db2 \
  --file enterprise-db2-db2-20261031-020000.dump.enc \
  --target "db2://db2inst1:db2pwd123@127.0.0.1:50000/SAMPLE" --yes
```

---

## IBM Db2 Python Client & Verification CLI

In addition to the high-performance Go daemon, `src/python_client/db2_backup_helper.py` provides Python integration utilizing the official `ibm_db` and `SQLAlchemy` connectors:

```bash
# Verify Db2 connectivity and database health
python src/python_client/db2_backup_helper.py health-check --dsn "db2://db2inst1:password@127.0.0.1:50000/SAMPLE"

# Trigger hot backup with integrity verification
python src/python_client/db2_backup_helper.py backup --database SAMPLE --out-dir ./backups
```

---

## Verification & Testing

To validate the submission files against the official IBM Db2 TechX validator:
```bash
python scripts/validate_submission.py submissions/dbhaven-db2
```

To run offline unit and integration tests:
```bash
python submissions/dbhaven-db2/tests/verify_db2_test.py
```

---

## License

Licensed under the Apache License, Version 2.0.
