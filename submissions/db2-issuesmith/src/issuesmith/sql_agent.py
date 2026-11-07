"""Insights analyst agent: natural-language questions -> read-only Db2 SQL.

Guardrails: single SELECT/WITH statement, no DML/DDL keywords, only objects in
the IssueSmith schema, row limit enforced, and the transaction is rolled back.
"""
from __future__ import annotations

import re

from .llm import BaseLLM, LLMUnavailable

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|GRANT|REVOKE|CALL|TRUNCATE|EXPORT|IMPORT|LOAD|"
    r"REORG|RUNSTATS|SET|DECLARE|EXECUTE|COMMIT|ROLLBACK|LOCK)\b",
    re.IGNORECASE,
)
FROM_JOIN = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z0-9_.\"]+)", re.IGNORECASE)


def schema_doc(schema: str) -> str:
    s = schema.upper()
    return f"""Db2 objects you may query (schema {s}):
{s}.INCIDENTS(INCIDENT_ID, SOURCE_NAME, CATEGORY, CONFIDENCE, SIGNATURE, REDACTION_COUNT, STATUS, DUPLICATE_OF, CREATED_AT)
  CATEGORY values: RUNTIME_INSTALL, RESTART, CONNECTION, AUTHENTICATION, NETWORK, EXTENSION, UNCLASSIFIED
  STATUS values: NEW, DRAFTED, DUPLICATE, POSTED
{s}.EVIDENCE(EVIDENCE_ID, INCIDENT_ID, LINE_NO, KIND, LABEL, CATEGORY, LOG_LINE, SIGNATURE)  KIND: ERROR, WARNING, OBSERVATION
{s}.ISSUE_DRAFTS(DRAFT_ID, INCIDENT_ID, ROUND_NO, TITLE, CRITIC_SCORE, GENERATED_BY, IS_FINAL, GITHUB_URL, CREATED_AT)
{s}.AGENT_RUNS(RUN_ID, INCIDENT_ID, AGENT, STATUS, DETAIL, LATENCY_MS, CREATED_AT)
{s}.V_CATEGORY_STATS(CATEGORY, INCIDENTS, DUPLICATES, AVG_CONFIDENCE, SECRETS_REDACTED, LAST_SEEN)
{s}.V_TOP_SIGNATURES(SIGNATURE, LABEL, CATEGORY, INCIDENTS, FIRST_SEEN, LAST_SEEN)
{s}.V_AGENT_PERFORMANCE(AGENT, RUNS, AVG_LATENCY_MS, MAX_LATENCY_MS, FAILURES)
{s}.V_DRAFT_QUALITY(INCIDENT_ID, CATEGORY, ROUNDS_NEEDED, CRITIC_SCORE, GENERATED_BY, GITHUB_URL, CREATED_AT)
{s}.V_INCIDENT_ENV(INCIDENT_ID, CATEGORY, CREATED_AT, OPERATING_SYSTEM, CONTAINER_RUNTIME, EXTENSION_VERSION, DB2_VERSION)"""


SYSTEM = """You translate questions into ONE IBM Db2 SQL SELECT statement.
Rules: use only the listed objects with their schema prefix; Db2 syntax (FETCH FIRST n ROWS ONLY, CURRENT TIMESTAMP,
TIMESTAMPDIFF, DATE(...)); no semicolon; no comments; read-only. Reply with the SQL only."""


class UnsafeSQL(ValueError):
    pass


def validate_sql(sql: str, schema: str, max_rows: int = 200) -> str:
    q = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).strip().rstrip(";").strip()
    if ";" in q:
        raise UnsafeSQL("Only a single statement is allowed.")
    if "--" in q or "/*" in q:
        raise UnsafeSQL("Comments are not allowed.")
    if not re.match(r"^(SELECT|WITH)\b", q, re.IGNORECASE):
        raise UnsafeSQL("Only SELECT queries are allowed.")
    bad = FORBIDDEN.search(q)
    if bad:
        raise UnsafeSQL(f"Keyword not allowed: {bad.group(0).upper()}")
    ctes = {m.upper() for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", q, re.IGNORECASE)}
    for obj in FROM_JOIN.findall(q):
        name = obj.replace('"', "").upper()
        if name.startswith("(") or name in ctes:
            continue
        if not name.startswith(schema.upper() + "."):
            raise UnsafeSQL(f"Object outside the {schema.upper()} schema: {obj}")
    if not re.search(r"FETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY", q, re.IGNORECASE):
        q += f" FETCH FIRST {max_rows} ROWS ONLY"
    return q


def question_to_sql(llm: BaseLLM, question: str, schema: str) -> str:
    if not llm.available:
        raise LLMUnavailable("Set LLM_PROVIDER in .env to ask questions in plain English.")
    raw = llm.chat(SYSTEM, f"{schema_doc(schema)}\n\nQuestion: {question}\nSQL:")
    return validate_sql(raw, schema)
