-- Optional engine-level leash on PortProof's adversarial test queries.
-- Requires WLMADM or DBADM, so setup_db.py applies this on a best-effort basis
-- and the application works without it. Verified on Db2 CE 12.1.5: a query that
-- exceeds the row threshold is stopped by the engine with SQL4712N.
-- Statements are separated by a line containing only --@

CREATE SERVICE CLASS PPAGENT
--@
CREATE WORKLOAD PPAGENT_WL CURRENT CLIENT_APPLNAME ('portproof-prover')
  SERVICE CLASS PPAGENT
--@
GRANT USAGE ON WORKLOAD PPAGENT_WL TO PUBLIC
--@
-- An adversarial query that tries to scan the world is stopped mid-flight.
CREATE THRESHOLD PP_MAX_ROWS FOR SERVICE CLASS PPAGENT ACTIVITIES
  ENFORCEMENT DATABASE
  WHEN SQLROWSRETURNED > 5000 STOP EXECUTION
--@
CREATE THRESHOLD PP_MAX_COST FOR SERVICE CLASS PPAGENT ACTIVITIES
  ENFORCEMENT DATABASE
  WHEN ESTIMATEDSQLCOST > 500000 STOP EXECUTION
