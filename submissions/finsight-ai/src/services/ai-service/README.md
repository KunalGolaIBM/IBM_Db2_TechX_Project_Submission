# FinSight AI — Python AI Service

This service provides:
1. **LangChain & IBM Db2 Vector Search**: Semantic search over financial transaction records powered by `langchain-db2` and native Db2 `VECTOR(384, FLOAT32)`.
2. **Controlled Financial Intelligence**: Grounded financial assistant with 9 parameterized database tools that directly query IBM Db2.
3. **Explainable Anomaly Triage**: Deterministic statistical outlier identification and LLM narrative explanation.
4. **FastAPI Endpoints**: Fully typed REST API with Pydantic request/response schemas and internal service authentication.

---

## Architecture

```
[ Incoming Request ]
         │
         ▼
[ FastAPI App (main.py) ]
   ├── Authentication Middleware (Service Token)
   ├── Routers:
   │     ├── /health & /health/db
   │     ├── /api/ai/chat (Assistant with Db2 Tools)
   │     ├── /api/ai/search (LangChain DB2VS Vector Search)
   │     ├── /api/ai/index-transactions (Vector Store Population)
   │     └── /api/ai/anomalies (Detection & Explanation)
   └── Services:
         ├── db.py (ibm_db connection management & pooling)
         ├── embeddings.py (384-dim semantic embeddings)
         ├── vector_store.py (LangChain DB2VS integration)
         ├── tools.py (Deterministic Db2 SQL analytical tools)
         ├── assistant.py (Evidence-grounded synthesis)
         └── anomaly_engine.py (Multi-factor anomaly calculation)
```

---

## Development & Deployment

The AI service is deployed via Docker Compose to guarantee zero C-driver DLL issues and seamless networking to the IBM Db2 database.
