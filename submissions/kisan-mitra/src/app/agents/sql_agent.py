"""
Text-to-SQL Agent for Kisan Mitra (किसान मित्र)
Translates farmer queries in Hindi, Hinglish, and English into optimized IBM Db2 SQL queries.
Executes against the MANDI_PRICES table under read-only safety constraints and formats results.
"""

import re
from typing import Dict, Any, List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from langchain_core.messages import SystemMessage, HumanMessage

from app.db_client import get_db_client
from app.agents.llm import get_llm

SQL_PROMPT_TEMPLATE = """You are an expert IBM Db2 SQL Engineer specializing in Indian agricultural market intelligence (Agmarknet).
Your job is to convert a user question into a single, syntactically correct, highly optimized READ-ONLY SELECT SQL query for IBM Db2.

Database Schema:
Table: MANDI_PRICES
Columns:
- state VARCHAR(64) - e.g. 'Uttar Pradesh', 'Punjab', 'Haryana', 'Madhya Pradesh'
- district VARCHAR(64) - e.g. 'Mathura', 'Agra', 'Aligarh', 'Lucknow', 'Kanpur Nagar', 'Varanasi', 'Bareilly', 'Meerut'
- market VARCHAR(128) - e.g. 'Mathura', 'Kosi Kalan', 'Agra', 'Fatehabad', 'Lucknow', 'Khair'
- commodity VARCHAR(128) - Commodity in Title Case. E.g. 'Potato' (Aloo), 'Wheat' (Gehun), 'Mustard' (Sarson), 'Onion' (Pyaz), 'Tomato' (Tamatar), 'Rice' (Chawal/Dhan), 'Gram' (Chana), 'Sugarcane' (Ganna)
- variety VARCHAR(128) - e.g. 'Desi', 'Dara', 'Black', 'Hybrid', 'FAQ'
- arrival_date DATE - Date of market arrival (YYYY-MM-DD)
- min_price DECIMAL(10,2) - Minimum price in Rs per quintal
- max_price DECIMAL(10,2) - Maximum price in Rs per quintal
- modal_price DECIMAL(10,2) - Modal/most frequent price in Rs per quintal

Rules & Guardrails:
1. Output ONLY the raw SQL query. Do not wrap in markdown ```sql ... ``` codeblocks, do not add explanations.
2. Only generate SELECT queries. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or TRUNCATE.
3. For recent or today's prices, order by arrival_date DESC.
4. For weekly or historical comparisons (e.g. 'pichhle hafte' / 'last week'), use: arrival_date >= CURRENT DATE - 7 DAYS.
5. In IBM Db2, limit rows using: FETCH FIRST <N> ROWS ONLY (e.g. FETCH FIRST 10 ROWS ONLY).
6. Match commodities accurately:
   - 'aloo' / 'aalu' / 'potato' -> 'Potato'
   - 'gehun' / 'gehu' / 'wheat' -> 'Wheat'
   - 'sarson' / 'mustard' -> 'Mustard'
   - 'pyaz' / 'onion' -> 'Onion'
   - 'tamatar' / 'tomato' -> 'Tomato'
   - 'chawal' / 'dhan' / 'rice' -> 'Rice' or 'Paddy'
   - 'chana' / 'gram' -> 'Gram'
7. Unless another state is explicitly asked, filter by state = 'Uttar Pradesh'.
"""

ANSWER_SYNTHESIS_PROMPT = """You are Kisan Mitra (किसान मित्र), a warm, supportive, and knowledgeable AI assistant for Indian farmers.
Synthesize a clear, concise, and farmer-friendly answer to the user's question based on the SQL query results.

Guidelines:
1. Reply in the SAME language and tone as the user query (Hindi Devanagari, Hinglish, or English).
2. Clearly highlight: Commodity, Market/Mandi, Date, and Modal Price (Rs/quintal).
3. If prices from multiple markets are returned, briefly mention the highest, lowest, or difference.
4. Keep the explanation brief, practical, and respectful.
"""

class SqlAgent:
    """Agent that translates natural language questions into Db2 SQL and executes them safely."""

    def __init__(self):
        self.db = get_db_client(read_only=True)
        self.llm = get_llm(temperature=0.1)

    def generate_sql(self, question: str) -> str:
        """Use LLM to generate syntactically correct Db2 SQL with graceful fallback."""
        messages = [
            SystemMessage(content=SQL_PROMPT_TEMPLATE),
            HumanMessage(content=f"User Question: {question}\nGenerate IBM Db2 SQL:")
        ]
        try:
            response = self.llm.invoke(messages)
            sql = response.content.strip()
        except Exception as err:
            from app.agents.llm import MockOfflineChatModel
            response = MockOfflineChatModel().invoke(messages)
            sql = response.content.strip()

        # Clean any markdown code fences if present
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
        return sql.strip()

    def run(self, question: str) -> Dict[str, Any]:
        """End-to-end pipeline: Question -> SQL -> Db2 Execution -> Natural Language Answer + Visuals."""
        # 1. Generate SQL
        generated_sql = self.generate_sql(question)
        
        # 2. Execute on Db2
        try:
            query_res = self.db.execute_query(generated_sql)
            rows = query_res["rows"]
            columns = query_res["columns"]
            latency_ms = query_res["latency_ms"]
            error = None
        except Exception as e:
            rows = []
            columns = []
            latency_ms = 0.0
            error = str(e)

        # 3. Synthesize Natural Language Answer
        if error:
            answer = f"क्षमा करें, क्वेरी निष्पादित करने में समस्या आई: {error}"
            chart_json = None
        elif not rows:
            answer = "दिए गए विवरण के अनुसार मंडी में कोई रिकॉर्ड नहीं मिला। कृपया मंडी या फसल का नाम जांचें।"
            chart_json = None
        else:
            synth_messages = [
                SystemMessage(content=ANSWER_SYNTHESIS_PROMPT),
                HumanMessage(content=(
                    f"Farmer Question: {question}\n"
                    f"Generated SQL: {generated_sql}\n"
                    f"Query Results ({len(rows)} records): {rows[:8]}\n\n"
                    f"Generate a friendly answer in the farmer's language:"
                ))
            ]
            try:
                ans_res = self.llm.invoke(synth_messages)
                answer = ans_res.content.strip()
            except Exception:
                from app.agents.llm import MockOfflineChatModel
                ans_res = MockOfflineChatModel().invoke(synth_messages)
                answer = ans_res.content.strip()

            # 4. Generate Plotly chart if tabular data has numbers
            chart_json = self._create_chart(rows, columns, question)

        return {
            "question": question,
            "generated_sql": generated_sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "latency_ms": latency_ms,
            "answer": answer,
            "chart_json": chart_json,
            "error": error,
            "engine": self.db.engine_type,
        }

    def _create_chart(self, rows: List[Dict[str, Any]], columns: List[str], question: str) -> Optional[str]:
        """Generate an interactive Plotly chart if numerical price data is present."""
        if not rows or len(rows) < 1:
            return None
        df = pd.DataFrame(rows)
        
        # Check price column
        price_col = None
        for col in ["modal_price", "max_price", "min_price", "price", "MODAL_PRICE", "MAX_PRICE"]:
            if col in df.columns:
                price_col = col
                break
                
        if not price_col:
            return None

        # Convert price to numeric
        df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
        df = df.dropna(subset=[price_col])
        if df.empty:
            return None

        # Determine label column
        label_col = "market" if "market" in df.columns else ("commodity" if "commodity" in df.columns else ("district" if "district" in df.columns else df.columns[0]))

        # Bar chart or line chart
        if "arrival_date" in df.columns and len(df["arrival_date"].unique()) > 1:
            fig = px.line(
                df, x="arrival_date", y=price_col, color=label_col if label_col != "arrival_date" else None,
                markers=True,
                title=f"Mandi Price Trend (₹ / Quintal)",
                labels={price_col: "Price (₹/Qtl)", "arrival_date": "Date"}
            )
        else:
            fig = px.bar(
                df, x=label_col, y=price_col, color=label_col,
                text_auto=True,
                title=f"Mandi Price Comparison (₹ / Quintal)",
                labels={price_col: "Modal Price (₹/Qtl)", label_col: "Mandi / Commodity"}
            )
        
        fig.update_layout(
            template="plotly_white",
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False if len(df) <= 5 else True
        )
        return fig.to_json()


def get_sql_agent() -> SqlAgent:
    """Factory helper for SqlAgent."""
    return SqlAgent()
