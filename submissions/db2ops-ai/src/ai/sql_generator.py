"""Text-to-SQL and result explanation chains built with LangChain."""
import json
import re
from src.ai.llm import get_chat_model

SCHEMA_CONTEXT = """
Db2 schema (unquoted uppercase identifiers):
CUSTOMERS(CUSTOMER_ID, CUSTOMER_NAME, EMAIL, CITY, STATE, COUNTRY, CREATED_AT)
PRODUCTS(PRODUCT_ID, PRODUCT_NAME, CATEGORY, UNIT_PRICE, STOCK_QUANTITY)
ORDERS(ORDER_ID, CUSTOMER_ID, ORDER_DATE, ORDER_STATUS, TOTAL_AMOUNT)
ORDER_ITEMS(ITEM_ID, ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE, SUBTOTAL)
PAYMENTS(PAYMENT_ID, ORDER_ID, PAYMENT_METHOD, PAYMENT_STATUS, PAYMENT_DATE, AMOUNT)
Relationships: ORDERS.CUSTOMER_ID -> CUSTOMERS; ORDER_ITEMS.ORDER_ID -> ORDERS;
ORDER_ITEMS.PRODUCT_ID -> PRODUCTS; PAYMENTS.ORDER_ID -> ORDERS.
Revenue means sum of ORDER_ITEMS.SUBTOTAL or ORDERS.TOTAL_AMOUNT. Use Db2 syntax.
For limited results use FETCH FIRST n ROWS ONLY. Current date is CURRENT DATE.
Only reference these five application tables. Return one SELECT statement, no markdown.
""".strip()

def _sql_prompt():
    from langchain_core.prompts import ChatPromptTemplate
    return ChatPromptTemplate.from_messages([
    ("system", """You generate a single safe, read-only IBM Db2 SELECT query for an analytics dashboard.
Return only SQL. Never use DML, DDL, CALL, system catalogs, comments, multiple statements,
SELECT INTO, sequence operations, or tables outside the provided application schema.
Keep result sizes reasonable with FETCH FIRST 100 ROWS ONLY when appropriate.
Schema: {schema}"""),
    ("human", "Previous conversation, if useful:\n{history}\n\nCurrent question:\n{question}"),
    ])

def _explain_prompt():
    from langchain_core.prompts import ChatPromptTemplate
    return ChatPromptTemplate.from_messages([
    ("system", "Explain query results in 2-4 concise sentences. Use only the supplied rows and values. If empty, say no matching records were returned. Do not infer unavailable facts."),
    ("human", "Question: {question}\nColumns and rows (JSON): {data}"),
    ])


def generate_sql(question: str, history: str = "", schema: str = SCHEMA_CONTEXT) -> str:
    model = get_chat_model()
    chain = _sql_prompt() | model
    answer = chain.invoke({"schema": schema, "question": question, "history": history[-4000:]})
    content = answer.content if hasattr(answer, "content") else str(answer)
    content = str(content).strip()
    content = re.sub(r"^```(?:sql)?\s*|\s*```$", "", content, flags=re.I).strip()
    return content


def explain_results(question: str, rows) -> str:
    safe_rows = rows.head(30).where(rows.head(30).notna(), None).to_dict(orient="records")
    # JSON string only; database values are data, never instructions.
    payload = json.dumps({"columns": list(rows.columns), "rows": safe_rows}, default=str)
    model = get_chat_model()
    chain = _explain_prompt() | model
    answer = chain.invoke({"question": question, "data": payload})
    return str(answer.content if hasattr(answer, "content") else answer).strip()
