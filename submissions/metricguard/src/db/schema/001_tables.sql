-- MetricGuard schema for IBM Db2 (LUW 11.5+/12.1).
-- Statement terminator: ';' (one statement per terminator, run by `metricguard db init`).
-- All timestamps are UTC. All money is DECIMAL(…,2) in USD.

CREATE SCHEMA METRICGUARD;

-- ---------------------------------------------------------------------------
-- PRODUCTS: product catalog (dimension).
-- ---------------------------------------------------------------------------
CREATE TABLE METRICGUARD.PRODUCTS (
    PRODUCT_ID      INTEGER       NOT NULL,
    SKU             VARCHAR(32)   NOT NULL,
    PRODUCT_NAME    VARCHAR(120)  NOT NULL,
    CATEGORY        VARCHAR(16)   NOT NULL,
    LIST_PRICE      DECIMAL(10,2) NOT NULL,
    IS_ACTIVE       SMALLINT      NOT NULL DEFAULT 1,
    CREATED_AT      TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT PK_PRODUCTS PRIMARY KEY (PRODUCT_ID),
    CONSTRAINT UQ_PRODUCTS_SKU UNIQUE (SKU),
    CONSTRAINT CK_PRODUCTS_CATEGORY CHECK (CATEGORY IN ('ELECTRONICS','HOME','APPAREL','BEAUTY','SPORTS')),
    CONSTRAINT CK_PRODUCTS_PRICE CHECK (LIST_PRICE >= 0),
    CONSTRAINT CK_PRODUCTS_ACTIVE CHECK (IS_ACTIVE IN (0, 1))
);

-- ---------------------------------------------------------------------------
-- ORDERS: one row per customer order (order header).
-- SHIPPING_AMOUNT is intentionally NOT revenue (see docs/METRIC_SEMANTICS.md);
-- summing it after joining ORDER_ITEMS multiplies it by the line count.
-- ---------------------------------------------------------------------------
CREATE TABLE METRICGUARD.ORDERS (
    ORDER_ID        INTEGER       NOT NULL,
    ORDER_NUMBER    VARCHAR(20)   NOT NULL,
    CUSTOMER_ID     INTEGER       NOT NULL,
    ORDER_TS        TIMESTAMP     NOT NULL,
    STATUS          VARCHAR(16)   NOT NULL,
    REGION_CODE     VARCHAR(8)    NOT NULL,
    CHANNEL_CODE    VARCHAR(12)   NOT NULL,
    CURRENCY_CODE   CHAR(3)       NOT NULL DEFAULT 'USD',
    SHIPPING_AMOUNT DECIMAL(10,2) NOT NULL DEFAULT 0,
    PROMO_CODE      VARCHAR(20),
    CANCELLED_TS    TIMESTAMP,
    CONSTRAINT PK_ORDERS PRIMARY KEY (ORDER_ID),
    CONSTRAINT UQ_ORDERS_NUMBER UNIQUE (ORDER_NUMBER),
    CONSTRAINT CK_ORDERS_STATUS CHECK (STATUS IN ('COMPLETED','CANCELLED','PENDING')),
    CONSTRAINT CK_ORDERS_REGION CHECK (REGION_CODE IN ('NA','EMEA','APAC','LATAM')),
    CONSTRAINT CK_ORDERS_CHANNEL CHECK (CHANNEL_CODE IN ('WEB','MOBILE','STORE','MARKETPLACE')),
    CONSTRAINT CK_ORDERS_CURRENCY CHECK (CURRENCY_CODE = 'USD'),
    CONSTRAINT CK_ORDERS_SHIPPING CHECK (SHIPPING_AMOUNT >= 0),
    CONSTRAINT CK_ORDERS_CANCEL_TS CHECK (
        (STATUS = 'CANCELLED' AND CANCELLED_TS IS NOT NULL AND CANCELLED_TS >= ORDER_TS)
        OR (STATUS <> 'CANCELLED' AND CANCELLED_TS IS NULL)
    )
);

-- ---------------------------------------------------------------------------
-- ORDER_ITEMS: order lines. Revenue grain.
-- DISCOUNT_AMOUNT is the total discount for the line (not per unit).
-- ---------------------------------------------------------------------------
CREATE TABLE METRICGUARD.ORDER_ITEMS (
    ORDER_ITEM_ID   INTEGER       NOT NULL,
    ORDER_ID        INTEGER       NOT NULL,
    LINE_NUMBER     SMALLINT      NOT NULL,
    PRODUCT_ID      INTEGER       NOT NULL,
    QUANTITY        INTEGER       NOT NULL,
    UNIT_PRICE      DECIMAL(10,2) NOT NULL,
    DISCOUNT_AMOUNT DECIMAL(10,2) NOT NULL DEFAULT 0,
    CONSTRAINT PK_ORDER_ITEMS PRIMARY KEY (ORDER_ITEM_ID),
    CONSTRAINT UQ_ORDER_ITEMS_LINE UNIQUE (ORDER_ID, LINE_NUMBER),
    CONSTRAINT UQ_ORDER_ITEMS_ITEM_ORDER UNIQUE (ORDER_ITEM_ID, ORDER_ID),
    CONSTRAINT FK_ORDER_ITEMS_ORDER FOREIGN KEY (ORDER_ID)
        REFERENCES METRICGUARD.ORDERS (ORDER_ID) ON DELETE RESTRICT,
    CONSTRAINT FK_ORDER_ITEMS_PRODUCT FOREIGN KEY (PRODUCT_ID)
        REFERENCES METRICGUARD.PRODUCTS (PRODUCT_ID) ON DELETE RESTRICT,
    CONSTRAINT CK_ORDER_ITEMS_QTY CHECK (QUANTITY > 0),
    CONSTRAINT CK_ORDER_ITEMS_PRICE CHECK (UNIT_PRICE >= 0),
    CONSTRAINT CK_ORDER_ITEMS_DISCOUNT CHECK (DISCOUNT_AMOUNT >= 0 AND DISCOUNT_AMOUNT <= QUANTITY * UNIT_PRICE)
);

-- ---------------------------------------------------------------------------
-- REFUNDS: money returned against a specific order line.
-- Multiple refunds per line are allowed (partial refunds in installments).
-- (ORDER_ITEM_ID, ORDER_ID) composite FK guarantees the refund's order matches its line.
-- Cross-row rule "processed refunds <= line amount" is enforced by the seed generator
-- and checked by `metricguard db verify` (data-quality check DQ-03).
-- ---------------------------------------------------------------------------
CREATE TABLE METRICGUARD.REFUNDS (
    REFUND_ID       INTEGER       NOT NULL,
    ORDER_ID        INTEGER       NOT NULL,
    ORDER_ITEM_ID   INTEGER       NOT NULL,
    REFUND_TS       TIMESTAMP     NOT NULL,
    REFUND_AMOUNT   DECIMAL(10,2) NOT NULL,
    STATUS          VARCHAR(12)   NOT NULL,
    REASON_CODE     VARCHAR(24),
    CONSTRAINT PK_REFUNDS PRIMARY KEY (REFUND_ID),
    CONSTRAINT FK_REFUNDS_ORDER FOREIGN KEY (ORDER_ID)
        REFERENCES METRICGUARD.ORDERS (ORDER_ID) ON DELETE RESTRICT,
    CONSTRAINT FK_REFUNDS_ITEM FOREIGN KEY (ORDER_ITEM_ID, ORDER_ID)
        REFERENCES METRICGUARD.ORDER_ITEMS (ORDER_ITEM_ID, ORDER_ID) ON DELETE RESTRICT,
    CONSTRAINT CK_REFUNDS_AMOUNT CHECK (REFUND_AMOUNT > 0),
    CONSTRAINT CK_REFUNDS_STATUS CHECK (STATUS IN ('PROCESSED','PENDING','REJECTED'))
);

-- ---------------------------------------------------------------------------
-- METRIC_DEFINITIONS: approved, versioned metric semantics.
-- Declarative metadata only. No executable SQL is stored here; SQL is produced by
-- the version-controlled compiler (backend/metricguard/core/compiler.py).
-- DEFINITION_HASH = SHA-256 of the canonical DEFINITION_JSON; the API refuses to
-- mark a result VERIFIED if the runtime registry hash differs from the approved row.
-- ---------------------------------------------------------------------------
CREATE TABLE METRICGUARD.METRIC_DEFINITIONS (
    METRIC_NAME             VARCHAR(64)   NOT NULL,
    METRIC_VERSION          VARCHAR(16)   NOT NULL,
    DISPLAY_NAME            VARCHAR(80)   NOT NULL,
    DESCRIPTION             VARCHAR(1000) NOT NULL,
    CALCULATION             VARCHAR(1000) NOT NULL,
    UNIT                    VARCHAR(8)    NOT NULL,
    METRIC_KIND             VARCHAR(8)    NOT NULL,
    IS_ADDITIVE             SMALLINT      NOT NULL,
    ELIGIBLE_ORDER_STATUSES VARCHAR(200)  NOT NULL,
    DATE_ATTRIBUTION        VARCHAR(500)  NOT NULL,
    NULL_HANDLING           VARCHAR(500)  NOT NULL,
    REFUND_TREATMENT        VARCHAR(500)  NOT NULL,
    DISCOUNT_TREATMENT      VARCHAR(500)  NOT NULL,
    ALLOWED_DIMENSIONS      VARCHAR(500)  NOT NULL,
    ALLOWED_FILTERS         VARCHAR(500)  NOT NULL,
    DEFINITION_JSON         CLOB(64K)     NOT NULL,
    DEFINITION_HASH         CHAR(64)      NOT NULL,
    LIFECYCLE_STATUS        VARCHAR(12)   NOT NULL DEFAULT 'APPROVED',
    OWNER                   VARCHAR(80)   NOT NULL,
    APPROVED_AT             TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT PK_METRIC_DEFINITIONS PRIMARY KEY (METRIC_NAME, METRIC_VERSION),
    CONSTRAINT CK_METRIC_UNIT CHECK (UNIT IN ('USD','COUNT','RATIO')),
    CONSTRAINT CK_METRIC_KIND CHECK (METRIC_KIND IN ('BASE','DERIVED')),
    CONSTRAINT CK_METRIC_ADDITIVE CHECK (IS_ADDITIVE IN (0, 1)),
    CONSTRAINT CK_METRIC_LIFECYCLE CHECK (LIFECYCLE_STATUS IN ('DRAFT','APPROVED','DEPRECATED'))
);

-- ---------------------------------------------------------------------------
-- QUERY_AUDIT_LOG: one row per /api/analyze request, whatever the outcome.
-- ---------------------------------------------------------------------------
CREATE TABLE METRICGUARD.QUERY_AUDIT_LOG (
    REQUEST_ID          CHAR(36)      NOT NULL,
    CREATED_AT          TIMESTAMP     NOT NULL DEFAULT CURRENT TIMESTAMP,
    QUESTION            VARCHAR(2000) NOT NULL,
    STATUS              VARCHAR(24)   NOT NULL,
    STATUS_REASON       VARCHAR(1000),
    METRIC_REFS         VARCHAR(1000),
    PLANNER             VARCHAR(80),
    PLAN_JSON           CLOB(1M),
    SQL_TEXT            CLOB(1M),
    SQL_PARAMS_JSON     CLOB(256K),
    SQL_HASH            CHAR(64),
    VERIFICATION_JSON   CLOB(1M),
    RESULT_ROW_COUNT    INTEGER,
    RESULT_PREVIEW_JSON CLOB(1M),
    TOTAL_MS            INTEGER,
    PLANNING_MS         INTEGER,
    VALIDATION_MS       INTEGER,
    EXECUTION_MS        INTEGER,
    VERIFICATION_MS     INTEGER,
    ERROR_CODE          VARCHAR(64),
    ERROR_MESSAGE       VARCHAR(1000),
    API_VERSION         VARCHAR(16)   NOT NULL,
    CONSTRAINT PK_QUERY_AUDIT_LOG PRIMARY KEY (REQUEST_ID),
    CONSTRAINT CK_AUDIT_STATUS CHECK (STATUS IN
        ('VERIFIED','EXECUTED_WITH_WARNINGS','AMBIGUOUS','BLOCKED','EXECUTION_FAILED')),
    CONSTRAINT CK_AUDIT_ROWS CHECK (RESULT_ROW_COUNT IS NULL OR RESULT_ROW_COUNT >= 0)
);
