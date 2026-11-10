import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

needs_db2 = pytest.mark.skipif(not os.getenv("DB2_PASSWORD"), reason="set DB2_PASSWORD to run against a real Db2")

@pytest.fixture(scope="session")
def conn():
    # Autocommit off, so a test's rollback really discards its writes (the tests run against the live data).
    from db import connect
    c = connect(autocommit=False)
    yield c
    c.rollback(); c.close()

@pytest.fixture(scope="session")
def reader_conn():
    import ibm_db_dbi
    from ask import reader
    c = ibm_db_dbi.Connection(reader())
    yield c
    c.close()

@pytest.fixture(scope="session")
def app_conn():
    from db import connect_app
    if not os.getenv("DB2_APP_PASSWORD"): pytest.skip("set DB2_APP_PASSWORD to test the app's Db2 ID")
    c = connect_app(); c.set_autocommit(False)
    yield c
    c.rollback(); c.close()
