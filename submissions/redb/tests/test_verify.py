from redb.verify import equivalence_sql, has_outer_order_by, prove


def test_equivalence_sql():
    sql = equivalence_sql("SELECT A FROM T;", "SELECT A FROM U")
    assert sql == ("SELECT (SELECT COUNT(*) FROM ((SELECT * FROM (SELECT A FROM T) X) EXCEPT ALL "
                   "(SELECT * FROM (SELECT A FROM U) Y)) D1) AS A_MINUS_B, "
                   "(SELECT COUNT(*) FROM ((SELECT * FROM (SELECT A FROM U) X) EXCEPT ALL "
                   "(SELECT * FROM (SELECT A FROM T) Y)) D2) AS B_MINUS_A FROM SYSIBM.SYSDUMMY1")


def test_outer_order_by():
    assert has_outer_order_by("SELECT A FROM T ORDER BY A")
    assert not has_outer_order_by("SELECT A FROM (SELECT A FROM T ORDER BY A) X")
    assert not has_outer_order_by("SELECT 'ORDER BY' FROM T")


class FakeDb:
    def __init__(self, counts, rows=None, fail=False):
        self.counts, self.rows, self.fail = counts, rows or {}, fail

    def query(self, sql, params=None):
        if self.fail:
            raise RuntimeError("SQL0104N")
        if "EXCEPT ALL" in sql:
            return [{"A_MINUS_B": self.counts[0], "B_MINUS_A": self.counts[1]}]
        return self.rows[sql]


def test_prove_outcomes():
    assert prove(FakeDb((0, 0)), "SELECT A FROM T", "SELECT A FROM U")["proven"]
    assert not prove(FakeDb((0, 2)), "SELECT A FROM T", "SELECT A FROM U")["proven"]
    assert not prove(FakeDb((0, 0), fail=True), "SELECT A FROM T", "SELECT A FROM U")["proven"]
    rows = {"SELECT A FROM T ORDER BY A": [{"A": 1}, {"A": 2}], "SELECT A FROM U ORDER BY A DESC": [{"A": 2}, {"A": 1}]}
    assert not prove(FakeDb((0, 0), rows), "SELECT A FROM T ORDER BY A", "SELECT A FROM U ORDER BY A DESC")["proven"]
