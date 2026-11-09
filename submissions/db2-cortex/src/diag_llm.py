import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
from llm import LLM
k = os.getenv("GROQ_API_KEY", "")
print("provider:", os.getenv("LLM_PROVIDER"), "| key length:", len(k), "| model:", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
print("LLM object:", type(LLM).__name__)
try:
    print("REPLY:", LLM.invoke("Reply with the single word OK").content)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e).replace(k, "***")[:500])
    try:
        from openai import OpenAI
        ids = [m.id for m in OpenAI(base_url="https://api.groq.com/openai/v1", api_key=k).models.list().data]
        print("MODELS AVAILABLE TO YOUR KEY:", ids)
    except Exception as e2:
        print("MODEL LIST ERROR:", type(e2).__name__, str(e2).replace(k, "***")[:300])
