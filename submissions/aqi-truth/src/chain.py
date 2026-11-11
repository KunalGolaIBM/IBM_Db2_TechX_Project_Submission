"""The question box's model step, built with LangChain (LCEL, langchain-core + langchain-ollama).

    PromptTemplate (schema, worked examples, question)
      | OllamaLLM: IBM Granite 4.0 micro on the local Ollama server, temperature 0
      | StrOutputParser
      | RunnableLambda(extract)       -> one SQL statement
      | RunnableLambda(run)           -> ask.check_sql (sqlglot: one SELECT, only AQ.V_DAY / AQ.V_CHECK, row cap)
                                         then Db2 runs it as AQREADER with a query timeout

LangChain orchestrates the model call; it adds no capability past it. The safety checks and Db2's own
privileges decide what runs, exactly as before. "AI explains, code computes."
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_ollama import OllamaLLM
import ask, llm

PROMPT = PromptTemplate.from_template(ask.TEMPLATE).partial(schema=ask.SCHEMA, examples=ask.EXAMPLES)

def granite(max_tokens=200):
    """IBM Granite through langchain-ollama, with the same settings as llm.py (keep_alive -1: stay in memory)."""
    return OllamaLLM(model=llm.MODEL, base_url=llm.OLLAMA, temperature=0, num_predict=max_tokens, keep_alive=-1).bind(system=ask.SYSTEM)

def sql_chain(model=None):
    """Question -> raw model text (streamable token by token). `model` lets tests pass a fake LLM."""
    return PROMPT | (model or granite()) | StrOutputParser()

def answer_chain(conn=None, model=None):
    """Question -> checked SQL -> Db2 result dict (refused / BLOCKED / DB2_ERROR / ANSWERED)."""
    return sql_chain(model) | RunnableLambda(ask.extract) | RunnableLambda(lambda sql: ask.run(sql, conn))
