-- Hotel Ops Copilot: bitemporal promotions and a materialized query table.
-- Run after the data load (setup_db.py), statement delimiter '@'.

-- ---------------------------------------------------------------------------
-- PROMOTIONS: a BITEMPORAL table.
--   BUSINESS_TIME (VALID_FROM, VALID_TO) = the stay dates a promotion applies to (application time).
--   SYSTEM_TIME                          = when the hotel's records said so (transaction time, kept by Db2).
-- So the agent can answer "what discount applied to the night of 21 Nov, as we knew it yesterday?",
-- and a correction made today does not erase what a guest was quoted yesterday.
-- ---------------------------------------------------------------------------
CREATE TABLE PROMOTIONS (
    PROMO_ID      INTEGER       NOT NULL,
    ROOM_TYPE_ID  SMALLINT      NOT NULL REFERENCES ROOM_TYPES,
    NAME          VARCHAR(80)   NOT NULL,
    DISCOUNT_PCT  DECIMAL(4,1)  NOT NULL CHECK (DISCOUNT_PCT BETWEEN 0 AND 40),
    VALID_FROM    DATE          NOT NULL,
    VALID_TO      DATE          NOT NULL,
    UPDATED_BY    VARCHAR(40)   NOT NULL DEFAULT 'SYSTEM',
    CHANGE_REASON VARCHAR(200),
    PROPERTY_ID   SMALLINT      NOT NULL DEFAULT 1,
    SYS_START     TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN,
    SYS_END       TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END,
    TRANS_ID      TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID IMPLICITLY HIDDEN,
    PERIOD SYSTEM_TIME (SYS_START, SYS_END),
    PERIOD BUSINESS_TIME (VALID_FROM, VALID_TO),
    PRIMARY KEY (PROMO_ID, BUSINESS_TIME WITHOUT OVERLAPS),
    CONSTRAINT FK_PROMO_PROPERTY FOREIGN KEY (ROOM_TYPE_ID, PROPERTY_ID) REFERENCES ROOM_TYPES (ROOM_TYPE_ID, PROPERTY_ID)
)
@
CREATE TABLE PROMOTIONS_HISTORY LIKE PROMOTIONS
@
ALTER TABLE PROMOTIONS ADD VERSIONING USE HISTORY TABLE PROMOTIONS_HISTORY
@
COMMENT ON TABLE PROMOTIONS IS 'Bitemporal promotions. BUSINESS_TIME (VALID_FROM incl., VALID_TO excl.) = stay dates the discount covers; SYSTEM_TIME = when recorded. Use FOR BUSINESS_TIME AS OF <date> [FOR SYSTEM_TIME AS OF <ts>].'
@

-- ---------------------------------------------------------------------------
-- MQT_DAILY_KPIS: a materialized query table (REFRESH DEFERRED) over V_DAILY_KPIS.
-- Occupancy for past nights no longer changes, so the dashboard history and trend questions read
-- a precomputed table instead of re-aggregating every reservation. Refreshed by setup and on demand.
-- ---------------------------------------------------------------------------
CREATE TABLE MQT_DAILY_KPIS AS (
    SELECT PROPERTY_ID, STAY_DATE, DAY_NAME, IS_WEEKEND, ROOMS_IN_SERVICE, ROOMS_SOLD, ROOM_REVENUE,
           OCCUPANCY_PCT, ADR, REVPAR
      FROM V_DAILY_KPIS)
    DATA INITIALLY DEFERRED REFRESH DEFERRED ENABLE QUERY OPTIMIZATION MAINTAINED BY SYSTEM
@
COMMENT ON TABLE MQT_DAILY_KPIS IS 'Materialized (REFRESH DEFERRED) copy of V_DAILY_KPIS: OCCUPANCY_PCT, ADR, REVPAR per property and STAY_DATE. Fast for history and trends; may lag the live view until REFRESH TABLE. Has its own row permission, so an agent only sees its own hotel here too.'
@
