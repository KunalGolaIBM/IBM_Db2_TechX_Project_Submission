-- Staging model: stg_market_bars.sql
-- Cleanses raw OHLCV bars stored in IBM Db2 LUW

WITH raw_bars AS (
    SELECT
        CAST(ID AS BIGINT) AS bar_id,
        UPPER(TRIM(SYMBOL)) AS symbol,
        CAST(TIMESTAMP AS TIMESTAMP) AS bar_timestamp,
        CAST(OPEN AS DECIMAL(18, 4)) AS open_price,
        CAST(HIGH AS DECIMAL(18, 4)) AS high_price,
        CAST(LOW AS DECIMAL(18, 4)) AS low_price,
        CAST(CLOSE AS DECIMAL(18, 4)) AS close_price,
        CAST(VOLUME AS BIGINT) AS volume
    FROM MARKET_BARS
    WHERE CLOSE > 0.0 AND VOLUME >= 0
)

SELECT
    bar_id,
    symbol,
    bar_timestamp,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    CAST((high_price + low_price + close_price) / 3.0 AS DECIMAL(18, 4)) AS typical_price,
    CAST((high_price - low_price) AS DECIMAL(18, 4)) AS true_range,
    CASE 
        WHEN open_price > 0 THEN CAST((close_price - open_price) / open_price AS DOUBLE)
        ELSE 0.0
    END AS bar_return,
    CURRENT TIMESTAMP AS ingested_at
FROM raw_bars

