from issuesmith.db import Db2Repository


def test_schema_statements_are_complete_and_parameterised():
    repo = Db2Repository(conn=None, schema="ISSUESMITH")
    stmts = repo._schema_statements(dim=384)
    bodies = [b for _, b in stmts]
    assert len(stmts) == 15
    assert all("{schema}" not in b and "{dim}" not in b for b in bodies)
    assert any("VECTOR(384, FLOAT32)" in b for b in bodies)
    proc = [b for b in bodies if "FIND_SIMILAR_INCIDENTS" in b][0]
    assert "VECTOR_DISTANCE(T.EMBEDDING, O.EMBEDDING, COSINE)" in proc and proc.rstrip().endswith("END")
    optional = [b for opt, b in stmts if opt]
    assert len(optional) == 1 and "JSON_VALUE" in optional[0]
    assert not any(line.strip().startswith("--") for b in bodies for line in b.splitlines())
