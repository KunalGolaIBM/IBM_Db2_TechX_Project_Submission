"""Integration tests. These need a live Db2 and skip cleanly without one.

They assert the properties PortProof's claims rest on:

* ``PREPARE`` really is a server-side compile (the deferred-prepare trap)
* the least-privilege user genuinely cannot write the ledger
* the stored procedures record what they are told to
* Db2 computes the certificate hash, not Python
* the engine maintains the MQT and the temporal history by itself
* the translator's silent failures are real, and the repair loop fixes them
* the proof engine finds the known divergence and does not invent others
"""
from __future__ import annotations

import uuid

import pytest

from src import db, translate
from src.corpus import BASE, CORPUS, VARIANTS

# conftest.pytest_collection_modifyitems turns this marker into a clean skip
# when no database is reachable, so ``pytest -q`` still passes on a bare laptop.
pytestmark = pytest.mark.db2


# --------------------------------------------------------------------------
# the compile oracle
# --------------------------------------------------------------------------
def test_prepare_accepts_valid_sql(owner_conn):
    assert db.compile_check(owner_conn, "SELECT 1 FROM SYSIBM.SYSDUMMY1").ok


def test_prepare_rejects_an_unknown_table(owner_conn):
    result = db.compile_check(owner_conn, "SELECT x FROM definitely_not_a_table_42")
    assert not result.ok
    assert result.sqlcode == -204


def test_prepare_is_a_real_server_side_compile(owner_conn):
    """Regression for the deferred-prepare trap.

    With the Db2 CLI default, PREPARE is held on the client until execution, so
    ``prepare()`` returns success for SQL the server would reject. PortProof
    disables it in the DSN; if that ever regresses, every verdict silently
    becomes meaningless, so it is asserted here.
    """
    for bad in (
        "SELECT * FROM customers WHERE name ILIKE '%x%'",
        "SELECT payload->>'city' FROM events",
        "SELECT nope FROM definitely_not_a_table_42",
    ):
        assert not db.compile_check(owner_conn, bad).ok, bad


def test_ensure_fixture_schema_is_enough_to_resolve_unqualified_names(owner_conn):
    """Regression: the oracle's name-resolution context must be explicit.

    The corpus is unqualified SQL (``FROM orders``), so a wrong CURRENT SCHEMA
    turns valid SQL into SQLCODE -204 and PortProof reports a 'silent failure'
    that never happened. This used to depend on ``Db2Target.__init__`` running
    first; any caller that compiled before building a target got false alarms.
    """
    from src.counterexample import FIXTURE_SCHEMA, ensure_fixture_schema

    db.execute(owner_conn, "SET CURRENT SCHEMA PPOWN")
    ensure_fixture_schema(owner_conn)

    assert db.fetch_one(owner_conn, "VALUES CURRENT SCHEMA")[0].strip() == FIXTURE_SCHEMA
    result = db.compile_check(
        owner_conn, "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id"
    )
    assert result.ok, f"unqualified fixture SQL did not compile: {result.message}"


def test_prepare_does_not_execute(owner_conn, loaded_target):
    """A statement that compiles must not have run."""
    before = db.fetch_one(owner_conn, "SELECT COUNT(*) FROM PPTEST.customers")[0]
    assert db.compile_check(owner_conn, "DELETE FROM PPTEST.customers").ok
    after = db.fetch_one(owner_conn, "SELECT COUNT(*) FROM PPTEST.customers")[0]
    assert before == after


# --------------------------------------------------------------------------
# least privilege
# --------------------------------------------------------------------------
def test_runtime_user_cannot_insert_into_the_ledger(app_conn):
    with pytest.raises(db.Db2Error) as caught:
        db.execute(
            app_conn,
            "INSERT INTO PORTPROOF.STATEMENT (CASE_NAME, SRC_DIALECT, SRC_SQL, STATUS) "
            "VALUES (?, ?, ?, ?)",
            ("test/forbidden", "postgres", "SELECT 1", "COMPILES"),
        )
    assert caught.value.sqlcode == -551


def test_runtime_user_cannot_create_tables(app_conn):
    with pytest.raises(db.Db2Error):
        db.execute(app_conn, "CREATE TABLE PORTPROOF.SHOULD_NOT_EXIST (A INT)")


def test_runtime_user_can_read_the_ledger(app_conn):
    db.fetch_all(app_conn, "SELECT COUNT(*) FROM PORTPROOF.STATEMENT")


# --------------------------------------------------------------------------
# SQL PL procedures and the in-engine certificate
# --------------------------------------------------------------------------
def test_record_translation_then_verdict_round_trip(app_conn):
    case = "test/roundtrip"
    out = db.call_proc(
        app_conn,
        "PORTPROOF.RECORD_TRANSLATION",
        (case, "postgres", "SELECT 1", "SELECT 1 FROM SYSIBM.SYSDUMMY1", "COMPILES", None, None, "{}", 1, 0),
    )
    stmt_id = int(out[-1])
    assert stmt_id > 0

    verdict = db.call_proc(
        app_conn, "PORTPROOF.RECORD_VERDICT", (stmt_id, "COMPILE", "PASS", 6, '{"t":1}', "")
    )
    cert = str(verdict[-1])
    # SHA-256 computed by Db2's own HASH function, not by Python.
    assert len(cert) == 64 and all(c in "0123456789abcdef" for c in cert)

    row = db.fetch_one(
        app_conn,
        "SELECT s.STATUS, v.OUTCOME, v.INSTANCES FROM PORTPROOF.STATEMENT s "
        "JOIN PORTPROOF.VERDICT v ON v.STMT_ID = s.STMT_ID WHERE s.CASE_NAME = ? "
        "ORDER BY v.VERDICT_ID DESC FETCH FIRST 1 ROWS ONLY",
        (case,),
    )
    assert row[0].strip() == "COMPILES"
    assert row[1].strip() == "PASS"
    assert int(row[2]) == 6


def test_check_constraint_rejects_an_unknown_status(app_conn):
    with pytest.raises(db.Db2Error) as caught:
        db.call_proc(
            app_conn,
            "PORTPROOF.RECORD_TRANSLATION",
            ("test/badstatus", "postgres", "SELECT 1", None, "NOT_A_STATUS", None, None, "{}", 1, 0),
        )
    assert caught.value.sqlcode == -545


def test_check_constraint_rejects_an_unknown_dialect(app_conn):
    with pytest.raises(db.Db2Error) as caught:
        db.call_proc(
            app_conn,
            "PORTPROOF.RECORD_TRANSLATION",
            ("test/baddialect", "oracle", "SELECT 1", None, "COMPILES", None, None, "{}", 1, 0),
        )
    assert caught.value.sqlcode == -545


# --------------------------------------------------------------------------
# things the engine maintains by itself
# --------------------------------------------------------------------------
def test_system_versioning_keeps_history(app_conn):
    case = "test/versioning"
    db.call_proc(
        app_conn,
        "PORTPROOF.RECORD_TRANSLATION",
        (case, "postgres", "SELECT 1", None, "COMPILE_FAIL", -104, "first", "{}", 1, 0),
    )
    db.call_proc(
        app_conn,
        "PORTPROOF.RECORD_TRANSLATION",
        (case, "postgres", "SELECT 1", "SELECT 1", "REPAIRED", -104, "second", "{}", 2, 0),
    )
    current = db.fetch_one(
        app_conn, "SELECT STATUS FROM PORTPROOF.STATEMENT WHERE CASE_NAME = ?", (case,)
    )
    assert current[0].strip() == "REPAIRED"
    # The engine wrote the previous version to the history table unprompted.
    history = db.fetch_one(
        app_conn, "SELECT COUNT(*) FROM PORTPROOF.STATEMENT_HIST WHERE CASE_NAME = ?", (case,)
    )
    assert int(history[0]) >= 1


def test_mqt_is_refreshed_by_the_engine(app_conn):
    db.call_proc(
        app_conn,
        "PORTPROOF.RECORD_TRANSLATION",
        ("test/mqt", "mysql", "SELECT 1", None, "COMPILE_FAIL", -999, "mqt probe", "{}", 1, 0),
    )
    row = db.fetch_one(
        app_conn,
        "SELECT N FROM PORTPROOF.MQT_FAILURE_BY_CODE WHERE SRC_DIALECT = ? AND LAST_SQLCODE = ?",
        ("mysql", -999),
    )
    assert row is not None and int(row[0]) >= 1


def test_expression_index_exists(owner_conn):
    row = db.fetch_one(
        owner_conn,
        "SELECT COUNT(*) FROM SYSCAT.INDEXES WHERE INDSCHEMA = ? AND INDNAME = ?",
        ("PORTPROOF", "IX_STMT_CASEFOLD"),
    )
    assert int(row[0]) == 1


def test_collation_key_gives_case_insensitive_comparison(owner_conn):
    """The comparison form PortProof emits to preserve MySQL semantics."""
    row = db.fetch_one(
        owner_conn,
        "SELECT CASE WHEN COLLATION_KEY_BIT(?, 'UCA500R1_S1') = "
        "COLLATION_KEY_BIT(?, 'UCA500R1_S1') THEN 1 ELSE 0 END FROM SYSIBM.SYSDUMMY1",
        ("Asha", "ASHA"),
    )
    assert int(row[0]) == 1


# --------------------------------------------------------------------------
# the premise, and the repair loop
# --------------------------------------------------------------------------
def test_translator_fails_silently_on_real_db2(owner_conn, loaded_target):
    """The finding PortProof exists for.

    IBM's dialect raises nothing, yet a substantial share of its output is
    rejected by a real Db2. The assertion is deliberately a range rather than an
    exact count, so a future release of the dialect improves the number without
    breaking the suite -- but a claim of zero silent failures would fail here,
    which is the point.
    """
    silent = []
    for statement in CORPUS:
        attempt = translate.translate(statement.sql, statement.dialect)
        assert attempt.ok and not attempt.raised, statement.case_name
        if not db.compile_check(owner_conn, attempt.db2_sql).ok:
            silent.append(statement.case_name)
    assert len(silent) >= 5, f"expected silent failures, found {silent}"


def test_repair_loop_fixes_every_compile_failure(owner_conn, loaded_target):
    from src.repair import RepairLoop

    loop = RepairLoop(owner_conn, memory=None)
    unrepaired = []
    for statement in CORPUS:
        attempt = translate.translate(statement.sql, statement.dialect)
        if db.compile_check(owner_conn, attempt.db2_sql).ok:
            continue
        outcome = loop.run(
            source_sql=statement.sql, db2_sql=attempt.db2_sql, dialect=statement.dialect
        )
        if not outcome.attempts[-1].ok:
            unrepaired.append((statement.case_name, outcome.attempts[-1].sqlcode))
    assert unrepaired == []


def test_repair_is_verified_by_db2_not_asserted(owner_conn, loaded_target):
    """A repair that does not compile must not be accepted."""
    from src.repair import RepairLoop

    class AlwaysWrong:
        last_rules: list[str] = []

        def invoke(self, *_args, **_kwargs):
            return "SELECT this_is_not_valid FROM nowhere_at_all"

    loop = RepairLoop(owner_conn, memory=None)
    loop.chain = AlwaysWrong()  # type: ignore[assignment]
    outcome = loop.run(
        source_sql="SELECT 1", db2_sql="SELECT nope FROM missing_table_zz", dialect="postgres"
    )
    assert not outcome.attempts[-1].ok
    assert not outcome.repaired


# --------------------------------------------------------------------------
# the semantic proof
# --------------------------------------------------------------------------
def test_integer_division_is_proven_different(owner_conn):
    """MySQL's 7/2 is 3.5 and Db2's is 3. Both compile; the answers differ.

    This is the one that has to be judged by a *real* MySQL. DuckDB in
    PostgreSQL mode also answers 3.5, which made this look like a MySQL
    divergence when it was partly DuckDB's own; see the next test.
    """
    from src.counterexample import (
        Db2Target,
        MySqlSource,
        ensure_fixture_schema,
        prove_semantics,
    )

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    try:
        source = MySqlSource()
    except Exception as exc:  # pragma: no cover - no MySQL on this machine
        pytest.skip(f"no MySQL reachable: {str(exc)[:80]}")
    try:
        verdict = prove_semantics(
            source_sql="SELECT 7 / 2 AS q FROM customers WHERE id = 1",
            db2_sql="SELECT 7 / 2 AS q FROM customers WHERE id = 1",
            source=source,
            target=target,
            variants=[BASE],
            dialect="mysql",
        )
    finally:
        source.close()
    assert verdict.outcome == "DIFFERENT"
    assert verdict.witness is not None
    assert verdict.witness.source_rows == [("3.5",)]
    assert verdict.witness.db2_rows == [("3",)]


def test_the_duckdb_stand_in_refuses_to_judge_division(owner_conn):
    """A false PROVEN DIFFERENT: DuckDB says 7/2 is 3.5, PostgreSQL says 3.

    PostgreSQL and Db2 agree here, so reporting a difference would have sent a
    reviewer after a bug that is not in their code. The stand in declines.
    """
    from src.counterexample import (
        Db2Target,
        DuckDbSource,
        ensure_fixture_schema,
        prove_semantics,
    )

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    source = DuckDbSource()
    try:
        verdict = prove_semantics(
            source_sql="SELECT 7 / 2 AS q FROM customers WHERE id = 1",
            db2_sql="SELECT 7 / 2 AS q FROM customers WHERE id = 1",
            source=source,
            target=target,
            variants=[BASE],
            dialect="postgres",
        )
    finally:
        source.close()
    assert verdict.outcome == "INCONCLUSIVE"
    assert "declined to adjudicate" in verdict.notes[0]


def test_a_real_postgres_agrees_with_db2_about_integer_division(owner_conn):
    from src.counterexample import (
        Db2Target,
        PostgresSource,
        ensure_fixture_schema,
        prove_semantics,
    )

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    try:
        source = PostgresSource()
    except Exception as exc:  # pragma: no cover - no PostgreSQL on this machine
        pytest.skip(f"no PostgreSQL reachable: {str(exc)[:80]}")
    try:
        verdict = prove_semantics(
            source_sql="SELECT 7 / 2 AS q FROM customers WHERE id = 1",
            db2_sql="SELECT 7 / 2 AS q FROM customers WHERE id = 1",
            source=source,
            target=target,
            variants=VARIANTS[:2],
            dialect="postgres",
        )
    finally:
        source.close()
    assert verdict.outcome == "EQUIVALENT", verdict.witness_table()


def test_a_semantic_divergence_is_repaired_and_re_proved(owner_conn):
    """The end to end claim: compiles, wrong rows, rewritten, proof agrees."""
    from src.counterexample import (
        Db2Target,
        MySqlSource,
        ensure_fixture_schema,
        prove_semantics,
    )
    from src.semantic_repair import SemanticRepairLoop

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    try:
        source = MySqlSource()
    except Exception as exc:  # pragma: no cover - no MySQL on this machine
        pytest.skip(f"no MySQL reachable: {str(exc)[:80]}")
    sql = "SELECT id FROM customers WHERE name = 'asha smith' ORDER BY id"
    try:
        before = prove_semantics(
            source_sql=sql,
            db2_sql=sql,
            source=source,
            target=target,
            dialect="mysql",
        )
        assert before.outcome == "DIFFERENT", before.headline

        fix = SemanticRepairLoop(owner_conn, source=source, target=target).run(
            source_sql=sql, db2_sql=sql, dialect="mysql", before=before
        )
    finally:
        source.close()

    assert fix.repaired, fix.summary()
    assert fix.rule == "mysql-case-insensitive-collation"
    assert "COLLATION_KEY_BIT" in fix.final_sql
    # The rewrite is reported only because the proof that caught the bug agrees.
    assert fix.verdict is not None
    assert fix.verdict.outcome == "EQUIVALENT"
    assert fix.verdict.strength != "NONE"


def test_identical_trivial_statement_is_proven_equivalent(owner_conn):
    from src.counterexample import (
        Db2Target,
        DuckDbSource,
        ensure_fixture_schema,
        prove_semantics,
    )

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    source = DuckDbSource()
    try:
        verdict = prove_semantics(
            source_sql="SELECT id FROM customers ORDER BY id",
            db2_sql="SELECT id FROM customers ORDER BY id",
            source=source,
            target=target,
        )
    finally:
        source.close()
    assert verdict.outcome == "EQUIVALENT"
    assert verdict.instances_agreed == len(VARIANTS)


def test_proof_does_not_report_driver_type_differences(owner_conn):
    """Regression: DECIMAL arrives as a string from ibm_db and as Decimal from
    DuckDB. That is a driver artefact and must never be a verdict."""
    from src.counterexample import (
        Db2Target,
        DuckDbSource,
        ensure_fixture_schema,
        prove_semantics,
    )

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    source = DuckDbSource()
    try:
        verdict = prove_semantics(
            source_sql="SELECT id, amount FROM orders ORDER BY id",
            db2_sql="SELECT id, amount FROM orders ORDER BY id",
            source=source,
            target=target,
            # Two variants, not one: a single instance is now deliberately below
            # MIN_CONCLUSIVE_INSTANCES and comes back INCONCLUSIVE.
            variants=VARIANTS[:2],
        )
    finally:
        source.close()
    assert verdict.outcome == "EQUIVALENT", verdict.witness_table()
    assert verdict.strength in ("MODERATE", "STRONG")


# --------------------------------------------------------------------------
# the fix memory
# --------------------------------------------------------------------------
def test_fix_memory_recalls_what_it_stored(app_conn):
    from src.embeddings import DeterministicEmbeddings
    from src.fixmemory import FixMemory

    memory = FixMemory(app_conn, embeddings=DeterministicEmbeddings())
    # Durable store, no DELETE for the runtime user: use a fresh key so the test
    # is idempotent and does not depend on the table being empty.
    unique = uuid.uuid4().hex[:8].upper()
    before = memory.count()
    stored = memory.remember(
        bad_sql=f"SELECT GROUP_CONCAT_{unique}(sku, ',') FROM order_items",
        fixed_sql=f"SELECT LISTAGG_{unique}(sku, ',') FROM order_items",
        sqlcode=-440,
        error_text=f"No authorized routine named GROUP_CONCAT_{unique}",
        dialect="mysql",
        case_name="test/memory",
    )
    assert stored is True
    assert memory.count() == before + 1

    recalled = memory.recall(
        bad_sql=f"SELECT GROUP_CONCAT_{unique}(x, ',') FROM t",
        sqlcode=-440,
        error_text=f"No authorized routine named GROUP_CONCAT_{unique}",
        k=3,
    )
    assert any(f"LISTAGG_{unique}" in fix.fixed_sql for fix in recalled), [
        f.fixed_sql for f in recalled
    ]


def test_hybrid_recall_combines_vector_and_relational_filter(app_conn):
    """One Db2 statement: VECTOR_DISTANCE ranking plus a JSON predicate."""
    from src.embeddings import DeterministicEmbeddings
    from src.fixmemory import FixMemory

    memory = FixMemory(app_conn, embeddings=DeterministicEmbeddings())
    memory.remember(
        bad_sql="SELECT CONCAT(a, b, c) FROM t",
        fixed_sql="SELECT (a || b || c) FROM t",
        sqlcode=-440,
        error_text="No authorized routine named CONCAT",
        dialect="mysql",
        case_name="test/hybrid",
    )
    hits = memory.recall_sql(
        bad_sql="SELECT CONCAT(x, y, z) FROM t",
        sqlcode=-440,
        error_text="No authorized routine named CONCAT",
        dialect="mysql",
        k=5,
    )
    assert hits, "hybrid vector + relational recall returned nothing"
    assert all(fix.dialect == "mysql" for fix in hits)


# --------------------------------------------------------------------------
# physical design: measured by the engine, not guessed by a model
# --------------------------------------------------------------------------
def test_compression_saving_is_measured_and_cross_checked(owner_conn):
    """Two independent Db2 sources must agree about the same tables.

    One number comes from SYSCAT.TABLES.NPAGES after RUNSTATS on two tables
    holding byte-identical rows; the other from Db2's own compression
    estimator. If they disagreed wildly, the "measured" claim would be hollow,
    so the agreement itself is the assertion.
    """
    from src.physical import measure_compression

    advice = measure_compression(owner_conn, rows=4000)

    measured = advice.measured_page_saving
    assert measured is not None, advice.note
    assert advice.uncompressed_pages > advice.compressed_pages
    assert 20.0 < measured < 99.0, measured

    assert advice.percent_saved is not None, (
        f"the estimator returned nothing: {advice.note}. The column is not "
        "called PCTPAGESSAVED on this version -- see src/physical.py."
    )
    assert abs(measured - advice.percent_saved) < 10.0, (
        f"catalog says {measured:.1f}% but the estimator says "
        f"{advice.percent_saved:.1f}%"
    )
    assert "not measurable" not in advice.headline


def test_columnar_organisation_is_available(owner_conn):
    from src.physical import check_columnar

    advice = check_columnar(owner_conn)
    assert advice.supported, advice.note


def test_package_cache_shows_real_executions(owner_conn):
    """MON_GET_PKG_CACHE_STMT needs EXECUTE granted per routine, or this is
    empty and the regression check silently reports nothing."""
    from src.physical import workload_hotspots

    db.fetch_all(owner_conn, "SELECT COUNT(*) FROM PPTEST.customers")
    hotspots = workload_hotspots(owner_conn, limit=5)
    assert hotspots, "package cache empty: is EXECUTE granted on MON_GET_PKG_CACHE_STMT?"
    assert all(n > 0 for _, n, _ in hotspots)


def test_fix_memory_does_not_store_the_same_repair_twice(app_conn):
    """Recall must show distinct precedents, not one repair repeated."""
    from src.embeddings import DeterministicEmbeddings
    from src.fixmemory import FixMemory

    memory = FixMemory(app_conn, embeddings=DeterministicEmbeddings())
    # The store is durable and the runtime user cannot DELETE, so the test has
    # to bring its own fresh key rather than assume an empty table.
    unique = uuid.uuid4().hex[:8]
    payload = dict(
        bad_sql=f"SELECT DUPLICATE_ME_{unique}(a) FROM t",
        fixed_sql=f"SELECT LISTAGG_{unique}(a) FROM t",
        sqlcode=-440,
        error_text="No authorized routine named DUPLICATE_ME",
        dialect="mysql",
        case_name="test/dedup",
    )
    before = memory.count()
    assert memory.remember(**payload) is True
    assert memory.count() == before + 1

    assert memory.remember(**payload) is False
    assert memory.count() == before + 1, "the same repair was stored twice"


def test_failure_rollup_mqt_counts_only_failures(owner_conn, app_conn):
    """The MQT is named FAILURE_BY_CODE, so a successful compile must not be in
    it. ``LAST_SQLCODE IS NOT NULL`` also matches 0, which counted successes as
    failures."""
    rows = db.fetch_all(
        app_conn, "SELECT LAST_SQLCODE FROM PORTPROOF.MQT_FAILURE_BY_CODE"
    )
    assert rows, "rollup is empty"
    assert all(int(code) < 0 for (code,) in rows), rows


def test_failure_rollup_is_refreshed_by_the_engine(app_conn):
    """No application code maintains this table; Db2 does, on insert."""
    case = f"test/mqt_{uuid.uuid4().hex[:8]}"
    before = db.fetch_one(
        app_conn,
        "SELECT COALESCE(SUM(N), 0) FROM PORTPROOF.MQT_FAILURE_BY_CODE "
        "WHERE LAST_SQLCODE = ?",
        (-911,),
    )[0]
    db.call_proc(
        app_conn,
        "PORTPROOF.RECORD_TRANSLATION",
        (case, "postgres", "SELECT 1", None, "COMPILE_FAIL", -911, "synthetic", "{}", 1, 0),
    )
    after = db.fetch_one(
        app_conn,
        "SELECT COALESCE(SUM(N), 0) FROM PORTPROOF.MQT_FAILURE_BY_CODE "
        "WHERE LAST_SQLCODE = ?",
        (-911,),
    )[0]
    assert int(after) == int(before) + 1, "REFRESH IMMEDIATE did not maintain the MQT"


# --------------------------------------------------------------------------
# federation: the engine checking the inputs for itself
# --------------------------------------------------------------------------
@pytest.mark.db2
def test_db2_can_read_the_source_tables_and_agree_about_their_contents(owner_conn):
    """The federated cross-check, end to end against the real servers.

    Skipped rather than failed when no nicknames exist, because federation is
    optional: scripts/create_federation.sh has to be run once, as the instance
    owner, and a checkout that has not run it must still pass its tests.
    """
    from src import federation
    from src.corpus import BASE, FIXTURE_TABLES
    from src.counterexample import Db2Target, available_sources, ensure_fixture_schema

    state = federation.status(owner_conn)
    if not state.available:
        pytest.skip(f"federation not configured: {state.note}")

    sources = available_sources()
    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)

    for dialect, engine in sources.items():
        if dialect not in state.dialects():
            continue
        # Load the same dataset on both sides, then ask Db2 to compare them
        # itself. This is the one check in the suite that does not rely on
        # Python having read both results correctly.
        engine.load(BASE)
        target.load(BASE)

        result = federation.corroborate(owner_conn, FIXTURE_TABLES, dialect)
        assert result.verdict == "INPUTS_MATCH", result.evidence()
        assert result.strengthens_proof
        assert all(c.columns_compared > 0 for c in result.comparisons), result.evidence()


@pytest.mark.db2
def test_the_federated_comparison_notices_a_row_only_db2_has(owner_conn):
    """A deliberate divergence has to be caught, or the check proves nothing.

    One extra row is inserted into the Db2 copy and nowhere else. Db2's own
    symmetric difference must report exactly that one row, on the Db2 side.
    """
    from src import db, federation
    from src.corpus import BASE
    from src.counterexample import FIXTURE_SCHEMA, Db2Target, available_sources, \
        ensure_fixture_schema

    state = federation.status(owner_conn)
    sources = available_sources()
    dialect = next((d for d in state.dialects() if d in sources), None)
    if dialect is None:
        pytest.skip("federation not configured for any available source engine")

    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    sources[dialect].load(BASE)
    target.load(BASE)

    nickname = next(
        n for n in state.nicknames[dialect] if n.upper().endswith("_CUSTOMERS")
    )
    db.execute(owner_conn, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")
    db.execute(
        owner_conn,
        "INSERT INTO customers (id, name, email, first_name, last_name, "
        "is_active, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [9901, "only in db2", "nowhere@example.com", "only", "db2", True, False],
    )
    try:
        result = federation.compare_inputs(owner_conn, "customers", dialect, nickname)
        assert result.attempted, result.describe()
        assert result.only_in_db2 == 1, result.describe()
        assert result.only_in_source == 0, result.describe()
        assert not result.identical
    finally:
        db.execute(owner_conn, "DELETE FROM customers WHERE id = ?", [9901])
