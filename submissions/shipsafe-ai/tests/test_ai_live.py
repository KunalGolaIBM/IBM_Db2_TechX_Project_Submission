"""Live AI features on real IBM Db2 + local Granite (Ollama). Nothing is mocked.

- Haystack project memory in a Db2 vector table
- LangChain standards Q&A with Db2 vector retrieval and Granite
- CrewAI fix-and-verify, then the fixed function is EXECUTED against a real Db2 table
"""

import ibm_db
import pytest

from shipsafe.agents import FixCrew, extract_code
from shipsafe.knowledge.standards import verify_citations
from shipsafe.memory import ProjectMemory

pytestmark = pytest.mark.ollama


# ------------------------------------------------------------------ memory
@pytest.fixture(scope="module")
def memory(config, db2_schema, granite):
    m = ProjectMemory(config)
    yield m
    m.close()


def test_remember_and_recall_are_scoped_by_project(memory):
    a = memory.remember("Money amounts are stored as DECIMAL(15,2), never float", kind="decision",
                        project="shop", tags=["Money", " db2 "], author="pytest")
    memory.remember("Every write to the LEDGER table goes through a stored procedure", kind="convention", project="shop")
    memory.remember("Use Pydantic v2 models for every API payload", kind="convention", project="other")
    again = memory.remember("money amounts are stored as  DECIMAL(15,2), never float", project="shop",
                            tags=["money", "db2"])
    assert again["id"] == a["id"]  # same memory, updated not duplicated
    assert memory.count("shop") == 2 and memory.count() >= 3

    hits = memory.recall("add an endpoint that records a refund amount", project="shop")
    assert {h["project"] for h in hits} == {"shop"}
    assert hits[0]["text"].lower().startswith("money amounts")  # the second save updated the wording
    assert hits[0]["tags"] == ["db2", "money"] and 0 < hits[0]["score"] <= 1
    assert all(h["kind"] == "convention" for h in memory.recall("ledger writes", project="shop", kind="convention"))
    assert memory.recall("anything", project="shop", min_similarity=0.99) == []
    memory.forget(a["id"])
    assert memory.count("shop") == 1


@pytest.mark.parametrize("kwargs, message", [
    ({"text": "  "}, "empty"),
    ({"text": "x" * 4001}, "limited"),
    ({"text": "ok", "kind": "rumour"}, "kind must be"),
])
def test_remember_validates_input(memory, kwargs, message):
    with pytest.raises(ValueError, match=message):
        memory.remember(**kwargs)


def test_recall_rejects_empty_query(memory):
    with pytest.raises(ValueError):
        memory.recall("   ")


# ---------------------------------------------------------------- standards
def test_standards_answer_is_grounded_and_cited(services):
    r = services.ask_standards("How must user input be passed into Db2 queries?")
    assert r["citations"][0]["doc_id"] == "POL-DB2-001"
    assert "?" in r["answer"]
    assert r["unverified_citations"] == []
    assert r["model"] == services.config.llm.chat_model
    with pytest.raises(ValueError):
        services.ask_standards("  ")


def test_verify_citations_corrects_and_flags():
    text, cited, unverified = verify_citations(
        "Per POL-DB2-001 and [SEC-POL-002], not [ABC-XYZ-123]; CVE-2020-14343 is untouched.",
        ["POL-DB2-001", "POL-SEC-002"])
    assert "[POL-SEC-002]" in text and "ABC-XYZ-123 (unverified)" in text and "CVE-2020-14343" in text
    assert cited == ["POL-DB2-001", "POL-SEC-002"] and unverified == ["ABC-XYZ-123"]


# ------------------------------------------------------------------ fix crew
VULNERABLE = '''import ibm_db

API_SECRET = "sk_live_9f8e7d6c5b4a3210"


def get_order(conn, order_id):
    sql = f"SELECT ID, TOTAL FROM ORDERS WHERE ID = '{order_id}'"
    stmt = ibm_db.exec_immediate(conn, sql)
    return ibm_db.fetch_assoc(stmt)
'''


@pytest.fixture()
def orders_conn(config, db2_schema):
    conn = ibm_db.connect(config.db2.connection_string(), "", "")
    ibm_db.exec_immediate(conn, f"SET SCHEMA {config.db2.schema}")
    try:
        ibm_db.exec_immediate(conn, "DROP TABLE ORDERS")
    except Exception:
        pass
    ibm_db.exec_immediate(conn, "CREATE TABLE ORDERS (ID VARCHAR(20) NOT NULL PRIMARY KEY, TOTAL DECIMAL(15,2))")
    ibm_db.exec_immediate(conn, "INSERT INTO ORDERS VALUES ('A1', 10.50), ('B2', 99.00)")
    yield conn
    ibm_db.exec_immediate(conn, "DROP TABLE ORDERS")
    ibm_db.close(conn)


def _load(code: str):
    ns: dict = {}
    exec(compile(code, "<fixed>", "exec"), ns)  # noqa: S102 - executing the verified fix is the point of this test
    return ns


def test_original_code_is_really_injectable(orders_conn):
    get_order = _load(VULNERABLE)["get_order"]
    assert get_order(orders_conn, "A1")["ID"] == "A1"
    assert get_order(orders_conn, "x' OR '1'='1")  # the injection returns a row


def test_fix_is_verified_and_works_on_real_db2(services, orders_conn, monkeypatch):
    result = services.fix_code(VULNERABLE, "orders/repository.py", client="pytest")
    assert result["verified"], result["message"] + "\n" + (result["fixed_code"] or "")
    before = {i["rule_id"] for i in result["issues_before"]}
    assert "SQLI-DYNAMIC" in before and before & {"SEC-005", "SEC-006"}
    assert result["issues_after"] == []
    assert result["fix_id"] and result["diff"].startswith("--- a/orders/repository.py")
    assert {p["doc_id"] for p in result["policies"]} >= {"POL-DB2-001"}

    monkeypatch.setenv("API_SECRET", "from-env")
    fixed = _load(result["fixed_code"])
    assert fixed["get_order"](orders_conn, "A1")["ID"] == "A1"            # still works
    assert not fixed["get_order"](orders_conn, "x' OR '1'='1")           # injection no longer returns data
    code = result["fixed_code"]
    assert "sk_live_" not in code and ("os.environ" in code or "getenv" in code)  # secret now comes from the environment
    assert services.repository.list_fix_attempts(limit=1)[0]["VERIFIED"] == 1


def test_clean_code_needs_no_fix(granite):
    r = FixCrew(granite).fix("def add(a, b):\n    return a + b\n", "m.py")
    assert r.verified and r.rounds == 0 and "Nothing to fix" in r.message


def test_extract_code():
    assert extract_code("Here:\n```python\nx = 1\n```\nand\n```\ny = 22222\n```") == "y = 22222\n"
    assert extract_code("plain = True") == "plain = True\n"
    assert extract_code("") == "\n"
