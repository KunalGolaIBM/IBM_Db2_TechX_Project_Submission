-- =====================================================================
-- YojanaLens :: 04_procedure.sql
-- TERMINATOR @
--
-- SP_RECORD_TRACE moves the entire rule-evaluation matrix into Db2.
-- Python passes only (run_id, profile_id); Db2 joins every active scheme's
-- rules against the applicant's normalised facts and persists one row per
-- criterion with its verdict and the clause that grounds it.
--
-- This is the core of the "why Db2" argument: the join of semantic
-- candidates, structured facts and business rules happens in one engine
-- and one transaction, next to the data.
-- =====================================================================

CREATE OR REPLACE PROCEDURE SP_RECORD_TRACE (
    IN p_run_id      VARCHAR(64),
    IN p_profile_id  VARCHAR(64)
)
LANGUAGE SQL
BEGIN
    DELETE FROM decision_trace WHERE run_id = p_run_id;

    INSERT INTO decision_trace (
        run_id, scheme_id, rule_id, criterion_code, rule_op, mandatory,
        observed_value, verdict, clause_ref, chunk_id
    )
    SELECT
        p_run_id,
        r.scheme_id,
        r.rule_id,
        r.criterion_code,
        r.rule_op,
        r.mandatory,
        COALESCE(CAST(f.fact_num AS VARCHAR(32)), f.fact_text),
        CASE
            WHEN f.fact_key IS NULL THEN 'UNKNOWN'
            WHEN r.rule_op = 'eq' THEN
                CASE WHEN LOWER(f.fact_text) = LOWER(r.value_text)
                     THEN 'PASS' ELSE 'FAIL' END
            WHEN r.rule_op = 'in' THEN
                CASE WHEN LOCATE(',' || LOWER(f.fact_text) || ',',
                                 ',' || LOWER(r.value_text) || ',') > 0
                     THEN 'PASS' ELSE 'FAIL' END
            WHEN r.rule_op = 'lte' THEN
                CASE WHEN f.fact_num IS NULL THEN 'UNKNOWN'
                     WHEN f.fact_num <= r.value_num THEN 'PASS' ELSE 'FAIL' END
            WHEN r.rule_op = 'gte' THEN
                CASE WHEN f.fact_num IS NULL THEN 'UNKNOWN'
                     WHEN f.fact_num >= r.value_num THEN 'PASS' ELSE 'FAIL' END
            ELSE 'UNKNOWN'
        END,
        r.clause_ref,
        r.chunk_id
    FROM scheme_rules r
    JOIN schemes s
      ON s.scheme_id = r.scheme_id
     AND s.status = 'ACTIVE'
    LEFT JOIN profile_facts f
      ON f.fact_key = r.criterion_code
     AND f.profile_id = p_profile_id;
END @
