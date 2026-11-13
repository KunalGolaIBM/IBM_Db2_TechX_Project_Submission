"""Tests for the things that decide whether a verdict can be believed.

Every test in this file exists because PortProof once got the corresponding
answer wrong. They are grouped by the mistake, not by the module, because the
mistake is the point: a prover that reports a false EQUIVALENT is worse than no
prover at all, and a prover that reports a false DIFFERENT wastes a reviewer's
afternoon on a bug that is not there.

No database and no network are needed here. The end to end proofs against a
real Db2, a real PostgreSQL and a real MySQL live in test_integration.py.
"""
from __future__ import annotations

import pytest

from src import federation
from src.corpus import CORPUS, VARIANTS
from src.counterexample import (
    InstanceResult,
    SemanticVerdict,
    canon_columns,
    canon_value,
    comparable_columns,
    has_outer_order_by,
)


# --------------------------------------------------------------------------
# which ORDER BY actually orders the result
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql,ordered",
    [
        ("SELECT id FROM t ORDER BY id", True),
        ("SELECT id FROM t", False),
        # A window function's ordering says nothing about the order the rows
        # come back in. Treating it as if it did made PortProof compare ties
        # positionally and call the engines different when they were not.
        ("SELECT lag(a) OVER (PARTITION BY c ORDER BY b) FROM t", False),
        ("SELECT * FROM (SELECT a FROM t ORDER BY a) x", False),
        ("WITH c AS (SELECT a FROM t ORDER BY a) SELECT * FROM c", False),
        ("WITH c AS (SELECT a FROM t) SELECT * FROM c ORDER BY a", True),
        ("SELECT string_agg(s, ',' ORDER BY s) FROM t", False),
        ("SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY amount) FROM t", False),
        # Words inside a literal or a comment are not a clause.
        ("SELECT 'order by' FROM t", False),
        ("SELECT a FROM t -- order by a", False),
        ("SELECT a FROM t /* order by a */", False),
        # An unbalanced parenthesis inside a literal must not shift the depth
        # of everything after it.
        ("SELECT '((' AS p FROM t ORDER BY p", True),
    ],
)
def test_only_an_outer_order_by_asserts_row_order(sql, ordered):
    assert has_outer_order_by(sql) is ordered


# --------------------------------------------------------------------------
# agreement on nothing
# --------------------------------------------------------------------------
def _instance(name, *, agreed, source=(), db2=(), cols=("ID",)):
    return InstanceResult(
        variant=name,
        targets="",
        agreed=agreed,
        source_rows=list(source),
        db2_rows=list(db2),
        source_columns=cols,
        db2_columns=cols,
    )


def _verdict(outcome, instances):
    agreed = sum(1 for i in instances if i.agreed)
    return SemanticVerdict(
        outcome=outcome,
        instances_checked=len(instances),
        instances_agreed=agreed,
        source_engine="test",
        instances=instances,
    )


def test_two_empty_results_are_not_evidence_of_anything():
    empty = _instance("empty_groups", agreed=True)
    assert empty.vacuous is True
    assert empty.rows_compared == 0

    real = _instance("base", agreed=True, source=[("1",)], db2=[("1",)])
    assert real.vacuous is False
    assert real.rows_compared == 1


def test_a_vacuous_verdict_can_never_be_strong():
    verdict = _verdict("VACUOUS", [_instance(f"v{i}", agreed=True) for i in range(6)])
    assert verdict.strength == "NONE"
    assert verdict.substantive_instances == 0
    assert verdict.vacuous_instances == 6
    assert "nothing was compared" in verdict.headline


def test_six_datasets_that_all_produce_the_same_rows_are_one_test():
    same = [
        _instance(f"v{i}", agreed=True, source=[("1",)], db2=[("1",)]) for i in range(6)
    ]
    verdict = _verdict("EQUIVALENT", same)
    assert verdict.distinct_inputs == 1
    assert verdict.strength == "WEAK"


def test_varied_inputs_earn_a_strong_verdict():
    varied = [
        _instance(
            f"v{i}",
            agreed=True,
            source=[(str(i),), (str(i + 9),)],
            db2=[(str(i),), (str(i + 9),)],
        )
        for i in range(4)
    ]
    verdict = _verdict("EQUIVALENT", varied)
    assert verdict.distinct_inputs == 4
    assert verdict.rows_compared == 8
    assert verdict.strength == "STRONG"


def test_the_certificate_cannot_confuse_a_vacuous_proof_with_a_real_one():
    """RECORD_VERDICT hashes this dict, so the two must not be equal."""
    vacuous = _verdict("VACUOUS", [_instance("a", agreed=True), _instance("b", agreed=True)])
    real = _verdict(
        "EQUIVALENT",
        [
            _instance("a", agreed=True, source=[("1",)], db2=[("1",)]),
            _instance("b", agreed=True, source=[("2",)], db2=[("2",)]),
        ],
    )
    assert vacuous.evidence() != real.evidence()
    assert vacuous.evidence()["strength"] == "NONE"
    assert real.evidence()["strength"] in ("MODERATE", "STRONG")


# --------------------------------------------------------------------------
# the result's shape, not only its values
# --------------------------------------------------------------------------
def test_column_names_are_normalised_but_not_invented():
    assert canon_columns([" id ", "Name"]) == ("ID", "NAME")
    # Engines spell a generated name for an unaliased expression differently.
    # Comparing those would measure the drivers rather than the migration.
    assert comparable_columns(["1", "total"]) == ()
    assert comparable_columns(["EXPR", "total"]) == ()
    assert comparable_columns(["id", "total"]) == ("ID", "TOTAL")


def test_an_array_is_rendered_the_way_sql_renders_it():
    """psycopg hands back a Python list, whose repr is Python's, not SQL's."""
    assert canon_value([10, 11]) == "{10,11}"
    assert canon_value([]) == "{}"


# --------------------------------------------------------------------------
# a stand in engine has to say where it stands in badly
# --------------------------------------------------------------------------
def test_duckdb_declines_the_constructs_it_gets_wrong():
    from src.counterexample import DuckDbSource

    source = object.__new__(DuckDbSource)  # no connection needed
    declare = DuckDbSource.declared_divergences
    assert "floating-point" in declare(source, "SELECT 7 / 2 AS q FROM t")
    assert declare(source, "SELECT array_agg(id) FROM t")
    assert declare(source, "SELECT id FROM t ORDER BY id") == ""
    # A slash inside a literal is not a division.
    assert declare(source, "SELECT 'a/b' FROM t") == ""


def test_the_prover_refuses_a_dialect_its_engine_does_not_speak():
    """The exact bug that certified mysql/case_insensitive_eq as equivalent."""
    from src.counterexample import prove_semantics

    class PretendPostgres:
        name = "pretend"
        dialect = "postgres"

        def load(self, variant):  # pragma: no cover - never reached
            raise AssertionError("the guard should have stopped this")

        def run(self, sql):  # pragma: no cover - never reached
            raise AssertionError("the guard should have stopped this")

        def close(self):
            pass

    verdict = prove_semantics(
        source_sql="SELECT id FROM customers WHERE name = 'asha smith'",
        db2_sql="SELECT id FROM customers WHERE name = 'asha smith'",
        source=PretendPostgres(),
        target=None,
        dialect="mysql",
    )
    assert verdict.outcome == "INCONCLUSIVE"
    assert verdict.strength == "NONE"
    assert "refused to judge mysql SQL" in verdict.notes[0]


# --------------------------------------------------------------------------
# the semantic repair rules
# --------------------------------------------------------------------------
def test_collation_rule_wraps_both_sides_of_the_comparison():
    from src.semantic_repair import _collate_string_equality

    out = _collate_string_equality("SELECT id FROM c WHERE name = 'asha smith'")
    assert out.count("COLLATION_KEY_BIT") == 2
    assert "'UCA500R1_S1'" in out


def test_division_rule_replaces_the_translators_float_cast():
    from src.semantic_repair import _mysql_decimal_division

    out = _mysql_decimal_division(
        "SELECT CAST(amount AS DOUBLE) / NULLIF(quantity, 0) AS u FROM orders"
    )
    assert "DOUBLE" not in out
    assert "ROUND(" in out and "DECIMAL(31,6)" in out
    # NULLIF survives, because MySQL's x / 0 really is NULL.
    assert "NULLIF(quantity, 0)" in out


def test_division_rule_uses_mysqls_scale_for_an_integer_literal():
    from src.semantic_repair import _mysql_decimal_division

    # MySQL's 7 / 2 is 3.5000: the numerator's scale (0) plus 4.
    assert "DECIMAL(31,4)" in _mysql_decimal_division("SELECT 7 / 2 AS q")


def test_format_model_rule_turns_strftime_back_into_db2():
    from src.semantic_repair import _db2_format_model

    out = _db2_format_model("SELECT VARCHAR_FORMAT(created_at, '%Y-%m') AS m FROM o")
    assert "'YYYY-MM'" in out
    assert "%" not in out


def test_linguistic_order_rule_keeps_asc_and_desc_outside_the_key():
    from src.semantic_repair import _linguistic_order

    out = _linguistic_order("SELECT id FROM c ORDER BY name DESC")
    assert "COLLATION_KEY_BIT(name, 'UCA500R1_S3') DESC" in out


def test_array_text_rule_produces_postgresqls_braces():
    from src.semantic_repair import _postgres_array_text

    out = _postgres_array_text(
        "SELECT customer_id, LISTAGG(CAST(id AS VARCHAR(200)), ',') AS ids FROM orders"
    )
    assert "'{' || LISTAGG" in out and "|| '}'" in out


def test_no_semantic_rule_ever_crosses_dialects():
    """A PostgreSQL statement must never be fixed with MySQL's collation."""
    from src.semantic_repair import SEMANTIC_RULES

    mysql_only = {"mysql-case-insensitive-collation", "mysql-decimal-division"}
    postgres_only = {"postgres-array-text-form", "postgres-linguistic-collation-order"}
    for rule in SEMANTIC_RULES:
        if rule.name in mysql_only:
            assert rule.dialect == "mysql", rule.name
        if rule.name in postgres_only:
            assert rule.dialect == "postgres", rule.name
    assert {r.dialect for r in SEMANTIC_RULES} <= {"postgres", "mysql", "tsql", "sqlite"}
    by_name = {r.name: r.dialect for r in SEMANTIC_RULES if r.name.startswith("sqlserver-")}
    assert set(by_name.values()) <= {"tsql"}


def test_every_semantic_rule_is_a_no_op_on_sql_it_does_not_match():
    from src.semantic_repair import SEMANTIC_RULES

    harmless = "SELECT id FROM customers WHERE id > 3"
    for rule in SEMANTIC_RULES:
        if rule.detect(harmless):
            continue
        assert rule.rewrite(harmless) == harmless, rule.name


# --------------------------------------------------------------------------
# the stability probe
# --------------------------------------------------------------------------
def test_reinserting_the_same_rows_changes_nothing_logically():
    for variant in VARIANTS:
        shuffled = variant.shuffled()
        assert set(shuffled.rows) == set(variant.rows)
        for table, rows in variant.rows.items():
            assert sorted(map(repr, shuffled.rows[table])) == sorted(map(repr, rows))
            if len(rows) > 1:
                assert shuffled.rows[table] != rows
        assert shuffled.name != variant.name


# --------------------------------------------------------------------------
# the corpus itself
# --------------------------------------------------------------------------
def test_the_adversarial_datasets_are_actually_different_from_each_other():
    """They used to share row lists by reference, so six datasets were two."""
    seen: dict[str, set[str]] = {}
    for variant in VARIANTS:
        for table, rows in variant.rows.items():
            seen.setdefault(table, set()).add(repr(rows))
    for table, shapes in seen.items():
        # empty_groups deliberately empties every table, so the floor is three
        # genuinely distinct datasets per table rather than six.
        assert len(shapes) >= 3, f"{table} has only {len(shapes)} distinct dataset(s)"


def test_the_corpus_exercises_joins_and_null_logic():
    sql = " ".join(s.sql.upper() for s in CORPUS)
    assert "JOIN" in sql, "a single table corpus cannot expose a join difference"
    assert "NOT IN" in sql
    assert "LEFT JOIN" in sql


def test_limit_with_an_offset_cannot_hide_a_swap():
    """MySQL's LIMIT 2, 2 is offset 2 count 2, so swapping them is invisible."""
    for statement in CORPUS:
        if statement.dialect != "mysql" or "LIMIT" not in statement.sql.upper():
            continue
        if "," not in statement.sql.split("LIMIT")[-1]:
            continue
        offset, count = (
            part.strip() for part in statement.sql.split("LIMIT")[-1].split(",")
        )
        assert offset != count, f"{statement.case_name}: LIMIT {offset}, {count}"


# --------------------------------------------------------------------------
# federation: Db2's own opinion on whether the inputs even matched
# --------------------------------------------------------------------------
def test_an_identical_input_strengthens_a_divergence_and_a_different_one_does_not():
    """The whole point of the federated cross-check.

    A divergence is only evidence about the translation if both engines were
    reading the same rows. Keeping the two cases apart is what stops a loading
    bug from being filed as a translator bug.
    """
    matched = federation.Corroboration(
        "INPUTS_MATCH",
        (federation.InputComparison("orders", "postgres", "DB2INST1.PG_ORDERS",
                                    columns_compared=6),),
    )
    assert matched.strengthens_proof
    assert not matched.undermines_proof

    differed = federation.Corroboration(
        "INPUTS_DIFFER",
        (federation.InputComparison("orders", "postgres", "DB2INST1.PG_ORDERS",
                                    only_in_source=2, columns_compared=6),),
    )
    assert differed.undermines_proof
    assert not differed.strengthens_proof


def test_no_federation_is_not_an_opinion_either_way():
    """A checkout that never ran the setup script must not look like a pass."""
    absent = federation.Corroboration("UNAVAILABLE", note="no nicknames for mysql")
    assert not absent.strengthens_proof
    assert not absent.undermines_proof
    assert "no nicknames" in absent.headline()


def test_a_skipped_column_is_named_rather_than_quietly_dropped():
    """Db2 refuses to cast a MySQL BOOLEAN nickname column (SQL0461N).

    Dropping it silently would turn a partial check into one that reads as
    complete, so the description has to say which columns were left out.
    """
    partial = federation.InputComparison(
        "customers",
        "mysql",
        "DB2INST1.MY_CUSTOMERS",
        columns_compared=5,
        columns_skipped=("IS_ACTIVE", "IS_DELETED"),
    )
    assert partial.identical
    text = partial.describe()
    assert "5 columns" in text
    assert "IS_ACTIVE" in text and "IS_DELETED" in text


def test_a_comparison_that_errored_is_not_counted_as_agreement():
    failed = federation.InputComparison(
        "orders", "mysql", "DB2INST1.MY_ORDERS", error="SQL1101N"
    )
    assert not failed.attempted
    assert not failed.identical
    assert "not compared" in failed.describe()


def test_the_local_column_type_is_what_the_remote_is_cast_to():
    assert federation._db2_type("VARCHAR", 40, 0) == "VARCHAR(40)"
    assert federation._db2_type("DECIMAL", 10, 2) == "DECIMAL(10,2)"
    assert federation._db2_type("INTEGER", 4, 0) == "INTEGER"
    # TIMESTAMP carries a precision Db2 will not accept in this position.
    assert federation._db2_type("TIMESTAMP", 26, 6) == "TIMESTAMP"


def test_only_a_real_identifier_can_reach_the_statement_text():
    """SQL has no parameter marker for an identifier, so the guard is the check."""
    assert federation._safe_identifier("pg_orders") == "PG_ORDERS"
    for bad in ("orders; DROP TABLE t", 'orders"', "", "9lives", "a b"):
        with pytest.raises(ValueError):
            federation._safe_identifier(bad)


def test_a_table_that_was_never_read_cannot_be_folded_into_a_pass():
    """Four tables agreeing and a fifth never read is not confirmation.

    This is the same mistake as a vacuous proof, one level up: the summary
    looked like a clean pass while one of the inputs had not been compared at
    all.
    """
    ok = federation.InputComparison("orders", "mysql", "N.MY_ORDERS", columns_compared=6)
    unread = federation.InputComparison(
        "customers", "mysql", "N.MY_CUSTOMERS", error="SQL1101N"
    )
    partial = federation.Corroboration("UNAVAILABLE", (ok, unread), note="not compared")
    assert not partial.strengthens_proof
    assert not partial.undermines_proof
