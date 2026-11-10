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
    if p == "groq":
        from langchain_openai import ChatOpenAI
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # check `python diag_llm.py` / console.groq.com for models your key can use
        extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}  # reasoning models: keep thinking short
        return ChatOpenAI(model=model, base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"),
                          temperature=0, max_tokens=1800, timeout=60, max_retries=3, extra_body=extra or None)
    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"), temperature=0, max_tokens=700)
    if p == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3.1"), temperature=0)
    if p == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"), temperature=0)
    return None  # demo mode: deterministic offline planner


LLM = get_llm()
