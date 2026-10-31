# Architecture Design: dbhaven for IBM Db2

## Executive Summary

`dbhaven` is a high-performance, resilient database backup and disaster recovery daemon engineered for enterprise database infrastructure. By integrating native IBM Db2 LUW backup and recovery capabilities, `dbhaven` enables automated, non-blocking online database backups, authenticated streaming encryption via AES-256-GCM, automated replication to local and S3-compatible cloud storage, and Grandfather-Father-Son (GFS) archival retention.

---

## 1. Architectural Overview & Component Pipeline

The core pipeline operates on a streaming, zero-disk-footprint model where raw database dumps are compressed, encrypted, and uploaded directly to multi-tier destinations in real time without storing unencrypted intermediate files on disk.

```
┌─────────────────┐
│   IBM Db2 12+   │ (Docker / Cloud / On-Premise)
│   (SAMPLE DB)   │
└────────┬────────┘
         │
         │  1. `db2 backup database ... online to -` / `ibm_db` snapshot
         ▼
┌─────────────────┐
│   Dump Engine   │  Native Dumper interface translating DSNs & managing process I/O
└────────┬────────┘
         │
         │  2. Raw stdout stream pipe
         ▼
┌─────────────────┐
│ Stream Crypto   │  Chunked AES-256-GCM authenticated cipher with 12-byte IVs
│  (AES-256-GCM)  │  and 16-byte HMAC integrity tags per 64KB block
└────────┬────────┘
         │
         │  3. Encrypted ciphertext stream
         ▼
┌─────────────────┐
│ Storage Router  │  Multi-destination fanout (Concurrent S3 multipart & local disk)
└────────┬────────┘
         │
         ├─────────────────────────────────────────┐
         ▼                                         ▼
┌─────────────────┐                       ┌─────────────────┐
│ Local Disk Store│                       │ S3 Cloud Store  │
│ (/var/backups/) │                       │ (AWS / MinIO)   │
└────────┬────────┘                       └────────┬────────┘
         │                                         │
         └────────────────────┬────────────────────┘
                              │
                              │  4. Automated GFS Pruning
                              ▼
                     ┌─────────────────┐
                     │ Retention Engine│  (Daily 7, Weekly 4, Monthly 12)
                     └─────────────────┘
```

---

## 2. Technical Component Breakdown

### 2.1 IBM Db2 Dumper Module (`internal/dump/db2.go`)
- **DSN Protocol:** Uses URI scheme `db2://user:password@host:port/dbname`.
- **Online Hot Backups:** Invokes non-blocking online hot backups using `db2 backup database <dbname> online to -`. Applications continue executing read/write transactions without table locks or latency degradation.
- **Table Space Granularity:** Supports optional parameters (e.g., `TABLESPACE (USERSPACE1)`) passed via `extra_args` in configuration.
- **Dry-Run Previews:** `DumpArgs()` generates exact executable argv vectors, allowing database administrators to audit and verify execution plans prior to running backups.

### 2.2 Streaming Encryption Engine (`internal/crypto/`)
- **Cipher:** AES-256 in Galois/Counter Mode (GCM).
- **Chunking Model:** Streams large databases in 64 KiB chunks. Each chunk contains an independent 12-byte cryptographic nonce and 16-byte Poly1305/GHASH tag.
- **Tamper Resistance:** Detects any silent corruption, bit flips, or in-flight tampering. If an attacker modifies even 1 bit of an S3 object, decompression fails immediately before touching the database restore subsystem.
- **Key Hierarchy:** Supports secure 256-bit key loading via restricted POSIX/Windows key files or encrypted environment variables (`DBHAVEN_KEY`).

### 2.3 Storage Backends (`internal/store/`)
- **Local Filesystem:** Atomic writing with atomic sync (`fsync`) and checksum metadata files.
- **S3 / Object Storage:** Built using the high-performance MinIO/AWS Go SDK with chunked streaming multipart upload. Backups stream directly across TLS 1.3 to AWS S3, Cloudflare R2, MinIO, or Google Cloud Storage.

### 2.4 Retention Engine (`internal/retention/`)
- **Grandfather-Father-Son (GFS):**
  - **Daily:** Retains 7 daily snapshots.
  - **Weekly:** Retains 4 weekly snapshots (captured at end of week).
  - **Monthly:** Retains 12 monthly archival snapshots.
- **Simple Mode (`keep_last: N`):** Maintains a fixed sliding window of the most recent N backup archives.

---

## 3. Disaster Recovery & Restoration Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Admin as DB Administrator / SRE
    participant CLI as dbhaven CLI
    participant S3 as S3 / Local Storage
    participant Crypto as AES-256-GCM Engine
    participant Db2 as IBM Db2 Database

    Admin->>CLI: dbhaven restore --job enterprise-db2 --file backup.dump.enc --yes
    CLI->>S3: Stream encrypted backup archive
    S3-->>Crypto: Ciphertext chunks + Auth Tags
    Crypto->>Crypto: Verify GCM auth tags & decrypt in-memory
    Crypto-->>CLI: Plaintext Db2 backup stream
    CLI->>Db2: db2 restore database SAMPLE from - without prompting
    Db2->>Db2: Rollforward recovery & rebuild tablespaces
    Db2-->>CLI: Recovery Complete (Status: SQL0000W / 0)
    CLI-->>Admin: Database successfully restored & verified
```

---

## 4. Threat Model & Security Posture

| Threat Vector | Mitigation Strategy |
|---|---|
| **Eavesdropping on Backup Transit** | AES-256-GCM authenticated encryption applied before leaving process space + TLS 1.3 transport. |
| **Storage Breach / S3 Leaks** | S3 stores only encrypted binary blobs (`.dump.enc`). Without the master key, ciphertext is indistinguishable from random noise. |
| **Ransomware / Bit Rot Corruption** | GCM authentication tags validate the cryptographic integrity of every 64KB block; corrupted blocks trigger immediate termination. |
| **Credential Exposure in Process Table** | Credentials are parsed into internal memory descriptors and never exposed in plain command-line flags. |
