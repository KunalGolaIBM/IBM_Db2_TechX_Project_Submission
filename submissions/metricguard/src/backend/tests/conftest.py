def pytest_configure(config):
    config.addinivalue_line("markers", "db2: requires a live IBM Db2 connection (set MG_RUN_DB2_TESTS=1)")
    config.addinivalue_line("markers", "live_llm: calls the real Anthropic API (set MG_RUN_LIVE_LLM_TESTS=1)")
