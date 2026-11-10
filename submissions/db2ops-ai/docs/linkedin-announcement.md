# LinkedIn announcement draft

I’m building **Db2Ops AI**, an intelligent database copilot for IBM Db2.

Business teams often need help translating a question into SQL. Db2Ops AI lets a user ask questions in plain language, reviews the generated Db2 SQL through a read-only validation layer, and presents the records returned by the database in tables and interactive charts.

The implementation uses Streamlit, IBM Db2 with the `ibm_db` Python driver, LangChain prompt chains, SQLGlot for Db2 SQL parsing, Pandas, and Plotly. The application is designed to use real Db2 records; it does not substitute a local mock database when Db2 is disconnected.

I’m working through how to make text-to-SQL useful while keeping the database boundary visible: the generated SQL can be reviewed, validated, and constrained before execution. I’m also learning how much the final result depends on reproducible database setup and clear reporting of what has and has not been verified.

The local Db2 installation and live connection still need to be completed before I can share a verified end-to-end demo.

#IBMDb2 #LangChain #Python #DataEngineering #AI
