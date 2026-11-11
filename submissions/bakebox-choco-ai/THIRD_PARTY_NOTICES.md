# Original Authorship & Third-Party Dependency License Declarations

## Original Work Statement
All application source code, IBM Db2 DDL/SQL scripts (`SP_RESERVE_CAKE_STOCK`, Recursive BOM CTE, RBAC roles), retrieval pipelines, FastAPI endpoints, UI playground, documentation, and test suites inside `submissions/bakebox-choco-ai/` are **100% original work** authored by **Ayush Dhangar ([@AYUSHDHANGAR](https://github.com/AYUSHDHANGAR))** for **IBM Db2Hack 2026**, copyright (c) 2026 Ayush Dhangar under the [MIT License](LICENSE).

## Declared External Open-Source Packages & Model Licenses
In accordance with the IBM Db2Hack 2026 submission requirement (*"Follow the Code of Conduct and declare third-party licences"*), the external runtime Python packages (from `requirements.txt`) and pre-trained embedding model used by this project are declared below:

| External Dependency / Model | Usage Scope | License |
| :--- | :--- | :--- |
| `ibm-db` (IBM) | Official IBM Db2 Python CLI / DB-API 2.0 driver | Apache-2.0 |
| `llama-index-core` | RAG orchestration abstractions | MIT |
| `llama-index-vector-stores-db2` | IBM Db2 `VECTOR` store connector (`DB2LlamaVS`) | MIT |
| `fastapi` & `uvicorn` | Asynchronous REST API server & ASGI runner | MIT / BSD-3-Clause |
| `pydantic` | Request/response schema validation | MIT |
| `scikit-learn` & `numpy` | TF-IDF lexical retrieval & numerical array operations | BSD-3-Clause |
| `fastembed` (Qdrant) | Local ONNX sentence embedding inference | Apache-2.0 |
| `BAAI/bge-small-en-v1.5` | 384-dimensional pre-trained text embedding model | MIT |
| `google-genai` | Optional Google Gemini LLM synthesis SDK | Apache-2.0 |
| `python-dotenv` | `.env` configuration loader | BSD-3-Clause |
| `httpx` & `pytest` | HTTP client testing & test runner | BSD-3-Clause / MIT |
