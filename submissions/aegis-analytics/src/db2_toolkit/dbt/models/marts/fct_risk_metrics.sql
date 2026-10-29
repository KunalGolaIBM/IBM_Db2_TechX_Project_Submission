-- Mart model: fct_risk_metrics.sql
-- Joins cleansed market bars with conformal prediction residuals to assess coverage & tail risk

WITH market_bars AS (
    SELECT * FROM {{ ref('stg_market_bars') }}
),

conformal_data AS (
    SELECT
        CAST(ID AS BIGINT) AS residual_id,
        UPPER(TRIM(SYMBOL)) AS symbol,
        CAST(TIMESTAMP AS TIMESTAMP) AS prediction_timestamp,
        MODEL_ID AS model_id,
        CAST(SCORE AS DOUBLE) AS nonconformity_score,
        CAST(ALPHA AS DOUBLE) AS alpha,
        CAST(INTERVAL_LOWER AS DECIMAL(18, 4)) AS interval_lower,
        CAST(INTERVAL_UPPER AS DECIMAL(18, 4)) AS interval_upper,
        CAST(COVERED AS SMALLINT) AS is_covered
    FROM CONFORMAL_RESIDUALS
),

joined AS (
    SELECT
        b.symbol,
        b.bar_timestamp,
        b.close_price,
        b.bar_return,
        c.model_id,
        c.nonconformity_score,
        c.alpha,
        c.interval_lower,
        c.interval_upper,
        CASE
            WHEN b.close_price >= c.interval_lower AND b.close_price <= c.interval_upper THEN 1
            ELSE 0
        END AS realized_coverage,
        CAST(c.interval_upper - c.interval_lower AS DECIMAL(18, 4)) AS interval_bandwidth
    FROM market_bars b
    INNER JOIN conformal_data c
        ON b.symbol = c.symbol
        AND DATE(b.bar_timestamp) = DATE(c.prediction_timestamp)
)

SELECT
    symbol,
    model_id,
    COUNT(*) AS total_observations,
    AVG(bar_return) AS mean_return,
    AVG(realized_coverage) AS empirical_coverage_rate,
    1.0 - AVG(alpha) AS nominal_confidence_level,
    AVG(interval_bandwidth) AS avg_bandwidth,
    AVG(nonconformity_score) AS avg_nonconformity_score,
    CURRENT TIMESTAMP AS calculated_at
FROM joined
GROUP BY symbol, model_id
FETCH FIRST 100 ROWS ONLY

