import os
import threading
from datetime import datetime, timezone


class Db2UnavailableError(RuntimeError):
    pass


class Db2Store:
    def __init__(self):
        self.host = os.environ.get("DB2_HOST", "localhost")
        self.port = os.environ.get("DB2_PORT", "5000")
        self.database = os.environ.get("DB2_DATABASE", "TESTDB")
        self.user = os.environ.get("DB2_USER", "db2inst1")
        self.password = os.environ.get("DB2_PASSWORD", "")
        self._driver_error = None

    @property
    def is_configured(self):
        return bool(self.host and self.port and self.database and self.user and self.password)

    def _connect(self):
        if not self.is_configured:
            raise Db2UnavailableError(
                "Set DB2_PASSWORD and verify DB2_HOST, DB2_PORT, DB2_DATABASE, and DB2_USER."
            )
        try:
            import ibm_db_dbi
        except (ImportError, OSError) as exc:
            raise Db2UnavailableError(
                "The IBM Db2 driver could not be loaded. Install a compatible driver build "
                "or run with REQUIRE_DB2=false to use local memory storage."
            ) from exc

        self._driver_error = ibm_db_dbi.Error
        dsn = (
            f"DATABASE={self.database};HOSTNAME={self.host};"
            f"PORT={self.port};PROTOCOL=TCPIP;"
        )
        try:
            return ibm_db_dbi.connect(dsn, self.user, self.password)
        except (ibm_db_dbi.Error, OSError) as exc:
            raise Db2UnavailableError(
                "Could not connect to IBM Db2. Check the connection settings and server status."
            ) from exc

    def initialize(self):
        statements = (
            """CREATE TABLE AETHEL_PROFILE (
                SESSION_ID VARCHAR(32) NOT NULL PRIMARY KEY,
                DISPLAY_NAME VARCHAR(60) NOT NULL,
                TIME_ZONE VARCHAR(80) NOT NULL,
                CHECK_INS_ENABLED SMALLINT NOT NULL,
                CREATED_AT TIMESTAMP NOT NULL
            )""",
            """CREATE TABLE AETHEL_TASK (
                TASK_ID VARCHAR(32) NOT NULL PRIMARY KEY,
                SESSION_ID VARCHAR(32) NOT NULL,
                TASK_TYPE VARCHAR(20) NOT NULL,
                DESCRIPTION VARCHAR(160) NOT NULL,
                DUE_AT TIMESTAMP NOT NULL,
                STATUS VARCHAR(16) NOT NULL,
                NOTIFIED_AT TIMESTAMP
            )""",
            """CREATE TABLE AETHEL_LOG (
                LOG_ID BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                SESSION_ID VARCHAR(32) NOT NULL,
                SPEAKER VARCHAR(16) NOT NULL,
                MESSAGE VARCHAR(4000) NOT NULL,
                CREATED_AT TIMESTAMP NOT NULL
            )""",
            """CREATE TABLE AETHEL_REVIEW (
                REVIEW_ID VARCHAR(32) NOT NULL PRIMARY KEY,
                SESSION_ID VARCHAR(32) NOT NULL,
                DISPLAY_NAME VARCHAR(36) NOT NULL,
                MESSAGE VARCHAR(320) NOT NULL,
                CREATED_AT TIMESTAMP NOT NULL
            )""",
        )
        connection = self._connect()
        try:
            cursor = connection.cursor()
            for statement in statements:
                try:
                    cursor.execute(statement)
                except self._driver_error as exc:
                    if "-601" not in str(exc) and "42710" not in str(exc):
                        raise
            connection.commit()
        except self._driver_error as exc:
            raise Db2UnavailableError(
                "Could not initialize the Aethel Db2 tables. Check database permissions."
            ) from exc
        finally:
            connection.close()

    def ping(self):
        def operation(cursor):
            cursor.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
            return cursor.fetchone() == (1,)

        return self._run(operation)

    def _run(self, operation):
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                result = operation(cursor)
                connection.commit()
                return result
            except self._driver_error as exc:
                connection.rollback()
                raise Db2UnavailableError(
                    "Db2 could not complete the request. Initialize the Aethel tables and retry."
                ) from exc
        finally:
            connection.close()

    def get_profile(self, session_id):
        def operation(cursor):
            cursor.execute(
                "SELECT DISPLAY_NAME, TIME_ZONE, CHECK_INS_ENABLED "
                "FROM AETHEL_PROFILE WHERE SESSION_ID = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "name": row[0],
                "time_zone": row[1],
                "check_ins_enabled": bool(row[2]),
            }

        return self._run(operation)

    def save_profile(self, session_id, profile):
        def operation(cursor):
            cursor.execute(
                "UPDATE AETHEL_PROFILE SET DISPLAY_NAME = ?, TIME_ZONE = ?, "
                "CHECK_INS_ENABLED = ? WHERE SESSION_ID = ?",
                (
                    profile["name"],
                    profile["time_zone"],
                    int(profile["check_ins_enabled"]),
                    session_id,
                ),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO AETHEL_PROFILE "
                    "(SESSION_ID, DISPLAY_NAME, TIME_ZONE, CHECK_INS_ENABLED, CREATED_AT) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        session_id,
                        profile["name"],
                        profile["time_zone"],
                        int(profile["check_ins_enabled"]),
                        datetime.now(timezone.utc).replace(tzinfo=None),
                    ),
                )

        self._run(operation)

    def list_tasks(self, session_id):
        def operation(cursor):
            cursor.execute(
                "SELECT TASK_ID, TASK_TYPE, DESCRIPTION, DUE_AT, STATUS "
                "FROM AETHEL_TASK WHERE SESSION_ID = ? "
                "ORDER BY DUE_AT ASC FETCH FIRST 100 ROWS ONLY",
                (session_id,),
            )
            return [
                {
                    "id": row[0],
                    "task_type": row[1],
                    "description": row[2],
                    "due_at": self._utc_iso(row[3]),
                    "status": row[4],
                }
                for row in cursor.fetchall()
            ]

        return self._run(operation)

    def create_task(self, session_id, task):
        def operation(cursor):
            cursor.execute(
                "INSERT INTO AETHEL_TASK "
                "(TASK_ID, SESSION_ID, TASK_TYPE, DESCRIPTION, DUE_AT, STATUS) "
                "VALUES (?, ?, ?, ?, ?, 'pending')",
                (
                    task["id"],
                    session_id,
                    task["task_type"],
                    task["description"],
                    task["due_at"].astimezone(timezone.utc).replace(tzinfo=None),
                ),
            )

        self._run(operation)

    def claim_due_tasks(self, session_id):
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        def operation(cursor):
            cursor.execute(
                "SELECT TASK_ID, TASK_TYPE, DESCRIPTION, DUE_AT FROM AETHEL_TASK "
                "WHERE SESSION_ID = ? AND STATUS = 'pending' AND NOTIFIED_AT IS NULL "
                "AND DUE_AT <= ? ORDER BY DUE_AT ASC",
                (session_id, now),
            )
            rows = cursor.fetchall()
            claimed = []
            for row in rows:
                cursor.execute(
                    "UPDATE AETHEL_TASK SET NOTIFIED_AT = ? "
                    "WHERE TASK_ID = ? AND SESSION_ID = ? AND NOTIFIED_AT IS NULL",
                    (now, row[0], session_id),
                )
                if cursor.rowcount == 1:
                    claimed.append(
                        {
                            "id": row[0],
                            "task_type": row[1],
                            "description": row[2],
                            "due_at": self._utc_iso(row[3]),
                        }
                    )
            return claimed

        return self._run(operation)

    def complete_task(self, session_id, task_id):
        def operation(cursor):
            cursor.execute(
                "UPDATE AETHEL_TASK SET STATUS = 'completed' "
                "WHERE TASK_ID = ? AND SESSION_ID = ? AND STATUS = 'pending'",
                (task_id, session_id),
            )
            return cursor.rowcount == 1

        return self._run(operation)

    def get_history(self, session_id):
        def operation(cursor):
            cursor.execute(
                "SELECT SPEAKER, MESSAGE, CREATED_AT FROM AETHEL_LOG "
                "WHERE SESSION_ID = ? ORDER BY CREATED_AT DESC, LOG_ID DESC "
                "FETCH FIRST 30 ROWS ONLY",
                (session_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "role": row[0],
                    "content": row[1],
                    "created_at": self._utc_iso(row[2]),
                }
                for row in reversed(rows)
            ]

        return self._run(operation)

    def add_turn(self, session_id, user_message, assistant_message):
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        def operation(cursor):
            cursor.executemany(
                "INSERT INTO AETHEL_LOG (SESSION_ID, SPEAKER, MESSAGE, CREATED_AT) "
                "VALUES (?, ?, ?, ?)",
                (
                    (session_id, "user", user_message, now),
                    (session_id, "assistant", assistant_message, now),
                ),
            )

        self._run(operation)

    def list_reviews(self):
        def operation(cursor):
            cursor.execute(
                "SELECT REVIEW_ID, DISPLAY_NAME, MESSAGE, CREATED_AT "
                "FROM AETHEL_REVIEW ORDER BY CREATED_AT DESC "
                "FETCH FIRST 40 ROWS ONLY"
            )
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "message": row[2],
                    "created_at": self._utc_iso(row[3]),
                }
                for row in cursor.fetchall()
            ]

        return self._run(operation)

    def create_review(self, session_id, review):
        def operation(cursor):
            cursor.execute(
                "INSERT INTO AETHEL_REVIEW "
                "(REVIEW_ID, SESSION_ID, DISPLAY_NAME, MESSAGE, CREATED_AT) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    review["id"],
                    session_id,
                    review["name"],
                    review["message"],
                    datetime.fromisoformat(review["created_at"]).astimezone(timezone.utc).replace(tzinfo=None),
                ),
            )

        self._run(operation)

    @staticmethod
    def _utc_iso(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")


class LocalMemoryStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._profiles = {}
        self._tasks = {}
        self._history = {}
        self._reviews = []

    def get_profile(self, session_id):
        with self._lock:
            profile = self._profiles.get(session_id)
            return dict(profile) if profile is not None else None

    def save_profile(self, session_id, profile):
        with self._lock:
            self._profiles[session_id] = dict(profile)

    def list_tasks(self, session_id):
        with self._lock:
            tasks = self._tasks.get(session_id, {}).values()
            return [
                {key: value for key, value in task.items() if key != "notified"}
                for task in sorted(tasks, key=lambda item: item["due_at"])[:100]
            ]

    def create_task(self, session_id, task):
        with self._lock:
            self._tasks.setdefault(session_id, {})[task["id"]] = {
                **task,
                "status": "pending",
                "notified": False,
            }

    def claim_due_tasks(self, session_id):
        now = datetime.now(timezone.utc)
        with self._lock:
            due_tasks = sorted(
                (
                    task
                    for task in self._tasks.get(session_id, {}).values()
                    if task["status"] == "pending"
                    and not task["notified"]
                    and task["due_at"] <= now
                ),
                key=lambda task: task["due_at"],
            )
            claimed = []
            for task in due_tasks:
                task["notified"] = True
                claimed.append(
                    {
                        "id": task["id"],
                        "task_type": task["task_type"],
                        "description": task["description"],
                        "due_at": self._utc_iso(task["due_at"]),
                    }
                )
            return claimed

    def complete_task(self, session_id, task_id):
        with self._lock:
            task = self._tasks.get(session_id, {}).get(task_id)
            if task is None or task["status"] != "pending":
                return False
            task["status"] = "completed"
            return True

    def get_history(self, session_id):
        with self._lock:
            return [dict(entry) for entry in self._history.get(session_id, [])[-30:]]

    def add_turn(self, session_id, user_message, assistant_message):
        now = self._utc_iso(datetime.now(timezone.utc))
        with self._lock:
            history = self._history.setdefault(session_id, [])
            history.extend(
                (
                    {"role": "user", "content": user_message, "created_at": now},
                    {"role": "assistant", "content": assistant_message, "created_at": now},
                )
            )
            del history[:-30]

    def list_reviews(self):
        with self._lock:
            return [dict(review) for review in self._reviews[-40:][::-1]]

    def create_review(self, session_id, review):
        with self._lock:
            self._reviews.append(dict(review))
            del self._reviews[:-40]

    @staticmethod
    def _utc_iso(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
