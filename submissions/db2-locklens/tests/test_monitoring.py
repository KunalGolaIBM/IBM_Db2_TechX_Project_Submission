from helpers import CONN_COLS, LOCKS_COLS, WAIT_COLS, ScriptedExecutor, permission_error

from locklens.db.monitoring import MonitoringClient, build_select
from locklens.errors import Db2QueryError


def test_build_select_uses_only_available_columns_and_hex_lock_names():
    sql = build_select(["MEMBER", "LOCK_NAME", "NOT_A_REAL_COLUMN"], ["MEMBER", "LOCK_NAME"],
                       from_clause="TABLE(MON_GET_LOCKS(NULL, -2)) AS T", max_rows=50)
    assert "NOT_A_REAL_COLUMN" not in sql
    assert "HEX(T.LOCK_NAME) AS LOCK_NAME_HEX" in sql and sql.endswith("FETCH FIRST 50 ROWS ONLY")
    assert build_select(["X"], ["Y"], from_clause="T") is None


def test_collect_parses_documented_columns_and_ignores_unknown_future_ones():
    ex = (ScriptedExecutor()
          .on("MON_GET_LOCKS", [{"APPLICATION_HANDLE": 7, "LOCK_NAME_HEX": "AA11", "LOCK_STATUS": "G",
                                 "LOCK_MODE": "X", "LOCK_OBJECT_TYPE": "ROW", "LOCK_COUNT": 1, "MEMBER": 0}])
          .on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9, "HLD_APPLICATION_HANDLE": 7,
                                         "LOCK_NAME_HEX": "AA11", "LOCK_MODE_REQUESTED": "X",
                                         "LOCK_WAIT_START_TIME": "2026-11-10-10.00.00.000000", "WAIT_SECONDS": 12}])
          .on("MON_GET_CONNECTION", [{"APPLICATION_HANDLE": 7, "APPLICATION_NAME": "db2bp",
                                      "SYSTEM_AUTH_ID": "DB2INST1", "WORKLOAD_OCCURRENCE_STATE": "UOWWAIT"},
                                     {"APPLICATION_HANDLE": 999, "APPLICATION_NAME": "other"}])
          .on("MON_FORMAT_LOCK_NAME", [{"NAME": "TABSCHEMA", "VALUE": "LOCKLENS_DEMO"},
                                       {"NAME": "TABNAME", "VALUE": "ACCOUNTS"},
                                       {"NAME": "LOCK_OBJECT_TYPE", "VALUE": "ROW"}]))
    snap = MonitoringClient(ex).collect()
    assert snap.locks[0].application_handle == 7 and snap.locks[0].lock_status == "G"
    w = snap.waits[0]
    assert (w.req_application_handle, w.hld_application_handle, w.wait_seconds) == (9, 7, 12)
    assert snap.sessions[7].workload_state == "UOWWAIT" and 999 not in snap.sessions
    assert snap.resources["AA11"].label == "ROW on LOCKLENS_DEMO.ACCOUNTS"
    assert not snap.notes
    selects = [c[0] for c in ex.calls if "FROM TABLE(MON_GET_CONNECTION" in c[0] and "1=0" not in c[0]]
    assert "SOMETHING_NEW_IN_FUTURE" not in selects[0]          # never select unknown columns


def test_lock_names_are_passed_as_bound_parameters_not_interpolated():
    ex = (ScriptedExecutor().on("MON_GET_LOCKS", [])
          .on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9, "HLD_APPLICATION_HANDLE": 7, "LOCK_NAME_HEX": "AA11"}])
          .on("MON_GET_CONNECTION", []).on("MON_FORMAT_LOCK_NAME", []))
    MonitoringClient(ex).collect()
    fmt = [c for c in ex.calls if "MON_FORMAT_LOCK_NAME" in c[0]]
    assert fmt and "AA11" not in fmt[0][0] and fmt[0][1] == ("AA11",)


def test_malformed_lock_name_is_never_sent_to_the_database():
    ex = (ScriptedExecutor().on("MON_GET_LOCKS", [])
          .on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9, "LOCK_NAME_HEX": "'; DROP TABLE X;--"}])
          .on("MON_GET_CONNECTION", []))
    MonitoringClient(ex).collect()
    assert not [c for c in ex.calls if "MON_FORMAT_LOCK_NAME" in c[0]]


def test_missing_privilege_produces_an_explanatory_note_not_fake_data():
    ex = ScriptedExecutor().on("MON_GET_LOCKS", permission_error()).on("MON_GET_APPL_LOCKWAIT", permission_error())
    snap = MonitoringClient(ex).collect()
    assert not snap.locks and not snap.waits and not snap.locks_available and not snap.waits_available
    msgs = " ".join(n.message for n in snap.notes)
    assert "Not authorized" in msgs and "EXECUTE" in msgs and all(n.level == "error" for n in snap.notes)


def test_function_missing_on_old_or_limited_server_is_explained():
    ex = ScriptedExecutor(columns={"MON_GET_LOCKS": None, "MON_GET_APPL_LOCKWAIT": WAIT_COLS, "MON_GET_CONNECTION": CONN_COLS})
    ex.on("MON_GET_APPL_LOCKWAIT", [])
    snap = MonitoringClient(ex).collect()
    assert not snap.locks_available and snap.waits_available
    assert any("not available on this Db2 server" in n.message for n in snap.notes)


def test_missing_holder_column_is_reported_to_user():
    cols = [c for c in WAIT_COLS if c != "HLD_APPLICATION_HANDLE"]
    ex = ScriptedExecutor(columns={"MON_GET_LOCKS": LOCKS_COLS, "MON_GET_APPL_LOCKWAIT": cols, "MON_GET_CONNECTION": CONN_COLS})
    ex.on("MON_GET_LOCKS", []).on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9}]).on("MON_GET_CONNECTION", [])
    snap = MonitoringClient(ex).collect()
    assert snap.waits[0].hld_application_handle is None
    assert any("holding application" in n.message for n in snap.notes)


def test_connection_enrichment_denied_degrades_to_warning_only():
    ex = (ScriptedExecutor().on("MON_GET_LOCKS", [])
          .on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9, "HLD_APPLICATION_HANDLE": 7}])
          .on("MON_GET_CONNECTION", permission_error()))
    snap = MonitoringClient(ex).collect()
    assert snap.waits and not snap.sessions
    assert any(n.level == "warning" and "MON_GET_CONNECTION" in n.message for n in snap.notes)


def test_column_discovery_is_cached_between_collections():
    ex = ScriptedExecutor().on("MON_GET_LOCKS", []).on("MON_GET_APPL_LOCKWAIT", [])
    client = MonitoringClient(ex)
    client.collect(); client.collect()
    probes = [c for c in ex.calls if "WHERE 1=0" in c[0]]
    assert len(probes) == 2         # locks + lockwait once each, not once per collect


def test_row_limit_truncation_is_flagged():
    rows = [{"APPLICATION_HANDLE": i, "LOCK_NAME_HEX": "AA", "LOCK_STATUS": "G"} for i in range(10)]
    ex = ScriptedExecutor().on("MON_GET_LOCKS", rows).on("MON_GET_APPL_LOCKWAIT", [])
    snap = MonitoringClient(ex, max_rows=10).collect()
    assert any("truncated" in n.message for n in snap.notes)


def test_lockwait_falls_back_to_three_argument_signature():
    from locklens.errors import Db2QueryError

    class ThreeArgOnly(ScriptedExecutor):
        def query_with_columns(self, sql, params=()):
            if "MON_GET_APPL_LOCKWAIT(NULL, -2))" in sql:         # two-argument form rejected
                raise Db2QueryError("SQL0440N no matching routine", 440)
            return super().query_with_columns(sql, params)

    ex = ThreeArgOnly().on("MON_GET_LOCKS", []).on("MON_GET_APPL_LOCKWAIT",
                                                  [{"REQ_APPLICATION_HANDLE": 9, "HLD_APPLICATION_HANDLE": 7}])
    snap = MonitoringClient(ex).collect()
    assert snap.waits_available and snap.waits[0].hld_application_handle == 7
    used = [c[0] for c in ex.calls if "FROM TABLE(MON_GET_APPL_LOCKWAIT" in c[0] and "1=0" not in c[0]]
    assert "MON_GET_APPL_LOCKWAIT(NULL, -2, NULL)" in used[0]


def test_permission_error_during_discovery_is_not_retried_with_other_signatures():
    ex = ScriptedExecutor().on("MON_GET_LOCKS", [])
    calls = {"n": 0}
    orig = ex.query_with_columns

    def counting(sql, params=()):
        if "MON_GET_APPL_LOCKWAIT" in sql:
            calls["n"] += 1
            raise permission_error()
        return orig(sql, params)

    ex.query_with_columns = counting
    snap = MonitoringClient(ex).collect()
    assert calls["n"] == 1 and not snap.waits_available


def test_lock_name_decoding_falls_back_to_binary_join_form():
    # Rules match in registration order, so the more specific decode rules come first.
    ex = (ScriptedExecutor()
          .on("CAST(? AS VARCHAR(64))", [])                          # hex form yields nothing
          .on("HEX(L.LOCK_NAME) = ?", [{"NAME": "TABNAME", "VALUE": "ACCOUNTS"}])
          .on("MON_GET_LOCKS", [])
          .on("MON_GET_APPL_LOCKWAIT", [{"REQ_APPLICATION_HANDLE": 9, "HLD_APPLICATION_HANDLE": 7,
                                         "LOCK_NAME_HEX": "AA11"}])
          .on("MON_GET_CONNECTION", []))
    snap = MonitoringClient(ex).collect()
    assert snap.resources["AA11"].table_name == "ACCOUNTS"
    assert all("AA11" not in c[0] for c in ex.calls)                # still bound, never interpolated
