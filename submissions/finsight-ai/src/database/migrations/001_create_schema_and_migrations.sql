-- ==============================================================================
-- Migration: 001_create_schema_and_migrations.sql
-- Description: Establishes the migration tracking table in FINSIGHT schema.
-- ==============================================================================

-- Migration history table (Db2 automatically manages schema authorization)
CREATE TABLE FINSIGHT.SCHEMA_MIGRATIONS (
    migration_id VARCHAR(100) NOT NULL PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    checksum VARCHAR(64)
);
