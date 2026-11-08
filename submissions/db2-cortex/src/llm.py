import os
from config import LLM_PROVIDER


def get_llm():
    p = LLM_PROVIDER
    if p == "watsonx":
        from langchain_ibm import ChatWatsonx
        return ChatWatsonx(model_id=os.getenv("WATSONX_MODEL", "ibm/granite-3-3-8b-instruct"), url=os.getenv("WATSONX_URL"),
                           apikey=os.getenv("WATSONX_APIKEY"), project_id=os.getenv("WATSONX_PROJECT_ID"),
                           params={"temperature": 0, "max_new_tokens": 600})
    if p == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
    if p == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3.1"), temperature=0)
    if p == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"), temperature=0)
    return None  # demo mode: deterministic offline planner


LLM = get_llm()
