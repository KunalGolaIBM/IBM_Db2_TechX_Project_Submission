-- =====================================================================
-- YojanaLens :: 03_queries.sql
--
-- These are the canonical queries the application executes. They live in
-- a .sql file on purpose: a reviewer can paste any section into a Db2
-- CLP session and see exactly what the engine is doing.
--
-- Sections are delimited by `-- name: <key>`. src/sql_loader.py replaces
-- every :parameter with a positional marker (?) in order of appearance,
-- so the number of markers and the parameter list can never drift apart.
-- =====================================================================

-- ---------------------------------------------------------------------
-- name: retrieval
-- One round trip: residency pre-filter + optional category filter + native
-- vector ranking, executed entirely inside Db2.
-- ---------------------------------------------------------------------
WITH candidate AS (
    SELECT s.scheme_id
    FROM schemes s
    WHERE s.status = 'ACTIVE'
      AND (CAST(:state AS VARCHAR(8)) IS NULL OR s.state_code IN ('ALL', :state))
      AND (CAST(:category AS VARCHAR(32)) IS NULL OR s.category = :category)
)
SELECT c.chunk_id,
       c.scheme_id,
       c.clause_ref,
       c.section,
       SUBSTR(c.chunk_text, 1, 700) AS chunk_text,
       VECTOR_DISTANCE(c.embedding,
                       VECTOR(CAST(:query_vec AS VARCHAR(32672)), 384, FLOAT32),
                       COSINE) AS distance
FROM scheme_chunks c
JOIN candidate s ON s.scheme_id = c.scheme_id
ORDER BY distance ASC
FETCH FIRST 12 ROWS ONLY;

-- ---------------------------------------------------------------------
-- name: scheme_trace
-- Everything needed to render and audit one scheme's decision.
-- ---------------------------------------------------------------------
SELECT t.scheme_id,
       s.name,
       s.category,
       s.gov_level,
       s.state_code,
       s.benefit_summary,
       s.source_url,
       t.rule_id,
       t.criterion_code,
       t.rule_op,
       t.mandatory,
       t.observed_value,
       t.verdict,
       t.clause_ref,
       t.chunk_id,
       t.narrative,
       r.value_num,
       r.value_text,
       c.chunk_text
FROM decision_trace t
JOIN scheme_rules r ON r.rule_id = t.rule_id
JOIN schemes s      ON s.scheme_id = t.scheme_id
LEFT JOIN scheme_chunks c ON c.chunk_id = t.chunk_id
WHERE t.run_id = :run_id
ORDER BY t.scheme_id, t.rule_id;

-- ---------------------------------------------------------------------
-- name: run_overview
-- Audit reconstruction: who asked what, which model, which SQL, what was
-- decided, and when.
-- ---------------------------------------------------------------------
SELECT a.run_id,
       a.profile_id,
       p.raw_text,
       a.model,
       a.prompt_version,
       a.retriever_top_k,
       a.candidates,
       a.latency_ms,
       a.status,
       a.started_at,
       a.finished_at,
       a.summary_json,
       (SELECT COUNT(*) FROM decision_trace t WHERE t.run_id = a.run_id) AS rules_evaluated,
       (SELECT COUNT(*) FROM decision_trace t
         WHERE t.run_id = a.run_id AND t.verdict = 'PASS')                AS rules_passed,
       (SELECT COUNT(*) FROM audit_log g WHERE g.run_id = a.run_id)       AS audit_events
FROM agent_runs a
JOIN profiles p ON p.profile_id = a.profile_id
WHERE a.run_id = :run_id;

-- ---------------------------------------------------------------------
-- name: audit_events
-- Append-only log for one run, newest last.
-- ---------------------------------------------------------------------
SELECT audit_id, actor, action, detail, sql_hash, created_at
FROM audit_log
WHERE run_id = :run_id
ORDER BY audit_id;

-- ---------------------------------------------------------------------
-- name: recent_runs
-- Small dashboard for the UI: last decisions in the database.
-- ---------------------------------------------------------------------
SELECT a.run_id,
       a.profile_id,
       a.model,
       a.status,
       a.latency_ms,
       a.started_at,
       (SELECT COUNT(*) FROM decision_trace t WHERE t.run_id = a.run_id) AS rules_evaluated
FROM agent_runs a
ORDER BY a.started_at DESC
FETCH FIRST 10 ROWS ONLY;

-- ---------------------------------------------------------------------
-- name: corpus_stats
-- Live counters shown in the UI header (never hardcoded).
-- ---------------------------------------------------------------------
SELECT (SELECT COUNT(*) FROM schemes WHERE status = 'ACTIVE')  AS active_schemes,
       (SELECT COUNT(*) FROM scheme_rules)                     AS total_rules,
       (SELECT COUNT(*) FROM scheme_chunks)                    AS total_clauses,
       (SELECT COUNT(DISTINCT criterion_code) FROM scheme_rules) AS criteria_covered
FROM SYSIBM.SYSDUMMY1;
