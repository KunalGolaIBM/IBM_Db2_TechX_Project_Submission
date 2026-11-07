"""All Db2 access lives here (ibm_db / ibm_db_dbi, parameterised SQL only)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .embeddings import DIM, to_vector_literal

log = logging.getLogger(__name__)
SCHEMA_FILE = Path(__file__).with_name("schema.sql")
_ALREADY_EXISTS = ("SQL0601N", "SQL0624N", "SQL0605W")
_NOT_FOUND = ("SQL0204N",)
_TABLES_DROP_ORDER = ("EVIDENCE", "ISSUE_DRAFTS", "AGENT_RUNS", "INCIDENTS", "KB_DOCS")


class Db2Error(RuntimeError):
    """Raised with a human-readable hint when Db2 is unreachable or misconfigured."""


def connect(conn_str: str):
    try:
        import ibm_db_dbi
    except ImportError as exc:  # pragma: no cover
        raise Db2Error("The 'ibm_db' package is not installed. Run: pip install -r requirements.txt") from exc
    try:
        conn = ibm_db_dbi.connect(conn_str, "", "")
    except Exception as exc:
        safe = re.sub(r"PWD=[^;]*", "PWD=***", conn_str)
        raise Db2Error(
            f"Could not connect to Db2 ({safe}). Is the container running and finished "
            f"setting up? Check DB2_* values in .env. Driver said: {exc}"
        ) from exc
    try:
        conn.set_autocommit(False)
    except Exception:  # older drivers
        pass
    return conn


class Db2Repository:
    def __init__(self, conn, schema: str = "ISSUESMITH") -> None:
        self.conn = conn
        self.schema = schema.upper()

    # ------------------------------------------------------------------ helpers
    def _q(self, sql: str) -> str:
        return sql.replace("{schema}", self.schema)

    def _exec(self, sql: str, params: tuple | list | None = None) -> Any:
        cur = self.conn.cursor()
        if params:
            cur.execute(self._q(sql), tuple(params))
        else:
            cur.execute(self._q(sql))
        return cur

    def _rows(self, sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
        cur = self._exec(sql, params)
        try:
            cols = [d[0].upper() for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            cur.close()

    def commit(self) -> None:
        self.conn.commit()

    # ------------------------------------------------------------------ schema
    def check_vector_support(self) -> float:
        """Raises if this Db2 build has no VECTOR type (needs 12.1.2+)."""
        rows = self._rows(
            "SELECT VECTOR_DISTANCE(VECTOR('[1,0]', 2, FLOAT32), VECTOR('[0,1]', 2, FLOAT32), COSINE) AS D "
            "FROM SYSIBM.SYSDUMMY1"
        )
        return float(rows[0]["D"])

    def db2_version(self) -> str:
        rows = self._rows("SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO()) AS T")
        return str(rows[0]["SERVICE_LEVEL"]) if rows else "unknown"

    def init_schema(self, reset: bool = False, dim: int = DIM) -> list[str]:
        messages: list[str] = []
        if reset:
            for table in _TABLES_DROP_ORDER:
                try:
                    self._exec(f"DROP TABLE {{schema}}.{table}").close()
                    messages.append(f"dropped {table}")
                except Exception as exc:
                    if not any(code in str(exc) for code in _NOT_FOUND):
                        raise
            self.commit()
        try:
            self._exec(f'CREATE SCHEMA "{self.schema}"').close()
            messages.append(f"created schema {self.schema}")
        except Exception as exc:
            if not any(code in str(exc) for code in _ALREADY_EXISTS):
                raise

        for optional, stmt in self._schema_statements(dim):
            first_line = stmt.splitlines()[0][:70]
            try:
                self._exec(stmt).close()
                messages.append(f"ok: {first_line}")
            except Exception as exc:
                text = str(exc)
                if any(code in text for code in _ALREADY_EXISTS):
                    messages.append(f"exists: {first_line}")
                elif optional:
                    messages.append(f"skipped optional: {first_line} ({text[:120]})")
                    log.warning("Optional statement failed: %s", text)
                else:
                    self.conn.rollback()
                    raise Db2Error(f"Schema statement failed: {first_line}\n{text}") from exc
        self.commit()
        return messages

    def _schema_statements(self, dim: int) -> list[tuple[bool, str]]:
        raw = SCHEMA_FILE.read_text(encoding="utf-8").replace("{dim}", str(dim))
        out: list[tuple[bool, str]] = []
        for chunk in re.split(r"^\s*@\s*$", raw, flags=re.MULTILINE):
            lines = chunk.strip().splitlines()
            optional = any(line.strip().lower() == "-- optional" for line in lines)
            body = "\n".join(line for line in lines if not line.strip().startswith("--")).strip()
            if body:
                out.append((optional, self._q(body)))
        return out

    # ------------------------------------------------------------------ incidents
    def create_incident(self, source_name: str, sanitized_log: str, redactions: int) -> int:
        rows = self._rows(
            "SELECT INCIDENT_ID FROM FINAL TABLE ("
            " INSERT INTO {schema}.INCIDENTS (SOURCE_NAME, SANITIZED_LOG, REDACTION_COUNT)"
            " VALUES (?, ?, ?))",
            (source_name[:255], sanitized_log, int(redactions)),
        )
        self.commit()
        return int(rows[0]["INCIDENT_ID"])

    def update_classification(
        self, incident_id: int, category: str, confidence: float, env: dict, signature: str, embedding: list[float]
    ) -> None:
        dim = len(embedding)
        self._exec(
            "UPDATE {schema}.INCIDENTS SET CATEGORY = ?, CONFIDENCE = ?, ENV_JSON = ?, SIGNATURE = ?,"
            f" EMBEDDING = VECTOR(?, {dim}, FLOAT32) WHERE INCIDENT_ID = ?",
            (category, round(float(confidence), 3), json.dumps(env), signature[:3000],
             to_vector_literal(embedding), incident_id),
        ).close()
        self.commit()

    def add_evidence(self, incident_id: int, evidence: list[dict]) -> None:
        if not evidence:
            return
        cur = self.conn.cursor()
        try:
            cur.executemany(
                self._q(
                    "INSERT INTO {schema}.EVIDENCE (INCIDENT_ID, LINE_NO, KIND, LABEL, CATEGORY, LOG_LINE, SIGNATURE)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)"
                ),
                [
                    (incident_id, e["line_no"], e["kind"], e["label"][:120], e["category"],
                     e["log_line"][:2000], e["signature"][:1000])
                    for e in evidence
                ],
            )
        finally:
            cur.close()
        self.commit()

    def find_similar(self, incident_id: int) -> list[dict[str, Any]]:
        """Vector similarity inside Db2 via stored procedure (falls back to inline SQL)."""
        try:
            cur = self.conn.cursor()
            cur.callproc(f"{self.schema}.FIND_SIMILAR_INCIDENTS", (incident_id,))
            cols = [d[0].upper() for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            via = "procedure"
        except Exception as exc:
            log.warning("FIND_SIMILAR_INCIDENTS call failed (%s); using inline SQL.", exc)
            rows = self._rows(
                "SELECT O.INCIDENT_ID, O.CATEGORY, O.STATUS, O.CREATED_AT,"
                " VECTOR_DISTANCE(T.EMBEDDING, O.EMBEDDING, COSINE) AS DISTANCE"
                " FROM {schema}.INCIDENTS T JOIN {schema}.INCIDENTS O ON O.INCIDENT_ID <> T.INCIDENT_ID"
                " WHERE T.INCIDENT_ID = ? AND T.EMBEDDING IS NOT NULL AND O.EMBEDDING IS NOT NULL"
                " ORDER BY DISTANCE FETCH FIRST 5 ROWS ONLY",
                (incident_id,),
            )
            via = "inline-sql"
        for r in rows:
            r["DISTANCE"] = float(r["DISTANCE"])
            r["VIA"] = via
        return rows

    def set_status(self, incident_id: int, status: str, duplicate_of: int | None = None) -> None:
        self._exec(
            "UPDATE {schema}.INCIDENTS SET STATUS = ?, DUPLICATE_OF = ? WHERE INCIDENT_ID = ?",
            (status, duplicate_of, incident_id),
        ).close()
        self.commit()

    # ------------------------------------------------------------------ drafts & audit
    def save_draft(
        self, incident_id: int, round_no: int, title: str, body: str, score: float,
        notes: dict, generated_by: str, is_final: bool,
    ) -> int:
        if is_final:
            self._exec("UPDATE {schema}.ISSUE_DRAFTS SET IS_FINAL = 'N' WHERE INCIDENT_ID = ?", (incident_id,)).close()
        rows = self._rows(
            "SELECT DRAFT_ID FROM FINAL TABLE ("
            " INSERT INTO {schema}.ISSUE_DRAFTS"
            " (INCIDENT_ID, ROUND_NO, TITLE, BODY_MD, CRITIC_SCORE, CRITIC_NOTES, GENERATED_BY, IS_FINAL)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?))",
            (incident_id, round_no, title[:300], body, round(float(score), 2), json.dumps(notes),
             generated_by[:80], "Y" if is_final else "N"),
        )
        self.commit()
        return int(rows[0]["DRAFT_ID"])

    def update_final_draft(self, incident_id: int, title: str, body: str) -> None:
        self._exec(
            "UPDATE {schema}.ISSUE_DRAFTS SET TITLE = ?, BODY_MD = ? WHERE INCIDENT_ID = ? AND IS_FINAL = 'Y'",
            (title[:300], body, incident_id),
        ).close()
        self.commit()

    def mark_posted(self, incident_id: int, url: str) -> None:
        self._exec(
            "UPDATE {schema}.ISSUE_DRAFTS SET GITHUB_URL = ? WHERE INCIDENT_ID = ? AND IS_FINAL = 'Y'",
            (url, incident_id),
        ).close()
        self._exec("UPDATE {schema}.INCIDENTS SET STATUS = 'POSTED' WHERE INCIDENT_ID = ?", (incident_id,)).close()
        self.commit()

    def log_agent_run(self, incident_id: int | None, agent: str, status: str, detail: str, latency_ms: int) -> None:
        self._exec(
            "INSERT INTO {schema}.AGENT_RUNS (INCIDENT_ID, AGENT, STATUS, DETAIL, LATENCY_MS) VALUES (?, ?, ?, ?, ?)",
            (incident_id, agent, status, detail[:2000], int(latency_ms)),
        ).close()
        self.commit()

    # ------------------------------------------------------------------ analytics
    def category_stats(self) -> list[dict]:
        return self._rows("SELECT * FROM {schema}.V_CATEGORY_STATS ORDER BY INCIDENTS DESC")

    def top_signatures(self, limit: int = 10) -> list[dict]:
        return self._rows(
            f"SELECT * FROM {{schema}}.V_TOP_SIGNATURES ORDER BY INCIDENTS DESC, LAST_SEEN DESC FETCH FIRST {int(limit)} ROWS ONLY"
        )

    def agent_performance(self) -> list[dict]:
        return self._rows("SELECT * FROM {schema}.V_AGENT_PERFORMANCE ORDER BY AGENT")

    def draft_quality(self) -> list[dict]:
        return self._rows("SELECT * FROM {schema}.V_DRAFT_QUALITY ORDER BY CREATED_AT DESC FETCH FIRST 50 ROWS ONLY")

    def recent_incidents(self, limit: int = 25) -> list[dict]:
        return self._rows(
            "SELECT I.INCIDENT_ID, I.SOURCE_NAME, I.CATEGORY, I.CONFIDENCE, I.STATUS, I.DUPLICATE_OF,"
            " I.REDACTION_COUNT, I.CREATED_AT, D.TITLE, D.CRITIC_SCORE, D.GITHUB_URL"
            " FROM {schema}.INCIDENTS I"
            " LEFT JOIN {schema}.ISSUE_DRAFTS D ON D.INCIDENT_ID = I.INCIDENT_ID AND D.IS_FINAL = 'Y'"
            f" ORDER BY I.CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
        )

    def incident_detail(self, incident_id: int) -> dict:
        inc = self._rows(
            "SELECT INCIDENT_ID, SOURCE_NAME, CATEGORY, CONFIDENCE, STATUS, DUPLICATE_OF, ENV_JSON, CREATED_AT"
            " FROM {schema}.INCIDENTS WHERE INCIDENT_ID = ?",
            (incident_id,),
        )
        drafts = self._rows(
            "SELECT DRAFT_ID, ROUND_NO, TITLE, BODY_MD, CRITIC_SCORE, CRITIC_NOTES, GENERATED_BY, IS_FINAL, GITHUB_URL"
            " FROM {schema}.ISSUE_DRAFTS WHERE INCIDENT_ID = ? ORDER BY ROUND_NO",
            (incident_id,),
        )
        runs = self._rows(
            "SELECT AGENT, STATUS, DETAIL, LATENCY_MS, CREATED_AT FROM {schema}.AGENT_RUNS"
            " WHERE INCIDENT_ID = ? ORDER BY RUN_ID",
            (incident_id,),
        )
        evidence = self._rows(
            "SELECT LINE_NO, KIND, LABEL, LOG_LINE FROM {schema}.EVIDENCE WHERE INCIDENT_ID = ? ORDER BY LINE_NO",
            (incident_id,),
        )
        return {"incident": inc[0] if inc else None, "drafts": drafts, "runs": runs, "evidence": evidence}

    def env_breakdown(self) -> list[dict]:
        try:
            return self._rows(
                "SELECT COALESCE(CONTAINER_RUNTIME, 'unknown') AS CONTAINER_RUNTIME,"
                " COALESCE(OPERATING_SYSTEM, 'unknown') AS OPERATING_SYSTEM, COUNT(*) AS INCIDENTS"
                " FROM {schema}.V_INCIDENT_ENV GROUP BY CONTAINER_RUNTIME, OPERATING_SYSTEM ORDER BY INCIDENTS DESC"
            )
        except Exception as exc:
            log.warning("V_INCIDENT_ENV unavailable: %s", exc)
            return []

    def run_readonly(self, sql: str) -> list[dict]:
        """Executes an already-validated SELECT (see sql_agent.validate_sql)."""
        try:
            return self._rows(sql)
        finally:
            self.conn.rollback()
