# Required genuine screenshots

Do not submit mock, generated or placeholder screenshots as proof. Capture these only after running the application against your own services:

1. `01_db2_connection.png` — VS Code IBM Db2 Developer Extension showing a successful connection to your Db2 instance (hide passwords/host secrets if needed).
2. `02_db2_tables.png` — Db2 object explorer or SQL results showing `ESAI_EQUIPMENT`, `ESAI_TELEMETRY` and `ESAI_EVENTS` with your inserted demo rows.
3. `03_api_docs.png` — FastAPI Swagger UI showing a successful telemetry POST and analysis response.
4. `04_dashboard.png` — EnergySense AI Streamlit dashboard using the same demo readings.
5. `05_agent_tool_result.png` — optional LangChain assistant response grounded in a telemetry tool call and Db2 maintenance-note retrieval.
6. `06_db2_vector_search.png` — optional DB2VS maintenance retrieval result (requires Db2 vector-search support).

Only include screenshots captured on your machine. Remove API keys, database credentials and private personal information before committing them.
