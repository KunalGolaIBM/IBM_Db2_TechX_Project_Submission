# TECH STACK DECISION — Framework & Model Selection

**Date:** 30 October 2026 (IST) — Milestone M0 (research only, no implementation)
**Decision owner:** Individual Db2Hack submission

Verification legend: ✅ officially verified / ⚠️ technical finding / 💡 recommendation / ❓ unresolved.

---

## 1. Mandatory Constraint Recap

- At least one of **LangChain, Haystack, CrewAI, LlamaIndex, Langflow** must be used (✅ website FAQ — mandatory).
- Code must genuinely integrate **IBM Db2** (✅).
- Approved LLM providers: watsonx.ai, OpenAI, Gemini, OpenRouter, **Ollama** (✅). AI itself is optional but strongly rewarded by the rubric ("Technical architecture & AI").
- Local reality (✅ `ENVIRONMENT_AUDIT.md`): Python **3.14.2**, no Ollama installed yet, Docker installed but daemon off, 16 GB RAM (~4.5 GB free), C: drive nearly full (3.4 GB), E: drive has 123 GB free.

## 2. Framework Comparison (for *our* use case: RAG + agentic QA over Db2, local models, solo hackathon build)

| Criterion | **LangChain** (`langchain-db2`) | **Haystack** (`ibm-db-haystack`) | **CrewAI** (`crewai-tools`+`ibm_db`) | **LlamaIndex** (`llama-index-vector-stores-db2`) | **Langflow** (`lfx-ibm`) |
|---|---|---|---|---|---|
| Db2 official integration | ✅ `DB2VS` vector store (langchain-ai/langchain-ibm monorepo, maintained by `langchain` org) | ✅ Db2 document store | ✅ `DB2SearchTool` vector search tool for agents | ✅ Db2 vector store (v0.1.0 — very young) | ✅ No-code Db2 vector store component (IBM bundle) |
| Works on local Python 3.14 | ✅ (`>=3.10,<4.0`; ibm_db 3.3.0 has cp314 win wheel) | ✅ (`>=3.11`) | ❌ (`crewai-tools <3.14`) — needs separate 3.12 venv | ❌ (`<3.13`) — needs separate 3.12 venv | ✅ (`lfx-ibm <3.16`) |
| RAG capabilities | ✅ Mature: splitters, retrievers, chains, LCEL, LangGraph for agentic RAG | ✅ Good pipelines (extractor→embedder→retriever→reader) | ⚠️ Agent-centric; RAG possible via tools | ✅ Strong RAG heritage | ⚠️ Visual prototyping; weaker for code-reviewed, testable submission |
| Ollama integration | ✅ `langchain-ollama` **already installed locally** (v1.1.0) + `ChatOllama`, `OllamaEmbeddings` | ✅ `haystack-ollama` integration exists | ⚠️ via `ollama` client or LiteLLM | ✅ `llama-index-llms-ollama` / embedders | ⚠️ Ollama components exist in Langflow but version-sensitive |
| Embedding support | ✅ `HuggingFaceEmbeddings` (official site worked example) or `OllamaEmbeddings(nomic-embed-text)` | ✅ SentenceTransformers / Ollama embedders | ⚠️ mostly retrieval-side | ✅ | ⚠️ node-based |
| Dev complexity (solo, ~days) | Low-medium — huge docs, canonical code-first path | Low-medium — pipeline boilerplate more verbose | Medium — agent loops add moving parts | Low-medium | Low for prototype, **high to make production-grade/reviewable** |
| Documentation quality | ✅ Best: official IBM worked example **on the summit site itself uses `langchain_db2.db2vs.DB2VS`** + LangChain docs page + IBM announcement | ✅ Good (PyPI + official tutorial video `T3it5_2JwIw`) | ✅ Good (docs + tutorial video `qZnhCnwGttg`) | ⚠️ Connector is 0.1.0, docs thinner | ✅ Tutorial video `NRo4ePT2MEE` |
| Runtime resource use | Low (library only; LLM runs in Ollama) | Low | Medium (crew process overhead) | Low | High (Node + React server, ports, memory) |
| Demo ease | ✅ CLI + small FastAPI/Gradio UI | ✅ | ✅ impressive agent demo but flakier | ✅ | ✅ visually impressive live flow |
| Fits judging "Reproducibility" | ✅ pip-install + script | ✅ | ⚠️ version/venv friction hurts "easy setup" | ⚠️ same | ⚠️ heavy environment |
| Risk of "generic chatbot" perception | Medium — mitigated by hybrid design (see §5) | Medium | High (agents demos look samey) | Medium | Medium |

## 3. Decision: **LangChain (primary) + LangGraph-style agentic step only if time permits**

**Rationale (evidence-based, not popularity-based):**

1. **Only framework whose Db2 connector the organizers themselves demo in code.** The official summit site's worked example (`/submit` quick-start) is literally `pip install -U langchain-db2 …` + `DB2VS.from_documents(...)` + `similarity_search(...)`. Mirroring the canonical pattern minimizes integration risk and matches what judges will recognize as "correct framework integration" (rubric: "Correct drivers, connectors or framework integrations"). ✅
2. **Zero interpreter friction on this machine.** `langchain-db2 1.0.0` supports Python `>=3.10,<4.0` and `ibm_db 3.3.0` ships a cp314 Windows wheel — both installable on the existing Python 3.14.2. CrewAI and LlamaIndex connectors are hard-blocked by `requires_python` caps. ✅ (PyPI)
3. **Ollama glue already present locally**: `langchain-ollama 1.1.0` + `ollama 0.6.2` client are installed. Swapping `ChatOllama`/`OllamaEmbeddings` in/out of a LangChain app is a one-line change (also lets us fall back to watsonx.ai/OpenAI if Ollama underperforms). ✅
4. **Best documentation density**: LangChain docs page listed in the official resource grid + IBM announcement ("Announcing the Db2 LangChain Connector — enterprise vector storage for Python AI workflows") + the site's example code. ✅
5. **Deepest Db2 story with least code**: DB2VS gives vector persistence *in Db2* (not a side-car vector DB), satisfying the "Db2 is the vector store" guidance and the 25–30% Db2-depth criterion. 💡

**Secondary/optional:** if time allows, add a **CrewAI agent** in a `uv`-managed Python 3.12 venv purely as a demo variant — *not planned by default* (venv friction + RAM). Langflow is deliberately **rejected** as primary: its strength (visual building) is invisible to judges reviewing a code submission, and it increases the reproducibility surface (long-running GUI server) for a solo build.

**Haystack** remains the fallback if `DB2VS` proves buggy on Db2 Community Edition — `ibm-db-haystack 1.0.0` is also Python-3.14-clean, so the fallback costs no environment work. ❓ (contingency, untested)

## 4. Model Selection

| Role | Choice | Verified identity | Size / footprint | Rationale |
|---|---|---|---|---|
| Generator LLM | **`granite4.2:3b`** (Ollama) | ✅ https://ollama.com/library/granite4.2 — tag `3b` exists | 2.2 GB, 128K ctx, Apache-2.0 | IBM's own Granite family = perfect summit alignment (IBM event, IBM model, IBM DB). Supports RAG, tool use, JSON output. 3B is the only size that fits ~4.5 GB free RAM alongside Db2. 8B (5.3 GB) / 30b (18 GB) are not viable here. ⚠️ |
| Embeddings | **`nomic-embed-text:v1.5`** (Ollama) | ✅ https://ollama.com/library/nomic-embed-text — tag `v1.5` exists (= `latest`) | 274 MB, **2K ctx**, embedding-only | Proven, tiny, standard RAG embedding. ⚠️ 2K token context: chunk sizes must stay well under that (e.g., 300–800 tokens). |
| Embeddings (alt) | `sentence-transformers/all-mpnet-base-v2` | ✅ used in the organizers' own worked example | ~400 MB HF download | Fallback if Ollama embedding latency is bad; keeps generator on Granite. 💡 |

⚠️ Both Ollama models must still be **installed and downloaded** in M1 (~2.5 GB — put `OLLAMA_MODELS` on E:, not C:). Neither is currently present. Inference speed on this CPU (6C/12T) is **unmeasured** — first M1 task after provisioning. ❓

## 5. Stack Summary (proposed, pending M1 validation)

```
Language:      Python 3.14.2 (existing interpreter — no new venv needed)
Framework:     LangChain 1.x  +  langchain-db2 (DB2VS)  +  langchain-ollama
Driver:        ibm_db 3.3.0 (cp314 win wheel)  [under DB2VS via ibm_db_dbi]
Database:      IBM Db2 Community Edition (Docker image icr.io/db2_community/db2)
               provisioned via VS Code IBM Db2 Developer Extension "Create Db2 instance"
               or plain docker run — final route decided in M1
Embeddings:    nomic-embed-text:v1.5 via Ollama   (alt: sentence-transformers)
Generator:     granite4.2:3b via Ollama           (alt: watsonx.ai Granite)
App surface:   FastAPI backend + minimal web UI (details in PROPOSED_ARCHITECTURE.md)
Submission:    GitHub PR to KunalGolaIBM/IBM_Db2_TechX_Project_Submission
```

**Explicit non-goals for the stack:** no CrewAI/LlamaIndex/Langflow (friction vs. reward), no cloud DB (local CE is reproducible and free), no extra vector DB (Db2 *is* the vector store — that's the point of the hackathon).
