import math

from redb.memory import hash_embed, normalize_sql, signature


def test_normalize_replaces_literals():
    a = normalize_sql("select * from t where id = 4242 and name = 'Bob'  and x=1.5")
    assert a == "SELECT * FROM T WHERE ID = ? AND NAME = ? AND X=?"
    assert normalize_sql("SELECT * FROM T WHERE ID = 1") == normalize_sql("select *  from t where id = 99")


def test_signature_contains_parts():
    s = signature("SELECT 1 FROM RETAIL.ORDERS WHERE A = 5", ["RETAIL.ORDERS"], ["TBSCAN", "RETURN"])
    assert "RETAIL.ORDERS" in s and "RETURN,TBSCAN" in s and "A = ?" in s


def test_hash_embedding_unit_length_and_similarity():
    a = hash_embed(signature("SELECT * FROM RETAIL.ORDERS WHERE CUSTOMER_ID = 1", ["RETAIL.ORDERS"], ["TBSCAN"]))
    b = hash_embed(signature("SELECT * FROM RETAIL.ORDERS WHERE CUSTOMER_ID = 2", ["RETAIL.ORDERS"], ["TBSCAN"]))
    c = hash_embed("SELECT NAME FROM HR.EMPLOYEES JOIN HR.DEPT ON 1=1")
    assert len(a) == 768
    assert math.isclose(math.sqrt(sum(v * v for v in a)), 1.0, rel_tol=1e-9)
    dot = lambda x, y: sum(p * q for p, q in zip(x, y))  # noqa: E731
    assert math.isclose(dot(a, b), 1.0)
    assert dot(a, c) < 0.5
