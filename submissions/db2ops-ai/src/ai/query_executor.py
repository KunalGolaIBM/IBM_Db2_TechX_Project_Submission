"""Validated AI query execution boundary."""
from src.ai.sql_validator import validate_sql
from src.config import get_settings
from src.database.connection import query_dataframe


def execute_read_query(sql: str):
    safe_sql = validate_sql(sql)
    settings = get_settings()
    # Defense in depth: FETCH FIRST bounds the returned rows even if the model omitted it.
    if "FETCH FIRST" not in safe_sql.upper() and "FETCH NEXT" not in safe_sql.upper():
        safe_sql = f"{safe_sql.rstrip().rstrip(';')} FETCH FIRST {settings.db2_max_rows} ROWS ONLY"
    return query_dataframe(safe_sql, settings=settings)
