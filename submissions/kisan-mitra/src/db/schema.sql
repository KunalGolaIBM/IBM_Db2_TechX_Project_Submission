-- =============================================================================
-- Kisan Mitra (किसान मित्र) - IBM Db2 Database Schema
-- Compatible with IBM Db2 12.1+ (Engine supporting native VECTOR data type)
-- =============================================================================

-- Clean up existing tables if rebuilding
BEGIN
    DECLARE CONTINUE HANDLER FOR SQLSTATE '42704' BEGIN END;
    EXECUTE IMMEDIATE 'DROP TABLE MANDI_PRICES';
    EXECUTE IMMEDIATE 'DROP TABLE DOC_CHUNKS';
END@

-- -----------------------------------------------------------------------------
-- 1. MANDI_PRICES: Real-time & Historical Mandi (Market) Daily Price Records
-- Sourced from Agmarknet (data.gov.in)
-- -----------------------------------------------------------------------------
CREATE TABLE MANDI_PRICES (
    id            BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    state         VARCHAR(64) NOT NULL,
    district      VARCHAR(64) NOT NULL,
    market        VARCHAR(128) NOT NULL,
    commodity     VARCHAR(128) NOT NULL,
    variety       VARCHAR(128) DEFAULT 'FAQ',
    arrival_date  DATE NOT NULL,
    min_price     DECIMAL(10,2),
    max_price     DECIMAL(10,2),
    modal_price   DECIMAL(10,2) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_mandi_prices PRIMARY KEY (id)
);

-- Optimized composite indexes for Text-to-SQL analytics & filtering
CREATE INDEX idx_mandi_state_comm_date 
    ON MANDI_PRICES (state, commodity, arrival_date);

CREATE INDEX idx_mandi_district_market 
    ON MANDI_PRICES (district, market, arrival_date);

CREATE INDEX idx_mandi_commodity_date 
    ON MANDI_PRICES (commodity, arrival_date);

-- -----------------------------------------------------------------------------
-- 2. DOC_CHUNKS: Knowledge Base Chunks with IBM Db2 Native VECTOR Embeddings
-- Stores chunked official Government Welfare Scheme Guidelines (PM-KISAN, PMFBY, KCC)
-- Embedding vector: 384-dimensional REAL coordinates matching paraphrase-multilingual-MiniLM-L12-v2
-- -----------------------------------------------------------------------------
CREATE TABLE DOC_CHUNKS (
    id            BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    doc_name      VARCHAR(256) NOT NULL,
    scheme_name   VARCHAR(128) NOT NULL,
    page_number   INT NOT NULL,
    chunk_index   INT NOT NULL,
    chunk_text    CLOB(64K) NOT NULL,
    embedding     VECTOR(384, REAL) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT pk_doc_chunks PRIMARY KEY (id)
);

CREATE INDEX idx_doc_scheme_page 
    ON DOC_CHUNKS (scheme_name, page_number);

-- -----------------------------------------------------------------------------
-- 3. Security Hardening: Read-Only Privilege Delegation
-- The Text-to-SQL agent connects using the read-only user 'kisan_ro'.
-- Granting SELECT only ensures the LLM cannot mutate data or execute DDL.
-- -----------------------------------------------------------------------------
GRANT SELECT ON TABLE MANDI_PRICES TO USER kisan_ro;
GRANT SELECT ON TABLE DOC_CHUNKS TO USER kisan_ro;

-- Explicitly revoke data modifications (defense in depth)
REVOKE INSERT, UPDATE, DELETE ON TABLE MANDI_PRICES FROM USER kisan_ro;
REVOKE INSERT, UPDATE, DELETE ON TABLE DOC_CHUNKS FROM USER kisan_ro;
