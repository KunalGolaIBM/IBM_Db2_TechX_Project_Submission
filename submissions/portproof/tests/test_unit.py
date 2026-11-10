"""Unit tests. No database, no network, no model download."""
from __future__ import annotations

import decimal

import pytest

from src.corpus import CORPUS, FIXTURE_TABLES, VARIANTS
from src.counterexample import canon_rows, canon_value
from src.llm import RuleRepairLLM, apply_rules
from src.repair import clean_sql
from src.safety import UnsafeSql, check_read_only, is_read_only
from src.translate import normalise, translate


# --------------------------------------------------------------------------
# value canonicalisation -- this is what makes a verdict trustworthy
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [
        (decimal.Decimal("50.00"), "50"),
        (decimal.Decimal("100"), "100"),
        (decimal.Decimal("99.50"), "99.5"),
        (decimal.Decimal("0.01"), "0.01"),
        (decimal.Decimal("3.5"), "3.5"),
        (100, "100"),
        (0, "0"),
        (1.50, "1.5"),
        (None, "<null>"),
        (True, "true"),
        (False, "false"),
        # ibm_db hands DECIMAL back as a string; it must canonicalise the same.
        ("50.00", "50"),
        ("-3", "-3"),
        ("  padded   ", "  padded"),
    ],
)
def test_canon_value(value, expected):
    assert canon_value(value) == expected


def test_canon_value_never_mangles_integers():
    """Regression: stripping trailing zeros would turn 100 into 1."""
    assert canon_value(decimal.Decimal("100")) == "100"
    assert canon_value(decimal.Decimal("1000.00")) == "1000"


def test_canon_value_never_uses_exponent_form():
    """Regression: Decimal.normalize() renders 50.00 as '5E+1'."""
    for raw in ("50.00", "100.000", "1.5E+2"):
        assert "E" not in canon_value(decimal.Decimal(raw))


def test_decimal_and_string_forms_agree():
    """The two drivers disagree about type; the verdict must not notice."""
    assert canon_value(decimal.Decimal("150.00")) == canon_value("150.00")


def test_canon_rows_unordered_is_a_multiset():
    rows_a = [(1, "a"), (2, "b")]
    rows_b = [(2, "b"), (1, "a")]
    assert canon_rows(rows_a, ordered=False) == canon_rows(rows_b, ordered=False)
    assert canon_rows(rows_a, ordered=True) != canon_rows(rows_b, ordered=True)


# --------------------------------------------------------------------------
# repair rules
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad,must_contain,rule",
    [
        ("SELECT GROUP_CONCAT(sku, ',') FROM t", "LISTAGG", "group_concat->listagg"),
        ("SELECT ARRAY_AGG(id) FROM t", "LISTAGG", "array_agg->listagg"),
        ("SELECT CONCAT(a, ' ', b) FROM t", "||", "concat->||"),
        ("SELECT TIMESTAMP_TRUNC(ts, MONTH) FROM t", "TRUNC_TIMESTAMP", "timestamp_trunc->trunc_timestamp"),
        ("SELECT JSON_EXTRACT_SCALAR(p, '$.c') FROM t", "JSON_VALUE", "json_extract_scalar->json_value"),
        ("SELECT * FROM t WHERE REGEXP_I_LIKE(e, 'x')", "REGEXP_LIKE", "regexp_i_like->regexp_like"),
        ("SELECT COUNT(*) FILTER(WHERE s = 'P') FROM t", "CASE WHEN", "filter->case"),
        ("WITH RECURSIVE r(n) AS (SELECT 1) SELECT n FROM r", "WITH r", "drop-recursive-keyword"),
        ('SELECT "id" FROM "customers"', "SELECT id FROM customers", "unquote-lowercase-identifiers"),
        ("SELECT ROW_NUMBER() OVER () AS _rn FROM t", "pp_rn", "rename-leading-underscore-identifiers"),
    ],
)
def test_rule_fires_and_rewrites(bad, must_contain, rule):
    fixed, fired = apply_rules(bad)
    assert must_contain in fixed, fixed
    assert rule in fired, fired


def test_group_by_ordinal_is_resolved_to_the_expression():
    bad = "SELECT TRUNC_TIMESTAMP(ts, 'MONTH') AS m, SUM(a) AS s FROM t GROUP BY 1 ORDER BY 1"
    fixed, fired = apply_rules(bad)
    assert "GROUP BY TRUNC_TIMESTAMP(ts, 'MONTH')" in fixed, fixed
    assert "resolve-group-by-ordinal" in fired
    # Regression: the separating space must survive, or ORDER BY is glued on.
    assert "1ORDER" not in fixed


def test_group_by_rewrite_keeps_following_clause_separate():
    fixed, _ = apply_rules("SELECT a AS x, COUNT(*) FROM t GROUP BY 1 ORDER BY 1")
    assert "ORDER BY" in fixed
    assert "BYORDER" not in fixed and "1ORDER" not in fixed


def test_rules_are_idempotent():
    once, _ = apply_rules("SELECT GROUP_CONCAT(sku, ',') FROM t")
    twice, _ = apply_rules(once)
    assert once == twice


def test_rules_leave_valid_sql_alone():
    good = "SELECT ID, NAME FROM CUSTOMERS WHERE ID = 1 ORDER BY NAME"
    fixed, fired = apply_rules(good)
    assert fixed == good
    assert fired == []


def test_rule_llm_reads_the_tagged_block():
    llm = RuleRepairLLM()
    prompt = "noise <FAILING_DB2_SQL>SELECT CONCAT(a,b,c) FROM t</FAILING_DB2_SQL> more noise"
    assert "||" in llm.invoke(prompt)


# --------------------------------------------------------------------------
# model output handling -- never trust it verbatim
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("```sql\nSELECT 1\n```", "SELECT 1"),
        ("SELECT 1;", "SELECT 1"),
        ("Here you go:\nSELECT 1 FROM t", "SELECT 1 FROM t"),
        ("   SELECT 1   ", "SELECT 1"),
        ("", ""),
    ],
)
def test_clean_sql(raw, expected):
    assert clean_sql(raw) == expected


# --------------------------------------------------------------------------
# translation
# --------------------------------------------------------------------------
def test_translation_produces_sql_for_every_corpus_statement():
    for statement in CORPUS:
        result = translate(statement.sql, statement.dialect)
        assert result.ok, f"{statement.case_name}: {result.error}"
        assert result.db2_sql


def test_translator_reports_no_error_on_the_whole_corpus():
    """The premise of the project, asserted as a test.

    IBM's dialect raises nothing for any of these statements. Whether the
    output is *valid Db2* is a separate question, which only Db2 can answer --
    see test_integration.py.
    """
    raised = [s.case_name for s in CORPUS if translate(s.sql, s.dialect).raised]
    assert raised == []


def test_normalise_collapses_whitespace():
    assert normalise("SELECT   1\n  FROM  t") == "SELECT 1 FROM t"


# --------------------------------------------------------------------------
# input validation -- the statement under test is the untrusted input
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT 1;",
        "  select id from customers where id = 1  ",
        "WITH r(n) AS (SELECT 1) SELECT n FROM r",
        "VALUES (1), (2)",
        "(SELECT 1)",
        "SELECT 'drop table t' AS joke FROM customers",  # keyword inside a literal
        "SELECT id FROM customers -- delete me\n",  # keyword inside a comment
    ],
)
def test_read_only_statements_are_accepted(sql):
    assert is_read_only(sql), sql


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "SELECT 1; DROP TABLE customers",
        "DROP TABLE customers",
        "INSERT INTO customers VALUES (1)",
        "UPDATE customers SET id = 2",
        "DELETE FROM customers",
        "CALL PORTPROOF.RECORD_VERDICT(1,'COMPILE','PASS',1,'{}','')",
        "GRANT DBADM ON DATABASE TO USER PPAPP",
        "SELECT 1 /* x */ ; GRANT DBADM ON DATABASE TO USER PPAPP",
        "SET CURRENT SCHEMA SYSIBM",
        "SELECT 1 UNION SELECT 1; SELECT 2",
    ],
)
def test_unsafe_statements_are_rejected(sql):
    assert not is_read_only(sql), sql
    with pytest.raises(UnsafeSql):
        check_read_only(sql)


def test_a_comment_cannot_hide_a_second_statement():
    """A stripped comment must not merge two statements into one."""
    with pytest.raises(UnsafeSql):
        check_read_only("SELECT 1 --\n; DELETE FROM customers")


def test_overlong_statements_are_rejected():
    with pytest.raises(UnsafeSql):
        check_read_only("SELECT " + "1," * 20_000 + "1 FROM customers")


def test_the_guard_accepts_every_corpus_statement_and_its_translation():
    """The guard has to let real work through, or it is just an obstacle."""
    for statement in CORPUS:
        check_read_only(statement.sql)
        check_read_only(translate(statement.sql, statement.dialect).db2_sql or "")


# --------------------------------------------------------------------------
# the test embedding must actually preserve similarity
# --------------------------------------------------------------------------
def _cosine_distance(a, b):
    return 1.0 - sum(x * y for x, y in zip(a, b))


def test_deterministic_embeddings_are_deterministic():
    from src.embeddings import DeterministicEmbeddings

    emb = DeterministicEmbeddings()
    assert emb.embed_query("SQLCODE=-440 GROUP_CONCAT") == emb.embed_query(
        "SQLCODE=-440 GROUP_CONCAT"
    )


def test_deterministic_embeddings_rank_similar_text_closer():
    """Regression: hashing the whole string made recall indistinguishable from
    random, so the fix-memory recall test asserted nothing."""
    from src.embeddings import DeterministicEmbeddings

    emb = DeterministicEmbeddings()
    query = emb.embed_query("SQLCODE=-440 :: no authorized routine named GROUP_CONCAT")
    near = emb.embed_query("SQLCODE=-440 :: no authorized routine GROUP_CONCAT found")
    far = emb.embed_query("SQLCODE=-204 :: PPTEST.WIDGETS is an undefined name")

    assert _cosine_distance(query, near) < _cosine_distance(query, far)


def test_deterministic_embeddings_have_the_db2_vector_width():
    from src.embeddings import EMBEDDING_DIM, DeterministicEmbeddings

    assert len(DeterministicEmbeddings().embed_query("x")) == EMBEDDING_DIM == 384


# --------------------------------------------------------------------------
# corpus and fixture integrity
# --------------------------------------------------------------------------
def test_corpus_case_names_are_unique():
    names = [s.case_name for s in CORPUS]
    assert len(names) == len(set(names))


def test_every_variant_only_uses_known_tables():
    for variant in VARIANTS:
        assert set(variant.rows).issubset(set(FIXTURE_TABLES)), variant.name


def test_variants_have_consistent_column_counts():
    widths: dict[str, set[int]] = {}
    for variant in VARIANTS:
        for table, rows in variant.rows.items():
            for row in rows:
                widths.setdefault(table, set()).add(len(row))
    for table, found in widths.items():
        assert len(found) == 1, f"{table} has rows of differing width: {found}"
