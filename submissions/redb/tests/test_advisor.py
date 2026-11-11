import pytest

from redb.advisor import consolidate, has_parameter_markers, index_ddl, parse_colnames, valid_ident


def test_parse_colnames():
    assert parse_colnames("+CUSTOMER_ID-ORDER_DATE") == [("CUSTOMER_ID", "ASC"), ("ORDER_DATE", "DESC")]
    assert parse_colnames(" +A ") == [("A", "ASC")]
    with pytest.raises(ValueError):
        parse_colnames("")


def test_index_ddl_is_non_unique_and_reversible():
    name, ddl, undo = index_ddl("RETAIL", "ORDERS", [("CUSTOMER_ID", "ASC"), ("ORDER_DATE", "DESC")])
    assert name.startswith("REDB_IX_ORDERS_")
    assert ddl == f'CREATE INDEX "RETAIL"."{name}" ON "RETAIL"."ORDERS" ("CUSTOMER_ID" ASC, "ORDER_DATE" DESC)'
    assert "UNIQUE" not in ddl
    assert undo == f'DROP INDEX "RETAIL"."{name}"'
    # deterministic
    assert index_ddl("RETAIL", "ORDERS", [("CUSTOMER_ID", "ASC"), ("ORDER_DATE", "DESC")])[0] == name


@pytest.mark.parametrize("bad", ['ORD"ERS', "orders", "A B", "X;DROP", ""])
def test_identifier_validation(bad):
    assert not valid_ident(bad)
    with pytest.raises(ValueError):
        index_ddl("RETAIL", bad, [("A", "ASC")])
    with pytest.raises(ValueError):
        index_ddl("RETAIL", "T", [(bad, "ASC")])


def test_identifier_ok():
    assert valid_ident("ORDER_ITEMS") and valid_ident("A#1$@")


def test_parameter_markers():
    assert has_parameter_markers("SELECT * FROM T WHERE A = ?")
    assert has_parameter_markers("SELECT * FROM T WHERE A = :hv")
    assert not has_parameter_markers("SELECT * FROM T WHERE A = '?' AND B = 'x:y'")


def test_index_ddl_with_explicit_name_and_bad_direction():
    name, ddl, undo = index_ddl("RETAIL", "CUSTOMERS", [("SIGNUP_DATE", "ASC")], name="IX_OLD")
    assert name == "IX_OLD" and ddl == 'CREATE INDEX "RETAIL"."IX_OLD" ON "RETAIL"."CUSTOMERS" ("SIGNUP_DATE" ASC)'
    with pytest.raises(ValueError):
        index_ddl("RETAIL", "T", [("A", "ASC; DROP")])


def test_consolidate_drops_redundant_index_but_keeps_needed_ones():
    a, b, c = ({"name": n, "size_mb": s} for n, s in (("A", 10), ("B", 30), ("C", 5)))
    # B is redundant when A exists; C carries most of the gain
    def cost(kept):
        names = {k["name"] for k in kept}
        return 1000 - (600 if "C" in names else 0) - (300 if names & {"A", "B"} else 0)
    kept, dropped = consolidate([a, b, c], cost, baseline=1000)
    assert [k["name"] for k in kept] == ["A", "C"] and [d["name"] for d in dropped] == ["B"]
