"""Mock IBM Db2 LUW Sandbox Engine.

Provides an offline, high-fidelity in-memory Db2 LUW environment for testing,
development, and seamless failover when a live Db2 instance is unconfigured.
"""

from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


class MockDb2Sandbox:
    """In-memory mock database simulating IBM Db2 LUW."""

    def __init__(self, dbname: str = "BLUDB") -> None:
        self.dbname = dbname.upper()
        self.created_at = datetime.now(timezone.utc).isoformat()
        self._tables: Dict[str, List[Dict[str, Any]]] = {}
        self._schemas: Dict[str, Dict[str, str]] = {}
        self._seed_default_schema()

    def _seed_default_schema(self) -> None:
        """Initializes default tables and sample market/risk data."""
        # 1. MARKET_BARS
        self._schemas["MARKET_BARS"] = {
            "ID": "BIGINT",
            "SYMBOL": "VARCHAR(32)",
            "TIMESTAMP": "TIMESTAMP",
            "OPEN": "DECIMAL(18, 4)",
            "HIGH": "DECIMAL(18, 4)",
            "LOW": "DECIMAL(18, 4)",
            "CLOSE": "DECIMAL(18, 4)",
            "VOLUME": "BIGINT",
        }
        self._tables["MARKET_BARS"] = [
            {
                "ID": 1,
                "SYMBOL": "AAPL",
                "TIMESTAMP": "2026-10-27 15:30:00",
                "OPEN": 230.50,
                "HIGH": 232.10,
                "LOW": 229.80,
                "CLOSE": 231.45,
                "VOLUME": 45210000,
            },
            {
                "ID": 2,
                "SYMBOL": "AAPL",
                "TIMESTAMP": "2026-10-28 15:30:00",
                "OPEN": 231.50,
                "HIGH": 234.00,
                "LOW": 231.10,
                "CLOSE": 233.80,
                "VOLUME": 48190000,
            },
            {
                "ID": 3,
                "SYMBOL": "RELIANCE.NS",
                "TIMESTAMP": "2026-10-28 15:30:00",
                "OPEN": 2980.00,
                "HIGH": 3015.50,
                "LOW": 2972.10,
                "CLOSE": 3008.25,
                "VOLUME": 7890000,
            },
            {
                "ID": 4,
                "SYMBOL": "INFY.NS",
                "TIMESTAMP": "2026-10-28 15:30:00",
                "OPEN": 1890.00,
                "HIGH": 1920.00,
                "LOW": 1885.00,
                "CLOSE": 1912.40,
                "VOLUME": 5420000,
            },
        ]

        # 2. CONFORMAL_RESIDUALS
        self._schemas["CONFORMAL_RESIDUALS"] = {
            "ID": "BIGINT",
            "SYMBOL": "VARCHAR(32)",
            "TIMESTAMP": "TIMESTAMP",
            "MODEL_ID": "VARCHAR(64)",
            "SCORE": "DOUBLE",
            "ALPHA": "DOUBLE",
            "INTERVAL_LOWER": "DECIMAL(18, 4)",
            "INTERVAL_UPPER": "DECIMAL(18, 4)",
            "COVERED": "SMALLINT",
        }
        self._tables["CONFORMAL_RESIDUALS"] = [
            {
                "ID": 1,
                "SYMBOL": "AAPL",
                "TIMESTAMP": "2026-10-28 15:30:00",
                "MODEL_ID": "lgbm_conformal_v2",
                "SCORE": 0.0125,
                "ALPHA": 0.05,
                "INTERVAL_LOWER": 228.10,
                "INTERVAL_UPPER": 238.20,
                "COVERED": 1,
            },
            {
                "ID": 2,
                "SYMBOL": "RELIANCE.NS",
                "TIMESTAMP": "2026-10-28 15:30:00",
                "MODEL_ID": "lgbm_conformal_v2",
                "SCORE": 0.0210,
                "ALPHA": 0.05,
                "INTERVAL_LOWER": 2920.00,
                "INTERVAL_UPPER": 3090.00,
                "COVERED": 1,
            },
            {
                "ID": 3,
                "SYMBOL": "INFY.NS",
                "TIMESTAMP": "2026-10-28 15:30:00",
                "MODEL_ID": "lgbm_conformal_v2",
                "SCORE": 0.0450,
                "ALPHA": 0.05,
                "INTERVAL_LOWER": 1860.00,
                "INTERVAL_UPPER": 1965.00,
                "COVERED": 1,
            },
        ]

        # 3. PORTFOLIO_RISK
        self._schemas["PORTFOLIO_RISK"] = {
            "PORTFOLIO_ID": "VARCHAR(32)",
            "SYMBOL": "VARCHAR(32)",
            "VAR_95": "DOUBLE",
            "CVAR_95": "DOUBLE",
            "VOLATILITY": "DOUBLE",
            "MAX_DRAWDOWN": "DOUBLE",
            "STATUS": "VARCHAR(16)",
        }
        self._tables["PORTFOLIO_RISK"] = [
            {
                "PORTFOLIO_ID": "ALPHA_CORE",
                "SYMBOL": "AAPL",
                "VAR_95": 0.024,
                "CVAR_95": 0.038,
                "VOLATILITY": 0.182,
                "MAX_DRAWDOWN": 0.085,
                "STATUS": "OPTIMAL",
            },
            {
                "PORTFOLIO_ID": "ALPHA_CORE",
                "SYMBOL": "RELIANCE.NS",
                "VAR_95": 0.019,
                "CVAR_95": 0.029,
                "VOLATILITY": 0.165,
                "MAX_DRAWDOWN": 0.062,
                "STATUS": "OPTIMAL",
            },
        ]

        # 4. DB2_VECTOR_STORE
        self._schemas["DB2_VECTOR_STORE"] = {
            "DOC_ID": "VARCHAR(64)",
            "CONTENT": "CLOB",
            "METADATA_JSON": "VARCHAR(2048)",
            "EMBEDDING": "BLOB",
            "CREATED_AT": "TIMESTAMP",
        }
        self._tables["DB2_VECTOR_STORE"] = [
            {
                "DOC_ID": "doc_101",
                "CONTENT": "Quarterly financial risk disclosure: Low tail risk observed across equity holdings with 95% conformal interval coverage maintained at 96.2%.",
                "METADATA_JSON": json.dumps({"source": "10-Q", "symbol": "AAPL", "year": 2026}),
                "EMBEDDING": [0.12, 0.45, -0.23, 0.88, 0.05],
                "CREATED_AT": "2026-10-25 10:00:00",
            },
            {
                "DOC_ID": "doc_102",
                "CONTENT": "Algorithmic execution review: Conformal prediction quantiles provided effective slippage guards during high volatility intraday auctions.",
                "METADATA_JSON": json.dumps({"source": "RiskDesk", "symbol": "RELIANCE.NS", "year": 2026}),
                "EMBEDDING": [0.10, 0.42, -0.19, 0.81, 0.09],
                "CREATED_AT": "2026-10-26 14:15:00",
            },
        ]

    def list_tables(self) -> List[str]:
        """Returns all table names in this mock catalog."""
        return sorted(list(self._tables.keys()))

    def describe_table(self, table_name: str) -> List[Dict[str, str]]:
        """Describes column names and types for a given table."""
        name = table_name.strip().upper()
        if name not in self._schemas:
            raise ValueError(f"Table '{table_name}' does not exist in Db2 database '{self.dbname}'")
        return [
            {"COLNAME": col, "TYPENAME": dtype}
            for col, dtype in self._schemas[name].items()
        ]

    def execute_query(
        self, sql: str, params: Optional[Union[Tuple[Any, ...], List[Any], Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Executes a SELECT query against the mock sandbox."""
        clean_sql = sql.strip().strip(";")
        upper_sql = clean_sql.upper()

        # Handle SYSCAT.TABLES inspection
        if "SYSCAT.TABLES" in upper_sql:
            return [
                {"TABSCHEMA": "DB2INST1", "TABNAME": t, "TYPE": "T"}
                for t in self.list_tables()
            ]

        # Handle SYSCAT.COLUMNS inspection
        if "SYSCAT.COLUMNS" in upper_sql:
            match = re.search(r"TABNAME\s*=\s*'([^']+)'", clean_sql, re.IGNORECASE)
            target_tab = match.group(1).upper() if match else self.list_tables()[0]
            if target_tab in self._schemas:
                return [
                    {"TABNAME": target_tab, "COLNAME": c, "TYPENAME": t}
                    for c, t in self._schemas[target_tab].items()
                ]
            return []

        # Find target table
        target_table: Optional[str] = None
        for tbl in self._tables.keys():
            if re.search(r"\bFROM\s+" + tbl + r"\b", upper_sql):
                target_table = tbl
                break

        if not target_table:
            # Fallback table discovery
            match = re.search(r"\bFROM\s+([A-Za-z0-9_]+)", upper_sql)
            if match:
                candidate = match.group(1).upper()
                if candidate in self._tables:
                    target_table = candidate

        if not target_table:
            # Dual or constant select (e.g., SELECT 1 FROM SYSIBM.SYSDUMMY1)
            if "SYSDUMMY1" in upper_sql:
                return [{"1": 1}]
            return [{"STATUS": "OK", "MESSAGE": "Mock Db2 query executed successfully"}]

        rows = [dict(row) for row in self._tables[target_table]]

        # Parameter binding
        if params and isinstance(params, (list, tuple)) and "?" in clean_sql:
            # Simple parameter substitution for WHERE clauses
            where_match = re.search(r"WHERE\s+([A-Za-z0-9_]+)\s*=\s*\?", clean_sql, re.IGNORECASE)
            if where_match and len(params) > 0:
                col = where_match.group(1).upper()
                val = params[0]
                rows = [r for r in rows if str(r.get(col, "")).upper() == str(val).upper()]

        # Basic WHERE SYMBOL = '...' filtering
        sym_match = re.search(r"WHERE\s+SYMBOL\s*=\s*['\"]([^'\"]+)['\"]", clean_sql, re.IGNORECASE)
        if sym_match:
            symbol_filter = sym_match.group(1).upper()
            rows = [r for r in rows if r.get("SYMBOL", "").upper() == symbol_filter]

        # Handle COUNT(*)
        if "COUNT(*)" in upper_sql:
            return [{"COUNT": len(rows)}]

        # Handle FETCH FIRST n ROWS ONLY
        limit_match = re.search(r"FETCH\s+FIRST\s+(\d+)\s+ROWS\s+ONLY", clean_sql, re.IGNORECASE)
        if limit_match:
            n = int(limit_match.group(1))
            rows = rows[:n]

        # Handle LIMIT n (transpiled or direct)
        lim_match = re.search(r"\bLIMIT\s+(\d+)\b", clean_sql, re.IGNORECASE)
        if lim_match and not limit_match:
            n = int(lim_match.group(1))
            rows = rows[:n]

        return rows

    def execute_statement(
        self, sql: str, params: Optional[Union[Tuple[Any, ...], List[Any], Dict[str, Any]]] = None
    ) -> int:
        """Executes INSERT / UPDATE / DELETE statement."""
        clean_sql = sql.strip().strip(";")
        upper_sql = clean_sql.upper()

        if upper_sql.startswith("INSERT INTO"):
            match = re.search(r"INSERT\s+INTO\s+([A-Za-z0-9_]+)", clean_sql, re.IGNORECASE)
            if match:
                table = match.group(1).upper()
                if table not in self._tables:
                    self._tables[table] = []
                    self._schemas[table] = {"ID": "BIGINT", "DATA": "VARCHAR(256)"}

                new_row = {"ID": len(self._tables[table]) + 1, "CREATED_AT": datetime.now(timezone.utc).isoformat()}
                if isinstance(params, dict):
                    new_row.update(params)
                elif isinstance(params, (list, tuple)):
                    for idx, val in enumerate(params):
                        new_row[f"COL_{idx + 1}"] = val
                self._tables[table].append(new_row)
                return 1

        if upper_sql.startswith("UPDATE"):
            return 1

        if upper_sql.startswith("DELETE"):
            return 1

        return 0

    def explain_plan(self, sql: str) -> Dict[str, Any]:
        """Simulates IBM Db2 Visual Explain plan operator graph."""
        return {
            "statement": sql,
            "optimizer": "IBM Db2 Cost-Based Optimizer (Simulated)",
            "total_cost": 142.50,
            "estimated_cardinality": 4200,
            "operators": [
                {"id": 1, "type": "RETURN", "cost": 142.50},
                {"id": 2, "type": "TBSCAN", "table": "MARKET_BARS", "cost": 110.20},
                {"id": 3, "type": "SORT", "cost": 32.30},
            ],
            "index_recommended": False,
        }

