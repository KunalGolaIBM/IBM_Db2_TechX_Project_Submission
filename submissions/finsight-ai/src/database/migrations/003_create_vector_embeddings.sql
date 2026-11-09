-- ==============================================================================
-- Migration: 003_create_vector_embeddings.sql
-- Description: Creates TRANSACTION_EMBEDDINGS table using native Db2 12.1 VECTOR(384, FLOAT32).
-- ==============================================================================

CREATE TABLE FINSIGHT.TRANSACTION_EMBEDDINGS (
    embedding_id VARCHAR(36) NOT NULL PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    transaction_id VARCHAR(36) NOT NULL,
    content CLOB(10000) NOT NULL,
    embedding VECTOR(384, FLOAT32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT FK_VEC_USER FOREIGN KEY (user_id) REFERENCES FINSIGHT.USERS(user_id) ON DELETE CASCADE,
    CONSTRAINT FK_VEC_TX FOREIGN KEY (transaction_id) REFERENCES FINSIGHT.TRANSACTIONS(transaction_id) ON DELETE CASCADE
);

CREATE INDEX FINSIGHT.IDX_VEC_USER ON FINSIGHT.TRANSACTION_EMBEDDINGS(user_id);
CREATE INDEX FINSIGHT.IDX_VEC_TX ON FINSIGHT.TRANSACTION_EMBEDDINGS(transaction_id);
