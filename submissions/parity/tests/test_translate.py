"""Tests for the rule translator."""

import pytest

from parity.translate.rules import find_untranslatable, list_rules, translate


def test_clean_query_unchanged():
    result = translate("SELECT id FROM users WHERE id = 1")
    assert result.db2_sql == "SELECT id FROM users WHERE id = 1"
    assert result.applied_rules == ()
    assert result.untranslatable == ()


def test_cast_rule():
    result = translate("SELECT id::text FROM users")
    assert result.db2_sql == "SELECT CAST(id AS VARCHAR(4000)) AS text FROM users"
    assert "cast_double_colon" in result.applied_rules


def test_cast_int_rule():
    result = translate("SELECT x::int FROM t")
    assert "CAST(x AS INTEGER)" in result.db2_sql


def test_ilike_rule():
    result = translate("SELECT name FROM users WHERE name ILIKE 'a%'")
    assert "UPPER(name) LIKE UPPER('a%')" in result.db2_sql


def test_limit_rule():
    result = translate("SELECT id FROM users LIMIT 10")
    assert "FETCH FIRST 10 ROWS ONLY" in result.db2_sql


def test_limit_offset_rule():
    result = translate("SELECT id FROM users LIMIT 10 OFFSET 5")
    assert "OFFSET 5 ROWS FETCH NEXT 10 ROWS ONLY" in result.db2_sql


def test_now_and_random_rules():
    assert "CURRENT_TIMESTAMP" in translate("SELECT now()").db2_sql
    assert "RAND()" in translate("SELECT random()").db2_sql


def test_substring_rule():
    result = translate("SELECT SUBSTRING(name FROM 2 FOR 3) FROM users")
    assert "SUBSTRING(name, 2, 3)" in result.db2_sql


def test_untranslatable_json_arrow():
    result = translate("SELECT data->>'key' FROM t")
    assert "json_arrow_operator" in result.untranslatable
    assert result.needs_agent is True


def test_untranslatable_returning():
    assert "returning_clause" in find_untranslatable("DELETE FROM t RETURNING id")


def test_empty_sql_rejected():
    with pytest.raises(ValueError):
        translate("   ")


def test_rules_listed():
    rules = list_rules()
    assert "cast_double_colon" in rules
    assert "ilike_to_upper_like" in rules
    assert len(rules) >= 6


def test_combined_rewrites_recorded():
    result = translate("SELECT id::int FROM users WHERE name ILIKE 'a%' LIMIT 5")
    assert set(result.applied_rules) == {
        "cast_double_colon",
        "ilike_to_upper_like",
        "limit_offset_to_fetch",
        "alias_expressions",
    }


def test_aggregate_alias_bare_count():
    result = translate("SELECT COUNT(*) FROM demo_users")
    assert result.db2_sql == "SELECT COUNT(*) AS count FROM demo_users"
    assert "alias_expressions" in result.applied_rules


def test_aggregate_alias_lowercase_keeps_lcase():
    result = translate("SELECT count(*) FROM t")
    assert result.db2_sql == "SELECT count(*) AS count FROM t"


def test_alias_expressions_multiple_columns():
    result = translate("SELECT SUM(price), COUNT(*) FROM t")
    assert result.db2_sql == "SELECT SUM(price) AS sum, COUNT(*) AS count FROM t"


def test_alias_expressions_skips_explct_alias():
    assert translate("SELECT COUNT(*) AS total FROM t").db2_sql == "SELECT COUNT(*) AS total FROM t"
    assert "alias_expressions" not in translate(
        "SELECT COUNT(*) AS total FROM t"
    ).applied_rules


def test_alias_expressions_skips_having_and_order():
    result = translate("SELECT dept FROM t GROUP BY dept HAVING COUNT(*) > 1 ORDER BY dept")
    assert "alias_expressions" not in result.applied_rules
    assert "HAVING COUNT(*) > 1" in result.db2_sql
    result = translate("SELECT name FROM t ORDER BY COUNT(*) DESC")
    assert "alias_expressions" not in result.applied_rules
    assert "ORDER BY COUNT(*) DESC" in result.db2_sql


def test_alias_expressions_scalar_function():
    result = translate("SELECT UPPER(name) FROM customers WHERE id = 1")
    assert result.db2_sql == "SELECT UPPER(name) AS upper FROM customers WHERE id = 1"


def test_alias_expressions_extract():
    result = translate("SELECT EXTRACT(YEAR FROM signup_date) FROM customers")
    assert result.db2_sql == (
        "SELECT EXTRACT(YEAR FROM signup_date) AS extract FROM customers"
    )


def test_alias_expressions_arithmetic():
    result = translate("SELECT id, price * stock FROM products")
    assert result.db2_sql == 'SELECT id, price * stock AS "?column?" FROM products'


def test_alias_expressions_leaves_columns_alone():
    result = translate("SELECT id, name FROM customers")
    assert result.db2_sql == "SELECT id, name FROM customers"
    assert "alias_expressions" not in result.applied_rules


def test_alias_expressions_leaves_where_alone():
    result = translate("SELECT id FROM t WHERE UPPER(name) = 'A'")
    assert "AS upper" not in result.db2_sql


def test_alias_expressions_leaves_star_alone():
    result = translate("SELECT * FROM t")
    assert result.db2_sql == "SELECT * FROM t"


def test_alias_expressions_leaves_qualified_star_alone():
    result = translate("SELECT t.* FROM t")
    assert result.db2_sql == "SELECT t.* FROM t"


def test_alias_expressions_keeps_subquery_item():
    """Postgres names a subquery expression ?column?."""
    result = translate("SELECT (SELECT MAX(id) FROM o) FROM c")
    assert result.db2_sql == 'SELECT (SELECT MAX(id) FROM o) AS "?column?" FROM c'


def test_offset_without_limit_becomes_rows():
    result = translate("SELECT id, name FROM products ORDER BY name OFFSET 2")
    assert result.db2_sql == "SELECT id, name FROM products ORDER BY name OFFSET 2 ROWS"
    assert "offset_to_rows" in result.applied_rules


def test_offset_with_limit_not_doubled():
    result = translate("SELECT id FROM t LIMIT 5 OFFSET 2")
    assert result.db2_sql == "SELECT id FROM t OFFSET 2 ROWS FETCH NEXT 5 ROWS ONLY"
    assert "offset_to_rows" not in result.applied_rules
