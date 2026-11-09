"""All SQL lives here. Every statement is parameterized; multi-step writes share one transaction."""
import json
from decimal import Decimal
from typing import Any, Optional

from app.database.db2 import Db2Pool


def _txt(v: Any) -> Any:
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).decode("utf-8")
    if hasattr(v, "read"):
        return v.read()
    return v


def _clean(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {k: (float(v) if isinstance(v, Decimal) else _txt(v)) for k, v in row.items()}


def _new_id(cur) -> int:
    cur.execute("SELECT IDENTITY_VAL_LOCAL() FROM SYSIBM.SYSDUMMY1")
    return int(cur.fetchone()[0])


class Repo:
    def __init__(self, pool: Db2Pool):
        self.pool = pool

    # ---- users
    def create_user(self, username: str, email: str, pw_hash: str, role: str = "RESEARCHER") -> int:
        with self.pool.transaction() as cur:
            cur.execute("INSERT INTO USERS (USERNAME, EMAIL, PASSWORD_HASH, ROLE) VALUES (?,?,?,?)",
                        (username, email, pw_hash, role))
            uid = _new_id(cur)
            cur.execute("INSERT INTO AUDIT_LOGS (USER_ID, EVENT_TYPE, DETAILS) VALUES (?,?,?)",
                        (uid, "USER_REGISTERED", username))
            return uid

    def user_by_username(self, username: str):
        return _clean(self.pool.fetch_one("SELECT user_id, username, email, password_hash, role, is_active FROM USERS WHERE USERNAME = ?", (username,)))

    def user_by_id(self, uid: int):
        return _clean(self.pool.fetch_one("SELECT user_id, username, email, role, is_active FROM USERS WHERE USER_ID = ?", (uid,)))

    def count_users(self) -> int:
        return int(self.pool.fetch_one("SELECT COUNT(*) AS n FROM USERS")["n"])

    def audit(self, user_id: Optional[int], event: str, details: str = "") -> None:
        self.pool.execute("INSERT INTO AUDIT_LOGS (USER_ID, EVENT_TYPE, DETAILS) VALUES (?,?,?)", (user_id, event, details[:1000]))

    # ---- datasets
    def create_dataset(self, owner_id: int, name: str, source: str, storage_ref: str, target: Optional[str], analysis: dict) -> int:
        with self.pool.transaction() as cur:
            cur.execute("INSERT INTO DATASETS (OWNER_ID, NAME, SOURCE, STORAGE_REF, TARGET_COLUMN, STATUS) VALUES (?,?,?,?,?,?)",
                        (owner_id, name, source, storage_ref, target, "ANALYZED"))
            did = _new_id(cur)
            cur.execute("INSERT INTO DATASET_METADATA (DATASET_ID, ROW_COUNT, COLUMN_COUNT, DUPLICATE_ROWS, SCHEMA_JSON, MISSING_JSON, STATS_JSON) VALUES (?,?,?,?,?,?,?)",
                        (did, analysis["rows"], analysis["columns"], analysis["duplicate_rows"],
                         json.dumps(analysis["schema"]), json.dumps(analysis["missing_values"]), json.dumps(analysis["stats"])))
            cur.execute("INSERT INTO AUDIT_LOGS (USER_ID, EVENT_TYPE, DETAILS) VALUES (?,?,?)", (owner_id, "DATASET_UPLOADED", name))
            return did

    def list_datasets(self, owner_id: Optional[int], limit: int = 50, offset: int = 0):
        base = ("SELECT d.dataset_id, d.name, d.source, d.target_column, d.status, d.uploaded_at, m.row_count, m.column_count, m.duplicate_rows "
                "FROM DATASETS d JOIN DATASET_METADATA m ON m.DATASET_ID = d.DATASET_ID ")
        if owner_id is None:
            rows = self.pool.fetch_all(base + "ORDER BY d.UPLOADED_AT DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", (offset, limit))
        else:
            rows = self.pool.fetch_all(base + "WHERE d.OWNER_ID = ? ORDER BY d.UPLOADED_AT DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", (owner_id, offset, limit))
        return [_clean(r) for r in rows]

    def get_dataset(self, dataset_id: int):
        return _clean(self.pool.fetch_one("SELECT dataset_id, owner_id, name, storage_ref, target_column, status FROM DATASETS WHERE DATASET_ID = ?", (dataset_id,)))

    def delete_dataset(self, dataset_id: int, user_id: int) -> None:
        with self.pool.transaction() as cur:
            cur.execute("DELETE FROM DATASETS WHERE DATASET_ID = ?", (dataset_id,))
            cur.execute("INSERT INTO AUDIT_LOGS (USER_ID, EVENT_TYPE, DETAILS) VALUES (?,?,?)", (user_id, "DATASET_DELETED", str(dataset_id)))

    # ---- experiments
    def save_preprocessing(self, dataset_id: int, config: dict) -> int:
        with self.pool.transaction() as cur:
            cur.execute("INSERT INTO PREPROCESSING_CONFIGS (DATASET_ID, CONFIG_JSON, RANDOM_SEED, TEST_SIZE) VALUES (?,?,?,?)",
                        (dataset_id, json.dumps(config), config["seed"], config["test_size"]))
            return _new_id(cur)

    def create_experiment(self, dataset_id: int, config_id: int, family: str, algorithm: str, params: dict) -> int:
        with self.pool.transaction() as cur:
            cur.execute("INSERT INTO EXPERIMENTS (DATASET_ID, CONFIG_ID, MODEL_FAMILY, ALGORITHM, PARAMS_JSON, STATUS) VALUES (?,?,?,?,?,?)",
                        (dataset_id, config_id, family, algorithm, json.dumps(params), "RUNNING"))
            return _new_id(cur)

    def finish_experiment(self, experiment_id: int, result: Optional[dict], error: Optional[str] = None) -> None:
        with self.pool.transaction() as cur:
            if result is not None:
                extra = {k: result[k] for k in ("quantum", "algorithm") if k in result}
                cur.execute("INSERT INTO MODEL_RESULTS (EXPERIMENT_ID, ACCURACY, PRECISION_SCORE, RECALL, F1_SCORE, ROC_AUC, CONFUSION_JSON, TRAIN_SECONDS, INFER_SECONDS, BACKEND_INFO, EXTRA_JSON) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (experiment_id, result["accuracy"], result["precision"], result["recall"], result["f1"], result["roc_auc"],
                             json.dumps(result["confusion"]), result["train_seconds"], result["infer_seconds"],
                             result["backend_info"], json.dumps(extra)))
                cur.execute("UPDATE EXPERIMENTS SET STATUS='COMPLETED', FINISHED_AT=CURRENT TIMESTAMP WHERE EXPERIMENT_ID = ?", (experiment_id,))
            else:
                cur.execute("UPDATE EXPERIMENTS SET STATUS='FAILED', ERROR_MESSAGE=?, FINISHED_AT=CURRENT TIMESTAMP WHERE EXPERIMENT_ID = ?", ((error or "")[:1000], experiment_id))

    def get_experiment(self, experiment_id: int):
        return _clean(self.pool.fetch_one(
            "SELECT e.experiment_id, e.dataset_id, e.model_family, e.algorithm, e.status, e.error_message, e.created_at, e.finished_at, "
            "r.accuracy, r.precision_score, r.recall, r.f1_score, r.roc_auc, r.confusion_json, r.train_seconds, r.infer_seconds, r.backend_info, r.extra_json "
            "FROM EXPERIMENTS e LEFT JOIN MODEL_RESULTS r ON r.EXPERIMENT_ID = e.EXPERIMENT_ID WHERE e.EXPERIMENT_ID = ?", (experiment_id,)))

    def comparison(self, dataset_id: int):
        rows = self.pool.fetch_all(
            "SELECT e.experiment_id, e.model_family, e.algorithm, e.created_at, r.accuracy, r.precision_score, r.recall, r.f1_score, r.roc_auc, r.train_seconds, r.infer_seconds, r.backend_info "
            "FROM EXPERIMENTS e JOIN MODEL_RESULTS r ON r.EXPERIMENT_ID = e.EXPERIMENT_ID "
            "WHERE e.DATASET_ID = ? AND e.STATUS = 'COMPLETED' ORDER BY r.F1_SCORE DESC", (dataset_id,))
        return [_clean(r) for r in rows]

    # ---- agents and reports
    def create_agent_run(self, dataset_id: int, user_id: int, mode: str) -> int:
        with self.pool.transaction() as cur:
            cur.execute("INSERT INTO AGENT_RUNS (DATASET_ID, STARTED_BY, RUN_MODE, STATUS) VALUES (?,?,?,'RUNNING')", (dataset_id, user_id, mode))
            return _new_id(cur)

    def finish_agent_run(self, run_id: int, status: str, error: Optional[str] = None) -> None:
        self.pool.execute("UPDATE AGENT_RUNS SET STATUS=?, ERROR_MESSAGE=?, FINISHED_AT=CURRENT TIMESTAMP WHERE RUN_ID = ?",
                          (status, (error or "")[:1000] or None, run_id))

    def log_activity(self, run_id: int, agent: str, tool: str, status: str, input_ref: str = "",
                     output_summary: str = "", error: Optional[str] = None) -> None:
        self.pool.execute("INSERT INTO AGENT_ACTIVITIES (RUN_ID, AGENT_NAME, TOOL_NAME, STATUS, INPUT_REF, OUTPUT_SUMMARY, ERROR_MESSAGE) VALUES (?,?,?,?,?,?,?)",
                          (run_id, agent, tool, status, input_ref[:500], output_summary[:20000], (error or "")[:1000] or None))

    def get_run(self, run_id: int):
        return _clean(self.pool.fetch_one(
            "SELECT r.run_id, r.dataset_id, r.started_by, r.run_mode AS mode, r.status, r.error_message, r.started_at, r.finished_at, d.owner_id "
            "FROM AGENT_RUNS r JOIN DATASETS d ON d.DATASET_ID = r.DATASET_ID WHERE r.RUN_ID = ?", (run_id,)))

    def list_runs(self, owner_id: Optional[int], limit: int = 50):
        q = ("SELECT r.run_id, r.dataset_id, r.run_mode AS mode, r.status, r.started_at, r.finished_at FROM AGENT_RUNS r "
             "JOIN DATASETS d ON d.DATASET_ID = r.DATASET_ID ")
        if owner_id is None:
            rows = self.pool.fetch_all(q + "ORDER BY r.STARTED_AT DESC FETCH FIRST ? ROWS ONLY", (limit,))
        else:
            rows = self.pool.fetch_all(q + "WHERE d.OWNER_ID = ? ORDER BY r.STARTED_AT DESC FETCH FIRST ? ROWS ONLY", (owner_id, limit))
        return [_clean(r) for r in rows]

    def activities(self, run_id: int):
        return [_clean(r) for r in self.pool.fetch_all(
            "SELECT activity_id, agent_name, tool_name, status, input_ref, output_summary, error_message, created_at "
            "FROM AGENT_ACTIVITIES WHERE RUN_ID = ? ORDER BY ACTIVITY_ID", (run_id,))]

    def save_report(self, run_id: int, dataset_id: int, title: str, body_md: str, status: str = "FINAL") -> int:
        with self.pool.transaction() as cur:
            cur.execute("INSERT INTO RESEARCH_REPORTS (RUN_ID, DATASET_ID, TITLE, BODY_MD, STATUS) VALUES (?,?,?,?,?)",
                        (run_id, dataset_id, title[:250], body_md, status))
            return _new_id(cur)

    def get_report(self, report_id: int):
        return _clean(self.pool.fetch_one(
            "SELECT p.report_id, p.run_id, p.dataset_id, p.title, p.body_md, p.status, p.created_at, d.owner_id "
            "FROM RESEARCH_REPORTS p JOIN DATASETS d ON d.DATASET_ID = p.DATASET_ID WHERE p.REPORT_ID = ?", (report_id,)))

    def list_reports(self, owner_id: Optional[int], limit: int = 50):
        q = ("SELECT p.report_id, p.run_id, p.dataset_id, p.title, p.status, p.created_at FROM RESEARCH_REPORTS p "
             "JOIN DATASETS d ON d.DATASET_ID = p.DATASET_ID ")
        if owner_id is None:
            rows = self.pool.fetch_all(q + "ORDER BY p.CREATED_AT DESC FETCH FIRST ? ROWS ONLY", (limit,))
        else:
            rows = self.pool.fetch_all(q + "WHERE d.OWNER_ID = ? ORDER BY p.CREATED_AT DESC FETCH FIRST ? ROWS ONLY", (owner_id, limit))
        return [_clean(r) for r in rows]
